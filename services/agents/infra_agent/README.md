# Infrastructure Agent

The Infrastructure Agent is a specialized AI agent for comprehensive infrastructure management including Docker, Nginx, SSL certificates, and system operations within the Wyld Fyre AI Infrastructure.

## Capabilities

### System Operations
- **shell_execute** - Execute shell commands with safety checks
- **process_list** - List running processes
- **process_kill** - Terminate processes
- **service_manage** - Manage systemd services
- **resource_monitor** - Monitor CPU, memory, disk usage
- **system_info** - Get detailed system information

### Docker Operations
- **docker_list_containers** - List containers with status
- **docker_inspect_container** - Get container details
- **docker_logs** - View container logs
- **docker_stats** - Real-time resource stats
- **docker_exec** - Execute commands in containers
- **docker_pull_image** - Pull images from registry
- **docker_build_image** - Build images from Dockerfile
- **docker_compose_up/down/restart** - Manage compose services
- **docker_health_check** - Check container health
- **docker_prune** - Clean up unused resources

### Nginx Management
- **nginx_status** - Check Nginx service status
- **nginx_test_config** - Validate configuration syntax
- **nginx_reload** - Graceful configuration reload
- **nginx_create_vhost** - Create virtual host configurations
- **nginx_enable/disable_site** - Manage site activation
- **nginx_logs** - View access and error logs

### SSL/TLS Certificates
- **ssl_list_certificates** - List managed certificates
- **ssl_check_certificate** - Check expiry and validity
- **ssl_request_certificate** - Request via Let's Encrypt
- **ssl_renew_certificates** - Renew expiring certificates

### Domain Provisioning
- **domain_list** - List all configured domains
- **domain_status** - Get detailed domain status
- **domain_provision** - Full domain setup (web root, Nginx, SSL)
- **domain_remove** - Remove domain configurations
- **domain_verify** - Verify domain accessibility

### Cloudflare Integration
- **cf_list_zones** - List DNS zones
- **cf_list_dns_records** - List zone DNS records
- **cf_create/update/delete_dns_record** - Manage DNS records
- **cf_purge_cache** - Purge CDN cache
- **cf_set_ssl_mode** - Configure SSL mode
- **cf_get_analytics** - View analytics data

### Systemd Service Management
- **systemd_list_units** - List service units
- **systemd_status** - Get unit status
- **systemd_start/stop/restart/reload** - Control services
- **systemd_enable/disable** - Boot-time activation
- **systemd_logs** - View journalctl logs
- **systemd_create_unit** - Create service/timer units

## Configuration

### Environment Variables
```bash
REDIS_HOST=redis
POSTGRES_HOST=postgres
CLOUDFLARE_API_TOKEN=<token>     # For Cloudflare operations
CLOUDFLARE_ZONE_ID=<zone_id>
```

### Permission Level
The Infra Agent operates at **Permission Level 3** (ADMIN), allowing it to:
- Execute system commands
- Manage Docker containers and images
- Configure Nginx and SSL
- Provision domains
- Manage Cloudflare DNS

## Usage Examples

### Deploy Container
```json
{
  "tool": "docker_compose_up",
  "arguments": {
    "compose_file": "/home/wyld-core/docker-compose.yml",
    "services": ["api"],
    "detach": true,
    "build": true
  }
}
```

### Provision Domain
```json
{
  "tool": "domain_provision",
  "arguments": {
    "domain": "app.wyldfyre.ai",
    "create_webroot": true,
    "enable_ssl": true,
    "upstream": "http://localhost:3000"
  }
}
```

### Request SSL Certificate
```json
{
  "tool": "ssl_request_certificate",
  "arguments": {
    "domain": "api.wyldfyre.ai",
    "email": "admin@wyldfyre.ai"
  }
}
```

### Create DNS Record
```json
{
  "tool": "cf_create_dns_record",
  "arguments": {
    "zone_id": "abc123",
    "type": "A",
    "name": "api",
    "content": "192.168.1.100",
    "proxied": true
  }
}
```

## Architecture

```
services/agents/infra_agent/
├── src/
│   └── infra_agent/
│       ├── __init__.py
│       ├── agent.py              # Main agent class
│       └── tools/
│           ├── __init__.py
│           ├── system_tools.py      # System operations
│           ├── docker_tools.py      # Docker management
│           ├── nginx_tools.py       # Nginx configuration
│           ├── ssl_tools.py         # Certificate management
│           ├── domain_tools.py      # Domain provisioning
│           ├── cloudflare_tools.py  # Cloudflare integration
│           └── systemd_tools.py     # Service management
├── pyproject.toml
└── README.md
```

## Security

- Docker operations limited to allowed prefixes (ai-*, ai_*, aiinfra)
- Dangerous commands require explicit confirmation
- Environment variables are never exposed in logs
- SSL certificates auto-renewed before expiry
- All infrastructure changes are logged

## Dependencies
- ai-core, ai-messaging, ai-memory, base-agent
- docker - Docker SDK
- httpx - HTTP client for Cloudflare API

## Running

### With Docker Compose
```bash
docker compose up -d infra-agent
```

### Standalone
```bash
python -m services.agents.infra_agent.src.infra_agent.agent
```

## Volumes
- `/var/run/docker.sock` - Docker socket (read-only)
- `/etc/nginx` - Nginx configuration
- `/etc/letsencrypt` - SSL certificates

## Logs
Logs are written to `/home/wyld-data/logs/agents/infra-agent.log`
