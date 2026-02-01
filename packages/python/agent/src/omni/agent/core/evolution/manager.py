"""
manager.py - Evolution Orchestration Manager

Orchestrates the complete skill crystallization workflow:
- UniversalSolver: Execute tasks and record traces
- Harvester: Analyze traces and extract candidate skills
- SkillFactory: Generate and validate new skills
- ImmuneSystem: Security validation (quarantine → validate → promote)

Integration: OmniCell → Solver → Tracer → Harvester → Factory → Immune → Skills
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.evolution.manager")


@dataclass
class EvolutionConfig:
    """Configuration for evolution manager."""

    # Thresholds
    min_trace_frequency: int = 3  # Minimum executions before harvesting
    min_success_rate: float = 0.8  # Minimum success rate for crystallization
    max_trace_age_hours: int = 24  # Only consider traces from last N hours

    # Scheduling
    check_interval_seconds: int = 300  # How often to check for crystallization
    batch_size: int = 10  # Traces to process per batch

    # Feature flags
    auto_crystallize: bool = False  # Auto-create skills (requires approval)
    dry_run: bool = False  # Simulate without creating skills


@dataclass
class EvolutionState:
    """Current state of the evolution system."""

    last_check: datetime | None = None
    total_traces: int = 0
    total_skills_crystallized: int = 0
    pending_candidates: int = 0
    last_error: str | None = None
    is_active: bool = False


@dataclass
class CrystallizationCandidate:
    """A candidate skill ready for crystallization."""

    task_pattern: str
    trace_count: int
    success_rate: float
    avg_duration_ms: float
    command_pattern: list[str]
    sample_traces: list[str]  # trace_ids
    created_at: datetime = field(default_factory=datetime.now)


class EvolutionManager:
    """
    Orchestrates the complete skill evolution workflow.

    Responsibilities:
    - Coordinate UniversalSolver, Harvester, Factory, and Immune
    - Detect when crystallization should occur
    - Manage the evolution state
    - Provide observability into the evolution process

    Integration with Hippocampus:
    - Stores successful execution traces for experience-driven reasoning
    - Recalls similar experiences before checking crystallization

    Workflow:
        1. Recall similar experiences from Hippocampus
        2. Check for crystallization candidates
        3. Extract patterns from recent traces
        4. Generate candidate skills via Harvester
        5. Synthesize code via Factory
        6. Validate via ImmuneSystem
        7. Register new skill (or await approval)
        8. Store successful traces to Hippocampus
    """

    def __init__(
        self,
        config: EvolutionConfig | None = None,
        trace_collector=None,
        harvester=None,
        factory=None,
        immune_system=None,
        hippocampus=None,
    ):
        """Initialize the evolution manager.

        Args:
            config: Evolution configuration
            trace_collector: Optional TraceCollector instance
            harvester: Optional Harvester instance
            factory: Optional SkillFactory instance
            immune_system: Optional ImmuneSystem instance
            hippocampus: Optional Hippocampus instance for experience memory
        """
        self.config = config or EvolutionConfig()
        self.state = EvolutionState()

        # Lazy-load components
        self._trace_collector = trace_collector
        self._harvester = harvester
        self._factory = factory
        self._immune_system = immune_system
        self._hippocampus = hippocampus

    # Lazy-load property accessors

    async def _get_trace_collector(self):
        if self._trace_collector is None:
            from omni.agent.core.evolution.tracer import TraceCollector

            self._trace_collector = TraceCollector()
        return self._trace_collector

    async def _get_harvester(self):
        if self._harvester is None:
            from omni.agent.core.evolution.harvester import Harvester

            self._harvester = Harvester()
        return self._harvester

    async def _get_factory(self):
        if self._factory is None:
            from omni.agent.core.evolution.factory import SkillFactory

            self._factory = SkillFactory()
        return self._factory

    async def _get_immune_system(self):
        if self._immune_system is None:
            from omni.agent.core.evolution.immune import ImmuneSystem

            self._immune_system = ImmuneSystem()
        return self._immune_system

    async def _get_hippocampus(self):
        """Lazy load Hippocampus for experience memory."""
        if self._hippocampus is None:
            from omni.agent.core.memory.hippocampus import get_hippocampus

            self._hippocampus = get_hippocampus()
        return self._hippocampus

    # Main orchestration methods

    async def check_crystallization(self) -> list[CrystallizationCandidate]:
        """Check for tasks that meet crystallization criteria.

        Returns:
            List of candidate skills ready for crystallization
        """
        self.state.last_check = datetime.now()
        self.state.is_active = True

        # [HIPPOCAMPS] Recall relevant experiences before checking
        try:
            hippocampus = await self._get_hippocampus()
            # Get recent successful traces to recall similar experiences
            tracer = await self._get_trace_collector()
            recent_traces = await tracer.get_recent_traces(limit=20)

            if recent_traces:
                # Recall experience for the most recent task pattern
                latest_trace = recent_traces[0]
                # Extract domain from metadata (default to "general")
                domain = latest_trace.metadata.get("domain", "general")
                experiences = await hippocampus.recall_experience(
                    query=latest_trace.task_description,
                    domain=domain,
                    limit=3,
                )
                if experiences:
                    logger.info(
                        "evolution.hippocampus_experiences_found",
                        count=len(experiences),
                        task=latest_trace.task_description[:50],
                    )
        except Exception as e:
            logger.warning("evolution.hippocampus_recall_failed", error=str(e))

        tracer = await self._get_trace_collector()

        # Get recent traces
        recent_traces = await tracer.get_recent_traces(limit=self.config.batch_size * 10)

        if not recent_traces:
            logger.debug("evolution.no_recent_traces")
            return []

        # Group traces by task pattern
        task_groups = self._group_traces_by_task(recent_traces)

        # Find candidates that meet thresholds
        candidates = []
        for task_pattern, traces in task_groups.items():
            trace_count = len(traces)
            success_rate = sum(1 for t in traces if t.success) / trace_count
            avg_duration = sum(t.duration_ms for t in traces) / trace_count

            if (
                trace_count >= self.config.min_trace_frequency
                and success_rate >= self.config.min_success_rate
            ):
                candidate = CrystallizationCandidate(
                    task_pattern=task_pattern,
                    trace_count=trace_count,
                    success_rate=success_rate,
                    avg_duration_ms=avg_duration,
                    command_pattern=self._extract_command_pattern(traces),
                    sample_traces=[t.timestamp.isoformat() for t in traces[:5]],
                )
                candidates.append(candidate)
                logger.info(
                    "evolution.candidate_found",
                    task_pattern=task_pattern,
                    trace_count=trace_count,
                    success_rate=success_rate,
                )

        self.state.pending_candidates = len(candidates)
        self.state.total_traces = len(recent_traces)

        return candidates

    async def crystallize_candidate(self, candidate: CrystallizationCandidate) -> dict[str, Any]:
        """Execute full crystallization pipeline for a candidate.

        Pipeline: Harvester → Factory → Immune (Quarantine → Validate → Promote)

        Args:
            candidate: Candidate skill to crystallize

        Returns:
            Dict with crystallization results
        """
        logger.info(
            "evolution.crystallizing",
            task_pattern=candidate.task_pattern,
        )

        if self.config.dry_run:
            logger.info("evolution.dry_run_mode", candidate=candidate.task_pattern)
            return {
                "status": "dry_run",
                "candidate": candidate.task_pattern,
                "actions": "Would crystallize skill",
            }

        try:
            # Step 1: Harvester - Extract skill requirements from traces
            tracer = await self._get_trace_collector()

            # Get traces matching the task pattern
            traces_by_task = await tracer.get_traces_by_task(candidate.task_pattern)
            if not traces_by_task:
                return {
                    "status": "error",
                    "candidate": candidate.task_pattern,
                    "error": "No traces found for task pattern",
                }

            # Use the most recent successful trace
            sample_trace = traces_by_task[0]

            # Use module-level function for trace processing
            from omni.agent.core.evolution.harvester import process_trace_for_skill

            candidate_skill = await process_trace_for_skill(sample_trace)

            if candidate_skill is None:
                logger.info(
                    "evolution.harvest_no_candidate",
                    task_pattern=candidate.task_pattern,
                )
                return {
                    "status": "harvest_skipped",
                    "candidate": candidate.task_pattern,
                    "reason": "Trace not deemed worthy for crystallization",
                }

            # Step 2: Factory - Generate skill files (goes to quarantine)
            factory = await self._get_factory()
            result = await factory.manufacture(candidate_skill, skip_quarantine=False)

            if not result.success:
                return {
                    "status": "factory_failed",
                    "candidate": candidate.task_pattern,
                    "error": result.error,
                }

            skill_path = result.skill_path

            # Step 3: Immune System - Validate and promote
            immune = await self._get_immune_system()
            from pathlib import Path

            skill_file = Path(skill_path) / f"{result.skill_name}.py"
            if not skill_file.exists():
                # Try alternative location
                skill_file = Path(skill_path).with_suffix(".py")

            immune_report = await immune.process_candidate(skill_file)

            if not immune_report.promoted:
                logger.warning(
                    "evolution.immune_rejected",
                    skill=result.skill_name,
                    reason=immune_report.rejection_reason,
                )
                return {
                    "status": "immune_rejected",
                    "candidate": candidate.task_pattern,
                    "skill_name": result.skill_name,
                    "skill_path": str(skill_path),
                    "immune_report": immune_report.to_dict(),
                    "rejection_reason": immune_report.rejection_reason,
                }

            # Step 4: Skill promoted successfully
            self.state.total_skills_crystallized += 1

            logger.info(
                "evolution.crystallization_complete",
                task_pattern=candidate.task_pattern,
                skill_name=result.skill_name,
            )

            return {
                "status": "success",
                "candidate": candidate.task_pattern,
                "skill_name": result.skill_name,
                "skill_path": str(skill_path),
                "immune_report": immune_report.to_dict(),
            }

        except Exception as e:
            error_msg = f"Crystallization failed: {e}"
            self.state.last_error = error_msg
            logger.error("evolution.crystallization_error", error=str(e))
            return {
                "status": "error",
                "candidate": candidate.task_pattern,
                "error": error_msg,
            }

    async def run_evolution_cycle(self) -> dict[str, Any]:
        """Run a complete evolution cycle.

        Returns:
            Dict with cycle results
        """
        cycle_start = datetime.now()
        results = {
            "cycle_started": cycle_start.isoformat(),
            "candidates_found": 0,
            "crystallizations": [],
            "errors": [],
        }

        try:
            # Check for candidates
            candidates = await self.check_crystallization()
            results["candidates_found"] = len(candidates)

            # Process each candidate
            for candidate in candidates:
                result = await self.crystallize_candidate(candidate)
                results["crystallizations"].append(result)

                if result["status"] == "error":
                    results["errors"].append(result)

        except Exception as e:
            error_msg = f"Evolution cycle failed: {e}"
            self.state.last_error = error_msg
            results["errors"].append({"error": error_msg})

        results["cycle_completed"] = datetime.now().isoformat()
        results["duration_ms"] = (datetime.now() - cycle_start).total_seconds() * 1000

        logger.info(
            "evolution.cycle_complete",
            candidates=results["candidates_found"],
            crystallized=len([c for c in results["crystallizations"] if c["status"] == "success"]),
            duration_ms=results["duration_ms"],
        )

        return results

    async def get_evolution_status(self) -> dict[str, Any]:
        """Get current evolution system status.

        Returns:
            Dict with status information
        """
        tracer = await self._get_trace_collector()

        return {
            "state": {
                "is_active": self.state.is_active,
                "last_check": self.state.last_check.isoformat() if self.state.last_check else None,
                "total_traces": self.state.total_traces,
                "total_skills_crystallized": self.state.total_skills_crystallized,
                "pending_candidates": self.state.pending_candidates,
                "last_error": self.state.last_error,
            },
            "config": {
                "min_trace_frequency": self.config.min_trace_frequency,
                "min_success_rate": self.config.min_success_rate,
                "check_interval_seconds": self.config.check_interval_seconds,
                "auto_crystallize": self.config.auto_crystallize,
                "dry_run": self.config.dry_run,
            },
            "trace_count": tracer.trace_count,
        }

    # Helper methods

    def _group_traces_by_task(self, traces) -> dict[str, list]:
        """Group execution traces by task pattern."""
        groups: dict[str, list] = {}
        for trace in traces:
            # Use description as key, normalize case
            key = trace.task_description.lower().strip()
            if key not in groups:
                groups[key] = []
            groups[key].append(trace)
        return groups

    def _extract_command_pattern(self, traces) -> list[str]:
        """Extract common command patterns from traces."""
        all_commands = []
        for trace in traces:
            all_commands.extend(trace.commands)

        # Return unique commands (could be more sophisticated)
        return list(dict.fromkeys(all_commands))

    async def cleanup_old_traces(self, keep_count: int = 500) -> int:
        """Clean up old traces to manage storage.

        Args:
            keep_count: Number of traces to keep

        Returns:
            Number of traces removed
        """
        tracer = await self._get_trace_collector()
        removed = await tracer.cleanup_old_traces(keep_count)
        return removed

    # =========================================================================
    # Quarantine Management (Immune System Integration)
    # =========================================================================

    async def scan_quarantine(self, quarantine_dir: str | None = None) -> list[dict]:
        """Scan quarantine directory and attempt to validate/promote skills.

        Args:
            quarantine_dir: Path to quarantine directory (auto-detected if None)

        Returns:
            List of promotion results
        """
        from pathlib import Path

        if quarantine_dir is None:
            factory = await self._get_factory()
            quarantine_dir = str(factory.quarantine_dir)
        else:
            quarantine_dir = quarantine_dir

        immune = await self._get_immune_system()
        results = []

        for skill_file in Path(quarantine_dir).rglob("*.py"):
            if skill_file.name.startswith("_") or skill_file.name.startswith("test_"):
                continue

            immune_report = await immune.process_candidate(skill_file)
            results.append(
                {
                    "skill_file": str(skill_file),
                    "promoted": immune_report.promoted,
                    "reason": immune_report.rejection_reason,
                    "report": immune_report.to_dict(),
                }
            )

        promoted = sum(1 for r in results if r["promoted"])
        logger.info(
            "evolution.quarantine_scan_complete",
            total=len(results),
            promoted=promoted,
        )

        return results

    async def promote_skill(self, skill_path: str) -> dict:
        """Manually promote a quarantined skill.

        Args:
            skill_path: Path to the skill file

        Returns:
            Promotion result
        """
        from pathlib import Path

        immune = await self._get_immune_system()
        immune_report = await immune.process_candidate(Path(skill_path))

        return {
            "skill_path": skill_path,
            "promoted": immune_report.promoted,
            "reason": immune_report.rejection_reason,
            "report": immune_report.to_dict(),
        }

    # =========================================================================
    # Hippocampus Integration (Experience-Driven Reasoning)
    # =========================================================================

    async def finalize_session(
        self,
        task_description: str,
        commands: list[str],
        outputs: list[str],
        success: bool,
        duration_ms: float,
        domain: str = "general",
        tags: list[str] | None = None,
    ) -> str | None:
        """
        Finalize a session by storing successful execution to Hippocampus.

        Called after successful task execution to crystallize the experience.

        Args:
            task_description: Description of the task
            commands: List of commands executed
            outputs: List of command outputs
            success: Whether the execution was successful
            duration_ms: Total execution duration
            domain: Domain category
            tags: Optional tags

        Returns:
            Trace ID if stored, None otherwise
        """
        if not success:
            logger.debug("evolution.not_storing_failed_trace")
            return None

        try:
            hippocampus = await self._get_hippocampus()

            # Create trace data
            from omni.agent.core.memory.hippocampus import create_hippocampus_trace

            trace = await create_hippocampus_trace(
                task_description=task_description,
                steps=[
                    {
                        "command": cmd,
                        "output": out,
                        "success": success,
                        "duration_ms": duration_ms / max(len(commands), 1),
                    }
                    for cmd, out in zip(commands, outputs)
                ],
                success=True,
                domain=domain,
                tags=tags,
            )

            # Store to Hippocampus
            await hippocampus.commit_to_long_term_memory(trace)

            logger.info(
                "evolution.hippocampus_trace_stored",
                trace_id=trace.trace_id,
                task=task_description[:50],
            )

            return trace.trace_id

        except Exception as e:
            logger.error(
                "evolution.hippocampus_store_failed",
                task=task_description[:50],
                error=str(e),
            )
            return None


__all__ = [
    "EvolutionManager",
    "EvolutionConfig",
    "EvolutionState",
    "CrystallizationCandidate",
]
