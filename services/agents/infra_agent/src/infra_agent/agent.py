"""
Infra Agent - Specialized agent for infrastructure management.

Provides comprehensive infrastructure management including:
- Docker container and image management
- Nginx virtual host configuration
- SSL/TLS certificate lifecycle
- Domain provisioning workflow
- Cloudflare DNS and CDN management
- Systemd service management
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    # Docker tools
    docker_build,
    docker_compose_down,
    docker_compose_logs,
    docker_compose_ps,
    docker_compose_restart,
    docker_compose_up,
    docker_exec,
    docker_health_check,
    docker_images,
    docker_inspect,
    docker_logs,
    docker_ps,
    docker_pull,
    docker_stats,
    docker_system_prune,
    # Nginx tools
    nginx_create_site,
    nginx_disable_site,
    nginx_enable_site,
    nginx_read_site_config,
    nginx_reload,
    nginx_status,
    nginx_test_config,
    nginx_view_logs,
    # SSL tools
    check_certificate,
    list_certificates,
    renew_certificate,
    request_certificate,
    # Domain tools
    get_domain_status,
    list_domains,
    provision_domain,
    remove_domain,
    verify_domain,
    # Cloudflare tools
    cf_create_dns_record,
    cf_delete_dns_record,
    cf_get_analytics,
    cf_get_zone,
    cf_list_dns_records,
    cf_list_zones,
    cf_purge_cache,
    cf_set_ssl_mode,
    cf_update_dns_record,
    # Systemd tools
    systemd_create_service,
    systemd_create_timer,
    systemd_daemon_reload,
    systemd_disable,
    systemd_enable,
    systemd_get_status,
    systemd_list_timers,
    systemd_list_units,
    systemd_read_unit_file,
    systemd_reload,
    systemd_restart,
    systemd_start,
    systemd_stop,
    systemd_view_logs,
)

logger = get_logger(__name__)

INFRA_AGENT_SYSTEM_PROMPT = """You are the Infra Agent for AI Infrastructure, specializing in comprehensive infrastructure management.

Your capabilities:

1. **Docker Operations**
   - List and inspect containers and images
   - View container logs and resource stats
   - Execute commands in containers
   - Pull and build Docker images
   - Manage docker-compose services (up, down, restart)
   - Health check containers
   - Prune unused resources

2. **Nginx Management**
   - Check Nginx service status
   - Test configuration syntax
   - Reload configuration gracefully
   - Create and manage virtual host configurations
   - Enable/disable sites
   - View access and error logs

3. **SSL/TLS Certificates**
   - List managed certificates
   - Check certificate expiry and validity
   - Request new certificates via Let's Encrypt
   - Renew expiring certificates

4. **Domain Provisioning**
   - List all configured domains
   - Get detailed domain status
   - Provision complete domain setup (web root, Nginx, SSL)
   - Remove domain configurations
   - Verify domain accessibility

5. **Cloudflare Integration**
   - List and manage DNS zones
   - Create, update, delete DNS records
   - Purge CDN cache
   - Configure SSL modes
   - View analytics

6. **Systemd Service Management**
   - List and inspect service units
   - Start, stop, restart, reload services
   - Enable/disable services at boot
   - View service logs via journalctl
   - Create service and timer units

Guidelines:
- Always test Nginx configuration before reloading
- Check certificate expiry dates regularly
- Use docker-compose for service orchestration
- Verify container health before operations
- Log all infrastructure changes
- Require confirmation for destructive operations
- Create backups before major changes

When working on tasks:
1. First assess current state (status, logs, health)
2. Plan changes carefully
3. Test configurations before applying
4. Apply changes with minimal disruption
5. Verify successful application
6. Document changes made

