#!/bin/bash
cd /home/wyld-core
set -a  # Export all variables
source .env
set +a

# Override hosts for local execution (outside Docker)
export REDIS_HOST=localhost
export QDRANT_HOST=localhost
export POSTGRES_HOST=localhost

# Set Python path
export PYTHONPATH=/home/wyld-core/services/supervisor/src:/home/wyld-core/packages/core/src:/home/wyld-core/packages/messaging/src:/home/wyld-core/packages/memory/src:/home/wyld-core/packages/agents/src

exec python3 -m supervisor
