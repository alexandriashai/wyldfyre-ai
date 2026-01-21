"""
Research Agent tools.
"""

from .documentation_tools import (
    create_documentation,
    read_documentation,
    search_documentation,
    update_documentation,
)
from .web_tools import (
    fetch_url,
    search_web,
    summarize_page,
)
from .github_tools import (
    github_search_repos,
    github_get_repo,
    github_get_readme,
    pypi_search,
    npm_search,
    npm_get_package,
    check_package_versions,
)

__all__ = [
    # Web tools
    "search_web",
    "fetch_url",
    "summarize_page",
    # Documentation tools
    "search_documentation",
    "read_documentation",
    "create_documentation",
    "update_documentation",
    # GitHub tools
    "github_search_repos",
    "github_get_repo",
    "github_get_readme",
    # Package registry tools
    "pypi_search",
    "npm_search",
    "npm_get_package",
    "check_package_versions",
]
