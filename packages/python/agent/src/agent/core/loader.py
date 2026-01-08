"""
agent/core/loader.py
Phase 29: Unified Skill Loader Pipeline

Complete pipeline: Discover → Validate → Install → Load → Register

Design:
- Single entry point for all skill operations
- Pluggable validators and security checks
- Structured concurrency for parallel loading
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import structlog

if TYPE_CHECKING:
    from agent.core.protocols import ISkill, SecurityAssessment, SecurityDecision
    from agent.core.skill_manager import Skill, SkillManager

logger = structlog.get_logger(__name__)


# =============================================================================
# Pipeline Configuration
# =============================================================================


@dataclass(slots=True)
class LoaderConfig:
    """Configuration for skill loading pipeline."""

    # Discovery options
    discover_patterns: tuple[str, ...] = ("SKILL.md",)

    # Security options
    security_enabled: bool = True
    trust_local_skills: bool = True

    # Performance options
    parallel_loading: bool = True
    max_concurrent: int = 4

    # Validation options
    require_manifest: bool = True
    require_tools: bool = True


@dataclass(slots=True)
class LoadResult:
    """Result of loading a skill."""

    success: bool
    skill_name: str
    skill_path: Path
    error: str | None = None
    assessment: SecurityAssessment | None = None
    loaded_skill: Skill | None = None


@dataclass(slots=True)
class PipelineStats:
    """Statistics for the loading pipeline."""

    discovered: int = 0
    loaded: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovered": self.discovered,
            "loaded": self.loaded,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "duration_ms": round(self.duration_ms, 2),
        }


# =============================================================================
# Pipeline Stages
# =============================================================================


class DiscoveryStage:
    """Stage 1: Discover skills in the skills directory."""

    __slots__ = ("config",)

    def __init__(self, config: LoaderConfig) -> None:
        self.config = config

    def run(self, skills_dir: Path) -> list[Path]:
        """Discover all skill directories."""
        if not skills_dir.exists():
            logger.warning("Skills directory not found", path=str(skills_dir))
            return []

        skills: list[Path] = []
        for entry in skills_dir.iterdir():
            if not entry.is_dir():
                continue

            # Check for required files
            has_skill_md = (entry / "SKILL.md").exists()
            has_tools = (entry / "tools.py").exists()

            if self.config.require_manifest and not has_skill_md:
                logger.debug("Skipping - no SKILL.md", skill=entry.name)
                continue

            if self.config.require_tools and not has_tools:
                logger.debug("Skipping - no tools.py", skill=entry.name)
                continue

            skills.append(entry)

        logger.info("Discovery complete", count=len(skills))
        return skills


class ValidationStage:
    """Stage 2: Validate skill SKILL.md and structure."""

    __slots__ = ("config",)

    def __init__(self, config: LoaderConfig) -> None:
        self.config = config

    def run(self, skill_path: Path) -> tuple[bool, str]:
        """
        Validate a skill.

        Returns:
            (is_valid, error_message)
        """
        import frontmatter

        # Check SKILL.md exists
        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            return False, f"SKILL.md not found at {skill_md_path}"

        # Validate SKILL.md frontmatter
        try:
            with open(skill_md_path) as f:
                post = frontmatter.load(f)
            manifest = post.metadata or {}

            # Required fields
            required = ["name", "version", "description"]
            for field in required:
                if field not in manifest:
                    return False, f"Required field '{field}' missing from SKILL.md"

            # Validate name
            name = manifest.get("name", "")
            if not name or not isinstance(name, str):
                return False, "Invalid skill name"

            # Validate version
            version = manifest.get("version", "")
            if not isinstance(version, str):
                return False, "Invalid version format"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in manifest: {e}"

        return True, ""


class SecurityStage:
    """Stage 3: Security assessment for skills."""

    __slots__ = ("config",)

    def __init__(self, config: LoaderConfig) -> None:
        self.config = config

    def run(self, skill_path: Path) -> SecurityAssessment:
        """Perform security assessment."""
        if not self.config.security_enabled:
            return self._create_passive_assessment()

        try:
            from agent.core.protocols import SecurityDecision, SecurityAssessment

            # Check trusted sources
            if self.config.trust_local_skills:
                return SecurityAssessment(
                    decision=SecurityDecision.SAFE,
                    score=0,
                    findings_count=0,
                    is_trusted=True,
                    reason="Local skill (trusted)",
                )

            # Full security scan
            from agent.core.security.immune_system import ImmuneSystem

            immune = ImmuneSystem()
            assessment = immune.assess(skill_path)

            return SecurityAssessment(
                decision=SecurityDecision(assessment.decision.value),
                score=assessment.score,
                findings_count=assessment.findings_count,
                is_trusted=assessment.is_trusted,
                reason=assessment.reason,
                details=assessment.details,
            )

        except Exception as e:
            logger.warning("Security scan failed", skill=skill_path.name, error=str(e))
            return SecurityAssessment(
                decision=SecurityDecision.SAFE,
                score=0,
                findings_count=0,
                is_trusted=False,
                reason=f"Scan error: {e}",
            )

    def _create_passive_assessment(self) -> SecurityAssessment:
        """Create a passive (skip) assessment."""
        from agent.core.protocols import SecurityDecision

        return SecurityAssessment(
            decision=SecurityDecision.SAFE,
            score=0,
            findings_count=0,
            is_trusted=self.config.trust_local_skills,
            reason="Security disabled",
        )


# =============================================================================
# Unified Skill Loader
# =============================================================================


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
        manager: SkillManager | None = None,
    ) -> None:
        """
        Initialize the skill loader.

        Args:
            config: Pipeline configuration
            manager: SkillManager instance (or create new)
        """
        self.config = config or LoaderConfig()

        if manager is None:
            from agent.core.skill_manager import SkillManager

            self._manager = SkillManager()
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

    def assess_security(self, skill_path: Path) -> SecurityAssessment:
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
        skill_paths = self.discover(skill_dir=skills_dir)
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
        import time

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
    def manager(self) -> SkillManager:
        """Access the underlying SkillManager."""
        return self._manager


# =============================================================================
# Convenience Functions
# =============================================================================


def load_skills(
    skills_dir: Path | None = None,
    *,
    parallel: bool = True,
    security: bool = True,
    on_progress: Callable[[LoadResult], None] | None = None,
) -> tuple[list[LoadResult], PipelineStats]:
    """
    Convenience function to load all skills.

    Usage:
        results, stats = load_skills()

        for result in results:
            if result.success:
                print(f"✓ {result.skill_name}")
            else:
                print(f"✗ {result.skill_name}: {result.error}")
    """
    config = LoaderConfig(
        parallel_loading=parallel,
        security_enabled=security,
    )

    loader = SkillLoader(config=config)
    return loader.load_all(skills_dir, on_progress=on_progress)


def quick_load(skill_name: str, skills_dir: Path | None = None) -> LoadResult:
    """
    Quickly load a single skill by name.

    Usage:
        result = quick_load("git")
        if result.success:
            print(f"Loaded {result.skill_name}")
    """
    from agent.core.skill_manager import SkillManager
    from common.skills_path import SKILLS_DIR

    if skills_dir is None:
        skills_dir = SKILLS_DIR()

    skill_path = skills_dir / skill_name
    if not skill_path.exists():
        return LoadResult(
            success=False,
            skill_name=skill_name,
            skill_path=skill_path,
            error="Skill directory not found",
        )

    loader = SkillLoader()
    return loader.load(skill_path)


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "LoaderConfig",
    "LoadResult",
    "PipelineStats",
    "SkillLoader",
    "DiscoveryStage",
    "ValidationStage",
    "SecurityStage",
    "load_skills",
    "quick_load",
]
