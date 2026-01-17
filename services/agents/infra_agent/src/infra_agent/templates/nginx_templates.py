"""
Nginx configuration templates.
"""

from string import Template


# Basic static site template
NGINX_STATIC_TEMPLATE = Template("""server {
    listen 80;
    listen [::]:80;
    server_name ${server_name};

    root ${root};
    index index.html index.htm;

    location / {
        try_files $$uri $$uri/ =404;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Logging
    access_log /var/log/nginx/${domain}.access.log;
    error_log /var/log/nginx/${domain}.error.log;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml;
}
""")


# Reverse proxy template
NGINX_PROXY_TEMPLATE = Template("""server {
    listen 80;
    listen [::]:80;
    server_name ${server_name};

    location / {
        proxy_pass ${upstream_url};
        proxy_http_version 1.1;
        proxy_set_header Host $$host;
        proxy_set_header X-Real-IP $$remote_addr;
        proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $$scheme;
        proxy_set_header X-Forwarded-Host $$host;
        proxy_set_header X-Forwarded-Port $$server_port;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 16k;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/${domain}.access.log;
    error_log /var/log/nginx/${domain}.error.log;
}
""")


# PHP-FPM site template
NGINX_PHP_TEMPLATE = Template("""server {
    listen 80;
    listen [::]:80;
    server_name ${server_name};

    root ${root};
    index index.php index.html index.htm;

    location / {
        try_files $$uri $$uri/ /index.php?$$query_string;
    }

    location ~ \\.php$$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass ${php_socket};
        fastcgi_param SCRIPT_FILENAME $$realpath_root$$fastcgi_script_name;
        include fastcgi_params;

        # Timeouts
        fastcgi_connect_timeout 60s;
        fastcgi_send_timeout 60s;
        fastcgi_read_timeout 60s;
    }

    location ~ /\\.ht {
        deny all;
    }

    location ~ /\\.git {
        deny all;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/${domain}.access.log;
    error_log /var/log/nginx/${domain}.error.log;

    # File upload limits
    client_max_body_size ${max_body_size};
}
""")


# SSL/HTTPS template
NGINX_SSL_TEMPLATE = Template("""# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name ${server_name};
    return 301 https://$$server_name$$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${server_name};

    # SSL certificates
    ssl_certificate ${ssl_cert};
    ssl_certificate_key ${ssl_key};

    # SSL configuration
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    # OCSP stapling
    ssl_stapling on;
    ssl_stapling_verify on;

    root ${root};
    index index.html index.htm;

    location / {
        try_files $$uri $$uri/ =404;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Logging
    access_log /var/log/nginx/${domain}.access.log;
    error_log /var/log/nginx/${domain}.error.log;
}
""")


# HTTP redirect template (domain redirect)
NGINX_REDIRECT_TEMPLATE = Template("""server {
    listen 80;
    listen [::]:80;
    server_name ${server_name};

    return ${redirect_code} ${redirect_url};

    access_log /var/log/nginx/${domain}.access.log;
}
""")


# WebSocket proxy template
NGINX_WEBSOCKET_TEMPLATE = Template("""server {
    listen 80;
    listen [::]:80;
    server_name ${server_name};

    location / {
        proxy_pass ${upstream_url};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $$host;
        proxy_set_header X-Real-IP $$remote_addr;
        proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $$scheme;

        # WebSocket specific
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 60s;

        # Buffer settings for WebSocket
        proxy_buffering off;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Logging
    access_log /var/log/nginx/${domain}.access.log;
    error_log /var/log/nginx/${domain}.error.log;
}
""")


def render_nginx_template(
    template_name: str,
    **kwargs,
) -> str:
    """
    Render an Nginx template with the given parameters.

    Args:
        template_name: Name of the template to render
        **kwargs: Template variables

    Returns:
        Rendered template string

    Example:
        config = render_nginx_template(
            "static",
            server_name="example.com",
            domain="example.com",
            root="/var/www/example.com",
        )
    """
    templates = {
        "static": NGINX_STATIC_TEMPLATE,
        "proxy": NGINX_PROXY_TEMPLATE,
        "php": NGINX_PHP_TEMPLATE,
        "ssl": NGINX_SSL_TEMPLATE,
        "redirect": NGINX_REDIRECT_TEMPLATE,
        "websocket": NGINX_WEBSOCKET_TEMPLATE,
    }

    template = templates.get(template_name)
    if not template:
        raise ValueError(f"Unknown template: {template_name}")

    # Set defaults
    defaults = {
        "php_socket": "unix:/var/run/php/php-fpm.sock",
        "max_body_size": "64M",
        "redirect_code": "301",
    }

    for key, value in defaults.items():
        kwargs.setdefault(key, value)

    # Ensure domain is set if server_name is provided
    if "server_name" in kwargs and "domain" not in kwargs:
        # Use first domain if multiple are provided
        kwargs["domain"] = kwargs["server_name"].split()[0]

    return template.safe_substitute(**kwargs)
