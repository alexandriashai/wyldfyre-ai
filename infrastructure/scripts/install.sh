#!/bin/bash
# Wyld Fyre AI - Installation Script
# Usage: ./install.sh [OPTIONS]
#
# Options:
#   --fresh     Fresh installation (default)
#   --clean     Clean up existing installations before installing
#   --upgrade   Upgrade existing installation
#   --parallel  Install alongside existing services (different ports)
#   --dry-run   Show what would be done without making changes
#   --skip-docker  Skip Docker installation (if already installed)
#   --skip-deps    Skip dependency installation
#   -y, --yes   Auto-confirm all prompts
#   -h, --help  Show this help message

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default options
INSTALL_MODE="fresh"
CLEAN_FIRST=false
DRY_RUN=false
SKIP_DOCKER=false
SKIP_DEPS=false
AUTO_CONFIRM=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fresh)
            INSTALL_MODE="fresh"
            shift
            ;;
        --clean)
            CLEAN_FIRST=true
            shift
            ;;
        --upgrade)
            INSTALL_MODE="upgrade"
            shift
            ;;
        --parallel)
            INSTALL_MODE="parallel"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        -y|--yes)
            AUTO_CONFIRM=true
            shift
            ;;
        -h|--help)
            head -20 "$0" | tail -18
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Dry run wrapper
run() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${PURPLE}[DRY-RUN]${NC} Would execute: $*"
    else
        "$@"
    fi
}

