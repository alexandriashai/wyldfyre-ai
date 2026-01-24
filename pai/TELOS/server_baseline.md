# Server Baseline

This server is a single VPS running all services. Projects are built IN PLACE within their directory - there is NO need to set up new servers, install infrastructure, or configure deployment pipelines from scratch.

## Deployment Pattern

Each project has its own configuration with:
- **root_path**: The filesystem directory where project files live (build here)
- **primary_url**: The URL where the project is served
- **domain**: The domain name associated with the project

When asked to "build a website" or "create a project", the agent should:
1. Use the project's configured `root_path` as the working directory — build files there
2. Use the project's configured domain/primary_url for any nginx or DNS references
3. NOT suggest setting up cloud infrastructure, CI/CD pipelines, Docker registries, or provisioning servers
4. NOT create Docker containers for simple websites — just write the files directly in the project root
5. Nginx and SSL are already handled — focus only on the application files
6. File permissions are automatically set (644, www-data:www-data) for web-served directories

## File Permissions

Web-served files (under `/home/wyld-web/` or `/var/www/`) are automatically set to:
- Ownership: `www-data:www-data`
- Permissions: `644` (owner read/write, group/others read)
- Parent directories: created automatically with appropriate permissions

The agent does NOT need to manually set permissions — the write_file tool handles this.

## Installed Software

### Web Server
- Nginx 1.28.0 (with brotli, geoip, image-filter, stream modules)
- Certbot 2.9.0 (with nginx + cloudflare-dns plugins)
- SSL auto-renewal configured

### Languages & Runtimes
- Python 3.12.3 (pip, uv package manager)
- Node.js 22.19.0 (npm 10.9.3, npx)
- PHP 7.1 through 8.5 (all versions available, switchable)
- Git 2.43.0

### Containers
- Docker 29.1.5
- Docker Compose v5.0.1

### Databases & Storage (via Docker Compose in /home/wyld-core)
- PostgreSQL 16 (port 5432)
- Redis 7 (port 6379)
- Qdrant vector DB (port 6333)
- Meilisearch (port 7700)

### Monitoring (via Docker Compose)
- Grafana (port 3001)
- Prometheus (port 9090)
- Loki (log aggregation)

### AI Platform Services (Docker Compose)
- API service (FastAPI, port 8010 -> 8000)
- Web dashboard (Next.js, port 3010 -> 3000)
- Voice service (port 8001)
- Supervisor agent

### Build Tools
- build-essential (gcc, make, etc.)
- curl, wget

### Mail Server
- Full mail stack on port 25/465/587 (SMTP), 143 (IMAP), 110 (POP3)

## Active Domains & Sites
- wyldfyre.ai (main site)
- api.wyldfyre.ai (API proxy -> port 8010)
- web.wyldfyre.ai (web dashboard proxy -> port 3010)
- grafana.wyldfyre.ai (monitoring proxy -> port 3001)
- blackbook.reviews (PHP site)
- dev.blackbook.reviews (dev PHP site)
- bbr.link (short links)
- d.erl.ink (short links)
- wyldfyre.me (personal)
- escort.reviews (mail + web)

## Directory Structure
- `/home/wyld-core/` - AI platform codebase (monorepo)
- Each project's `root_path` - where that project's files live (set in project config)
- `/etc/nginx/sites-enabled/` - Nginx virtual host configs
- `/etc/letsencrypt/` - SSL certificates (managed by certbot)

## Key Constraints
- Single server - all resources are shared
- No cloud services (no AWS, GCP, etc.) - everything runs locally
- No CI/CD pipeline - deployments are direct file operations + service restarts
- No load balancer - nginx handles everything
- Docker is used for databases and platform services, NOT typically for simple websites
