"""AI configuration validation, request validation and HTTP error mapping (no network, no database)."""
import pytest

from app.ai.errors import AIError
from app.config import Settings
from tests.conftest import make_ai_settings
from tests.helpers.fakes import BIN_004, CRITICAL, FakeMCP, ScriptedGroq, call, say, tool_call


def test_settings_readiness_and_placeholders():
    s = Settings(_env_file=None)
    assert not s.groq_text_ready and not s.groq_vision_ready and not s.mcp_ready
    placeholders = Settings(_env_file=None, groq_api_key="<GROQ_API_KEY>", groq_text_model="<GROQ_TEXT_MODEL>",
                            groq_vision_model="<GROQ_VISION_MODEL>", mcp_server_url="http://x/mcp", mcp_api_token="<MCP_API_TOKEN>")
    assert not placeholders.groq_text_ready and not placeholders.groq_vision_ready and not placeholders.mcp_ready
    ok = make_ai_settings()
    assert ok.groq_text_ready and ok.groq_vision_ready and ok.mcp_ready
    # a key without a model is not "ready": model names are never hardcoded
    assert not make_ai_settings(groq_text_model="").groq_text_ready


def test_secrets_never_appear_in_repr():
    s = make_ai_settings()
    assert "gsk_test_key_not_real" not in repr(s) and ("t" * 40) not in repr(s)


def test_status_reports_without_revealing_secrets(ai_client):
    r = ai_client(make_ai_settings()).get("/api/v1/ai/status")
    body = r.json()
    assert r.status_code == 200 and body["chat_available"] and body["classification_available"]
    assert "gsk_test_key_not_real" not in r.text and ("t" * 40) not in r.text
    r = ai_client(Settings(_env_file=None)).get("/api/v1/ai/status")
    assert r.json()["chat_available"] is False and r.json()["notes"]


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "   "}, {"message": "x" * 501}, {"message": 5}, {"msg": "hi"}])
def test_chat_rejects_invalid_requests(ai_client, payload):
    assert ai_client().post("/api/v1/ai/chat", json=payload).status_code == 422


def test_chat_not_configured_is_503_with_code(ai_client):
    for settings in (Settings(_env_file=None), make_ai_settings(mcp_api_token="")):
        r = ai_client(settings, groq=ScriptedGroq(), mcp=FakeMCP()).post("/api/v1/ai/chat", json={"message": "hi"})
        assert r.status_code == 503 and r.json()["detail"]["code"] == "ai_not_configured"


def test_classify_not_configured_is_503(ai_client):
    r = ai_client(make_ai_settings(groq_vision_model="")).post("/api/v1/ai/classify-waste", files={"image": ("a.jpg", b"x", "image/jpeg")})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "ai_not_configured"


@pytest.mark.parametrize("code,status,retry", [("ai_rate_limited", 429, 7), ("ai_timeout", 504, None), ("ai_auth_failed", 502, None),
                                               ("ai_provider_unavailable", 502, None), ("ai_model_unsupported", 502, None)])
def test_provider_failures_become_safe_http_errors(ai_client, code, status, retry):
    groq = ScriptedGroq(AIError(code, "Safe message", status, retry))
    r = ai_client(groq=groq, mcp=FakeMCP({"get_critical_bins": lambda a: CRITICAL})).post("/api/v1/ai/chat", json={"message": "critical?"})
    assert r.status_code == status and r.json() == {"detail": {"code": code, "message": "Safe message"}}
    if retry:
        assert r.headers["retry-after"] == str(retry)


def test_chat_endpoint_happy_path_is_grounded(ai_client):
    groq = ScriptedGroq(call(tool_call("get_critical_bins")), say("BIN-004 is critical with score 97."))
    r = ai_client(groq=groq, mcp=FakeMCP({"get_critical_bins": lambda a: CRITICAL})).post("/api/v1/ai/chat", json={"message": "What is critical?"})
    body = r.json()
    assert r.status_code == 200 and body["data_status"] == "verified" and body["tools_used"] == ["get_critical_bins"]
    assert body["referenced_bins"] == [{"bin_id": "BIN-004", "priority_score": 97, "priority_level": "CRITICAL"}]


def test_ai_rate_limit_returns_429(ai_client):
    client = ai_client(make_ai_settings(ai_rate_limit_per_minute=2), groq=ScriptedGroq(*[say("hello")] * 5), mcp=FakeMCP())
    codes = [client.post("/api/v1/ai/chat", json={"message": "hi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
