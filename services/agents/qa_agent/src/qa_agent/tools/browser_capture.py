"""
Browser capture tools for the QA Agent.

Provides tools for capturing browser state:
- Screenshots (full page and element)
- Video recording
- Playwright trace capture
- PDF export
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

from ..browser_config import (
    SCREENSHOT_DEFAULTS,
    TRACE_DEFAULTS,
    VIDEO_DEFAULTS,
)
from ..browser_manager import get_browser_manager

logger = get_logger(__name__)


def _ensure_output_dir(path: str) -> Path:
    """Ensure output directory exists."""
    output_path = Path(path)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def _generate_filename(prefix: str, extension: str) -> str:
    """Generate a timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"


# ============================================================================
# Screenshot Tools
# ============================================================================


@tool(
    name="screenshot_page",
    description="Take a screenshot of the page.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "path": {
                "type": "string",
                "description": "Output file path (optional, generates if not provided)",
            },
            "full_page": {
                "type": "boolean",
                "description": "Capture full scrollable page",
                "default": False,
            },
            "type": {
                "type": "string",
                "enum": ["png", "jpeg"],
                "description": "Image format",
                "default": "png",
            },
            "quality": {
                "type": "integer",
                "description": "JPEG quality (0-100)",
                "default": 80,
            },
            "omit_background": {
                "type": "boolean",
                "description": "Transparent background (PNG only)",
                "default": False,
            },
        },
        "required": ["page_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def screenshot_page(
    page_id: str,
    path: str | None = None,
    full_page: bool = False,
    type: str = "png",
    quality: int = 80,
    omit_background: bool = False,
) -> ToolResult:
    """Take a page screenshot."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Generate path if not provided
        if not path:
            output_dir = _ensure_output_dir(SCREENSHOT_DEFAULTS.output_dir)
            filename = _generate_filename("screenshot", type)
            path = str(output_dir / filename)
        else:
            # Ensure parent directory exists
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        screenshot_options: dict[str, Any] = {
            "path": path,
            "full_page": full_page,
            "type": type,
            "animations": SCREENSHOT_DEFAULTS.animations,
            "caret": SCREENSHOT_DEFAULTS.caret,
        }

        if type == "jpeg":
            screenshot_options["quality"] = quality

        if type == "png" and omit_background:
            screenshot_options["omit_background"] = True

        await page.screenshot(**screenshot_options)

        # Get file size
        file_size = os.path.getsize(path)

        return ToolResult.ok(
            {
                "path": path,
                "full_page": full_page,
                "type": type,
                "size_bytes": file_size,
            }
        )

    except Exception as e:
        logger.error("Screenshot failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"Screenshot failed: {e}")


@tool(
    name="screenshot_element",
    description="Take a screenshot of a specific element.",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "selector": {
                "type": "string",
                "description": "CSS or Playwright selector for the element",
            },
            "path": {
                "type": "string",
                "description": "Output file path (optional)",
            },
            "type": {
                "type": "string",
                "enum": ["png", "jpeg"],
                "default": "png",
            },
            "quality": {
                "type": "integer",
                "default": 80,
            },
            "timeout": {
                "type": "integer",
                "default": 30000,
            },
        },
        "required": ["page_id", "selector"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def screenshot_element(
    page_id: str,
    selector: str,
    path: str | None = None,
    type: str = "png",
    quality: int = 80,
    timeout: int = 30000,
) -> ToolResult:
    """Take an element screenshot."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Generate path if not provided
        if not path:
            output_dir = _ensure_output_dir(SCREENSHOT_DEFAULTS.output_dir)
            filename = _generate_filename("element", type)
            path = str(output_dir / filename)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        locator = page.locator(selector)
        screenshot_options: dict[str, Any] = {
            "path": path,
            "type": type,
            "animations": SCREENSHOT_DEFAULTS.animations,
            "caret": SCREENSHOT_DEFAULTS.caret,
            "timeout": timeout,
        }

        if type == "jpeg":
            screenshot_options["quality"] = quality

        await locator.screenshot(**screenshot_options)

        file_size = os.path.getsize(path)

        return ToolResult.ok(
            {
                "path": path,
                "selector": selector,
                "type": type,
                "size_bytes": file_size,
            }
        )

    except Exception as e:
        logger.error(
            "Element screenshot failed",
            page_id=page_id,
            selector=selector,
            error=str(e),
        )
        return ToolResult.fail(f"Element screenshot failed: {e}")


