#!/bin/bash
# Backup Script for AI Infrastructure
# Creates backups of database, memory, and configuration

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

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="ai-infrastructure-backup-$TIMESTAMP"

# Create backup directory
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

log_info "Starting backup: $BACKUP_NAME"

# Docker Compose command
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Backup PostgreSQL database
backup_database() {
    log_info "Backing up PostgreSQL database..."

    cd "$PROJECT_ROOT"

    # Get database credentials from environment
    source .env 2>/dev/null || true
    POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

    # Dump database
    $COMPOSE_CMD exec -T postgres pg_dump -U postgres ai_infrastructure \
        > "$BACKUP_DIR/$BACKUP_NAME/database.sql" 2>/dev/null

    if [ -f "$BACKUP_DIR/$BACKUP_NAME/database.sql" ] && [ -s "$BACKUP_DIR/$BACKUP_NAME/database.sql" ]; then
        gzip "$BACKUP_DIR/$BACKUP_NAME/database.sql"
        log_success "Database backed up: database.sql.gz"
    else
        log_warn "Database backup may be empty (is the database running?)"
        rm -f "$BACKUP_DIR/$BACKUP_NAME/database.sql"
    fi
}

# Backup Qdrant vector database
backup_qdrant() {
    log_info "Backing up Qdrant vector database..."

    cd "$PROJECT_ROOT"

    # Create Qdrant snapshot
    curl -s -X POST "http://localhost:6333/collections/learnings/snapshots" \
        -o /dev/null 2>/dev/null || true

    # Copy Qdrant data directory
    if [ -d "data/qdrant" ]; then
        tar -czf "$BACKUP_DIR/$BACKUP_NAME/qdrant-data.tar.gz" -C data qdrant 2>/dev/null
        log_success "Qdrant data backed up: qdrant-data.tar.gz"
    else
        log_warn "Qdrant data directory not found"
    fi
}

# Backup Redis data
backup_redis() {
    log_info "Backing up Redis data..."

    cd "$PROJECT_ROOT"

    # Trigger Redis BGSAVE
    $COMPOSE_CMD exec -T redis redis-cli BGSAVE >/dev/null 2>&1 || true
    sleep 2

    # Copy Redis dump
    if $COMPOSE_CMD exec -T redis cat /data/dump.rdb > "$BACKUP_DIR/$BACKUP_NAME/redis-dump.rdb" 2>/dev/null; then
        if [ -s "$BACKUP_DIR/$BACKUP_NAME/redis-dump.rdb" ]; then
            gzip "$BACKUP_DIR/$BACKUP_NAME/redis-dump.rdb"
            log_success "Redis data backed up: redis-dump.rdb.gz"
        else
            rm -f "$BACKUP_DIR/$BACKUP_NAME/redis-dump.rdb"
            log_warn "Redis dump is empty"
        fi
    else
        log_warn "Could not backup Redis (is it running?)"
    fi
}

# Backup configuration files
backup_config() {
    log_info "Backing up configuration files..."

    cd "$PROJECT_ROOT"

    # Create config backup directory
    mkdir -p "$BACKUP_DIR/$BACKUP_NAME/config"

    # Copy config files (excluding secrets)
    cp -r config/* "$BACKUP_DIR/$BACKUP_NAME/config/" 2>/dev/null || true

    # Copy docker-compose files
    cp docker-compose.yml "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || true
    cp docker-compose.dev.yml "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || true

    # Copy .env.example (not .env which contains secrets)
    cp .env.example "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || true

    log_success "Configuration files backed up"
}

# Backup PAI memory files
backup_pai_memory() {
    log_info "Backing up PAI memory files..."

    cd "$PROJECT_ROOT"

    if [ -d "pai" ]; then
        tar -czf "$BACKUP_DIR/$BACKUP_NAME/pai-memory.tar.gz" pai 2>/dev/null
        log_success "PAI memory backed up: pai-memory.tar.gz"
    else
        log_warn "PAI directory not found"
    fi
}

# Create backup archive
create_archive() {
    log_info "Creating backup archive..."

    cd "$BACKUP_DIR"

    tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
    rm -rf "$BACKUP_NAME"

    log_success "Backup archive created: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
}

# Cleanup old backups (keep last 10)
cleanup_old_backups() {
    log_info "Cleaning up old backups..."

    cd "$BACKUP_DIR"

    # Count backups
    backup_count=$(ls -1 ai-infrastructure-backup-*.tar.gz 2>/dev/null | wc -l)

    if [ "$backup_count" -gt 10 ]; then
        # Remove oldest backups, keep 10
        ls -1t ai-infrastructure-backup-*.tar.gz | tail -n +11 | xargs rm -f
        log_success "Cleaned up old backups (keeping last 10)"
    fi
}

# Print backup summary
print_summary() {
    local backup_file="$BACKUP_DIR/$BACKUP_NAME.tar.gz"
    local size=$(du -h "$backup_file" | cut -f1)

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    Backup Complete!                           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Backup file: $backup_file"
    echo "Size: $size"
    echo ""
    echo "Contents:"
    tar -tzf "$backup_file" | head -20
    echo "..."
    echo ""
    echo "To restore from this backup:"
    echo "  ./scripts/restore.sh $backup_file"
    echo ""
}

# Main
main() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              AI Infrastructure Backup                         ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    backup_database
    backup_qdrant
    backup_redis
    backup_config
    backup_pai_memory
    create_archive
    cleanup_old_backups
    print_summary
}

# Run
main "$@"
