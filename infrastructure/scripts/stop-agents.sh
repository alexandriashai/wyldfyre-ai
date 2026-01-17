#!/bin/bash
# Stop all AI Infrastructure agents

set -e

SESSION_NAME="ai-infrastructure"

# Check if session exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Stopping agents..."

    # Send SIGINT to all windows
    for window in $(tmux list-windows -t "$SESSION_NAME" -F '#W'); do
        echo "Stopping $window..."
        tmux send-keys -t "$SESSION_NAME:$window" C-c
        sleep 1
    done

    # Wait a moment for graceful shutdown
    sleep 3

    # Kill the session
    tmux kill-session -t "$SESSION_NAME"
    echo "All agents stopped"
else
    echo "No running session found"
fi
