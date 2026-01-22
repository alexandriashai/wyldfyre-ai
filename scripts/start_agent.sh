#!/bin/bash
# Agent startup script
# Usage: ./start_agent.sh <agent_name>

AGENT_NAME=$1

if [ -z "$AGENT_NAME" ]; then
    echo "Usage: $0 <agent_name>"
    echo "Available agents: wyld, code-agent, data-agent, infra-agent, research-agent, qa-agent"
    exit 1
fi

# Base directory
BASE_DIR="/home/wyld-core"

# Set up PYTHONPATH for all packages
export PYTHONPATH="${BASE_DIR}/packages/core/src:${BASE_DIR}/packages/memory/src:${BASE_DIR}/packages/messaging/src:${BASE_DIR}/packages/agents/src:${BASE_DIR}/services/agents/code_agent/src:${BASE_DIR}/services/agents/data_agent/src:${BASE_DIR}/services/agents/infra_agent/src:${BASE_DIR}/services/agents/research_agent/src:${BASE_DIR}/services/agents/qa_agent/src:${BASE_DIR}/services/supervisor/src"

# Environment configuration for local run (use localhost instead of Docker hostnames)
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_PASSWORD="UOrd6ciOkzRPMERthqWAci5pnW0rnrPM"
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export QDRANT_API_KEY="EAp2zFPe2DFAWghiWxZZXXB2TkiY5Rm5"
export DATABASE_URL="postgresql://wyld:xSBaVQKSwUbWjLxaTdmZ69h4bkuNRY4n@localhost:5432/ai_infrastructure"

# Load .env for any additional settings
if [ -f "${BASE_DIR}/.env" ]; then
    export $(grep -v '^#' "${BASE_DIR}/.env" | grep -v '^REDIS_HOST' | grep -v '^QDRANT_HOST' | xargs)
fi

# Activate virtual environment
source "${BASE_DIR}/.venv/bin/activate"

# Map agent name to module
case "$AGENT_NAME" in
    wyld|supervisor)
        MODULE="supervisor"
        ;;
    code-agent|code)
        MODULE="code_agent"
        ;;
    data-agent|data)
        MODULE="data_agent"
        ;;
    infra-agent|infra)
        MODULE="infra_agent"
        ;;
    research-agent|research)
        MODULE="research_agent"
        ;;
    qa-agent|qa)
        MODULE="qa_agent"
        ;;
    *)
        echo "Unknown agent: $AGENT_NAME"
        exit 1
        ;;
esac

echo "Starting ${AGENT_NAME} (module: ${MODULE})..."
cd "${BASE_DIR}"
python -m "$MODULE"
