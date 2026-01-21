"""
SSL/TLS certificate tools for the Infra Agent.
"""

import asyncio
import os
import socket
import ssl
import subprocess
from datetime import datetime
from pathlib import Path

from ai_core import get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Certificate paths
CERT_DIR = Path(os.environ.get("CERT_DIR", "/etc/letsencrypt/live"))
CERTBOT_PATH = os.environ.get("CERTBOT_PATH", "certbot")


async def _run_certbot_command(args: list[str]) -> tuple[int, str, str]:
    """Run a certbot command and return (returncode, stdout, stderr)."""
    process = await asyncio.create_subprocess_exec(
        CERTBOT_PATH,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    return (
        process.returncode or 0,
        stdout.decode().strip(),
        stderr.decode().strip(),
    )


def _get_cert_info(domain: str) -> dict | None:
    """Get certificate information for a domain."""
    cert_path = CERT_DIR / domain / "fullchain.pem"
    key_path = CERT_DIR / domain / "privkey.pem"

    if not cert_path.exists():
        return None

    try:
        # Read certificate using openssl command
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-dates", "-subject"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        info = {
            "domain": domain,
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "exists": True,
        }

        # Parse output
        for line in result.stdout.splitlines():
            if line.startswith("notBefore="):
                date_str = line.split("=", 1)[1]
                info["not_before"] = date_str
            elif line.startswith("notAfter="):
                date_str = line.split("=", 1)[1]
                info["not_after"] = date_str
                # Parse expiry date
                try:
                    expiry = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
                    info["expires"] = expiry.isoformat()
                    info["days_until_expiry"] = (expiry - datetime.now()).days
                except ValueError:
                    pass
            elif line.startswith("subject="):
                info["subject"] = line.split("=", 1)[1]

        return info

    except Exception as e:
        logger.error("Failed to get cert info", domain=domain, error=str(e))
        return None


@tool(
    name="list_certificates",
    description="List all SSL certificates managed by Let's Encrypt",
    parameters={
        "type": "object",
        "properties": {},
    },
)
async def list_certificates() -> ToolResult:
    """List all certificates."""
    try:
        certificates = []

        if CERT_DIR.exists():
            for domain_dir in CERT_DIR.iterdir():
                if domain_dir.is_dir():
                    cert_info = _get_cert_info(domain_dir.name)
                    if cert_info:
                        certificates.append(cert_info)

        # Sort by expiry date
        certificates.sort(
            key=lambda x: x.get("days_until_expiry", 999),
        )

        return ToolResult.ok(
            certificates,
            count=len(certificates),
            cert_dir=str(CERT_DIR),
        )

    except Exception as e:
        logger.error("List certificates failed", error=str(e))
        return ToolResult.fail(f"List certificates failed: {e}")


@tool(
    name="check_certificate",
    description="Check SSL certificate status for a domain (local or remote)",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain name to check",
            },
            "check_remote": {
                "type": "boolean",
                "description": "Check the live certificate via HTTPS",
                "default": False,
            },
        },
        "required": ["domain"],
    },
)
async def check_certificate(
    domain: str,
    check_remote: bool = False,
) -> ToolResult:
    """Check certificate status for a domain."""
    try:
        result = {
            "domain": domain,
            "local": None,
            "remote": None,
        }

        # Check local certificate
        local_info = _get_cert_info(domain)
        if local_info:
            result["local"] = local_info

        # Check remote certificate if requested
        if check_remote:
            try:
                context = ssl.create_default_context()
                with socket.create_connection((domain, 443), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=domain) as ssock:
                        cert = ssock.getpeercert()

                        if cert:
                            # Parse certificate info
                            not_after = cert.get("notAfter", "")
                            not_before = cert.get("notBefore", "")

                            # Parse expiry
                            try:
                                expiry = datetime.strptime(
                                    not_after, "%b %d %H:%M:%S %Y %Z"
                                )
                                days_left = (expiry - datetime.now()).days
                            except ValueError:
                                expiry = None
                                days_left = None

                            # Get subject
                            subject = dict(x[0] for x in cert.get("subject", []))

                            result["remote"] = {
                                "valid": True,
                                "issuer": dict(x[0] for x in cert.get("issuer", [])),
                                "subject": subject,
                                "not_before": not_before,
                                "not_after": not_after,
                                "expires": expiry.isoformat() if expiry else None,
                                "days_until_expiry": days_left,
                                "san": [
                                    x[1]
                                    for x in cert.get("subjectAltName", [])
                                    if x[0] == "DNS"
                                ],
                            }

            except ssl.SSLError as e:
                result["remote"] = {
                    "valid": False,
                    "error": f"SSL error: {e}",
                }
            except socket.error as e:
                result["remote"] = {
                    "valid": False,
                    "error": f"Connection error: {e}",
                }

        # Determine overall status
        if result["local"]:
            days_left = result["local"].get("days_until_expiry", 0)
            if days_left < 0:
                result["status"] = "expired"
            elif days_left < 7:
                result["status"] = "critical"
            elif days_left < 30:
                result["status"] = "warning"
            else:
                result["status"] = "ok"
        else:
            result["status"] = "not_found"

        return ToolResult.ok(result)

    except Exception as e:
        logger.error("Check certificate failed", domain=domain, error=str(e))
        return ToolResult.fail(f"Check certificate failed: {e}")


