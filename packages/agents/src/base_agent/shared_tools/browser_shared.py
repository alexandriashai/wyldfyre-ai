"""
Shared browser tools available to all agents.

Provides lightweight browser utilities that don't require
the full QA agent browser toolset:
- Browser status checking
- One-shot URL screenshots
- Page content fetching
- Visual comparison
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Output directory for screenshots
SHARED_SCREENSHOT_DIR = "/tmp/browser_screenshots"


@tool(
    name="browser_status",
    description="Check browser manager status and active resources. Use to verify browser automation is available.",
    parameters={"type": "object", "properties": {}},
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def browser_status() -> ToolResult:
    """Get browser manager status."""
    try:
        # Try to import browser manager
        try:
            from qa_agent.browser_manager import get_browser_manager

            manager = get_browser_manager()
            stats = manager.get_stats()

            return ToolResult.ok(
                {
                    "available": True,
                    "browsers_active": stats["browsers_active"],
                    "contexts_active": stats["contexts_active"],
                    "pages_active": stats["pages_active"],
                    "limits": stats["limits"],
                }
            )
        except ImportError:
            return ToolResult.ok(
                {
                    "available": False,
                    "message": "Browser manager not available. QA Agent required.",
                }
            )

    except Exception as e:
        logger.error("Browser status check failed", error=str(e))
        return ToolResult.fail(f"Browser status check failed: {e}")


@tool(
    name="screenshot_url",
    description="Take a one-shot screenshot of a URL. Creates a temporary browser, navigates, captures, and closes.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to screenshot",
            },
            "path": {
                "type": "string",
                "description": "Output file path (optional)",
            },
            "full_page": {
                "type": "boolean",
                "description": "Capture full scrollable page",
                "default": False,
            },
            "viewport_width": {
                "type": "integer",
                "description": "Viewport width",
                "default": 1280,
            },
            "viewport_height": {
                "type": "integer",
                "description": "Viewport height",
                "default": 720,
            },
            "wait_for_load": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle"],
                "description": "Wait for this state before screenshot",
                "default": "load",
            },
        },
        "required": ["url"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def screenshot_url(
    url: str,
    path: str | None = None,
    full_page: bool = False,
    viewport_width: int = 1280,
    viewport_height: int = 720,
    wait_for_load: str = "load",
) -> ToolResult:
    """Take a one-shot screenshot of a URL."""
    try:
        from playwright.async_api import async_playwright

        # Generate output path
        if not path:
            output_dir = Path(SHARED_SCREENSHOT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(output_dir / f"url_screenshot_{timestamp}.png")
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": viewport_width, "height": viewport_height}
            )
            page = await context.new_page()

            await page.goto(url, wait_until=wait_for_load)
            await page.screenshot(path=path, full_page=full_page)

            final_url = page.url
            title = await page.title()

            await browser.close()

        file_size = os.path.getsize(path)

        return ToolResult.ok(
            {
                "path": path,
                "url": final_url,
                "title": title,
                "full_page": full_page,
                "size_bytes": file_size,
            }
        )

    except ImportError:
        return ToolResult.fail("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    except Exception as e:
        logger.error("Screenshot URL failed", url=url, error=str(e))
        return ToolResult.fail(f"Screenshot URL failed: {e}")


@tool(
    name="page_content_fetch",
    description="Fetch rendered HTML content from a URL. Uses a browser to render JavaScript.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch content from",
            },
            "wait_for_load": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle"],
                "default": "load",
            },
            "wait_for_selector": {
                "type": "string",
                "description": "Optional selector to wait for before getting content",
            },
            "max_content_length": {
                "type": "integer",
                "description": "Maximum content length to return",
                "default": 100000,
            },
        },
        "required": ["url"],
    },
    permission_level=1,
    capability_category=CapabilityCategory.WEB,
)
async def page_content_fetch(
    url: str,
    wait_for_load: str = "load",
    wait_for_selector: str | None = None,
    max_content_length: int = 100000,
) -> ToolResult:
    """Fetch rendered HTML content from a URL."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, wait_until=wait_for_load)

            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=30000)

            content = await page.content()
            final_url = page.url
            title = await page.title()

            await browser.close()

        truncated = len(content) > max_content_length

        return ToolResult.ok(
            {
                "url": final_url,
                "title": title,
                "content": content[:max_content_length],
                "content_length": len(content),
                "truncated": truncated,
            }
        )

    except ImportError:
        return ToolResult.fail("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    except Exception as e:
        logger.error("Page content fetch failed", url=url, error=str(e))
        return ToolResult.fail(f"Page content fetch failed: {e}")


@tool(
    name="visual_diff",
    description="Compare two screenshots and compute difference. Useful for visual regression testing.",
    parameters={
        "type": "object",
        "properties": {
            "image1_path": {
                "type": "string",
                "description": "Path to first image",
            },
            "image2_path": {
                "type": "string",
                "description": "Path to second image",
            },
            "diff_output_path": {
                "type": "string",
                "description": "Path to save difference image (optional)",
            },
            "threshold": {
                "type": "number",
                "description": "Pixel difference threshold (0-255)",
                "default": 10,
            },
        },
        "required": ["image1_path", "image2_path"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def visual_diff(
    image1_path: str,
    image2_path: str,
    diff_output_path: str | None = None,
    threshold: int = 10,
) -> ToolResult:
    """Compare two screenshots for visual differences."""
    try:
        from PIL import Image, ImageChops
        import numpy as np

        # Load images
        img1 = Image.open(image1_path).convert("RGB")
        img2 = Image.open(image2_path).convert("RGB")

        # Check dimensions
        if img1.size != img2.size:
            return ToolResult.ok(
                {
                    "identical": False,
                    "reason": "size_mismatch",
                    "image1_size": img1.size,
                    "image2_size": img2.size,
                }
            )

        # Compute difference
        diff = ImageChops.difference(img1, img2)
        diff_array = np.array(diff)

        # Count pixels above threshold
        diff_pixels = np.sum(np.any(diff_array > threshold, axis=2))
        total_pixels = img1.size[0] * img1.size[1]
        diff_percentage = (diff_pixels / total_pixels) * 100

        # Save diff image if requested
        if diff_output_path:
            Path(diff_output_path).parent.mkdir(parents=True, exist_ok=True)
            # Enhance diff for visibility
            enhanced = diff.point(lambda x: min(255, x * 5))
            enhanced.save(diff_output_path)

        identical = diff_pixels == 0

        return ToolResult.ok(
            {
                "identical": identical,
                "diff_pixels": int(diff_pixels),
                "total_pixels": total_pixels,
                "diff_percentage": round(diff_percentage, 2),
                "threshold": threshold,
                "diff_image": diff_output_path,
            }
        )

    except ImportError:
        return ToolResult.fail("PIL (Pillow) and numpy required. Install with: pip install Pillow numpy")
    except Exception as e:
        logger.error("Visual diff failed", error=str(e))
        return ToolResult.fail(f"Visual diff failed: {e}")


def get_browser_shared_tools():
    """Get all shared browser tool functions for registration."""
    return [
        browser_status,
        screenshot_url,
        page_content_fetch,
        visual_diff,
    ]
