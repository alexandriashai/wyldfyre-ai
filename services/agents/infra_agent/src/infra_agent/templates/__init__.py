"""
Infrastructure templates for the Infra Agent.

Provides pre-built templates for common infrastructure configurations.
"""

from .nginx_templates import (
    NGINX_STATIC_TEMPLATE,
    NGINX_PROXY_TEMPLATE,
    NGINX_PHP_TEMPLATE,
    NGINX_SSL_TEMPLATE,
    NGINX_REDIRECT_TEMPLATE,
    NGINX_WEBSOCKET_TEMPLATE,
    render_nginx_template,
)
from .systemd_templates import (
    SYSTEMD_SERVICE_TEMPLATE,
    SYSTEMD_TIMER_TEMPLATE,
    SYSTEMD_SOCKET_TEMPLATE,
    SYSTEMD_PATH_TEMPLATE,
    render_systemd_template,
)
from .docker_templates import (
    DOCKERFILE_PYTHON_TEMPLATE,
    DOCKERFILE_NODE_TEMPLATE,
    DOCKER_COMPOSE_TEMPLATE,
    render_docker_template,
)

__all__ = [
    # Nginx
    "NGINX_STATIC_TEMPLATE",
    "NGINX_PROXY_TEMPLATE",
    "NGINX_PHP_TEMPLATE",
    "NGINX_SSL_TEMPLATE",
    "NGINX_REDIRECT_TEMPLATE",
    "NGINX_WEBSOCKET_TEMPLATE",
    "render_nginx_template",
    # Systemd
    "SYSTEMD_SERVICE_TEMPLATE",
    "SYSTEMD_TIMER_TEMPLATE",
    "SYSTEMD_SOCKET_TEMPLATE",
    "SYSTEMD_PATH_TEMPLATE",
    "render_systemd_template",
    # Docker
    "DOCKERFILE_PYTHON_TEMPLATE",
    "DOCKERFILE_NODE_TEMPLATE",
    "DOCKER_COMPOSE_TEMPLATE",
    "render_docker_template",
]
