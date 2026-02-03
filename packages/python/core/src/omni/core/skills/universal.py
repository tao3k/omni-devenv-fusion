"""universal.py - Universal Skill Container.

Zero-Code Skill Architecture:
- Kernel discovers skills from assets/ directory
- Each skill gets a UniversalScriptSkill instance
- Extensions and scripts are auto-loaded and wired together
- Skills register activation rules for context-aware activation
"""

from __future__ import annotations

import inspect
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger
from pydantic import BaseModel

logger = get_logger("omni.core.universal")


class SkillActivationConfig(BaseModel):
    """Skill activation configuration from SKILL.md frontmatter."""

    files: list[str] = []
    pattern: str | None = None


class SimpleSkillMetadata(BaseModel):
    """Simple skill metadata for universal skills."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = []
    activation: SkillActivationConfig | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str) -> SimpleSkillMetadata:
        """Create metadata from Index dictionary.

        Args:
            data: Dictionary with skill metadata (from LanceDB)
            name: Skill name

        Returns:
            SimpleSkillMetadata instance
        """
        # Map Index 'routing_keywords' to 'capabilities'
        capabilities = data.get("routing_keywords", [])
        if not capabilities and "capabilities" in data:
            capabilities = data["capabilities"]

        return cls(
            name=name,
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            capabilities=capabilities,
            activation=None,  # Activation now handled by Core Sniffer
        )


def parse_skill_md_frontmatter(skill_md_path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from SKILL.md file.

    Args:
        skill_md_path: Path to SKILL.md file

    Returns:
        Dictionary of frontmatter values
    """
    if not skill_md_path.exists():
        return {}

    try:
        content = skill_md_path.read_text()
        # Match YAML frontmatter between --- markers
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            yaml_content = match.group(1)
            return _parse_simple_yaml(yaml_content)
    except Exception as e:
        logger.debug(f"Failed to parse frontmatter from {skill_md_path}: {e}")

    return {}


def _parse_simple_yaml(yaml_str: str) -> dict[str, Any]:
    """Parse simple YAML to dict (no external dependencies).

    Handles basic YAML structures like:
    ---
    name: "value"
    activation:
      files:
        - "file1"
        - "file2"
    ---
    """
    result = {}
    current_section = None
    current_list = None
    current_dict = None

    for line in yaml_str.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Top-level key: value
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if not value:
                # Start of nested structure
                current_section = key
                if key == "activation":
                    current_dict = {}
                    result[key] = current_dict
                else:
                    current_dict = None
            else:
                # Simple value
                result[key] = _parse_yaml_value(value)
                current_section = None
                current_dict = None

        # Nested key: value
        elif current_section and ":" in line:
            # Remove leading spaces
            stripped = line.lstrip()
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if current_dict is not None:
                if not value:
                    # Start of list
                    current_list = []
                    current_dict[key] = current_list
                else:
                    current_dict[key] = _parse_yaml_value(value)

            elif current_section == "activation" and key == "files":
                # Files is a list at activation level
                current_list = []
                result["activation"]["files"] = current_list

    # Convert nested dict to SkillActivationConfig
    if "activation" in result and isinstance(result["activation"], dict):
        act_dict = result["activation"]
        files = act_dict.get("files", [])
        result["activation"] = SkillActivationConfig(files=files)

    return result


def _parse_yaml_value(value: str) -> Any:
    """Parse a YAML value string to Python type."""
    value = value.strip()

    # Remove quotes
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1]

    # Boolean
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # None
    if value.lower() == "null" or value.lower() == "none":
        return None

    # Number
    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value


