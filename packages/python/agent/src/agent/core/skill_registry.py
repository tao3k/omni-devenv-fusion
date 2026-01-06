"""
src/agent/core/skill_registry.py
The Kernel of the Skill-Centric OS.
V2: Uses Spec-based loading for precise, pollution-free plugin management.
Phase 13.10: Config-driven preloading + on-demand loading.
Phase 25.1: Supports @skill_command decorator pattern.
Phase 26: Skill Network with libvcs + GitPython, version resolution from manifest/lockfile/git.
"""

import json
import importlib.util
import subprocess
import sys
import types
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import structlog
from mcp.server.fastmcp import FastMCP
from git import Repo, InvalidGitRepositoryError

from agent.core.schema import SkillManifest
from agent.core.installer import SkillInstaller, install_skill
from common.gitops import get_project_root
from common.settings import get_setting

logger = structlog.get_logger(__name__)

# Marker attribute for @skill_command decorated functions
_SKILL_COMMAND_MARKER = "_is_skill_command"


class SkillRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkillRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.project_root = get_project_root()
        skills_path = get_setting("skills.path", "assets/skills")
        self.skills_dir = self.project_root / skills_path
        self.loaded_skills: Dict[str, SkillManifest] = {}
        self.module_cache: Dict[str, types.ModuleType] = {}
        self.skill_tools: Dict[str, list[str]] = {}  # Track tool names per skill
        self._initialized = True

        self.skills_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Configuration-Driven Loading (Phase 13.10)
    # =========================================================================

    def get_preload_skills(self) -> List[str]:
        """Get list of skills to preload from settings.yaml."""
        return get_setting("skills.preload", [])

    def preload_all(self, mcp: FastMCP) -> Tuple[int, List[str]]:
        """
        Load all preload skills from settings.yaml.
        Returns: (count of loaded, list of skill names)
        """
        preload_skills = self.get_preload_skills()
        loaded = []
        failed = []

        for skill in preload_skills:
            if skill in self.loaded_skills:
                continue  # Already loaded
            success, msg = self.load_skill(skill, mcp)
            if success:
                loaded.append(skill)
                logger.info(f"Preloaded skill: {skill}")
            else:
                failed.append(skill)
                logger.warning(f"Failed to preload {skill}: {msg}")

        return len(loaded), loaded

    def list_available_skills(self) -> List[str]:
        """Scan the skills directory for valid skills."""
        skills = []
        if not self.skills_dir.exists():
            return []

        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                skills.append(item.name)
        return sorted(skills)

    def list_loaded_skills(self) -> List[str]:
        """List currently loaded skills."""
        return list(self.loaded_skills.keys())

    def get_skill_manifest(self, skill_name: str) -> Optional[SkillManifest]:
        """Read and parse a skill's manifest."""
        manifest_path = self.skills_dir / skill_name / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return SkillManifest(**data)
        except Exception as e:
            logger.error(f"Failed to parse manifest for {skill_name}", error=str(e))
            return None

    def _load_module_from_path(self, module_name: str, file_path: Path) -> types.ModuleType:
        """
        Load a python module directly from a file path without polluting sys.path.
        Enables hot reloading by re-executing the module code.
        """
        import types

        # Clear any existing module from sys.modules to ensure hot reload works
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Resolve the project root and skills directory
        skills_dir = self.skills_dir

        # Ensure parent packages exist in sys.modules for relative imports
        # This allows 'from agent.skills.decorators import ...' to work
        parts = module_name.split(".")
        for i in range(1, len(parts)):
            parent_name = ".".join(parts[:i])
            if parent_name not in sys.modules:
                parent_mod = types.ModuleType(parent_name)
                # Set __path__ to make it a package (required for subpackage imports)
                parent_mod.__path__ = []
                sys.modules[parent_name] = parent_mod

        # Pre-load the decorators module if the skill imports it
        # This is required for @skill_command decorator to work
        decorators_path = skills_dir / "decorators.py"
        if decorators_path.exists() and "agent.skills.decorators" not in sys.modules:
            decorators_spec = importlib.util.spec_from_file_location(
                "agent.skills.decorators", decorators_path
            )
            decorators_module = importlib.util.module_from_spec(decorators_spec)
            sys.modules["agent.skills.decorators"] = decorators_module
            decorators_spec.loader.exec_module(decorators_module)

        # Create the Spec (The Blueprint)
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not create spec for {file_path}")

        # Create the Module (The Instance)
        module = importlib.util.module_from_spec(spec)

        # Set __package__ to enable relative imports inside the skill
        # Extract package from module name (e.g., "agent.skills.git.tools" -> "agent.skills.git")
        if len(parts) > 1:
            module.__package__ = ".".join(parts[:-1])
        else:
            module.__package__ = ""

        # Register in sys.modules for relative imports inside the skill
        sys.modules[module_name] = module

        # Execute the code (The Activation)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise e

        return module

    def load_skill(self, skill_name: str, mcp: FastMCP) -> Tuple[bool, str]:
        """
        Dynamically load a skill into the MCP server using spec-based loading.
        Supports HOT RELOAD.
        """
        manifest = self.get_skill_manifest(skill_name)
        if not manifest:
            return False, f"Skill '{skill_name}' not found or invalid."

        # 1. Resolve Skill Dependencies
        skill_deps = (
            manifest.dependencies.skills if hasattr(manifest.dependencies, "skills") else {}
        )
        if isinstance(skill_deps, dict):
            # v2.0 format: dependencies = {"skills": {"filesystem": ">=1.0.0"}, "python": {...}}
            for dep in skill_deps.keys():
                if dep not in self.loaded_skills:
                    success, msg = self.load_skill(dep, mcp)
                    if not success:
                        return False, f"Dependency '{dep}' failed: {msg}"
        elif isinstance(manifest.dependencies, list):
            # v1.x format: dependencies = ["filesystem"]
            for dep in manifest.dependencies:
                if dep not in self.loaded_skills:
                    success, msg = self.load_skill(dep, mcp)
                    if not success:
                        return False, f"Dependency '{dep}' failed: {msg}"

        # 2. Check Python Dependencies (future implementation)
        python_deps = (
            manifest.dependencies.python if hasattr(manifest.dependencies, "python") else {}
        )
        if isinstance(python_deps, dict) and python_deps:
            # TODO: Implement Python package installation
            logger.info(f"[{skill_name}] Python dependencies declared: {list(python_deps.keys())}")

        # 2. Locate the Tools File
        # tools_module="agent.skills.git.tools" -> agent/skills/git/tools.py
        # Handle both "agent.skills" and "assets.skills" prefixes for backward/forward compatibility
        tools_module = manifest.tools_module
        if tools_module.startswith("agent.skills."):
            tools_module = "assets.skills." + tools_module[len("agent.skills.") :]
        relative_path = tools_module.replace(".", "/") + ".py"
        source_path = self.project_root / relative_path

        if not source_path.exists():
            return False, f"Source file not found: {source_path}"

        # 3. Load/Reload Logic
        try:
            module_name = manifest.tools_module

            # Explicitly load from file (bypasses cache because we re-exec)
            module = self._load_module_from_path(module_name, source_path)

            # 4. Registration
            # Phase 25.1: Check for @skill_command decorated functions
            skill_commands = []
            for name in dir(module):
                if name.startswith("_"):
                    continue
                obj = getattr(module, name)
                if callable(obj) and hasattr(obj, _SKILL_COMMAND_MARKER):
                    skill_commands.append(name)

            if skill_commands:
                logger.info(
                    f"Skill '{skill_name}' uses @skill_command pattern. Commands: {skill_commands}"
                )
            else:
                return (
                    False,
                    f"Module {source_path.name} has no @skill_command decorated functions.",
                )

            # Update State
            self.loaded_skills[skill_name] = manifest
            self.module_cache[skill_name] = module

            logger.info(f"Skill loaded via Spec: {skill_name}")
            return True, f"Skill '{skill_name}' loaded via Direct Spec (Hot Reload)."

        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}", error=str(e))
            return False, f"Load Error: {str(e)}"

    def get_skill_context(self, skill_name: str, use_diff: bool = False) -> str:
        """
        Retrieve the 'Procedural Knowledge' (guide.md) for a skill.

        Args:
            skill_name: Name of the skill
            use_diff: If True, show only changes via git diff (token-efficient)
        """
        manifest = self.loaded_skills.get(skill_name) or self.get_skill_manifest(skill_name)
        if not manifest:
            return ""

        content = ""

        # Helper to get file content or diff
        def get_file_content_or_diff(file_path: Path, file_label: str) -> str:
            if not file_path.exists():
                return ""
            if use_diff:
                # Use git diff for token-efficient updates
                import subprocess

                try:
                    diff = subprocess.run(
                        ["git", "diff", str(file_path)],
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                    )
                    if diff.returncode == 0 and diff.stdout.strip():
                        return (
                            f"\n--- {skill_name.upper()} {file_label} (CHANGED) ---\n{diff.stdout}"
                        )
                    else:
                        return f"\n--- {skill_name.upper()} {file_label} ---\n[Unchanged - not showing]"
                except Exception:
                    # Fallback to full content if git fails
                    pass
            return f"\n--- {skill_name.upper()} {file_label} ---\n{file_path.read_text(encoding='utf-8')}\n"

        # Get guide content
        guide_path = self.skills_dir / skill_name / manifest.guide_file
        content += get_file_content_or_diff(guide_path, "GUIDE")

        # Get prompts content
        if manifest.prompts_file:
            prompts_path = self.skills_dir / skill_name / manifest.prompts_file
            content += get_file_content_or_diff(prompts_path, "SYSTEM PROMPTS")

        return content

    def get_combined_context(self) -> str:
        """
        Aggregate prompts.md from all loaded skills into a single context string.

        This is the "dynamic brain" of the Agent - it contains routing rules
        and policies that Claude must follow for each active skill.

        Returns:
            Combined context string from all loaded skills' prompts.md files.
        """
        if not self.loaded_skills:
            return "# No skills loaded\n\nActive skills will have their prompts.md aggregated here."

        combined = []
        combined.append("# 🧠 Active Skill Policies & Routing Rules")
        combined.append(
            "The following skills are loaded and active. You MUST follow their routing logic.\n"
        )

        for skill_name in sorted(self.loaded_skills.keys()):
            manifest = self.loaded_skills[skill_name]

            # Read prompts.md
            if manifest.prompts_file:
                prompts_path = self.skills_dir / skill_name / manifest.prompts_file
                if prompts_path.exists():
                    content = prompts_path.read_text(encoding="utf-8")
                    combined.append(f"\n## 📦 Skill: {skill_name.upper()}")
                    combined.append(content)
                    combined.append("\n---\n")

        return "\n".join(combined)

    # =========================================================================
    # Phase 26: Remote Skill Installation (libvcs + GitPython)
    # =========================================================================

    def install_remote_skill(
        self,
        skill_name: str,
        repo_url: str,
        version: str = "main",
        install_deps: bool = True,
    ) -> Tuple[bool, str]:
        """
        Install a skill from a remote Git repository using libvcs + GitPython.

        Args:
            skill_name: Name to assign to the skill locally
            repo_url: URL of the Git repository
            version: Git ref (branch, tag, commit) to checkout
            install_deps: Whether to install skill dependencies (default: True)

        Returns:
            Tuple of (success, message)
        """
        target_dir = self.skills_dir / skill_name

        # Check if skill already exists locally
        if target_dir.exists():
            return (
                False,
                f"Skill '{skill_name}' already exists locally. Use update_remote_skill() to update.",
            )

        installer = SkillInstaller()

        try:
            result = installer.install(
                repo_url=repo_url,
                target_dir=target_dir,
                version=version,
            )

            # Install Python dependencies if requested
            if install_deps:
                self._install_skill_python_deps(target_dir)

            logger.info(f"Installed remote skill '{skill_name}' from {repo_url}")
            return True, f"Skill '{skill_name}' installed from {repo_url}"

        except Exception as e:
            logger.error(f"Failed to install remote skill '{skill_name}': {e}")
            return False, f"Installation failed: {str(e)}"

    def install_remote_skill_with_deps(
        self,
        skill_name: str,
        repo_url: str,
        version: str = "main",
        visited: Optional[set] = None,
    ) -> Tuple[bool, str]:
        """
        Install a skill and recursively install its dependencies from manifest.

        Args:
            skill_name: Name to assign to the skill locally
            repo_url: URL of the Git repository
            version: Git ref (branch, tag, commit) to checkout
            visited: Set of already-installed repos (for cycle detection)

        Returns:
            Tuple of (success, message)
        """
        if visited is None:
            visited = set()

        # Prevent circular dependencies
        if skill_name in visited:
            logger.warning(f"Skipping already-processed skill: {skill_name}")
            return True, f"Skill '{skill_name}' (skipped - circular dependency)"

        visited.add(skill_name)

        # First install dependencies
        target_dir = self.skills_dir / skill_name
        if not target_dir.exists():
            # Install dependencies first (recursively)
            manifest_path = None
            temp_dir = self.skills_dir / f".{skill_name}_temp"
            try:
                # Download manifest to check dependencies
                import tempfile
                import subprocess

                subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, str(temp_dir)],
                    capture_output=True,
                )
                manifest_path = temp_dir / "manifest.json"
            except Exception:
                pass

            if manifest_path and manifest_path.exists():
                try:
                    import json

                    manifest = json.loads(manifest_path.read_text())
                    deps = manifest.get("dependencies", {}).get("skills", {})

                    for dep_name, dep_version in deps.items():
                        # Find the dependency repo URL (simplified - would need registry)
                        logger.info(f"Installing dependency: {dep_name}")

                        # Check if already installed
                        if (self.skills_dir / dep_name).exists():
                            logger.info(f"Dependency {dep_name} already installed")
                            continue

                        # TODO: Resolve dependency URL from skill registry
                        logger.warning(
                            f"Dependency resolution for '{dep_name}' not yet implemented. "
                            "Please install manually."
                        )
                except Exception as e:
                    logger.warning(f"Could not parse dependencies: {e}")
                finally:
                    if temp_dir.exists():
                        import shutil

                        shutil.rmtree(temp_dir)

        # Now install the main skill
        return self.install_remote_skill(skill_name, repo_url, version, install_deps=True)

    def update_remote_skill(
        self,
        skill_name: str,
        strategy: str = "stash",
    ) -> Tuple[bool, str]:
        """
        Update an already installed skill from its remote repository.

        Args:
            skill_name: Name of the installed skill
            strategy: Update strategy for dirty repos:
                - "stash": Stash local changes, pull, then pop (default)
                - "abort": Abort if local changes detected
                - "overwrite": Force overwrite (dangerous!)

        Returns:
            Tuple of (success, message)
        """
        target_dir = self.skills_dir / skill_name

        if not target_dir.exists():
            return False, f"Skill '{skill_name}' not found locally."

        installer = SkillInstaller()

        try:
            result = installer.update(target_dir, strategy=strategy)
            logger.info(f"Updated skill '{skill_name}'")
            return (
                True,
                f"Skill '{skill_name}' updated to revision {result.get('revision', 'unknown')}",
            )

        except Exception as e:
            logger.error(f"Failed to update skill '{skill_name}': {e}")
            return False, f"Update failed: {str(e)}"

    def _install_skill_python_deps(self, target_dir: Path) -> Tuple[bool, str]:
        """Install Python dependencies from skill's manifest."""
        installer = SkillInstaller()
        result = installer.install_python_deps(target_dir)

        if result.get("success"):
            packages = result.get("packages", [])
            if packages:
                logger.info(f"Installed Python dependencies: {packages}")
            return True, f"Dependencies installed: {packages}"
        else:
            logger.warning(f"Failed to install Python deps: {result.get('error')}")
            return False, f"Failed to install dependencies: {result.get('error')}"

    def get_skill_revision(self, skill_name: str) -> Optional[str]:
        """
        Get the current revision of an installed skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Commit hash or None
        """
        target_dir = self.skills_dir / skill_name
        if not target_dir.exists():
            return None

        installer = SkillInstaller()
        return installer.get_revision(target_dir)

    def _resolve_skill_version(self, skill_path: Path) -> str:
        """
        Multi-strategy skill version resolution:
        1.优先读取 .omni-lock.json (if installed via omni install)
        2.其次读取 manifest.json 中的 version 字段
        3.再次尝试 git rev-parse HEAD
        4.均失败则返回 "unknown"
        """
        # Strategy 1: Lockfile (Omni Managed)
        lockfile_path = skill_path / ".omni-lock.json"
        if lockfile_path.exists():
            try:
                data = json.loads(lockfile_path.read_text())
                revision = data.get("revision", "")[:7]
                updated = data.get("updated_at", "")[:10]
                return f"{revision} ({updated})"
            except Exception:
                pass

        # Strategy 2: Manifest (Static version)
        manifest_path = skill_path / "manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text())
                if "version" in data:
                    return data["version"]
            except Exception:
                pass

        # Strategy 3: Git HEAD (Dev Mode)
        try:
            # Try native git repo first
            repo = Repo(skill_path)
            sha = repo.head.commit.hexsha
            is_dirty = repo.is_dirty()
            suffix = " *" if is_dirty else ""
            return f"{sha[:7]}{suffix}"
        except (InvalidGitRepositoryError, ValueError):
            pass

        # Strategy 4: Git rev-parse from parent repo (for skills in monorepo)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(skill_path),
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                sha = result.stdout.strip()
                # Check dirty status (only within this skill directory)
                diff_result = subprocess.run(
                    ["git", "diff", "--name-only", "--", "."],
                    cwd=str(skill_path),
                    capture_output=True,
                    text=True,
                )
                untracked_result = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=str(skill_path),
                    capture_output=True,
                    text=True,
                )
                is_dirty = bool(diff_result.stdout.strip() or untracked_result.stdout.strip())
                suffix = " *" if is_dirty else ""
                return f"{sha[:7]}{suffix}"
        except Exception:
            pass

        return "unknown"

    def get_skill_info(self, skill_name: str) -> dict:
        """
        Get detailed information about an installed skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Dict with skill info (manifest, lockfile, revision, etc.)
        """
        target_dir = self.skills_dir / skill_name
        if not target_dir.exists():
            return {"error": f"Skill '{skill_name}' not found"}

        installer = SkillInstaller()

        # Resolve version using multi-strategy approach
        version = self._resolve_skill_version(target_dir)

        info = {
            "name": skill_name,
            "version": version,
            "path": str(target_dir),
            "revision": installer.get_revision(target_dir),
            "is_dirty": installer.is_dirty(target_dir),
        }

        # Read manifest
        manifest_path = target_dir / "manifest.json"
        if manifest_path.exists():
            try:
                import json

                info["manifest"] = json.loads(manifest_path.read_text())
            except Exception as e:
                info["manifest_error"] = str(e)

        # Read lockfile
        lockfile_path = target_dir / ".omni-lock.json"
        if lockfile_path.exists():
            try:
                import json

                info["lockfile"] = json.loads(lockfile_path.read_text())
            except Exception as e:
                info["lockfile_error"] = str(e)

        return info


