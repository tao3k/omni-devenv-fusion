"""
kernel/components/registry.py - Unified Skill Registry

Merges functionality from:
- skill_runtime/core/registry.py: Core registry with state management
- skill_registry/core.py: Additional discovery and metadata functionality

This is the SINGLE source of truth for skill registry.
"""

from __future__ import annotations

from omni.foundation.config.logging import get_logger

logger = get_logger(__name__)


class UnifiedRegistry:
    """Unified skill registry - single source of truth.

    Responsibilities:
    - Skill discovery and listing
    - Manifest parsing and metadata
    - Module caching
    - State management
    - Remote installation

    Replaces both skill_runtime.core.registry and skill_registry.core.
    """

    __slots__ = (
        "_initialized",
        "_loaded_skills",
        "_module_cache",
        "_project_root",
        "_skill_tools",
        "_skills_dir",
    )

    _instance: UnifiedRegistry | None = None

    def __new__(cls) -> UnifiedRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        from omni.foundation.config.skills import SKILLS_DIR
        from omni.foundation.runtime.gitops import get_project_root

        self._project_root = get_project_root()
        self._skills_dir = SKILLS_DIR()
        self._loaded_skills: dict[str, Any] = {}
        self._module_cache: dict[str, Any] = {}
        self._skill_tools: dict[str, list[str]] = {}
        self._initialized = True

        logger.debug(
            "UnifiedRegistry initialized",
            project_root=str(self._project_root),
            skills_dir=str(self._skills_dir),
        )

    # =========================================================================
    # Singleton Access
    # =========================================================================

    @classmethod
    def get_instance(cls) -> UnifiedRegistry:
        """Get the singleton instance."""
        return cls()

    # =========================================================================
    # Discovery
    # =========================================================================

    def list_available_skills(self) -> list[str]:
        """Scan the skills directory for valid skills."""
        if not self._skills_dir.exists():
            return []

        skills = [
            item.name
            for item in self._skills_dir.iterdir()
            if item.is_dir() and (item / "SKILL.md").exists()
        ]
        return sorted(skills)

    def list_loaded_skills(self) -> list[str]:
        """List currently loaded skills."""
        return list(self._loaded_skills.keys())

    def is_loaded(self, skill_name: str) -> bool:
        """Check if a skill is loaded."""
        return skill_name in self._loaded_skills

    # =========================================================================
    # Metadata
    # =========================================================================

    def get_skill_metadata(self, skill_name: str) -> dict[str, Any] | None:
        """Get skill metadata from SKILL.md."""
        skill_path = self._skills_dir / skill_name
        if not skill_path.exists():
            return None

        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            return None

        try:
            import frontmatter

            with open(skill_md_path, encoding="utf-8") as f:
                post = frontmatter.load(f)

            metadata = post.metadata or {}
            return {
                "name": skill_name,
                "version": metadata.get("version", "0.1.0"),
                "description": metadata.get("description", ""),
                "author": metadata.get("authors", ["unknown"])[0]
                if metadata.get("authors")
                else "unknown",
                "routing_keywords": metadata.get("routing_keywords", []),
                "intents": metadata.get("intents", []),
            }
        except Exception as e:
            logger.warning(f"Failed to parse skill metadata: {e}")
            return None

    # =========================================================================
    # Module Management
    # =========================================================================

    def register_module(self, skill_name: str, module: Any) -> None:
        """Register a loaded module."""
        self._module_cache[skill_name] = module

        # Extract tool names from @skill_command decorated functions
        tools = []
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, "_is_skill_command"):
                tools.append(name)
        self._skill_tools[skill_name] = tools

    def get_module(self, skill_name: str) -> Any | None:
        """Get a loaded module."""
        return self._module_cache.get(skill_name)

    def get_skill_tools(self, skill_name: str) -> dict[str, Any]:
        """Get all @skill_command decorated tools from a skill."""
        module = self.get_module(skill_name)
        if not module:
            return {}

        tools = {}
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, "_is_skill_command"):
                tools[name] = obj

        return tools

    # =========================================================================
    # Loading
    # =========================================================================

    def load_skill(self, skill_name: str, mcp: Server | None = None) -> tuple[bool, str]:
        """Load a skill by name.

        Delegates to skill_runtime.SkillContext for actual loading.
        """
        from agent.core.skill_runtime import get_skill_context

        ctx = get_skill_context()
        # Use the context's load method
        # This maintains compatibility with existing loading logic
        try:
            # Import the loader from skill_registry
            from agent.core.skill_registry.loader import SkillLoader

            loader = SkillLoader(self)
            return loader.load_skill(skill_name, mcp)
        except Exception as e:
            return False, str(e)

    def preload_skills(self, mcp: Server | None = None) -> tuple[int, list[str]]:
        """Load all preload skills from settings."""
        from omni.foundation.config.settings import get_setting

        preload_list = get_setting("skills.preload", [])
        loaded = []
        failed = []

        for skill in preload_list:
            if skill in self._loaded_skills:
                continue
            success, msg = self.load_skill(skill, mcp)
            if success:
                loaded.append(skill)
            else:
                failed.append(skill)
                logger.warning(f"Failed to preload skill ({skill}): {msg}")

        return len(loaded), loaded

    # =========================================================================
    # Version Info
    # =========================================================================

    def get_skill_version(self, skill_name: str) -> str | None:
        """Get the version string for a skill."""
        from agent.core.skill_registry.resolver import VersionResolver

        target_dir = self._skills_dir / skill_name
        if not target_dir.exists():
            return None

        return VersionResolver.resolve_version(target_dir)

    def get_skill_revision(self, skill_name: str) -> str | None:
        """Get the current revision of an installed skill."""
        from agent.core.skill_registry.resolver import VersionResolver

        target_dir = self._skills_dir / skill_name
        if not target_dir.exists():
            return None

        return VersionResolver.resolve_revision(target_dir)

    def get_skill_info(self, skill_name: str) -> dict[str, Any]:
        """Get detailed information about an installed skill."""
        from agent.core.skill_registry.resolver import VersionResolver

        target_dir = self._skills_dir / skill_name
        if not target_dir.exists():
            return {"error": f"Skill '{skill_name}' not found"}

        version = VersionResolver.resolve_version(target_dir)
        revision = VersionResolver.resolve_revision(target_dir)
        is_dirty = VersionResolver.is_dirty(target_dir)

        return {
            "name": skill_name,
            "version": version,
            "revision": revision,
            "path": str(target_dir),
            "is_dirty": is_dirty,
        }

    # =========================================================================
    # Remote Installation
    # =========================================================================

    def install_remote_skill(
        self,
        skill_name: str,
        repo_url: str,
        version: str = "main",
        install_deps: bool = True,
    ) -> tuple[bool, str]:
        """Install a skill from a remote Git repository."""
        from agent.core.skill_registry.installer import RemoteInstaller

        target_dir = self._skills_dir / skill_name
        if target_dir.exists():
            return False, f"Skill '{skill_name}' already exists locally."

        installer = RemoteInstaller(self)

        try:
            success, msg = installer.install(target_dir, repo_url, version)
            if success and install_deps:
                installer.install_python_deps(target_dir)
            logger.info("Installed remote skill", skill=skill_name, url=repo_url)
            return success, msg
        except Exception as e:
            logger.error("Failed to install remote skill", skill=skill_name, error=str(e))
            return False, f"Installation failed: {e}"

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return self._project_root

    @property
    def skills_dir(self) -> Path:
        """Get skills directory."""
        return self._skills_dir


def get_unified_registry() -> UnifiedRegistry:
    """Get the unified registry instance."""
    return UnifiedRegistry.get_instance()
