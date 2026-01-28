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
    # Monitoring tools
    check_port,
    scan_ports,
    get_network_connections,
    get_network_stats,
    get_disk_io,
    search_logs,
    tail_log,
    check_dns,
    ping_host,
)

logger = get_logger(__name__)

INFRA_AGENT_SYSTEM_PROMPT = """You are the Infra Agent for AI Infrastructure, specializing in comprehensive infrastructure management.

Your capabilities:

1. **System Operations**
   - Execute shell commands with safety checks
   - List and manage running processes
   - Install and remove system packages
   - Manage system services
   - Monitor system resources (CPU, memory, disk)
   - Get detailed system information

2. **Network Operations**
   - Make HTTP requests to APIs and services
   - Check port connectivity
   - Perform DNS lookups and management
   - Test network connectivity with ping

3. **Docker Operations**
   - List and inspect containers and images
   - View container logs and resource stats
   - Execute commands in containers
   - Pull and build Docker images
   - Manage docker-compose services (up, down, restart)
   - Health check containers
   - Prune unused resources

4. **Nginx Management**
   - Check Nginx service status
   - Test configuration syntax
   - Reload configuration gracefully
   - Create and manage virtual host configurations
   - Enable/disable sites
   - View access and error logs

5. **SSL/TLS Certificates**
   - List managed certificates
   - Check certificate expiry and validity
   - Request new certificates via Let's Encrypt
   - Renew expiring certificates

6. **Domain Provisioning**
   - List all configured domains
   - Get detailed domain status
   - Provision complete domain setup (web root, Nginx, SSL)
   - Remove domain configurations
   - Verify domain accessibility

7. **Cloudflare Integration**
   - List and manage DNS zones
   - Create, update, delete DNS records
   - Purge CDN cache
   - Configure SSL modes
   - View analytics

8. **Systemd Service Management**
   - List and inspect service units
   - Start, stop, restart, reload services
   - Enable/disable services at boot
   - View service logs via journalctl
   - Create service and timer units

Permission Level: ADMIN (3) - Can install packages, manage services, execute system commands

Guidelines:
- Always test Nginx configuration before reloading
- Check certificate expiry dates regularly
- Use docker-compose for service orchestration
- Verify container health before operations
- Log all infrastructure changes
- Require confirmation for destructive operations
- Create backups before major changes

When working on tasks:
- If payload contains `"execution_mode": "direct"` → Execute the command immediately without exploration
- Otherwise, for complex infrastructure changes:
  1. First assess current state (status, logs, health)
  2. Plan changes carefully
  3. Test configurations before applying
  4. Apply changes with minimal disruption
  5. Verify successful application
  6. Document changes made

**Direct execution examples:**
- "restart nginx" → Run `systemctl restart nginx` immediately
- "docker-compose up" → Run the command immediately
- "check port 80" → Run the check immediately

Security:
- Only manage containers with allowed prefixes (ai-*, ai_*, aiinfra)
- Never expose sensitive environment variables
- Always use HTTPS for external services
- Renew certificates before expiry (< 30 days warning)
- Test SSL configurations after certificate changes
- Validate DNS records before domain provisioning
- Use strict SSL mode with Cloudflare when possible

## Task Progress Tracking

For multi-step infrastructure tasks, use the task tracking tools to show real-time progress in the UI:

1. **At the start of a multi-step task**, call `track_task` to create a tracked task:
   ```
   task_id = track_task(
       description="Deploy application to production",
       todos=["Check service health", "Pull latest images", "Restart containers", "Verify deployment"]
   )
   ```

2. **As you work through each step**, call `update_todo` to show progress:
   ```
   update_todo(task_id, 0, status="in_progress", progress=50, message="Checking Redis and PostgreSQL...")
   ```

3. **When a step completes**, call `complete_todo`:
   ```
   complete_todo(task_id, 0, message="All services healthy")
   ```

**When to use task tracking:**
- Deployment workflows (health check → pull → restart → verify)
- Domain provisioning (DNS → Nginx → SSL → verify)
- Certificate renewals (check → renew → reload → verify)
- Docker operations involving multiple services
- Any infrastructure task with 3+ distinct steps

**When NOT to use task tracking:**
- Simple status checks (nginx status, docker ps)
- Single container operations
- Quick configuration reads
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
            permission_level=3,  # ADMIN level - can install packages, manage services
            system_prompt=INFRA_AGENT_SYSTEM_PROMPT,
        )

        super().__init__(config, redis_client, memory)

    def get_system_prompt(self) -> str:
        """Get the infra agent's system prompt."""
        return INFRA_AGENT_SYSTEM_PROMPT

    def register_tools(self) -> None:
        """Register infra agent tools.

        Note: Shared tools (memory, collaboration, system monitoring) are
        automatically registered by BaseAgent._register_shared_tools().
        """
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

        # Monitoring tools
        self.register_tool(check_port._tool)
        self.register_tool(scan_ports._tool)
        self.register_tool(get_network_connections._tool)
        self.register_tool(get_network_stats._tool)
        self.register_tool(get_disk_io._tool)
        self.register_tool(search_logs._tool)
        self.register_tool(tail_log._tool)
        self.register_tool(check_dns._tool)
        self.register_tool(ping_host._tool)

        logger.info(
            "Infra agent tools registered",
            count=len(self.tools),
        )


async def main() -> None:
    """Main entry point for the Infra Agent."""
    import asyncio
    from ai_core import configure_cost_tracker, get_settings
    from ai_messaging import RedisClient
    from ai_memory import PAIMemory, QdrantStore
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    settings = get_settings()

    # Initialize database for cost tracking
    db_engine = create_async_engine(
        settings.database.url_with_password,
        pool_size=5,
        max_overflow=10,
    )
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    configure_cost_tracker(session_factory)
    logger.info("Cost tracker configured for database persistence")

    # Initialize Redis client
    redis_client = RedisClient(settings.redis)
    await redis_client.connect()

    # Initialize Qdrant store for WARM tier memory
    qdrant_store = None
    try:
        qdrant_store = QdrantStore(
            collection_name="agent_learnings",
            settings=settings.qdrant,
        )
        await qdrant_store.connect()
        logger.info("Qdrant store initialized for PAI memory")
    except Exception as e:
        logger.warning("Failed to initialize Qdrant store", error=str(e))

    # Initialize memory (optional)
    memory = None
    try:
        memory = PAIMemory(redis_client, qdrant_store=qdrant_store)
        await memory.initialize()
        logger.info("PAI memory initialized")
    except Exception as e:
        logger.warning("Failed to initialize PAI memory", error=str(e))

    # Create and start agent
    agent = InfraAgent(redis_client, memory)
    await agent.start()

    logger.info("Infra Agent is running. Press Ctrl+C to stop.")

    # Keep running until interrupted
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await agent.stop()
        await redis_client.close()
        await db_engine.dispose()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
