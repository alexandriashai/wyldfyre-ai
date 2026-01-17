"""
Docker and Docker Compose templates.
"""

from string import Template


# Python Dockerfile template
DOCKERFILE_PYTHON_TEMPLATE = Template("""# syntax=docker/dockerfile:1
FROM python:${python_version}-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR ${workdir}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ${system_deps} \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r ${user} && useradd -r -g ${user} ${user}

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ${copy_src} ${copy_dest}

# Change ownership
RUN chown -R ${user}:${user} ${workdir}

# Switch to non-root user
USER ${user}

# Expose port
EXPOSE ${port}

# Health check
HEALTHCHECK --interval=${healthcheck_interval} --timeout=${healthcheck_timeout} --start-period=${healthcheck_start_period} --retries=${healthcheck_retries} \\
    CMD ${healthcheck_cmd}

# Run application
CMD ${cmd}
""")


# Node.js Dockerfile template
DOCKERFILE_NODE_TEMPLATE = Template("""# syntax=docker/dockerfile:1
FROM node:${node_version}-slim

# Set environment variables
ENV NODE_ENV=${node_env}

# Set work directory
WORKDIR ${workdir}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    ${system_deps} \\
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r ${user} && useradd -r -g ${user} ${user}

# Copy package files first for better caching
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY ${copy_src} ${copy_dest}

# Change ownership
RUN chown -R ${user}:${user} ${workdir}

# Switch to non-root user
USER ${user}

# Expose port
EXPOSE ${port}

# Health check
HEALTHCHECK --interval=${healthcheck_interval} --timeout=${healthcheck_timeout} --start-period=${healthcheck_start_period} --retries=${healthcheck_retries} \\
    CMD ${healthcheck_cmd}

# Run application
CMD ${cmd}
""")


# Docker Compose template
DOCKER_COMPOSE_TEMPLATE = Template("""version: "${compose_version}"

services:
${services}

${networks_section}

${volumes_section}
""")


# Individual service template for Docker Compose
DOCKER_COMPOSE_SERVICE_TEMPLATE = Template("""  ${name}:
    ${build_or_image}
    container_name: ${container_name}
    restart: ${restart}
    ${ports_section}
    ${environment_section}
    ${env_file_section}
    ${volumes_section}
    ${depends_on_section}
    ${networks_section}
    ${healthcheck_section}
    ${deploy_section}
""")


