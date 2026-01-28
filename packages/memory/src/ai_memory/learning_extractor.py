"""
Automatic learning extraction from task results.

Enhanced with:
- Phase-specific extraction patterns
- Trace extraction from task execution
- Learning consolidation to avoid redundancy
- Quality filtering to avoid low-value learnings
"""
import re
from typing import Any

from .pai_memory import Learning, PAIPhase


class LearningExtractor:
    """Extract learnings from task execution results with quality filtering."""

    # Quality thresholds
    MIN_LEARNING_LENGTH = 25  # Minimum characters for a learning
    MAX_LEARNING_LENGTH = 500  # Maximum before truncation
    MIN_WORDS = 5  # Minimum word count
    MIN_CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence to store

    # Blocklist patterns - content matching these is filtered out
    BLOCKLIST_PATTERNS = [
        r"(?i)^(ok|okay|done|yes|no|sure|thanks|thank you|got it)[\.\s]*$",
        r"(?i)^(running|executing|processing|loading|starting|checking)\.{0,3}$",
        r"(?i)^(all \d+ tools? executed successfully)$",
        r"(?i)^(task completed?|completed successfully)[\.\s]*$",
        r"(?i)^(success|failed|error)[\.\s]*$",
        r"(?i)^[\d\.\s]+$",  # Just numbers
        r"(?i)^[a-z_]+\s*=\s*[a-z0-9_]+$",  # Variable assignments
        r"(?i)console\.(log|error|warn|info)",  # Logging statements
        r"(?i)^(null|undefined|none|true|false)$",
        r"(?i)^file (not found|exists|created|deleted|updated)$",
        r"(?i)^\[.*\]\s*$",  # Just timestamps or brackets
        r"(?i)^https?://",  # URLs only
        r"(?i)^/[^\s]+$",  # File paths only
    ]

    # Noise words that indicate low-quality content
    NOISE_INDICATORS = [
        "todo", "fixme", "hack", "xxx", "debug",
        "test123", "asdf", "lorem ipsum",
    ]

    # Patterns indicating learning-worthy content (tightened)
    # Now require more context and full sentences
    LEARNING_PATTERNS = [
        r"(?i)(?:I\s+)?learned\s+that\s+(.{25,})",
        r"(?i)(?:I\s+)?discovered\s+that\s+(.{25,})",
        r"(?i)(?:I\s+)?found\s+that\s+(.{25,})",
        r"(?i)(?:I\s+)?realized\s+that\s+(.{25,})",
        r"(?i)key\s+(?:insight|finding|takeaway):\s*(.{25,})",
        r"(?i)the\s+(?:solution|fix|answer)\s+(?:is|was)\s+to\s+(.{25,})",
        r"(?i)important(?:ly)?:\s*(.{30,})",
        r"(?i)note:\s*(?:the|this|when|if|always|never)\s+(.{25,})",
    ]

    # Error patterns - more specific to capture actionable errors
    ERROR_PATTERNS = [
        r"(?i)error:\s*([A-Z][^.!?]{20,}[.!?])",
        r"(?i)failed\s+(?:to|because|due to)\s+(.{25,})",
        r"(?i)exception:\s*([A-Z][^.!?]{15,})",
        r"(?i)bug\s+(?:found|detected|identified):\s*(.{20,})",
        r"(?i)issue:\s*(?:the|this|when)\s+(.{25,})",
    ]

    # Phase-specific patterns for enhanced extraction (tightened)
    # Now require minimum content length and more specific context
    PHASE_PATTERNS = {
        PAIPhase.OBSERVE: [
            r"(?i)observed\s+that\s+(.{25,})",
            r"(?i)noticed\s+that\s+(.{25,})",
            r"(?i)saw\s+that\s+the\s+(.{25,})",
            r"(?i)detected\s+(?:a|an|the)\s+(.{25,})",
            r"(?i)identified\s+(?:a|an|the)\s+(.{25,})",
            r"(?i)the\s+(?:file|code|system|codebase)\s+(?:shows|has|contains|uses)\s+(.{25,})",
        ],
        PAIPhase.THINK: [
            r"(?i)the\s+reasoning\s+(?:is|behind)\s+(.{25,})",
            r"(?i)the\s+approach\s+(?:is|should be)\s+(.{25,})",
            r"(?i)the\s+strategy\s+(?:is|for)\s+(.{25,})",
            r"(?i)analysis\s+shows\s+that\s+(.{25,})",
            r"(?i)the\s+(?:best|correct|right)\s+way\s+(?:is|to)\s+(.{25,})",
        ],
        PAIPhase.PLAN: [
            r"(?i)the\s+plan\s+(?:is|involves)\s+(.{25,})",
            r"(?i)will\s+(?:first|then|next)\s+(.{20,})\s+(?:and|before|after)",
            r"(?i)the\s+steps?\s+(?:are|include)\s+(.{25,})",
            r"(?i)the\s+procedure\s+(?:is|for)\s+(.{25,})",
            r"(?i)the\s+workflow\s+(?:is|involves)\s+(.{25,})",
        ],
        PAIPhase.BUILD: [
            r"(?i)using\s+(?:the\s+)?tool\s+(.{15,})\s+(?:to|for|because)",
            r"(?i)tool\s+(?:selection|choice)\s+(?:is|was)\s+(.{20,})\s+because",
        ],
        PAIPhase.EXECUTE: [
            # Removed generic "result", "output", "completed" patterns
            # Only capture meaningful execution learnings
            r"(?i)execution\s+(?:showed|revealed)\s+that\s+(.{25,})",
            r"(?i)the\s+(?:result|output)\s+(?:indicates|shows)\s+that\s+(.{25,})",
        ],
        PAIPhase.VERIFY: [
            r"(?i)verified\s+that\s+(.{25,})",
            r"(?i)confirmed\s+that\s+(.{25,})",
            r"(?i)tested\s+and\s+found\s+that\s+(.{25,})",
            r"(?i)validated\s+that\s+(.{25,})",
            r"(?i)checking\s+(?:showed|revealed)\s+that\s+(.{25,})",
        ],
        PAIPhase.LEARN: [
            r"(?i)learned\s+that\s+(.{25,})",
            r"(?i)the\s+takeaway\s+is\s+that\s+(.{25,})",
            r"(?i)the\s+lesson\s+(?:is|here)\s+(?:is\s+)?that\s+(.{25,})",
            r"(?i)(?:key|main)\s+insight:\s*(.{25,})",
            r"(?i)for\s+(?:next|future)\s+time,?\s+(.{25,})",
            r"(?i)remember\s+(?:to|that)\s+(.{25,})",
        ],
    }

    # Tool result patterns for mid-execution learning (tightened)
    # Removed generic success patterns that don't provide actionable knowledge
    TOOL_SUCCESS_PATTERNS = [
        # Only capture patterns that include WHY or context
        r"(?i)successfully\s+(?:created|updated)\s+(.{15,})\s+(?:by|using|with|because)",
        r"(?i)(?:file|resource)\s+(?:created|updated)\s+at\s+(.{10,})\s+(?:with|containing)",
    ]

    TOOL_ERROR_PATTERNS = [
        # More specific error patterns that capture root cause
        r"(?i)(?:file|directory)\s+not\s+found:\s*(.{15,})\s+-\s+(.{10,})",
        r"(?i)permission\s+denied\s+(?:for|when|accessing)\s+(.{15,})",
        r"(?i)timeout\s+(?:after|waiting for)\s+(.{15,})",
        r"(?i)connection\s+(?:failed|refused)\s+(?:to|because)\s+(.{15,})",
        r"(?i)invalid\s+(?:input|argument):\s*(.{20,})",
    ]

    def _passes_quality_check(self, content: str) -> bool:
        """
        Check if content passes quality filters.

        Returns True if content is high-quality learning material.
        """
        if not content or not isinstance(content, str):
            return False

        content = content.strip()

        # Length checks
        if len(content) < self.MIN_LEARNING_LENGTH:
            return False

        # Word count check
        words = content.split()
        if len(words) < self.MIN_WORDS:
            return False

        # Check blocklist patterns
        for pattern in self.BLOCKLIST_PATTERNS:
            if re.match(pattern, content):
                return False

        # Check for noise indicators
        content_lower = content.lower()
        for noise in self.NOISE_INDICATORS:
            if noise in content_lower:
                return False

        # Must contain at least one verb (basic sentence structure)
        verb_indicators = [
            " is ", " are ", " was ", " were ", " be ", " been ",
            " have ", " has ", " had ", " do ", " does ", " did ",
            " will ", " would ", " could ", " should ", " can ",
            " use ", " used ", " using ", " create ", " created ",
            " implement ", " fix ", " add ", " remove ", " update ",
        ]
        has_verb = any(v in f" {content_lower} " for v in verb_indicators)
        if not has_verb:
            return False

        # Avoid content that's mostly code or symbols
        alpha_chars = sum(1 for c in content if c.isalpha() or c.isspace())
        if alpha_chars / max(len(content), 1) < 0.5:
            return False

        return True

    def _distill_error(self, error_msg: str, context: str = "") -> str | None:
        """
        Distill raw error message into actionable learning.

        Instead of storing verbatim errors, extract the actionable insight.
        Returns None if error can't be distilled into useful learning.
        """
        if not error_msg:
            return None

        # Skip generic errors that don't teach anything
        generic_errors = [
            "internal server error",
            "something went wrong",
            "an error occurred",
            "unknown error",
            "null pointer",
            "undefined is not",
        ]
        error_lower = error_msg.lower()
        for generic in generic_errors:
            if generic in error_lower:
                return None

        # Extract the root cause if possible
        root_cause_patterns = [
            r"(?i)caused by[:\s]+(.{20,})",
            r"(?i)reason[:\s]+(.{20,})",
            r"(?i)because\s+(.{20,})",
            r"(?i)due to\s+(.{20,})",
        ]

        for pattern in root_cause_patterns:
            match = re.search(pattern, error_msg)
            if match:
                cause = match.group(1).strip()
                if self._passes_quality_check(cause):
                    return f"When {context}: {cause}" if context else cause

        # If we can't extract root cause, try to create actionable format
        # Only if error is specific enough
        if len(error_msg) > 30 and not any(g in error_lower for g in generic_errors):
            # Truncate long stack traces
            lines = error_msg.split("\n")
            if len(lines) > 3:
                error_msg = lines[0]
            if len(error_msg) > 150:
                error_msg = error_msg[:147] + "..."

            return f"Error pattern to avoid: {error_msg}"

        return None

    def extract_from_result(
        self,
        task_id: str,
        result: dict[str, Any],
        agent_type: str,
        permission_level: int = 1,
    ) -> list[Learning]:
        """
        Extract learnings from a task result with quality filtering.

        Args:
            task_id: Task identifier
            result: Task result dictionary
            agent_type: Type of agent that executed the task
            permission_level: Permission level for ACL

        Returns:
            List of Learning objects ready for storage (quality-filtered)
        """
        learnings = []

        # 1. Check for explicit learnings field
        if "learnings" in result and result["learnings"]:
            for item in result["learnings"]:
                content = item if isinstance(item, str) else item.get("content", str(item))
                # Apply quality check even to explicit learnings
                if self._passes_quality_check(content):
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

        # 3. Extract from errors - distill instead of storing verbatim
        if result.get("error") or result.get("status") == "failed":
            error_msg = result.get("error", "") or result.get("error_message", "")
            if error_msg:
                # Get context for better error distillation
                task_type = result.get("task_type", "")
                distilled = self._distill_error(error_msg, context=task_type)
                if distilled and self._passes_quality_check(distilled):
                    learnings.append(self._create_learning(
                        content=distilled,
                        phase=PAIPhase.VERIFY,
                        category="error_pattern",
                        task_id=task_id,
                        agent_type=agent_type,
                        confidence=0.85,  # Slightly lower for distilled errors
                        permission_level=permission_level,
                        metadata={
                            "error_type": "task_failure",
                            "original_error_length": len(error_msg),
                        },
                    ))

        return learnings

    def _extract_from_text(
        self,
        text: str,
        task_id: str,
        agent_type: str,
        permission_level: int,
    ) -> list[Learning]:
        """Extract learnings from free text using patterns with quality filtering."""
        learnings = []
        seen_content = set()  # Avoid duplicates within same extraction

        for pattern in self.LEARNING_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                content = match[-1] if isinstance(match, tuple) else match
                content = content.strip()

                # Skip duplicates
                if content in seen_content:
                    continue

                # Apply quality check
                if not self._passes_quality_check(content):
                    continue

                # Truncate very long content
                if len(content) > self.MAX_LEARNING_LENGTH:
                    content = content[:self.MAX_LEARNING_LENGTH - 3] + "..."

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
        """Extract learnings from a single trace with quality filtering."""
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

                if content in seen_content:
                    continue

                # Apply quality check
                if not self._passes_quality_check(content):
                    continue

                if len(content) > self.MAX_LEARNING_LENGTH:
                    content = content[:self.MAX_LEARNING_LENGTH - 3] + "..."

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

        # REMOVED: Generic success/failure metrics like "All X tools executed successfully"
        # These don't provide actionable knowledge and clutter the learning store.
        # Only meaningful execution patterns with context should be stored.

        # Extract meaningful execution patterns (only if they have context)
        if phase == PAIPhase.EXECUTE:
            # Only capture if there's meaningful context about WHAT was executed
            tool_name = trace.get("tool_name", "")
            result = trace.get("result", "")
            if tool_name and result:
                success_rate = trace.get("success_rate")
                if success_rate is not None and success_rate < 0.5:
                    # Only store low success patterns if we have enough context
                    error_context = trace.get("error", trace.get("failure_reason", ""))
                    if error_context and len(error_context) > 20:
                        distilled = self._distill_error(error_context, context=tool_name)
                        if distilled and self._passes_quality_check(distilled):
                            learnings.append(self._create_learning(
                                content=distilled,
                                phase=phase,
                                category="execution_pattern",
                                task_id=task_id,
                                agent_type=agent_type,
                                confidence=0.75,
                                permission_level=permission_level,
                                metadata={"tool": tool_name, "success_rate": success_rate},
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

        Only extracts learnings that provide actionable knowledge, not generic
        success/failure messages.

        Args:
            tool_name: Name of the tool that was executed
            tool_arguments: Arguments passed to the tool
            result: Tool execution result
            task_id: Task identifier
            agent_type: Type of agent
            permission_level: Permission level for ACL

        Returns:
            List of Learning objects if notable patterns found (quality filtered)
        """
        learnings = []
        success = result.get("success", True)
        output = str(result.get("output", ""))
        error = result.get("error", "")

        # Check for notable success patterns (only if they provide context)
        if success and output:
            for pattern in self.TOOL_SUCCESS_PATTERNS:
                matches = re.findall(pattern, output)
                for match in matches:
                    content = match[-1] if isinstance(match, tuple) else match
                    content = f"When using {tool_name}: {content.strip()}"

                    # Apply quality check
                    if self._passes_quality_check(content):
                        learnings.append(self._create_learning(
                            content=content[:self.MAX_LEARNING_LENGTH],
                            phase=PAIPhase.EXECUTE,
                            category="tool_pattern",
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

        # Check for error patterns - distill rather than store verbatim
        if error or not success:
            error_text = error or output
            distilled = self._distill_error(error_text, context=tool_name)
            if distilled and self._passes_quality_check(distilled):
                learnings.append(self._create_learning(
                    content=distilled[:self.MAX_LEARNING_LENGTH],
                    phase=PAIPhase.EXECUTE,
                    category="tool_error_pattern",
                    task_id=task_id,
                    agent_type=agent_type,
                    confidence=0.80,
                    permission_level=permission_level,
                    metadata={
                        "tool_name": tool_name,
                        "source": "tool_result",
                        "error_type": "execution_error",
                    },
                ))

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
        Extract learnings from text using phase-specific patterns with quality filtering.

        Args:
            text: Text to extract learnings from
            phase: PAI phase to use for pattern matching
            task_id: Task identifier
            agent_type: Type of agent
            permission_level: Permission level for ACL

        Returns:
            List of Learning objects (quality filtered)
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

                if content in seen_content:
                    continue

                # Apply quality check
                if not self._passes_quality_check(content):
                    continue

                if len(content) > self.MAX_LEARNING_LENGTH:
                    content = content[:self.MAX_LEARNING_LENGTH - 3] + "..."

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
