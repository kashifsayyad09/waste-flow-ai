"""Static bearer-token authentication for the HTTP transport (pure ASGI, constant-time compare)."""
import hmac

from starlette.types import ASGIApp, Receive, Scope, Send


class BearerTokenMiddleware:
    def __init__(self, app: ASGIApp, token: str):
        if not token:
            raise ValueError("a bearer token is required")
        self.app = app
        self._expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            supplied = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self._expected):
                await send({"type": "http.response.start", "status": 401, "headers": [
                    (b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b'{"error":"unauthorized"}'})
                return
        elif scope["type"] == "websocket":
            # The MCP transport is plain HTTP; refuse any websocket upgrade instead of letting it bypass auth.
            await send({"type": "websocket.close", "code": 1008})
            return
        await self.app(scope, receive, send)
