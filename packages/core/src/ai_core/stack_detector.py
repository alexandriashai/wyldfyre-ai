"""
Project Stack Detector.

Automatically detects the technology stack of a project by analyzing:
- Environment files (.env, .env.local, .env.production)
- Docker configuration (docker-compose.yml, Dockerfile)
- Package manifests (package.json, requirements.txt, pyproject.toml)
- Config files (database configs, framework configs)

This helps agents understand the project context before taking actions,
preventing issues like using the wrong database type.
"""

import os
import re
import json
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class DatabaseConfig:
    """Detected database configuration."""
    type: str  # mysql, postgresql, sqlite, mongodb, redis, etc.
    host: str = "localhost"
    port: int = 0
    database: str = ""
    container_name: str = ""
    version: str = ""
    connection_string: str = ""
    source: str = ""  # Where this was detected from

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "container_name": self.container_name,
            "version": self.version,
            "source": self.source,
        }


@dataclass
class ProjectStack:
    """Complete project technology stack."""
    # Project info
    project_path: str = ""
    project_name: str = ""

    # Primary database
    database: DatabaseConfig | None = None

    # Additional databases (cache, queue, etc.)
    redis: DatabaseConfig | None = None
    cache: DatabaseConfig | None = None

    # Framework and language
    language: str = ""  # python, javascript, typescript, go, etc.
    framework: str = ""  # fastapi, django, flask, express, nextjs, etc.
    runtime_version: str = ""

    # Container info
    uses_docker: bool = False
    docker_compose_file: str = ""
    containers: list[str] = field(default_factory=list)

    # Package manager
    package_manager: str = ""  # pip, npm, yarn, pnpm, poetry, etc.

    # Detection metadata
    detection_sources: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1 confidence in detection

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_path": self.project_path,
            "database": self.database.to_dict() if self.database else None,
            "redis": self.redis.to_dict() if self.redis else None,
            "language": self.language,
            "framework": self.framework,
            "runtime_version": self.runtime_version,
            "uses_docker": self.uses_docker,
            "docker_compose_file": self.docker_compose_file,
            "containers": self.containers,
            "package_manager": self.package_manager,
            "detection_sources": self.detection_sources,
            "confidence": self.confidence,
        }

    def summary(self) -> str:
        """Generate a human-readable summary."""
        parts = []
        if self.project_name:
            parts.append(f"Project: {self.project_name}")
        if self.language:
            parts.append(f"Language: {self.language}")
        if self.framework:
            parts.append(f"Framework: {self.framework}")
        if self.database:
            db = self.database
            db_info = f"Database: {db.type}"
            if db.version:
                db_info += f" {db.version}"
            if db.container_name:
                db_info += f" (container: {db.container_name})"
            elif db.host and db.host != "localhost":
                db_info += f" ({db.host}:{db.port})"
            parts.append(db_info)
        if self.redis:
            parts.append(f"Cache: Redis")
        if self.uses_docker:
            parts.append(f"Docker: {len(self.containers)} containers")
        return " | ".join(parts) if parts else "Unknown stack"


