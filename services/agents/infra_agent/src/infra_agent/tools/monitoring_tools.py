"""
Infrastructure monitoring tools for the Infra Agent.

These tools provide advanced monitoring capabilities:
- Network port scanning and connection stats
- Log analysis and pattern searching
- Disk I/O monitoring
- Network interface statistics
"""

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)


async def _run_command(
    command: str,
    timeout: int = 60,
) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
        return (
            process.returncode or 0,
            stdout.decode().strip(),
            stderr.decode().strip(),
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise TimeoutError(f"Command timed out after {timeout}s")


@tool(
    name="check_port",
    description="""Check if a TCP port is open on a host.
    Use this to verify service availability.""",
    parameters={
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Host to check (default: localhost)",
                "default": "localhost",
            },
            "port": {
                "type": "integer",
                "description": "Port number to check",
            },
            "timeout": {
                "type": "number",
                "description": "Connection timeout in seconds",
                "default": 5,
            },
        },
        "required": ["port"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def check_port(
    port: int,
    host: str = "localhost",
    timeout: float = 5,
) -> ToolResult:
    """Check if a TCP port is open."""
    try:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            is_open = True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            is_open = False

        return ToolResult.ok({
            "message": f"Port {port} on {host} is {'open' if is_open else 'closed'}",
            "host": host,
            "port": port,
            "is_open": is_open,
        })

    except Exception as e:
        logger.error("Check port failed", host=host, port=port, error=str(e))
        return ToolResult.fail(f"Check port failed: {e}")


@tool(
    name="scan_ports",
    description="""Scan a range of TCP ports on a host.
    Use this to discover available services.""",
    parameters={
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Host to scan",
                "default": "localhost",
            },
            "ports": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of ports to scan (default: common ports)",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout per port",
                "default": 2,
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def scan_ports(
    host: str = "localhost",
    ports: list[int] | None = None,
    timeout: float = 2,
) -> ToolResult:
    """Scan a range of TCP ports."""
    try:
        # Default to common ports
        if not ports:
            ports = [22, 80, 443, 3000, 3306, 5432, 6379, 6333, 8000, 8080, 9090]

        # Limit ports to scan
        ports = ports[:50]

        async def check_single_port(p: int) -> dict:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, p),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                return {"port": p, "status": "open"}
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                return {"port": p, "status": "closed"}

        # Scan ports concurrently
        results = await asyncio.gather(
            *[check_single_port(p) for p in ports]
        )

        open_ports = [r for r in results if r["status"] == "open"]
        closed_ports = [r for r in results if r["status"] == "closed"]

        return ToolResult.ok({
            "message": f"Scanned {len(ports)} ports: {len(open_ports)} open, {len(closed_ports)} closed",
            "host": host,
            "open_ports": [r["port"] for r in open_ports],
            "closed_ports": [r["port"] for r in closed_ports],
            "total_scanned": len(ports),
        })

    except Exception as e:
        logger.error("Port scan failed", host=host, error=str(e))
        return ToolResult.fail(f"Port scan failed: {e}")


@tool(
    name="get_network_connections",
    description="""Get active network connections and listening ports.
    Shows established connections and services listening for connections.""",
    parameters={
        "type": "object",
        "properties": {
            "state": {
                "type": "string",
                "enum": ["all", "listen", "established"],
                "description": "Filter by connection state",
                "default": "all",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum connections to return",
                "default": 100,
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def get_network_connections(
    state: str = "all",
    limit: int = 100,
) -> ToolResult:
    """Get active network connections."""
    try:
        # Build ss command based on state filter
        if state == "listen":
            cmd = "ss -tlnp"
        elif state == "established":
            cmd = "ss -tnp state established"
        else:
            cmd = "ss -tnp"

        code, stdout, stderr = await _run_command(cmd)

        if code != 0:
            return ToolResult.fail(f"ss command failed: {stderr}")

        lines = stdout.splitlines()
        connections = []

        # Parse ss output
        for line in lines[1:]:  # Skip header
            if len(connections) >= limit:
                break

            parts = line.split()
            if len(parts) >= 5:
                conn = {
                    "state": parts[0],
                    "recv_q": parts[1],
                    "send_q": parts[2],
                    "local": parts[3],
                    "peer": parts[4],
                }
                # Extract process if available
                if len(parts) > 5:
                    process_match = re.search(r'"([^"]+)"', parts[-1])
                    if process_match:
                        conn["process"] = process_match.group(1)
                connections.append(conn)

        # Summary
        listening = len([c for c in connections if c["state"] == "LISTEN"])
        established = len([c for c in connections if c["state"] == "ESTAB"])

        return ToolResult.ok({
            "message": f"Found {len(connections)} connections ({listening} listening, {established} established)",
            "connections": connections,
            "summary": {
                "total": len(connections),
                "listening": listening,
                "established": established,
            },
        })

    except Exception as e:
        logger.error("Get network connections failed", error=str(e))
        return ToolResult.fail(f"Get network connections failed: {e}")


@tool(
    name="get_network_stats",
    description="""Get network interface statistics including bytes/packets transmitted and received.""",
    parameters={
        "type": "object",
        "properties": {
            "interface": {
                "type": "string",
                "description": "Specific interface (default: all)",
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def get_network_stats(
    interface: str | None = None,
) -> ToolResult:
    """Get network interface statistics."""
    try:
        interfaces = []

        # Read from /proc/net/dev
        with open("/proc/net/dev", "r") as f:
            lines = f.readlines()

        # Skip header lines
        for line in lines[2:]:
            parts = line.strip().split()
            if not parts:
                continue

            iface_name = parts[0].rstrip(":")

            # Filter if interface specified
            if interface and iface_name != interface:
                continue

            iface_stats = {
                "interface": iface_name,
                "rx_bytes": int(parts[1]),
                "rx_packets": int(parts[2]),
                "rx_errors": int(parts[3]),
                "rx_dropped": int(parts[4]),
                "tx_bytes": int(parts[9]),
                "tx_packets": int(parts[10]),
                "tx_errors": int(parts[11]),
                "tx_dropped": int(parts[12]),
            }

            # Convert to human readable
            iface_stats["rx_bytes_human"] = _bytes_to_human(iface_stats["rx_bytes"])
            iface_stats["tx_bytes_human"] = _bytes_to_human(iface_stats["tx_bytes"])

            interfaces.append(iface_stats)

        return ToolResult.ok({
            "message": f"Retrieved stats for {len(interfaces)} interfaces",
            "interfaces": interfaces,
            "count": len(interfaces),
        })

    except Exception as e:
        logger.error("Get network stats failed", error=str(e))
        return ToolResult.fail(f"Get network stats failed: {e}")


def _bytes_to_human(bytes_val: int) -> str:
    """Convert bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


@tool(
    name="get_disk_io",
    description="""Get disk I/O statistics for block devices.""",
    parameters={
        "type": "object",
        "properties": {
            "device": {
                "type": "string",
                "description": "Specific device (e.g., sda, nvme0n1)",
            },
        },
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def get_disk_io(
    device: str | None = None,
) -> ToolResult:
    """Get disk I/O statistics."""
    try:
        code, stdout, stderr = await _run_command("iostat -dx 1 1 2>/dev/null || cat /proc/diskstats")

        if code != 0 and not stdout:
            # Fall back to /proc/diskstats
            with open("/proc/diskstats", "r") as f:
                stdout = f.read()

        devices = []

        # Try parsing iostat output first
        if "Device" in stdout:
            lines = stdout.splitlines()
            in_device_section = False

            for line in lines:
                if line.startswith("Device"):
                    in_device_section = True
                    continue

                if in_device_section and line.strip():
                    parts = line.split()
                    if len(parts) >= 14:
                        dev_name = parts[0]
                        if device and dev_name != device:
                            continue

                        devices.append({
                            "device": dev_name,
                            "r_s": float(parts[1]),  # reads/s
                            "w_s": float(parts[2]),  # writes/s
                            "rkB_s": float(parts[3]),  # read KB/s
                            "wkB_s": float(parts[4]),  # write KB/s
                            "await": float(parts[9]) if len(parts) > 9 else None,  # avg wait time
                            "util_percent": float(parts[13]) if len(parts) > 13 else None,
                        })
        else:
            # Parse /proc/diskstats
            for line in stdout.splitlines():
                parts = line.split()
                if len(parts) >= 14:
                    dev_name = parts[2]
                    # Skip partitions (usually have numbers)
                    if re.match(r"(sd[a-z]|nvme\d+n\d+)$", dev_name):
                        if device and dev_name != device:
                            continue

                        devices.append({
                            "device": dev_name,
                            "reads_completed": int(parts[3]),
                            "reads_merged": int(parts[4]),
                            "sectors_read": int(parts[5]),
                            "writes_completed": int(parts[7]),
                            "writes_merged": int(parts[8]),
                            "sectors_written": int(parts[9]),
                            "io_in_progress": int(parts[11]),
                        })

        return ToolResult.ok({
            "message": f"Retrieved I/O stats for {len(devices)} devices",
            "devices": devices,
            "count": len(devices),
        })

    except Exception as e:
        logger.error("Get disk I/O failed", error=str(e))
        return ToolResult.fail(f"Get disk I/O failed: {e}")


@tool(
    name="search_logs",
    description="""Search through log files for patterns.
    Supports regex patterns and multiple log sources.""",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Search pattern (regex supported)",
            },
            "log_file": {
                "type": "string",
                "description": "Log file path (default: /var/log/syslog)",
                "default": "/var/log/syslog",
            },
            "lines": {
                "type": "integer",
                "description": "Maximum lines to return",
                "default": 50,
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case sensitive search",
                "default": False,
            },
        },
        "required": ["pattern"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def search_logs(
    pattern: str,
    log_file: str = "/var/log/syslog",
    lines: int = 50,
    case_sensitive: bool = False,
) -> ToolResult:
    """Search through log files."""
    try:
        # Validate log file path (security)
        log_path = Path(log_file)
        if not str(log_path).startswith("/var/log"):
            return ToolResult.fail("Log file must be in /var/log directory")

        if not log_path.exists():
            return ToolResult.fail(f"Log file not found: {log_file}")

        # Build grep command
        # -E = extended regex, -i = case insensitive
        grep_opts = "-Ei" if not case_sensitive else "-E"
        cmd = f"grep {grep_opts} '{pattern}' {log_file} | tail -n {lines}"

        code, stdout, stderr = await _run_command(cmd)

        # grep returns 1 if no matches
        if code not in (0, 1):
            return ToolResult.fail(f"Search failed: {stderr}")

        matches = stdout.splitlines() if stdout else []

        return ToolResult.ok({
            "message": f"Found {len(matches)} matches in {log_file}",
            "log_file": log_file,
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
        })

    except Exception as e:
        logger.error("Search logs failed", pattern=pattern, error=str(e))
        return ToolResult.fail(f"Search logs failed: {e}")


@tool(
    name="tail_log",
    description="""Get the last N lines from a log file.""",
    parameters={
        "type": "object",
        "properties": {
            "log_file": {
                "type": "string",
                "description": "Log file path",
            },
            "lines": {
                "type": "integer",
                "description": "Number of lines to return",
                "default": 50,
            },
        },
        "required": ["log_file"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def tail_log(
    log_file: str,
    lines: int = 50,
) -> ToolResult:
    """Get the last N lines from a log file."""
    try:
        # Validate log file path (security)
        log_path = Path(log_file)
        allowed_dirs = ["/var/log", "/var/lib/docker", "/root"]
        if not any(str(log_path).startswith(d) for d in allowed_dirs):
            return ToolResult.fail("Access to this log file is not allowed")

        if not log_path.exists():
            return ToolResult.fail(f"Log file not found: {log_file}")

        # Limit lines
        lines = min(lines, 500)

        cmd = f"tail -n {lines} {log_file}"
        code, stdout, stderr = await _run_command(cmd)

        if code != 0:
            return ToolResult.fail(f"tail failed: {stderr}")

        log_lines = stdout.splitlines()

        return ToolResult.ok({
            "message": f"Retrieved last {len(log_lines)} lines from {log_file}",
            "log_file": log_file,
            "lines": log_lines,
            "count": len(log_lines),
        })

    except Exception as e:
        logger.error("Tail log failed", log_file=log_file, error=str(e))
        return ToolResult.fail(f"Tail log failed: {e}")


@tool(
    name="check_dns",
    description="""Perform DNS lookup for a domain.""",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain to lookup",
            },
            "record_type": {
                "type": "string",
                "enum": ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA"],
                "description": "DNS record type",
                "default": "A",
            },
            "nameserver": {
                "type": "string",
                "description": "Specific nameserver to use",
            },
        },
        "required": ["domain"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def check_dns(
    domain: str,
    record_type: str = "A",
    nameserver: str | None = None,
) -> ToolResult:
    """Perform DNS lookup."""
    try:
        # Build dig command
        cmd = f"dig +short {record_type} {domain}"
        if nameserver:
            cmd = f"dig @{nameserver} +short {record_type} {domain}"

        code, stdout, stderr = await _run_command(cmd)

        if code != 0:
            return ToolResult.fail(f"DNS lookup failed: {stderr}")

        records = [r.strip() for r in stdout.splitlines() if r.strip()]

        return ToolResult.ok({
            "message": f"Found {len(records)} {record_type} records for {domain}",
            "domain": domain,
            "record_type": record_type,
            "records": records,
            "nameserver": nameserver or "default",
            "count": len(records),
        })

    except Exception as e:
        logger.error("DNS check failed", domain=domain, error=str(e))
        return ToolResult.fail(f"DNS check failed: {e}")


@tool(
    name="ping_host",
    description="""Ping a host to check connectivity and latency.""",
    parameters={
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Host to ping",
            },
            "count": {
                "type": "integer",
                "description": "Number of pings",
                "default": 4,
            },
        },
        "required": ["host"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.MONITORING,
)
async def ping_host(
    host: str,
    count: int = 4,
) -> ToolResult:
    """Ping a host."""
    try:
        count = min(count, 10)  # Limit pings

        cmd = f"ping -c {count} -W 5 {host}"
        code, stdout, stderr = await _run_command(cmd, timeout=30)

        # Parse ping output
        result = {
            "host": host,
            "reachable": code == 0,
        }

        if code == 0:
            # Extract statistics
            for line in stdout.splitlines():
                if "packets transmitted" in line:
                    match = re.search(
                        r"(\d+) packets transmitted, (\d+) received.*?(\d+(?:\.\d+)?)% packet loss",
                        line,
                    )
                    if match:
                        result["packets_sent"] = int(match.group(1))
                        result["packets_received"] = int(match.group(2))
                        result["packet_loss_percent"] = float(match.group(3))

                if "rtt min/avg/max" in line or "round-trip" in line:
                    match = re.search(
                        r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)",
                        line,
                    )
                    if match:
                        result["rtt_min_ms"] = float(match.group(1))
                        result["rtt_avg_ms"] = float(match.group(2))
                        result["rtt_max_ms"] = float(match.group(3))

            result["message"] = f"Host {host} is reachable (avg latency: {result.get('rtt_avg_ms', 'N/A')}ms)"
        else:
            result["message"] = f"Host {host} is not reachable"
            result["error"] = stderr or "Host unreachable"

        return ToolResult.ok(result)

    except Exception as e:
        logger.error("Ping failed", host=host, error=str(e))
        return ToolResult.fail(f"Ping failed: {e}")
