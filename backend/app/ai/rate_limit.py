"""Tiny in-memory per-client limiter for the (costly) AI endpoints. Per process, not shared across workers."""
import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from app.ai.errors import AIError
from app.config import Settings, get_settings

_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(request: Request, settings: Settings = Depends(get_settings)) -> None:
    limit = settings.ai_rate_limit_per_minute
    if limit <= 0:
        return
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _hits[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise AIError("rate_limited", "Too many AI requests. Please wait a minute and try again.", 429, retry_after=int(60 - (now - window[0])) + 1)
    window.append(now)


def reset() -> None:
    _hits.clear()
