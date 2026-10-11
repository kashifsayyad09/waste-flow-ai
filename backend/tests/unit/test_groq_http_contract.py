"""The REAL groq SDK against a local fake Groq server: request format, auth, error mapping."""
import asyncio

import pytest

from app.ai.errors import AIError
from app.ai.groq_service import GroqService
from tests.conftest import make_ai_settings
from tests.helpers.fake_groq_server import FakeGroqServer


@pytest.fixture(scope="module")
def server():
    s = FakeGroqServer().start()
    yield s
    s.stop()


@pytest.fixture
def svc(server):
    server.mode = "chat"
    server.requests.clear()
    server.headers.clear()
    return GroqService(make_ai_settings(groq_base_url=server.base_url))


def run(coro):
    return asyncio.run(coro)


def test_request_uses_configured_model_key_and_tools(svc, server):
    tools = [{"type": "function", "function": {"name": "get_critical_bins", "description": "d", "parameters": {"type": "object", "properties": {}}}}]
    c = run(svc.complete("text", [{"role": "user", "content": "hi"}], tools=tools))
    sent = server.requests[0]
    assert sent["model"] == "test-text-model" and sent["tools"] == tools and sent["tool_choice"] == "auto"
    assert server.headers[0]["authorization"] == "Bearer gsk_test_key_not_real"
    assert c.tool_calls and c.tool_calls[0].name == "get_critical_bins" and c.model == "test-text-model"


def test_vision_requests_use_the_vision_model(svc, server):
    server.mode = "classify"
    msg = [{"role": "user", "content": [{"type": "text", "text": "x"}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}]}]
    c = run(svc.complete("vision", msg, max_tokens=300, temperature=0.0))
    assert server.requests[0]["model"] == "test-vision-model" and "organic" in c.content


@pytest.mark.parametrize("mode,code,status", [("unauthorized", "ai_auth_failed", 502), ("rate_limit", "ai_rate_limited", 429),
                                              ("bad_request", "ai_model_unsupported", 502), ("server_error", "ai_provider_unavailable", 502)])
def test_provider_errors_are_mapped_and_sanitised(svc, server, mode, code, status):
    server.mode = mode
    with pytest.raises(AIError) as e:
        run(svc.complete("text", [{"role": "user", "content": "hi"}]))
    assert e.value.code == code and e.value.status_code == status
    for leaked in ("Invalid API Key", "Rate limit reached", "boom", "gsk_test_key_not_real", "does not support image"):
        assert leaked not in e.value.message
    if mode == "rate_limit":
        assert e.value.retry_after == 7


def test_timeout_is_mapped(server):
    server.mode = "slow"
    svc = GroqService(make_ai_settings(groq_base_url=server.base_url, groq_timeout_seconds=0.5))
    with pytest.raises(AIError) as e:
        run(svc.complete("text", [{"role": "user", "content": "hi"}]))
    assert e.value.code == "ai_timeout" and e.value.status_code == 504


def test_connection_failure_is_mapped():
    svc = GroqService(make_ai_settings(groq_base_url="http://127.0.0.1:1"))
    with pytest.raises(AIError) as e:
        run(svc.complete("text", [{"role": "user", "content": "hi"}]))
    assert e.value.code == "ai_provider_unavailable"


def test_missing_model_or_key_is_not_configured_and_makes_no_request(server):
    server.requests.clear()
    for settings in (make_ai_settings(groq_text_model="", groq_base_url=server.base_url), make_ai_settings(groq_api_key="", groq_base_url=server.base_url)):
        with pytest.raises(AIError) as e:
            run(GroqService(settings).complete("text", [{"role": "user", "content": "hi"}]))
        assert e.value.code == "ai_not_configured" and e.value.status_code == 503
    assert server.requests == []


def test_malformed_provider_response_is_rejected():
    class Bad:
        class chat:
            class completions:
                @staticmethod
                async def create(**kw):
                    class R:
                        choices = []
                    return R()

    svc = GroqService(make_ai_settings(), client=Bad())
    with pytest.raises(AIError) as e:
        run(svc.complete("text", [{"role": "user", "content": "hi"}]))
    assert e.value.code == "ai_bad_response"
