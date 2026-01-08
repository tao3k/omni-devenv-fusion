"""
Common Path Utilities - Simplified path handling for skills.

Provides:
- SKILLS_DIR: Callable to get skill paths (e.g., SKILLS_DIR("git") -> Path)
- load_skill_module(): Load skill modules with simplified API
- SkillPathBuilder: Builder for skill-related paths

Usage:
    from common.skills_path import SKILLS_DIR, load_skill_module
    from common.gitops import get_project_root

    # Get skill directory path from settings.yaml -> assets/skills
    git_path = SKILLS_DIR("git")              # -> /project/root/assets/skills/git
    git_tools = SKILLS_DIR("git", "tools.py") # -> /project/root/assets/skills/git/tools.py

    # Load skill module
    git_tools = load_skill_module("git")

    # Project root (uses git rev-parse --show-toplevel)
    root = get_project_root()

Settings:
    Reads from settings.yaml:
        assets:
          skills_dir: "assets/skills"  (relative to project root)
"""

import importlib.util
import sys
from pathlib import Path
from typing import Optional


class _SkillDirCallable:
    """Callable that returns skill paths based on settings.yaml config.

    Usage:
        SKILLS_DIR("git")              # -> Path("assets/skills/git")
        SKILLS_DIR("git", "tools.py")  # -> Path("assets/skills/git/tools.py")
        SKILLS_DIR()                   # -> Path("assets/skills") (base path)
    """

    _cached_base_path: Optional[Path] = None

    def _get_base_path(self) -> Path:
        """Get the base skills path from settings.yaml (assets.skills_dir)."""
        if self._cached_base_path is not None:
            return self._cached_base_path

        try:
            from common.settings import get_setting

            # Read from settings.yaml -> assets.skills_dir
            skills_path_str = get_setting("assets.skills_dir")
            if skills_path_str:
                self._cached_base_path = Path(skills_path_str)
                return self._cached_base_path
        except Exception:
            pass

        # Fallback: use default "assets/skills"
        self._cached_base_path = Path("assets/skills")
        return self._cached_base_path

    def _resolve_with_root(self, path: Path) -> Path:
        """Resolve path relative to project root using git toplevel."""
        if path.is_absolute():
            return path

        # Use gitops to get project root (most reliable)
        from common.gitops import get_project_root

        project_root = get_project_root()
        return project_root / path

    def __call__(
        self,
        skill: str | None = None,
        *,
        filename: str | None = None,
        path: str | None = None,
    ) -> Path:
        """Get path for a skill or skill file.

        Args:
            skill: Name of the skill (e.g., "git", "filesystem")
            filename: Optional filename within the skill directory
            path: Optional nested path within the skill directory

        Returns:
            Path to the skill directory or specific file

        Usage:
            SKILLS_DIR()                                  # -> assets/skills (base)
            SKILLS_DIR(skill="git")                       # -> assets/skills/git
            SKILLS_DIR(skill="git", filename="tools.py")  # -> assets/skills/git/tools.py
            SKILLS_DIR(skill="skill", path="data/known_skills.json")  # -> assets/skills/skill/data/known_skills.json
        """
        base = self._get_base_path()
        base = self._resolve_with_root(base)

        if skill is None:
            return base

        result = base / skill

        if path:
            result = result / path
        elif filename:
            result = result / filename

        return result

    def __getattr__(self, name: str) -> Path:
        """Attribute access for skill names (for backwards compatibility).

        Usage:
            SKILLS_DIR.git  # -> Path("assets/skills/git")
        """
        return self(name)


# Global instance
SKILLS_DIR: _SkillDirCallable = _SkillDirCallable()


def load_skill_module(
    skill_name: str,
    project_root: Optional[Path] = None,
    module_name: Optional[str] = None,
) -> object:
    """
    Load a skill module directly from its tools.py file.

    Replaces the verbose pattern:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "assets/skills/git"))
        from tools import _get_cog_scopes

    With the simple pattern:
        from common.skills_path import load_skill_module
        git_tools = load_skill_module("git")
        scopes = git_tools._get_cog_scopes()

    Args:
        skill_name: Name of the skill (e.g., "git", "filesystem")
        project_root: Project root path (auto-detected via git toplevel if None)
        module_name: Optional custom module name

    Returns:
        The loaded module object

    Raises:
        FileNotFoundError: If tools.py not found
    """
    if project_root is None:
        from common.gitops import get_project_root

        project_root = get_project_root()

    # Use SKILLS_DIR to get the path (already resolved with project_root)
    tools_path = SKILLS_DIR(skill=skill_name, filename="tools.py")

    if not tools_path.exists():
        raise FileNotFoundError(f"Skill tools.py not found: {tools_path}")

    if module_name is None:
        module_name = f"_test_skill_{skill_name}"

    # Clean up existing module if present
    if module_name in sys.modules:
        del sys.modules[module_name]

    # Load the module from file
    spec = importlib.util.spec_from_file_location(module_name, tools_path)
    if spec is None:
        raise ImportError(f"Cannot load spec for {tools_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


def load_skill_function(
    skill_name: str,
    function_name: str,
    project_root: Optional[Path] = None,
) -> object:
    """
    Load a specific function from a skill module.

    Args:
        skill_name: Name of the skill
        function_name: Name of the function to extract
        project_root: Project root path (auto-detected if None)

    Returns:
        The function object

    Usage:
        get_scopes = load_skill_function("git", "_get_cog_scopes")
        scopes = get_scopes(root)
    """
    module = load_skill_module(skill_name, project_root)

    if not hasattr(module, function_name):
        raise AttributeError(f"Function '{function_name}' not found in skill '{skill_name}'")

    return getattr(module, function_name)


class SkillPathBuilder:
    """Builder pattern for constructing skill-related paths.

    Usage:
        builder = SkillPathBuilder()
        builder.git / "tools.py"
        builder.git / "prompts.md"
    """

    def __init__(self, project_root: Optional[Path] = None):
        from common.gitops import get_project_root

        self._project_root = project_root or get_project_root()
        self._skills_base = SKILLS_DIR()  # Already resolved with project_root

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def skills(self) -> Path:
        return self._skills_base

    def __getattr__(self, name: str) -> Path:
        """Access skill directories via attributes."""
        return self._skills_base / name

    def skill(self, name: str) -> Path:
        """Get path for a specific skill."""
        return self._skills_base / name

    def skill_file(self, skill_name: str, filename: str) -> Path:
        """Get a specific file within a skill directory."""
        return self._skills_base / skill_name / filename

    def manifest(self, skill_name: str) -> Path:
        """Get the SKILL.md for a skill."""
        return self._skills_base / skill_name / "SKILL.md"

    def guide(self, skill_name: str) -> Path:
        """Get the guide.md for a skill."""
        return self._skills_base / skill_name / "guide.md"

    def tools(self, skill_name: str) -> Path:
        """Get the tools.py for a skill."""
        return self._skills_base / skill_name / "tools.py"

    def prompts(self, skill_name: str) -> Path:
        """Get the prompts.md for a skill."""
        return self._skills_base / skill_name / "prompts.md"


# =============================================================================
# Export
# =============================================================================
