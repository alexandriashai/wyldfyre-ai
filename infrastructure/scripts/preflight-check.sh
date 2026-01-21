#!/bin/bash
# Wyld Fyre AI - Pre-flight Check Script
# Assesses server state before installation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Results storage
WARNINGS=()
ERRORS=()
INFO=()
EXISTING_SERVICES=()
CONFLICTS=()

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Wyld Fyre AI - Pre-flight Check                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ==============================================================================
# System Requirements
# ==============================================================================
echo -e "${YELLOW}[1/8] Checking System Requirements...${NC}"

# Check OS
OS=$(uname -s)
if [ "$OS" != "Linux" ]; then
    WARNINGS+=("Non-Linux OS detected: $OS. Installation tested on Linux only.")
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    INFO+=("Running as root user")
else
    INFO+=("Running as user: $(whoami)")
fi

# Check available memory
TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -lt 16 ]; then
    WARNINGS+=("Low memory: ${TOTAL_MEM}GB detected. Recommended: 16GB minimum, 64GB for full deployment")
elif [ "$TOTAL_MEM" -lt 64 ]; then
    INFO+=("Memory: ${TOTAL_MEM}GB (sufficient for basic deployment)")
else
    INFO+=("Memory: ${TOTAL_MEM}GB (optimal)")
fi

# Check available disk space
AVAILABLE_DISK=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$AVAILABLE_DISK" -lt 50 ]; then
    WARNINGS+=("Low disk space: ${AVAILABLE_DISK}GB available. Recommended: 100GB+")
else
    INFO+=("Disk space: ${AVAILABLE_DISK}GB available")
fi

# Check CPU cores
CPU_CORES=$(nproc)
if [ "$CPU_CORES" -lt 4 ]; then
    WARNINGS+=("Low CPU cores: ${CPU_CORES}. Recommended: 8+ cores")
else
    INFO+=("CPU cores: ${CPU_CORES}")
fi

echo -e "  ${GREEN}✓${NC} System requirements checked"

# ==============================================================================
# Docker Check
# ==============================================================================
echo -e "${YELLOW}[2/8] Checking Docker...${NC}"

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
    INFO+=("Docker installed: v${DOCKER_VERSION}")

    if docker info &> /dev/null; then
        INFO+=("Docker daemon running")

        # Check existing containers
        RUNNING_CONTAINERS=$(docker ps --format '{{.Names}}' | wc -l)
        if [ "$RUNNING_CONTAINERS" -gt 0 ]; then
            INFO+=("Running containers: ${RUNNING_CONTAINERS}")
            docker ps --format '  - {{.Names}} ({{.Image}})'
        fi

        # Check for wyld-fyre related containers
        WYLD_CONTAINERS=$(docker ps -a --format '{{.Names}}' | grep -i 'wyld\|fyre\|ai-infra' || true)
        if [ -n "$WYLD_CONTAINERS" ]; then
            EXISTING_SERVICES+=("Previous Wyld Fyre containers found")
            echo -e "  ${YELLOW}!${NC} Existing Wyld Fyre containers:"
            echo "$WYLD_CONTAINERS" | while read name; do echo "    - $name"; done
        fi
    else
        WARNINGS+=("Docker daemon not running")
    fi
else
    INFO+=("Docker not installed (will be installed)")
fi

if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    INFO+=("Docker Compose available")
else
    INFO+=("Docker Compose not installed (will be installed)")
fi

echo -e "  ${GREEN}✓${NC} Docker check complete"

# ==============================================================================
# Port Availability
# ==============================================================================
echo -e "${YELLOW}[3/8] Checking Port Availability...${NC}"

# Define required ports
declare -A PORTS=(
    [3000]="Web Portal (Next.js)"
    [3001]="Grafana"
    [3100]="Loki"
    [5432]="PostgreSQL"
    [6333]="Qdrant"
    [6379]="Redis"
    [8000]="FastAPI"
    [8001]="Voice Service"
    [9090]="Prometheus"
)

for PORT in "${!PORTS[@]}"; do
    SERVICE="${PORTS[$PORT]}"
    if ss -tuln | grep -q ":${PORT} "; then
        PROCESS=$(ss -tulnp | grep ":${PORT} " | awk '{print $7}' | cut -d'"' -f2 | head -1)
        CONFLICTS+=("Port ${PORT} (${SERVICE}) in use by: ${PROCESS:-unknown}")
        EXISTING_SERVICES+=("Port ${PORT} occupied")
    else
        echo -e "  ${GREEN}✓${NC} Port ${PORT} available (${SERVICE})"
    fi
done

# ==============================================================================
# Existing Database Services
# ==============================================================================
echo -e "${YELLOW}[4/8] Checking Existing Database Services...${NC}"

