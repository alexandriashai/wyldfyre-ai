# Base Dockerfile for Wyld project containers
# All project-specific images extend this

FROM ubuntu:22.04

LABEL maintainer="Wyld AI Infrastructure"
LABEL org.opencontainers.image.source="https://github.com/wyld-ai/wyld-core"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install base system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential tools
    curl \
    wget \
    git \
    vim \
    nano \
    jq \
    unzip \
    zip \
    tar \
    gzip \
    # Network tools
    openssh-client \
    rsync \
    ca-certificates \
    gnupg \
    # Build essentials
    build-essential \
    # Process management
    supervisor \
    # Terminal
    tmux \
    # Python (always available for PAI tools)
    python3 \
    python3-pip \
    python3-venv \
    # gosu for privilege dropping
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x for Claude Code CLI
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code

# Create wyld group (gid 2000) to match host permissions for mounted files
RUN groupadd -g 2000 wyldgroup

# Create wyld user for running project code, add to wyldgroup
RUN useradd -m -s /bin/bash -u 1000 -G wyldgroup wyld

# Create standard directories including writable Claude config with all subdirs
RUN mkdir -p /app /home/wyld/.local/bin /home/wyld/.claude \
    /home/wyld/.claude-local/cache \
    /home/wyld/.claude-local/debug \
    /home/wyld/.claude-local/plugins \
    /home/wyld/.claude-local/projects \
    /home/wyld/.claude-local/session-env \
    /home/wyld/.claude-local/statsig \
    /home/wyld/.claude-local/todos && \
    chown -R wyld:wyld /app /home/wyld

# Install PAI CLI tools
COPY packages/cli/pai-memory /home/wyld/.local/bin/pai-memory
COPY packages/cli/wyld-claude /home/wyld/.local/bin/wyld-claude
RUN chmod +x /home/wyld/.local/bin/*

# Set up PATH, terminal, and Claude config location
ENV PATH="/home/wyld/.local/bin:${PATH}"
ENV TERM="xterm-256color"
ENV CLAUDE_CONFIG_DIR="/home/wyld/.claude-local"

# Create entrypoint script - runs as root to copy credentials, then drops to wyld
RUN printf '#!/bin/bash\n\
# Copy Claude credentials to writable location if mounted (root can read ACL-protected files)\n\
if [ -f /home/wyld/.claude/.credentials.json ]; then\n\
  cp -f /home/wyld/.claude/.credentials.json /home/wyld/.claude-local/ 2>/dev/null || true\n\
fi\n\
if [ -f /home/wyld/.claude/settings.json ]; then\n\
  cp -f /home/wyld/.claude/settings.json /home/wyld/.claude-local/ 2>/dev/null || true\n\
fi\n\
# Ensure wyld owns everything in .claude-local\n\
chown -R wyld:wyld /home/wyld/.claude-local 2>/dev/null || true\n\
# Drop to wyld user and execute command\n\
exec gosu wyld "$@"\n' > /entrypoint.sh && chmod +x /entrypoint.sh

# Working directory
WORKDIR /app

# Entrypoint runs as root, drops to wyld via gosu
ENTRYPOINT ["/entrypoint.sh"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD gosu wyld echo "healthy" || exit 1

# Default command - keep container running
CMD ["tail", "-f", "/dev/null"]
