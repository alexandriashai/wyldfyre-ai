"""
Code Agent - Specialized agent for code and git operations.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    delete_file,
    git_add,
    git_branch,
    git_checkout,
    git_commit,
    git_diff,
    git_log,
    git_pull,
    git_push,
    git_status,
    list_directory,
    read_file,
    search_files,
    write_file,
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
   - Review code structure
   - Identify patterns and issues
   - Suggest improvements

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
        """Register code agent tools."""
        # File tools
        self.register_tool(read_file._tool)
        self.register_tool(write_file._tool)
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

        logger.info(
            "Code agent tools registered",
            count=len(self.tools),
        )