class StackDetector:
    """
    Detects the technology stack of a project.

    Usage:
        detector = StackDetector("/path/to/project")
        stack = detector.detect()
        print(stack.summary())
    """

    # Database detection patterns
    DB_PATTERNS = {
        "mysql": {
            "env_keys": ["MYSQL_", "DB_CONNECTION=mysql", "DATABASE_URL=mysql"],
            "ports": [3306, 3307],
            "docker_images": ["mysql", "mariadb"],
            "connection_pattern": r"mysql://|mysql\+|mysqli://",
        },
        "postgresql": {
            "env_keys": ["POSTGRES", "PG_", "DATABASE_URL=postgres"],
            "ports": [5432, 5433],
            "docker_images": ["postgres", "postgresql"],
            "connection_pattern": r"postgres://|postgresql://|psycopg",
        },
        "mongodb": {
            "env_keys": ["MONGO", "MONGODB_"],
            "ports": [27017],
            "docker_images": ["mongo", "mongodb"],
            "connection_pattern": r"mongodb://|mongodb\+srv://",
        },
        "sqlite": {
            "env_keys": ["SQLITE", "DATABASE_URL=sqlite"],
            "ports": [],
            "docker_images": [],
            "connection_pattern": r"sqlite://|\.db$|\.sqlite",
        },
        "redis": {
            "env_keys": ["REDIS_"],
            "ports": [6379],
            "docker_images": ["redis"],
            "connection_pattern": r"redis://",
        },
    }

    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        "fastapi": {
            "imports": ["fastapi", "from fastapi"],
            "packages": ["fastapi"],
        },
        "django": {
            "imports": ["django"],
            "packages": ["django"],
            "files": ["manage.py", "settings.py"],
        },
        "flask": {
            "imports": ["flask", "from flask"],
            "packages": ["flask"],
        },
        "express": {
            "imports": ["express"],
            "packages": ["express"],
        },
        "nextjs": {
            "packages": ["next"],
            "files": ["next.config.js", "next.config.mjs"],
        },
        "nestjs": {
            "packages": ["@nestjs/core"],
        },
        "laravel": {
            "files": ["artisan"],
            "packages": ["laravel/framework"],
        },
    }

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path).resolve()
        self.stack = ProjectStack(
            project_path=str(self.project_path),
            project_name=self.project_path.name,
        )

    def detect(self) -> ProjectStack:
        """
        Detect the full project stack.

        Returns:
            ProjectStack with detected configuration
        """
        logger.info(f"Detecting stack for project: {self.project_path}")

        # Run all detection methods
        self._detect_from_env_files()
        self._detect_from_docker_compose()
        self._detect_from_dockerfile()
        self._detect_from_package_json()
        self._detect_from_python_packages()
        self._detect_language_and_framework()

        # Calculate confidence
        self._calculate_confidence()

        logger.info(f"Stack detected: {self.stack.summary()}")
        return self.stack

    def _detect_from_env_files(self):
        """Detect stack from .env files."""
        env_files = [
            ".env",
            ".env.local",
            ".env.development",
            ".env.production",
            ".env.example",
        ]

        for env_file in env_files:
            env_path = self.project_path / env_file
            if env_path.exists():
                self._parse_env_file(env_path)

    def _parse_env_file(self, env_path: Path):
        """Parse an environment file for stack info."""
        try:
            content = env_path.read_text()
            self.stack.detection_sources.append(str(env_path.name))

            # Parse key=value pairs
            env_vars = {}
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    env_vars[key] = value

            # Detect database from env vars
            for db_type, patterns in self.DB_PATTERNS.items():
                for env_key_pattern in patterns["env_keys"]:
                    for key, value in env_vars.items():
                        if env_key_pattern in key or env_key_pattern in f"{key}={value}":
                            self._set_database_from_env(db_type, key, value, env_vars, env_path.name)
                            break

            # Check for DATABASE_URL connection string
            if "DATABASE_URL" in env_vars:
                self._parse_database_url(env_vars["DATABASE_URL"], env_path.name)

        except Exception as e:
            logger.warning(f"Error parsing {env_path}: {e}")

    def _set_database_from_env(self, db_type: str, key: str, value: str, env_vars: dict, source: str):
        """Set database config from environment variables."""
        if db_type == "redis":
            if not self.stack.redis:
                self.stack.redis = DatabaseConfig(
                    type="redis",
                    host=env_vars.get("REDIS_HOST", "localhost"),
                    port=int(env_vars.get("REDIS_PORT", 6379)),
                    source=source,
                )
        else:
            if not self.stack.database:
                self.stack.database = DatabaseConfig(
                    type=db_type,
                    host=env_vars.get("DB_HOST", env_vars.get(f"{db_type.upper()}_HOST", "localhost")),
                    port=int(env_vars.get("DB_PORT", env_vars.get(f"{db_type.upper()}_PORT", self.DB_PATTERNS[db_type]["ports"][0] if self.DB_PATTERNS[db_type]["ports"] else 0))),
                    database=env_vars.get("DB_DATABASE", env_vars.get("DB_NAME", env_vars.get(f"{db_type.upper()}_DATABASE", ""))),
                    source=source,
                )

    def _parse_database_url(self, url: str, source: str):
        """Parse a DATABASE_URL connection string."""
        for db_type, patterns in self.DB_PATTERNS.items():
            if re.search(patterns["connection_pattern"], url, re.IGNORECASE):
                if db_type == "redis":
                    if not self.stack.redis:
                        self.stack.redis = DatabaseConfig(type="redis", connection_string=url, source=source)
                else:
                    if not self.stack.database:
                        # Parse URL components
                        match = re.match(r"(\w+)://(?:([^:]+):([^@]+)@)?([^:/]+)(?::(\d+))?(?:/([^?]+))?", url)
                        if match:
                            _, user, password, host, port, database = match.groups()
                            self.stack.database = DatabaseConfig(
                                type=db_type,
                                host=host or "localhost",
                                port=int(port) if port else (self.DB_PATTERNS[db_type]["ports"][0] if self.DB_PATTERNS[db_type]["ports"] else 0),
                                database=database or "",
                                connection_string=url,
                                source=source,
                            )
                        else:
                            self.stack.database = DatabaseConfig(type=db_type, connection_string=url, source=source)
                break

    def _detect_from_docker_compose(self):
        """Detect stack from docker-compose files."""
        compose_files = [
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
            "docker-compose.dev.yml",
            "docker-compose.local.yml",
        ]

        for compose_file in compose_files:
            compose_path = self.project_path / compose_file
            if compose_path.exists():
                self._parse_docker_compose(compose_path)
                break

    def _parse_docker_compose(self, compose_path: Path):
        """Parse docker-compose.yml for stack info."""
        try:
            content = compose_path.read_text()
            compose = yaml.safe_load(content)

            self.stack.uses_docker = True
            self.stack.docker_compose_file = compose_path.name
            self.stack.detection_sources.append(compose_path.name)

            services = compose.get("services", {})
            self.stack.containers = list(services.keys())

            for service_name, service_config in services.items():
                if not isinstance(service_config, dict):
                    continue

                image = service_config.get("image", "")
                container_name = service_config.get("container_name", service_name)

                # Detect database from Docker image
                for db_type, patterns in self.DB_PATTERNS.items():
                    for docker_image in patterns["docker_images"]:
                        if docker_image in image.lower() or docker_image in service_name.lower():
                            # Extract version from image tag
                            version = ""
                            if ":" in image:
                                version = image.split(":")[1]

                            # Get port mapping
                            ports = service_config.get("ports", [])
                            host_port = 0
                            for port in ports:
                                port_str = str(port)
                                if ":" in port_str:
                                    host_port = int(port_str.split(":")[0])
                                    break

                            if db_type == "redis":
                                self.stack.redis = DatabaseConfig(
                                    type="redis",
                                    container_name=container_name,
                                    version=version,
                                    port=host_port or 6379,
                                    source=compose_path.name,
                                )
                            else:
                                # Get database name from environment
                                env = service_config.get("environment", {})
                                if isinstance(env, list):
                                    env = dict(e.split("=", 1) for e in env if "=" in e)

                                db_name = ""
                                for key in ["MYSQL_DATABASE", "POSTGRES_DB", "MONGO_INITDB_DATABASE"]:
                                    if key in env:
                                        db_name = env[key]
                                        break

                                self.stack.database = DatabaseConfig(
                                    type=db_type,
                                    container_name=container_name,
                                    version=version,
                                    port=host_port or (patterns["ports"][0] if patterns["ports"] else 0),
                                    database=db_name,
                                    source=compose_path.name,
                                )
                            break

        except Exception as e:
            logger.warning(f"Error parsing {compose_path}: {e}")

    def _detect_from_dockerfile(self):
        """Detect language/runtime from Dockerfile."""
        dockerfile_path = self.project_path / "Dockerfile"
        if not dockerfile_path.exists():
            return

        try:
            content = dockerfile_path.read_text()
            self.stack.detection_sources.append("Dockerfile")

            # Detect base image
            from_match = re.search(r"FROM\s+(\S+)", content, re.IGNORECASE)
            if from_match:
                base_image = from_match.group(1).lower()

                if "python" in base_image:
                    self.stack.language = "python"
                    version_match = re.search(r"python:?([\d.]+)?", base_image)
                    if version_match:
                        self.stack.runtime_version = version_match.group(1) or ""
                elif "node" in base_image:
                    self.stack.language = "javascript"
                    version_match = re.search(r"node:?([\d.]+)?", base_image)
                    if version_match:
                        self.stack.runtime_version = version_match.group(1) or ""
                elif "golang" in base_image or "go:" in base_image:
                    self.stack.language = "go"
                elif "php" in base_image:
                    self.stack.language = "php"

        except Exception as e:
            logger.warning(f"Error parsing Dockerfile: {e}")

    def _detect_from_package_json(self):
        """Detect stack from package.json."""
        package_path = self.project_path / "package.json"
        if not package_path.exists():
            return

        try:
            content = package_path.read_text()
            package = json.loads(content)
            self.stack.detection_sources.append("package.json")

            if not self.stack.language:
                self.stack.language = "javascript"

            # Check for TypeScript
            deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            if "typescript" in deps:
                self.stack.language = "typescript"

            # Detect package manager
            if (self.project_path / "yarn.lock").exists():
                self.stack.package_manager = "yarn"
            elif (self.project_path / "pnpm-lock.yaml").exists():
                self.stack.package_manager = "pnpm"
            elif (self.project_path / "package-lock.json").exists():
                self.stack.package_manager = "npm"

            # Detect framework
            for framework, patterns in self.FRAMEWORK_PATTERNS.items():
                for pkg in patterns.get("packages", []):
                    if pkg in deps:
                        self.stack.framework = framework
                        return

        except Exception as e:
            logger.warning(f"Error parsing package.json: {e}")

    def _detect_from_python_packages(self):
        """Detect stack from Python package files."""
        # Check requirements.txt
        req_path = self.project_path / "requirements.txt"
        if req_path.exists():
            self._parse_requirements(req_path)

        # Check pyproject.toml
        pyproject_path = self.project_path / "pyproject.toml"
        if pyproject_path.exists():
            self._parse_pyproject(pyproject_path)

    def _parse_requirements(self, req_path: Path):
        """Parse requirements.txt for framework detection."""
        try:
            content = req_path.read_text().lower()
            self.stack.detection_sources.append("requirements.txt")
            self.stack.language = "python"
            self.stack.package_manager = "pip"

            for framework, patterns in self.FRAMEWORK_PATTERNS.items():
                for pkg in patterns.get("packages", []):
                    if pkg.lower() in content:
                        self.stack.framework = framework
                        return

        except Exception as e:
            logger.warning(f"Error parsing requirements.txt: {e}")

    def _parse_pyproject(self, pyproject_path: Path):
        """Parse pyproject.toml for stack info."""
        try:
            content = pyproject_path.read_text()
            self.stack.detection_sources.append("pyproject.toml")
            self.stack.language = "python"

            # Check for poetry
            if "[tool.poetry]" in content:
                self.stack.package_manager = "poetry"

            # Simple check for dependencies (not full TOML parsing)
            for framework, patterns in self.FRAMEWORK_PATTERNS.items():
                for pkg in patterns.get("packages", []):
                    if pkg in content:
                        self.stack.framework = framework
                        return

        except Exception as e:
            logger.warning(f"Error parsing pyproject.toml: {e}")

    def _detect_language_and_framework(self):
        """Final pass to detect language from file extensions if not already set."""
        if self.stack.language:
            return

        # Count file extensions
        extensions = {}
        for file in self.project_path.rglob("*"):
            if file.is_file() and not any(p in str(file) for p in ["node_modules", ".git", "__pycache__", "venv"]):
                ext = file.suffix.lower()
                extensions[ext] = extensions.get(ext, 0) + 1

        # Determine language from extensions
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".php": "php",
            ".rb": "ruby",
            ".rs": "rust",
        }

        max_count = 0
        for ext, lang in lang_map.items():
            count = extensions.get(ext, 0)
            if count > max_count:
                max_count = count
                self.stack.language = lang

    def _calculate_confidence(self):
        """Calculate confidence score based on detection sources."""
        score = 0.0
        max_score = 5.0

        # Database detected from docker-compose (high confidence)
        if self.stack.database and "docker-compose" in self.stack.database.source:
            score += 1.5
        # Database detected from .env
        elif self.stack.database and ".env" in self.stack.database.source:
            score += 1.0

        # Language detected
        if self.stack.language:
            score += 1.0

        # Framework detected
        if self.stack.framework:
            score += 1.0

        # Docker detected
        if self.stack.uses_docker:
            score += 0.5

        # Multiple sources
        if len(self.stack.detection_sources) >= 3:
            score += 1.0

        self.stack.confidence = min(score / max_score, 1.0)


def detect_project_stack(project_path: str | Path) -> ProjectStack:
    """
    Convenience function to detect project stack.

    Args:
        project_path: Path to the project root

    Returns:
        ProjectStack with detected configuration
    """
    detector = StackDetector(project_path)
    return detector.detect()


def get_database_info(project_path: str | Path) -> dict[str, Any] | None:
    """
    Get just the database configuration for a project.

    Args:
        project_path: Path to the project root

    Returns:
        Dictionary with database info or None if not detected
    """
    stack = detect_project_stack(project_path)
    if stack.database:
        return stack.database.to_dict()
    return None


# Cache for detected stacks
_stack_cache: dict[str, ProjectStack] = {}


def get_cached_stack(project_path: str | Path, force_refresh: bool = False) -> ProjectStack:
    """
    Get project stack with caching.

    Args:
        project_path: Path to the project root
        force_refresh: Force re-detection even if cached

    Returns:
        ProjectStack with detected configuration
    """
    path_str = str(Path(project_path).resolve())

    if force_refresh or path_str not in _stack_cache:
        _stack_cache[path_str] = detect_project_stack(project_path)

    return _stack_cache[path_str]


def clear_stack_cache():
    """Clear the stack detection cache."""
    _stack_cache.clear()
