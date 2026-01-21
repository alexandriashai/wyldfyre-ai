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
    # Browser lifecycle tools
    browser_launch,
    browser_close,
    browser_close_all,
    browser_list,
    browser_context_create,
    browser_context_close,
    page_new,
    page_close,
    page_goto,
    page_reload,
    page_go_back,
    page_go_forward,
    page_get_url,
    page_get_title,
    page_get_content,
    page_wait_for_selector,
    page_wait_for_load_state,
    page_wait_for_url,
    page_evaluate,
    # Browser action tools
    element_click,
    element_dblclick,
    element_hover,
    element_fill,
    element_type,
    element_clear,
    element_press,
    element_focus,
    element_select_option,
    element_check,
    element_uncheck,
    element_drag_drop,
    element_upload_file,
    element_query,
    element_query_all,
    element_count,
    element_get_text,
    element_get_attribute,
    element_is_visible,
    element_is_enabled,
    # Browser assertion tools
    expect_element_visible,
    expect_element_hidden,
    expect_element_enabled,
    expect_element_text,
    expect_element_value,
    expect_element_attribute,
    expect_page_url,
    expect_page_title,
    expect_element_count,
    expect_element_checked,
    expect_element_focused,
    # Browser capture tools
    screenshot_page,
    screenshot_element,
    video_start,
    video_stop,
    trace_start,
    trace_stop,
    pdf_export,
    # Browser network tools
    network_intercept_enable,
    network_mock_response,
    network_mock_json,
    network_block_urls,
    network_get_requests,
    network_wait_for_response,
    network_wait_for_request,
    network_clear_interceptors,
    # Browser auth tools
    credential_store_tool,
    credential_get,
    credential_rotate,
    credential_list,
    credential_delete,
    auth_login,
    auth_logout,
    auth_save_session,
    auth_load_session,
    auth_list_sessions,
    auth_delete_session,
)
from .browser_manager import get_browser_manager, shutdown_browser_manager

logger = get_logger(__name__)

