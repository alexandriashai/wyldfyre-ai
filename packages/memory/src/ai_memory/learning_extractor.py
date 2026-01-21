"""
Automatic learning extraction from task results.
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