# PostgreSQL
if command -v psql &> /dev/null; then
    EXISTING_SERVICES+=("PostgreSQL client installed")
    if systemctl is-active --quiet postgresql 2>/dev/null || pgrep -x postgres > /dev/null; then
        EXISTING_SERVICES+=("PostgreSQL server running")

        # Check for existing databases
        if sudo -u postgres psql -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "wyld_fyre\|ai_infrastructure"; then
            WARNINGS+=("Existing Wyld Fyre database found in PostgreSQL")
        fi
    fi
fi

# Redis
if command -v redis-cli &> /dev/null; then
    EXISTING_SERVICES+=("Redis client installed")
    if systemctl is-active --quiet redis 2>/dev/null || pgrep -x redis-server > /dev/null; then
        EXISTING_SERVICES+=("Redis server running")
    fi
fi

# MongoDB (check for any existing usage)
if command -v mongod &> /dev/null || pgrep -x mongod > /dev/null; then
    EXISTING_SERVICES+=("MongoDB detected")
fi

echo -e "  ${GREEN}✓${NC} Database services checked"

# ==============================================================================
# Web Server Check
# ==============================================================================
echo -e "${YELLOW}[5/8] Checking Web Servers...${NC}"

# Nginx
if command -v nginx &> /dev/null; then
    EXISTING_SERVICES+=("Nginx installed")
    if systemctl is-active --quiet nginx 2>/dev/null || pgrep -x nginx > /dev/null; then
        EXISTING_SERVICES+=("Nginx running")

        # Check for existing sites
        if [ -d /etc/nginx/sites-enabled ]; then
            SITE_COUNT=$(ls -1 /etc/nginx/sites-enabled 2>/dev/null | wc -l)
            if [ "$SITE_COUNT" -gt 0 ]; then
                INFO+=("Nginx: ${SITE_COUNT} sites configured")
            fi
        fi
    fi
fi

# Apache
if command -v apache2 &> /dev/null || command -v httpd &> /dev/null; then
    if systemctl is-active --quiet apache2 2>/dev/null || systemctl is-active --quiet httpd 2>/dev/null; then
        EXISTING_SERVICES+=("Apache running")
    fi
fi

# Caddy
if command -v caddy &> /dev/null; then
    if systemctl is-active --quiet caddy 2>/dev/null; then
        EXISTING_SERVICES+=("Caddy running")
    fi
fi

echo -e "  ${GREEN}✓${NC} Web servers checked"

# ==============================================================================
# Node.js/Python Check
# ==============================================================================
echo -e "${YELLOW}[6/8] Checking Runtime Environments...${NC}"

# Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    INFO+=("Node.js installed: ${NODE_VERSION}")

    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d'.' -f1 | tr -d 'v')
    if [ "$NODE_MAJOR" -lt 20 ]; then
        WARNINGS+=("Node.js version ${NODE_VERSION} is old. Recommended: v20+")
    fi
else
    INFO+=("Node.js not installed (will be installed)")
fi

# Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    INFO+=("Python installed: ${PYTHON_VERSION}")

    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
    if [ "$PYTHON_MINOR" -lt 11 ]; then
        WARNINGS+=("Python ${PYTHON_VERSION} is old. Recommended: 3.12+")
    fi
else
    INFO+=("Python3 not installed (will be installed)")
fi

echo -e "  ${GREEN}✓${NC} Runtime environments checked"

# ==============================================================================
# Existing Data Check
# ==============================================================================
echo -e "${YELLOW}[7/8] Checking Existing Data...${NC}"

# Check for existing installation directory
INSTALL_DIRS=(
    "/opt/wyld-fyre"
    "/opt/ai-infrastructure"
    "/var/lib/wyld-fyre"
    "$HOME/AI-Infrastructure"
)

for DIR in "${INSTALL_DIRS[@]}"; do
    if [ -d "$DIR" ]; then
        SIZE=$(du -sh "$DIR" 2>/dev/null | cut -f1)
        EXISTING_SERVICES+=("Installation directory found: ${DIR} (${SIZE})")
    fi
done

# Check Docker volumes
if command -v docker &> /dev/null && docker info &> /dev/null; then
    WYLD_VOLUMES=$(docker volume ls --format '{{.Name}}' | grep -i 'wyld\|fyre\|ai-infra\|postgres\|redis\|qdrant' || true)
    if [ -n "$WYLD_VOLUMES" ]; then
        INFO+=("Docker volumes found that may contain data:")
        echo "$WYLD_VOLUMES" | while read vol; do
            SIZE=$(docker system df -v 2>/dev/null | grep "$vol" | awk '{print $4}' || echo "unknown")
            echo -e "    - ${vol} (${SIZE})"
        done
    fi