QA_AGENT_SYSTEM_PROMPT = """You are the QA Agent for AI Infrastructure, specializing in quality assurance, testing, security validation, and E2E browser automation.

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

6. **Browser Automation (E2E Testing)**
   - Launch and manage browser instances (Chromium, Firefox, WebKit)
   - Create isolated browser contexts for test isolation
   - Navigate pages, fill forms, click elements
   - Assert on element visibility, text, attributes
   - Take screenshots and record videos
   - Capture Playwright traces for debugging
   - Mock network responses and intercept requests
   - Manage encrypted test credentials
   - Save and restore authenticated sessions

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
- E2E tests for critical user flows

Browser Automation Strategy:
- Use browser contexts for test isolation
- Store credentials securely with encryption
- Save session states for faster test setup
- Capture screenshots/traces on failures
- Mock network responses for deterministic tests
- Clean up browser resources after tests

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
    QA Agent for testing, code review, security validation, and E2E browser automation.

    Provides tools for:
    - Test execution and coverage
    - Code review and quality analysis
    - Security scanning and validation
    - Browser automation and E2E testing
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
        self._browser_manager = None

    async def start(self) -> None:
        """Start the QA agent and initialize browser manager."""
        await super().start()
        # Browser manager is initialized lazily on first use

    async def stop(self) -> None:
        """Stop the QA agent and cleanup browser resources."""
        # Cleanup browser resources
        try:
            await shutdown_browser_manager()
        except Exception as e:
            logger.warning("Error shutting down browser manager", error=str(e))

        await super().stop()

    async def on_task_complete(self, request, result) -> None:
        """Clean up browser resources associated with completed task."""
        await super().on_task_complete(request, result)
        try:
            manager = get_browser_manager()
            await manager.cleanup_task_resources(request.id)
        except Exception as e:
            logger.warning("Error cleaning up task browser resources", error=str(e))

    async def on_task_error(self, request, error) -> None:
        """Clean up browser resources on task error."""
        await super().on_task_error(request, error)
        try:
            manager = get_browser_manager()
            await manager.cleanup_task_resources(request.id)
        except Exception as e:
            logger.warning("Error cleaning up task browser resources on error", error=str(e))

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

        # Browser lifecycle tools
        self.register_tool(browser_launch._tool)
        self.register_tool(browser_close._tool)
        self.register_tool(browser_close_all._tool)
        self.register_tool(browser_list._tool)
        self.register_tool(browser_context_create._tool)
        self.register_tool(browser_context_close._tool)
        self.register_tool(page_new._tool)
        self.register_tool(page_close._tool)
        self.register_tool(page_goto._tool)
        self.register_tool(page_reload._tool)
        self.register_tool(page_go_back._tool)
        self.register_tool(page_go_forward._tool)
        self.register_tool(page_get_url._tool)
        self.register_tool(page_get_title._tool)
        self.register_tool(page_get_content._tool)
        self.register_tool(page_wait_for_selector._tool)
        self.register_tool(page_wait_for_load_state._tool)
        self.register_tool(page_wait_for_url._tool)
        self.register_tool(page_evaluate._tool)

        # Browser action tools
        self.register_tool(element_click._tool)
        self.register_tool(element_dblclick._tool)
        self.register_tool(element_hover._tool)
        self.register_tool(element_fill._tool)
        self.register_tool(element_type._tool)
        self.register_tool(element_clear._tool)
        self.register_tool(element_press._tool)
        self.register_tool(element_focus._tool)
        self.register_tool(element_select_option._tool)
        self.register_tool(element_check._tool)
        self.register_tool(element_uncheck._tool)
        self.register_tool(element_drag_drop._tool)
        self.register_tool(element_upload_file._tool)
        self.register_tool(element_query._tool)
        self.register_tool(element_query_all._tool)
        self.register_tool(element_count._tool)
        self.register_tool(element_get_text._tool)
        self.register_tool(element_get_attribute._tool)
        self.register_tool(element_is_visible._tool)
        self.register_tool(element_is_enabled._tool)

        # Browser assertion tools
        self.register_tool(expect_element_visible._tool)
        self.register_tool(expect_element_hidden._tool)
        self.register_tool(expect_element_enabled._tool)
        self.register_tool(expect_element_text._tool)
        self.register_tool(expect_element_value._tool)
        self.register_tool(expect_element_attribute._tool)
        self.register_tool(expect_page_url._tool)
        self.register_tool(expect_page_title._tool)
        self.register_tool(expect_element_count._tool)
        self.register_tool(expect_element_checked._tool)
        self.register_tool(expect_element_focused._tool)

        # Browser capture tools
        self.register_tool(screenshot_page._tool)
        self.register_tool(screenshot_element._tool)
        self.register_tool(video_start._tool)
        self.register_tool(video_stop._tool)
        self.register_tool(trace_start._tool)
        self.register_tool(trace_stop._tool)
        self.register_tool(pdf_export._tool)

        # Browser network tools
        self.register_tool(network_intercept_enable._tool)
        self.register_tool(network_mock_response._tool)
        self.register_tool(network_mock_json._tool)
        self.register_tool(network_block_urls._tool)
        self.register_tool(network_get_requests._tool)
        self.register_tool(network_wait_for_response._tool)
        self.register_tool(network_wait_for_request._tool)
        self.register_tool(network_clear_interceptors._tool)

        # Browser auth tools
        self.register_tool(credential_store_tool._tool)
        self.register_tool(credential_get._tool)
        self.register_tool(credential_rotate._tool)
        self.register_tool(credential_list._tool)
        self.register_tool(credential_delete._tool)
        self.register_tool(auth_login._tool)
        self.register_tool(auth_logout._tool)
        self.register_tool(auth_save_session._tool)
        self.register_tool(auth_load_session._tool)
        self.register_tool(auth_list_sessions._tool)
        self.register_tool(auth_delete_session._tool)

        logger.info(
            "QA agent tools registered",
            count=len(self.tools),
        )


async def main() -> None:
    """Main entry point for the QA Agent."""
    import asyncio
    from ai_core import get_settings
    from ai_messaging import RedisClient
    from ai_memory import PAIMemory

    settings = get_settings()

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


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
