"""
Automatic learning extraction from task results.

Enhanced with:
- Phase-specific extraction patterns
- Trace extraction from task execution
- Learning consolidation to avoid redundancy
"""
import re
from typing import Any

from .pai_memory import Learning, PAIPhase


class LearningExtractor:
    """Extract learnings from task execution results."""

    # Patterns indicating learning-worthy content
    LEARNING_PATTERNS = [
        r"(?i)learned?:?\s*(.+)",
        r"(?i)discovered?:?\s*(.+)",
        r"(?i)found that:?\s*(.+)",
        r"(?i)realized?:?\s*(.+)",
        r"(?i)note:?\s*(.+)",
        r"(?i)important:?\s*(.+)",
        r"(?i)key (insight|finding|takeaway):?\s*(.+)",
        r"(?i)the (solution|fix|answer) (is|was):?\s*(.+)",
    ]

    # Error patterns for error phase learning
    ERROR_PATTERNS = [
        r"(?i)error:?\s*(.+)",
        r"(?i)failed:?\s*(.+)",
        r"(?i)exception:?\s*(.+)",
        r"(?i)bug:?\s*(.+)",
        r"(?i)issue:?\s*(.+)",
    ]

    # Phase-specific patterns for enhanced extraction
    PHASE_PATTERNS = {
        PAIPhase.OBSERVE: [
            r"(?i)observed:?\s*(.+)",
            r"(?i)noticed:?\s*(.+)",
            r"(?i)saw that:?\s*(.+)",
            r"(?i)detected:?\s*(.+)",
            r"(?i)identified:?\s*(.+)",
            r"(?i)the (file|code|system) (shows|has|contains):?\s*(.+)",
        ],
        PAIPhase.THINK: [
            r"(?i)reasoning:?\s*(.+)",
            r"(?i)approach:?\s*(.+)",
            r"(?i)strategy:?\s*(.+)",
            r"(?i)analysis:?\s*(.+)",
            r"(?i)considering:?\s*(.+)",
            r"(?i)the (best|correct|right) way (is|to):?\s*(.+)",
        ],
        PAIPhase.PLAN: [
            r"(?i)plan:?\s*(.+)",
            r"(?i)will (first|then|next):?\s*(.+)",
            r"(?i)steps?:?\s*(.+)",
            r"(?i)procedure:?\s*(.+)",
            r"(?i)workflow:?\s*(.+)",
            r"(?i)(first|then|next|finally),?\s*(.+)",
        ],
        PAIPhase.BUILD: [
            r"(?i)using tool:?\s*(.+)",
            r"(?i)executing:?\s*(.+)",
            r"(?i)calling:?\s*(.+)",
            r"(?i)tool (selection|choice):?\s*(.+)",
            r"(?i)prepared:?\s*(.+)",
        ],
        PAIPhase.EXECUTE: [
            r"(?i)result:?\s*(.+)",
            r"(?i)output:?\s*(.+)",
            r"(?i)completed:?\s*(.+)",
            r"(?i)executed:?\s*(.+)",
            r"(?i)returned:?\s*(.+)",
            r"(?i)success(fully)?:?\s*(.+)",
        ],
        PAIPhase.VERIFY: [
            r"(?i)verified:?\s*(.+)",
            r"(?i)confirmed:?\s*(.+)",
            r"(?i)tested:?\s*(.+)",
            r"(?i)validated:?\s*(.+)",
            r"(?i)checked:?\s*(.+)",
            r"(?i)(works|working):?\s*(.+)",
        ],
        PAIPhase.LEARN: [
            r"(?i)learned:?\s*(.+)",
            r"(?i)takeaway:?\s*(.+)",
            r"(?i)lesson:?\s*(.+)",
            r"(?i)insight:?\s*(.+)",
            r"(?i)for (next|future) time:?\s*(.+)",
            r"(?i)remember:?\s*(.+)",
        ],
    }

    # Tool result patterns for mid-execution learning
    TOOL_SUCCESS_PATTERNS = [
        r"(?i)successfully (created|updated|deleted|read|wrote|executed):?\s*(.+)",
        r"(?i)(file|directory|resource) (created|found|updated):?\s*(.+)",
        r"(?i)command (completed|succeeded):?\s*(.+)",
    ]

    TOOL_ERROR_PATTERNS = [
        r"(?i)(file|directory|resource) not found:?\s*(.+)",
        r"(?i)permission denied:?\s*(.+)",
        r"(?i)timeout:?\s*(.+)",
        r"(?i)connection (failed|refused|error):?\s*(.+)",
        r"(?i)invalid (input|argument|parameter):?\s*(.+)",
    ]

    def extract_from_result(
        self,
        task_id: str,
        result: dict[str, Any],
        agent_type: str,
        permission_level: int = 1,
    ) -> list[Learning]:
        """
        Extract learnings from a task result.

        Args:
            task_id: Task identifier
            result: Task result dictionary
            agent_type: Type of agent that executed the task
            permission_level: Permission level for ACL

        Returns:
            List of Learning objects ready for storage
        """
        learnings = []

        # 1. Check for explicit learnings field
        if "learnings" in result and result["learnings"]:
            for item in result["learnings"]:
                content = item if isinstance(item, str) else item.get("content", str(item))
                learnings.append(self._create_learning(
                    content=content,
                    phase=PAIPhase.LEARN,
                    category="explicit",
                    task_id=task_id,
                    agent_type=agent_type,
                    confidence=0.9,
                    permission_level=permission_level,
                ))

        # 2. Extract from output text using patterns
        output = result.get("output", "") or result.get("message", "") or result.get("response", "")
        if output:
            pattern_learnings = self._extract_from_text(
                output, task_id, agent_type, permission_level
            )
            learnings.extend(pattern_learnings)

        # 3. Extract from errors (error phase learning)
        if result.get("error") or result.get("status") == "failed":
            error_msg = result.get("error", "") or result.get("error_message", "")
            if error_msg:
                learnings.append(self._create_learning(
                    content=f"Error encountered: {error_msg}",
                    phase=PAIPhase.VERIFY,  # Error during verify phase
                    category="error",
                    task_id=task_id,
                    agent_type=agent_type,
                    confidence=0.95,  # High confidence for errors
                    permission_level=permission_level,
                    metadata={"error_type": "task_failure"},
                ))

        return learnings

    def _extract_from_text(
        self,
        text: str,
        task_id: str,
        agent_type: str,
        permission_level: int,
    ) -> list[Learning]:
        """Extract learnings from free text using patterns."""
        learnings = []
        seen_content = set()  # Avoid duplicates within same extraction

        for pattern in self.LEARNING_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                content = match[-1] if isinstance(match, tuple) else match
                content = content.strip()

                # Skip very short matches or duplicates
                if len(content) < 10 or content in seen_content:
                    continue

                # Truncate very long content
                if len(content) > 500:
                    content = content[:497] + "..."

                seen_content.add(content)
                learnings.append(self._create_learning(
                    content=content,
                    phase=PAIPhase.LEARN,
                    category="extracted",
                    task_id=task_id,
                    agent_type=agent_type,
                    confidence=0.7,  # Lower confidence for pattern extraction
                    permission_level=permission_level,
                ))

        return learnings

    def _create_learning(
        self,
        content: str,
        phase: PAIPhase,
        category: str,
        task_id: str,
        agent_type: str,
        confidence: float,
        permission_level: int = 1,
        metadata: dict | None = None,
    ) -> Learning:
        """Create a Learning object with proper defaults."""
        return Learning(
            content=content,
            phase=phase,
            category=category,
            task_id=task_id,
            agent_type=agent_type,
            confidence=confidence,
            metadata=metadata or {},
            created_by_agent=agent_type,
            permission_level=permission_level,
            sensitivity="internal",
            allowed_agents=[],
        )

    def extract_from_traces(
        self,
        traces: list[dict[str, Any]],
        task_id: str,
        agent_type: str,
        permission_level: int = 1,
    ) -> list[Learning]:
        """
        Extract learnings from task execution traces.

        Analyzes traces from all PAI phases and extracts phase-specific learnings.

        Args:
            traces: List of trace dicts from PAI memory
            task_id: Task identifier
            agent_type: Type of agent that executed the task
            permission_level: Permission level for ACL

        Returns:
            List of Learning objects extracted from traces
        """
        learnings = []
        seen_content = set()

        for trace in traces:
            phase_str = trace.get("phase", "learn")
            try:
                phase = PAIPhase(phase_str)
            except ValueError:
                phase = PAIPhase.LEARN

            # Extract from trace data
            trace_learnings = self._extract_from_trace(
                trace=trace,
                phase=phase,
                task_id=task_id,
                agent_type=agent_type,
                permission_level=permission_level,
                seen_content=seen_content,
            )
            learnings.extend(trace_learnings)

        return learnings

    def _extract_from_trace(
        self,
        trace: dict[str, Any],
        phase: PAIPhase,
        task_id: str,
        agent_type: str,
        permission_level: int,
        seen_content: set,
    ) -> list[Learning]:
        """Extract learnings from a single trace."""
        learnings = []

        # Get phase-specific patterns
        patterns = self.PHASE_PATTERNS.get(phase, self.LEARNING_PATTERNS)

        # Check for notable patterns in trace data
        trace_text = " ".join(
            str(v) for v in trace.values()
            if isinstance(v, (str, int, float, bool))
        )

        for pattern in patterns:
            matches = re.findall(pattern, trace_text)
            for match in matches:
                content = match[-1] if isinstance(match, tuple) else match
                content = content.strip()

                if len(content) < 10 or content in seen_content:
                    continue

                if len(content) > 300:
                    content = content[:297] + "..."

                seen_content.add(content)
                learnings.append(self._create_learning(
                    content=content,
                    phase=phase,
                    category=f"{phase.value}_extracted",
                    task_id=task_id,
                    agent_type=agent_type,
                    confidence=0.6,  # Lower confidence for trace extraction
                    permission_level=permission_level,
                    metadata={"source": "trace", "trace_phase": phase.value},
                ))

        # Extract from specific trace fields
        if phase == PAIPhase.EXECUTE:
            success_rate = trace.get("success_rate")
            tools_executed = trace.get("tools_executed", 0)

            if success_rate is not None and tools_executed > 0:
                if success_rate == 1.0:
                    content = f"All {tools_executed} tools executed successfully"
                    learnings.append(self._create_learning(
                        content=content,
                        phase=phase,
                        category="execution_success",
                        task_id=task_id,
                        agent_type=agent_type,
                        confidence=0.8,
                        permission_level=permission_level,
                    ))
                elif success_rate < 0.5:
                    content = f"Low success rate ({success_rate:.0%}) across {tools_executed} tools"
                    learnings.append(self._create_learning(
                        content=content,
                        phase=phase,
                        category="execution_warning",
                        task_id=task_id,
                        agent_type=agent_type,
                        confidence=0.8,
                        permission_level=permission_level,
                    ))

        return learnings

    def extract_from_tool_result(
        self,
        tool_name: str,
        tool_arguments: dict[str, Any],
        result: dict[str, Any],
        task_id: str,
        agent_type: str,
        permission_level: int = 1,
    ) -> list[Learning]:
        """
        Extract learnings from a tool execution result (mid-execution learning).

        Args:
            tool_name: Name of the tool that was executed
            tool_arguments: Arguments passed to the tool
            result: Tool execution result
            task_id: Task identifier
            agent_type: Type of agent
            permission_level: Permission level for ACL

        Returns:
            List of Learning objects if notable patterns found
        """
        learnings = []
        success = result.get("success", True)
        output = str(result.get("output", ""))
        error = result.get("error", "")

        # Check for notable success patterns
        if success and output:
            for pattern in self.TOOL_SUCCESS_PATTERNS:
                matches = re.findall(pattern, output)
                for match in matches:
                    content = match[-1] if isinstance(match, tuple) else match
                    content = f"Successful {tool_name}: {content.strip()}"

                    if len(content) > 10:
                        learnings.append(self._create_learning(
                            content=content[:300],
                            phase=PAIPhase.EXECUTE,
                            category="tool_success",
                            task_id=task_id,
                            agent_type=agent_type,
                            confidence=0.75,
                            permission_level=permission_level,
                            metadata={
                                "tool_name": tool_name,
                                "source": "tool_result",
                            },
                        ))
                        break  # One learning per tool execution

        # Check for error patterns
        if error or not success:
            error_text = error or output
            for pattern in self.TOOL_ERROR_PATTERNS:
                matches = re.findall(pattern, error_text)
                for match in matches:
                    content = match[-1] if isinstance(match, tuple) else match
                    content = f"Error in {tool_name}: {content.strip()}"

                    if len(content) > 10:
                        learnings.append(self._create_learning(
                            content=content[:300],
                            phase=PAIPhase.EXECUTE,
                            category="tool_error",
                            task_id=task_id,
                            agent_type=agent_type,
                            confidence=0.85,  # High confidence for errors
                            permission_level=permission_level,
                            metadata={
                                "tool_name": tool_name,
                                "source": "tool_result",
                                "error_type": "execution_error",
                            },
                        ))
                        break

        return learnings

    def consolidate_learnings(
        self,
        learnings: list[Learning],
        similarity_threshold: float = 0.85,
    ) -> list[Learning]:
        """
        Consolidate similar learnings to avoid redundancy.

        Uses simple text similarity to identify and merge duplicates.

        Args:
            learnings: List of Learning objects to consolidate
            similarity_threshold: Minimum similarity ratio to consider as duplicate

        Returns:
            Consolidated list of Learning objects
        """
        if not learnings:
            return []

        from difflib import SequenceMatcher

        consolidated = []
        used_indices = set()

        for i, learning in enumerate(learnings):
            if i in used_indices:
                continue

            # Find similar learnings
            similar_group = [learning]

            for j, other in enumerate(learnings[i + 1:], start=i + 1):
                if j in used_indices:
                    continue

                # Calculate similarity
                ratio = SequenceMatcher(
                    None,
                    learning.content.lower(),
                    other.content.lower(),
                ).ratio()

                if ratio >= similarity_threshold:
                    similar_group.append(other)
                    used_indices.add(j)

            # Keep the highest confidence learning from the group
            best = max(similar_group, key=lambda l: l.confidence)
            consolidated.append(best)
            used_indices.add(i)

        return consolidated

    def extract_with_phase(
        self,
        text: str,
        phase: PAIPhase,
        task_id: str,
        agent_type: str,
        permission_level: int = 1,
    ) -> list[Learning]:
        """
        Extract learnings from text using phase-specific patterns.

        Args:
            text: Text to extract learnings from
            phase: PAI phase to use for pattern matching
            task_id: Task identifier
            agent_type: Type of agent
            permission_level: Permission level for ACL

        Returns:
            List of Learning objects
        """
        learnings = []
        seen_content = set()

        # Get phase-specific patterns (make a copy to avoid mutating class attribute)
        patterns = list(self.PHASE_PATTERNS.get(phase, []))
        # Also use general patterns
        patterns.extend(self.LEARNING_PATTERNS)

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                content = match[-1] if isinstance(match, tuple) else match
                content = content.strip()

                if len(content) < 10 or content in seen_content:
                    continue

                if len(content) > 500:
                    content = content[:497] + "..."

                seen_content.add(content)

                # Determine category based on phase
                category = f"{phase.value}_pattern" if phase != PAIPhase.LEARN else "extracted"

                learnings.append(self._create_learning(
                    content=content,
                    phase=phase,
                    category=category,
                    task_id=task_id,
                    agent_type=agent_type,
                    confidence=0.65,
                    permission_level=permission_level,
                ))

        return learnings
