"""
Health check endpoints for voice service.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from ai_core import get_logger

from ..config import get_voice_config

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """
    Liveness probe - checks if service is running.
    """
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """
    Readiness probe - checks if service is ready to handle requests.
    """
    config = get_voice_config()

    checks = {
        "openai_configured": bool(config.openai_api_key),
    }

    is_ready = all(checks.values())

    return {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/health")
async def health() -> dict[str, Any]:
    """
    Combined health check endpoint.
    """
    config = get_voice_config()

    return {
        "status": "healthy",
        "service": "voice-service",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "whisper_model": config.whisper_model,
            "tts_model": config.tts_model,
            "tts_voice": config.tts_voice,
            "max_audio_size_mb": config.max_audio_size_mb,
        },
    }
