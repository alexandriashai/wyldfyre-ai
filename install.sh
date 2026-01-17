#!/bin/bash
# Wyld Fyre AI Installer
# One-line install: curl -fsSL https://raw.githubusercontent.com/alexandriashai/AI-Infrastructure/main/install.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/alexandriashai/AI-Infrastructure.git"
INSTALL_DIR="${WYLD_FYRE_INSTALL_DIR:-${AI_INSTALL_DIR:-$HOME/wyld-fyre-ai}}"
MIN_DISK_SPACE_GB=10
MIN_RAM_GB=8

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Print banner
print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║              🔥  W Y L D   F Y R E   A I  🔥                 ║"
    echo "║                                                              ║"
    echo "║          Multi-Agent AI System with PAI Framework            ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check system resources
check_system_resources() {
    log_info "Checking system resources..."

    # Check available disk space
    local available_space_kb
    available_space_kb=$(df -k "$HOME" | awk 'NR==2 {print $4}')
    local available_space_gb=$((available_space_kb / 1024 / 1024))

    if [ "$available_space_gb" -lt "$MIN_DISK_SPACE_GB" ]; then
        log_error "Insufficient disk space: ${available_space_gb}GB available, ${MIN_DISK_SPACE_GB}GB required"
        exit 1
    else
        log_success "Disk space: ${available_space_gb}GB available"
    fi

    # Check available RAM (Linux/macOS compatible)
    local total_ram_gb
    if [[ "$(uname)" == "Darwin" ]]; then
        total_ram_gb=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
    else
        total_ram_gb=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 / 1024 ))
    fi

    if [ "$total_ram_gb" -lt "$MIN_RAM_GB" ]; then
        log_warn "Low RAM detected: ${total_ram_gb}GB available, ${MIN_RAM_GB}GB recommended"
        log_warn "The system may run slowly with limited memory"
    else
        log_success "RAM: ${total_ram_gb}GB available"
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()
    local optional_missing=()

    # Check Docker
    if ! command_exists docker; then
        missing+=("docker")
    else
        log_success "Docker found: $(docker --version)"
    fi

    # Check Docker Compose
    if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
        missing+=("docker-compose")
    else
        if docker compose version >/dev/null 2>&1; then
            log_success "Docker Compose found: $(docker compose version)"
        else
            log_success "Docker Compose found: $(docker-compose --version)"
        fi
    fi

    # Check Git
    if ! command_exists git; then
        missing+=("git")
    else
        log_success "Git found: $(git --version)"
    fi

    # Check tmux (required for agent management)
    if ! command_exists tmux; then
        missing+=("tmux")
    else
        log_success "tmux found: $(tmux -V)"
    fi

    # Check curl (for API testing and health checks)
    if ! command_exists curl; then
        optional_missing+=("curl")
        log_warn "curl not found (recommended for health checks)"
    else
        log_success "curl found"
    fi

    # Check Python (optional but recommended)
    if command_exists python3; then
        local py_version
        py_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        local py_major py_minor
        py_major=$(echo "$py_version" | cut -d. -f1)
        py_minor=$(echo "$py_version" | cut -d. -f2)

        if [ "$py_major" -ge 3 ] && [ "$py_minor" -ge 12 ]; then
            log_success "Python found: $py_version"
        else
            log_warn "Python $py_version found, but 3.12+ recommended for development"
        fi
    else
        log_warn "Python 3 not found (optional for development)"
    fi

    # Check Node.js (optional for development)
    if command_exists node; then
        log_success "Node.js found: $(node --version)"
    else
        log_warn "Node.js not found (optional for development)"
    fi

    # Check openssl for JWT secret generation
    if ! command_exists openssl; then
        log_warn "openssl not found, will use alternative method for secret generation"
    else
        log_success "openssl found"
    fi

    # Report missing dependencies
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required dependencies: ${missing[*]}"
        echo ""
        echo "Please install the following:"
        for dep in "${missing[@]}"; do
            case "$dep" in
                docker)
                    echo "  - Docker: https://docs.docker.com/get-docker/"
                    ;;
                docker-compose)
                    echo "  - Docker Compose: https://docs.docker.com/compose/install/"
                    ;;
                git)
                    echo "  - Git: https://git-scm.com/downloads"
                    ;;
                tmux)
                    echo "  - tmux: apt install tmux (Debian/Ubuntu) or brew install tmux (macOS)"
                    ;;
            esac
        done
        exit 1
    fi

    log_success "All prerequisites met!"
}

