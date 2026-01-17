"""
Research Agent - Specialized agent for web search, documentation, and synthesis.
"""

from ai_core import AgentType, get_logger
from ai_memory import PAIMemory
from ai_messaging import RedisClient
from base_agent import BaseAgent
from base_agent.agent import AgentConfig

from .tools import (
    create_documentation,
    fetch_url,
    read_documentation,
    search_documentation,
    search_web,
    summarize_page,
    update_documentation,
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

3. **Information Synthesis**
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
        """Register research agent tools."""
        # Web tools
        self.register_tool(search_web._tool)
        self.register_tool(fetch_url._tool)
        self.register_tool(summarize_page._tool)

        # Documentation tools
        self.register_tool(search_documentation._tool)
        self.register_tool(read_documentation._tool)
        self.register_tool(create_documentation._tool)
        self.register_tool(update_documentation._tool)

        logger.info(
            "Research agent tools registered",
            count=len(self.tools),
        )
