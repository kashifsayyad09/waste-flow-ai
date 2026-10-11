from functools import lru_cache

from fastapi import APIRouter, Depends, File, UploadFile
from starlette.concurrency import run_in_threadpool

from app.ai import assistant, classifier
from app.ai.errors import AIError, not_configured
from app.ai.groq_service import GroqService
from app.ai.mcp_client import MCPToolClient
from app.ai.rate_limit import rate_limit
from app.config import Settings, get_settings
from app.schemas.ai import AIStatus, ChatRequest, ChatResponse, ClassificationResult

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@lru_cache
def _groq_singleton() -> GroqService:
    return GroqService(get_settings())


def get_groq_service() -> GroqService:
    return _groq_singleton()


def get_mcp_client(settings: Settings = Depends(get_settings)) -> MCPToolClient:
    return MCPToolClient(settings)


@router.get("/status", response_model=AIStatus)
def ai_status(settings: Settings = Depends(get_settings)):
    """Which AI features are configured. Does not call Groq and never reveals secrets."""
    notes = []
    if not settings.groq_text_ready:
        notes.append("Set GROQ_API_KEY and GROQ_TEXT_MODEL to enable the assistant.")
    if not settings.mcp_ready:
        notes.append("Set MCP_SERVER_URL and MCP_API_TOKEN (and run the MCP server) to enable the assistant.")
    if not settings.groq_vision_ready:
        notes.append("Set GROQ_VISION_MODEL (a vision-capable model on your account) to enable photo classification.")
    return AIStatus(
        chat_available=settings.groq_text_ready and settings.mcp_ready,
        classification_available=settings.groq_vision_ready,
        text_model=settings.groq_text_model.strip() or None if settings.groq_text_ready else None,
        vision_model=settings.groq_vision_model.strip() or None if settings.groq_vision_ready else None,
        mcp_configured=settings.mcp_ready,
        notes=notes,
    )


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit)])
async def chat(
    body: ChatRequest,
    settings: Settings = Depends(get_settings),
    groq: GroqService = Depends(get_groq_service),
    mcp: MCPToolClient = Depends(get_mcp_client),
):
    if not settings.groq_text_ready:
        raise not_configured("The Groq text model (GROQ_API_KEY / GROQ_TEXT_MODEL)")
    if not settings.mcp_ready:
        raise not_configured("The MCP data service (MCP_SERVER_URL / MCP_API_TOKEN)")
    return await assistant.answer_question(body.message, groq, mcp, settings)


@router.post("/classify-waste", response_model=ClassificationResult, dependencies=[Depends(rate_limit)])
async def classify_waste(
    image: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    groq: GroqService = Depends(get_groq_service),
):
    if not settings.groq_vision_ready:
        raise not_configured("The Groq vision model (GROQ_API_KEY / GROQ_VISION_MODEL)")
    raw = await image.read(settings.upload_max_bytes + 1)  # never buffer more than the limit + 1 byte
    await image.close()
    if len(raw) > settings.upload_max_bytes:
        raise AIError("image_too_large", f"The image is larger than {settings.upload_max_bytes // (1024 * 1024)} MB.", 413)
    # Decoding/resizing is CPU work: keep it off the event loop. Validation errors surface from prepare_image.
    prepared = await run_in_threadpool(classifier.prepare_image, raw, image.content_type, settings.upload_max_bytes)
    return await classifier.classify_prepared(prepared, groq)
