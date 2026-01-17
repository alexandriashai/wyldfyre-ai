#!/bin/bash
# Development Environment Setup Script
# Sets up Python virtual environment, Node.js dependencies, and pre-commit hooks

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         AI Infrastructure Development Setup                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Python version
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log_success "Python $PYTHON_VERSION found"

if [[ $(echo "$PYTHON_VERSION < 3.12" | bc -l) -eq 1 ]]; then
    log_warn "Python 3.12+ recommended. You have $PYTHON_VERSION"
fi

# Check Node.js version
log_info "Checking Node.js version..."
if ! command -v node &> /dev/null; then
    log_error "Node.js is required but not installed"
    log_info "Install Node.js 22+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v)
log_success "Node.js $NODE_VERSION found"

# Create Python virtual environment
log_info "Setting up Python virtual environment..."

if [ -d ".venv" ]; then
    log_warn "Virtual environment already exists. Skipping creation."
else
    python3 -m venv .venv
    log_success "Virtual environment created"
fi

# Activate virtual environment
source .venv/bin/activate
log_success "Virtual environment activated"

# Upgrade pip
log_info "Upgrading pip..."
pip install --upgrade pip wheel setuptools

# Install Python packages
log_info "Installing Python packages..."

# Install core packages
pip install -e packages/core
pip install -e packages/messaging
pip install -e packages/memory
pip install -e packages/tmux_manager

# Install services
pip install -e services/api
pip install -e services/supervisor
pip install -e services/voice

# Install agents
for agent_dir in services/agents/*/; do
    if [ -f "${agent_dir}pyproject.toml" ]; then
        pip install -e "$agent_dir"
    fi
done

# Install database package
pip install -e database

# Install development dependencies
pip install ruff mypy pytest pytest-asyncio pytest-cov httpx

log_success "Python packages installed"

# Setup Node.js dependencies
log_info "Installing Node.js dependencies..."
cd web
npm install
cd "$PROJECT_ROOT"
log_success "Node.js dependencies installed"

# Setup pre-commit hooks
log_info "Setting up pre-commit hooks..."

if command -v pre-commit &> /dev/null; then
    pre-commit install
    log_success "Pre-commit hooks installed"
else
    pip install pre-commit
    pre-commit install
    log_success "Pre-commit installed and hooks configured"
fi

# Create local configuration files
log_info "Setting up local configuration..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_success "Created .env from .env.example"
        log_warn "Please edit .env with your API keys"
    fi
else
    log_info ".env file already exists"
fi

# Print success message
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║             Development Setup Complete!                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "To activate the virtual environment:"
echo "  source .venv/bin/activate"
echo ""
echo "To start development servers:"
echo "  make docker-up     # Start databases"
echo "  make dev-api       # Start FastAPI (terminal 1)"
echo "  make dev-web       # Start Next.js (terminal 2)"
echo "  make agents-start  # Start agents (terminal 3)"
echo ""
echo "Run tests:"
echo "  make test          # Run all tests"
echo "  make lint          # Run linters"
echo ""
