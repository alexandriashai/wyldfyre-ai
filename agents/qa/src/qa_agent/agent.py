"""
QA Agent - Specialized agent for testing, code review, and security validation.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    # Test tools
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
    # Type checking tools
    run_mypy,
    check_type_coverage,
    run_ruff,
    # API test tools
    test_api_endpoint,
    test_api_batch,
    validate_json_schema,
    measure_api_performance,
    check_api_health,
)

logger = get_logger(__name__)

QA_AGENT_SYSTEM_PROMPT = """You are the QA Agent for AI Infrastructure, specializing in quality assurance, testing, and security validation.

Your capabilities:
1. **Testing**
   - Run pytest tests with various options
   - List available tests
   - Generate coverage reports
   - Run linting tools

2. **Type Checking & Linting**
   - Run mypy for static type analysis
   - Check type annotation coverage
   - Run ruff for fast Python linting
   - Automatically fix linting issues

3. **API Testing**
   - Test individual API endpoints
   - Run batch API tests
   - Measure API performance (response times, throughput)
   - Validate JSON responses against schemas
   - Check health of multiple endpoints

4. **Code Review**
   - Review git changes for common issues
   - Analyze code quality metrics
   - Check dependency configurations

5. **Security Validation**
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
        """Register QA agent tools.

        Note: Shared tools (memory, collaboration, system monitoring) are
        automatically registered by BaseAgent._register_shared_tools().
        """
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

        # Type checking tools
        self.register_tool(run_mypy._tool)
        self.register_tool(check_type_coverage._tool)
        self.register_tool(run_ruff._tool)

        # API test tools
        self.register_tool(test_api_endpoint._tool)
        self.register_tool(test_api_batch._tool)
        self.register_tool(validate_json_schema._tool)
        self.register_tool(measure_api_performance._tool)
        self.register_tool(check_api_health._tool)

        logger.info(
            "QA agent tools registered",
            count=len(self.tools),
        )


async def main() -> None:
    """Main entry point for the QA Agent."""
    import asyncio
    from ai_core import configure_cost_tracker, get_settings
    from ai_messaging import RedisClient
    from ai_memory import PAIMemory
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

    # Initialize memory (optional)
    memory = None
    try:
        memory = PAIMemory(redis_client)
    except Exception as e:
        logger.warning("Failed to initialize PAI memory", error=str(e))

    # Create and start agent
    agent = QAAgent(redis_client, memory)
    await agent.start()

    logger.info("QA Agent is running. Press Ctrl+C to stop.")

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