def render_docker_template(
    template_name: str,
    **kwargs,
) -> str:
    """
    Render a Docker template with the given parameters.

    Args:
        template_name: Name of the template
        **kwargs: Template variables

    Returns:
        Rendered template string

    Example:
        dockerfile = render_docker_template(
            "python",
            python_version="3.12",
            workdir="/app",
            port="8000",
        )
    """
    templates = {
        "python": DOCKERFILE_PYTHON_TEMPLATE,
        "node": DOCKERFILE_NODE_TEMPLATE,
        "compose": DOCKER_COMPOSE_TEMPLATE,
    }

    template = templates.get(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")

    # Set defaults based on template type
    if template_name == "python":
        defaults = {
            "python_version": "3.12",
            "workdir": "/app",
            "system_deps": "curl",
            "user": "app",
            "copy_src": ".",
            "copy_dest": ".",
            "port": "8000",
            "healthcheck_interval": "30s",
            "healthcheck_timeout": "10s",
            "healthcheck_start_period": "5s",
            "healthcheck_retries": "3",
            "healthcheck_cmd": 'curl -f http://localhost:8000/health || exit 1',
            "cmd": '["python", "main.py"]',
        }
    elif template_name == "node":
        defaults = {
            "node_version": "22",
            "node_env": "production",
            "workdir": "/app",
            "system_deps": "curl",
            "user": "app",
            "copy_src": ".",
            "copy_dest": ".",
            "port": "3000",
            "healthcheck_interval": "30s",
            "healthcheck_timeout": "10s",
            "healthcheck_start_period": "5s",
            "healthcheck_retries": "3",
            "healthcheck_cmd": 'curl -f http://localhost:3000/health || exit 1',
            "cmd": '["node", "index.js"]',
        }
    elif template_name == "compose":
        defaults = {
            "compose_version": "3.8",
            "services": "",
            "networks_section": "",
            "volumes_section": "",
        }
    else:
        defaults = {}

    for key, value in defaults.items():
        kwargs.setdefault(key, value)

    rendered = template.safe_substitute(**kwargs)

    # Clean up empty lines from optional fields
    lines = rendered.splitlines()
    cleaned_lines = []

    for line in lines:
        # Skip lines that are just whitespace
        if not line.strip():
            # Keep one empty line for readability
            if cleaned_lines and cleaned_lines[-1].strip():
                cleaned_lines.append("")
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def build_compose_service(
    name: str,
    image: str | None = None,
    build: str | None = None,
    ports: list[str] | None = None,
    environment: dict | None = None,
    env_file: str | None = None,
    volumes: list[str] | None = None,
    depends_on: list[str] | None = None,
    networks: list[str] | None = None,
    restart: str = "unless-stopped",
    healthcheck: dict | None = None,
    deploy: dict | None = None,
) -> str:
    """
    Build a Docker Compose service block.

    Args:
        name: Service name
        image: Docker image to use
        build: Build context path
        ports: List of port mappings
        environment: Environment variables
        env_file: Environment file path
        volumes: Volume mounts
        depends_on: Service dependencies
        networks: Networks to connect to
        restart: Restart policy
        healthcheck: Health check configuration
        deploy: Deploy configuration

    Returns:
        Formatted service YAML block
    """
    lines = [f"  {name}:"]

    if build:
        lines.append(f"    build: {build}")
    elif image:
        lines.append(f"    image: {image}")

    lines.append(f"    container_name: {name}")
    lines.append(f"    restart: {restart}")

    if ports:
        lines.append("    ports:")
        for port in ports:
            lines.append(f'      - "{port}"')

    if environment:
        lines.append("    environment:")
        for key, value in environment.items():
            lines.append(f"      {key}: {value}")

    if env_file:
        lines.append("    env_file:")
        lines.append(f"      - {env_file}")

    if volumes:
        lines.append("    volumes:")
        for volume in volumes:
            lines.append(f"      - {volume}")

    if depends_on:
        lines.append("    depends_on:")
        for dep in depends_on:
            lines.append(f"      - {dep}")

    if networks:
        lines.append("    networks:")
        for network in networks:
            lines.append(f"      - {network}")

    if healthcheck:
        lines.append("    healthcheck:")
        for key, value in healthcheck.items():
            lines.append(f"      {key}: {value}")

    if deploy:
        lines.append("    deploy:")
        for key, value in deploy.items():
            if isinstance(value, dict):
                lines.append(f"      {key}:")
                for k, v in value.items():
                    lines.append(f"        {k}: {v}")
            else:
                lines.append(f"      {key}: {value}")

    return "\n".join(lines)


def build_compose_file(
    services: list[dict],
    networks: list[str] | None = None,
    volumes: list[str] | None = None,
    version: str = "3.8",
) -> str:
    """
    Build a complete Docker Compose file.

    Args:
        services: List of service configurations
        networks: List of network names
        volumes: List of volume names
        version: Compose file version

    Returns:
        Complete Docker Compose YAML content
    """
    lines = [f'version: "{version}"', "", "services:"]

    for service in services:
        service_block = build_compose_service(**service)
        lines.append(service_block)
        lines.append("")

    if networks:
        lines.append("networks:")
        for network in networks:
            lines.append(f"  {network}:")
            lines.append("    driver: bridge")
        lines.append("")

    if volumes:
        lines.append("volumes:")
        for volume in volumes:
            lines.append(f"  {volume}:")
        lines.append("")

    return "\n".join(lines)
