# Node.js project container for Wyld
# Supports: Node.js, Next.js, React, Vue, Astro, etc.

ARG NODE_VERSION=20

FROM node:${NODE_VERSION}-bookworm-slim AS node-base

LABEL maintainer="Wyld AI Infrastructure"
LABEL wyld.project.type="node"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    vim \
    nano \
    jq \
    unzip \
    openssh-client \
    rsync \
    ca-certificates \
    build-essential \
    tmux \
    python3 \
    python3-pip \
    # For native modules
    libpng-dev \
    libjpeg-dev \
    libwebp-dev \
    # For Puppeteer/Playwright
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Create wyld user
RUN useradd -m -s /bin/bash -u 1000 wyld || true

# Create directories
RUN mkdir -p /app /home/wyld/.local/bin /home/wyld/.claude /home/wyld/.npm && \
    chown -R wyld:wyld /app /home/wyld

# Install global npm packages
RUN npm install -g \
    pnpm \
    yarn \
    typescript \
    ts-node \
    eslint \
    prettier \
    @anthropic-ai/claude-code \
    && npm cache clean --force

# Copy PAI tools
COPY packages/cli/pai-memory /home/wyld/.local/bin/pai-memory
COPY packages/cli/wyld-claude /home/wyld/.local/bin/wyld-claude
RUN chmod +x /home/wyld/.local/bin/*

# Environment
ENV PATH="/home/wyld/.local/bin:/app/node_modules/.bin:${PATH}"
ENV NODE_ENV=development
ENV NPM_CONFIG_PREFIX=/home/wyld/.npm-global

WORKDIR /app
USER wyld

# Install dependencies if package.json exists (for pre-built images)
# In practice, dependencies are installed at runtime via volume mount
COPY --chown=wyld:wyld package*.json ./
RUN if [ -f package.json ]; then npm install; fi

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD node -e "console.log('healthy')" || exit 1

CMD ["tail", "-f", "/dev/null"]
