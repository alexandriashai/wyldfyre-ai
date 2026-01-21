"""
Task router for the Supervisor agent.

Determines which agent(s) should handle a given task.
"""

from dataclasses import dataclass, field
from enum import Enum

from ai_core import AgentType, get_logger

logger = get_logger(__name__)


class RoutingStrategy(str, Enum):
    """How to route a task."""
    SINGLE = "single"         # Route to one agent
    SEQUENTIAL = "sequential"  # Route to agents in sequence
    PARALLEL = "parallel"      # Route to agents in parallel
    CONSULT = "consult"       # Get input from agent before deciding


@dataclass
class RoutingDecision:
    """Result of routing analysis."""
    strategy: RoutingStrategy
    primary_agent: AgentType
    secondary_agents: list[AgentType] = field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.8


# Task type patterns for routing
TASK_PATTERNS: dict[str, AgentType] = {
    # Code-related tasks
    "code_review": AgentType.CODE,
    "code_analysis": AgentType.CODE,
    "write_code": AgentType.CODE,
    "fix_bug": AgentType.CODE,
    "refactor": AgentType.CODE,
    "git_": AgentType.CODE,
    "test_": AgentType.CODE,

    # Data-related tasks
    "sql_": AgentType.DATA,
    "query_": AgentType.DATA,
    "database_": AgentType.DATA,
    "data_analysis": AgentType.DATA,
    "etl_": AgentType.DATA,
    "backup_": AgentType.DATA,

    # Infrastructure tasks
    "docker_": AgentType.INFRA,
    "nginx_": AgentType.INFRA,
    "ssl_": AgentType.INFRA,
    "domain_": AgentType.INFRA,
    "deploy_": AgentType.INFRA,
    "server_": AgentType.INFRA,

    # Research tasks
    "search_": AgentType.RESEARCH,
    "research_": AgentType.RESEARCH,
    "lookup_": AgentType.RESEARCH,
    "documentation_": AgentType.RESEARCH,

    # QA tasks
    "review_": AgentType.QA,
    "validate_": AgentType.QA,
    "security_": AgentType.QA,
    "audit_": AgentType.QA,
}


class TaskRouter:
    """
    Routes tasks to appropriate agents based on task type and content.

    Uses pattern matching and heuristics for fast routing,
    with fallback to LLM-based analysis for ambiguous cases.
    """

    def __init__(self) -> None:
        self._patterns = TASK_PATTERNS.copy()

    def add_pattern(self, pattern: str, agent: AgentType) -> None:
        """Add a routing pattern."""
        self._patterns[pattern] = agent

    def route_by_pattern(self, task_type: str) -> AgentType | None:
        """
        Route task using pattern matching.

        Returns:
            Target agent or None if no pattern matches
        """
        task_lower = task_type.lower()

        # Check exact match first
        if task_lower in self._patterns:
            return self._patterns[task_lower]

        # Check prefix patterns
        for pattern, agent in self._patterns.items():
            if pattern.endswith("_"):
                if task_lower.startswith(pattern) or task_lower.startswith(pattern[:-1]):
                    return agent
            elif task_lower.startswith(pattern) or pattern in task_lower:
                return agent

        return None

    def analyze_task(
        self,
        task_type: str,
        payload: dict | None = None,
        metadata: dict | None = None,
    ) -> RoutingDecision:
        """
        Analyze task and determine routing.

        Args:
            task_type: Type of task
            payload: Task payload
            metadata: Task metadata

        Returns:
            RoutingDecision with target agent(s)
        """
        # Try pattern matching first
        primary = self.route_by_pattern(task_type)

        if primary:
            return RoutingDecision(
                strategy=RoutingStrategy.SINGLE,
                primary_agent=primary,
                reasoning=f"Matched pattern for {task_type}",
                confidence=0.9,
            )

        # Analyze payload for clues
        if payload:
            payload_str = str(payload).lower()

            # Check for code indicators
            if any(kw in payload_str for kw in ["code", "function", "class", "bug", "test"]):
                return RoutingDecision(
                    strategy=RoutingStrategy.SINGLE,
                    primary_agent=AgentType.CODE,
                    reasoning="Payload contains code-related keywords",
                    confidence=0.7,
                )

            # Check for data indicators
            if any(kw in payload_str for kw in ["sql", "query", "database", "table"]):
                return RoutingDecision(
                    strategy=RoutingStrategy.SINGLE,
                    primary_agent=AgentType.DATA,
                    reasoning="Payload contains data-related keywords",
                    confidence=0.7,
                )

            # Check for infrastructure indicators
            if any(kw in payload_str for kw in ["docker", "nginx", "server", "deploy"]):
                return RoutingDecision(
                    strategy=RoutingStrategy.SINGLE,
                    primary_agent=AgentType.INFRA,
                    reasoning="Payload contains infrastructure keywords",
                    confidence=0.7,
                )

        # Default to research for unknown tasks
        return RoutingDecision(
            strategy=RoutingStrategy.SINGLE,
            primary_agent=AgentType.RESEARCH,
            reasoning="No clear pattern match, defaulting to research",
            confidence=0.5,
        )

    def route_complex_task(
        self,
        task_type: str,
        subtasks: list[str],
    ) -> RoutingDecision:
        """
        Route a complex task that may require multiple agents.

        Args:
            task_type: Main task type
            subtasks: List of subtask types

        Returns:
            RoutingDecision with orchestration strategy
        """
        # Analyze each subtask
        agents_needed = set()
        for subtask in subtasks:
            agent = self.route_by_pattern(subtask)
            if agent:
                agents_needed.add(agent)

        if len(agents_needed) == 0:
            # No matches, treat as single task
            return self.analyze_task(task_type)

        if len(agents_needed) == 1:
            return RoutingDecision(
                strategy=RoutingStrategy.SINGLE,
                primary_agent=list(agents_needed)[0],
                reasoning="All subtasks map to single agent",
                confidence=0.8,
            )

        # Multiple agents needed
        agents_list = list(agents_needed)
        primary = agents_list[0]
        secondary = agents_list[1:]

        # Determine if sequential or parallel
        # For now, default to sequential for safety
        return RoutingDecision(
            strategy=RoutingStrategy.SEQUENTIAL,
            primary_agent=primary,
            secondary_agents=secondary,
            reasoning=f"Complex task requiring {len(agents_needed)} agents",
            confidence=0.7,
        )
