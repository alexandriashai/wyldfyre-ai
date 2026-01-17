"""
Voice Service FastAPI application.

Provides endpoints for speech-to-text (transcription) and text-to-speech (synthesis).
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_core import configure_logging, get_logger, get_settings

from .config import VoiceConfig, get_voice_config
from .routes import health_router, synthesize_router, transcribe_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting Voice Service...")

    # Configure logging
    settings = get_settings()
    configure_logging(
        log_level=settings.logging.level,
        log_format=settings.logging.format,
    )

    logger.info("Voice Service started")

    yield

    logger.info("Shutting down Voice Service...")
    logger.info("Voice Service stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_voice_config()

    app = FastAPI(
        title="AI Infrastructure Voice Service",
        description="Speech-to-Text and Text-to-Speech API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(transcribe_router, prefix="/api")
    app.include_router(synthesize_router, prefix="/api")

    return app


# Create application instance
app = create_app()


def main() -> None:
    """Run the voice service."""
    import uvicorn

    config = get_voice_config()

    uvicorn.run(
        "voice_service.main:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
        log_level="info" if not config.debug else "debug",
    )


if __name__ == "__main__":
    main()
