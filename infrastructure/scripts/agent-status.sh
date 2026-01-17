#!/bin/bash
# Check status of AI Infrastructure agents

SESSION_NAME="ai-infrastructure"

echo "=== AI Infrastructure Agent Status ==="
echo ""

# Check if session exists
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Status: NOT RUNNING"
    echo "No tmux session found"
    exit 1
fi

echo "Status: RUNNING"
echo "Session: $SESSION_NAME"
echo ""

# List all windows with their status
echo "Agents:"
echo "-------"
tmux list-windows -t "$SESSION_NAME" -F "  #{window_name}: #{window_active} (pane: #{pane_current_command})"

echo ""
echo "Use 'tmux attach -t $SESSION_NAME' to view agents"
echo "Use 'tmux select-window -t $SESSION_NAME:<agent-name>' to switch to specific agent"
