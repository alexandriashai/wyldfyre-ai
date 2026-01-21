# Wyld Fyre AI Makefile
# Common commands for development, building, and deployment

# Load .env file if it exists (for Redis password, etc.)
-include .env
export

.PHONY: help install dev prod stop build test lint format clean docker-up docker-down \
        agents-start agents-stop agents agent-logs status backup snapshot setup

# Default target
help:
	@echo "Wyld Fyre AI - Available Commands"
	@echo "=================================="
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install all dependencies"
	@echo "  make dev          - Start development environment"
	@echo "  make dev-api      - Start API server in dev mode"
	@echo "  make dev-web      - Start web portal in dev mode"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-int     - Run integration tests"
	@echo "  make test-e2e     - Run end-to-end tests"
	@echo "  make test-cov     - Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint         - Run linters (ruff, eslint)"
	@echo "  make format       - Format code (ruff, prettier)"
	@echo "  make typecheck    - Run type checking (mypy, tsc)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up    - Start all Docker services"
	@echo "  make docker-down  - Stop all Docker services"
	@echo "  make docker-logs  - View Docker service logs"
	@echo "  make docker-build - Build Docker images"
	@echo ""
	@echo "Agents:"
	@echo "  make agents-start - Start all agents in tmux"
	@echo "  make agents-stop  - Stop all agents"
	@echo "  make agents-status- Check agent status"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate   - Run database migrations"
	@echo "  make db-seed      - Seed database with initial data"
	@echo "  make db-reset     - Reset database (WARNING: destructive)"
	@echo ""
	@echo "Quick Start:"
	@echo "  make prod         - Start production (alias for docker-up)"
	@echo "  make stop         - Stop all services and agents"
	@echo "  make status       - Show status of all services"
	@echo ""
	@echo "Git/Backup:"
	@echo "  make backup       - Commit and push to GitHub"
	@echo "  make snapshot     - Create tagged release"
	@echo "  make setup        - Initial setup for new installation"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make clean-all    - Remove all generated files"

# =============================================================================
# Installation
# =============================================================================

install: install-python install-node
	@echo "✓ All dependencies installed"

install-python:
	@echo "Installing Python dependencies..."
	pip install -e ".[dev]"
	pip install -e packages/core
	pip install -e packages/messaging
	pip install -e packages/memory
	pip install -e packages/tmux_manager
	pre-commit install

install-node:
	@echo "Installing Node.js dependencies..."
	cd web && npm install

# =============================================================================
# Development
# =============================================================================

dev: docker-up
	@echo "Starting development environment..."
	@echo "Run 'make dev-api' and 'make dev-web' in separate terminals"

dev-api:
	cd services/api && uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd web && npm run dev

dev-voice:
	cd services/voice && uvicorn src.voice_service.main:app --reload --host 0.0.0.0 --port 8001

# =============================================================================
# Testing
# =============================================================================

test: test-unit test-int
	@echo "✓ All tests passed"

test-unit:
	pytest tests/unit -v

test-int:
	pytest tests/integration -v

test-e2e:
	pytest tests/e2e -v

test-cov:
	pytest tests/ --cov=packages --cov=services --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

# =============================================================================
# Code Quality
# =============================================================================

lint: lint-python lint-node
	@echo "✓ Linting complete"

lint-python:
	ruff check packages/ services/ tests/
	mypy packages/ services/

lint-node:
	cd web && npm run lint

format: format-python format-node
	@echo "✓ Formatting complete"

format-python:
	ruff check packages/ services/ tests/ --fix
	ruff format packages/ services/ tests/

format-node:
	cd web && npm run format

typecheck: typecheck-python typecheck-node
	@echo "✓ Type checking complete"

typecheck-python:
	mypy packages/ services/

typecheck-node:
	cd web && npm run typecheck

# =============================================================================
# Docker
# =============================================================================

docker-up:
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "✓ Docker services started"

docker-down:
	docker-compose down
	@echo "✓ Docker services stopped"

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

docker-clean:
	docker-compose down -v --rmi local
	@echo "✓ Docker cleanup complete"

# =============================================================================
# Agents
# =============================================================================

agents-start:
	./infrastructure/scripts/start-agents.sh
	@echo "✓ Agents started in tmux session 'wyld-fyre-ai'"
	@echo "Run 'tmux attach -t wyld-fyre-ai' to view"

agents-stop:
	./infrastructure/scripts/stop-agents.sh
	@echo "✓ Agents stopped"

agents-status:
	./infrastructure/scripts/agent-status.sh

agents-attach:
	tmux attach -t wyld-fyre-ai

# =============================================================================
# Database
# =============================================================================

db-migrate:
	alembic upgrade head
	@echo "✓ Database migrations complete"

db-seed:
	python -m database.seeds.run
	@echo "✓ Database seeded"

db-reset:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	alembic downgrade base
	alembic upgrade head
	@echo "✓ Database reset complete"

db-shell:
	docker-compose exec postgres psql -U ai_infra -d ai_infrastructure

# =============================================================================
# Cleanup
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage
	@echo "✓ Build artifacts cleaned"

clean-all: clean docker-clean
	rm -rf web/node_modules web/.next
	rm -rf .venv
	@echo "✓ All generated files cleaned"

# =============================================================================
# Production
# =============================================================================

build:
	docker-compose -f docker-compose.yml build
	cd web && npm run build

deploy-staging:
	@echo "Deploying to staging..."
	# Add staging deployment commands

deploy-prod:
	@echo "Deploying to production..."
	# Add production deployment commands

# =============================================================================
# Quick Start Aliases
# =============================================================================

prod: docker-up agents-start
	@echo "✓ Production environment started"

stop: agents-stop docker-down
	@echo "✓ All services stopped"

agents: agents-start

agent-logs:
	@tail -f /home/wyld-data/logs/agents/*.log 2>/dev/null || \
		echo "No agent logs found. Are agents running?"

status:
	@echo "=== Docker Services ==="
	@docker-compose ps 2>/dev/null || echo "Docker compose not available"
	@echo ""
	@echo "=== Agent Sessions ==="
	@tmux ls 2>/dev/null || echo "No tmux sessions"
	@echo ""
	@echo "=== Recent Agent Heartbeats ==="
	@redis-cli -a "$(REDIS_PASSWORD)" keys "agent:heartbeat:*" 2>/dev/null || echo "Redis not available"

# =============================================================================
# Git/Backup
# =============================================================================

backup:
	@echo "Backing up to GitHub..."
	@git add -A
	@git commit -m "backup: $$(date '+%Y-%m-%d %H:%M:%S')" || echo "Nothing to commit"
	@git push origin main
	@echo "✓ Backup complete"

snapshot:
	@read -p "Enter version tag (e.g., v1.0.0): " tag && \
		git tag -a "$$tag" -m "Release $$tag" && \
		git push origin "$$tag"
	@echo "✓ Snapshot created"

# =============================================================================
# Setup
# =============================================================================

setup:
	@echo "Setting up Wyld Fyre AI..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from template. Please edit with your API keys."; \
	fi
	@$(MAKE) install
	@$(MAKE) docker-build
	@echo ""
	@echo "✓ Setup complete! Next steps:"
	@echo "1. Edit .env with your API keys"
	@echo "2. Run 'make dev' to start services"
	@echo "3. Run 'make agents' to start AI agents"
