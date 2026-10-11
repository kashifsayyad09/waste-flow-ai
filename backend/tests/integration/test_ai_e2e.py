"""Full chain, no mocks inside the app:

  FastAPI /api/v1/ai/chat -> real GroqService (real groq SDK) -> local fake Groq HTTP server
                          -> real MCPToolClient -> real MCP server over HTTP (bearer auth) -> real MySQL -> priority engine

Only the Groq cloud itself is replaced (by tests/helpers/fake_groq_server.py).
"""
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mcp-server"))

from app.ai.groq_service import GroqService  # noqa: E402
from app.database import get_session_factory  # noqa: E402
from app.services import bin_service  # noqa: E402
from app.services.priority_engine import rank_bins  # noqa: E402
from tests.conftest import make_ai_settings  # noqa: E402
from tests.helpers.fake_groq_server import FakeGroqServer  # noqa: E402
from tests.unit.test_ai_classifier import img_bytes  # noqa: E402

pytestmark = pytest.mark.integration
TOKEN = "e2e-token-0123456789-0123456789-0123456789"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def mcp_url(database_available):
    if not database_available:
        pytest.skip("MySQL not configured/reachable")
    from wasteflow_mcp.app import create_app
    from wasteflow_mcp.config import MCPSettings

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(MCPSettings(_env_file=None, mcp_api_token=TOKEN, mcp_port=port)),
                                           host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True


@pytest.fixture(scope="module")
def fake_groq():
    s = FakeGroqServer().start()
    yield s
    s.stop()


@pytest.fixture
def chat(ai_client, fake_groq, mcp_url):
    fake_groq.mode, fake_groq.invented_id, fake_groq.chat_tool_args = "chat", None, {}
    fake_groq.requests.clear()

    def build(token=TOKEN, url=None):
        settings = make_ai_settings(groq_base_url=fake_groq.base_url, mcp_server_url=url or mcp_url, mcp_api_token=token)
        client = ai_client(settings, groq=GroqService(settings))
        return lambda msg="question": client.post("/api/v1/ai/chat", json={"message": msg})

    return build


def db_ranked():
    with get_session_factory()() as db:
        return rank_bins(bin_service.list_bins(db))


def test_critical_bins_answer_matches_database_and_engine(chat, fake_groq):
    fake_groq.chat_tool = "get_critical_bins"
    r = chat()("Which bins are critical?")
    body = r.json()
    expected = [(b.id, p.priority_score, p.priority_level) for b, p in db_ranked() if p.priority_level == "CRITICAL"]
    assert r.status_code == 200 and body["data_status"] == "verified" and body["tools_used"] == ["get_critical_bins"]
    assert [(x["bin_id"], x["priority_score"], x["priority_level"]) for x in body["referenced_bins"]] == expected
    for bin_id, score, _ in expected:
        assert f"{bin_id} has priority {score}" in body["answer"]


def test_top_three_uses_tool_arguments_and_engine_order(chat, fake_groq):
    fake_groq.chat_tool, fake_groq.chat_tool_args = "list_bins_by_priority", {"limit": 3}
    body = chat()("Which three bins first?").json()
    expected = [(b.id, p.priority_score) for b, p in db_ranked()[:3]]
    assert [(x["bin_id"], x["priority_score"]) for x in body["referenced_bins"]] == expected


def test_explanation_for_a_single_bin(chat, fake_groq):
    ranked = db_ranked()
    target, prio = ranked[0]
    fake_groq.chat_tool, fake_groq.chat_tool_args = "get_bin_priority_explanation", {"bin_id": target.id}
    body = chat()(f"Why is {target.id} urgent?").json()
    assert body["data_status"] == "verified"
    assert body["referenced_bins"][0]["bin_id"] == target.id and body["referenced_bins"][0]["priority_score"] == prio.priority_score


def test_unknown_bin_is_reported_as_unverified(chat, fake_groq):
    fake_groq.chat_tool, fake_groq.chat_tool_args = "get_bin_details", {"bin_id": "NO-SUCH-BIN"}
    body = chat()("Tell me about NO-SUCH-BIN").json()
    assert body["data_status"] == "partial" and "could not verify" in body["answer"] and body["referenced_bins"] == []


def test_invented_bin_id_from_the_model_is_blocked(chat, fake_groq):
    fake_groq.chat_tool, fake_groq.invented_id = "get_critical_bins", "BIN-777"
    body = chat()("critical?").json()
    assert "BIN-777" not in body["answer"] and body["data_status"] == "partial"


def test_invalid_tool_arguments_from_the_model_are_rejected_by_the_mcp_server(chat, fake_groq):
    fake_groq.chat_tool, fake_groq.chat_tool_args = "list_bins_by_priority", {"limit": 9999}
    body = chat()("everything").json()
    assert body["data_status"] == "partial" and body["referenced_bins"] == []


def test_wrong_mcp_token_means_unavailable_and_groq_is_never_called(chat, fake_groq):
    body = chat(token="x" * 40)("critical?").json()
    assert body["status"] == "unavailable" and body["data_status"] == "unavailable" and fake_groq.requests == []


def test_mcp_server_down_means_unavailable(chat):
    body = chat(url=f"http://127.0.0.1:{_free_port()}/mcp")("critical?").json()
    assert body["status"] == "unavailable" and "couldn't verify" in body["answer"]


def test_provider_errors_reach_the_user_safely(chat, fake_groq):
    for mode, status, code in [("rate_limit", 429, "ai_rate_limited"), ("unauthorized", 502, "ai_auth_failed"), ("server_error", 502, "ai_provider_unavailable")]:
        fake_groq.mode = mode
        r = chat()("critical?")
        assert r.status_code == status and r.json()["detail"]["code"] == code
        assert "gsk_" not in r.text and "Invalid API Key" not in r.text


def test_classification_through_real_sdk(ai_client, fake_groq):
    fake_groq.mode, fake_groq.requests = "classify", []
    settings = make_ai_settings(groq_base_url=fake_groq.base_url)
    client = ai_client(settings, groq=GroqService(settings))
    with client:  # one event loop for both requests, as in production (the SDK's HTTP pool is loop-bound)
        r = client.post("/api/v1/ai/classify-waste", files={"image": ("p.jpg", img_bytes(size=(300, 200)), "image/jpeg")})
        assert r.status_code == 200 and r.json()["category"] == "organic" and r.json()["confidence"] is None
        sent = fake_groq.requests[0]
        assert sent["model"] == "test-vision-model"
        assert sent["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        fake_groq.mode = "bad_request"
        r = client.post("/api/v1/ai/classify-waste", files={"image": ("p.jpg", img_bytes(size=(300, 200)), "image/jpeg")})
        assert r.status_code == 502 and r.json()["detail"]["code"] == "ai_model_unsupported"
