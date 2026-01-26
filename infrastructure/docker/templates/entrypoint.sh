#!/bin/bash
# Entrypoint script for Wyld project containers
# Fixes file ownership and then runs as wyld user

# If running as root, fix ownership and re-exec as wyld
if [ "$(id -u)" = "0" ]; then
    # Fix ownership of /app (the project mount)
    chown -R wyld:wyld /app 2>/dev/null || true

    # Fix ownership of writable config directories
    chown -R wyld:wyld /home/wyld/.claude-local 2>/dev/null || true
    chown -R wyld:wyld /home/wyld/.npm 2>/dev/null || true
    chown -R wyld:wyld /home/wyld/.local 2>/dev/null || true

    # Re-exec this script as wyld user
    exec gosu wyld "$0" "$@"
fi

# Now running as wyld user
exec "$@"
