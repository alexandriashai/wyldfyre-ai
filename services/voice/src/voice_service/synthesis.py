"""
Text-to-Speech synthesis service using OpenAI TTS.
"""

import asyncio
import io
from typing import AsyncIterator, Literal

from openai import AsyncOpenAI

from ai_core import get_logger

from .config import get_voice_config

logger = get_logger(__name__)

# Available TTS voices
VoiceType = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
AudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


class SynthesisService:
    """Service for synthesizing text to speech using OpenAI TTS."""

    AVAILABLE_VOICES: list[VoiceType] = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    AVAILABLE_FORMATS: list[AudioFormat] = ["mp3", "opus", "aac", "flac", "wav", "pcm"]

    def __init__(self) -> None:
        self.config = get_voice_config()
        self.client = AsyncOpenAI(api_key=self.config.openai_api_key)

    async def synthesize(
        self,
        text: str,
        voice: VoiceType | None = None,
        speed: float | None = None,
        response_format: AudioFormat | None = None,
        model: str | None = None,
    ) -> bytes:
        """
        Synthesize text to speech audio.

        Args:
            text: Text to convert to speech (max 4096 characters)
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            speed: Speaking speed (0.25 to 4.0)
            response_format: Audio format (mp3, opus, aac, flac, wav, pcm)
            model: TTS model (tts-1 or tts-1-hd)

        Returns:
            Audio data as bytes
        """
        # Validate text length
        if len(text) > 4096:
            raise ValueError("Text exceeds maximum length of 4096 characters")

        if not text.strip():
            raise ValueError("Text cannot be empty")

        # Use defaults from config if not specified
        voice = voice or self.config.tts_voice  # type: ignore
        speed = speed if speed is not None else self.config.tts_speed
        response_format = response_format or self.config.tts_response_format  # type: ignore
        model = model or self.config.tts_model

        # Validate parameters
        if voice not in self.AVAILABLE_VOICES:
            raise ValueError(f"Invalid voice: {voice}. Available: {self.AVAILABLE_VOICES}")

        if response_format not in self.AVAILABLE_FORMATS:
            raise ValueError(
                f"Invalid format: {response_format}. Available: {self.AVAILABLE_FORMATS}"
            )

        if not 0.25 <= speed <= 4.0:
            raise ValueError("Speed must be between 0.25 and 4.0")

        logger.info(
            "Synthesizing speech",
            text_length=len(text),
            voice=voice,
            speed=speed,
            format=response_format,
            model=model,
        )

        try:
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed,
                response_format=response_format,
            )

            # Get audio content
            audio_data = response.content

            logger.info(
                "Speech synthesis completed",
                audio_size=len(audio_data),
                format=response_format,
            )

            return audio_data

        except Exception as e:
            logger.error("Speech synthesis failed", error=str(e))
            raise

    async def synthesize_stream(
        self,
        text: str,
        voice: VoiceType | None = None,
        speed: float | None = None,
        response_format: AudioFormat = "mp3",
        model: str | None = None,
        chunk_size: int = 4096,
    ) -> AsyncIterator[bytes]:
        """
        Synthesize text to speech with streaming output.

        Args:
            text: Text to convert to speech
            voice: Voice to use
            speed: Speaking speed
            response_format: Audio format
            model: TTS model
            chunk_size: Size of each chunk in bytes

        Yields:
            Audio data chunks
        """
        # Use defaults from config if not specified
        voice = voice or self.config.tts_voice  # type: ignore
        speed = speed if speed is not None else self.config.tts_speed
        model = model or self.config.tts_model

        logger.info(
            "Starting streaming speech synthesis",
            text_length=len(text),
            voice=voice,
        )

        try:
            # Note: OpenAI TTS doesn't support true streaming yet,
            # so we simulate it by chunking the response
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed,
                response_format=response_format,
            )

            # Stream the content in chunks
            audio_data = response.content
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i : i + chunk_size]
                # Small delay to simulate streaming
                await asyncio.sleep(0.01)

            logger.info("Streaming synthesis completed")

        except Exception as e:
            logger.error("Streaming synthesis failed", error=str(e))
            raise

    def get_voice_info(self) -> list[dict]:
        """
        Get information about available voices.

        Returns:
            List of voice information dictionaries
        """
        voice_descriptions = {
            "alloy": "Neutral and balanced",
            "echo": "Warm and conversational",
            "fable": "Expressive and dramatic",
            "onyx": "Deep and authoritative",
            "nova": "Friendly and upbeat",
            "shimmer": "Clear and precise",
        }

        return [
            {
                "id": voice,
                "name": voice.capitalize(),
                "description": voice_descriptions.get(voice, ""),
            }
            for voice in self.AVAILABLE_VOICES
        ]


# Singleton instance
_synthesis_service: SynthesisService | None = None


def get_synthesis_service() -> SynthesisService:
    """Get the synthesis service singleton."""
    global _synthesis_service
    if _synthesis_service is None:
        _synthesis_service = SynthesisService()
    return _synthesis_service
