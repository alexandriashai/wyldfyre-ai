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

        logger.info(
            "Data agent tools registered",
            count=len(self.tools),
        )