# Clone repository
clone_repository() {
    if [ -d "$INSTALL_DIR" ]; then
        log_warn "Installation directory already exists: $INSTALL_DIR"
        read -p "Do you want to update the existing installation? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Updating existing installation..."
            cd "$INSTALL_DIR"
            git pull origin main
        else
            log_error "Installation cancelled"
            exit 1
        fi
    else
        log_info "Cloning repository to $INSTALL_DIR..."
        git clone "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi

    log_success "Repository ready!"
}

# Validate API key format
validate_api_key() {
    local key_name="$1"
    local key_value="$2"

    case "$key_name" in
        ANTHROPIC_API_KEY)
            if [[ ! "$key_value" =~ ^sk-ant- ]]; then
                log_warn "Anthropic API key should start with 'sk-ant-'"
                return 1
            fi
            ;;
        OPENAI_API_KEY)
            if [[ ! "$key_value" =~ ^sk- ]]; then
                log_warn "OpenAI API key should start with 'sk-'"
                return 1
            fi
            ;;
    esac
    return 0
}

# Generate secure random string
generate_secret() {
    local length="${1:-64}"
    if command_exists openssl; then
        openssl rand -hex "$((length/2))" 2>/dev/null
    elif [ -r /dev/urandom ]; then
        head -c "$length" /dev/urandom | base64 | tr -d '\n/+=' | head -c "$length"
    else
        # Fallback using $RANDOM
        local secret=""
        for i in $(seq 1 "$length"); do
            secret="${secret}$(printf '%x' $((RANDOM % 16)))"
        done
        echo "${secret:0:$length}"
    fi
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."

    cd "$INSTALL_DIR"

    # Copy example env file if .env doesn't exist
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info "Created .env from .env.example"
        else
            log_warn ".env.example not found, creating minimal .env"
            cat > .env << 'EOF'
# Wyld Fyre AI Environment Variables
# See documentation for full list

# Required API Keys
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Database
POSTGRES_PASSWORD=your_secure_password_here

# Redis
REDIS_PASSWORD=your_redis_password_here

# JWT Secret (auto-generated if empty)
JWT_SECRET=

# Optional: AWS for secrets management
# AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=

# Optional: Cloudflare for DNS
# CLOUDFLARE_API_KEY=
# CLOUDFLARE_EMAIL=
EOF
        fi

        echo ""
        log_warn "Please configure your API keys:"
        echo "  - ANTHROPIC_API_KEY: Get from https://console.anthropic.com/"
        echo "  - OPENAI_API_KEY: Get from https://platform.openai.com/"
        echo ""

        read -p "Would you like to enter API keys now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Get Anthropic API key with validation
            local anthropic_key=""
            while true; do
                read -p "Enter ANTHROPIC_API_KEY: " anthropic_key
                if [ -z "$anthropic_key" ]; then
                    log_warn "Anthropic API key is required for agent functionality"
                    read -p "Continue without it? (y/n) " -n 1 -r
                    echo
                    [[ $REPLY =~ ^[Yy]$ ]] && break
                elif validate_api_key "ANTHROPIC_API_KEY" "$anthropic_key"; then
                    break
                else
                    read -p "Key format looks incorrect. Use anyway? (y/n) " -n 1 -r
                    echo
                    [[ $REPLY =~ ^[Yy]$ ]] && break
                fi
            done

            # Get OpenAI API key with validation
            local openai_key=""
            while true; do
                read -p "Enter OPENAI_API_KEY: " openai_key
                if [ -z "$openai_key" ]; then
                    log_warn "OpenAI API key is required for embeddings and voice features"
                    read -p "Continue without it? (y/n) " -n 1 -r
                    echo
                    [[ $REPLY =~ ^[Yy]$ ]] && break
                elif validate_api_key "OPENAI_API_KEY" "$openai_key"; then
                    break
                else
                    read -p "Key format looks incorrect. Use anyway? (y/n) " -n 1 -r
                    echo
                    [[ $REPLY =~ ^[Yy]$ ]] && break
                fi
            done

            # Get database passwords
            local postgres_pass=""
            read -p "Enter POSTGRES_PASSWORD (leave blank to auto-generate): " postgres_pass
            if [ -z "$postgres_pass" ]; then
                postgres_pass=$(generate_secret 32)
                log_info "Generated secure PostgreSQL password"
            fi

            local redis_pass=""
            read -p "Enter REDIS_PASSWORD (leave blank to auto-generate): " redis_pass
            if [ -z "$redis_pass" ]; then
                redis_pass=$(generate_secret 32)
                log_info "Generated secure Redis password"
            fi

            # Generate JWT secret
            local jwt_secret
            jwt_secret=$(generate_secret 64)
            log_info "Generated JWT secret"

            # Update .env file using sed (macOS and Linux compatible)
            if [[ "$(uname)" == "Darwin" ]]; then
                sed -i '' "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$anthropic_key/" .env
                sed -i '' "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=$openai_key/" .env
                sed -i '' "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$postgres_pass/" .env
                sed -i '' "s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$redis_pass/" .env
                sed -i '' "s/^JWT_SECRET=.*/JWT_SECRET=$jwt_secret/" .env
            else
                sed -i "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$anthropic_key/" .env
                sed -i "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=$openai_key/" .env
                sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$postgres_pass/" .env
                sed -i "s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$redis_pass/" .env
                sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$jwt_secret/" .env
            fi

            log_success "Environment configured!"
        fi
    else
        log_info "Using existing .env file"
    fi
}

