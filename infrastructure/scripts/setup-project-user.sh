#!/bin/bash
#
# Setup a scoped project user with filesystem isolation
#
# Usage: setup-project-user.sh <username> <project_root> [--create]
#
# This script:
# 1. Creates a system user (if --create)
# 2. Sets up permissions so user can only access project_root
# 3. Configures sudo for the main wyld user to run as this user
# 4. Sets up rbash (restricted bash) with limited PATH
#

set -e

USERNAME="$1"
PROJECT_ROOT="$2"
CREATE_USER="$3"

if [[ -z "$USERNAME" || -z "$PROJECT_ROOT" ]]; then
    echo "Usage: $0 <username> <project_root> [--create]"
    exit 1
fi

# Validate project root exists
if [[ ! -d "$PROJECT_ROOT" ]]; then
    echo "Error: Project root does not exist: $PROJECT_ROOT"
    exit 1
fi

# Create user if requested
if [[ "$CREATE_USER" == "--create" ]]; then
    if id "$USERNAME" &>/dev/null; then
        echo "User $USERNAME already exists"
    else
        echo "Creating user: $USERNAME"
        useradd -r -s /bin/rbash -d "$PROJECT_ROOT" -M "$USERNAME"
    fi
fi

# Verify user exists
if ! id "$USERNAME" &>/dev/null; then
    echo "Error: User $USERNAME does not exist. Use --create to create it."
    exit 1
fi

# Set ownership and permissions on project root
echo "Setting permissions on $PROJECT_ROOT"
chown -R "$USERNAME:$USERNAME" "$PROJECT_ROOT"
chmod 755 "$PROJECT_ROOT"

# Create a restricted bin directory for the user
USER_BIN="$PROJECT_ROOT/.local/bin"
mkdir -p "$USER_BIN"
chown "$USERNAME:$USERNAME" "$USER_BIN"

# Link allowed commands to user's bin (these are the only commands they can run)
ALLOWED_COMMANDS=(
    # Basic file operations
    "/bin/ls"
    "/bin/cat"
    "/bin/head"
    "/bin/tail"
    "/bin/cp"
    "/bin/mv"
    "/bin/rm"
    "/bin/mkdir"
    "/bin/rmdir"
    "/bin/touch"
    "/bin/chmod"
    "/bin/pwd"
    "/bin/echo"
    "/bin/grep"
    "/bin/sed"
    "/bin/awk"
    "/bin/find"
    "/bin/wc"
    "/bin/sort"
    "/bin/uniq"
    "/bin/diff"
    "/bin/tar"
    "/bin/gzip"
    "/bin/gunzip"
    # Editors
    "/usr/bin/nano"
    "/usr/bin/vim"
    "/usr/bin/vi"
    # Git
    "/usr/bin/git"
    # Node/NPM (for web projects)
    "/usr/bin/node"
    "/usr/bin/npm"
    "/usr/bin/npx"
    # Python
    "/usr/bin/python3"
    "/usr/bin/pip3"
    # PHP (for WordPress/PHP projects)
    "/usr/bin/php"
    "/usr/bin/composer"
    # Common tools
    "/usr/bin/curl"
    "/usr/bin/wget"
    "/usr/bin/jq"
    "/usr/bin/ssh"
    "/usr/bin/rsync"
    # PAI tools
    "/home/wyld-core/packages/cli/pai-memory"
    "/home/wyld-core/packages/cli/wyld-claude"
)

echo "Linking allowed commands to $USER_BIN"
for cmd in "${ALLOWED_COMMANDS[@]}"; do
    if [[ -x "$cmd" ]]; then
        cmd_name=$(basename "$cmd")
        ln -sf "$cmd" "$USER_BIN/$cmd_name" 2>/dev/null || true
    fi
done

# Create .bashrc for restricted environment
USER_BASHRC="$PROJECT_ROOT/.bashrc"
cat > "$USER_BASHRC" << 'EOF'
# Restricted bash environment for Wyld project user
export PATH="$HOME/.local/bin"
export HOME="$PWD"

# Prevent changing directory outside project
cd_restricted() {
    local target="${1:-$HOME}"
    # Resolve to absolute path
    local abs_path=$(realpath -m "$target" 2>/dev/null || echo "$target")
    # Check if it starts with HOME
    if [[ "$abs_path" == "$HOME"* ]]; then
        builtin cd "$target"
    else
        echo "Permission denied: Cannot navigate outside project root"
        return 1
    fi
}
alias cd='cd_restricted'

# Friendly prompt showing project context
export PS1='\[\033[1;32m\][\u@wyld:\w]\$\[\033[0m\] '

# Source PAI environment if available
if [[ -f "$HOME/.pai_env" ]]; then
    source "$HOME/.pai_env"
fi

echo "Welcome to Wyld Terminal - Project: $(basename $HOME)"
echo "Available tools: pai-memory, wyld-claude, git, node, python3, php"
echo "Type 'pai-memory --help' or 'wyld-claude --help' for AI assistance"
EOF
chown "$USERNAME:$USERNAME" "$USER_BASHRC"

# Create .profile that sources .bashrc
USER_PROFILE="$PROJECT_ROOT/.profile"
cat > "$USER_PROFILE" << 'EOF'
if [ -f "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
fi
EOF
chown "$USERNAME:$USERNAME" "$USER_PROFILE"

# Configure sudoers to allow main wyld user to run as this user
SUDOERS_FILE="/etc/sudoers.d/wyld-$USERNAME"
echo "Configuring sudo access in $SUDOERS_FILE"
cat > "$SUDOERS_FILE" << EOF
# Allow wyld service to run commands as $USERNAME without password
wyld ALL=($USERNAME) NOPASSWD: ALL
www-data ALL=($USERNAME) NOPASSWD: ALL
root ALL=($USERNAME) NOPASSWD: ALL
EOF
chmod 440 "$SUDOERS_FILE"

echo ""
echo "Project user setup complete!"
echo "  Username: $USERNAME"
echo "  Home/Root: $PROJECT_ROOT"
echo "  Shell: /bin/rbash (restricted)"
echo "  Allowed commands: ${#ALLOWED_COMMANDS[@]}"
echo ""
echo "To use in Wyld, set 'Terminal User' to '$USERNAME' in Project Settings"
