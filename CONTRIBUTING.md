# Contributing to Wyld Fyre AI

Thank you for your interest in contributing to Wyld Fyre AI! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/wyld-core.git
   cd wyld-core
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/wyldfyre-ai/wyld-core.git
   ```

## Development Setup

### Prerequisites

- Docker 20.10+ and Docker Compose
- Python 3.12+
- Node.js 22.x
- pnpm (for frontend)
- tmux (for agent management)

### Environment Setup

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your API keys
# Required: ANTHROPIC_API_KEY
# Optional: OPENAI_API_KEY (for voice features)

# Start infrastructure services
docker compose up -d postgres redis qdrant

# Install Python dependencies
make install

# Install frontend dependencies
cd web && pnpm install && cd ..

# Run database migrations
make db-migrate
```

### Running Locally

```bash
# Start all services in development mode
make dev

# Or start services individually:
make dev-api      # API server (port 8000)
make dev-web      # Web portal (port 3000)
make agents-start # Agent workers
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-voice-commands` - New features
- `fix/memory-leak-in-supervisor` - Bug fixes
- `docs/update-api-reference` - Documentation
- `refactor/simplify-agent-routing` - Code refactoring

### Commit Messages

Follow conventional commit format:

```
type(scope): short description

Longer description if needed.

Closes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(agents): add browser automation to QA agent
fix(memory): resolve race condition in HOT tier writes
docs(api): add authentication endpoint examples
```

## Code Style

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use `ruff` for linting and formatting

```bash
# Format code
make format

# Run linters
make lint
```

### TypeScript/React

- Use TypeScript for all new code
- Follow existing component patterns
- Use functional components with hooks
- Prefer Tailwind CSS for styling

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_memory.py

# Run with coverage
make test-cov
```

### Writing Tests

- Place tests in `tests/` directories alongside source code
- Use pytest for Python tests
- Mock external services (Claude API, databases) in unit tests
- Write integration tests for critical paths

## Pull Request Process

### Before Submitting

1. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests**:
   ```bash
   make test
   make lint
   ```

3. **Update documentation** if needed

### PR Requirements

- Clear title and description
- Reference related issues
- Include test coverage for new features
- Pass all CI checks
- Request review from maintainers

### PR Template

When you open a PR, you'll see a template. Please fill it out completely:

- Summary of changes
- Type of change (feature, fix, etc.)
- Testing performed
- Breaking changes (if any)

### Review Process

1. Automated CI runs tests and linting
2. Maintainer reviews code
3. Address feedback in new commits
4. Maintainer approves and merges

## Issue Guidelines

### Bug Reports

Include:
- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, versions)
- Logs or error messages

### Feature Requests

Include:
- Clear description of the feature
- Use case and motivation
- Proposed implementation (optional)
- Alternatives considered

### Questions

For questions about usage or implementation:
- Check existing documentation first
- Search closed issues
- Open a discussion if still unclear

## Project Structure

Understanding the codebase:

```
wyld-core/
├── agents/           # Agent implementations
│   ├── code/         # Code Agent
│   ├── data/         # Data Agent
│   ├── infra/        # Infrastructure Agent
│   ├── qa/           # QA Agent
│   └── research/     # Research Agent
├── packages/         # Shared libraries
│   ├── agents/       # Base agent framework
│   ├── core/         # Core utilities
│   └── memory/       # Memory system
├── services/
│   ├── api/          # FastAPI backend
│   ├── supervisor/   # Wyld supervisor
│   └── voice/        # Voice service
├── web/              # Next.js frontend
└── pai/              # PAI framework integration
```

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues and discussions
- Read the [Architecture Guide](ARCHITECTURE.md) for technical details

## Recognition

Contributors are recognized in release notes and the project README. Thank you for helping make Wyld Fyre AI better!
