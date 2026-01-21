#!/bin/bash
# Wyld Fyre AI - Stop Agents Script
# Stops all AI agents by killing the tmux session

SESSION_NAME="wyldfyre-ai"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if session exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Stopping Wyld Fyre AI agents..."

    # Send SIGINT to all windows for graceful shutdown
    for window in $(tmux list-windows -t "$SESSION_NAME" -F '#W'); do
        echo "  Stopping $window..."
        tmux send-keys -t "$SESSION_NAME:$window" C-c 2>/dev/null || true
    done

    # Wait for graceful shutdown
    sleep 2

    # Kill the session
    tmux kill-session -t "$SESSION_NAME"
    log_success "All agents stopped"
else
    log_warn "No session '$SESSION_NAME' found - agents may not be running"
fi
