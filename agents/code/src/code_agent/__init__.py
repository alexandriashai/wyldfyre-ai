"""
Code Agent - Git and file operations specialist.

Handles:
- Git operations (clone, commit, push, pull, branch)
- File operations (read, write, search)
- Code analysis
- Test execution
"""

from .agent import CodeAgent

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "CodeAgent",
]
