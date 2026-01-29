"""
Task Complexity Classifier using MFRouter-style classification.

Analyzes task descriptions to determine execution_mode:
- "direct" - Simple commands that should execute immediately (builds, restarts, git ops)
- "complex" - Tasks requiring exploration/planning (features, refactoring, debugging)
- "plan" - Large tasks that should suggest entering plan mode first

Uses matrix factorization model trained on task complexity patterns,
similar to how ContentRouter routes to model tiers.
"""

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)

# Configuration
CLASSIFIER_ENABLED_KEY = "llm:task_classifier_enabled"
CLASSIFIER_CONFIG_PATH = os.environ.get(
    "TASK_CLASSIFIER_CONFIG_PATH",
    "/home/wyld-core/config/router/task_classifier_config.yaml"
)
LATENCY_BUDGET_MS = int(os.environ.get("TASK_CLASSIFIER_LATENCY_MS", "500"))
CACHE_TTL = 300  # 5 min cache for same task patterns


class ExecutionMode(str, Enum):
    """Task execution modes."""
    DIRECT = "direct"    # Execute immediately, no exploration
    COMPLEX = "complex"  # Explore first, then execute
    PLAN = "plan"        # Suggest entering plan mode first


@dataclass
class ClassificationResult:
    """Result of task complexity classification."""
    execution_mode: ExecutionMode
    suggest_plan: bool = False
    confidence: float = 1.0
    reason: str = ""


# Known direct execution patterns (fallback when ML model unavailable)
DIRECT_PATTERNS = [
    # Build commands
    "npm run", "npm build", "npm install", "npm start", "npm test",
    "yarn ", "pnpm ", "bun ",
    "make", "cmake", "cargo build", "cargo run", "cargo test",
    "go build", "go run", "go test",
    "python -m", "pip install", "pytest",
    "mvn ", "gradle ",
    # Service commands
    "restart", "stop", "start", "reload",
    "systemctl", "service ",
    "docker-compose up", "docker-compose down", "docker-compose restart",
    "docker run", "docker stop", "docker start",
    # Git operations
    "git push", "git pull", "git fetch", "git checkout", "git merge",
    "git commit", "git add", "git status", "git diff", "git log",
    # Simple file operations
    "create file", "delete file", "copy file", "move file",
    "touch ", "mkdir ", "rm ", "cp ", "mv ",
    # Status checks
    "check if", "show logs", "tail ", "cat ", "ls ", "ps ",
    "is running", "status of", "health check",
    # Network
    "curl ", "wget ", "ping ", "nc ", "telnet ",
]

# Known complex task patterns
COMPLEX_PATTERNS = [
    # Feature implementation
    "implement", "add feature", "create feature", "build feature",
    "develop", "design", "architect",
    # Refactoring
    "refactor", "restructure", "reorganize", "optimize", "improve",
    "clean up", "modernize", "migrate",
    # Debugging
    "debug", "investigate", "find bug", "fix bug", "troubleshoot",
    "diagnose", "analyze error", "root cause",
    # Architecture
    "integrate", "connect", "setup", "configure", "provision",
    # Research
    "research", "explore", "understand", "figure out", "learn about",
]

# Patterns that suggest entering plan mode (large multi-step tasks)
PLAN_WORTHY_PATTERNS = [
    # Large features
    "new feature", "major feature", "complete feature",
    "full implementation", "end to end", "e2e",
    # System-wide changes
    "across the codebase", "entire system", "all files",
    "every component", "whole project", "full stack",
    # Architecture changes
    "new architecture", "redesign", "rewrite", "overhaul",
    "major refactor", "complete rewrite", "from scratch",
    # Migrations
    "migrate from", "migrate to", "upgrade from", "convert to",
    "replace all", "switch from",
    # Multi-component
    "frontend and backend", "client and server", "api and ui",
    "database and api", "multiple services",
    # Security/Critical
    "authentication system", "authorization", "security layer",
    "payment", "billing", "subscription",
    # Indicators of scope
    "step by step", "phases", "milestones", "roadmap",
    "breakdown", "plan for", "strategy for",
]

# Confidence thresholds
PLAN_SUGGESTION_THRESHOLD = 0.7  # Suggest plan if confidence above this