class UniversalScriptSkill:
    """Universal Skill Container - wraps any skill from assets directory.

    This is "The One Skill to Rule Them All".
    It automatically:
    1. Loads extensions (Rust accelerators, hooks, etc.)
    2. Injects dependencies into scripts
    3. Registers skill commands from @skill_command decorators
    4. Registers activation rules for context-aware activation
    5. Dispatches commands to appropriate handlers

    Usage:
        skill = UniversalScriptSkill("git", "/path/to/assets/skills/git")
        await skill.load({"cwd": "/repo"})
        result = await skill.execute("git.status", {})
    """

    def __init__(
        self,
        skill_name: str,
        skill_path: str | Path,
        metadata: SimpleSkillMetadata | None = None,
    ):
        """Initialize the universal skill.

        Args:
            skill_name: Name of the skill (e.g., "git", "filesystem")
            skill_path: Path to the skill directory in assets
            metadata: Optional metadata (will load from SKILL.md if not provided)
        """
        self._name = skill_name
        self._path = Path(skill_path)
        self._metadata = metadata or self._load_metadata()
        self._script_loader: ScriptLoader | None = None
        self._ext_loader: SkillExtensionLoader | None = None
        self._loaded = False
        self._sniffer_ext: list[Callable[[str], float]] = []

    def _load_metadata(self) -> SimpleSkillMetadata:
        """Load metadata from SKILL.md frontmatter."""
        skill_md = self._path / "SKILL.md"

        if skill_md.exists():
            frontmatter = parse_skill_md_frontmatter(skill_md)

            activation_config = frontmatter.get("activation")
            if isinstance(activation_config, SkillActivationConfig):
                activation = activation_config
            elif isinstance(activation_config, dict):
                activation = SkillActivationConfig(files=activation_config.get("files", []))
            else:
                activation = None

            return SimpleSkillMetadata(
                name=self._name,
                version=frontmatter.get("version", "1.0.0"),
                description=frontmatter.get("description", ""),
                capabilities=frontmatter.get("capabilities", []),
                activation=activation,
            )

        return SimpleSkillMetadata(
            name=self._name,
            version="1.0.0",
            description=f"Skill: {self._name}",
        )

    @property
    def protocol_content(self) -> str:
        """Get the Markdown instructions (protocol) from SKILL.md.

        This excludes the YAML frontmatter and provides the core guidance
        used for cognitive re-anchoring.
        """
        skill_md = self._path / "SKILL.md"
        if not skill_md.exists():
            return f"No detailed protocol defined for skill '{self._name}'."

        try:
            content = skill_md.read_text()
            # Split by the second --- to get the body
            parts = re.split(r"^---\n.*?\n---", content, maxsplit=1, flags=re.DOTALL)
            if len(parts) > 1:
                return parts[1].strip()
            return content.strip()
        except Exception as e:
            return f"Error reading protocol for '{self._name}': {e}"

    @property
    def name(self) -> str:
        """Skill name."""
        return self._name

    @property
    def path(self) -> Path:
        """Path to skill directory."""
        return self._path

    @property
    def metadata(self) -> SimpleSkillMetadata:
        """Skill metadata."""
        return self._metadata

    @property
    def activation(self) -> SkillActivationConfig | None:
        """Skill activation configuration."""
        return self._metadata.activation

    @property
    def is_loaded(self) -> bool:
        """Check if skill is loaded."""
        return self._loaded

    @property
    def commands(self) -> dict[str, Callable]:
        """Get all registered commands (for backward compatibility)."""
        if self._script_loader:
            return self._script_loader.commands
        return {}

    def get_activation_rule(self) -> tuple[str, list[str]] | None:
        """Get activation rule tuple for this skill.

        Returns:
            Tuple of (skill_name, files) or None if no activation rules
        """
        if self._metadata.activation and self._metadata.activation.files:
            return (self._name, self._metadata.activation.files)
        return None

    def get_sniffer_extensions(self) -> list[Callable[[str], float]]:
        """Get all sniffer extensions loaded from extensions/sniffer/.

        Returns:
            List of sniffer functions (cwd: str) -> float
        """
        return self._sniffer_ext

    async def load(self, context: dict[str, Any] | None = None) -> None:
        """Load extensions and scripts.

        Auto-wiring flow:
        1. Clear sys.modules cache for this skill
        2. Load extensions from extensions/ directory
        3. Load sniffer extensions from extensions/sniffer/ (modular)
        4. Create ScriptLoader for scripts/ directory
        5. Inject Rust accelerator if available
        6. Load scripts (they get injected dependencies)
        """
        import sys

        from .extensions import SkillExtensionLoader
        from .extensions.sniffer import SnifferLoader

        context = context or {}
        cwd = context.get("cwd", os.getcwd())

        logger.debug(f"[{self._name}] Loading from {self._path}")

        # 0. Clear sys.modules cache for this skill (hot reload support)
        skill_module_prefix = f"{self._name}."
        modules_to_remove = [k for k in sys.modules if k.startswith(skill_module_prefix)]
        for mod in modules_to_remove:
            del sys.modules[mod]
        logger.debug(f"[{self._name}] Cleared {len(modules_to_remove)} cached modules")

        # Also clear workflow visualizations for this skill (they cache at module level)
        try:
            from omni.langgraph.visualize import clear_workflows

            cleared = clear_workflows(self._name)
            if cleared:
                logger.debug(f"[{self._name}] Cleared {cleared} workflow diagrams")
        except ImportError:
            pass

        # 1. Load Extensions
        ext_path = self._path / "extensions"
        if ext_path.exists():
            self._ext_loader = SkillExtensionLoader(str(ext_path), self._name)
            self._ext_loader.load_all()

        # 2. Load Modular Sniffer Extensions
        sniffer_path = self._path / "extensions" / "sniffer"
        if sniffer_path.exists():
            loader = SnifferLoader(sniffer_path)
            self._sniffer_ext = loader.load_all()
            if self._sniffer_ext:
                logger.debug(f"[{self._name}] {len(self._sniffer_ext)} sniffer extensions")

        # 3. Create Script Loader
        scripts_path = self._path / "scripts"
        self._script_loader = create_script_loader(scripts_path, self._name)

        # 4. Auto-Wiring: Inject Rust accelerator if present
        rust_bridge = self._get_extension("rust_bridge")
        if rust_bridge:
            try:
                accelerator = rust_bridge.RustAccelerator(cwd)
                if accelerator.is_active:
                    self._script_loader.inject("rust", accelerator)
                    logger.debug(f"[{self._name}] Rust Accelerator active")
                else:
                    self._script_loader.inject("rust", None)
                    logger.debug(f"[{self._name}] Rust accelerator inactive")
            except Exception as e:
                logger.debug(f"[{self._name}] Rust accelerator failed: {e}")
                self._script_loader.inject("rust", None)
        else:
            self._script_loader.inject("rust", None)

        # 5. Load Scripts
        self._script_loader.load_all()

        self._loaded = True
        logger.debug(f"[{self._name}] Loaded ({len(self._script_loader)} commands)")

    def _get_extension(self, name: str):
        """Get an extension by name."""

        if self._ext_loader:
            return self._ext_loader.get(name)
        return None

    def has_extension(self, name: str) -> bool:
        """Check if an extension is loaded."""
        if self._ext_loader is None:
            return False
        return self._ext_loader.has(name)

    async def execute(self, cmd_name: str, **kwargs: Any) -> Any:
        """Execute a command.

        Args:
            cmd_name: Full command name (e.g., "git.status")
            **kwargs: Command arguments

        Returns:
            Command result
        """
        if not self._loaded:
            raise RuntimeError(f"Skill {self._name} is not loaded")

        # Get handler - try full name first, then simple name
        handler = self._script_loader.get_command(cmd_name)
        if handler is None:
            # Try extracting simple name from "git.status" -> "status"
            simple_name = cmd_name.split(".")[-1] if "." in cmd_name else cmd_name
            handler = self._script_loader.get_command_simple(simple_name)

        if handler is None:
            available = self._script_loader.list_commands()
            raise ValueError(
                f"Command '{command}' not found in skill '{self._name}'. Available: {available}"
            )

        # Execute handler
        if inspect.iscoroutinefunction(handler):
            return await handler(**kwargs)
        return handler(**kwargs)

    def list_commands(self) -> list[str]:
        """List all available commands."""
        if self._script_loader:
            return self._script_loader.list_commands()
        return []

    def get_command(self, name: str) -> Callable | None:
        """Get a command handler by name."""
        if self._script_loader:
            return self._script_loader.get_command(name)
        return None

    def __repr__(self) -> str:
        status = "loaded" if self._loaded else "not loaded"
        cmds = len(self._script_loader) if self._script_loader else 0
        return f"<UniversalScriptSkill name='{self._name}' status='{status}' commands={cmds}>"


