"""Errors raised by the AI layer. Messages are safe to show to users (no secrets, no provider internals)."""


class AIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 502, retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


def not_configured(what: str) -> AIError:
    return AIError("ai_not_configured", f"{what} is not configured on the server.", 503)
