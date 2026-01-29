#!/bin/bash
# Docker cleanup script - run daily via cron

# Prune build cache older than 7 days
docker builder prune -f --filter "until=168h"

# Prune unused images older than 7 days
docker image prune -f --filter "until=168h"

# Prune stopped containers older than 24 hours
docker container prune -f --filter "until=24h"

# Prune unused volumes (careful - only if not attached)
# docker volume prune -f

# Log the cleanup
echo "$(date): Docker cleanup completed" >> /var/log/docker-cleanup.log
df -h / >> /var/log/docker-cleanup.log