class TaskComplexityClassifier:
    """
    ML-based task complexity classification.

    Uses MFRouter-style matrix factorization to predict execution_mode
    based on learned task patterns. Falls back to pattern matching
    when ML model unavailable.
    """

    def __init__(self, redis: Any = None):
        self._classifier = None  # Lazy-loaded ML model
        self._redis = redis
        self._enabled = os.environ.get("TASK_CLASSIFIER_ENABLED", "true").lower() == "true"
        self._latency_budget_ms = LATENCY_BUDGET_MS
        self._cache: dict[str, tuple[ClassificationResult, float]] = {}
        self._use_ml = False  # Will be set True if ML model loads

    def _get_classifier(self):
        """Lazy-load the ML classifier."""
        if self._classifier is None:
            if not CLASSIFIER_CONFIG_PATH or not os.path.exists(CLASSIFIER_CONFIG_PATH):
                logger.debug("Task classifier config not found, using pattern matching")
                return None

            try:
                from llmrouter.models.mfrouter.router import MFRouter
                self._classifier = MFRouter(yaml_path=CLASSIFIER_CONFIG_PATH)
                self._use_ml = True
                logger.info(f"Loaded task complexity classifier from {CLASSIFIER_CONFIG_PATH}")
            except ImportError:
                logger.debug("llmrouter not installed, using pattern matching")
                return None
            except Exception as e:
                logger.warning(f"Failed to load task classifier: {e}")
                return None
        return self._classifier

    async def classify(self, task_description: str) -> ExecutionMode:
        """
        Classify task complexity and return execution mode.
        Backward-compatible method that returns just the mode.

        Returns:
            ExecutionMode.DIRECT - Execute immediately
            ExecutionMode.COMPLEX - Explore/plan first
            ExecutionMode.PLAN - Suggest entering plan mode
        """
        result = await self.classify_full(task_description)
        return result.execution_mode

    async def classify_full(self, task_description: str) -> ClassificationResult:
        """
        Full classification with plan suggestions.

        Returns ClassificationResult with:
        - execution_mode: DIRECT, COMPLEX, or PLAN
        - suggest_plan: Whether to suggest entering plan mode
        - confidence: Classification confidence (0-1)
        - reason: Why this classification was chosen
        """
        if not self._enabled:
            return ClassificationResult(
                execution_mode=ExecutionMode.COMPLEX,
                suggest_plan=False,
                confidence=1.0,
                reason="Classifier disabled, defaulting to complex"
            )

        # Check cache
        cache_key = self._compute_cache_key(task_description)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Try ML classification first
        try:
            result = await self._classify_with_timeout(task_description)
            self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logger.debug(f"ML classification failed, using patterns: {e}")
            result = self._classify_by_patterns(task_description)
            self._cache_result(cache_key, result)
            return result

    async def _classify_with_timeout(self, task_description: str) -> ClassificationResult:
        """Run ML classification with timeout."""
        classifier = self._get_classifier()

        if classifier is None or not self._use_ml:
            return self._classify_by_patterns(task_description)

        result = await asyncio.wait_for(
            asyncio.to_thread(classifier.route_single, {"query": task_description}),
            timeout=self._latency_budget_ms / 1000,
        )

        # Map model name to execution mode
        model_name = result.get("model_name", "complex")
        confidence = result.get("confidence", 0.8)
        mode = self._mode_from_model_name(model_name)

        # Check if we should suggest plan mode
        suggest_plan, plan_reason = self._check_plan_worthy(task_description)

        return ClassificationResult(
            execution_mode=ExecutionMode.PLAN if suggest_plan else mode,
            suggest_plan=suggest_plan,
            confidence=confidence,
            reason=plan_reason if suggest_plan else f"ML classified as {model_name}"
        )

    def _mode_from_model_name(self, model_name: str) -> ExecutionMode:
        """Map classifier output to ExecutionMode."""
        mapping = {
            "direct": ExecutionMode.DIRECT,
            "simple": ExecutionMode.DIRECT,
            "fast": ExecutionMode.DIRECT,
            "complex": ExecutionMode.COMPLEX,
            "explore": ExecutionMode.COMPLEX,
            "powerful": ExecutionMode.COMPLEX,
            "plan": ExecutionMode.PLAN,
        }
        return mapping.get(model_name.lower(), ExecutionMode.COMPLEX)

    def _check_plan_worthy(self, task_description: str) -> tuple[bool, str]:
        """
        Check if a task warrants suggesting plan mode.

        Returns (should_suggest_plan, reason)
        """
        task_lower = task_description.lower().strip()

        # Check plan-worthy patterns
        matched_patterns = []
        for pattern in PLAN_WORTHY_PATTERNS:
            if pattern.lower() in task_lower:
                matched_patterns.append(pattern)

        if matched_patterns:
            reason = f"Task matches plan-worthy patterns: {', '.join(matched_patterns[:3])}"
            logger.debug(f"Suggesting plan mode: {reason}")
            return True, reason

        # Check task length/complexity heuristics
        words = task_lower.split()
        if len(words) > 30:
            return True, "Task description is lengthy, suggesting plan mode for clarity"

        # Multiple "and" connectors suggest multi-part task
        if task_lower.count(" and ") >= 3:
            return True, "Task has multiple components connected with 'and'"

        # Questions about approach suggest planning needed
        planning_questions = ["how should", "what's the best way", "how do i", "where should"]
        for q in planning_questions:
            if q in task_lower:
                return True, f"Task is asking for approach guidance: '{q}'"

        return False, ""

    def _classify_by_patterns(self, task_description: str) -> ClassificationResult:
        """
        Fallback pattern-based classification.

        Checks for known direct execution patterns first, then complex patterns.
        Defaults to COMPLEX for ambiguous tasks (safer to explore).
        """
        task_lower = task_description.lower().strip()

        # First check if this is plan-worthy (overrides other classifications)
        suggest_plan, plan_reason = self._check_plan_worthy(task_description)
        if suggest_plan:
            return ClassificationResult(
                execution_mode=ExecutionMode.PLAN,
                suggest_plan=True,
                confidence=0.85,
                reason=plan_reason
            )

        # Check direct patterns first
        for pattern in DIRECT_PATTERNS:
            if pattern.lower() in task_lower:
                logger.debug(f"Task matched direct pattern: {pattern}")
                return ClassificationResult(
                    execution_mode=ExecutionMode.DIRECT,
                    suggest_plan=False,
                    confidence=0.9,
                    reason=f"Matched direct pattern: {pattern}"
                )

        # Check complex patterns
        for pattern in COMPLEX_PATTERNS:
            if pattern.lower() in task_lower:
                logger.debug(f"Task matched complex pattern: {pattern}")
                return ClassificationResult(
                    execution_mode=ExecutionMode.COMPLEX,
                    suggest_plan=False,
                    confidence=0.85,
                    reason=f"Matched complex pattern: {pattern}"
                )

        # Short tasks without exploration keywords -> likely direct
        words = task_lower.split()
        if len(words) <= 5 and not any(p in task_lower for p in ["how", "why", "what", "should"]):
            # Very short imperative commands
            if words and words[0] in ["run", "execute", "start", "stop", "restart", "build", "test"]:
                return ClassificationResult(
                    execution_mode=ExecutionMode.DIRECT,
                    suggest_plan=False,
                    confidence=0.8,
                    reason="Short imperative command"
                )

        # Default to complex (safer - explores before executing)
        return ClassificationResult(
            execution_mode=ExecutionMode.COMPLEX,
            suggest_plan=False,
            confidence=0.6,
            reason="No pattern match, defaulting to complex for safety"
        )

    def classify_sync(self, task_description: str) -> ExecutionMode:
        """Synchronous classification using patterns only. Returns just the mode."""
        result = self.classify_full_sync(task_description)
        return result.execution_mode

    def classify_full_sync(self, task_description: str) -> ClassificationResult:
        """Synchronous full classification using patterns only."""
        # Check cache first
        cache_key = self._compute_cache_key(task_description)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result = self._classify_by_patterns(task_description)
        self._cache_result(cache_key, result)
        return result

    def _compute_cache_key(self, task_description: str) -> str:
        """Compute cache key from task description."""
        return hashlib.sha256(task_description.lower().encode()).hexdigest()[:16]

    def _get_cached(self, key: str) -> ClassificationResult | None:
        """Get cached classification if still valid."""
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < CACHE_TTL:
                return result
            del self._cache[key]
        return None

    def _cache_result(self, key: str, result: ClassificationResult):
        """Cache a classification result."""
        if len(self._cache) > 1000:
            cutoff = time.time() - CACHE_TTL
            self._cache = {k: v for k, v in self._cache.items() if v[1] > cutoff}
        self._cache[key] = (result, time.time())


# Global singleton
_task_classifier: TaskComplexityClassifier | None = None


def get_task_classifier(redis: Any = None) -> TaskComplexityClassifier:
    """Get or create the global TaskComplexityClassifier instance."""
    global _task_classifier
    if _task_classifier is None:
        _task_classifier = TaskComplexityClassifier(redis=redis)
    return _task_classifier
