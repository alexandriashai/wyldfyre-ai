"""
Speech-to-Text transcription routes.
"""

import json
import os
import tempfile
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, status
from pydantic import BaseModel

from ai_core import get_logger

from ..config import get_voice_config
from ..transcription import get_transcription_service

logger = get_logger(__name__)

router = APIRouter(prefix="/transcribe", tags=["Transcription"])


class TranscriptionResponse(BaseModel):
    """Transcription response model."""

    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[dict] | None = None


class TranscriptionRequest(BaseModel):
    """Transcription request for JSON body."""

    language: str | None = None
    prompt: str | None = None
    response_format: str = "json"
    temperature: float = 0.0


@router.post("", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    language: Annotated[str | None, Form()] = None,
    prompt: Annotated[str | None, Form()] = None,
    response_format: Annotated[str, Form()] = "json",
    temperature: Annotated[float, Form()] = 0.0,
) -> TranscriptionResponse:
    """
    Transcribe an uploaded audio file to text.

    Supports formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg, flac

    Args:
        file: Audio file upload
        language: ISO-639-1 language code (e.g., 'en', 'es', 'fr')
        prompt: Optional prompt to guide transcription style
        response_format: Output format (json, text, srt, verbose_json, vtt)
        temperature: Sampling temperature (0-1), lower is more deterministic

    Returns:
        Transcription result with text and optional metadata
    """
    config = get_voice_config()
    service = get_transcription_service()

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Check file extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in service.SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {ext}. "
            f"Supported formats: {', '.join(sorted(service.SUPPORTED_FORMATS))}",
        )

    # Check file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > config.max_audio_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({size_mb:.1f}MB) exceeds maximum ({config.max_audio_size_mb}MB)",
        )

    logger.info(
        "Received transcription request",
        filename=file.filename,
        size_mb=f"{size_mb:.1f}",
        language=language or "auto",
    )

    try:
        result = await service.transcribe_bytes(
            audio_data=content,
            filename=file.filename,
            language=language,
            prompt=prompt,
        )

        return TranscriptionResponse(
            text=result["text"],
            language=result.get("language"),
            duration=result.get("duration"),
            segments=result.get("segments"),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Transcription failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed",
        )


@router.websocket("/stream")
async def transcribe_stream(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for streaming audio transcription.

    Protocol:
    1. Client connects
    2. Client sends JSON config: {"language": "en", "prompt": "..."}
    3. Client sends binary audio chunks
    4. Client sends JSON: {"action": "end"} to finish
    5. Server responds with transcription result

    Audio should be sent in chunks of ~1-5 seconds.
    """
    await websocket.accept()
    config = get_voice_config()
    service = get_transcription_service()

    logger.info("WebSocket transcription session started")

    audio_chunks: list[bytes] = []
    session_config: dict[str, Any] = {}

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            # Handle text messages (config/commands)
            if "text" in message:
                try:
                    data = json.loads(message["text"])

                    if data.get("action") == "end":
                        # Process accumulated audio
                        if audio_chunks:
                            audio_data = b"".join(audio_chunks)
                            result = await service.transcribe_bytes(
                                audio_data=audio_data,
                                filename="stream.webm",
                                language=session_config.get("language"),
                                prompt=session_config.get("prompt"),
                            )
                            await websocket.send_json({
                                "type": "transcription",
                                "text": result["text"],
                                "language": result.get("language"),
                                "final": True,
                            })
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "No audio received",
                            })
                        break

                    elif data.get("action") == "config":
                        session_config = {
                            "language": data.get("language"),
                            "prompt": data.get("prompt"),
                        }
                        await websocket.send_json({
                            "type": "config_ack",
                            "message": "Configuration received",
                        })

                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })

            # Handle binary messages (audio data)
            elif "bytes" in message:
                chunk = message["bytes"]
                audio_chunks.append(chunk)

                # Check total size
                total_size = sum(len(c) for c in audio_chunks)
                if total_size > config.max_audio_size_mb * 1024 * 1024:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Audio size limit exceeded",
                    })
                    break

                # Send acknowledgment
                await websocket.send_json({
                    "type": "chunk_ack",
                    "chunks": len(audio_chunks),
                    "total_bytes": total_size,
                })

    except Exception as e:
        logger.error("WebSocket transcription error", error=str(e))
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass  # Connection already closed

    finally:
        logger.info(
            "WebSocket transcription session ended",
            chunks_received=len(audio_chunks),
        )