Security:
- Only manage containers with allowed prefixes (ai-*, ai_*, aiinfra)
- Never expose sensitive environment variables
- Always use HTTPS for external services
- Renew certificates before expiry (< 30 days warning)
- Test SSL configurations after certificate changes
- Validate DNS records before domain provisioning
- Use strict SSL mode with Cloudflare when possible
"""


class InfraAgent(BaseAgent):
    """
    Infra Agent for comprehensive infrastructure operations.

    Provides tools for:
    - Docker container, image, and compose management
    - Nginx configuration, virtual hosts, and logging
    - SSL certificate lifecycle management
    - Complete domain provisioning workflow
    - Cloudflare DNS and CDN management
    - Systemd service and timer management
    """

    def __init__(
        self,
        redis_client: RedisClient,
        memory: PAIMemory | None = None,
    ):
        config = AgentConfig(
            name="infra-agent",
            agent_type=AgentType.INFRA,
            permission_level=2,
            system_prompt=INFRA_AGENT_SYSTEM_PROMPT,
        )

        super().__init__(config, redis_client, memory)

    def get_system_prompt(self) -> str:
        """Get the infra agent's system prompt."""
        return INFRA_AGENT_SYSTEM_PROMPT

    def register_tools(self) -> None:
        """Register infra agent tools."""
        # Docker tools
        self.register_tool(docker_ps._tool)
        self.register_tool(docker_logs._tool)
        self.register_tool(docker_exec._tool)
        self.register_tool(docker_inspect._tool)
        self.register_tool(docker_compose_ps._tool)
        self.register_tool(docker_compose_up._tool)
        self.register_tool(docker_compose_down._tool)
        self.register_tool(docker_compose_restart._tool)
        self.register_tool(docker_compose_logs._tool)
        self.register_tool(docker_images._tool)
        self.register_tool(docker_pull._tool)
        self.register_tool(docker_build._tool)
        self.register_tool(docker_stats._tool)
        self.register_tool(docker_health_check._tool)
        self.register_tool(docker_system_prune._tool)

        # Nginx tools
        self.register_tool(nginx_status._tool)
        self.register_tool(nginx_test_config._tool)
        self.register_tool(nginx_reload._tool)
        self.register_tool(nginx_read_site_config._tool)
        self.register_tool(nginx_create_site._tool)
        self.register_tool(nginx_enable_site._tool)
        self.register_tool(nginx_disable_site._tool)
        self.register_tool(nginx_view_logs._tool)

        # SSL tools
        self.register_tool(list_certificates._tool)
        self.register_tool(check_certificate._tool)
        self.register_tool(request_certificate._tool)
        self.register_tool(renew_certificate._tool)

        # Domain tools
        self.register_tool(list_domains._tool)
        self.register_tool(get_domain_status._tool)
        self.register_tool(provision_domain._tool)
        self.register_tool(remove_domain._tool)
        self.register_tool(verify_domain._tool)

        # Cloudflare tools
        self.register_tool(cf_list_zones._tool)
        self.register_tool(cf_get_zone._tool)
        self.register_tool(cf_list_dns_records._tool)
        self.register_tool(cf_create_dns_record._tool)
        self.register_tool(cf_update_dns_record._tool)
        self.register_tool(cf_delete_dns_record._tool)
        self.register_tool(cf_purge_cache._tool)
        self.register_tool(cf_set_ssl_mode._tool)
        self.register_tool(cf_get_analytics._tool)

        # Systemd tools
        self.register_tool(systemd_list_units._tool)
        self.register_tool(systemd_get_status._tool)
        self.register_tool(systemd_start._tool)
        self.register_tool(systemd_stop._tool)
        self.register_tool(systemd_restart._tool)
        self.register_tool(systemd_reload._tool)
        self.register_tool(systemd_enable._tool)
        self.register_tool(systemd_disable._tool)
        self.register_tool(systemd_daemon_reload._tool)
        self.register_tool(systemd_view_logs._tool)
        self.register_tool(systemd_read_unit_file._tool)
        self.register_tool(systemd_create_service._tool)
        self.register_tool(systemd_create_timer._tool)
        self.register_tool(systemd_list_timers._tool)

        logger.info(
            "Infra agent tools registered",
            count=len(self.tools),
        )
