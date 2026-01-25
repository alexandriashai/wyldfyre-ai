# Wyld Server Infrastructure Requirements

## Required Packages

### Core System
```bash
# Ubuntu/Debian
apt update && apt install -y \
    tmux \
    sudo \
    python3 \
    python3-pip \
    git \
    curl \
    jq \
    rsync

# Make CLI tools executable
chmod +x /home/wyld-core/packages/cli/*
```

### For Terminal Users (Project Scoping)
```bash
# rbash is included with bash
# Verify it exists
ls -la /bin/rbash

# If not, create symlink
ln -s /bin/bash /bin/rbash
```

### For Claude Code Integration
```bash
# Install Node.js (required for Claude Code CLI)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Install Claude Code CLI globally
npm install -g @anthropic-ai/claude-code
```

### For Web Projects
```bash
# Node.js/NPM (already installed above)
# PHP (for WordPress/Laravel projects)
apt install -y php php-cli php-common php-curl php-json php-mbstring php-xml php-zip

# Composer
curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer
```

### For Python Projects
```bash
apt install -y python3-venv python3-dev
```

## Directory Structure

```
/home/wyld-core/
├── packages/
│   ├── cli/
│   │   ├── pai-memory          # PAI Memory CLI tool
│   │   └── wyld-claude         # Claude Code wrapper
│   ├── agents/                 # Agent code
│   ├── core/                   # Core libraries
│   └── memory/                 # Memory system
├── services/
│   └── api/                    # FastAPI backend
├── web/                        # Next.js frontend
├── database/                   # SQLAlchemy models & migrations
├── infrastructure/
│   ├── scripts/
│   │   └── setup-project-user.sh  # User isolation script
│   └── docs/
│       └── SERVER_REQUIREMENTS.md # This file
└── /home/wyld-data/            # Project data storage
    └── projects/
        └── {project-id}/       # Individual project roots
```

## Setting Up Project User Isolation

For each project that needs isolation:

```bash
# 1. Create a system user for the project
/home/wyld-core/infrastructure/scripts/setup-project-user.sh \
    project-mysite \
    /home/wyld-data/projects/abc123 \
    --create

# 2. In Wyld Project Settings, set Terminal User to "project-mysite"
```

### What the isolation provides:

1. **Restricted Shell (rbash)** - User cannot:
   - Change PATH
   - Use `cd` with absolute paths outside project
   - Run commands not in their restricted PATH

2. **Limited Commands** - Only allowed commands are available:
   - File operations: ls, cat, cp, mv, rm, mkdir, etc.
   - Editors: nano, vim
   - Dev tools: git, node, npm, python3, php
   - AI tools: pai-memory, wyld-claude

3. **Filesystem Permissions** - User only has write access to their project directory

4. **Sudo Configuration** - The Wyld service can run commands as the project user

## Security Considerations

### What IS isolated:
- File system access (restricted to project root)
- Available commands (whitelisted only)
- Shell capabilities (no PATH modification)

### What is NOT isolated (requires additional setup):
- **Network access** - Users can still make network requests
- **Process visibility** - Users might see other processes
- **Resource limits** - No CPU/memory limits by default

### For stronger isolation, consider:
```bash
# Option 1: Use Docker containers per project
# (Requires significant refactoring)

# Option 2: Use systemd-nspawn
# (Lightweight container)

# Option 3: Use Firejail
apt install firejail
firejail --private=/project/root --net=none bash
```

## Environment Variables

The terminal automatically injects:

| Variable | Description |
|----------|-------------|
| `PAI_API_URL` | API base URL |
| `PAI_TOKEN` | User's auth token |
| `PAI_PROJECT_ID` | Current project ID |
| `PAI_PROJECT_NAME` | Project name |
| `PAI_PROJECT_ROOT` | Project root path |
| `ANTHROPIC_AUTH_TOKEN` | For Claude subscription auth |

## Tmux Session Management

Sessions are named: `wyld-{user_id[:8]}-{project_id[:8]}`

```bash
# List all Wyld sessions
tmux list-sessions | grep wyld-

# Kill a specific session
tmux kill-session -t wyld-abc12345-def67890

# Kill all Wyld sessions
tmux list-sessions | grep wyld- | cut -d: -f1 | xargs -I{} tmux kill-session -t {}
```

## Troubleshooting

### Terminal won't connect
```bash
# Check if tmux is installed
which tmux

# Check if the project root exists
ls -la /path/to/project/root

# Check user permissions
sudo -u project-user ls /path/to/project/root
```

### Claude Code not working
```bash
# Check if Claude CLI is installed
which claude

# Check authentication
claude auth status

# Manual login (if needed)
claude login
```

### PAI Memory errors
```bash
# Test API connectivity
curl -H "Authorization: Bearer $PAI_TOKEN" $PAI_API_URL/api/health

# Check environment variables
env | grep PAI_
```
