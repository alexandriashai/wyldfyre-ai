# Python project container for Wyld
# Supports: Django, Flask, FastAPI, data science, etc.

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim-bookworm AS python-base

LABEL maintainer="Wyld AI Infrastructure"
LABEL wyld.project.type="python"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

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
    # For PostgreSQL
    libpq-dev \
    # For MySQL
    default-libmysqlclient-dev \
    # For image processing
    libpng-dev \
    libjpeg-dev \
    libwebp-dev \
    # For scientific computing
    libffi-dev \
    libssl-dev \
    # For lxml
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for frontend assets)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g pnpm yarn @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*

# Create wyld user
RUN useradd -m -s /bin/bash -u 1000 wyld

# Create directories
RUN mkdir -p /app /home/wyld/.local/bin /home/wyld/.claude /home/wyld/.cache/pip && \
    chown -R wyld:wyld /app /home/wyld

# Install common Python tools
RUN pip install --upgrade pip setuptools wheel && \
    pip install \
    poetry \
    pipenv \
    pdm \
    black \
    ruff \
    mypy \
    pytest \
    ipython

# Copy PAI tools
COPY packages/cli/pai-memory /home/wyld/.local/bin/pai-memory
COPY packages/cli/wyld-claude /home/wyld/.local/bin/wyld-claude
RUN chmod +x /home/wyld/.local/bin/*

# Environment
ENV PATH="/home/wyld/.local/bin:/app/.venv/bin:${PATH}"
ENV VIRTUAL_ENV=/app/.venv

WORKDIR /app
USER wyld

# Install dependencies if requirements exist
COPY --chown=wyld:wyld requirements*.txt pyproject.toml* poetry.lock* Pipfile* ./
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; \
    elif [ -f pyproject.toml ]; then pip install -e .; \
    elif [ -f Pipfile ]; then pipenv install; fi || true

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "print('healthy')" || exit 1

CMD ["tail", "-f", "/dev/null"]
