"""
Skill Pack Loader - Enhanced plugin loading with pack manifest support.

Provides standardized pack format alignment with Miessler's pack system:
- pack.yaml manifest format with skills, hooks, and dependencies
- Dependency resolution between packs
- Skill registration and discovery
- Backward compatibility with existing manifest.yaml format

Pack Structure:
    /plugins/{pack-name}/
    ├── pack.yaml           # Primary manifest (preferred)
    ├── manifest.yaml       # Fallback manifest (legacy)
    ├── tools.py            # Tool implementations
    ├── hooks.py            # Hook implementations
    ├── skills/             # Optional: skill-specific modules
    │   ├── __init__.py
    │   └── {skill_name}.py
    └── README.md           # Documentation
"""

import importlib.util
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import yaml

from .logging import get_logger
from .plugins import (
    HookEvent,
    Plugin,
    PluginHook,
    PluginRegistry,
    PluginStatus,
    PluginTool,
)

logger = get_logger(__name__)


class PackStatus(str, Enum):
    """Pack lifecycle status."""
    DISCOVERED = "discovered"
    LOADING = "loading"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"
    DEPENDENCY_MISSING = "dependency_missing"


@dataclass
class Skill:
    """
    Represents a skill within a pack.

    Skills are high-level capabilities that may use multiple tools.
    """
    name: str
    description: str
    tools: list[str] = field(default_factory=list)  # Tool names used by this skill
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    preconditions: list[str] = field(default_factory=list)  # Required state
    postconditions: list[str] = field(default_factory=list)  # Expected outcomes
    examples: list[dict[str, Any]] = field(default_factory=list)  # Usage examples


@dataclass
class Pack:
    """
    Represents a skill pack.

    Packs are collections of related skills, tools, and hooks
    that provide a cohesive capability set.
    """
    name: str
    version: str
    description: str
    author: str
    path: Path
    status: PackStatus = PackStatus.DISCOVERED

    # Components
    skills: list[Skill] = field(default_factory=list)
    tools: list[PluginTool] = field(default_factory=list)
    hooks: list[PluginHook] = field(default_factory=list)

    # Metadata
    dependencies: list[str] = field(default_factory=list)  # Other pack names
    permissions: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    agents: list[str] = field(default_factory=list)  # Which agents can use

    # Runtime
    loaded_at: datetime | None = None
    error: str | None = None
    resolved_dependencies: list[str] = field(default_factory=list)

    def to_plugin(self) -> Plugin:
        """Convert to legacy Plugin format for compatibility."""
        return Plugin(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            path=self.path,
            status=PluginStatus(self.status.value),
            tools=self.tools,
            hooks=self.hooks,
            requires=self.dependencies,
            permissions=self.permissions,
            config=self.config,
            agents=self.agents,
            loaded_at=self.loaded_at,
            error=self.error,
        )


