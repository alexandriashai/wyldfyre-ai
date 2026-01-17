#!/bin/bash
# AI Infrastructure Installer
# One-line install: curl -fsSL https://raw.githubusercontent.com/alexandriashai/AI-Infrastructure/main/install.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/alexandriashai/AI-Infrastructure.git"
INSTALL_DIR="${AI_INSTALL_DIR:-$HOME/AI-Infrastructure}"

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
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              AI Infrastructure Installer                      ║"
    echo "║          Multi-Agent AI System with PAI Framework             ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

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

    # Check Python (optional but recommended)
    if command_exists python3; then
        log_success "Python found: $(python3 --version)"
    else
        log_warn "Python 3 not found (optional for development)"
    fi

    # Check Node.js (optional for development)
    if command_exists node; then
        log_success "Node.js found: $(node --version)"
    else
        log_warn "Node.js not found (optional for development)"
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
# AI Infrastructure Environment Variables
# See documentation for full list

# Required API Keys
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Database
POSTGRES_PASSWORD=your_secure_password_here

# Redis
REDIS_PASSWORD=your_redis_password_here

# JWT Secret (generate with: openssl rand -hex 32)
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
        log_warn "Please edit .env file with your API keys:"
        echo "  - ANTHROPIC_API_KEY: Get from https://console.anthropic.com/"
        echo "  - OPENAI_API_KEY: Get from https://platform.openai.com/"
        echo ""

        read -p "Would you like to enter API keys now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            read -p "Enter ANTHROPIC_API_KEY: " anthropic_key
            read -p "Enter OPENAI_API_KEY: " openai_key
            read -p "Enter POSTGRES_PASSWORD: " postgres_pass
            read -p "Enter REDIS_PASSWORD: " redis_pass

            # Generate JWT secret
            jwt_secret=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '\n' | head -c 64)

            # Update .env file
            sed -i.bak "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=$anthropic_key/" .env
            sed -i.bak "s/^OPENAI_API_KEY=.*/OPENAI_API_KEY=$openai_key/" .env
            sed -i.bak "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$postgres_pass/" .env
            sed -i.bak "s/^REDIS_PASSWORD=.*/REDIS_PASSWORD=$redis_pass/" .env
            sed -i.bak "s/^JWT_SECRET=.*/JWT_SECRET=$jwt_secret/" .env
            rm -f .env.bak

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
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Installation Complete!                          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Access your AI Infrastructure at:"
    echo ""
    echo "  Web Portal:    http://localhost:3000"
    echo "  API Docs:      http://localhost:8000/docs"
    echo "  Grafana:       http://localhost:3001"
    echo "  Prometheus:    http://localhost:9090"
    echo ""
    echo "Useful commands:"
    echo ""
    echo "  View logs:     docker compose logs -f"
    echo "  Stop:          docker compose down"
    echo "  Restart:       docker compose restart"
    echo "  Status:        docker compose ps"
    echo ""
    echo "Documentation:   $INSTALL_DIR/docs/"
    echo ""
}

# Main installation flow
main() {
    print_banner

    log_info "Starting AI Infrastructure installation..."
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

# Run main
main "$@"
