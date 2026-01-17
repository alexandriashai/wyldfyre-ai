"""
Text-to-Speech synthesis routes.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ai_core import get_logger

from ..synthesis import AudioFormat, VoiceType, get_synthesis_service

logger = get_logger(__name__)

router = APIRouter(prefix="/synthesize", tags=["Synthesis"])


class SynthesizeRequest(BaseModel):
    """Text-to-speech synthesis request."""

    text: str = Field(..., min_length=1, max_length=4096, description="Text to synthesize")
    voice: VoiceType = Field(default="alloy", description="Voice to use")
    speed: float = Field(default=1.0, ge=0.25, le=4.0, description="Speaking speed")
    response_format: AudioFormat = Field(default="mp3", description="Audio output format")
    model: Literal["tts-1", "tts-1-hd"] = Field(
        default="tts-1",
        description="TTS model (tts-1 for speed, tts-1-hd for quality)",
    )


class VoiceInfo(BaseModel):
    """Voice information."""

    id: str
    name: str
    description: str


@router.post("")
async def synthesize_speech(
    request: SynthesizeRequest,
) -> Response:
    """
    Convert text to speech audio.

    Returns audio file in the specified format.

    Args:
        request: Synthesis parameters including text, voice, speed, and format

    Returns:
        Audio file response
    """
    service = get_synthesis_service()

    logger.info(
        "Received synthesis request",
        text_length=len(request.text),
        voice=request.voice,
        format=request.response_format,
    )

    try:
        audio_data = await service.synthesize(
            text=request.text,
            voice=request.voice,
            speed=request.speed,
            response_format=request.response_format,
            model=request.model,
        )

        # Determine content type
        content_types = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }
        content_type = content_types.get(request.response_format, "audio/mpeg")

        return Response(
            content=audio_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="speech.{request.response_format}"',
            },
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Synthesis failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Speech synthesis failed",
        )


@router.get("/stream")
async def synthesize_stream(
    text: Annotated[str, Query(..., min_length=1, max_length=4096)],
    voice: Annotated[VoiceType, Query()] = "alloy",
    speed: Annotated[float, Query(ge=0.25, le=4.0)] = 1.0,
    response_format: Annotated[AudioFormat, Query()] = "mp3",
    model: Annotated[Literal["tts-1", "tts-1-hd"], Query()] = "tts-1",
) -> StreamingResponse:
    """
    Convert text to speech with streaming response.

    Returns audio as a streaming response, useful for longer texts.

    Args:
        text: Text to synthesize
        voice: Voice to use
        speed: Speaking speed (0.25-4.0)
        response_format: Audio format
        model: TTS model

    Returns:
        Streaming audio response
    """
    service = get_synthesis_service()

    logger.info(
        "Received streaming synthesis request",
        text_length=len(text),
        voice=voice,
    )

    content_types = {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "pcm": "audio/pcm",
    }
    content_type = content_types.get(response_format, "audio/mpeg")

    try:
        return StreamingResponse(
            service.synthesize_stream(
                text=text,
                voice=voice,
                speed=speed,
                response_format=response_format,
                model=model,
            ),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="speech.{response_format}"',
            },
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/voices", response_model=list[VoiceInfo])
async def list_voices() -> list[VoiceInfo]:
    """
    List available TTS voices.

    Returns information about all available voices including
    their names and descriptions.
    """
    service = get_synthesis_service()
    voices = service.get_voice_info()
    return [VoiceInfo(**v) for v in voices]


@router.get("/formats")
async def list_formats() -> dict:
    """
    List available audio output formats.

    Returns supported audio formats with their MIME types.
    """
    return {
        "formats": [
            {"id": "mp3", "name": "MP3", "mime_type": "audio/mpeg", "description": "Compressed, widely supported"},
            {"id": "opus", "name": "Opus", "mime_type": "audio/opus", "description": "High quality, low latency"},
            {"id": "aac", "name": "AAC", "mime_type": "audio/aac", "description": "Good compression, Apple compatible"},
            {"id": "flac", "name": "FLAC", "mime_type": "audio/flac", "description": "Lossless compression"},
            {"id": "wav", "name": "WAV", "mime_type": "audio/wav", "description": "Uncompressed, highest quality"},
            {"id": "pcm", "name": "PCM", "mime_type": "audio/pcm", "description": "Raw audio data"},
        ],
    }