class PackLoader:
    """
    Enhanced pack loader with skill support.

    Provides:
    - Pack discovery from plugins directory
    - Dependency resolution between packs
    - Skill registration and lookup
    - Backward compatibility with PluginRegistry
    """

    def __init__(
        self,
        plugins_dir: str | Path = "/home/wyld-core/plugins",
        registry: PluginRegistry | None = None,
    ):
        self.plugins_dir = Path(plugins_dir)
        self._registry = registry
        self.packs: dict[str, Pack] = {}
        self.skills: dict[str, Skill] = {}  # skill_name -> Skill
        self._load_order: list[str] = []  # Topologically sorted pack names

    def discover_packs(self) -> list[str]:
        """
        Discover all packs in the plugins directory.

        Looks for pack.yaml (preferred) or manifest.yaml (fallback).

        Returns:
            List of discovered pack names
        """
        discovered: list[str] = []

        if not self.plugins_dir.exists():
            logger.warning("Plugins directory does not exist", path=str(self.plugins_dir))
            return discovered

        for pack_path in self.plugins_dir.iterdir():
            if not pack_path.is_dir():
                continue

            # Skip hidden directories
            if pack_path.name.startswith("."):
                continue

            # Try pack.yaml first, then manifest.yaml
            manifest_path = pack_path / "pack.yaml"
            if not manifest_path.exists():
                manifest_path = pack_path / "manifest.yaml"
                if not manifest_path.exists():
                    continue

            try:
                pack = self._load_manifest(pack_path, manifest_path)
                self.packs[pack.name] = pack
                discovered.append(pack.name)
                logger.info(
                    "Discovered pack",
                    name=pack.name,
                    version=pack.version,
                    skills=len(pack.skills),
                    tools=len(pack.tools),
                )
            except Exception as e:
                logger.error(
                    "Failed to load pack manifest",
                    path=str(pack_path),
                    error=str(e),
                )

        return discovered

    def _load_manifest(self, pack_path: Path, manifest_path: Path) -> Pack:
        """Load a pack manifest file."""
        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        # Parse skills (new pack.yaml format)
        skills = []
        for skill_data in data.get("skills", []):
            skills.append(Skill(
                name=skill_data["name"],
                description=skill_data.get("description", ""),
                tools=skill_data.get("tools", []),
                parameters=skill_data.get("parameters", {}),
                preconditions=skill_data.get("preconditions", []),
                postconditions=skill_data.get("postconditions", []),
                examples=skill_data.get("examples", []),
            ))

        # Parse tools (same as manifest.yaml)
        tools = []
        for tool_data in data.get("tools", []):
            tools.append(PluginTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                handler=tool_data["handler"],
                parameters=tool_data.get("parameters", {}),
                permission_level=tool_data.get("permission_level", 0),
            ))

        # Parse hooks
        hooks = []
        for hook_data in data.get("hooks", []):
            try:
                event = HookEvent(hook_data["event"])
                hooks.append(PluginHook(
                    event=event,
                    handler=hook_data["handler"],
                    priority=hook_data.get("priority", 50),
                ))
            except ValueError:
                logger.warning(
                    "Unknown hook event",
                    pack=data.get("name", "unknown"),
                    event=hook_data.get("event"),
                )

        # Parse dependencies
        dependencies = []
        for dep in data.get("dependencies", data.get("requires", [])):
            # Handle both "pack-name" and "pack-name >= 1.0.0" formats
            if isinstance(dep, str):
                # Extract just the pack name (before any version specifier)
                dep_name = dep.split()[0].split(">=")[0].split("<=")[0].split("==")[0]
                if not dep_name.startswith("ai_"):  # Skip core dependencies
                    dependencies.append(dep_name)

        return Pack(
            name=data["name"],
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "Unknown"),
            path=pack_path,
            skills=skills,
            tools=tools,
            hooks=hooks,
            dependencies=dependencies,
            permissions=data.get("permissions", []),
            config=data.get("config", {}),
            agents=data.get("agents", ["*"]),
        )

    def resolve_dependencies(self) -> list[str]:
        """
        Resolve pack dependencies using topological sort.

        Returns:
            List of pack names in load order

        Raises:
            ValueError: If circular dependency detected
        """
        # Build dependency graph
        in_degree: dict[str, int] = {name: 0 for name in self.packs}
        graph: dict[str, list[str]] = {name: [] for name in self.packs}

        for name, pack in self.packs.items():
            for dep in pack.dependencies:
                if dep in self.packs:
                    graph[dep].append(name)
                    in_degree[name] += 1
                else:
                    # Mark as missing dependency
                    logger.warning(
                        "Missing pack dependency",
                        pack=name,
                        dependency=dep,
                    )
                    pack.status = PackStatus.DEPENDENCY_MISSING
                    pack.error = f"Missing dependency: {dep}"

        # Topological sort (Kahn's algorithm)
        queue = [name for name, degree in in_degree.items() if degree == 0]
        load_order = []

        while queue:
            name = queue.pop(0)
            load_order.append(name)

            for dependent in graph[name]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for circular dependencies
        if len(load_order) != len(self.packs):
            remaining = set(self.packs.keys()) - set(load_order)
            raise ValueError(f"Circular dependency detected in packs: {remaining}")

        self._load_order = load_order
        return load_order

    def load_pack(self, name: str) -> bool:
        """
        Load a pack and register its components.

        Args:
            name: Pack name to load

        Returns:
            True if loaded successfully
        """
        if name not in self.packs:
            logger.error("Pack not found", name=name)
            return False

        pack = self.packs[name]

        # Skip if already in error state
        if pack.status in (PackStatus.ERROR, PackStatus.DEPENDENCY_MISSING):
            return False

        pack.status = PackStatus.LOADING

        try:
            # Load tool handlers
            for tool in pack.tools:
                tool._callable = self._load_handler(pack.path, tool.handler)
                logger.debug("Loaded tool handler", pack=name, tool=tool.name)

            # Load hook handlers
            for hook in pack.hooks:
                hook._callable = self._load_handler(pack.path, hook.handler)
                logger.debug("Loaded hook handler", pack=name, event=hook.event.value)

            # Register skills
            for skill in pack.skills:
                self.skills[skill.name] = skill
                logger.debug("Registered skill", pack=name, skill=skill.name)

            # If we have a registry, register with it for compatibility
            if self._registry:
                plugin = pack.to_plugin()
                self._registry.plugins[name] = plugin
                for tool in pack.tools:
                    self._registry.tools[tool.name] = tool
                for hook in pack.hooks:
                    self._registry.hooks[hook.event].append(hook)
                    self._registry.hooks[hook.event].sort(key=lambda h: h.priority, reverse=True)

            pack.status = PackStatus.ACTIVE
            pack.loaded_at = datetime.now(timezone.utc)
            pack.resolved_dependencies = [
                dep for dep in pack.dependencies
                if dep in self.packs and self.packs[dep].status == PackStatus.ACTIVE
            ]

            logger.info(
                "Pack loaded successfully",
                name=name,
                skills=len(pack.skills),
                tools=len(pack.tools),
                hooks=len(pack.hooks),
            )
            return True

        except Exception as e:
            pack.status = PackStatus.ERROR
            pack.error = str(e)
            logger.error("Failed to load pack", name=name, error=str(e))
            return False

    def _load_handler(self, pack_path: Path, handler_path: str) -> Callable[..., Any]:
        """Load a handler function from a module path."""
        module_path, func_name = handler_path.rsplit(":", 1)

        # Convert module path to file path
        parts = module_path.split(".")
        module_file = pack_path

        for part in parts:
            module_file = module_file / part

        # Try different file patterns
        if module_file.with_suffix(".py").exists():
            module_file = module_file.with_suffix(".py")
        elif (module_file / "__init__.py").exists():
            module_file = module_file / "__init__.py"
        else:
            # Try as direct .py file
            alt_file = pack_path / f"{module_path}.py"
            if alt_file.exists():
                module_file = alt_file
            else:
                raise ImportError(f"Module not found: {module_path}")

        # Create unique module name
        unique_name = f"packs.{pack_path.name}.{module_path}"

        # Load the module
        spec = importlib.util.spec_from_file_location(unique_name, module_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module: {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        spec.loader.exec_module(module)

        # Get the function
        func = getattr(module, func_name, None)
        if func is None:
            raise ImportError(f"Function not found: {func_name} in {module_path}")

        return func

    def load_all(self) -> dict[str, bool]:
        """
        Load all discovered packs in dependency order.

        Returns:
            Dict mapping pack name to load success
        """
        # Resolve dependencies first
        try:
            self.resolve_dependencies()
        except ValueError as e:
            logger.error("Dependency resolution failed", error=str(e))
            return {name: False for name in self.packs}

        results = {}
        for name in self._load_order:
            results[name] = self.load_pack(name)

        return results

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self.skills.get(name)

    def get_skills_for_agent(self, agent_name: str) -> list[Skill]:
        """Get all skills available to a specific agent."""
        available = []
        for pack in self.packs.values():
            if pack.status != PackStatus.ACTIVE:
                continue
            if "*" in pack.agents or agent_name in pack.agents:
                available.extend(pack.skills)
        return available

    def get_tools_for_skill(self, skill_name: str) -> list[PluginTool]:
        """Get all tools used by a skill."""
        skill = self.skills.get(skill_name)
        if not skill:
            return []

        tools = []
        for tool_name in skill.tools:
            if self._registry and tool_name in self._registry.tools:
                tools.append(self._registry.tools[tool_name])
        return tools

    def get_pack_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all packs."""
        return {
            name: {
                "status": pack.status.value,
                "version": pack.version,
                "skills": len(pack.skills),
                "tools": len(pack.tools),
                "hooks": len(pack.hooks),
                "dependencies": pack.dependencies,
                "resolved_dependencies": pack.resolved_dependencies,
                "loaded_at": pack.loaded_at.isoformat() if pack.loaded_at else None,
                "error": pack.error,
            }
            for name, pack in self.packs.items()
        }


# Global pack loader
_pack_loader: PackLoader | None = None


def get_pack_loader(
    plugins_dir: str | Path = "/home/wyld-core/plugins",
    registry: PluginRegistry | None = None,
) -> PackLoader:
    """Get the global pack loader."""
    global _pack_loader
    if _pack_loader is None:
        _pack_loader = PackLoader(plugins_dir, registry)
    return _pack_loader


def init_packs(
    plugins_dir: str | Path = "/home/wyld-core/plugins",
    registry: PluginRegistry | None = None,
) -> PackLoader:
    """Initialize and load all packs."""
    loader = get_pack_loader(plugins_dir, registry)
    loader.discover_packs()
    loader.load_all()
    return loader
