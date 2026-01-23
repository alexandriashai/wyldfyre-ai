#!/bin/bash
# Startup script for Supervisor agent
# Sources .env and starts the supervisor with proper PYTHONPATH

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Export all variables from .env (handling KEY=VALUE format)
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading environment from $PROJECT_ROOT/.env"
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        # Remove any surrounding quotes from value
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        # Export the variable
        export "$key=$value"
    done < "$PROJECT_ROOT/.env"
fi

# Override hosts to use localhost (supervisor runs on host, not in Docker)
export REDIS_HOST=localhost
export POSTGRES_HOST=localhost
export QDRANT_HOST=localhost

# Set PYTHONPATH for all internal packages
export PYTHONPATH="$SCRIPT_DIR/src:$PROJECT_ROOT/packages/core/src:$PROJECT_ROOT/packages/agents/src:$PROJECT_ROOT/packages/memory/src:$PROJECT_ROOT/packages/messaging/src:$PROJECT_ROOT/packages/db/src:$PROJECT_ROOT"

echo "Starting Supervisor agent..."
echo "  REDIS_HOST=$REDIS_HOST"
echo "  POSTGRES_HOST=$POSTGRES_HOST"
echo "  POSTGRES_USER=$POSTGRES_USER"
echo "  QDRANT_HOST=$QDRANT_HOST"
echo "  ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:0:20}..."

exec python3 -m supervisor "$@"
