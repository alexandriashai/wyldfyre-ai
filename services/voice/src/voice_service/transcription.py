"""
Speech-to-Text transcription service using OpenAI Whisper.
"""

import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator

import aiofiles
from openai import AsyncOpenAI
from pydub import AudioSegment

from ai_core import get_logger

from .config import get_voice_config

logger = get_logger(__name__)


class TranscriptionService:
    """Service for transcribing audio to text using Whisper."""

    SUPPORTED_FORMATS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg", "flac"}

    def __init__(self) -> None:
        self.config = get_voice_config()
        self.client = AsyncOpenAI(api_key=self.config.openai_api_key)

    async def transcribe_file(
        self,
        file_path: str | Path,
        language: str | None = None,
        prompt: str | None = None,
        response_format: str = "json",
        temperature: float = 0.0,
    ) -> dict:
        """
        Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file
            language: ISO-639-1 language code (optional, auto-detect if None)
            prompt: Optional prompt to guide transcription
            response_format: Output format (json, text, srt, verbose_json, vtt)
            temperature: Sampling temperature (0-1)

        Returns:
            Transcription result with text and metadata
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.config.max_audio_size_mb:
            raise ValueError(
                f"File size ({file_size_mb:.1f}MB) exceeds maximum "
                f"({self.config.max_audio_size_mb}MB)"
            )

        logger.info(
            "Transcribing audio file",
            file=str(file_path),
            size_mb=f"{file_size_mb:.1f}",
            language=language or "auto",
        )

        try:
            async with aiofiles.open(file_path, "rb") as f:
                audio_data = await f.read()

            # Create a file-like object for the API
            audio_file = io.BytesIO(audio_data)
            audio_file.name = file_path.name

            # Build API parameters
            params: dict = {
                "model": self.config.whisper_model,
                "file": audio_file,
                "response_format": response_format,
                "temperature": temperature,
            }

            if language:
                params["language"] = language
            elif self.config.whisper_language:
                params["language"] = self.config.whisper_language

            if prompt:
                params["prompt"] = prompt

            # Call Whisper API
            response = await self.client.audio.transcriptions.create(**params)

            # Handle different response formats
            if response_format in ("json", "verbose_json"):
                result = {
                    "text": response.text,
                    "language": getattr(response, "language", language),
                    "duration": getattr(response, "duration", None),
                }
                if hasattr(response, "segments"):
                    result["segments"] = response.segments
            else:
                result = {"text": response if isinstance(response, str) else response.text}

            logger.info("Transcription completed", text_length=len(result["text"]))
            return result

        except Exception as e:
            logger.error("Transcription failed", error=str(e))
            raise

    async def transcribe_bytes(
        self,
        audio_data: bytes,
        filename: str = "audio.webm",
        language: str | None = None,
        prompt: str | None = None,
    ) -> dict:
        """
        Transcribe audio from bytes.

        Args:
            audio_data: Raw audio bytes
            filename: Original filename (for format detection)
            language: ISO-639-1 language code (optional)
            prompt: Optional prompt to guide transcription

        Returns:
            Transcription result
        """
        # Save to temporary file
        suffix = Path(filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            result = await self.transcribe_file(
                tmp_path,
                language=language,
                prompt=prompt,
            )
            return result
        finally:
            # Cleanup
            os.unlink(tmp_path)

    async def convert_audio_format(
        self,
        audio_data: bytes,
        source_format: str,
        target_format: str = "mp3",
    ) -> bytes:
        """
        Convert audio from one format to another.

        Args:
            audio_data: Input audio bytes
            source_format: Source format (e.g., "webm", "wav")
            target_format: Target format (e.g., "mp3")

        Returns:
            Converted audio bytes
        """
        # Run conversion in thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        def _convert():
            audio = AudioSegment.from_file(
                io.BytesIO(audio_data),
                format=source_format,
            )
            output = io.BytesIO()
            audio.export(output, format=target_format)
            return output.getvalue()

        return await loop.run_in_executor(None, _convert)


# Singleton instance
_transcription_service: TranscriptionService | None = None


def get_transcription_service() -> TranscriptionService:
    """Get the transcription service singleton."""
    global _transcription_service
    if _transcription_service is None:
        _transcription_service = TranscriptionService()
    return _transcription_service