@tool(
    name="request_certificate",
    description="Request a new SSL certificate from Let's Encrypt",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Primary domain name",
            },
            "additional_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional domain names (SANs)",
            },
            "email": {
                "type": "string",
                "description": "Email for certificate notifications",
            },
            "webroot": {
                "type": "string",
                "description": "Webroot path for HTTP challenge",
            },
            "dry_run": {
                "type": "boolean",
                "description": "Test without actually obtaining certificate",
                "default": False,
            },
        },
        "required": ["domain", "email"],
    },
    permission_level=2,
)
async def request_certificate(
    domain: str,
    email: str,
    additional_domains: list[str] | None = None,
    webroot: str | None = None,
    dry_run: bool = False,
) -> ToolResult:
    """Request a new certificate from Let's Encrypt."""
    try:
        args = [
            "certonly",
            "--non-interactive",
            "--agree-tos",
            "--email",
            email,
            "-d",
            domain,
        ]

        # Add additional domains
        if additional_domains:
            for d in additional_domains:
                args.extend(["-d", d])

        # Use webroot or standalone
        if webroot:
            args.extend(["--webroot", "-w", webroot])
        else:
            args.append("--standalone")

        if dry_run:
            args.append("--dry-run")

        code, stdout, stderr = await _run_certbot_command(args)

        output = stdout if stdout else stderr

        if code != 0:
            return ToolResult.fail(f"Certificate request failed: {output}")

        return ToolResult.ok({
            "message": "Certificate requested successfully" if not dry_run else "Dry run successful",
            "domain": domain,
            "additional_domains": additional_domains,
            "dry_run": dry_run,
            "output": output,
        })

    except Exception as e:
        logger.error("Request certificate failed", domain=domain, error=str(e))
        return ToolResult.fail(f"Request certificate failed: {e}")


@tool(
    name="renew_certificate",
    description="Renew SSL certificates (all or specific domain)",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Specific domain to renew (all if not specified)",
            },
            "force": {
                "type": "boolean",
                "description": "Force renewal even if not due",
                "default": False,
            },
            "dry_run": {
                "type": "boolean",
                "description": "Test renewal without actually renewing",
                "default": False,
            },
        },
    },
    permission_level=2,
)
async def renew_certificate(
    domain: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> ToolResult:
    """Renew certificates."""
    try:
        args = ["renew", "--non-interactive"]

        if domain:
            args.extend(["--cert-name", domain])

        if force:
            args.append("--force-renewal")

        if dry_run:
            args.append("--dry-run")

        code, stdout, stderr = await _run_certbot_command(args)

        output = stdout if stdout else stderr

        if code != 0:
            return ToolResult.fail(f"Certificate renewal failed: {output}")

        # Parse renewal results
        renewed = []
        not_due = []
        failed = []

        for line in output.splitlines():
            line_lower = line.lower()
            if "renewed" in line_lower or "successfully" in line_lower:
                renewed.append(line.strip())
            elif "not yet due" in line_lower or "not due" in line_lower:
                not_due.append(line.strip())
            elif "failed" in line_lower or "error" in line_lower:
                failed.append(line.strip())

        result = {
            "renewed": renewed,
            "not_due": not_due,
            "failed": failed,
            "dry_run": dry_run,
            "output": output[:1000],  # Truncate long output
        }

        if failed and not dry_run:
            result["message"] = "Some renewals failed"
            return ToolResult.ok(result)

        result["message"] = "Renewal completed" if not dry_run else "Dry run completed"
        return ToolResult.ok(result)

    except Exception as e:
        logger.error("Renew certificate failed", domain=domain, error=str(e))
        return ToolResult.fail(f"Renew certificate failed: {e}")
