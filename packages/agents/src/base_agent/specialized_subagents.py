"""
Specialized subagent classes for Explore and Plan capabilities.

These subagents provide Claude Code-style exploration and planning
capabilities as tools within existing agents.
"""

from typing import Any

from ai_core import LLMClient, get_logger

from .subagent import ActionCallback, Subagent, SubagentResult
from .tools import ToolRegistry

logger = get_logger(__name__)

# Read-only tools that ExploreSubagent can use
EXPLORE_TOOLS = frozenset([
    "read_file",
    "list_directory",
    "search_files",
    "code_search",
    "find_definition",
    "find_references",
    "get_package_dependencies",
    "get_python_imports",
])

# Tools available to PlanSubagent (explore + dependency analysis)
PLAN_TOOLS = EXPLORE_TOOLS | frozenset([
    "search_memory",  # Can search existing knowledge
])

# Thoroughness level to iteration mapping
THOROUGHNESS_MAP = {
    "quick": 3,
    "medium": 7,
    "thorough": 12,
}


class ExploreSubagent(Subagent):
    """
    Fast codebase exploration subagent.

    Specialized for quickly searching and understanding code:
    - Pattern matching with glob and grep
    - Reading specific files
    - Mapping dependencies and relationships
    - Reporting structured findings
    """

    def __init__(
        self,
        llm: LLMClient,
        tool_registry: ToolRegistry,
        task: str,
        max_iterations: int = 7,
        model_tier: str = "balanced",
        parent_agent_type: str = "unknown",
        action_callback: ActionCallback | None = None,
    ) -> None:
        super().__init__(
            llm=llm,
            tool_registry=tool_registry,
            task=task,
            max_iterations=max_iterations,
            model_tier=model_tier,
            parent_agent_type=parent_agent_type,
            action_callback=action_callback,
            subagent_type="explore",
        )

    def _get_system_prompt(self) -> str:
        """Generate the explore agent's system prompt."""
        return f"""You are an Explore agent - a fast codebase exploration specialist.

Your task: {self._task}

Guidelines:
- Search efficiently using glob patterns and grep
- Read only necessary files (don't read entire directories)
- Map dependencies and relationships between files
- Report file paths with line numbers for findings
- Be thorough but fast - explore multiple search strategies
- If one approach doesn't find results, try alternative patterns

Output Format:
Return your findings as a structured JSON object:
{{
  "findings": [
    {{"file": "path/to/file.py", "line": 42, "match": "...", "context": "..."}}
  ],
  "structure": {{
    "directories": ["..."],
    "key_files": ["..."]
  }},
  "summary": "Brief explanation of what was found"
}}

Important:
- Stay focused on the exploration task
- Don't make changes, only gather information
- Be concise in your final response
- If you can't find what you're looking for, explain what you tried"""


class PlanSubagent(Subagent):
    """
    Architecture and implementation planning subagent.

    Specialized for designing implementation approaches:
    - Analyzes existing patterns before proposing changes
    - Identifies all files that need modification
    - Considers edge cases and error handling
    - Creates step-by-step implementation plans
    """

    def __init__(
        self,
        llm: LLMClient,
        tool_registry: ToolRegistry,
        task: str,
        context: str | None = None,
        max_iterations: int = 10,
        model_tier: str = "balanced",
        parent_agent_type: str = "unknown",
        action_callback: ActionCallback | None = None,
    ) -> None:
        # Prepend context to task if provided
        full_task = task
        if context:
            full_task = f"{task}\n\nAdditional context:\n{context}"

        super().__init__(
            llm=llm,
            tool_registry=tool_registry,
            task=full_task,
            max_iterations=max_iterations,
            model_tier=model_tier,
            parent_agent_type=parent_agent_type,
            action_callback=action_callback,
            subagent_type="plan",
        )

    def _get_system_prompt(self) -> str:
        """Generate the plan agent's system prompt."""
        return f"""You are a Plan agent - a software architect specializing in implementation planning.

Your task: {self._task}

Two-Phase Approach:
1. EXPLORE: First understand the current codebase state
   - Search for existing patterns and conventions
   - Find related code that might need to be modified
   - Identify dependencies and relationships

2. PLAN: Then design the implementation approach
   - Propose a step-by-step plan
   - Identify all files to create or modify
   - Consider edge cases and error handling

Guidelines:
- Analyze existing patterns before proposing changes
- Identify ALL files that need modification
- Consider edge cases and error handling
- Propose a step-by-step implementation order
- Flag potential risks or breaking changes

Output Format:
Return your plan as a structured JSON object:
{{
  "summary": "Brief description of the approach",
  "files_to_modify": [
    {{"path": "...", "action": "create|modify|delete", "reason": "..."}}
  ],
  "implementation_steps": [
    {{"step": 1, "description": "...", "files": ["..."]}}
  ],
  "testing_approach": "How to test the changes",
  "risks": ["Potential issues to watch for"],
  "estimated_complexity": "low|medium|high"
}}

Important:
- Don't make changes, only create the plan
- Be specific about file paths and changes needed
- Consider backward compatibility
- If requirements are unclear, note what assumptions you're making"""


def create_filtered_registry(
    source_registry: ToolRegistry,
    allowed_tools: frozenset[str],
) -> ToolRegistry:
    """
    Create a new ToolRegistry containing only the specified tools.

    Args:
        source_registry: The registry to filter from
        allowed_tools: Set of tool names to include

    Returns:
        A new ToolRegistry with only the allowed tools
    """
    filtered = ToolRegistry(source_registry._permission_context)

    for tool in source_registry.list_tools():
        if tool.name in allowed_tools:
            filtered.register(tool)

    return filtered
