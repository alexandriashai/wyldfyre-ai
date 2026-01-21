# Troubleshooting Guide

Common issues and their solutions.

## Agents Not Starting

### Symptoms
- No heartbeat in Redis
- Tmux session empty or erroring

### Solutions

```bash
# Check tmux session
tmux attach -t wyldfyre-ai

# Check logs
tail -f /home/wyld-data/logs/agents/*.log

# Restart agents
make agents-stop
make agents-start
```

### Common Causes
- Missing API keys in .env
- Redis not accessible
- Python dependencies not installed

## API Connection Refused

### Symptoms
- 502 Bad Gateway from nginx
- Connection refused on port 8000

### Solutions

```bash
# Check API container
docker-compose ps ai-api
docker-compose logs ai-api

# Restart API
docker-compose restart ai-api
```

## Redis Connection Failed

### Symptoms
- "Connection refused" errors
- Agents can't communicate

### Solutions

```bash
# Check Redis
docker-compose ps ai-redis
docker-compose logs ai-redis

# Test connection
redis-cli -a "$REDIS_PASSWORD" ping
```

## Database Connection Failed

### Symptoms
- API fails to start
- Migration errors

### Solutions

```bash
# Check PostgreSQL
docker-compose ps ai-db
docker-compose logs ai-db

# Test connection
docker-compose exec ai-db psql -U ai_infra -c "SELECT 1"
```

## Memory Issues

### Symptoms
- OOM killer terminating processes
- Services crashing

### Solutions

```bash
# Check memory usage
free -h
docker stats

# Reduce agent count in config/agents.yaml
# Add swap if needed
sudo fallocate -l 8G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## SSL Certificate Issues

### Symptoms
- Browser security warnings
- Certificate expired

### Solutions

```bash
# Check certificate status
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Renew certificate
certbot renew

# Reload nginx
systemctl reload nginx
```

## Permission Denied Errors

### Symptoms
- Can't read/write files
- Script execution fails

### Solutions

```bash
# Check ownership
ls -la /home/wyld-core/

# Fix permissions
sudo chown -R wyld-core:wyld /home/wyld-core/
chmod 750 /home/wyld-core/
chmod 600 /home/wyld-core/.env
```

## Log Analysis

### Structured Log Query

Logs are JSON formatted. Use jq for querying:

```bash
# Find errors
cat /home/wyld-data/logs/api/app.log | jq 'select(.level == "error")'

# Find by agent
cat /home/wyld-data/logs/agents/*.log | jq 'select(.agent == "code")'
```

### Grafana Loki

Query logs in Grafana:
```logql
{job="agents"} | json | level="error"
```

## Getting Help

1. Check this guide
2. Search existing GitHub issues
3. Open new issue with:
   - Error messages
   - Relevant logs
   - Steps to reproduce
