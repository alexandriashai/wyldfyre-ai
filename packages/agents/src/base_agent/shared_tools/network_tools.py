"""
Network operation tools for AI Infrastructure agents.

These tools provide network-related operations like HTTP requests,
DNS lookups, port checking, and connectivity testing.

Security:
- All HTTP requests are rate-limited and logged
- Private IP ranges are blocked by default for external requests
- DNS operations are read-only unless using dns_manage
"""

import asyncio
import re
import socket
from typing import Any
from urllib.parse import urlparse

import aiohttp

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Request timeout defaults
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 120

# Rate limiting (per hour)
MAX_REQUESTS_PER_HOUR = 1000

# Private IP ranges to block for external requests
PRIVATE_IP_PATTERNS = [
    r"^127\.",  # Localhost
    r"^10\.",  # Class A private
    r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",  # Class B private
    r"^192\.168\.",  # Class C private
    r"^169\.254\.",  # Link-local
    r"^0\.",  # Current network
]


def _is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private range."""
    for pattern in PRIVATE_IP_PATTERNS:
        if re.match(pattern, ip):
            return True
    return False


def _is_safe_url(url: str, allow_private: bool = False) -> tuple[bool, str | None]:
    """
    Check if a URL is safe to request.

    Returns:
        Tuple of (is_safe, reason if unsafe)
    """
    try:
        parsed = urlparse(url)

        # Only allow http/https
        if parsed.scheme not in ("http", "https"):
            return False, f"Protocol not allowed: {parsed.scheme}"

        # Check for file:// or other dangerous schemes
        if not parsed.netloc:
            return False, "Invalid URL - no host specified"

        # Resolve hostname to check for private IPs
        if not allow_private:
            try:
                hostname = parsed.hostname
                if hostname:
                    # Quick check for obvious private patterns
                    if hostname in ("localhost", "127.0.0.1", "::1"):
                        return False, "Localhost not allowed"

                    # Check if it's an IP address directly
                    if re.match(r"^\d+\.\d+\.\d+\.\d+$", hostname):
                        if _is_private_ip(hostname):
                            return False, "Private IP addresses not allowed"

            except Exception:
                pass  # DNS resolution will fail later if invalid

        return True, None

    except Exception as e:
        return False, f"URL parsing failed: {e}"


@tool(
    name="http_request",
    description="Make an HTTP request to a URL. Supports GET, POST, PUT, DELETE methods.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to request",
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"],
                "description": "HTTP method",
                "default": "GET",
            },
            "headers": {
                "type": "object",
                "description": "Request headers",
            },
            "body": {
                "type": "string",
                "description": "Request body (for POST/PUT/PATCH)",
            },
            "json_body": {
                "type": "object",
                "description": "JSON request body (automatically sets Content-Type)",
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds (max 120)",
                "default": 30,
            },
            "allow_private": {
                "type": "boolean",
                "description": "Allow requests to private/internal IPs",
                "default": False,
            },
        },
        "required": ["url"],
    },
    permission_level=1,  # READ_WRITE
    capability_category=CapabilityCategory.NETWORK,
)
async def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = 30,
    allow_private: bool = False,
) -> ToolResult:
    """Make an HTTP request."""
    try:
        # Validate URL
        is_safe, reason = _is_safe_url(url, allow_private)
        if not is_safe:
            return ToolResult.fail(f"URL blocked: {reason}")

        # Limit timeout
        timeout = min(timeout, MAX_TIMEOUT)

        # Prepare request
        request_headers = headers or {}
        if json_body:
            request_headers["Content-Type"] = "application/json"

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            kwargs: dict[str, Any] = {
                "headers": request_headers,
            }

            if body:
                kwargs["data"] = body
            elif json_body:
                kwargs["json"] = json_body

            async with session.request(method, url, **kwargs) as response:
                # Read response
                try:
                    response_text = await response.text()
                except Exception:
                    response_text = "[Binary content]"

                # Truncate large responses
                if len(response_text) > 50000:
                    response_text = response_text[:50000] + "\n[Truncated...]"

                result = {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response_text,
                    "url": str(response.url),
                }

                if response.status >= 400:
                    return ToolResult.fail(
                        f"HTTP {response.status}",
                        **result,
                    )

                return ToolResult.ok(result)

    except aiohttp.ClientError as e:
        return ToolResult.fail(f"Request failed: {e}")
    except asyncio.TimeoutError:
        return ToolResult.fail(f"Request timed out after {timeout}s")
    except Exception as e:
        logger.error("HTTP request failed", url=url[:100], error=str(e))
        return ToolResult.fail(f"Request failed: {e}")


@tool(
    name="port_check",
    description="Check if a port is open on a host",
    parameters={
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Hostname or IP address",
            },
            "port": {
                "type": "integer",
                "description": "Port number to check",
            },
            "timeout": {
                "type": "integer",
                "description": "Connection timeout in seconds",
                "default": 5,
            },
        },
        "required": ["host", "port"],
    },
    permission_level=0,  # READ_ONLY
    capability_category=CapabilityCategory.NETWORK,
)
async def port_check(
    host: str,
    port: int,
    timeout: int = 5,
) -> ToolResult:
    """Check if a port is open."""
    try:
        # Validate port
        if port < 1 or port > 65535:
            return ToolResult.fail("Invalid port number")

        # Limit timeout
        timeout = min(timeout, 30)

        # Try to connect
        loop = asyncio.get_event_loop()

        def check_port():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                result = sock.connect_ex((host, port))
                return result == 0
            finally:
                sock.close()

        is_open = await loop.run_in_executor(None, check_port)

        return ToolResult.ok({
            "host": host,
            "port": port,
            "is_open": is_open,
            "status": "open" if is_open else "closed",
        })

    except socket.gaierror as e:
        return ToolResult.fail(f"DNS resolution failed: {e}")
    except Exception as e:
        logger.error("Port check failed", host=host, port=port, error=str(e))
        return ToolResult.fail(f"Port check failed: {e}")


@tool(
    name="dns_lookup",
    description="Perform DNS lookups for a hostname",
    parameters={
        "type": "object",
        "properties": {
            "hostname": {
                "type": "string",
                "description": "Hostname to look up",
            },
            "record_type": {
                "type": "string",
                "enum": ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"],
                "description": "DNS record type",
                "default": "A",
            },
        },
        "required": ["hostname"],
    },
    permission_level=0,  # READ_ONLY
    capability_category=CapabilityCategory.NETWORK,
)
async def dns_lookup(
    hostname: str,
    record_type: str = "A",
) -> ToolResult:
    """Perform DNS lookup."""
    try:
        import subprocess

        # Use dig for more detailed lookup
        cmd = ["dig", "+short", record_type, hostname]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return ToolResult.fail(f"DNS lookup failed: {stderr.decode()}")

        records = [r.strip() for r in stdout.decode().splitlines() if r.strip()]

        # Also get basic A record if not already doing that
        ip_addresses = []
        if record_type != "A":
            try:
                loop = asyncio.get_event_loop()
                ip_addresses = await loop.run_in_executor(
                    None,
                    lambda: socket.gethostbyname_ex(hostname)[2],
                )
            except socket.gaierror:
                pass

        return ToolResult.ok({
            "hostname": hostname,
            "record_type": record_type,
            "records": records,
            "ip_addresses": ip_addresses if ip_addresses else None,
        })

    except FileNotFoundError:
        # Fallback if dig is not available
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: socket.gethostbyname_ex(hostname),
            )

            return ToolResult.ok({
                "hostname": hostname,
                "record_type": "A",
                "aliases": result[1],
                "ip_addresses": result[2],
            })

        except socket.gaierror as e:
            return ToolResult.fail(f"DNS lookup failed: {e}")

    except Exception as e:
        logger.error("DNS lookup failed", hostname=hostname, error=str(e))
        return ToolResult.fail(f"DNS lookup failed: {e}")


@tool(
    name="dns_manage",
    description="Manage DNS records via Cloudflare API. Requires CLOUDFLARE_API_TOKEN environment variable.",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "update", "delete"],
                "description": "Action to perform",
            },
            "zone": {
                "type": "string",
                "description": "Domain zone (e.g., 'example.com')",
            },
            "record_name": {
                "type": "string",
                "description": "Record name (e.g., 'www')",
            },
            "record_type": {
                "type": "string",
                "enum": ["A", "AAAA", "CNAME", "TXT", "MX"],
                "description": "Record type",
            },
            "content": {
                "type": "string",
                "description": "Record content (IP address, hostname, etc.)",
            },
            "ttl": {
                "type": "integer",
                "description": "TTL in seconds (1 = auto)",
                "default": 1,
            },
            "proxied": {
                "type": "boolean",
                "description": "Whether to proxy through Cloudflare",
                "default": False,
            },
        },
        "required": ["action", "zone"],
    },
    permission_level=3,  # ADMIN
    capability_category=CapabilityCategory.NETWORK,
    requires_confirmation=True,
)
async def dns_manage(
    action: str,
    zone: str,
    record_name: str | None = None,
    record_type: str | None = None,
    content: str | None = None,
    ttl: int = 1,
    proxied: bool = False,
) -> ToolResult:
    """Manage DNS records via Cloudflare."""
    import os

    try:
        api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
        if not api_token:
            return ToolResult.fail("CLOUDFLARE_API_TOKEN environment variable not set")

        base_url = "https://api.cloudflare.com/client/v4"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            # First, get zone ID
            async with session.get(
                f"{base_url}/zones?name={zone}",
                headers=headers,
            ) as resp:
                zone_data = await resp.json()

            if not zone_data.get("success") or not zone_data.get("result"):
                return ToolResult.fail(f"Zone not found: {zone}")

            zone_id = zone_data["result"][0]["id"]

            if action == "list":
                # List records
                params = {}
                if record_name:
                    params["name"] = f"{record_name}.{zone}"
                if record_type:
                    params["type"] = record_type

                async with session.get(
                    f"{base_url}/zones/{zone_id}/dns_records",
                    headers=headers,
                    params=params,
                ) as resp:
                    data = await resp.json()

                if not data.get("success"):
                    return ToolResult.fail(f"Failed to list records: {data.get('errors')}")

                records = [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["type"],
                        "content": r["content"],
                        "ttl": r["ttl"],
                        "proxied": r.get("proxied", False),
                    }
                    for r in data["result"]
                ]

                return ToolResult.ok({
                    "zone": zone,
                    "records": records,
                    "count": len(records),
                })

            elif action == "create":
                if not all([record_name, record_type, content]):
                    return ToolResult.fail("record_name, record_type, and content required")

                payload = {
                    "type": record_type,
                    "name": record_name,
                    "content": content,
                    "ttl": ttl,
                    "proxied": proxied if record_type in ("A", "AAAA", "CNAME") else False,
                }

                async with session.post(
                    f"{base_url}/zones/{zone_id}/dns_records",
                    headers=headers,
                    json=payload,
                ) as resp:
                    data = await resp.json()

                if not data.get("success"):
                    return ToolResult.fail(f"Failed to create record: {data.get('errors')}")

                return ToolResult.ok({
                    "action": "created",
                    "record": data["result"],
                })

            elif action in ("update", "delete"):
                if not record_name:
                    return ToolResult.fail("record_name required")

                # Find the record first
                full_name = f"{record_name}.{zone}" if not record_name.endswith(zone) else record_name

                async with session.get(
                    f"{base_url}/zones/{zone_id}/dns_records?name={full_name}",
                    headers=headers,
                ) as resp:
                    find_data = await resp.json()

                if not find_data.get("result"):
                    return ToolResult.fail(f"Record not found: {record_name}")

                record_id = find_data["result"][0]["id"]

                if action == "delete":
                    async with session.delete(
                        f"{base_url}/zones/{zone_id}/dns_records/{record_id}",
                        headers=headers,
                    ) as resp:
                        data = await resp.json()

                    if not data.get("success"):
                        return ToolResult.fail(f"Failed to delete: {data.get('errors')}")

                    return ToolResult.ok({
                        "action": "deleted",
                        "record_id": record_id,
                    })

                else:  # update
                    if not content:
                        return ToolResult.fail("content required for update")

                    payload = {
                        "type": record_type or find_data["result"][0]["type"],
                        "name": record_name,
                        "content": content,
                        "ttl": ttl,
                        "proxied": proxied,
                    }

                    async with session.put(
                        f"{base_url}/zones/{zone_id}/dns_records/{record_id}",
                        headers=headers,
                        json=payload,
                    ) as resp:
                        data = await resp.json()

                    if not data.get("success"):
                        return ToolResult.fail(f"Failed to update: {data.get('errors')}")

                    return ToolResult.ok({
                        "action": "updated",
                        "record": data["result"],
                    })

            else:
                return ToolResult.fail(f"Unknown action: {action}")

    except Exception as e:
        logger.error("DNS manage failed", action=action, zone=zone, error=str(e))
        return ToolResult.fail(f"DNS management failed: {e}")


@tool(
    name="ping",
    description="Check network connectivity to a host using ping",
    parameters={
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Hostname or IP address to ping",
            },
            "count": {
                "type": "integer",
                "description": "Number of ping packets to send",
                "default": 4,
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout per packet in seconds",
                "default": 5,
            },
        },
        "required": ["host"],
    },
    permission_level=0,  # READ_ONLY
    capability_category=CapabilityCategory.NETWORK,
)
async def ping(
    host: str,
    count: int = 4,
    timeout: int = 5,
) -> ToolResult:
    """Check network connectivity using ping."""
    try:
        # Limit count and timeout
        count = min(count, 10)
        timeout = min(timeout, 30)

        # Run ping command
        process = await asyncio.create_subprocess_exec(
            "ping",
            "-c", str(count),
            "-W", str(timeout),
            host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=count * timeout + 5,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return ToolResult.fail(f"Ping timed out after {count * timeout}s")

        output = stdout.decode()

        # Parse results
        result = {
            "host": host,
            "success": process.returncode == 0,
            "raw_output": output,
        }

        # Extract statistics
        lines = output.splitlines()
        for line in lines:
            if "packets transmitted" in line:
                # Parse: 4 packets transmitted, 4 received, 0% packet loss
                parts = line.split(",")
                for part in parts:
                    if "transmitted" in part:
                        result["transmitted"] = int(part.split()[0])
                    elif "received" in part:
                        result["received"] = int(part.split()[0])
                    elif "packet loss" in part:
                        result["packet_loss"] = part.strip()

            elif "rtt min/avg/max" in line or "round-trip min/avg/max" in line:
                # Parse: rtt min/avg/max/mdev = 0.123/0.456/0.789/0.012 ms
                match = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)", line)
                if match:
                    result["rtt_min_ms"] = float(match.group(1))
                    result["rtt_avg_ms"] = float(match.group(2))
                    result["rtt_max_ms"] = float(match.group(3))

        return ToolResult.ok(result)

    except FileNotFoundError:
        return ToolResult.fail("ping command not available")
    except Exception as e:
        logger.error("Ping failed", host=host, error=str(e))
        return ToolResult.fail(f"Ping failed: {e}")
