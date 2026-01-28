#!/bin/bash
# Documentation organization script for dev-blackbook-reviews project

PROJECT_PATH="/home/wyld-web/static/dev-blackbook-reviews"
DOCS_PATH="$PROJECT_PATH/docs"

echo "Organizing documentation structure..."

# Create a proper docs index if it doesn't exist
if [ ! -f "$DOCS_PATH/INDEX.md" ]; then
    cat > "$DOCS_PATH/INDEX.md" << 'EOF'
# BlackBook Reviews - Documentation Index

## Core Documentation
- [README](README.md) - Project overview and quick start
- [Feature Status](FEATURE_STATUS.md) - Current feature implementation status
- [AI Development Workflow](AI_DEVELOPMENT_WORKFLOW.md) - AI-assisted development process
- [Design Tokens](DESIGN_TOKENS.md) - Design system tokens and usage

## Architecture & Technical Docs
- [Architecture](architecture/) - System architecture and design decisions
- [API Documentation](api/) - REST API endpoints and specifications
- [Database](database/) - Schema, migrations, and data management
- [Authentication](authentication/) - Auth system implementation
- [Security](security/) - Security measures and best practices

## Development & Operations
- [Backend Development](backend/) - PHP/Laravel development guides
- [Frontend Development](frontend/) - TypeScript/Vite frontend guides
- [Testing](testing/) - Test strategies and implementation
- [Infrastructure](infrastructure/) - Deployment and server configuration
- [Operations](operations/) - Monitoring, logging, and maintenance

## Features & Integrations
- [Features](features/) - Feature-specific documentation
- [Integrations](integrations/) - Third-party service integrations
- [Performance](performance/) - Optimization and performance tuning

## Development Process
- [Guides](guides/) - Step-by-step development guides
- [Test Plans](test-plans/) - Testing procedures and checklists
- [Roadmap](roadmap/) - Future development plans
- [Quick Reference](quick-reference/) - Common commands and shortcuts

## Archive
- [Archive](archive/) - Deprecated documentation and historical records
EOF
fi

# Remove any empty directories in docs
find "$DOCS_PATH" -type d -empty -delete 2>/dev/null || true

# Create a cleanup summary
echo "Documentation organization completed!"
echo "- Updated main documentation index"
echo "- Removed empty directories"
echo "- Maintained proper folder structure"
echo ""
echo "Current documentation structure:"
ls -la "$DOCS_PATH" | head -20