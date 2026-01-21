#!/bin/bash
# Wyld Fyre AI - Start Agents Script
# Starts all AI agents in a tmux session

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SESSION_NAME="wyldfyre-ai"
LOG_DIR="/home/wyld-data/logs/agents"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed. Please install tmux first."
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    log_warn "Session '$SESSION_NAME' already exists"
    read -p "Kill existing session and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux kill-session -t "$SESSION_NAME"
        log_info "Killed existing session"
    else
        log_info "Attaching to existing session..."
        exec tmux attach -t "$SESSION_NAME"
    fi
fi

log_info "Starting Wyld Fyre AI agents..."

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Load environment from .env and export all variables
# The Docker containers use internal hostnames, but agents on host need localhost
set -a  # Auto-export all variables
source "$PROJECT_ROOT/.env"
set +a

# Override service settings for host-based agent access
# Agents run on the host and connect via localhost, not Docker network
export REDIS_HOST=localhost
export REDIS_PORT=6379
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export QDRANT_PREFER_GRPC=false
export QDRANT_HTTPS=false
log_info "Agents connecting to Redis at localhost:6379"
log_info "Agents connecting to Qdrant at localhost:6333 (HTTP mode, no TLS)"
log_info "Using Anthropic API key: ${ANTHROPIC_API_KEY:0:20}..."

# Create new tmux session with Wyld (Supervisor) agent
cd "$PROJECT_ROOT"
tmux new-session -d -s "$SESSION_NAME" -n "wyld"

# Common environment setup command for all agents
ENV_SETUP="set -a && source .env && set +a && source .venv/bin/activate && export REDIS_HOST=localhost REDIS_PORT=6379 QDRANT_HOST=localhost QDRANT_PORT=6333 QDRANT_PREFER_GRPC=false QDRANT_HTTPS=false"

# Wyld (Supervisor) - Window 0
tmux send-keys -t "$SESSION_NAME:wyld" "cd $PROJECT_ROOT && $ENV_SETUP" C-m
tmux send-keys -t "$SESSION_NAME:wyld" "echo 'Starting Wyld (Supervisor Agent)...'" C-m
tmux send-keys -t "$SESSION_NAME:wyld" "python -m services.supervisor.src.supervisor.agent 2>&1 | tee $LOG_DIR/wyld.log" C-m

# Code Agent - Window 1
tmux new-window -t "$SESSION_NAME" -n "code"
tmux send-keys -t "$SESSION_NAME:code" "cd $PROJECT_ROOT && $ENV_SETUP" C-m
tmux send-keys -t "$SESSION_NAME:code" "echo 'Starting Code Agent...'" C-m
tmux send-keys -t "$SESSION_NAME:code" "python -m agents.code.src.code_agent.agent 2>&1 | tee $LOG_DIR/code_agent.log" C-m

# Data Agent - Window 2
tmux new-window -t "$SESSION_NAME" -n "data"
tmux send-keys -t "$SESSION_NAME:data" "cd $PROJECT_ROOT && $ENV_SETUP" C-m
tmux send-keys -t "$SESSION_NAME:data" "echo 'Starting Data Agent...'" C-m
tmux send-keys -t "$SESSION_NAME:data" "python -m agents.data.src.data_agent.agent 2>&1 | tee $LOG_DIR/data_agent.log" C-m

# Infrastructure Agent - Window 3
tmux new-window -t "$SESSION_NAME" -n "infra"
tmux send-keys -t "$SESSION_NAME:infra" "cd $PROJECT_ROOT && $ENV_SETUP" C-m
tmux send-keys -t "$SESSION_NAME:infra" "echo 'Starting Infrastructure Agent...'" C-m
tmux send-keys -t "$SESSION_NAME:infra" "python -m agents.infra.src.infra_agent.agent 2>&1 | tee $LOG_DIR/infra_agent.log" C-m

# Research Agent - Window 4
tmux new-window -t "$SESSION_NAME" -n "research"
tmux send-keys -t "$SESSION_NAME:research" "cd $PROJECT_ROOT && $ENV_SETUP" C-m
tmux send-keys -t "$SESSION_NAME:research" "echo 'Starting Research Agent...'" C-m
tmux send-keys -t "$SESSION_NAME:research" "python -m agents.research.src.research_agent.agent 2>&1 | tee $LOG_DIR/research_agent.log" C-m

# QA Agent - Window 5
tmux new-window -t "$SESSION_NAME" -n "qa"
tmux send-keys -t "$SESSION_NAME:qa" "cd $PROJECT_ROOT && $ENV_SETUP" C-m
tmux send-keys -t "$SESSION_NAME:qa" "echo 'Starting QA Agent...'" C-m
tmux send-keys -t "$SESSION_NAME:qa" "python -m agents.qa.src.qa_agent.agent 2>&1 | tee $LOG_DIR/qa_agent.log" C-m

# Logs window - Window 6
tmux new-window -t "$SESSION_NAME" -n "logs"
tmux send-keys -t "$SESSION_NAME:logs" "cd $LOG_DIR && tail -f *.log 2>/dev/null || echo 'Waiting for logs...'" C-m

# Select the Wyld (Supervisor) window
tmux select-window -t "$SESSION_NAME:wyld"

log_success "Agents started in tmux session '$SESSION_NAME'"
echo ""
echo -e "${CYAN}Windows:${NC}"
echo "  0: wyld     - Wyld (Supervisor Agent)"
echo "  1: code     - Code Agent"
echo "  2: data     - Data Agent"
echo "  3: infra    - Infrastructure Agent"
echo "  4: research - Research Agent"
echo "  5: qa       - QA Agent"
echo "  6: logs     - Combined logs"
echo ""
echo -e "${CYAN}Commands:${NC}"
echo "  tmux attach -t $SESSION_NAME    # Attach to session"
echo "  tmux kill-session -t $SESSION_NAME  # Stop all agents"
echo "  Ctrl+b, n                       # Next window"
echo "  Ctrl+b, p                       # Previous window"
echo "  Ctrl+b, d                       # Detach from session"
echo ""
