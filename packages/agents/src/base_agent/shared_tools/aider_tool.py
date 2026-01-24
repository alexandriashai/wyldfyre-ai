"""
Aider integration tool for AI agents.

Provides multi-file code editing with repo mapping, git integration,
and automatic linting/testing via Aider's Python API.
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from ai_core import CapabilityCategory, ModelTier, get_logger, get_settings

from base_agent import ToolResult, tool

logger = get_logger(__name__)

# Map platform tiers to Aider-compatible model names
TIER_TO_AIDER_MODEL = {
    ModelTier.FAST: "claude-haiku-4-20250514",
    ModelTier.BALANCED: "claude-sonnet-4-20250514",
    ModelTier.POWERFUL: "claude-opus-4-5-20251101",
}

# Env var fallbacks (used when Redis is unavailable)
_AIDER_ENABLED_DEFAULT = os.environ.get("AIDER_ENABLED", "true").lower() == "true"
_AIDER_DEFAULT_MODEL_DEFAULT = os.environ.get("AIDER_DEFAULT_MODEL", "claude-sonnet-4-20250514")
_AIDER_MAP_TOKENS_DEFAULT = int(os.environ.get("AIDER_MAP_TOKENS", "2048"))
_AIDER_EDIT_FORMAT_DEFAULT = os.environ.get("AIDER_EDIT_FORMAT", "diff")


async def _load_aider_config() -> dict[str, Any]:
    """Load Aider config from Redis, falling back to env vars."""
    config = {
        "enabled": _AIDER_ENABLED_DEFAULT,
        "default_model": _AIDER_DEFAULT_MODEL_DEFAULT,
        "map_tokens": _AIDER_MAP_TOKENS_DEFAULT,
        "edit_format": _AIDER_EDIT_FORMAT_DEFAULT,
    }
    try:
        from ai_messaging import get_redis_client
        redis = await get_redis_client()
        val = await redis.get("llm:aider_enabled")
        if val is not None:
            config["enabled"] = val == "1"
        val = await redis.get("llm:aider_default_model")
        if val is not None:
            config["default_model"] = val
        val = await redis.get("llm:aider_map_tokens")
        if val is not None:
            config["map_tokens"] = int(val)
        val = await redis.get("llm:aider_edit_format")
        if val is not None:
            config["edit_format"] = val
    except Exception:
        pass  # Use defaults if Redis unavailable
    return config


@tool(
    name="aider_code",
    description=(
        "Use Aider AI to make code changes across one or more files. "
        "Aider creates a repo map for context, edits files, auto-commits, "
        "and runs linting/testing. Best for multi-file edits and refactoring."
    ),
    capability_category=CapabilityCategory.CODE,
    permission_level=1,
    side_effects=True,
)
async def aider_code(
    instruction: str,
    files: list[str],
    root_path: str,
    model_tier: str = "auto",
    auto_commit: bool = True,
    lint: bool = True,
    test_cmd: str | None = None,
    edit_format: str | None = None,
) -> ToolResult:
    """
    Execute a coding task using Aider.

    Args:
        instruction: Natural language description of what to do
        files: List of file paths (relative to root_path) to edit
        root_path: Project root directory
        model_tier: "fast", "balanced", "powerful", or "auto"
        auto_commit: Whether to auto-commit changes
        lint: Whether to run linting after changes
        test_cmd: Optional test command to run after changes
        edit_format: Edit format - "diff", "udiff", or "whole" (defaults to env config)

    Returns:
        ToolResult with files changed, diff, and commit info
    """
    # Load runtime config from Redis (with env var fallback)
    aider_config = await _load_aider_config()

    if not aider_config["enabled"]:
        return ToolResult.fail("Aider tool is disabled")

    root = Path(root_path)
    if not root.exists():
        return ToolResult.fail(f"Root path does not exist: {root_path}")

    if not files:
        return ToolResult.fail("No files specified for editing")

    # Resolve absolute file paths
    abs_files = []
    for f in files:
        fp = root / f if not Path(f).is_absolute() else Path(f)
        abs_files.append(str(fp))

    # Determine model
    settings = get_settings()
    api_key = settings.api.anthropic_api_key.get_secret_value()

    if model_tier == "auto":
        model_name = aider_config["default_model"]
    elif model_tier in ("fast", "balanced", "powerful"):
        model_name = TIER_TO_AIDER_MODEL[ModelTier(model_tier)]
    else:
        model_name = model_tier  # Allow direct model name

    effective_edit_format = edit_format or aider_config["edit_format"]

    try:
        result = await asyncio.to_thread(
            _run_aider,
            instruction=instruction,
            files=abs_files,
            root_path=str(root),
            model_name=model_name,
            api_key=api_key,
            auto_commit=auto_commit,
            lint=lint,
            test_cmd=test_cmd,
            edit_format=effective_edit_format,
            map_tokens=aider_config["map_tokens"],
        )
        return ToolResult.ok(result)
    except Exception as e:
        logger.error("Aider execution failed", error=str(e))
        return ToolResult.fail(f"Aider error: {str(e)}")


def _run_aider(
    instruction: str,
    files: list[str],
    root_path: str,
    model_name: str,
    api_key: str,
    auto_commit: bool,
    lint: bool,
    test_cmd: str | None,
    edit_format: str,
    map_tokens: int = 2048,
) -> dict[str, Any]:
    """Run Aider synchronously (called in thread)."""
    from aider.coders import Coder
    from aider.io import InputOutput
    from aider.models import Model

    # Set API key in environment for Aider
    os.environ["ANTHROPIC_API_KEY"] = api_key

    # Configure Aider
    io = InputOutput(yes=True)  # Non-interactive mode
    model = Model(model_name)

    # Create coder with project context
    coder = Coder.create(
        main_model=model,
        fnames=files,
        io=io,
        auto_commits=auto_commit,
        dirty_commits=auto_commit,
        edit_format=edit_format,
        use_git=True,
        git_root=root_path,
        map_tokens=map_tokens,
        stream=False,
    )

    # Run the instruction
    result_text = coder.run(instruction)

    # Gather results
    output: dict[str, Any] = {
        "response": result_text,
        "files_changed": list(coder.aider_edited_files) if hasattr(coder, "aider_edited_files") else [],
        "auto_committed": auto_commit,
    }

    # Get git diff of changes
    try:
        diff_result = subprocess.run(
            ["git", "diff", "HEAD~1", "--stat"],
            cwd=root_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if diff_result.returncode == 0:
            output["diff_stat"] = diff_result.stdout
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Get last commit hash if auto-committed
    if auto_commit:
        try:
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if hash_result.returncode == 0:
                output["commit_hash"] = hash_result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Run tests if specified
    if test_cmd:
        try:
            test_result = subprocess.run(
                test_cmd.split(),
                cwd=root_path,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output["test_result"] = {
                "passed": test_result.returncode == 0,
                "stdout": test_result.stdout[-2000:],  # Last 2000 chars
                "stderr": test_result.stderr[-1000:],
            }
        except subprocess.TimeoutExpired:
            output["test_result"] = {"passed": False, "error": "Test timed out"}
        except Exception as e:
            output["test_result"] = {"passed": False, "error": str(e)}

    return output