fi

echo -e "  ${GREEN}✓${NC} Existing data checked"

# ==============================================================================
# Environment Variables Check
# ==============================================================================
echo -e "${YELLOW}[8/8] Checking Environment Configuration...${NC}"

ENV_VARS=(
    "ANTHROPIC_API_KEY"
    "OPENAI_API_KEY"
    "POSTGRES_PASSWORD"
    "REDIS_PASSWORD"
    "JWT_SECRET"
)

MISSING_ENV=()
for VAR in "${ENV_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
        MISSING_ENV+=("$VAR")
    else
        echo -e "  ${GREEN}✓${NC} ${VAR} is set"
    fi
done

if [ ${#MISSING_ENV[@]} -gt 0 ]; then
    INFO+=("Missing environment variables (will need to be configured):")
    for VAR in "${MISSING_ENV[@]}"; do
        INFO+=("  - $VAR")
    done
fi

echo -e "  ${GREEN}✓${NC} Environment check complete"

# ==============================================================================
# Summary Report
# ==============================================================================
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Pre-flight Summary                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Print info
if [ ${#INFO[@]} -gt 0 ]; then
    echo -e "${GREEN}[INFO]${NC}"
    for msg in "${INFO[@]}"; do
        echo -e "  ${msg}"
    done
    echo ""
fi

# Print existing services
if [ ${#EXISTING_SERVICES[@]} -gt 0 ]; then
    echo -e "${YELLOW}[EXISTING SERVICES DETECTED]${NC}"
    for msg in "${EXISTING_SERVICES[@]}"; do
        echo -e "  ${YELLOW}!${NC} ${msg}"
    done
    echo ""
fi

# Print conflicts
if [ ${#CONFLICTS[@]} -gt 0 ]; then
    echo -e "${RED}[PORT CONFLICTS]${NC}"
    for msg in "${CONFLICTS[@]}"; do
        echo -e "  ${RED}✗${NC} ${msg}"
    done
    echo ""
fi

# Print warnings
if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}[WARNINGS]${NC}"
    for msg in "${WARNINGS[@]}"; do
        echo -e "  ${YELLOW}!${NC} ${msg}"
    done
    echo ""
fi

# Print errors
if [ ${#ERRORS[@]} -gt 0 ]; then
    echo -e "${RED}[ERRORS]${NC}"
    for msg in "${ERRORS[@]}"; do
        echo -e "  ${RED}✗${NC} ${msg}"
    done
    echo ""
fi

# ==============================================================================
# Recommendations
# ==============================================================================
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Recommendations                         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ ${#EXISTING_SERVICES[@]} -eq 0 ] && [ ${#CONFLICTS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ Clean server detected - Ready for fresh installation${NC}"
    echo ""
    echo "Recommended action:"
    echo "  ./infrastructure/scripts/install.sh --fresh"
elif [ ${#EXISTING_SERVICES[@]} -gt 0 ]; then
    echo -e "${YELLOW}! Existing services detected${NC}"
    echo ""
    echo "Available options:"
    echo ""
    echo "  1. ${GREEN}Fresh Install (Recommended if you want to redo everything)${NC}"
    echo "     ./infrastructure/scripts/install.sh --fresh --clean"
    echo "     This will:"
    echo "       - Stop and remove existing containers"
    echo "       - Remove existing volumes (DATA WILL BE LOST)"
    echo "       - Clean up old installations"
    echo "       - Perform fresh installation"
    echo ""
    echo "  2. ${YELLOW}Upgrade/Merge${NC}"
    echo "     ./infrastructure/scripts/install.sh --upgrade"
    echo "     This will:"
    echo "       - Keep existing data"
    echo "       - Update code and configurations"
    echo "       - Restart services"
    echo ""
    echo "  3. ${BLUE}Parallel Installation${NC}"
    echo "     ./infrastructure/scripts/install.sh --parallel"
    echo "     This will:"
    echo "       - Use alternative ports"
    echo "       - Run alongside existing services"
    echo "       - No data conflicts"
fi

if [ ${#CONFLICTS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}! Port conflicts must be resolved before installation${NC}"
    echo ""
    echo "Options:"
    echo "  1. Stop conflicting services manually"
    echo "  2. Use --parallel flag to use alternative ports"
    echo "  3. Use --clean flag to stop and remove conflicting services"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Exit with appropriate code
if [ ${#ERRORS[@]} -gt 0 ]; then
    exit 1
elif [ ${#CONFLICTS[@]} -gt 0 ]; then
    exit 2
else
    exit 0
fi
