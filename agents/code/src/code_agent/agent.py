"""
Code Agent - Specialized agent for code and git operations.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    # File tools
    delete_file,
    edit_file,
    list_directory,
    read_file,
    search_files,
    write_file,
    # Git tools
    git_add,
    git_branch,
    git_checkout,
    git_commit,
    git_diff,
    git_log,
    git_pull,
    git_push,
    git_status,
    # Code analysis tools
    code_search,
    find_definition,
    find_references,
    get_python_imports,
    get_package_dependencies,
    count_lines,
)

logger = get_logger(__name__)

CODE_AGENT_SYSTEM_PROMPT = """You are the Code Agent for AI Infrastructure, specializing in code and git operations.

Your capabilities:
1. **File Operations**
   - Read, write, and search files
   - Navigate directory structures
   - Manage file organization

2. **Git Operations**
   - Check repository status
   - View diffs and logs
   - Stage, commit, and push changes
   - Manage branches

3. **Code Analysis**
   - Search code with ripgrep patterns
   - Find symbol definitions and references
   - Extract and analyze imports/dependencies
   - Count lines of code by language
   - Review code structure and patterns

Guidelines:
- Always check file existence before operations
- Use git status before making commits
- Write clear, descriptive commit messages
- Follow the repository's coding conventions
- Report errors clearly with context
- Never delete files without explicit confirmation

When working on tasks:
1. First understand the current state (git status, read files)
2. Plan your changes
3. Execute changes incrementally
4. Verify results
5. Commit with clear messages
"""


class CodeAgent(BaseAgent):
    """
    Code Agent for file and git operations.

    Provides tools for:
    - File read/write/search
    - Git operations (status, diff, commit, push, etc.)
    - Code analysis
    """

    def __init__(
        self,
        redis_client: RedisClient,
        memory: PAIMemory | None = None,
    ):
        config = AgentConfig(
            name="code-agent",
            agent_type=AgentType.CODE,
            permission_level=2,
            system_prompt=CODE_AGENT_SYSTEM_PROMPT,
        )

        super().__init__(config, redis_client, memory)

    def get_system_prompt(self) -> str:
        """Get the code agent's system prompt."""
        return CODE_AGENT_SYSTEM_PROMPT

    def register_tools(self) -> None:
        """Register code agent tools.

        Note: Shared tools (memory, collaboration, system monitoring) are
        automatically registered by BaseAgent._register_shared_tools().
        """
        # File tools
        self.register_tool(read_file._tool)
        self.register_tool(write_file._tool)
        self.register_tool(edit_file._tool)
        self.register_tool(list_directory._tool)
        self.register_tool(search_files._tool)
        self.register_tool(delete_file._tool)

        # Git tools
        self.register_tool(git_status._tool)
        self.register_tool(git_diff._tool)
        self.register_tool(git_log._tool)
        self.register_tool(git_add._tool)
        self.register_tool(git_commit._tool)
        self.register_tool(git_branch._tool)
        self.register_tool(git_checkout._tool)
        self.register_tool(git_pull._tool)
        self.register_tool(git_push._tool)

        # Code analysis tools
        self.register_tool(code_search._tool)
        self.register_tool(find_definition._tool)
        self.register_tool(find_references._tool)
        self.register_tool(get_python_imports._tool)
        self.register_tool(get_package_dependencies._tool)
        self.register_tool(count_lines._tool)

        logger.info(
            "Code agent tools registered",
            count=len(self.tools),
        )


async def main() -> None:
    """Main entry point for the Code Agent."""
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
            collection_name="pai_learnings",
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
    agent = CodeAgent(redis_client, memory)
    await agent.start()

    logger.info("Code Agent is running. Press Ctrl+C to stop.")

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
