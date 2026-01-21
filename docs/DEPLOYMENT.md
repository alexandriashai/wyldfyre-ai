# Deployment Guide

This guide covers deploying Wyld Fyre AI to production.

## Server Requirements

- Ubuntu 22.04+ (recommended)
- 64GB RAM (minimum 16GB)
- 8 CPU cores
- 100GB+ NVMe storage
- Domain name with DNS access

## Production Deployment

### 1. Initial Setup

```bash
# Clone repository
cd /home/wyld-core
git pull origin main

# Configure environment
cp .env.example .env
# Edit .env with production values
chmod 600 .env
```

### 2. Build and Start

```bash
# Build Docker images
make build

# Start services
make prod

# Verify
make status
```

### 3. SSL Configuration

SSL is managed via Certbot and Let's Encrypt:

```bash
# Certificate provisioning is handled by infra-agent
# Or manually:
certbot certonly --webroot -w /var/www/certbot -d yourdomain.com
```

### 4. Domain Management

Add domains via `config/domains.yaml`:

```yaml
domains:
  web.wyldfyre.ai:
    service: web
    port: 3000
    ssl: true

  api.wyldfyre.ai:
    service: api
    port: 8000
    ssl: true
```

## Nginx Configuration

Nginx handles TLS termination and routing:

```bash
# Test configuration
nginx -t

# Reload
systemctl reload nginx
```

## Monitoring

### Grafana Dashboards

Access Grafana at http://localhost:3001

Pre-configured dashboards:
- Agent Overview
- API Performance
- System Resources
- Redis Metrics

### Alerts

Alerts are configured in `infrastructure/monitoring/prometheus/alerts.yml`

## Backup Procedures

### Git Backup

```bash
make backup
```

### Database Backup

```bash
# Manual backup
docker-compose exec ai-db pg_dump -U ai_infra ai_infrastructure > backup.sql

# Automated backups run daily to /home/wyld-data/backups/daily/
```

## Rollback

```bash
# Stop services
make stop

# Checkout previous version
git checkout v1.0.0

# Rebuild and restart
make build
make prod
```

## Health Checks

```bash
# API health
curl https://api.wyldfyre.ai/health/live

# Service status
make status
```