class UniversalSkillFactory:
    """Factory for creating UniversalScriptSkill instances.

    Supports two creation modes:
    1. Direct mode: create_skill(name) - scans directory
    2. Index mode: create_from_discovered(ds) - uses DiscoveredSkill from Index
    """

    def __init__(self, base_path: str | Path):
        """Initialize with base path to skills (e.g., assets/skills)."""
        self.base_path = Path(base_path)

    def discover_skills(self) -> list[tuple[str, Path]]:
        """Discover all skills in the base path.

        Use SkillDiscoveryService.discover_all() instead for Rust-First Indexing.

        Returns:
            List of (skill_name, skill_path) tuples
        """
        skills = []
        if not self.base_path.exists():
            return skills

        for entry in self.base_path.iterdir():
            if entry.is_dir() and not entry.name.startswith("_"):
                skills.append((entry.name, entry))
        return skills

    def create_skill(self, skill_name_or_path: str | Path) -> UniversalScriptSkill:
        """Create a UniversalScriptSkill from a name or path.

        Args:
            skill_name_or_path: Skill name (e.g., "git") or tuple (name, path)

        Returns:
            UniversalScriptSkill instance
        """
        if isinstance(skill_name_or_path, tuple):
            # Unpack tuple from discover_skills()
            name, path = skill_name_or_path
        elif isinstance(skill_name_or_path, Path):
            path = skill_name_or_path
            name = path.name
        else:
            path = self.base_path / skill_name_or_path
            name = skill_name_or_path

        return UniversalScriptSkill(skill_name=name, skill_path=path)

    def create_from_discovered(self, discovered_skill: DiscoveredSkill) -> UniversalScriptSkill:
        """Create a skill from a DiscoveredSkill object (Index mode).

        This is the preferred method for Rust-First Indexing.
        It avoids SKILL.md parsing by using pre-loaded metadata.

        Args:
            discovered_skill: DiscoveredSkill object from DiscoveryService

        Returns:
            UniversalScriptSkill instance with pre-loaded metadata
        """
        # Convert raw dict metadata to SimpleSkillMetadata
        metadata = SimpleSkillMetadata.from_dict(discovered_skill.metadata, discovered_skill.name)

        # Resolve path relative to base_path (handles relative paths from index)
        skill_path = Path(discovered_skill.path)
        if not skill_path.is_absolute():
            skill_path = self.base_path / skill_path

        return UniversalScriptSkill(
            skill_name=discovered_skill.name,
            skill_path=skill_path,
            metadata=metadata,
        )

    def create_all_skills(self) -> list[UniversalScriptSkill]:
        """Create UniversalScriptSkill for all discovered skills.

        Returns:
            List of UniversalScriptSkill instances (not loaded)
        """
        return [self.create_skill(name_path) for name_path in self.discover_skills()]


def create_universal_skill(skill_name: str, skill_path: str | Path) -> UniversalScriptSkill:
    """Factory function to create a universal skill."""
    return UniversalScriptSkill(skill_name=skill_name, skill_path=skill_path)


def create_skill_from_assets(assets_path: str | Path, skill_name: str) -> UniversalScriptSkill:
    """Create a universal skill from assets directory."""
    skill_path = Path(assets_path) / skill_name
    return UniversalScriptSkill(skill_name=skill_name, skill_path=skill_path)


# Import ScriptLoader and SkillExtensionLoader at module level for circular import avoidance
from .extensions import SkillExtensionLoader
from .script_loader import ScriptLoader, create_script_loader
