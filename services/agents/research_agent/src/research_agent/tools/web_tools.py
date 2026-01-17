"""
Web search and fetch tools for the Research Agent.
"""

import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Configuration
SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY", "")
SEARCH_ENGINE_ID = os.environ.get("SEARCH_ENGINE_ID", "")
USER_AGENT = "AI-Infrastructure-Research/1.0"

# Rate limiting
MAX_CONTENT_LENGTH = 100000  # 100KB max content
REQUEST_TIMEOUT = 30.0


async def _make_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """Make an HTTP request with standard headers."""
    default_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    if headers:
        default_headers.update(headers)

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        return await client.request(
            method,
            url,
            headers=default_headers,
            params=params,
        )


def _extract_text_from_html(html: str, max_length: int = 10000) -> str:
    """Extract clean text from HTML content."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()

    # Get text
    text = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    # Truncate if needed
    if len(text) > max_length:
        text = text[:max_length] + "...[truncated]"

    return text


def _extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    """Extract links from HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)

        # Skip empty or javascript links
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue

        # Make absolute URL
        absolute_url = urljoin(base_url, href)

        # Only include http(s) links
        if absolute_url.startswith(("http://", "https://")):
            links.append({
                "url": absolute_url,
                "text": text[:100] if text else "",
            })

    return links[:50]  # Limit to 50 links


@tool(
    name="search_web",
    description="Search the web using Google Custom Search API",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return",
                "default": 10,
            },
            "site": {
                "type": "string",
                "description": "Limit search to specific site (e.g., 'docs.python.org')",
            },
        },
        "required": ["query"],
    },
)
async def search_web(
    query: str,
    num_results: int = 10,
    site: str | None = None,
) -> ToolResult:
    """Search the web."""
    try:
        if not SEARCH_API_KEY or not SEARCH_ENGINE_ID:
            return ToolResult.fail(
                "Search API not configured. Set SEARCH_API_KEY and SEARCH_ENGINE_ID."
            )

        # Build search query
        search_query = query
        if site:
            search_query = f"site:{site} {query}"

        # Google Custom Search API
        params = {
            "key": SEARCH_API_KEY,
            "cx": SEARCH_ENGINE_ID,
            "q": search_query,
            "num": min(num_results, 10),  # API max is 10
        }

        response = await _make_request(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
        )

        if response.status_code != 200:
            return ToolResult.fail(f"Search API error: {response.status_code}")

        data = response.json()
        items = data.get("items", [])

        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in items
        ]

        return ToolResult.ok(
            results,
            query=query,
            count=len(results),
            total_results=data.get("searchInformation", {}).get("totalResults"),
        )

    except httpx.HTTPError as e:
        logger.error("Search request failed", query=query, error=str(e))
        return ToolResult.fail(f"Search request failed: {e}")
    except Exception as e:
        logger.error("Web search failed", error=str(e))
        return ToolResult.fail(f"Web search failed: {e}")


@tool(
    name="fetch_url",
    description="Fetch content from a URL",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
            "extract_text": {
                "type": "boolean",
                "description": "Extract clean text from HTML",
                "default": True,
            },
            "extract_links": {
                "type": "boolean",
                "description": "Extract links from page",
                "default": False,
            },
        },
        "required": ["url"],
    },
)
async def fetch_url(
    url: str,
    extract_text: bool = True,
    extract_links: bool = False,
) -> ToolResult:
    """Fetch content from a URL."""
    try:
        # Validate URL
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ToolResult.fail(f"Invalid URL scheme: {parsed.scheme}")

        response = await _make_request(url)

        if response.status_code != 200:
            return ToolResult.fail(
                f"HTTP error: {response.status_code}",
                url=url,
                status_code=response.status_code,
            )

        # Check content length
        content_length = len(response.content)
        if content_length > MAX_CONTENT_LENGTH:
            return ToolResult.fail(
                f"Content too large: {content_length} bytes (max: {MAX_CONTENT_LENGTH})"
            )

        content_type = response.headers.get("content-type", "")
        html_content = response.text

        result: dict[str, Any] = {
            "url": str(response.url),  # Final URL after redirects
            "status_code": response.status_code,
            "content_type": content_type,
            "content_length": content_length,
        }

        if "text/html" in content_type:
            if extract_text:
                result["text"] = _extract_text_from_html(html_content)

            if extract_links:
                result["links"] = _extract_links(html_content, str(response.url))

            # Extract title
            soup = BeautifulSoup(html_content, "html.parser")
            title = soup.find("title")
            if title:
                result["title"] = title.get_text(strip=True)

        else:
            # For non-HTML content, include raw text if small
            if content_length < 10000:
                result["content"] = response.text[:10000]
            else:
                result["content"] = f"[Binary or large content: {content_length} bytes]"

        return ToolResult.ok(result)

    except httpx.HTTPError as e:
        logger.error("URL fetch failed", url=url, error=str(e))
        return ToolResult.fail(f"Fetch failed: {e}")
    except Exception as e:
        logger.error("Fetch URL failed", url=url, error=str(e))
        return ToolResult.fail(f"Fetch URL failed: {e}")


@tool(
    name="summarize_page",
    description="Fetch a URL and extract key information",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to summarize",
            },
            "focus": {
                "type": "string",
                "description": "Specific aspect to focus on (e.g., 'installation', 'API')",
            },
        },
        "required": ["url"],
    },
)
async def summarize_page(
    url: str,
    focus: str | None = None,
) -> ToolResult:
    """Fetch and summarize a page."""
    try:
        # Fetch the page
        response = await _make_request(url)

        if response.status_code != 200:
            return ToolResult.fail(f"HTTP error: {response.status_code}")

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return ToolResult.fail("URL is not HTML content")

        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract structured information
        result: dict[str, Any] = {
            "url": str(response.url),
        }

        # Title
        title = soup.find("title")
        if title:
            result["title"] = title.get_text(strip=True)

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            result["description"] = meta_desc.get("content", "")

        # Headings structure
        headings = []
        for level in range(1, 4):
            for h in soup.find_all(f"h{level}"):
                text = h.get_text(strip=True)
                if text:
                    headings.append({
                        "level": level,
                        "text": text[:100],
                    })
        result["headings"] = headings[:20]

        # Main content (try common content selectors)
        main_content = None
        for selector in ["main", "article", '[role="main"]', ".content", "#content"]:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if main_content:
            text = _extract_text_from_html(str(main_content), max_length=5000)
        else:
            text = _extract_text_from_html(html_content, max_length=5000)

        # If focus is specified, try to find relevant sections
        if focus:
            focus_lower = focus.lower()
            relevant_text = []
            paragraphs = text.split("\n\n")
            for para in paragraphs:
                if focus_lower in para.lower():
                    relevant_text.append(para)
            if relevant_text:
                result["focused_content"] = "\n\n".join(relevant_text[:5])
            else:
                result["focused_content"] = f"No content matching '{focus}' found"

        result["content"] = text

        # Code blocks (if any)
        code_blocks = []
        for pre in soup.find_all("pre"):
            code = pre.get_text(strip=True)
            if code:
                code_blocks.append(code[:500])
        if code_blocks:
            result["code_examples"] = code_blocks[:5]

        return ToolResult.ok(result)

    except httpx.HTTPError as e:
        logger.error("Page summarize failed", url=url, error=str(e))
        return ToolResult.fail(f"Summarize failed: {e}")
    except Exception as e:
        logger.error("Summarize page failed", url=url, error=str(e))
        return ToolResult.fail(f"Summarize page failed: {e}")
