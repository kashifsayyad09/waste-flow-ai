import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.ai.errors import AIError
from app.api.ai_routes import router as ai_router
from app.api.routes import router
from app.config import get_settings
from app.database import DatabaseNotConfigured, check_database

logger = logging.getLogger("wasteflow")
settings = get_settings()

app = FastAPI(title="WasteFlow AI", version="0.3.0", description="From waste data to the next collection decision.")

# CORS is configured here only; Nginx adds no CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
@app.exception_handler(DatabaseNotConfigured)
async def database_unavailable(_: Request, exc: Exception):
    # Log the type server-side; never send connection details to the client.
    logger.warning("Database error: %s", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.get("/health", tags=["system"])
def health():
    if check_database():
        return {"status": "ok", "database": "connected", "env": settings.app_env}
    return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "unreachable"})


@app.exception_handler(AIError)
async def ai_error_handler(_: Request, exc: AIError):
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return JSONResponse(status_code=exc.status_code, content={"detail": {"code": exc.code, "message": exc.message}}, headers=headers)


app.include_router(router)
app.include_router(ai_router)
