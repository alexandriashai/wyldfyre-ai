# PHP project container for Wyld
# Supports: Laravel, WordPress, Symfony, custom PHP

ARG PHP_VERSION=8.3

FROM php:${PHP_VERSION}-cli-bookworm AS php-base

LABEL maintainer="Wyld AI Infrastructure"
LABEL wyld.project.type="php"

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
    zip \
    openssh-client \
    rsync \
    ca-certificates \
    tmux \
    python3 \
    python3-pip \
    # PHP extensions dependencies
    libpng-dev \
    libjpeg-dev \
    libwebp-dev \
    libfreetype6-dev \
    libzip-dev \
    libicu-dev \
    libxml2-dev \
    libonig-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    # For MySQL/MariaDB
    default-mysql-client \
    # For PostgreSQL
    libpq-dev \
    # For Redis
    libhiredis-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions
RUN docker-php-ext-configure gd --with-freetype --with-jpeg --with-webp && \
    docker-php-ext-install -j$(nproc) \
    gd \
    zip \
    pdo \
    pdo_mysql \
    pdo_pgsql \
    mysqli \
    intl \
    xml \
    mbstring \
    curl \
    opcache \
    bcmath \
    exif

# Install Redis extension
RUN pecl install redis && docker-php-ext-enable redis

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Install Node.js (needed for asset building in Laravel/WordPress)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g pnpm yarn && \
    rm -rf /var/lib/apt/lists/*

# Create wyld user
RUN useradd -m -s /bin/bash -u 1000 wyld

# Create directories
RUN mkdir -p /app /home/wyld/.local/bin /home/wyld/.claude /home/wyld/.composer && \
    chown -R wyld:wyld /app /home/wyld

# Copy PAI tools
COPY packages/cli/pai-memory /home/wyld/.local/bin/pai-memory
COPY packages/cli/wyld-claude /home/wyld/.local/bin/wyld-claude
RUN chmod +x /home/wyld/.local/bin/*

# Install Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Environment
ENV PATH="/home/wyld/.local/bin:/app/vendor/bin:${PATH}"
ENV COMPOSER_HOME=/home/wyld/.composer

WORKDIR /app
USER wyld

# Install dependencies if composer.json exists
COPY --chown=wyld:wyld composer*.json ./
RUN if [ -f composer.json ]; then composer install --no-interaction --no-scripts; fi

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD php -v || exit 1

CMD ["tail", "-f", "/dev/null"]
