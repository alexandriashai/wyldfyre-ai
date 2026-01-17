"""
Voice service configuration.
"""

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class VoiceConfig(BaseSettings):
    """Voice service configuration."""

    # Server settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    debug: bool = Field(default=False)
    reload: bool = Field(default=False)

    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # OpenAI settings
    openai_api_key: str = Field(default="")

    # Whisper settings (Speech-to-Text)
    whisper_model: str = Field(default="whisper-1")
    whisper_language: str | None = Field(default=None)  # Auto-detect if None
    max_audio_size_mb: int = Field(default=25)

    # TTS settings (Text-to-Speech)
    tts_model: str = Field(default="tts-1")
    tts_voice: str = Field(default="alloy")  # alloy, echo, fable, onyx, nova, shimmer
    tts_speed: float = Field(default=1.0, ge=0.25, le=4.0)
    tts_response_format: str = Field(default="mp3")  # mp3, opus, aac, flac, wav, pcm

    # Audio processing
    temp_audio_dir: str = Field(default="/tmp/voice_service")
    cleanup_interval_seconds: int = Field(default=300)  # 5 minutes

    class Config:
        env_prefix = "VOICE_"
        env_file = ".env"


@lru_cache
def get_voice_config() -> VoiceConfig:
    """Get cached voice configuration."""
    return VoiceConfig()
