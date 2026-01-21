"""
Grafana proxy routes for SSO integration.

Proxies requests to Grafana with authentication headers,
allowing users logged into the web app to access Grafana seamlessly.
"""

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from ai_core import get_logger, get_settings

from ..dependencies import CurrentUserDep, CurrentUserOptionalDep

logger = get_logger(__name__)

router = APIRouter(prefix="/grafana", tags=["Grafana"])

# Grafana backend URL (internal Docker network)
GRAFANA_URL = "http://grafana:3000"


async def proxy_to_grafana(
    request: Request,
    path: str,
    user_email: str | None = None,
) -> Response:
    """
    Proxy request to Grafana backend.

    Args:
        request: The incoming request
        path: The path to proxy to
        user_email: The authenticated user's email (for X-WEBAUTH-USER header)

    Returns:
        The proxied response
    """
    # Build target URL
    target_url = f"{GRAFANA_URL}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Copy headers, excluding host
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("Host", None)

    # Add auth proxy header if user is authenticated
    if user_email:
        headers["X-WEBAUTH-USER"] = user_email
        logger.debug("Proxying to Grafana with auth", user=user_email, path=path)

    # Get request body if present
    body = await request.body() if request.method in ("POST", "PUT", "PATCH") else None

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=False,
            )

            # Build response headers, excluding hop-by-hop headers
            excluded_headers = {
                "content-encoding",
                "content-length",
                "transfer-encoding",
                "connection",
            }
            response_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in excluded_headers
            }

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type"),
            )

        except httpx.RequestError as e:
            logger.error("Grafana proxy error", error=str(e), path=path)
            return Response(
                content=f"Grafana proxy error: {e}",
                status_code=502,
                media_type="text/plain",
            )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def grafana_proxy(
    request: Request,
    path: str,
    current_user: CurrentUserOptionalDep,
) -> Response:
    """
    Proxy all requests to Grafana.

    If user is authenticated, includes X-WEBAUTH-USER header for SSO.
    Anonymous access is still allowed if Grafana permits it.
    """
    user_email = current_user.email if current_user else None
    return await proxy_to_grafana(request, path, user_email)


@router.get("")
async def grafana_root(
    request: Request,
    current_user: CurrentUserOptionalDep,
) -> Response:
    """Proxy root Grafana requests."""
    user_email = current_user.email if current_user else None
    return await proxy_to_grafana(request, "", user_email)
