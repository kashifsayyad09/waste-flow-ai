"""Thin, safe wrapper around the Groq API.

Never logs or returns the API key, request bodies or raw provider error text.
Model names come from configuration; nothing is hardcoded.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import groq

from app.ai.errors import AIError, not_configured
from app.config import Settings

logger = logging.getLogger("wasteflow.ai.groq")

ModelKind = Literal["text", "vision"]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string produced by the model; validated by the caller


@dataclass(frozen=True)
class Completion:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""


class GroqService:
    def __init__(self, settings: Settings, client: Any | None = None):
        self._settings = settings
        self._client = client

    def _model_for(self, kind: ModelKind) -> str:
        s = self._settings
        if kind == "text":
            if not s.groq_text_ready:
                raise not_configured("The Groq text model (GROQ_API_KEY / GROQ_TEXT_MODEL)")
            return s.groq_text_model.strip()
        if not s.groq_vision_ready:
            raise not_configured("The Groq vision model (GROQ_API_KEY / GROQ_VISION_MODEL)")
        return s.groq_vision_model.strip()

    def _get_client(self) -> Any:
        if self._client is None:
            kwargs: dict[str, Any] = {}
            if self._settings.groq_base_url.strip():
                kwargs["base_url"] = self._settings.groq_base_url.strip()
            self._client = groq.AsyncGroq(
                api_key=self._settings.groq_api_key.get_secret_value(),
                timeout=self._settings.groq_timeout_seconds,
                max_retries=self._settings.groq_max_retries,
                **kwargs,
            )
        return self._client

    async def complete(
        self,
        kind: ModelKind,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        max_tokens: int = 700,
        temperature: float = 0.1,
    ) -> Completion:
        model = self._model_for(kind)
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            response = await self._get_client().chat.completions.create(**kwargs)
        except groq.APITimeoutError as exc:
            raise self._fail("ai_timeout", "The AI provider took too long to respond. Please try again.", 504, exc)
        except groq.APIConnectionError as exc:
            raise self._fail("ai_provider_unavailable", "The AI provider could not be reached. Please try again later.", 502, exc)
        except groq.RateLimitError as exc:
            retry = _retry_after(exc)
            raise self._fail("ai_rate_limited", "The AI provider rate limit was reached. Please wait a moment and try again.", 429, exc, retry)
        except (groq.AuthenticationError, groq.PermissionDeniedError) as exc:
            raise self._fail("ai_auth_failed", "The server's AI credentials were rejected by the provider. Contact the administrator.", 502, exc)
        except (groq.BadRequestError, groq.NotFoundError, groq.UnprocessableEntityError) as exc:
            raise self._fail(
                "ai_model_unsupported",
                "The configured AI model is unavailable or does not support this request. Contact the administrator.",
                502,
                exc,
            )
        except groq.APIStatusError as exc:
            raise self._fail("ai_provider_unavailable", "The AI provider returned an error. Please try again later.", 502, exc)
        return _normalize(response, model)

    @staticmethod
    def _fail(code: str, message: str, status: int, exc: Exception, retry_after: int | None = None) -> AIError:
        # Log only the exception type / HTTP status: never the body (it may echo prompt content).
        logger.warning("Groq call failed: %s (status=%s)", type(exc).__name__, getattr(exc, "status_code", None))
        return AIError(code, message, status, retry_after)


def _retry_after(exc: Exception) -> int | None:
    try:
        value = exc.response.headers.get("retry-after")  # type: ignore[attr-defined]
        return max(1, min(int(float(value)), 120)) if value else None
    except Exception:  # noqa: BLE001
        return None


def _normalize(response: Any, model: str) -> Completion:
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        raise AIError("ai_bad_response", "The AI provider returned an unreadable response.", 502) from None
    calls = []
    for tc in getattr(message, "tool_calls", None) or []:
        try:
            calls.append(ToolCall(id=str(tc.id), name=str(tc.function.name), arguments=str(tc.function.arguments or "{}")))
        except AttributeError:
            raise AIError("ai_bad_response", "The AI provider returned a malformed tool call.", 502) from None
    content = getattr(message, "content", None)
    return Completion(content=content if isinstance(content, str) else None, tool_calls=calls, model=model)