# ============================================================================
# Video Recording Tools
# ============================================================================

# Track active video recordings
_video_contexts: dict[str, dict[str, Any]] = {}


@tool(
    name="video_start",
    description="Start video recording for a browser context. Must call video_stop to save the video.",
    parameters={
        "type": "object",
        "properties": {
            "browser_id": {
                "type": "string",
                "description": "Browser ID to create a recording context in",
            },
            "width": {
                "type": "integer",
                "description": "Video width",
                "default": 1280,
            },
            "height": {
                "type": "integer",
                "description": "Video height",
                "default": 720,
            },
            "output_dir": {
                "type": "string",
                "description": "Directory for video output",
            },
        },
        "required": ["browser_id"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def video_start(
    browser_id: str,
    width: int = 1280,
    height: int = 720,
    output_dir: str | None = None,
    _task_id: str | None = None,
) -> ToolResult:
    """Start video recording."""
    try:
        manager = get_browser_manager()
        browser = manager.get_browser(browser_id)

        if not browser:
            return ToolResult.fail(f"Browser not found: {browser_id}")

        # Prepare output directory
        video_dir = output_dir or VIDEO_DEFAULTS.output_dir
        _ensure_output_dir(video_dir)

        # Create context with video recording enabled
        context = await browser.new_context(
            record_video_dir=video_dir,
            record_video_size={"width": width, "height": height},
        )

        # Create a page in this context
        page = await context.new_page()

        # Generate IDs for tracking
        context_id = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        _video_contexts[context_id] = {
            "context": context,
            "page": page,
            "output_dir": video_dir,
            "browser_id": browser_id,
            "started_at": datetime.now().isoformat(),
        }

        return ToolResult.ok(
            {
                "recording_id": context_id,
                "output_dir": video_dir,
                "resolution": f"{width}x{height}",
            }
        )

    except Exception as e:
        logger.error("Video start failed", browser_id=browser_id, error=str(e))
        return ToolResult.fail(f"Video start failed: {e}")


@tool(
    name="video_stop",
    description="Stop video recording and save the video file.",
    parameters={
        "type": "object",
        "properties": {
            "recording_id": {
                "type": "string",
                "description": "Recording ID from video_start",
            },
        },
        "required": ["recording_id"],
    },
    permission_level=2,
    capability_category=CapabilityCategory.WEB,
)
async def video_stop(recording_id: str) -> ToolResult:
    """Stop video recording."""
    try:
        if recording_id not in _video_contexts:
            return ToolResult.fail(f"Recording not found: {recording_id}")

        recording = _video_contexts[recording_id]
        page = recording["page"]
        context = recording["context"]

        # Get video path before closing
        video = page.video
        video_path = None

        if video:
            await page.close()
            video_path = await video.path()

        # Close context
        await context.close()

        # Cleanup tracking
        del _video_contexts[recording_id]

        if video_path and os.path.exists(video_path):
            file_size = os.path.getsize(video_path)
            return ToolResult.ok(
                {
                    "recording_id": recording_id,
                    "video_path": str(video_path),
                    "size_bytes": file_size,
                }
            )
        else:
            return ToolResult.ok(
                {
                    "recording_id": recording_id,
                    "video_path": None,
                    "message": "Video may not have been saved",
                }
            )

    except Exception as e:
        logger.error("Video stop failed", recording_id=recording_id, error=str(e))
        return ToolResult.fail(f"Video stop failed: {e}")


# ============================================================================
# Trace Tools
# ============================================================================

# Track active traces
_active_traces: dict[str, dict[str, Any]] = {}


@tool(
    name="trace_start",
    description="Start recording a Playwright trace for debugging. Captures screenshots, snapshots, and network activity.",
    parameters={
        "type": "object",
        "properties": {
            "context_id": {
                "type": "string",
                "description": "Context ID to trace",
            },
            "name": {
                "type": "string",
                "description": "Name for the trace",
            },
            "screenshots": {
                "type": "boolean",
                "description": "Capture screenshots",
                "default": True,
            },
            "snapshots": {
                "type": "boolean",
                "description": "Capture DOM snapshots",
                "default": True,
            },
            "sources": {
                "type": "boolean",
                "description": "Include source code",
                "default": True,
            },
        },
        "required": ["context_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def trace_start(
    context_id: str,
    name: str | None = None,
    screenshots: bool = True,
    snapshots: bool = True,
    sources: bool = True,
) -> ToolResult:
    """Start trace recording."""
    try:
        manager = get_browser_manager()
        context = manager.get_context(context_id)

        if not context:
            return ToolResult.fail(f"Context not found: {context_id}")

        trace_name = name or f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        await context.tracing.start(
            name=trace_name,
            screenshots=screenshots,
            snapshots=snapshots,
            sources=sources,
        )

        _active_traces[context_id] = {
            "name": trace_name,
            "started_at": datetime.now().isoformat(),
            "options": {
                "screenshots": screenshots,
                "snapshots": snapshots,
                "sources": sources,
            },
        }

        return ToolResult.ok(
            {
                "context_id": context_id,
                "trace_name": trace_name,
                "started": True,
            }
        )

    except Exception as e:
        logger.error("Trace start failed", context_id=context_id, error=str(e))
        return ToolResult.fail(f"Trace start failed: {e}")


@tool(
    name="trace_stop",
    description="Stop trace recording and save the trace file.",
    parameters={
        "type": "object",
        "properties": {
            "context_id": {
                "type": "string",
                "description": "Context ID",
            },
            "path": {
                "type": "string",
                "description": "Output path for trace file (optional)",
            },
        },
        "required": ["context_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def trace_stop(
    context_id: str,
    path: str | None = None,
) -> ToolResult:
    """Stop trace recording."""
    try:
        manager = get_browser_manager()
        context = manager.get_context(context_id)

        if not context:
            return ToolResult.fail(f"Context not found: {context_id}")

        if context_id not in _active_traces:
            return ToolResult.fail(f"No active trace for context: {context_id}")

        trace_info = _active_traces[context_id]

        # Generate path if not provided
        if not path:
            output_dir = _ensure_output_dir(TRACE_DEFAULTS.output_dir)
            path = str(output_dir / f"{trace_info['name']}.zip")
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        await context.tracing.stop(path=path)

        # Cleanup tracking
        del _active_traces[context_id]

        file_size = os.path.getsize(path) if os.path.exists(path) else 0

        return ToolResult.ok(
            {
                "context_id": context_id,
                "trace_path": path,
                "trace_name": trace_info["name"],
                "size_bytes": file_size,
                "view_command": f"playwright show-trace {path}",
            }
        )

    except Exception as e:
        logger.error("Trace stop failed", context_id=context_id, error=str(e))
        return ToolResult.fail(f"Trace stop failed: {e}")


# ============================================================================
# PDF Export
# ============================================================================


@tool(
    name="pdf_export",
    description="Export the page as a PDF document (Chromium only).",
    parameters={
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Page ID",
            },
            "path": {
                "type": "string",
                "description": "Output file path (optional)",
            },
            "format": {
                "type": "string",
                "enum": ["Letter", "Legal", "Tabloid", "Ledger", "A0", "A1", "A2", "A3", "A4", "A5", "A6"],
                "description": "Paper format",
                "default": "A4",
            },
            "landscape": {
                "type": "boolean",
                "description": "Landscape orientation",
                "default": False,
            },
            "print_background": {
                "type": "boolean",
                "description": "Print background graphics",
                "default": True,
            },
            "scale": {
                "type": "number",
                "description": "Scale factor (0.1 - 2.0)",
                "default": 1.0,
            },
        },
        "required": ["page_id"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def pdf_export(
    page_id: str,
    path: str | None = None,
    format: str = "A4",
    landscape: bool = False,
    print_background: bool = True,
    scale: float = 1.0,
) -> ToolResult:
    """Export page as PDF."""
    try:
        manager = get_browser_manager()
        page = manager.get_page(page_id)

        if not page:
            return ToolResult.fail(f"Page not found: {page_id}")

        # Generate path if not provided
        if not path:
            output_dir = _ensure_output_dir(SCREENSHOT_DEFAULTS.output_dir)
            filename = _generate_filename("export", "pdf")
            path = str(output_dir / filename)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        await page.pdf(
            path=path,
            format=format,
            landscape=landscape,
            print_background=print_background,
            scale=scale,
        )

        file_size = os.path.getsize(path)

        return ToolResult.ok(
            {
                "path": path,
                "format": format,
                "landscape": landscape,
                "size_bytes": file_size,
            }
        )

    except Exception as e:
        logger.error("PDF export failed", page_id=page_id, error=str(e))
        return ToolResult.fail(f"PDF export failed: {e}")
