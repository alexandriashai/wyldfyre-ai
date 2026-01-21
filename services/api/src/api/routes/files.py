"""
File upload and management routes.
"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ai_core import get_logger

from ..config import APIConfig
from ..dependencies import ConfigDep, CurrentUserDep

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: CurrentUserDep = None,
    config: ConfigDep = None,
) -> dict[str, Any]:
    """
    Upload a file.

    Returns the file ID for later retrieval.
    """
    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > config.upload_max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {config.upload_max_size_mb}MB",
        )

    # Validate content type
    if file.content_type not in config.upload_allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {file.content_type} not allowed",
        )

    # Generate file ID and path
    file_id = str(uuid4())
    file_ext = Path(file.filename).suffix if file.filename else ""
    safe_filename = f"{file_id}{file_ext}"

    # Ensure upload directory exists
    upload_dir = Path(config.upload_directory) / current_user.sub
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / safe_filename

    # Save file
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(8192):
                await f.write(chunk)

        logger.info(
            "File uploaded",
            file_id=file_id,
            filename=file.filename,
            size=file_size,
            user_id=current_user.sub,
        )

        return {
            "id": file_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("File upload failed", error=str(e))
        # Clean up partial file
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save file",
        )


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    current_user: CurrentUserDep,
    config: ConfigDep,
) -> FileResponse:
    """
    Download a file by ID.
    """
    # Find file in user's directory
    upload_dir = Path(config.upload_directory) / current_user.sub

    if not upload_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found",
        )

    # Look for file with matching ID
    matching_files = list(upload_dir.glob(f"{file_id}*"))
    if not matching_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found",
        )

    file_path = matching_files[0]

    # Determine media type from extension
    ext_to_media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".json": "application/json",
    }
    media_type = ext_to_media_type.get(
        file_path.suffix.lower(),
        "application/octet-stream",
    )

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: CurrentUserDep,
    config: ConfigDep,
) -> dict[str, str]:
    """
    Delete a file by ID.
    """
    upload_dir = Path(config.upload_directory) / current_user.sub

    if not upload_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found",
        )

    # Look for file with matching ID
    matching_files = list(upload_dir.glob(f"{file_id}*"))
    if not matching_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found",
        )

    file_path = matching_files[0]

    try:
        file_path.unlink()
        logger.info("File deleted", file_id=file_id, user_id=current_user.sub)
        return {"message": f"File {file_id} deleted"}

    except Exception as e:
        logger.error("Failed to delete file", file_id=file_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        )


@router.get("")
async def list_files(
    current_user: CurrentUserDep,
    config: ConfigDep,
) -> dict[str, Any]:
    """
    List all files for the current user.
    """
    upload_dir = Path(config.upload_directory) / current_user.sub

    if not upload_dir.exists():
        return {"files": [], "count": 0}

    files = []
    for file_path in upload_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            # Extract file ID from filename
            file_id = file_path.stem

            files.append({
                "id": file_id,
                "filename": file_path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })

    return {
        "files": sorted(files, key=lambda f: f["modified_at"], reverse=True),
        "count": len(files),
    }
