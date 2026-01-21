"""
GitHub and package registry tools for the Research Agent.

These tools provide:
- GitHub repository search and exploration
- PyPI package search
- NPM package search
- Package version checking
"""

import asyncio
import json
import os
from typing import Any

from ai_core import CapabilityCategory, get_logger
from base_agent import ToolResult, tool

logger = get_logger(__name__)

# GitHub API token (optional, increases rate limits)
GITHUB_TOKEN = os.environ.get("GITHUB_PAT", "")


async def _fetch_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, dict | list | None]:
    """Fetch JSON from a URL using aiohttp."""
    try:
        import aiohttp

        default_headers = {
            "User-Agent": "AI-Infrastructure-Research-Agent",
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers=default_headers,
        ) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return response.status, await response.json()
                else:
                    return response.status, None
    except Exception as e:
        logger.warning("Fetch JSON failed", url=url, error=str(e))
        return 0, None


@tool(
    name="github_search_repos",
    description="""Search GitHub repositories by query.
    Returns repository information including stars, forks, and description.""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g., 'fastapi python', 'machine learning')",
            },
            "language": {
                "type": "string",
                "description": "Filter by programming language",
            },
            "sort": {
                "type": "string",
                "enum": ["stars", "forks", "updated", "best-match"],
                "description": "Sort order",
                "default": "best-match",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 10,
            },
        },
        "required": ["query"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def github_search_repos(
    query: str,
    language: str | None = None,
    sort: str = "best-match",
    limit: int = 10,
) -> ToolResult:
    """Search GitHub repositories."""
    try:
        # Build search query
        search_query = query
        if language:
            search_query += f" language:{language}"

        # Build URL
        url = f"https://api.github.com/search/repositories?q={search_query}&per_page={min(limit, 30)}"
        if sort and sort != "best-match":
            url += f"&sort={sort}"

        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        status, data = await _fetch_json(url, headers)

        if status != 200 or not data:
            return ToolResult.fail(f"GitHub API request failed with status {status}")

        repos = []
        for item in data.get("items", [])[:limit]:
            repos.append({
                "name": item.get("full_name"),
                "description": (item.get("description") or "")[:200],
                "url": item.get("html_url"),
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "language": item.get("language"),
                "updated_at": item.get("updated_at"),
                "topics": item.get("topics", [])[:5],
            })

        return ToolResult.ok({
            "message": f"Found {len(repos)} repositories for '{query}'",
            "query": query,
            "repositories": repos,
            "count": len(repos),
            "total_count": data.get("total_count", 0),
        })

    except Exception as e:
        logger.error("GitHub search failed", query=query, error=str(e))
        return ToolResult.fail(f"GitHub search failed: {e}")


@tool(
    name="github_get_repo",
    description="""Get detailed information about a specific GitHub repository.""",
    parameters={
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner (username or org)",
            },
            "repo": {
                "type": "string",
                "description": "Repository name",
            },
        },
        "required": ["owner", "repo"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def github_get_repo(owner: str, repo: str) -> ToolResult:
    """Get GitHub repository details."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"

        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        status, data = await _fetch_json(url, headers)

        if status == 404:
            return ToolResult.fail(f"Repository {owner}/{repo} not found")
        if status != 200 or not data:
            return ToolResult.fail(f"GitHub API request failed with status {status}")

        repo_info = {
            "name": data.get("full_name"),
            "description": data.get("description"),
            "url": data.get("html_url"),
            "homepage": data.get("homepage"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "watchers": data.get("watchers_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "language": data.get("language"),
            "license": data.get("license", {}).get("name") if data.get("license") else None,
            "topics": data.get("topics", []),
            "default_branch": data.get("default_branch"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "pushed_at": data.get("pushed_at"),
            "size_kb": data.get("size", 0),
        }

        return ToolResult.ok({
            "message": f"Retrieved info for {owner}/{repo}",
            "repository": repo_info,
        })

    except Exception as e:
        logger.error("Get repo failed", owner=owner, repo=repo, error=str(e))
        return ToolResult.fail(f"Get repo failed: {e}")


@tool(
    name="github_get_readme",
    description="""Get the README content of a GitHub repository.""",
    parameters={
        "type": "object",
        "properties": {
            "owner": {
                "type": "string",
                "description": "Repository owner",
            },
            "repo": {
                "type": "string",
                "description": "Repository name",
            },
        },
        "required": ["owner", "repo"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def github_get_readme(owner: str, repo: str) -> ToolResult:
    """Get GitHub repository README."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"

        headers = {"Accept": "application/vnd.github.raw"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        import aiohttp

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 404:
                    return ToolResult.fail(f"README not found for {owner}/{repo}")
                if response.status != 200:
                    return ToolResult.fail(f"GitHub API failed with status {response.status}")

                content = await response.text()

        # Truncate if too long
        if len(content) > 10000:
            content = content[:10000] + "\n\n... (truncated)"

        return ToolResult.ok({
            "message": f"Retrieved README for {owner}/{repo}",
            "owner": owner,
            "repo": repo,
            "content": content,
            "length": len(content),
        })

    except Exception as e:
        logger.error("Get README failed", owner=owner, repo=repo, error=str(e))
        return ToolResult.fail(f"Get README failed: {e}")


@tool(
    name="pypi_search",
    description="""Search PyPI for Python packages.""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Package search query",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 10,
            },
        },
        "required": ["query"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def pypi_search(query: str, limit: int = 10) -> ToolResult:
    """Search PyPI for packages."""
    try:
        # PyPI doesn't have a great search API, so we use the simple endpoint
        # and search by package name
        url = f"https://pypi.org/pypi/{query}/json"

        status, data = await _fetch_json(url)

        if status == 404:
            # Try search endpoint
            search_url = f"https://pypi.org/search/?q={query}"
            return ToolResult.ok({
                "message": f"Package '{query}' not found. Try searching at: {search_url}",
                "query": query,
                "packages": [],
                "count": 0,
                "search_url": search_url,
            })

        if status != 200 or not data:
            return ToolResult.fail(f"PyPI API request failed with status {status}")

        info = data.get("info", {})
        releases = data.get("releases", {})

        # Get latest versions
        versions = sorted(releases.keys(), reverse=True)[:5]

        package = {
            "name": info.get("name"),
            "version": info.get("version"),
            "summary": info.get("summary"),
            "author": info.get("author"),
            "license": info.get("license"),
            "homepage": info.get("home_page"),
            "project_url": info.get("project_url"),
            "requires_python": info.get("requires_python"),
            "keywords": info.get("keywords"),
            "classifiers": info.get("classifiers", [])[:5],
            "recent_versions": versions,
        }

        return ToolResult.ok({
            "message": f"Found package '{query}' on PyPI",
            "query": query,
            "package": package,
        })

    except Exception as e:
        logger.error("PyPI search failed", query=query, error=str(e))
        return ToolResult.fail(f"PyPI search failed: {e}")


@tool(
    name="npm_search",
    description="""Search NPM for JavaScript/TypeScript packages.""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Package search query",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results",
                "default": 10,
            },
        },
        "required": ["query"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def npm_search(query: str, limit: int = 10) -> ToolResult:
    """Search NPM for packages."""
    try:
        url = f"https://registry.npmjs.org/-/v1/search?text={query}&size={min(limit, 20)}"

        status, data = await _fetch_json(url)

        if status != 200 or not data:
            return ToolResult.fail(f"NPM API request failed with status {status}")

        packages = []
        for obj in data.get("objects", [])[:limit]:
            pkg = obj.get("package", {})
            packages.append({
                "name": pkg.get("name"),
                "version": pkg.get("version"),
                "description": (pkg.get("description") or "")[:200],
                "keywords": pkg.get("keywords", [])[:5],
                "author": pkg.get("author", {}).get("name") if isinstance(pkg.get("author"), dict) else pkg.get("author"),
                "npm_url": f"https://www.npmjs.com/package/{pkg.get('name')}",
                "score": obj.get("score", {}).get("final", 0),
            })

        return ToolResult.ok({
            "message": f"Found {len(packages)} packages for '{query}'",
            "query": query,
            "packages": packages,
            "count": len(packages),
            "total": data.get("total", 0),
        })

    except Exception as e:
        logger.error("NPM search failed", query=query, error=str(e))
        return ToolResult.fail(f"NPM search failed: {e}")


@tool(
    name="npm_get_package",
    description="""Get detailed information about a specific NPM package.""",
    parameters={
        "type": "object",
        "properties": {
            "package_name": {
                "type": "string",
                "description": "NPM package name",
            },
        },
        "required": ["package_name"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def npm_get_package(package_name: str) -> ToolResult:
    """Get NPM package details."""
    try:
        url = f"https://registry.npmjs.org/{package_name}"

        status, data = await _fetch_json(url)

        if status == 404:
            return ToolResult.fail(f"Package '{package_name}' not found on NPM")
        if status != 200 or not data:
            return ToolResult.fail(f"NPM API request failed with status {status}")

        # Get latest version info
        latest_version = data.get("dist-tags", {}).get("latest")
        versions = list(data.get("versions", {}).keys())
        versions.sort(reverse=True)

        latest_info = data.get("versions", {}).get(latest_version, {})

        package = {
            "name": data.get("name"),
            "description": data.get("description"),
            "latest_version": latest_version,
            "license": latest_info.get("license"),
            "homepage": latest_info.get("homepage"),
            "repository": latest_info.get("repository", {}).get("url") if isinstance(latest_info.get("repository"), dict) else None,
            "keywords": latest_info.get("keywords", [])[:10],
            "dependencies": list(latest_info.get("dependencies", {}).keys())[:20],
            "dev_dependencies": list(latest_info.get("devDependencies", {}).keys())[:10],
            "recent_versions": versions[:10],
            "maintainers": [m.get("name") for m in data.get("maintainers", [])][:5],
        }

        return ToolResult.ok({
            "message": f"Retrieved info for NPM package '{package_name}'",
            "package": package,
        })

    except Exception as e:
        logger.error("Get NPM package failed", package=package_name, error=str(e))
        return ToolResult.fail(f"Get NPM package failed: {e}")


@tool(
    name="check_package_versions",
    description="""Check available versions for a Python or NPM package.""",
    parameters={
        "type": "object",
        "properties": {
            "package_name": {
                "type": "string",
                "description": "Package name",
            },
            "registry": {
                "type": "string",
                "enum": ["pypi", "npm"],
                "description": "Package registry",
                "default": "pypi",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum versions to return",
                "default": 20,
            },
        },
        "required": ["package_name"],
    },
    permission_level=0,
    capability_category=CapabilityCategory.WEB,
)
async def check_package_versions(
    package_name: str,
    registry: str = "pypi",
    limit: int = 20,
) -> ToolResult:
    """Check package versions."""
    try:
        if registry == "pypi":
            url = f"https://pypi.org/pypi/{package_name}/json"
            status, data = await _fetch_json(url)

            if status == 404:
                return ToolResult.fail(f"Package '{package_name}' not found on PyPI")
            if status != 200 or not data:
                return ToolResult.fail(f"PyPI API failed with status {status}")

            releases = data.get("releases", {})
            versions = sorted(releases.keys(), reverse=True)[:limit]

            version_info = []
            for v in versions:
                release_files = releases.get(v, [])
                if release_files:
                    upload_time = release_files[0].get("upload_time", "")
                    version_info.append({
                        "version": v,
                        "upload_time": upload_time,
                    })
                else:
                    version_info.append({"version": v})

            return ToolResult.ok({
                "message": f"Found {len(versions)} versions for '{package_name}' on PyPI",
                "package": package_name,
                "registry": "pypi",
                "latest": data.get("info", {}).get("version"),
                "versions": version_info,
                "count": len(versions),
            })

        else:  # npm
            url = f"https://registry.npmjs.org/{package_name}"
            status, data = await _fetch_json(url)

            if status == 404:
                return ToolResult.fail(f"Package '{package_name}' not found on NPM")
            if status != 200 or not data:
                return ToolResult.fail(f"NPM API failed with status {status}")

            versions = sorted(data.get("versions", {}).keys(), reverse=True)[:limit]
            dist_tags = data.get("dist-tags", {})

            return ToolResult.ok({
                "message": f"Found {len(versions)} versions for '{package_name}' on NPM",
                "package": package_name,
                "registry": "npm",
                "latest": dist_tags.get("latest"),
                "dist_tags": dist_tags,
                "versions": versions,
                "count": len(versions),
            })

    except Exception as e:
        logger.error("Check versions failed", package=package_name, error=str(e))
        return ToolResult.fail(f"Check versions failed: {e}")