# Confirm prompt
confirm() {
    if [ "$AUTO_CONFIRM" = true ]; then
        return 0
    fi

    echo -e "${YELLOW}$1${NC}"
    read -p "Continue? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# ==============================================================================
# Banner
# ==============================================================================
echo -e "${PURPLE}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   ██╗    ██╗██╗   ██╗██╗     ██████╗     ███████╗██╗   ██╗██████╗ ███████╗║
║   ██║    ██║╚██╗ ██╔╝██║     ██╔══██╗    ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝║
║   ██║ █╗ ██║ ╚████╔╝ ██║     ██║  ██║    █████╗   ╚████╔╝ ██████╔╝█████╗  ║
║   ██║███╗██║  ╚██╔╝  ██║     ██║  ██║    ██╔══╝    ╚██╔╝  ██╔══██╗██╔══╝  ║
║   ╚███╔███╔╝   ██║   ███████╗██████╔╝    ██║        ██║   ██║  ██║███████╗║
║    ╚══╝╚══╝    ╚═╝   ╚══════╝╚═════╝     ╚═╝        ╚═╝   ╚═╝  ╚═╝╚══════╝║
║                                                                           ║
║                         AI Infrastructure Installer                       ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

log_info "Installation Mode: ${INSTALL_MODE}"
log_info "Clean First: ${CLEAN_FIRST}"
log_info "Project Root: ${PROJECT_ROOT}"

if [ "$DRY_RUN" = true ]; then
    log_warn "DRY RUN MODE - No changes will be made"
fi

echo ""

# ==============================================================================
# Step 1: Pre-flight Check
# ==============================================================================
log_step "Running pre-flight check..."

if [ -f "$SCRIPT_DIR/preflight-check.sh" ]; then
    bash "$SCRIPT_DIR/preflight-check.sh" || true
else
    log_warn "Pre-flight check script not found"
fi

echo ""

# ==============================================================================
# Step 2: Clean Up (if requested)
# ==============================================================================
if [ "$CLEAN_FIRST" = true ]; then
    log_step "Cleaning up existing installation..."

    if ! confirm "This will remove existing containers, volumes, and data. Are you sure?"; then
        log_error "Cleanup cancelled"
        exit 1
    fi

    # Stop and remove Docker containers
    if command -v docker &> /dev/null; then
        log_info "Stopping Docker containers..."
        run docker-compose -f "$PROJECT_ROOT/docker-compose.yml" down -v 2>/dev/null || true

        # Remove related containers
        CONTAINERS=$(docker ps -a --format '{{.Names}}' | grep -i 'wyld\|fyre\|ai-infra' || true)
        if [ -n "$CONTAINERS" ]; then
            log_info "Removing containers: $CONTAINERS"
            run docker rm -f $CONTAINERS 2>/dev/null || true
        fi

        # Remove related volumes
        VOLUMES=$(docker volume ls --format '{{.Name}}' | grep -i 'wyld\|fyre\|ai-infra\|_postgres\|_redis\|_qdrant' || true)
        if [ -n "$VOLUMES" ]; then
            log_info "Removing volumes: $VOLUMES"
            run docker volume rm $VOLUMES 2>/dev/null || true
        fi

        # Remove related networks
        NETWORKS=$(docker network ls --format '{{.Name}}' | grep -i 'wyld\|fyre\|ai-infra' || true)
        if [ -n "$NETWORKS" ]; then
            log_info "Removing networks: $NETWORKS"
            run docker network rm $NETWORKS 2>/dev/null || true
        fi
    fi

    # Clean up installation directories
    CLEANUP_DIRS=(
        "/opt/wyld-fyre"
        "/var/lib/wyld-fyre"
        "/var/log/wyld-fyre"
    )

    for DIR in "${CLEANUP_DIRS[@]}"; do
        if [ -d "$DIR" ]; then
            log_info "Removing directory: $DIR"
            run sudo rm -rf "$DIR"
        fi
    done

    log_info "Cleanup complete"
    echo ""
fi

# ==============================================================================
# Step 3: Install Dependencies
# ==============================================================================
if [ "$SKIP_DEPS" = false ]; then
    log_step "Installing dependencies..."

    # Detect package manager
    if command -v apt-get &> /dev/null; then
        PKG_MGR="apt-get"
        PKG_INSTALL="apt-get install -y"
        run sudo apt-get update
    elif command -v dnf &> /dev/null; then
        PKG_MGR="dnf"
        PKG_INSTALL="dnf install -y"
    elif command -v yum &> /dev/null; then
        PKG_MGR="yum"
        PKG_INSTALL="yum install -y"
    else
        log_warn "Unknown package manager - skipping system dependencies"
        PKG_MGR=""
    fi

    if [ -n "$PKG_MGR" ]; then
        log_info "Installing system packages..."
        run sudo $PKG_INSTALL curl wget git jq htop tmux
    fi

    # Install Docker
    if [ "$SKIP_DOCKER" = false ] && ! command -v docker &> /dev/null; then
        log_info "Installing Docker..."
        run curl -fsSL https://get.docker.com | sh
        run sudo usermod -aG docker $USER
        log_warn "You may need to log out and back in for Docker group changes to take effect"
    fi

    # Start Docker service
    if command -v docker &> /dev/null; then
        if ! docker info &> /dev/null; then
            log_info "Starting Docker service..."
            run sudo systemctl start docker
            run sudo systemctl enable docker
        fi
    fi

    # Install Node.js if not present
    if ! command -v node &> /dev/null; then
        log_info "Installing Node.js..."
        if [ "$PKG_MGR" = "apt-get" ]; then
            run curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
            run sudo apt-get install -y nodejs
        else
            run curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -
            run sudo $PKG_INSTALL nodejs
        fi
    fi

    # Install Python 3.12 if not present or too old
    PYTHON_VERSION=$(python3 --version 2>/dev/null | cut -d' ' -f2 | cut -d'.' -f2 || echo "0")
    if [ "$PYTHON_VERSION" -lt 11 ]; then
        log_info "Installing Python 3.12..."
        if [ "$PKG_MGR" = "apt-get" ]; then
            run sudo add-apt-repository -y ppa:deadsnakes/ppa
            run sudo apt-get update
            run sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
            run sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
        else
            log_warn "Please install Python 3.12+ manually"
        fi
    fi

    log_info "Dependencies installed"
    echo ""
fi

# ==============================================================================
# Step 4: Create Directory Structure
# ==============================================================================
log_step "Creating directory structure..."

DIRS=(
    "/opt/wyld-fyre"
    "/var/lib/wyld-fyre/data"
    "/var/lib/wyld-fyre/backups"
    "/var/log/wyld-fyre"
    "/etc/wyld-fyre"
)

for DIR in "${DIRS[@]}"; do
    if [ ! -d "$DIR" ]; then
        log_info "Creating $DIR"
        run sudo mkdir -p "$DIR"
        run sudo chown -R $USER:$USER "$DIR"
    fi
done

log_info "Directory structure created"
echo ""

# ==============================================================================
# Step 5: Configure Environment
# ==============================================================================
log_step "Configuring environment..."

ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        log_info "Creating .env from .env.example"
        run cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
        log_info "Creating default .env file"
        run cat > "$ENV_FILE" << 'ENVEOF'
# Wyld Fyre AI Configuration
# Generated by install.sh

# Required API Keys
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Database Configuration
POSTGRES_USER=wyld_fyre
POSTGRES_PASSWORD=
POSTGRES_DB=wyld_fyre

# Redis Configuration
REDIS_PASSWORD=

# Security
JWT_SECRET=

# Optional: Cloud Services
# CLOUDFLARE_API_KEY=
# CLOUDFLARE_EMAIL=
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_REGION=us-east-1

# Optional: GitHub Integration
# GITHUB_PAT=

# Service URLs (for Docker networking)
API_URL=http://api:8000
WEB_URL=http://web:3000
POSTGRES_HOST=db
REDIS_HOST=redis
QDRANT_HOST=qdrant
ENVEOF
    fi

    log_warn "Please edit $ENV_FILE and add your API keys and passwords"
else
    log_info ".env file already exists"
fi

# Generate secure passwords if not set
if [ "$DRY_RUN" = false ]; then
    if grep -q "^POSTGRES_PASSWORD=$" "$ENV_FILE" 2>/dev/null; then
        POSTGRES_PASS=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
        sed -i "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$POSTGRES_PASS/" "$ENV_FILE"
        log_info "Generated PostgreSQL password"
    fi

    if grep -q "^REDIS_PASSWORD=$" "$ENV_FILE" 2>/dev/null; then
        REDIS_PASS=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
        sed -i "s/^REDIS_PASSWORD=$/REDIS_PASSWORD=$REDIS_PASS/" "$ENV_FILE"
        log_info "Generated Redis password"
    fi

    if grep -q "^JWT_SECRET=$" "$ENV_FILE" 2>/dev/null; then
        JWT=$(openssl rand -base64 64 | tr -d '/+=' | head -c 64)
        sed -i "s/^JWT_SECRET=$/JWT_SECRET=$JWT/" "$ENV_FILE"
        log_info "Generated JWT secret"
    fi
fi

echo ""

# ==============================================================================
# Step 6: Build and Start Services
# ==============================================================================
log_step "Building and starting services..."

cd "$PROJECT_ROOT"

# Create docker-compose override for parallel installation
if [ "$INSTALL_MODE" = "parallel" ]; then
    log_info "Creating port override for parallel installation..."
    run cat > "$PROJECT_ROOT/docker-compose.override.yml" << 'DCEOF'
version: '3.8'
services:
  web:
    ports:
      - "3010:3000"
  api:
    ports:
      - "8010:8000"
  db:
    ports:
      - "5442:5432"
  redis:
    ports:
      - "6389:6379"
  qdrant:
    ports:
      - "6343:6333"
DCEOF
    log_info "Services will use alternative ports (3010, 8010, 5442, 6389, 6343)"
fi

# Pull and build images
log_info "Pulling base images..."
run docker-compose pull --ignore-pull-failures || true

log_info "Building services..."
run docker-compose build

# Start services
log_info "Starting services..."
run docker-compose up -d

# Wait for services to be ready
log_info "Waiting for services to start..."
sleep 10

# Check service status
log_info "Checking service status..."
run docker-compose ps

echo ""

# ==============================================================================
# Step 7: Initialize Database
# ==============================================================================
log_step "Initializing database..."

# Wait for database to be ready
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker-compose exec -T db pg_isready -U wyld_fyre &> /dev/null; then
        log_info "Database is ready"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    log_info "Waiting for database... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log_error "Database did not become ready in time"
    exit 1
fi

# Run migrations
log_info "Running database migrations..."
run docker-compose exec -T api python -m alembic upgrade head || true

# Seed database (if seed script exists)
if [ -f "$PROJECT_ROOT/scripts/seed-db.py" ]; then
    log_info "Seeding database..."
    run docker-compose exec -T api python scripts/seed-db.py || true
fi

echo ""

# ==============================================================================
# Step 8: Verify Installation
# ==============================================================================
log_step "Verifying installation..."

SERVICES_OK=true

# Check each service
check_service() {
    local name=$1
    local url=$2

    if curl -sf "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $name is running"
    else
        echo -e "  ${RED}✗${NC} $name is not responding at $url"
        SERVICES_OK=false
    fi
}

echo "Service Status:"

if [ "$INSTALL_MODE" = "parallel" ]; then
    check_service "Web Portal" "http://localhost:3010"
    check_service "API Server" "http://localhost:8010/health"
else
    check_service "Web Portal" "http://localhost:3000"
    check_service "API Server" "http://localhost:8000/health"
fi

# Docker container status
echo ""
echo "Container Status:"
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""

# ==============================================================================
# Completion
# ==============================================================================
if [ "$SERVICES_OK" = true ]; then
    echo -e "${GREEN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                    Installation Complete! 🎉                              ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    if [ "$INSTALL_MODE" = "parallel" ]; then
        echo "Access your Wyld Fyre AI instance at:"
        echo "  Web Portal:  http://localhost:3010"
        echo "  API Server:  http://localhost:8010"
    else
        echo "Access your Wyld Fyre AI instance at:"
        echo "  Web Portal:  http://localhost:3000"
        echo "  API Server:  http://localhost:8000"
    fi

    echo ""
    echo "Next steps:"
    echo "  1. Open the Web Portal and create an admin account"
    echo "  2. Add your Anthropic API key in the settings"
    echo "  3. Configure and start agents from the dashboard"
    echo ""
    echo "Useful commands:"
    echo "  docker-compose logs -f          # View logs"
    echo "  docker-compose restart          # Restart services"
    echo "  docker-compose down             # Stop services"
    echo "  docker-compose up -d            # Start services"
    echo ""
else
    echo -e "${YELLOW}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                Installation Complete with Warnings ⚠️                     ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"

    echo "Some services may not be running correctly."
    echo "Please check the logs with: docker-compose logs"
    echo ""
fi

# Create installation marker
if [ "$DRY_RUN" = false ]; then
    echo "$(date -Iseconds) - Installation completed (mode: $INSTALL_MODE)" >> /var/log/wyld-fyre/install.log
fi
