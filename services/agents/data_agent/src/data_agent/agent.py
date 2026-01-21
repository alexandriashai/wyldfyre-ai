"""
Data Agent - Specialized agent for SQL, ETL, and backup operations.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    create_backup,
    execute_query,
    export_to_csv,
    export_to_json,
    get_schema,
    import_from_csv,
    list_backups,
    list_tables,
    restore_backup,
    transform_data,
    # Qdrant tools
    qdrant_create_collection,
    qdrant_delete_collection,
    qdrant_describe_collection,
    qdrant_batch_upsert,
    qdrant_advanced_search,
    qdrant_delete_points,
    qdrant_scroll_points,
)

logger = get_logger(__name__)

DATA_AGENT_SYSTEM_PROMPT = """You are the Data Agent for AI Infrastructure, specializing in database and data operations.

Your capabilities:
1. **SQL Operations**
   - Execute read-only SQL queries
   - List and inspect table schemas
   - Analyze database structure

2. **ETL Operations**
   - Export data to CSV and JSON formats
   - Import and preview CSV data
   - Transform data with filters, mappings, and selections

3. **Backup Operations**
   - Create database backups (custom, plain SQL, or directory format)
   - List available backups
   - Restore backups (with confirmation)

4. **Vector Database (Qdrant) Operations**
   - Create and manage collections
   - Batch insert embeddings
   - Advanced semantic search with filters
   - Scroll and inspect stored vectors
   - Delete points by ID or filter

Guidelines:
- Only execute read-only queries (SELECT, WITH, EXPLAIN)
- Always verify table existence before querying
- Use appropriate row limits to prevent memory issues
- Create backups before any restore operations
- Report query results in a clear, structured format
- Handle large datasets carefully with pagination

When working on tasks:
1. First understand the data structure (list tables, get schema)
2. Plan your queries or operations
3. Execute with appropriate limits
4. Verify results before reporting
5. Clean up temporary files when done

Security:
- Never execute DROP, DELETE, UPDATE, or INSERT directly
- Always validate file paths within the workspace
- Require confirmation for destructive operations
- Log all operations for audit trails
"""


class DataAgent(BaseAgent):
    """
    Data Agent for SQL, ETL, and backup operations.

    Provides tools for:
    - SQL query execution (read-only)
    - Schema inspection
    - Data export (CSV, JSON)
    - Data transformation
    - Database backups and restores
    """

    def __init__(
        self,
        redis_client: RedisClient,
        memory: PAIMemory | None = None,
    ):
        config = AgentConfig(
            name="data-agent",
            agent_type=AgentType.DATA,
            permission_level=2,
            system_prompt=DATA_AGENT_SYSTEM_PROMPT,
        )

        super().__init__(config, redis_client, memory)

    def get_system_prompt(self) -> str:
        """Get the data agent's system prompt."""
        return DATA_AGENT_SYSTEM_PROMPT

    def register_tools(self) -> None:
        """Register data agent tools."""
        # SQL tools
        self.register_tool(execute_query._tool)
        self.register_tool(list_tables._tool)
        self.register_tool(get_schema._tool)

        # ETL tools
        self.register_tool(export_to_csv._tool)
        self.register_tool(export_to_json._tool)
        self.register_tool(import_from_csv._tool)
        self.register_tool(transform_data._tool)

        # Backup tools
        self.register_tool(create_backup._tool)
        self.register_tool(list_backups._tool)
        self.register_tool(restore_backup._tool)

        # Qdrant vector database tools
        self.register_tool(qdrant_create_collection._tool)
        self.register_tool(qdrant_delete_collection._tool)
        self.register_tool(qdrant_describe_collection._tool)
        self.register_tool(qdrant_batch_upsert._tool)
        self.register_tool(qdrant_advanced_search._tool)
        self.register_tool(qdrant_delete_points._tool)
        self.register_tool(qdrant_scroll_points._tool)

        logger.info(
            "Data agent tools registered",
            count=len(self.tools),
        )


async def main() -> None:
    """Main entry point for the Data Agent."""
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
    agent = DataAgent(redis_client, memory)
    await agent.start()

    logger.info("Data Agent is running. Press Ctrl+C to stop.")

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
