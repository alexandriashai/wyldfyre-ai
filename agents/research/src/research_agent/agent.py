"""
Research Agent - Specialized agent for web search, documentation, and synthesis.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    # Web tools
    create_documentation,
    fetch_url,
    read_documentation,
    search_documentation,
    search_web,
    summarize_page,
    update_documentation,
    # GitHub tools
    github_search_repos,
    github_get_repo,
    github_get_readme,
    # Package registry tools
    pypi_search,
    npm_search,
    npm_get_package,
    check_package_versions,
)

logger = get_logger(__name__)

RESEARCH_AGENT_SYSTEM_PROMPT = """You are the Research Agent for AI Infrastructure, specializing in information gathering and documentation.

Your capabilities:
1. **Web Research**
   - Search the web for information
   - Fetch and extract content from URLs
   - Summarize web pages with focus on specific topics

2. **Documentation Management**
   - Search through project documentation
   - Read and extract sections from docs
   - Create and update documentation files

3. **GitHub & Repository Research**
   - Search GitHub repositories by topic/language
   - Get repository details, READMEs, and metadata
   - Explore popular and trending projects

4. **Package Registry Research**
   - Search PyPI for Python packages
   - Search NPM for JavaScript/TypeScript packages
   - Check package versions and dependencies

5. **Information Synthesis**
   - Combine information from multiple sources
   - Extract key insights and patterns
   - Provide structured summaries

Guidelines:
- Verify information from multiple sources when possible
- Cite sources clearly in your responses
- Extract relevant code examples when applicable
- Maintain consistent documentation format
- Use markdown for all documentation
- Include timestamps in documentation updates

When researching:
1. Start with broad search to understand the landscape
2. Narrow down to specific sources
3. Extract key information and code examples
4. Synthesize findings into clear summaries
5. Document learnings for future reference

Documentation Format:
- Use YAML frontmatter for metadata (title, date, tags)
- Organize with clear heading hierarchy
- Include code blocks with language tags
- Add links to original sources
- Keep sections focused and scannable

Research Ethics:
- Only access publicly available information
- Respect rate limits and terms of service
- Attribute sources properly
- Do not scrape private or protected content
"""


class ResearchAgent(BaseAgent):
    """
    Research Agent for web search, documentation, and synthesis.

    Provides tools for:
    - Web search and content extraction
    - Documentation management
    - Information synthesis
    """

    def __init__(
        self,
        redis_client: RedisClient,
        memory: PAIMemory | None = None,
    ):
        config = AgentConfig(
            name="research-agent",
            agent_type=AgentType.RESEARCH,
            permission_level=1,
            system_prompt=RESEARCH_AGENT_SYSTEM_PROMPT,
        )

        super().__init__(config, redis_client, memory)

    def get_system_prompt(self) -> str:
        """Get the research agent's system prompt."""
        return RESEARCH_AGENT_SYSTEM_PROMPT

    def register_tools(self) -> None:
        """Register research agent tools.

        Note: Shared tools (memory, collaboration, system monitoring) are
        automatically registered by BaseAgent._register_shared_tools().
        """
        # Web tools
        self.register_tool(search_web._tool)
        self.register_tool(fetch_url._tool)
        self.register_tool(summarize_page._tool)

        # Documentation tools
        self.register_tool(search_documentation._tool)
        self.register_tool(read_documentation._tool)
        self.register_tool(create_documentation._tool)
        self.register_tool(update_documentation._tool)

        # GitHub tools
        self.register_tool(github_search_repos._tool)
        self.register_tool(github_get_repo._tool)
        self.register_tool(github_get_readme._tool)

        # Package registry tools
        self.register_tool(pypi_search._tool)
        self.register_tool(npm_search._tool)
        self.register_tool(npm_get_package._tool)
        self.register_tool(check_package_versions._tool)

        logger.info(
            "Research agent tools registered",
            count=len(self.tools),
        )


async def main() -> None:
    """Main entry point for the Research Agent."""
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
    agent = ResearchAgent(redis_client, memory)
    await agent.start()

    logger.info("Research Agent is running. Press Ctrl+C to stop.")

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
