"""
Infra Agent - Specialized agent for Docker, Nginx, and SSL operations.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    check_certificate,
    docker_compose_down,
    docker_compose_logs,
    docker_compose_ps,
    docker_compose_restart,
    docker_compose_up,
    docker_exec,
    docker_inspect,
    docker_logs,
    docker_ps,
    list_certificates,
    nginx_reload,
    nginx_status,
    nginx_test_config,
    renew_certificate,
    request_certificate,
)

logger = get_logger(__name__)

INFRA_AGENT_SYSTEM_PROMPT = """You are the Infra Agent for AI Infrastructure, specializing in infrastructure management.

Your capabilities:
1. **Docker Operations**
   - List and inspect containers
   - View container logs
   - Execute commands in containers
   - Manage docker-compose services (up, down, restart)

2. **Nginx Management**
   - Check Nginx service status
   - Test configuration syntax
   - Reload configuration gracefully

3. **SSL/TLS Certificates**
   - List managed certificates
   - Check certificate expiry and validity
   - Request new certificates via Let's Encrypt
   - Renew expiring certificates

Guidelines:
- Always test Nginx configuration before reloading
- Check certificate expiry dates regularly
- Use docker-compose for service orchestration
- Verify container health before operations
- Log all infrastructure changes
- Require confirmation for destructive operations

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
"""


class InfraAgent(BaseAgent):
    """
    Infra Agent for Docker, Nginx, and SSL operations.

    Provides tools for:
    - Docker container and compose management
    - Nginx configuration and status
    - SSL certificate lifecycle management
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

        # Nginx tools
        self.register_tool(nginx_status._tool)
        self.register_tool(nginx_test_config._tool)
        self.register_tool(nginx_reload._tool)

        # SSL tools
        self.register_tool(list_certificates._tool)
        self.register_tool(check_certificate._tool)
        self.register_tool(request_certificate._tool)
        self.register_tool(renew_certificate._tool)

        logger.info(
            "Infra agent tools registered",
            count=len(self.tools),
        )
