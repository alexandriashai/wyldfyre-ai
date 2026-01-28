"""
User prompt submit hook - Executed when a user sends a message.

Responsibilities:
- Log user input for analytics
- Extract implicit feedback from user messages
- Capture ideas from user messages
- Update UI/statusline
- Pre-process input for task routing
"""

import re
from datetime import datetime, timezone
from typing import Any

from ai_memory import PAIMemory, PAIPhase, TelosManager, get_telos_manager


# Patterns for detecting implicit feedback
POSITIVE_FEEDBACK_PATTERNS = [
    re.compile(r"(?i)that('s| is)?\s*(great|perfect|exactly|correct|right|good|awesome|nice|helpful)", re.IGNORECASE),
    re.compile(r"(?i)thank(s| you)", re.IGNORECASE),
    re.compile(r"(?i)well done", re.IGNORECASE),
    re.compile(r"(?i)this works", re.IGNORECASE),
    re.compile(r"(?i)yes[,!.]?\s*(that|this)", re.IGNORECASE),
]

NEGATIVE_FEEDBACK_PATTERNS = [
    re.compile(r"(?i)that('s| is)?\s*(wrong|incorrect|bad|not right|broken)", re.IGNORECASE),
    re.compile(r"(?i)no[,!.]?\s*(that|this)", re.IGNORECASE),
    re.compile(r"(?i)doesn't work", re.IGNORECASE),
    re.compile(r"(?i)still (broken|failing|not working)", re.IGNORECASE),
    re.compile(r"(?i)try again", re.IGNORECASE),
]

# Patterns for detecting ideas (tightened to require more context)
# Must have at least 20 chars of content to be a valid idea
IDEA_PATTERNS = [
    # Future intentions with concrete actions
    re.compile(r"(?i)(?:we|I)\s+should\s+(?:probably\s+)?(\w{3,}\s+.{15,})", re.IGNORECASE),
    # Hypotheticals with explanation
    re.compile(r"(?i)what\s+if\s+we\s+(\w{3,}\s+.{15,})", re.IGNORECASE),
    # Suggestions with reasoning
    re.compile(r"(?i)maybe\s+we\s+could\s+(\w{3,}\s+.{15,})", re.IGNORECASE),
    # Explicit idea markers (these are reliable signals)
    re.compile(r"(?i)TODO:\s*(\w{3,}\s+.{15,})", re.IGNORECASE),
    re.compile(r"(?i)IDEA:\s*(\w{3,}\s+.{15,})", re.IGNORECASE),
    re.compile(r"(?i)FEATURE:\s*(\w{3,}\s+.{15,})", re.IGNORECASE),
    # Cool/nice to have with substance
    re.compile(r"(?i)it\s+would\s+be\s+(?:cool|nice|great)\s+(?:if\s+we\s+|to\s+)(\w{3,}\s+.{15,})", re.IGNORECASE),
]

# Minimum length for captured idea content
MIN_IDEA_LENGTH = 20


