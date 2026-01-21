"""
Code Agent tools - file, git, and code analysis operations.
"""

from .file_tools import (
    delete_file,
    list_directory,
    read_file,
    search_files,
    write_file,
)
from .git_tools import (
    git_add,
    git_branch,
    git_checkout,
    git_commit,
    git_diff,
    git_log,
    git_pull,
    git_push,
    git_status,
)
from .code_analysis_tools import (
    code_search,
    find_definition,
    find_references,
    get_python_imports,
    get_package_dependencies,
    count_lines,
)

__all__ = [
    # File tools
    "read_file",
    "write_file",
    "list_directory",
    "search_files",
    "delete_file",
    # Git tools
    "git_status",
    "git_diff",
    "git_log",
    "git_add",
    "git_commit",
    "git_branch",
    "git_checkout",
    "git_pull",
    "git_push",
    # Code analysis tools
    "code_search",
    "find_definition",
    "find_references",
    "get_python_imports",
    "get_package_dependencies",
    "count_lines",
]
