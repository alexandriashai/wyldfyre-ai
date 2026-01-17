#!/bin/bash
# Start all AI Infrastructure agents in tmux

set -e

SESSION_NAME="ai-infrastructure"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed"
    exit 1
fi

# Kill existing session if it exists
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Create new session
tmux new-session -d -s "$SESSION_NAME" -n "supervisor"

# Configure environment for all windows
tmux send-keys -t "$SESSION_NAME:supervisor" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:supervisor" "source .venv/bin/activate 2>/dev/null || true" C-m
tmux send-keys -t "$SESSION_NAME:supervisor" "python -m services.supervisor" C-m

# Create windows for each agent
agents=("code-agent" "data-agent" "infra-agent" "research-agent" "qa-agent")

for agent in "${agents[@]}"; do
    tmux new-window -t "$SESSION_NAME" -n "$agent"
    tmux send-keys -t "$SESSION_NAME:$agent" "cd $PROJECT_ROOT" C-m
    tmux send-keys -t "$SESSION_NAME:$agent" "source .venv/bin/activate 2>/dev/null || true" C-m

    # Convert agent name to module path
    module_name=$(echo "$agent" | tr '-' '_')
    tmux send-keys -t "$SESSION_NAME:$agent" "python -m services.agents.$module_name" C-m
done

# Create monitoring window
tmux new-window -t "$SESSION_NAME" -n "monitor"
tmux send-keys -t "$SESSION_NAME:monitor" "cd $PROJECT_ROOT" C-m
tmux send-keys -t "$SESSION_NAME:monitor" "watch -n 5 'docker-compose ps'" C-m

# Select supervisor window
tmux select-window -t "$SESSION_NAME:supervisor"

echo "AI Infrastructure agents started in tmux session: $SESSION_NAME"
echo "Run 'tmux attach -t $SESSION_NAME' to view"
