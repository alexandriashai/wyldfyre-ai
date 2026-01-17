"""
QA Agent - Specialized agent for testing, code review, and security validation.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    analyze_code_quality,
    check_dependencies,
    check_secrets,
    list_tests,
    review_changes,
    run_coverage,
    run_lint,
    run_tests,
    scan_dependencies,
    validate_permissions,
)

logger = get_logger(__name__)

QA_AGENT_SYSTEM_PROMPT = """You are the QA Agent for AI Infrastructure, specializing in quality assurance, testing, and security validation.

Your capabilities:
1. **Testing**
   - Run pytest tests with various options
   - List available tests
   - Generate coverage reports
   - Run linting tools (ruff, mypy)

2. **Code Review**
   - Review git changes for common issues
   - Analyze code quality metrics
   - Check dependency configurations

3. **Security Validation**
   - Scan for hardcoded secrets and credentials
   - Check for vulnerable dependencies
   - Validate file permissions

Guidelines:
- Always run tests before approving changes
- Check for security issues in every code review
- Provide actionable feedback on issues found
- Prioritize issues by severity
- Track test coverage trends
- Ensure no secrets are committed

When reviewing code:
1. Check for security vulnerabilities first
2. Run linting and type checking
3. Review test coverage
4. Analyze code quality metrics
5. Provide summary with prioritized issues

Testing Strategy:
- Unit tests for all business logic
- Integration tests for service communication
- Security tests for authentication/authorization
- Performance tests for critical paths

Security Checklist:
- No hardcoded credentials
- Dependencies are up to date
- Proper file permissions
- Input validation present
- Error messages don't leak info
- Authentication on all endpoints
"""


class QAAgent(BaseAgent):
    """
    QA Agent for testing, code review, and security validation.

    Provides tools for:
    - Test execution and coverage
    - Code review and quality analysis
    - Security scanning and validation
    """

    def __init__(
        self,
        redis_client: RedisClient,
        memory: PAIMemory | None = None,
    ):
        config = AgentConfig(
            name="qa-agent",
            agent_type=AgentType.QA,
            permission_level=1,
            system_prompt=QA_AGENT_SYSTEM_PROMPT,
        )

        super().__init__(config, redis_client, memory)

    def get_system_prompt(self) -> str:
        """Get the QA agent's system prompt."""
        return QA_AGENT_SYSTEM_PROMPT

    def register_tools(self) -> None:
        """Register QA agent tools."""
        # Test tools
        self.register_tool(run_tests._tool)
        self.register_tool(list_tests._tool)
        self.register_tool(run_coverage._tool)
        self.register_tool(run_lint._tool)

        # Review tools
        self.register_tool(review_changes._tool)
        self.register_tool(analyze_code_quality._tool)
        self.register_tool(check_dependencies._tool)

        # Security tools
        self.register_tool(check_secrets._tool)
        self.register_tool(scan_dependencies._tool)
        self.register_tool(validate_permissions._tool)

        logger.info(
            "QA agent tools registered",
            count=len(self.tools),
        )