_registry = None


def get_skill_registry():
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def get_skill_tools(skill_name: str) -> Dict[str, callable]:
    """
    Get all tool functions from a loaded skill.

    Phase 19: Enables ReAct loop to access dynamically loaded skill tools.
    Phase 25.1: Returns only @skill_command decorated functions.

    Args:
        skill_name: Name of the skill (e.g., "filesystem")

    Returns:
        Dict of tool name -> callable function
    """
    registry = get_skill_registry()
    module = registry.module_cache.get(skill_name)

    if not module:
        return {}

    tools = {}
    # Get all callables with @skill_command decorator (has _is_skill_command attribute)
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, _SKILL_COMMAND_MARKER):
            tools[name] = obj

    return tools


# =========================================================================
# Phase 27: JIT Skill Acquisition
# =========================================================================


def jit_install_skill(skill_id: str, auto_load: bool = True) -> dict:
    """
    Just-in-Time Skill Installation.

    Automatically install a skill from the known skills index and optionally load it.

    Args:
        skill_id: Skill ID from known_skills.json (e.g., "pandas-expert")
        auto_load: Whether to load the skill after installation (default: True)

    Returns:
        Dict with success status and details
    """
    from agent.core.skill_discovery import SkillDiscovery

    registry = get_skill_registry()
    discovery = SkillDiscovery()

    # Find skill in index
    skill = discovery.find_by_id(skill_id)
    if not skill:
        # Try searching
        results = discovery.search_local(skill_id, limit=1)
        if results:
            skill = results[0]
        else:
            return {
                "success": False,
                "error": f"Skill '{skill_id}' not found in known skills index",
                "hint": f"Use 'omni skill list' to see installed skills, or 'discover_skills(\"{skill_id}\")' to search.",
            }

    skill_name = skill["id"]
    repo_url = skill["url"]
    version = skill.get("version", "main")

    # Check if already installed
    target_dir = registry.skills_dir / skill_name
    if target_dir.exists():
        return {
            "success": False,
            "error": f"Skill '{skill_name}' is already installed",
            "path": str(target_dir),
            "hint": "Use 'omni skill update " + skill_name + "' to update",
        }

    # Install the skill
    success, msg = registry.install_remote_skill(skill_name, repo_url, version)

    if not success:
        return {"success": False, "error": msg}

    # Optionally load the skill
    loaded = False
    load_msg = ""
    if auto_load:
        try:
            from agent.mcp_server import mcp

            success, load_msg = registry.load_skill(skill_name, mcp)
            loaded = success
        except Exception as e:
            load_msg = str(e)

    return {
        "success": True,
        "skill_id": skill_id,
        "skill_name": skill_name,
        "url": repo_url,
        "version": version,
        "installed_path": str(target_dir),
        "loaded": loaded,
        "load_message": load_msg if loaded else f"Load skipped or failed: {load_msg}",
        "ready_to_use": True,
    }


def discover_skills(query: str = "", limit: int = 5) -> dict:
    """
    Search the known skills index for matching skills.

    Args:
        query: Search query (matched against name, description, keywords)
        limit: Maximum number of results

    Returns:
        Dict with query results
    """
    from agent.core.skill_discovery import SkillDiscovery

    discovery = SkillDiscovery()
    results = discovery.search_local(query, limit)

    return {
        "query": query,
        "count": len(results),
        "skills": results,
        "ready_to_install": [s["id"] for s in results],
    }


def suggest_skills_for_task(task: str) -> dict:
    """
    Analyze a task and suggest relevant skills from the index.

    Args:
        task: Task description (e.g., "analyze pcap file")

    Returns:
        Dict with task analysis and skill suggestions
    """
    from agent.core.skill_discovery import SkillDiscovery

    discovery = SkillDiscovery()
    return discovery.suggest_for_query(task)
