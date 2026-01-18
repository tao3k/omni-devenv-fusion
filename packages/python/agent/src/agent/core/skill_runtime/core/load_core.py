"""
load_core.py - Skill Load Management

Handles skill loading: preload_skills, load_all, and progress display.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

if TYPE_CHECKING:
    from .models import Skill


class SkillLoadManager:
    """
    Manages skill loading with progress display.

    Features:
    - Load preload/core skills
    - Load all discovered skills
    - Rich progress display
    """

    __slots__ = (
        "_skills_dir",
        "_skills",
        "_core_skills",
        "_loaded",
        "_load_skill",
        "_discover",
        "_execute_subprocess",
        "_get_logger",
        "_console",
    )

    def __init__(
        self,
        skills_dir: Path,
        skills: dict[str, "Skill"],
        core_skills: set[str],
        load_skill: Callable[[Path], "Skill | None"],
        discover: Callable[[], list[Path]],
        execute_subprocess: Callable[[str, str, dict[str, Any] | None], str],
        get_logger: Callable,
    ) -> None:
        self._skills_dir = skills_dir
        self._skills = skills
        self._core_skills = core_skills
        self._loaded = False
        self._load_skill = load_skill
        self._discover = discover
        self._execute_subprocess = execute_subprocess
        self._get_logger = get_logger
        self._console = Console()

    # =========================================================================
    # Loading
    # =========================================================================

    def load_preload_skills(self) -> dict[str, "Skill"]:
        """
        Load only preload/core skills from settings.yaml.

        This is the default loading mode - only loads skills configured in
        skills.preload (e.g., knowledge, memory, git, filesystem, writer).
        Other skills are loaded JIT on first use.

        Returns:
            Dictionary of loaded preload skills
        """
        logger = self._get_logger()

        if self._loaded:
            logger.debug("Skills already loaded")
            return self._skills

        # Filter to skills that exist on disk
        preload_skills = [s for s in self._core_skills if (self._skills_dir / s).exists()]
        total = len(preload_skills)

        logger.info("Loading preload skills", total=total)

        # Use Rich Progress for clean loading display
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="green", finished_style="green"),
            TaskProgressColumn(show_speed=False),
            console=self._console,
            transient=True,
        ) as progress:
            load_task = progress.add_task("[cyan]Loading skills...", total=total)

            loaded_count = 0
            failed_skills = []

            for i, skill_name in enumerate(preload_skills, 1):
                skill_path = self._skills_dir / skill_name
                try:
                    self._load_skill(skill_path)
                    loaded_count += 1
                except Exception:
                    failed_skills.append(skill_name)

                progress.update(load_task, advance=1, description=f"[cyan]Loading {skill_name}...")

        self._loaded = True

        # Clean summary with rich panel
        if failed_skills:
            logger.warning(
                "Preload complete with failures",
                loaded=loaded_count,
                failed=len(failed_skills),
                failed_skills=failed_skills,
            )
        else:
            skills_preview = ", ".join(preload_skills[:5]) + (
                "..." if len(preload_skills) > 5 else ""
            )
            logger.info(
                "Preload complete",
                loaded=loaded_count,
                skills=skills_preview,
            )
        return self._skills

    def load_all(self) -> dict[str, "Skill"]:
        """
        Load all discovered skills (legacy behavior).

        Returns:
            Dictionary of loaded skills
        """
        logger = self._get_logger()

        if self._loaded:
            logger.debug("Skills already loaded")
            return self._skills

        skill_paths = self._discover()
        total = len(skill_paths)
        logger.info("Loading all skills", total=total)

        # Use Rich Progress for clean loading display
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="green", finished_style="green"),
            TaskProgressColumn(show_speed=False),
            console=self._console,
            transient=True,
        ) as progress:
            load_task = progress.add_task("[cyan]Loading skills...", total=total)

            loaded_count = 0
            failed_skills = []

            for i, path in enumerate(skill_paths, 1):
                skill_name = path.name
                try:
                    self._load_skill(path)
                    loaded_count += 1
                except Exception as e:
                    logger.error("Skill load failed", skill=skill_name, error=str(e))
                    failed_skills.append(skill_name)

                progress.update(load_task, advance=1, description=f"[cyan]Loading {skill_name}...")

        self._loaded = True

        if failed_skills:
            logger.warning(
                "Load complete with failures",
                loaded=loaded_count,
                failed=len(failed_skills),
                failed_skills=failed_skills,
            )
        else:
            logger.info("Load complete", loaded=loaded_count)
        return self._skills

    # Alias for backward compatibility
    load_skills = load_all

    def execute_in_subprocess(
        self,
        skill_name: str,
        command_name: str,
        args: dict[str, Any] | None = None,
    ) -> str:
        """Execute a command in a subprocess (for subprocess mode skills)."""
        return self._execute_subprocess(skill_name, command_name, args)


__all__ = ["SkillLoadManager"]
