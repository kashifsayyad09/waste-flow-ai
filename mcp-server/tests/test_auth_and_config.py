"""Bearer authentication, Host validation, and refusal to start with a weak token."""
import asyncio

import pytest
from starlette.testclient import TestClient

from wasteflow_mcp.app import create_app
from wasteflow_mcp.auth import BearerTokenMiddleware
from wasteflow_mcp.config import MCPSettings

TOKEN = "a-very-long-random-token-0123456789-abcdef"


def settings(**kw) -> MCPSettings:
    return MCPSettings(_env_file=None, mcp_api_token=kw.pop("token", TOKEN), **kw)


@pytest.mark.parametrize("token,expected", [("", "not set"), ("<MCP_API_TOKEN_32_PLUS_RANDOM_CHARS>", "not set"), ("short", "at least 32")])
def test_weak_or_placeholder_tokens_are_refused(token, expected):
    s = settings(token=token)
    assert expected in s.token_problem()
    with pytest.raises(RuntimeError):
        create_app(s)


def test_strong_token_is_accepted_and_hidden():
    s = settings()
    assert s.token_problem() is None and TOKEN not in repr(s)


def test_defaults_bind_loopback_only():
    s = settings()
    assert s.mcp_host == "127.0.0.1" and s.mcp_port == 8001
    assert "evil.example:8001" not in s.allowed_hosts and "127.0.0.1:8001" in s.allowed_hosts


def test_extra_allowed_host_is_added_with_port():
    assert "mcp.internal:8001" in settings(mcp_allowed_hosts="mcp.internal").allowed_hosts


def test_middleware_rejects_missing_wrong_and_lookalike_tokens():
    sent = []

    async def inner(scope, receive, send):
        sent.append("reached")

    mw = BearerTokenMiddleware(inner, TOKEN)

    async def attempt(headers):
        out = []

        async def send(msg):
            out.append(msg)

        await mw({"type": "http", "headers": headers}, None, send)
        return out[0]["status"] if out else None

    for headers in ([], [(b"authorization", b"Bearer wrong")], [(b"authorization", TOKEN.encode())],
                    [(b"authorization", f"bearer {TOKEN}".encode())], [(b"authorization", f"Bearer {TOKEN} ".encode())]):
        assert asyncio.run(attempt(headers)) == 401
    assert sent == []
    asyncio.run(attempt([(b"authorization", f"Bearer {TOKEN}".encode())]))
    assert sent == ["reached"]


def test_http_app_requires_token_and_valid_host():
    app = create_app(settings())
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        assert client.post("/mcp", json={}).status_code == 401
        assert client.get("/mcp").status_code == 401
        assert client.post("/mcp", json={}, headers={"Authorization": "Bearer nope"}).status_code == 401
        authed = client.post("/mcp", json={}, headers={"Authorization": f"Bearer {TOKEN}"})
        assert authed.status_code != 401  # passes auth (the empty JSON body is then rejected by MCP itself)
        evil = client.post("/mcp", json={}, headers={"Authorization": f"Bearer {TOKEN}", "Host": "evil.example"})
        assert evil.status_code in (400, 403, 421)  # DNS-rebinding protection
