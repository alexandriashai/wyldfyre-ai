"""
GitHub integration service.

Provides PAT resolution, encryption, and GitHub API operations.
PAT resolution chain: project override > Redis admin override > .env GITHUB_PAT
"""

import asyncio
import base64
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import aiohttp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ai_core import get_logger
from ai_messaging import RedisClient

logger = get_logger(__name__)

# Environment variables
ENCRYPTION_KEY_ENV = "CREDENTIAL_ENCRYPTION_KEY"
GITHUB_PAT_ENV = "GITHUB_PAT"

# Redis keys for global config
REDIS_GITHUB_ENABLED = "github:enabled"
REDIS_GITHUB_GLOBAL_PAT = "github:global_pat"
REDIS_GITHUB_GLOBAL_PAT_TS = "github:global_pat_ts"

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"


class GitHubEncryption:
    """Handles encryption/decryption of PAT values using Fernet."""

    _instance: "GitHubEncryption | None" = None
    _fernet: Fernet | None = None

    def __new__(cls) -> "GitHubEncryption":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize Fernet cipher with encryption key."""
        key = os.environ.get(ENCRYPTION_KEY_ENV)
        if not key:
            logger.warning(
                f"No {ENCRYPTION_KEY_ENV} found. GitHub PAT encryption will use ephemeral key."
            )
            key = Fernet.generate_key().decode()

        self._fernet = self._create_fernet(key)

    def _create_fernet(self, key: str) -> Fernet:
        """Create Fernet instance from a key string."""
        # Try using the key directly if it's a valid Fernet key
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            pass

        # Derive a proper Fernet key from the provided key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"github_pat_encryption",
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        return Fernet(derived_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a PAT and return base64-encoded ciphertext."""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext and return plaintext PAT."""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error("Failed to decrypt PAT", error=str(e))
            raise ValueError("Failed to decrypt PAT") from e


class GitHubService:
    """
    GitHub operations with PAT resolution and repo management.

    PAT Resolution Order:
    1. Project-specific PAT (encrypted in DB)
    2. Redis global PAT (admin override via UI)
    3. Environment GITHUB_PAT (from .env, auto-imported)
    """

    def __init__(self, redis: RedisClient):
        self.redis = redis
        self.encryption = GitHubEncryption()

    # === PAT Resolution ===

    async def get_effective_pat(
        self, project: Any | None = None
    ) -> str | None:
        """
        Resolve PAT with fallback chain.

        Args:
            project: Optional Project model with github_pat_encrypted

        Returns:
            Decrypted PAT or None if not configured
        """
        # 1. Check project override
        if project and project.github_pat_encrypted:
            try:
                return self.encryption.decrypt(project.github_pat_encrypted)
            except Exception as e:
                logger.warning("Failed to decrypt project PAT", error=str(e))

        # 2. Check Redis global PAT (admin override)
        try:
            redis_pat = await self.redis.get(REDIS_GITHUB_GLOBAL_PAT)
            if redis_pat:
                return self.encryption.decrypt(redis_pat)
        except Exception as e:
            logger.warning("Failed to get/decrypt Redis PAT", error=str(e))

        # 3. Fall back to environment variable
        env_pat = os.environ.get(GITHUB_PAT_ENV)
        if env_pat:
            return env_pat

        return None

    async def get_pat_source(self, project: Any | None = None) -> str | None:
        """
        Get the source of the effective PAT.

        Returns:
            "project" | "admin" | "env" | None
        """
        # 1. Check project override
        if project and project.github_pat_encrypted:
            return "project"

        # 2. Check Redis global PAT
        try:
            redis_pat = await self.redis.get(REDIS_GITHUB_GLOBAL_PAT)
            if redis_pat:
                return "admin"
        except Exception:
            pass

        # 3. Check environment variable
        if os.environ.get(GITHUB_PAT_ENV):
            return "env"

        return None

    def encrypt_pat(self, pat: str) -> str:
        """Encrypt a PAT for storage."""
        return self.encryption.encrypt(pat)

    # === Global Settings ===

    async def is_enabled(self) -> bool:
        """Check if GitHub integration is enabled."""
        try:
            enabled = await self.redis.get(REDIS_GITHUB_ENABLED)
            if enabled is not None:
                return enabled == "1"
        except Exception:
            pass
        # Default to enabled
        return True

    async def set_enabled(self, enabled: bool) -> None:
        """Set GitHub integration enabled state."""
        await self.redis.set(REDIS_GITHUB_ENABLED, "1" if enabled else "0")

    async def set_global_pat(self, pat: str) -> None:
        """Set global PAT (admin override)."""
        encrypted = self.encryption.encrypt(pat)
        await self.redis.set(REDIS_GITHUB_GLOBAL_PAT, encrypted)
        await self.redis.set(
            REDIS_GITHUB_GLOBAL_PAT_TS,
            datetime.now(timezone.utc).isoformat(),
        )
        logger.info("Global GitHub PAT updated via admin UI")

    async def clear_global_pat(self) -> None:
        """Clear global PAT (revert to .env)."""
        await self.redis.delete(REDIS_GITHUB_GLOBAL_PAT)
        await self.redis.delete(REDIS_GITHUB_GLOBAL_PAT_TS)
        logger.info("Global GitHub PAT cleared, reverting to .env")

    async def get_global_pat_timestamp(self) -> str | None:
        """Get timestamp when global PAT was last updated."""
        try:
            return await self.redis.get(REDIS_GITHUB_GLOBAL_PAT_TS)
        except Exception:
            return None

    # === Authenticated URL Generation ===

    def get_authenticated_url(self, url: str, pat: str) -> str:
        """
        Convert a GitHub URL to authenticated HTTPS URL.

        Examples:
            https://github.com/org/repo → https://x-access-token:PAT@github.com/org/repo
            git@github.com:org/repo.git → https://x-access-token:PAT@github.com/org/repo.git
        """
        # Handle SSH URLs
        ssh_match = re.match(r"git@github\.com:(.+)", url)
        if ssh_match:
            path = ssh_match.group(1)
            return f"https://x-access-token:{pat}@github.com/{path}"

        # Handle HTTPS URLs
        parsed = urlparse(url)
        if parsed.hostname in ("github.com", "www.github.com"):
            return f"https://x-access-token:{pat}@github.com{parsed.path}"

        # Return original if not a GitHub URL
        return url

    def strip_auth_from_url(self, url: str) -> str:
        """Remove authentication from a URL."""
        # Handle authenticated HTTPS URLs
        match = re.match(r"https://[^@]+@github\.com(.+)", url)
        if match:
            return f"https://github.com{match.group(1)}"
        return url

    # === GitHub API Client ===

    def _get_headers(self, pat: str) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        return {
            "Authorization": f"token {pat}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Wyld-Core-API",
        }

    async def test_pat(self, pat: str) -> dict[str, Any]:
        """
        Test a PAT against GitHub API.

        Returns:
            {success: bool, username: str | None, scopes: list | None, error: str | None}
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{GITHUB_API_BASE}/user",
                    headers=self._get_headers(pat),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        scopes = resp.headers.get("X-OAuth-Scopes", "").split(", ")
                        return {
                            "success": True,
                            "username": data.get("login"),
                            "scopes": [s for s in scopes if s],
                            "error": None,
                        }
                    elif resp.status == 401:
                        return {
                            "success": False,
                            "username": None,
                            "scopes": None,
                            "error": "Invalid or expired token",
                        }
                    else:
                        return {
                            "success": False,
                            "username": None,
                            "scopes": None,
                            "error": f"GitHub API error: {resp.status}",
                        }
        except Exception as e:
            logger.error("PAT test failed", error=str(e))
            return {
                "success": False,
                "username": None,
                "scopes": None,
                "error": str(e),
            }

    async def list_user_repos(
        self, pat: str, page: int = 1, per_page: int = 30
    ) -> list[dict[str, Any]]:
        """
        List repositories accessible by the PAT.

        Returns:
            List of repo objects with id, name, full_name, html_url, clone_url, private, description
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{GITHUB_API_BASE}/user/repos",
                    headers=self._get_headers(pat),
                    params={
                        "sort": "updated",
                        "direction": "desc",
                        "per_page": per_page,
                        "page": page,
                    },
                ) as resp:
                    if resp.status != 200:
                        logger.error("Failed to list repos", status=resp.status)
                        return []

                    repos = await resp.json()
                    return [
                        {
                            "id": r["id"],
                            "name": r["name"],
                            "full_name": r["full_name"],
                            "html_url": r["html_url"],
                            "clone_url": r["clone_url"],
                            "private": r["private"],
                            "description": r.get("description"),
                        }
                        for r in repos
                    ]
        except Exception as e:
            logger.error("Failed to list repos", error=str(e))
            return []

    async def create_repo(
        self,
        pat: str,
        name: str,
        description: str | None = None,
        private: bool = True,
    ) -> dict[str, Any] | None:
        """
        Create a new GitHub repository.

        Returns:
            Repo object or None on failure
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GITHUB_API_BASE}/user/repos",
                    headers=self._get_headers(pat),
                    json={
                        "name": name,
                        "description": description,
                        "private": private,
                        "auto_init": False,
                    },
                ) as resp:
                    if resp.status not in (200, 201):
                        error = await resp.json()
                        logger.error(
                            "Failed to create repo",
                            status=resp.status,
                            error=error,
                        )
                        return None

                    repo = await resp.json()
                    return {
                        "id": repo["id"],
                        "name": repo["name"],
                        "full_name": repo["full_name"],
                        "html_url": repo["html_url"],
                        "clone_url": repo["clone_url"],
                        "private": repo["private"],
                        "description": repo.get("description"),
                    }
        except Exception as e:
            logger.error("Failed to create repo", error=str(e))
            return None

    async def get_repo(self, pat: str, owner: str, repo: str) -> dict[str, Any] | None:
        """Get repository information."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}",
                    headers=self._get_headers(pat),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return {
                        "id": data["id"],
                        "name": data["name"],
                        "full_name": data["full_name"],
                        "html_url": data["html_url"],
                        "clone_url": data["clone_url"],
                        "private": data["private"],
                        "description": data.get("description"),
                        "default_branch": data.get("default_branch", "main"),
                    }
        except Exception as e:
            logger.error("Failed to get repo", error=str(e))
            return None

    # === Pull Request Operations ===

    async def list_pull_requests(
        self,
        pat: str,
        owner: str,
        repo: str,
        state: str = "open",
    ) -> list[dict[str, Any]]:
        """List pull requests for a repository."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
                    headers=self._get_headers(pat),
                    params={"state": state, "per_page": 30},
                ) as resp:
                    if resp.status != 200:
                        return []
                    prs = await resp.json()
                    return [
                        {
                            "number": pr["number"],
                            "title": pr["title"],
                            "body": pr.get("body"),
                            "state": pr["state"],
                            "head": pr["head"]["ref"],
                            "base": pr["base"]["ref"],
                            "html_url": pr["html_url"],
                            "created_at": pr["created_at"],
                            "user": pr["user"]["login"],
                            "mergeable": pr.get("mergeable"),
                            "draft": pr.get("draft", False),
                        }
                        for pr in prs
                    ]
        except Exception as e:
            logger.error("Failed to list PRs", error=str(e))
            return []

    async def create_pull_request(
        self,
        pat: str,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str = "main",
        body: str | None = None,
        draft: bool = False,
    ) -> dict[str, Any] | None:
        """Create a pull request."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls",
                    headers=self._get_headers(pat),
                    json={
                        "title": title,
                        "head": head,
                        "base": base,
                        "body": body,
                        "draft": draft,
                    },
                ) as resp:
                    if resp.status not in (200, 201):
                        error = await resp.json()
                        logger.error("Failed to create PR", error=error)
                        return None
                    pr = await resp.json()
                    return {
                        "number": pr["number"],
                        "title": pr["title"],
                        "body": pr.get("body"),
                        "state": pr["state"],
                        "head": pr["head"]["ref"],
                        "base": pr["base"]["ref"],
                        "html_url": pr["html_url"],
                        "created_at": pr["created_at"],
                        "user": pr["user"]["login"],
                        "mergeable": pr.get("mergeable"),
                        "draft": pr.get("draft", False),
                    }
        except Exception as e:
            logger.error("Failed to create PR", error=str(e))
            return None

    async def get_pull_request(
        self, pat: str, owner: str, repo: str, number: int
    ) -> dict[str, Any] | None:
        """Get pull request details."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{number}",
                    headers=self._get_headers(pat),
                ) as resp:
                    if resp.status != 200:
                        return None
                    pr = await resp.json()
                    return {
                        "number": pr["number"],
                        "title": pr["title"],
                        "body": pr.get("body"),
                        "state": pr["state"],
                        "head": pr["head"]["ref"],
                        "base": pr["base"]["ref"],
                        "html_url": pr["html_url"],
                        "created_at": pr["created_at"],
                        "user": pr["user"]["login"],
                        "mergeable": pr.get("mergeable"),
                        "draft": pr.get("draft", False),
                        "merged": pr.get("merged", False),
                        "merge_commit_sha": pr.get("merge_commit_sha"),
                        "comments": pr.get("comments", 0),
                        "review_comments": pr.get("review_comments", 0),
                        "commits": pr.get("commits", 0),
                        "additions": pr.get("additions", 0),
                        "deletions": pr.get("deletions", 0),
                        "changed_files": pr.get("changed_files", 0),
                    }
        except Exception as e:
            logger.error("Failed to get PR", error=str(e))
            return None

    async def merge_pull_request(
        self,
        pat: str,
        owner: str,
        repo: str,
        number: int,
        merge_method: str = "merge",
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        """
        Merge a pull request.

        Args:
            merge_method: "merge", "squash", or "rebase"

        Returns:
            {success: bool, sha: str | None, message: str}
        """
        try:
            async with aiohttp.ClientSession() as session:
                body: dict[str, Any] = {"merge_method": merge_method}
                if commit_message:
                    body["commit_message"] = commit_message

                async with session.put(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{number}/merge",
                    headers=self._get_headers(pat),
                    json=body,
                ) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        return {
                            "success": True,
                            "sha": data.get("sha"),
                            "message": data.get("message", "Pull request merged"),
                        }
                    else:
                        return {
                            "success": False,
                            "sha": None,
                            "message": data.get("message", "Merge failed"),
                        }
        except Exception as e:
            logger.error("Failed to merge PR", error=str(e))
            return {"success": False, "sha": None, "message": str(e)}

    # === Issue Operations ===

    async def list_issues(
        self,
        pat: str,
        owner: str,
        repo: str,
        state: str = "open",
        labels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List issues for a repository."""
        try:
            params: dict[str, Any] = {"state": state, "per_page": 30}
            if labels:
                params["labels"] = ",".join(labels)

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
                    headers=self._get_headers(pat),
                    params=params,
                ) as resp:
                    if resp.status != 200:
                        return []
                    issues = await resp.json()
                    # Filter out pull requests (they appear in issues API)
                    return [
                        {
                            "number": issue["number"],
                            "title": issue["title"],
                            "body": issue.get("body"),
                            "state": issue["state"],
                            "html_url": issue["html_url"],
                            "created_at": issue["created_at"],
                            "user": issue["user"]["login"],
                            "labels": [l["name"] for l in issue.get("labels", [])],
                            "comments": issue.get("comments", 0),
                        }
                        for issue in issues
                        if "pull_request" not in issue
                    ]
        except Exception as e:
            logger.error("Failed to list issues", error=str(e))
            return []

    async def create_issue(
        self,
        pat: str,
        owner: str,
        repo: str,
        title: str,
        body: str | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Create an issue."""
        try:
            data: dict[str, Any] = {"title": title}
            if body:
                data["body"] = body
            if labels:
                data["labels"] = labels

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
                    headers=self._get_headers(pat),
                    json=data,
                ) as resp:
                    if resp.status not in (200, 201):
                        return None
                    issue = await resp.json()
                    return {
                        "number": issue["number"],
                        "title": issue["title"],
                        "body": issue.get("body"),
                        "state": issue["state"],
                        "html_url": issue["html_url"],
                        "created_at": issue["created_at"],
                        "user": issue["user"]["login"],
                        "labels": [l["name"] for l in issue.get("labels", [])],
                    }
        except Exception as e:
            logger.error("Failed to create issue", error=str(e))
            return None

    # === Utility Methods ===

    @staticmethod
    def parse_repo_url(url: str) -> tuple[str, str] | None:
        """
        Extract owner and repo from a GitHub URL.

        Returns:
            (owner, repo) tuple or None if not a valid GitHub URL
        """
        patterns = [
            r"github\.com[:/]([^/]+)/([^/.]+)",
            r"github\.com[:/]([^/]+)/([^/]+)\.git",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2).rstrip(".git")
        return None


# Dependency for FastAPI
async def get_github_service(redis: RedisClient) -> GitHubService:
    """Get GitHub service instance."""
    return GitHubService(redis)