async def user_prompt_submit_hook(
    user_input: str,
    agent_type: str,
    session_id: str,
    memory: PAIMemory | None = None,
    telos: TelosManager | None = None,
    project_id: str | None = None,
    previous_task_id: str | None = None,
    previous_learnings_used: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute user prompt submit hook for input processing.

    Args:
        user_input: The user's message/prompt
        agent_type: Type of agent receiving the input
        session_id: Current session identifier
        memory: PAI memory instance (optional)
        telos: TELOS manager instance (optional)
        project_id: Optional project context
        previous_task_id: ID of previous task for feedback correlation
        previous_learnings_used: Learning IDs used in previous task
        metadata: Additional metadata

    Returns:
        Dict with:
        - feedback_type: "positive", "negative", or None
        - feedback_strength: 0-1 strength of detected feedback
        - ideas_captured: List of captured ideas
        - input_stats: Statistics about the input
        - preprocessed: Any preprocessed data
    """
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_length": len(user_input),
        "feedback_type": None,
        "feedback_strength": 0.0,
        "ideas_captured": [],
        "input_stats": {},
        "preprocessed": {},
    }

    # Analyze input statistics
    result["input_stats"] = {
        "char_count": len(user_input),
        "word_count": len(user_input.split()),
        "line_count": len(user_input.splitlines()),
        "has_code": "```" in user_input or "def " in user_input or "class " in user_input,
        "has_question": "?" in user_input,
        "has_command": user_input.strip().startswith("/"),
    }

    # Detect implicit feedback
    positive_matches = sum(1 for p in POSITIVE_FEEDBACK_PATTERNS if p.search(user_input))
    negative_matches = sum(1 for p in NEGATIVE_FEEDBACK_PATTERNS if p.search(user_input))

    if positive_matches > negative_matches:
        result["feedback_type"] = "positive"
        result["feedback_strength"] = min(1.0, positive_matches * 0.25)
    elif negative_matches > positive_matches:
        result["feedback_type"] = "negative"
        result["feedback_strength"] = min(1.0, negative_matches * 0.25)

    # Apply feedback to previous learnings if detected
    if memory and previous_learnings_used and result["feedback_type"]:
        for learning_id in previous_learnings_used:
            try:
                if result["feedback_type"] == "positive":
                    await memory.boost_learning(learning_id, amount=0.15)
                else:
                    await memory.decay_learning(learning_id, amount=0.1)
            except Exception:
                pass  # Non-critical

        result["feedback_applied_to"] = len(previous_learnings_used)

    # Initialize TELOS manager if not provided
    if telos is None:
        try:
            telos = get_telos_manager()
        except Exception:
            pass

    # Capture ideas from user input (with quality filtering)
    if telos:
        try:
            captured = await telos.detect_ideas_in_message(user_input, project_id)
            # Filter out short or low-quality ideas
            quality_ideas = [
                idea.content for idea in captured
                if len(idea.content.strip()) >= MIN_IDEA_LENGTH
                and sum(1 for c in idea.content if c.isalpha()) / max(len(idea.content), 1) > 0.5
            ]
            result["ideas_captured"] = quality_ideas
        except Exception as e:
            result["idea_capture_error"] = str(e)

    # Store input event in HOT memory for analytics
    if memory:
        try:
            await memory.store_task_trace(
                task_id=session_id,
                phase=PAIPhase.OBSERVE,
                data={
                    "event": "user_prompt_submit",
                    "agent_type": agent_type,
                    "project_id": project_id,
                    "input_length": result["input_length"],
                    "feedback_type": result["feedback_type"],
                    "ideas_count": len(result["ideas_captured"]),
                    "has_code": result["input_stats"]["has_code"],
                    "has_question": result["input_stats"]["has_question"],
                    "timestamp": result["timestamp"],
                },
            )
        except Exception:
            pass  # Non-critical

    return result


def extract_implicit_feedback(
    user_input: str,
) -> tuple[str | None, float]:
    """
    Extract implicit feedback from user message.

    Args:
        user_input: User's message

    Returns:
        Tuple of (feedback_type, strength)
        feedback_type: "positive", "negative", or None
        strength: 0-1 confidence in the feedback
    """
    positive_count = sum(1 for p in POSITIVE_FEEDBACK_PATTERNS if p.search(user_input))
    negative_count = sum(1 for p in NEGATIVE_FEEDBACK_PATTERNS if p.search(user_input))

    if positive_count > negative_count:
        return "positive", min(1.0, positive_count * 0.25)
    elif negative_count > positive_count:
        return "negative", min(1.0, negative_count * 0.25)
    return None, 0.0


def categorize_user_input(user_input: str) -> str:
    """
    Categorize user input for routing.

    Args:
        user_input: User's message

    Returns:
        Category string: "command", "question", "code_request",
                        "feedback", "conversation", etc.
    """
    input_lower = user_input.lower().strip()

    # Commands
    if input_lower.startswith("/"):
        return "command"

    # Questions
    question_words = ["what", "how", "why", "when", "where", "who", "can", "could", "would", "is", "are", "does", "do"]
    if "?" in user_input or any(input_lower.startswith(w) for w in question_words):
        return "question"

    # Code requests
    code_keywords = ["write", "create", "implement", "build", "code", "function", "class", "fix", "debug", "refactor"]
    if any(kw in input_lower for kw in code_keywords):
        return "code_request"

    # Feedback
    feedback_type, strength = extract_implicit_feedback(user_input)
    if feedback_type and strength > 0.5:
        return "feedback"

    # Default to conversation
    return "conversation"
