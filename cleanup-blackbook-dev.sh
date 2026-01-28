#!/bin/bash
# Cleanup script for dev-blackbook-reviews project

PROJECT_PATH="/home/wyld-web/static/dev-blackbook-reviews"

echo "Starting cleanup of dev-blackbook-reviews project..."

# Remove large log files (>1MB)
echo "Removing large log files..."
find "$PROJECT_PATH/var/logs" -name "*.log" -size +1M -delete 2>/dev/null || true

# Remove temporary build files
echo "Removing temporary build files..."
find "$PROJECT_PATH" -name "*.tmp" -type f -delete 2>/dev/null || true
find "$PROJECT_PATH" -name "*.bak" -type f -delete 2>/dev/null || true
find "$PROJECT_PATH" -name "*.old" -type f -delete 2>/dev/null || true
find "$PROJECT_PATH" -name "*.orig" -type f -delete 2>/dev/null || true

# Remove coverage log files
echo "Removing coverage log files..."
find "$PROJECT_PATH/coverage" -name "*.log" -delete 2>/dev/null || true

# Remove IDE and system files
echo "Removing IDE and system files..."
find "$PROJECT_PATH" -name ".DS_Store" -delete 2>/dev/null || true
find "$PROJECT_PATH" -name "Thumbs.db" -delete 2>/dev/null || true
find "$PROJECT_PATH" -name "*.swp" -delete 2>/dev/null || true
find "$PROJECT_PATH" -name "*.swo" -delete 2>/dev/null || true

# Clean up node_modules cache
echo "Cleaning node_modules cache..."
if [ -d "$PROJECT_PATH/node_modules/.cache" ]; then
    rm -rf "$PROJECT_PATH/node_modules/.cache"
fi

# Update .gitignore with better patterns
echo "Updating .gitignore with better temporary file patterns..."
cat >> "$PROJECT_PATH/.gitignore" << 'EOF'

# Temporary files and work folders
*.tmp
*.temp
*.bak
*.old
*.orig
*.swp
*.swo
*~
.DS_Store
Thumbs.db

# Work and documentation temporary folders
/docs/temp/
/docs/work/
/docs/draft/
/docs/backup/
/work/
/tmp/
/temp/

# IDE and editor files
.vscode/
.idea/
*.sublime-*

# Build and cache artifacts
.cache/
.parcel-cache/
.vite/
*.tsbuildinfo

# Large log files (keep pattern, ignore actual large files)
var/logs/*.log
EOF

echo "Cleanup completed successfully!"
echo "Summary of actions:"
echo "- Removed large log files (>1MB) from var/logs/"
echo "- Removed temporary files (*.tmp, *.bak, *.old, *.orig)"
echo "- Removed coverage log files"
echo "- Removed IDE and system files (.DS_Store, Thumbs.db, swap files)"
echo "- Cleaned node_modules cache"
echo "- Updated .gitignore with comprehensive temporary file patterns"