# Start services
start_services() {
    log_info "Starting services with Docker Compose..."

    cd "$INSTALL_DIR"

    # Use docker compose or docker-compose depending on what's available
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Pull latest images
    log_info "Pulling Docker images..."
    $COMPOSE_CMD pull

    # Start services
    log_info "Starting containers..."
    $COMPOSE_CMD up -d

    # Wait for services to be healthy
    log_info "Waiting for services to be ready..."
    sleep 10

    # Check service health
    if $COMPOSE_CMD ps | grep -q "healthy\|running"; then
        log_success "Services started successfully!"
    else
        log_warn "Some services may still be starting. Check with: docker compose ps"
    fi
}

# Initialize database
init_database() {
    log_info "Initializing database..."

    cd "$INSTALL_DIR"

    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Wait for database to be ready
    sleep 5

    # Run migrations
    $COMPOSE_CMD exec -T api alembic upgrade head 2>/dev/null || {
        log_warn "Database migration skipped (may already be up to date)"
    }

    log_success "Database initialized!"
}

# Print access information
print_access_info() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}║       🔥  Wyld Fyre AI Installation Complete!  🔥           ║${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Access Wyld Fyre AI at:"
    echo ""
    echo -e "  ${GREEN}Web Portal:${NC}    http://localhost:3000"
    echo -e "  ${GREEN}API Docs:${NC}      http://localhost:8000/docs"
    echo -e "  ${GREEN}Grafana:${NC}       http://localhost:3001"
    echo -e "  ${GREEN}Prometheus:${NC}    http://localhost:9090"
    echo ""
    echo "Talk to Wyld (your AI supervisor):"
    echo ""
    echo "  Open the Web Portal and start a conversation with Wyld,"
    echo "  your intelligent AI assistant powered by Claude."
    echo ""
    echo "Useful commands:"
    echo ""
    echo "  cd $INSTALL_DIR"
    echo "  make help             # Show all available commands"
    echo "  make agents-start     # Start AI agents in tmux"
    echo "  make agents-attach    # Attach to agent tmux session"
    echo "  docker compose logs -f  # View service logs"
    echo "  docker compose down   # Stop all services"
    echo ""
    echo "Documentation: $INSTALL_DIR/README.md"
    echo ""
}

# Main installation flow
main() {
    print_banner

    log_info "Starting Wyld Fyre AI installation..."
    echo ""

    check_system_resources
    echo ""

    check_prerequisites
    echo ""

    clone_repository
    echo ""

    setup_environment
    echo ""

    read -p "Start services now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_services
        echo ""
        init_database
        echo ""
    else
        log_info "You can start services later with: cd $INSTALL_DIR && docker compose up -d"
    fi

    print_access_info
}

# Handle script interruption
trap 'echo -e "\n${RED}Installation interrupted${NC}"; exit 1' INT TERM

# Run main
main "$@"
