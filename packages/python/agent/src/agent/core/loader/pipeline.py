# agent/core/loader/pipeline.py
"""
SkillLoader - Unified skill loading pipeline.

Orchestrates: Discover → Validate → Security → Load → Register
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import structlog

from .config import LoaderConfig, LoadResult, PipelineStats
from .stages import DiscoveryStage, ValidationStage, SecurityStage

if TYPE_CHECKING:
    from agent.core.protocols import SecurityAssessment
    from agent.core.skill_runtime import Skill, SkillManager

logger = structlog.get_logger(__name__)


class SkillLoader:
    """
    Unified skill loading pipeline.

    Orchestrates: Discover → Validate → Security → Load → Register

    Usage:
        loader = SkillLoader()
        results = loader.load_all(skills_dir)

        for result in results:
            if result.success:
                print(f"Loaded: {result.skill_name}")
            else:
                print(f"Failed: {result.skill_name} - {result.error}")
    """

    __slots__ = (
        "config",
        "_manager",
        "_stages",
    )

    def __init__(
        self,
        config: LoaderConfig | None = None,
        manager: "SkillManager | None" = None,
    ) -> None:
        """
        Initialize the skill loader.

        Args:
            config: Pipeline configuration
            manager: SkillManager instance (or create new)
        """
        self.config = config or LoaderConfig()

        if manager is None:
            from agent.core.skill_runtime import _get_singleton_manager

            self._manager = _get_singleton_manager()
        else:
            self._manager = manager

        # Initialize pipeline stages
        self._stages = {
            "discovery": DiscoveryStage(self.config),
            "validation": ValidationStage(self.config),
            "security": SecurityStage(self.config),
        }

    # =========================================================================
    # Pipeline Execution
    # =========================================================================

    def discover(self, skills_dir: Path) -> list[Path]:
        """Stage 1: Discover skills."""
        return self._stages["discovery"].run(skills_dir)

    def validate(self, skill_path: Path) -> tuple[bool, str]:
        """Stage 2: Validate a skill."""
        return self._stages["validation"].run(skill_path)

    def assess_security(self, skill_path: Path) -> "SecurityAssessment":
        """Stage 3: Assess security."""
        return self._stages["security"].run(skill_path)

    def load(
        self,
        skill_path: Path,
        *,
        skip_validation: bool = False,
        skip_security: bool = False,
    ) -> LoadResult:
        """
        Load a single skill through the full pipeline.

        Args:
            skill_path: Path to skill directory
            skip_validation: Skip manifest validation
            skip_security: Skip security assessment

        Returns:
            LoadResult with success status and details
        """
        skill_name = skill_path.name

        try:
            # Stage 2: Validation
            if not skip_validation:
                is_valid, error = self.validate(skill_path)
                if not is_valid:
                    return LoadResult(
                        success=False,
                        skill_name=skill_name,
                        skill_path=skill_path,
                        error=f"Validation failed: {error}",
                    )

            # Stage 3: Security
            if not skip_security:
                assessment = self.assess_security(skill_path)
                if assessment.decision.value == "block":
                    return LoadResult(
                        success=False,
                        skill_name=skill_name,
                        skill_path=skill_path,
                        error="Security blocked",
                        assessment=assessment,
                    )

            # Stage 4: Load via SkillManager
            skill = self._manager.load_skill(skill_path)
            if skill is None:
                return LoadResult(
                    success=False,
                    skill_name=skill_name,
                    skill_path=skill_path,
                    error="Failed to load skill module",
                )

            return LoadResult(
                success=True,
                skill_name=skill_name,
                skill_path=skill_path,
                loaded_skill=skill,
            )

        except Exception as e:
            logger.error("Unexpected error loading skill", skill=skill_name, error=str(e))
            return LoadResult(
                success=False,
                skill_name=skill_name,
                skill_path=skill_path,
                error=str(e),
            )

    # =========================================================================
    # Hot Reload
    # =========================================================================

    def reload(self, skill_name: str) -> LoadResult:
        """
        Hot reload a skill.

         Performs surgical reload:
        1. Identifies the skill path
        2. Unloads the skill via Manager (recursive sys.modules cleanup)
        3. Re-runs the full Load pipeline

        Args:
            skill_name: Name of the skill to reload

        Returns:
            LoadResult with success status
        """
        logger.info(f"🔄 [Loader] Performing hot reload for {skill_name}...")

        # Try to get path from loaded skill first
        skill = self._manager._skills.get(skill_name)
        skill_path = None

        if skill and skill.path:
            # Use parent directory of tools.py
            skill_path = skill.path.parent
        else:
            # Fallback to discovery
            paths = self.discover(self._manager.skills_dir)
            for p in paths:
                if p.name == skill_name:
                    skill_path = p
                    break

        if not skill_path or not skill_path.exists():
            return LoadResult(
                success=False,
                skill_name=skill_name,
                skill_path=skill_path or Path(skill_name),
                error="Skill path not found",
            )

        # Perform unload (via manager - does recursive cleanup)
        self._manager.unload(skill_name)

        # Perform fresh load
        return self.load(skill_path)

    def load_all(
        self,
        skills_dir: Path | None = None,
        *,
        on_progress: Callable[[LoadResult], None] | None = None,
    ) -> tuple[list[LoadResult], PipelineStats]:
        """
        Load all skills through the full pipeline.

        Args:
            skills_dir: Skills directory (default: from settings)
            on_progress: Callback for each loaded skill

        Returns:
            Tuple of (results, stats)
        """
        import time

        t0 = time.perf_counter()

        if skills_dir is None:
            skills_dir = self._manager.skills_dir

        # Stage 1: Discovery
        skill_paths = self.discover(skills_dir)
        stats = PipelineStats(discovered=len(skill_paths))

        results: list[LoadResult] = []

        # Load skills (parallel or sequential)
        if self.config.parallel_loading and len(skill_paths) > 1:
            results = self._load_parallel(skill_paths, on_progress)
        else:
            for path in skill_paths:
                result = self.load(path)
                results.append(result)
                if on_progress:
                    on_progress(result)

        # Update stats
        stats.loaded = sum(1 for r in results if r.success)
        stats.failed = sum(1 for r in results if not r.success and r.error != "Security blocked")
        stats.blocked = sum(1 for r in results if r.error == "Security blocked")
        stats.duration_ms = (time.perf_counter() - t0) * 1000

        logger.info("Skill loading complete", stats=stats.to_dict())

        return results, stats

    def _load_parallel(
        self,
        skill_paths: list[Path],
        on_progress: Callable[[LoadResult], None] | None,
    ) -> list[LoadResult]:
        """Load skills in parallel using asyncio."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        results: list[LoadResult] = []
        lock = asyncio.Lock()

        async def load_with_semaphore(path: Path) -> LoadResult:
            async with semaphore:
                result = self.load(path)
                if on_progress:
                    async with lock:
                        on_progress(result)
                return result

        async def gather_all() -> list[LoadResult]:
            tasks = [load_with_semaphore(p) for p in skill_paths]
            return await asyncio.gather(*tasks, return_exceptions=True)

        # Run in new event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        raw_results = loop.run_until_complete(gather_all())

        # Convert exceptions to LoadResult
        for i, r in enumerate(raw_results):
            if isinstance(r, Exception):
                path = skill_paths[i]
                results.append(
                    LoadResult(
                        success=False,
                        skill_name=path.name,
                        skill_path=path,
                        error=str(r),
                    )
                )
            else:
                results.append(r)

        return results

    # =========================================================================
    # Manager Access
    # =========================================================================

    @property
    def manager(self) -> "SkillManager":
        """Access the underlying SkillManager."""
        return self._manager


__all__ = ["SkillLoader"]
