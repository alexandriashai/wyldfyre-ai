"""
Cloudflare integration tools for the Infra Agent.

Provides DNS management and CDN controls via Cloudflare API.
"""

import os
from typing import Any

import aiohttp

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Cloudflare API configuration
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CF_API_EMAIL = os.environ.get("CLOUDFLARE_EMAIL", "")
CF_API_KEY = os.environ.get("CLOUDFLARE_API_KEY", "")
CF_API_BASE = "https://api.cloudflare.com/client/v4"


def _get_headers() -> dict[str, str]:
    """Get authentication headers for Cloudflare API."""
    if CF_API_TOKEN:
        return {
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json",
        }
    elif CF_API_EMAIL and CF_API_KEY:
        return {
            "X-Auth-Email": CF_API_EMAIL,
            "X-Auth-Key": CF_API_KEY,
            "Content-Type": "application/json",
        }
    else:
        return {}


async def _cf_request(
    method: str,
    endpoint: str,
    data: dict | None = None,
    params: dict | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Make a request to Cloudflare API."""
    headers = _get_headers()
    if not headers:
        return False, {"error": "Cloudflare API credentials not configured"}

    url = f"{CF_API_BASE}{endpoint}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                json=data,
                params=params,
            ) as response:
                result = await response.json()

                if response.status >= 400:
                    errors = result.get("errors", [])
                    error_msg = errors[0].get("message") if errors else "Unknown error"
                    return False, {"error": error_msg, "status": response.status}

                return result.get("success", False), result

    except aiohttp.ClientError as e:
        return False, {"error": f"HTTP error: {e}"}
    except Exception as e:
        return False, {"error": f"Request failed: {e}"}


@tool(
    name="cf_list_zones",
    description="List all zones (domains) in the Cloudflare account",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Filter by zone name (domain)",
            },
            "status": {
                "type": "string",
                "enum": ["active", "pending", "initializing", "moved", "deleted"],
                "description": "Filter by zone status",
            },
            "page": {
                "type": "integer",
                "description": "Page number",
                "default": 1,
            },
            "per_page": {
                "type": "integer",
                "description": "Results per page (max 50)",
                "default": 20,
            },
        },
    },
)
async def cf_list_zones(
    name: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> ToolResult:
    """List all zones in the Cloudflare account."""
    try:
        params = {
            "page": page,
            "per_page": min(per_page, 50),
        }

        if name:
            params["name"] = name
        if status:
            params["status"] = status

        success, result = await _cf_request("GET", "/zones", params=params)

        if not success:
            return ToolResult.fail(f"Failed to list zones: {result.get('error')}")

        zones = [
            {
                "id": zone["id"],
                "name": zone["name"],
                "status": zone["status"],
                "paused": zone.get("paused", False),
                "type": zone.get("type"),
                "name_servers": zone.get("name_servers", []),
            }
            for zone in result.get("result", [])
        ]

        return ToolResult.ok(
            zones,
            count=len(zones),
            total_count=result.get("result_info", {}).get("total_count", 0),
            page=page,
        )

    except Exception as e:
        logger.error("List zones failed", error=str(e))
        return ToolResult.fail(f"List zones failed: {e}")


@tool(
    name="cf_get_zone",
    description="Get details for a specific zone",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "domain": {
                "type": "string",
                "description": "Domain name (alternative to zone_id)",
            },
        },
    },
)
async def cf_get_zone(
    zone_id: str | None = None,
    domain: str | None = None,
) -> ToolResult:
    """Get zone details."""
    try:
        if not zone_id and not domain:
            return ToolResult.fail("Either zone_id or domain is required")

        # Look up zone by domain if needed
        if not zone_id and domain:
            success, result = await _cf_request(
                "GET", "/zones", params={"name": domain}
            )
            if not success:
                return ToolResult.fail(f"Zone lookup failed: {result.get('error')}")

            zones = result.get("result", [])
            if not zones:
                return ToolResult.fail(f"Zone not found for domain: {domain}")

            zone_id = zones[0]["id"]

        success, result = await _cf_request("GET", f"/zones/{zone_id}")

        if not success:
            return ToolResult.fail(f"Failed to get zone: {result.get('error')}")

        zone = result.get("result", {})

        return ToolResult.ok(
            {
                "id": zone.get("id"),
                "name": zone.get("name"),
                "status": zone.get("status"),
                "paused": zone.get("paused"),
                "type": zone.get("type"),
                "name_servers": zone.get("name_servers", []),
                "original_name_servers": zone.get("original_name_servers", []),
                "created_on": zone.get("created_on"),
                "modified_on": zone.get("modified_on"),
                "plan": zone.get("plan", {}).get("name"),
            }
        )

    except Exception as e:
        logger.error("Get zone failed", error=str(e))
        return ToolResult.fail(f"Get zone failed: {e}")


@tool(
    name="cf_list_dns_records",
    description="List DNS records for a zone",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "domain": {
                "type": "string",
                "description": "Domain name (alternative to zone_id)",
            },
            "record_type": {
                "type": "string",
                "enum": ["A", "AAAA", "CNAME", "TXT", "MX", "NS", "SRV", "CAA"],
                "description": "Filter by record type",
            },
            "name": {
                "type": "string",
                "description": "Filter by record name",
            },
            "page": {
                "type": "integer",
                "description": "Page number",
                "default": 1,
            },
        },
        "required": [],
    },
)
async def cf_list_dns_records(
    zone_id: str | None = None,
    domain: str | None = None,
    record_type: str | None = None,
    name: str | None = None,
    page: int = 1,
) -> ToolResult:
    """List DNS records for a zone."""
    try:
        if not zone_id and not domain:
            return ToolResult.fail("Either zone_id or domain is required")

        # Look up zone by domain if needed
        if not zone_id and domain:
            success, result = await _cf_request(
                "GET", "/zones", params={"name": domain}
            )
            if not success or not result.get("result"):
                return ToolResult.fail(f"Zone not found for domain: {domain}")
            zone_id = result["result"][0]["id"]

        params = {"page": page, "per_page": 50}
        if record_type:
            params["type"] = record_type
        if name:
            params["name"] = name

        success, result = await _cf_request(
            "GET", f"/zones/{zone_id}/dns_records", params=params
        )

        if not success:
            return ToolResult.fail(f"Failed to list DNS records: {result.get('error')}")

        records = [
            {
                "id": rec["id"],
                "type": rec["type"],
                "name": rec["name"],
                "content": rec["content"],
                "proxied": rec.get("proxied", False),
                "ttl": rec["ttl"],
                "priority": rec.get("priority"),
            }
            for rec in result.get("result", [])
        ]

        return ToolResult.ok(
            records,
            count=len(records),
            zone_id=zone_id,
        )

    except Exception as e:
        logger.error("List DNS records failed", error=str(e))
        return ToolResult.fail(f"List DNS records failed: {e}")


@tool(
    name="cf_create_dns_record",
    description="Create a new DNS record",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "domain": {
                "type": "string",
                "description": "Domain name (alternative to zone_id)",
            },
            "record_type": {
                "type": "string",
                "enum": ["A", "AAAA", "CNAME", "TXT", "MX", "NS", "SRV", "CAA"],
                "description": "DNS record type",
            },
            "name": {
                "type": "string",
                "description": "DNS record name (e.g., 'www' or '@' for root)",
            },
            "content": {
                "type": "string",
                "description": "DNS record content (IP address, hostname, etc.)",
            },
            "ttl": {
                "type": "integer",
                "description": "Time to live (1 = auto, otherwise 60-86400)",
                "default": 1,
            },
            "proxied": {
                "type": "boolean",
                "description": "Whether to proxy through Cloudflare (A/AAAA/CNAME only)",
                "default": False,
            },
            "priority": {
                "type": "integer",
                "description": "Priority for MX/SRV records",
            },
        },
        "required": ["record_type", "name", "content"],
    },
    permission_level=2,
)
async def cf_create_dns_record(
    record_type: str,
    name: str,
    content: str,
    zone_id: str | None = None,
    domain: str | None = None,
    ttl: int = 1,
    proxied: bool = False,
    priority: int | None = None,
) -> ToolResult:
    """Create a new DNS record."""
    try:
        if not zone_id and not domain:
            return ToolResult.fail("Either zone_id or domain is required")

        # Look up zone by domain if needed
        if not zone_id and domain:
            success, result = await _cf_request(
                "GET", "/zones", params={"name": domain}
            )
            if not success or not result.get("result"):
                return ToolResult.fail(f"Zone not found for domain: {domain}")
            zone_id = result["result"][0]["id"]

        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
        }

        # Only add proxied for supported record types
        if record_type in ["A", "AAAA", "CNAME"]:
            data["proxied"] = proxied

        if priority is not None and record_type in ["MX", "SRV"]:
            data["priority"] = priority

        success, result = await _cf_request(
            "POST", f"/zones/{zone_id}/dns_records", data=data
        )

        if not success:
            return ToolResult.fail(
                f"Failed to create DNS record: {result.get('error')}"
            )

        record = result.get("result", {})

        return ToolResult.ok(
            "DNS record created successfully",
            record_id=record.get("id"),
            record_type=record.get("type"),
            name=record.get("name"),
            content=record.get("content"),
        )

    except Exception as e:
        logger.error("Create DNS record failed", error=str(e))
        return ToolResult.fail(f"Create DNS record failed: {e}")


@tool(
    name="cf_update_dns_record",
    description="Update an existing DNS record",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "record_id": {
                "type": "string",
                "description": "DNS record ID to update",
            },
            "record_type": {
                "type": "string",
                "enum": ["A", "AAAA", "CNAME", "TXT", "MX", "NS", "SRV", "CAA"],
                "description": "DNS record type",
            },
            "name": {
                "type": "string",
                "description": "DNS record name",
            },
            "content": {
                "type": "string",
                "description": "DNS record content",
            },
            "ttl": {
                "type": "integer",
                "description": "Time to live",
            },
            "proxied": {
                "type": "boolean",
                "description": "Whether to proxy through Cloudflare",
            },
        },
        "required": ["zone_id", "record_id", "record_type", "name", "content"],
    },
    permission_level=2,
)
async def cf_update_dns_record(
    zone_id: str,
    record_id: str,
    record_type: str,
    name: str,
    content: str,
    ttl: int | None = None,
    proxied: bool | None = None,
) -> ToolResult:
    """Update an existing DNS record."""
    try:
        data = {
            "type": record_type,
            "name": name,
            "content": content,
        }

        if ttl is not None:
            data["ttl"] = ttl

        if proxied is not None and record_type in ["A", "AAAA", "CNAME"]:
            data["proxied"] = proxied

        success, result = await _cf_request(
            "PUT", f"/zones/{zone_id}/dns_records/{record_id}", data=data
        )

        if not success:
            return ToolResult.fail(
                f"Failed to update DNS record: {result.get('error')}"
            )

        record = result.get("result", {})

        return ToolResult.ok(
            "DNS record updated successfully",
            record_id=record.get("id"),
            name=record.get("name"),
            content=record.get("content"),
        )

    except Exception as e:
        logger.error("Update DNS record failed", error=str(e))
        return ToolResult.fail(f"Update DNS record failed: {e}")


@tool(
    name="cf_delete_dns_record",
    description="Delete a DNS record",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "record_id": {
                "type": "string",
                "description": "DNS record ID to delete",
            },
        },
        "required": ["zone_id", "record_id"],
    },
    permission_level=2,
)
async def cf_delete_dns_record(zone_id: str, record_id: str) -> ToolResult:
    """Delete a DNS record."""
    try:
        success, result = await _cf_request(
            "DELETE", f"/zones/{zone_id}/dns_records/{record_id}"
        )

        if not success:
            return ToolResult.fail(
                f"Failed to delete DNS record: {result.get('error')}"
            )

        return ToolResult.ok(
            "DNS record deleted successfully",
            record_id=record_id,
        )

    except Exception as e:
        logger.error("Delete DNS record failed", error=str(e))
        return ToolResult.fail(f"Delete DNS record failed: {e}")


@tool(
    name="cf_purge_cache",
    description="Purge Cloudflare cache for a zone",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "domain": {
                "type": "string",
                "description": "Domain name (alternative to zone_id)",
            },
            "purge_everything": {
                "type": "boolean",
                "description": "Purge all cached content",
                "default": False,
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific file URLs to purge",
            },
            "hosts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Hostnames to purge",
            },
        },
    },
    permission_level=2,
)
async def cf_purge_cache(
    zone_id: str | None = None,
    domain: str | None = None,
    purge_everything: bool = False,
    files: list[str] | None = None,
    hosts: list[str] | None = None,
) -> ToolResult:
    """Purge Cloudflare cache."""
    try:
        if not zone_id and not domain:
            return ToolResult.fail("Either zone_id or domain is required")

        # Look up zone by domain if needed
        if not zone_id and domain:
            success, result = await _cf_request(
                "GET", "/zones", params={"name": domain}
            )
            if not success or not result.get("result"):
                return ToolResult.fail(f"Zone not found for domain: {domain}")
            zone_id = result["result"][0]["id"]

        # Build purge request
        data: dict[str, Any] = {}

        if purge_everything:
            data["purge_everything"] = True
        elif files:
            data["files"] = files
        elif hosts:
            data["hosts"] = hosts
        else:
            return ToolResult.fail(
                "Specify purge_everything, files, or hosts to purge"
            )

        success, result = await _cf_request(
            "POST", f"/zones/{zone_id}/purge_cache", data=data
        )

        if not success:
            return ToolResult.fail(f"Failed to purge cache: {result.get('error')}")

        return ToolResult.ok(
            "Cache purged successfully",
            zone_id=zone_id,
            purge_everything=purge_everything,
            files_purged=len(files) if files else 0,
            hosts_purged=len(hosts) if hosts else 0,
        )

    except Exception as e:
        logger.error("Purge cache failed", error=str(e))
        return ToolResult.fail(f"Purge cache failed: {e}")


@tool(
    name="cf_set_ssl_mode",
    description="Set SSL/TLS encryption mode for a zone",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "domain": {
                "type": "string",
                "description": "Domain name (alternative to zone_id)",
            },
            "ssl_mode": {
                "type": "string",
                "enum": ["off", "flexible", "full", "strict"],
                "description": "SSL mode (off/flexible/full/strict)",
            },
        },
        "required": ["ssl_mode"],
    },
    permission_level=2,
)
async def cf_set_ssl_mode(
    ssl_mode: str,
    zone_id: str | None = None,
    domain: str | None = None,
) -> ToolResult:
    """Set SSL/TLS encryption mode."""
    try:
        if not zone_id and not domain:
            return ToolResult.fail("Either zone_id or domain is required")

        # Look up zone by domain if needed
        if not zone_id and domain:
            success, result = await _cf_request(
                "GET", "/zones", params={"name": domain}
            )
            if not success or not result.get("result"):
                return ToolResult.fail(f"Zone not found for domain: {domain}")
            zone_id = result["result"][0]["id"]

        success, result = await _cf_request(
            "PATCH",
            f"/zones/{zone_id}/settings/ssl",
            data={"value": ssl_mode},
        )

        if not success:
            return ToolResult.fail(f"Failed to set SSL mode: {result.get('error')}")

        return ToolResult.ok(
            "SSL mode updated successfully",
            zone_id=zone_id,
            ssl_mode=ssl_mode,
        )

    except Exception as e:
        logger.error("Set SSL mode failed", error=str(e))
        return ToolResult.fail(f"Set SSL mode failed: {e}")


@tool(
    name="cf_get_analytics",
    description="Get analytics data for a zone",
    parameters={
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Zone ID",
            },
            "domain": {
                "type": "string",
                "description": "Domain name (alternative to zone_id)",
            },
            "since": {
                "type": "string",
                "description": "Start time (ISO 8601 format or relative like -1440 for last 24h)",
                "default": "-1440",
            },
            "until": {
                "type": "string",
                "description": "End time (ISO 8601 format or relative)",
                "default": "0",
            },
        },
    },
)
async def cf_get_analytics(
    zone_id: str | None = None,
    domain: str | None = None,
    since: str = "-1440",
    until: str = "0",
) -> ToolResult:
    """Get zone analytics."""
    try:
        if not zone_id and not domain:
            return ToolResult.fail("Either zone_id or domain is required")

        # Look up zone by domain if needed
        if not zone_id and domain:
            success, result = await _cf_request(
                "GET", "/zones", params={"name": domain}
            )
            if not success or not result.get("result"):
                return ToolResult.fail(f"Zone not found for domain: {domain}")
            zone_id = result["result"][0]["id"]

        params = {
            "since": since,
            "until": until,
        }

        success, result = await _cf_request(
            "GET", f"/zones/{zone_id}/analytics/dashboard", params=params
        )

        if not success:
            return ToolResult.fail(f"Failed to get analytics: {result.get('error')}")

        analytics = result.get("result", {})

        # Extract key metrics
        totals = analytics.get("totals", {})
        timeseries = analytics.get("timeseries", [])

        return ToolResult.ok(
            {
                "requests": {
                    "all": totals.get("requests", {}).get("all", 0),
                    "cached": totals.get("requests", {}).get("cached", 0),
                    "uncached": totals.get("requests", {}).get("uncached", 0),
                },
                "bandwidth": {
                    "all": totals.get("bandwidth", {}).get("all", 0),
                    "cached": totals.get("bandwidth", {}).get("cached", 0),
                    "uncached": totals.get("bandwidth", {}).get("uncached", 0),
                },
                "threats": totals.get("threats", {}).get("all", 0),
                "pageviews": totals.get("pageviews", {}).get("all", 0),
                "uniques": totals.get("uniques", {}).get("all", 0),
                "timeseries_points": len(timeseries),
            },
            zone_id=zone_id,
            period=f"{since} to {until}",
        )

    except Exception as e:
        logger.error("Get analytics failed", error=str(e))
        return ToolResult.fail(f"Get analytics failed: {e}")
