import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.config import get_settings
from app.database import DatabaseNotConfigured, check_database

logger = logging.getLogger("wasteflow")
settings = get_settings()

app = FastAPI(title="WasteFlow AI", version="0.2.0", description="From waste data to the next collection decision.")

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


app.include_router(router)
