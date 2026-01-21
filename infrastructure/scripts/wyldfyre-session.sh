#!/bin/bash
# Wyld Fyre AI - Session chooser on SSH login

SESSION_ADMIN="wyldfyre-adm"
SESSION_AGENTS="wyldfyre-ai"
PROJECT_DIR="/root/AI-Infrastructure"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Skip for non-interactive shells
if [ ! -t 0 ]; then
  exit 0
fi

# Skip if SKIP_WYLDFYRE_SESSION is set
if [ -n "${SKIP_WYLDFYRE_SESSION:-}" ]; then
  exit 0
fi

# Avoid nesting if already in tmux
if [ -n "${TMUX:-}" ]; then
  exit 0
fi

echo
echo -e "${PURPLE}=============================================="
echo -e "  🔥 Wyld Fyre AI Infrastructure"
echo -e "==============================================${NC}"
echo

# Check which sessions exist
admin_exists=false
agents_exists=false

if tmux has-session -t "$SESSION_ADMIN" 2>/dev/null; then
  admin_exists=true
fi

if tmux has-session -t "$SESSION_AGENTS" 2>/dev/null; then
  agents_exists=true
fi

# Display session options
echo -e "${CYAN}Available sessions:${NC}"
echo

session_count=0
if $admin_exists; then
  admin_windows=$(tmux list-windows -t "$SESSION_ADMIN" 2>/dev/null | wc -l)
  echo -e "  ${GREEN}1)${NC} ${SESSION_ADMIN}  - Admin/Development (${admin_windows} windows)"
  ((session_count++))
fi

if $agents_exists; then
  agents_windows=$(tmux list-windows -t "$SESSION_AGENTS" 2>/dev/null | wc -l)
  agents_status="running"
  # Check if agents are actually running by looking for python processes
  if pgrep -f "python.*agent" > /dev/null 2>&1; then
    agents_status="${GREEN}active${NC}"
  else
    agents_status="${YELLOW}stopped${NC}"
  fi
  echo -e "  ${GREEN}2)${NC} ${SESSION_AGENTS}   - AI Agents ($agents_status, ${agents_windows} windows)"
  ((session_count++))
fi

echo -e "  ${GREEN}3)${NC} New shell       - Start a new shell (no tmux)"
echo
echo -e "  ${YELLOW}4)${NC} Start agents    - Start AI agents if not running"
echo

# Small delay to ensure terminal is ready for input
sleep 0.5

# Loop until valid choice is made
while true; do
  # Get user choice with timeout
  read -t 60 -p "Choose an option [1-4]: " choice
  read_status=$?

  # Handle timeout (read returns > 128 on timeout)
  if [ $read_status -gt 128 ]; then
    echo -e "\n${YELLOW}Timeout - starting new shell${NC}"
    exit 0
  fi

  # Handle empty input
  if [ -z "$choice" ]; then
    echo -e "${YELLOW}Please enter a number (1-4)${NC}"
    continue
  fi

  # Validate input is 1-4
  case "$choice" in
    1|2|3|4) break ;;
    *) echo -e "${YELLOW}Invalid choice. Please enter 1, 2, 3, or 4${NC}" ;;
  esac
done

case "$choice" in
  1)
    if $admin_exists; then
      echo -e "\n${CYAN}Attaching to ${SESSION_ADMIN}...${NC}"
      exec tmux attach-session -t "$SESSION_ADMIN"
    else
      echo -e "\n${YELLOW}Creating new admin session...${NC}"
      cd "$PROJECT_DIR" || exit 1
      tmux new-session -d -s "$SESSION_ADMIN" -n "main" -c "$PROJECT_DIR"
      tmux send-keys -t "$SESSION_ADMIN:main" "cd $PROJECT_DIR && docker compose ps" C-m
      tmux new-window -t "$SESSION_ADMIN" -n "logs" -c "$PROJECT_DIR"
      tmux send-keys -t "$SESSION_ADMIN:logs" "docker compose logs -f --tail=100" C-m
      tmux new-window -t "$SESSION_ADMIN" -n "api" -c "$PROJECT_DIR"
      tmux send-keys -t "$SESSION_ADMIN:api" "docker compose logs -f api --tail=50" C-m
      tmux new-window -t "$SESSION_ADMIN" -n "web" -c "$PROJECT_DIR"
      tmux send-keys -t "$SESSION_ADMIN:web" "docker compose logs -f web --tail=50" C-m
      tmux new-window -t "$SESSION_ADMIN" -n "claude" -c "$PROJECT_DIR"
      tmux select-window -t "$SESSION_ADMIN:main"
      exec tmux attach-session -t "$SESSION_ADMIN"
    fi
    ;;
  2)
    if $agents_exists; then
      echo -e "\n${CYAN}Attaching to ${SESSION_AGENTS}...${NC}"
      exec tmux attach-session -t "$SESSION_AGENTS"
    else
      echo -e "\n${YELLOW}Agent session not found. Starting agents...${NC}"
      bash "$PROJECT_DIR/infrastructure/scripts/start-agents.sh"
      exec tmux attach-session -t "$SESSION_AGENTS"
    fi
    ;;
  3)
    echo -e "\n${CYAN}Starting new shell...${NC}"
    exit 0
    ;;
  4)
    echo -e "\n${CYAN}Starting AI agents...${NC}"
    if $agents_exists; then
      echo -e "${YELLOW}Killing existing agent session first...${NC}"
      tmux kill-session -t "$SESSION_AGENTS" 2>/dev/null || true
    fi
    bash "$PROJECT_DIR/infrastructure/scripts/start-agents.sh"
    exec tmux attach-session -t "$SESSION_AGENTS"
    ;;
esac
