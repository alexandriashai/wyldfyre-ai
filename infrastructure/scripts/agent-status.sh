#!/bin/bash
# Wyld Fyre AI - Agent Status Script
# Shows the status of all AI agents

SESSION_NAME="wyldfyre-ai"
API_URL="${API_URL:-http://localhost:8000}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════╗"
echo "║           Wyld Fyre AI - Agent Status                  ║"
echo "╚════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check tmux session
echo -e "${BLUE}Tmux Session:${NC}"
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "  Status: ${GREEN}Running${NC}"
    echo "  Session: $SESSION_NAME"
    echo ""
    echo "  Windows:"
    tmux list-windows -t "$SESSION_NAME" -F "    #{window_index}: #{window_name} - #{pane_current_command}" 2>/dev/null
else
    echo -e "  Status: ${RED}Not Running${NC}"
    echo "  Run 'make agents-start' to start agents"
fi

echo ""

# Check API health
echo -e "${BLUE}API Health:${NC}"
if command -v curl &> /dev/null && curl -sf "$API_URL/health/live" > /dev/null 2>&1; then
    echo -e "  API: ${GREEN}Healthy${NC} ($API_URL)"

    # Try to get agent status from API
    response=$(curl -sf "$API_URL/api/agents" 2>/dev/null)
    if [ -n "$response" ] && [ "$response" != "[]" ]; then
        echo ""
        echo -e "${BLUE}Agent Status (from API):${NC}"
        echo "$response" | python3 -c "
import sys, json
try:
    agents = json.load(sys.stdin)
    for agent in agents:
        status = agent.get('status', 'unknown')
        name = agent.get('name', 'unknown')
        agent_type = agent.get('type', 'unknown')
        tasks = agent.get('tasks_completed', 0)

        if status in ('idle', 'busy'):
            color = '\\033[0;32m'
        elif status == 'offline':
            color = '\\033[0;31m'
        else:
            color = '\\033[1;33m'
        nc = '\\033[0m'

        print(f'  {name} ({agent_type}): {color}{status}{nc} - {tasks} tasks completed')
except Exception as e:
    pass
" 2>/dev/null || echo "  Unable to parse agent status"
    fi
else
    echo -e "  API: ${RED}Not Responding${NC}"
    echo "  Make sure the API server is running (make dev-api)"
fi

echo ""

# Check Docker services
echo -e "${BLUE}Docker Services:${NC}"
if command -v docker &> /dev/null; then
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        echo "  Docker Compose not available"
        exit 0
    fi

    services=$($COMPOSE_CMD ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null | tail -n +2)
    if [ -n "$services" ]; then
        echo "$services" | while read -r line; do
            name=$(echo "$line" | awk '{print $1}')
            status=$(echo "$line" | awk '{$1=""; print $0}' | xargs)

            if [[ "$status" == *"Up"* ]] || [[ "$status" == *"running"* ]]; then
                echo -e "  $name: ${GREEN}$status${NC}"
            elif [[ "$status" == *"Exit"* ]] || [[ "$status" == *"exited"* ]]; then
                echo -e "  $name: ${RED}$status${NC}"
            else
                echo -e "  $name: ${YELLOW}$status${NC}"
            fi
        done
    else
        echo "  No services running"
    fi
else
    echo "  Docker not installed"
fi

echo ""
echo "Use 'tmux attach -t $SESSION_NAME' to view agent windows"
echo ""
