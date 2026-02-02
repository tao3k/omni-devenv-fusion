"""
Hippocampus - Long-term Memory Center

Provides experience-driven reasoning to solve "intent drift" and "reinventing the wheel" problems.

Architecture:
- commit_to_long_term_memory(): Store successful execution traces
- recall_experience(): Retrieve similar successful experiences
- _extract_nu_pattern(): Extract Nu script skeleton from trace
- _save_trace_to_disk(): Persist to .cache/omni-dev-fusion/memory/trace/

Integration:
- omni.hippocampus namespace in omni-vector
- Trace storage: .cache/omni-dev-fusion/memory/trace/{trace_id}.json

Workflow:
    User Request
         ↓
    [recall_experience()] → Find similar successful experiences
         ↓
    Inject experience into context
         ↓
    Execute task
         ↓
    [commit_to_long_term_memory()] → Store successful trace
         ↓
    Experience available for future tasks
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.config.dirs import PRJ_CACHE
from omni.foundation.services.vector import get_vector_store, SearchResult

from .schemas import (
    HippocampusTrace,
    ExperienceMetadata,
    ExperienceRecallResult,
    ExecutionStep,
)

logger = structlog.get_logger("memory.hippocampus")

# Collection name for hippocampus experiences
HIPPOCAMPUS_COLLECTION = "memory.hippocampus"

# Trace storage directory (relative to PRJ_CACHE)
TRACE_DIR = "omni-dev-fusion/memory/trace"


class Hippocampus:
    """
    Long-term memory center for experience-driven reasoning.

    Responsibilities:
    - Store successful execution traces for future reference
    - Retrieve similar experiences based on semantic similarity
    - Extract Nu command patterns from traces for pattern mining
    - Persist traces to disk and index to vector store

    Design:
    - Lazy-loaded singleton for memory efficiency
    - Async operations for I/O (disk, vector store)
    - Graceful degradation if vector store unavailable
    """

    _instance: "Hippocampus | None" = None
    _initialized: bool = False

    def __new__(cls) -> "Hippocampus":
        """Singleton pattern for memory efficiency."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the hippocampus if not already initialized."""
        if not Hippocampus._initialized:
            self._vector_store = None
            self._trace_dir = PRJ_CACHE(TRACE_DIR)
            self._trace_dir.mkdir(parents=True, exist_ok=True)
            Hippocampus._initialized = True
            logger.info(
                "Hippocampus initialized",
                trace_dir=str(self._trace_dir),
                collection=HIPPOCAMPUS_COLLECTION,
            )

    @property
    def vector_store(self):
        """Lazy-load the vector store client."""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    async def commit_to_long_term_memory(self, trace: HippocampusTrace) -> None:
        """
        Crystallize successful trace into long-term memory.

        Only stores successful traces (failure traces go to short-term logging only).

        Args:
            trace: The execution trace to store

        Process:
            1. Verify trace.success == True
            2. Extract nu_pattern (ls|where|save skeleton)
            3. Save trace JSON to .cache/omni-dev-fusion/memory/trace/
            4. Index to omni-vector (omni.hippocampus namespace)
        """
        # Step 1: Validate - only store successful traces
        if not trace.success:
            logger.debug(
                "hippocampus.skipping_failed_trace",
                trace_id=trace.trace_id,
            )
            return

        logger.info(
            "hippocampus.storing_experience",
            trace_id=trace.trace_id,
            task=trace.task_description[:100],
        )

        # Step 2: Extract Nu pattern for pattern mining
        nu_pattern = self._extract_nu_pattern(trace)

        # Step 3: Save trace to disk
        await self._save_trace_to_disk(trace)

        # Step 4: Create metadata for vector indexing
        metadata = ExperienceMetadata(
            type="experience_trace",
            trace_id=trace.trace_id,
            domain=trace.domain,
            nu_pattern=nu_pattern,
            complexity=self._estimate_complexity(trace),
            success=True,
            tags=trace.tags,
            task_description=trace.task_description,
        )

        # Step 5: Index to vector store for semantic retrieval
        # Content is the task description + first few steps for context
        content = self._format_for_indexing(trace)

        try:
            await self.vector_store.add(
                content=content,
                metadata=metadata.model_dump(mode="json"),
                collection=HIPPOCAMPUS_COLLECTION,
            )
            logger.info(
                "hippocampus.experience_indexed",
                trace_id=trace.trace_id,
                domain=trace.domain,
            )
        except Exception as e:
            logger.error(
                "hippocampus.indexing_failed",
                trace_id=trace.trace_id,
                error=str(e),
            )
            # Still saved to disk, just not indexed

    async def recall_experience(
        self,
        query: str,
        domain: str | None = None,
        limit: int = 3,
    ) -> list[ExperienceRecallResult]:
        """
        Retrieve similar successful experiences from long-term memory.

        Args:
            query: Natural language query describing the task
            domain: Optional domain filter (file_manipulation, git, test, search)
            limit: Maximum number of results to return (default: 3)

        Returns:
            List of ExperienceRecallResult sorted by similarity

        Process:
            1. Semantic search omni-vector (omni.hippocampus namespace)
            2. Filter: {"type": "experience_trace", "success": true}
            3. If domain specified, add filter: {"domain": domain}
            4. Load full trace from disk for each result
        """
        logger.info(
            "hippocampus.recalling_experience",
            query=query[:100],
            domain=domain,
            limit=limit,
        )

        try:
            # Step 1: Search vector store
            results = await self.vector_store.search(
                query=query,
                n_results=limit * 2,  # Get extra to allow for filtering
                collection=HIPPOCAMPUS_COLLECTION,
                use_cache=True,
            )

            if not results:
                logger.debug("hippocampus.no_experiences_found")
                return []

            # Step 2: Filter and convert to ExperienceRecallResult
            experiences: list[ExperienceRecallResult] = []

            for result in results:
                metadata = result.metadata

                # Skip non-experience entries
                if metadata.get("type") != "experience_trace":
                    continue

                # Skip failed experiences (shouldn't exist, but safety check)
                if not metadata.get("success", False):
                    continue

                # Apply domain filter if specified
                if domain and metadata.get("domain") != domain:
                    continue

                # Load full trace from disk
                trace_id = metadata.get("trace_id", "")
                full_trace = await self._load_trace_from_disk(trace_id)

                if full_trace is None:
                    logger.warning(
                        "hippocampus.trace_file_missing",
                        trace_id=trace_id,
                    )
                    continue

                # Convert distance to similarity score (1 - normalized_distance)
                similarity_score = max(0.0, 1.0 - (result.distance or 0.0))

                experience = ExperienceRecallResult(
                    trace_id=trace_id,
                    task_description=full_trace.task_description,
                    similarity_score=similarity_score,
                    domain=metadata.get("domain", "general"),
                    nu_pattern=metadata.get("nu_pattern", ""),
                    tags=metadata.get("tags", []),
                    steps=full_trace.steps,
                    metadata=metadata,
                )
                experiences.append(experience)

            # Sort by similarity and limit results
            experiences.sort(key=lambda x: x.similarity_score, reverse=True)
            experiences = experiences[:limit]

            logger.info(
                "hippocampus.experiences_retrieved",
                count=len(experiences),
                query=query[:50],
            )

            return experiences

        except Exception as e:
            logger.error(
                "hippocampus.recall_failed",
                query=query[:100],
                error=str(e),
            )
            return []

    def _extract_nu_pattern(self, trace: HippocampusTrace) -> str:
        """
        Extract Nu script skeleton from trace commands.

        Converts shell commands to Nu equivalents:
        - ls → ls
        - grep → where $it =~ "pattern"
        - find → glob
        - cat → open
        - echo → print

        Args:
            trace: The execution trace

        Returns:
            Nu script skeleton as string
        """
        if not trace.steps:
            return ""

        # Build pattern from successful commands
        pattern_parts = []

        for step in trace.steps:
            if not step.success:
                continue

            command = step.command.strip()

            # Simple pattern extraction - extract key operations
            if command.startswith("ls"):
                pattern_parts.append("ls")
            elif command.startswith("find"):
                pattern_parts.append("glob")
            elif "grep" in command or "where" in command:
                pattern_parts.append("where")
            elif command.startswith("cat") or command.startswith("open"):
                pattern_parts.append("open")
            elif command.startswith("echo") or command.startswith("print"):
                pattern_parts.append("print")
            elif command.startswith("save") or ">" in command:
                pattern_parts.append("save")
            elif command.startswith("git"):
                if "status" in command:
                    pattern_parts.append("git status")
                elif "commit" in command:
                    pattern_parts.append("git commit")
                elif "add" in command:
                    pattern_parts.append("git add")
                else:
                    pattern_parts.append("git")
            elif "python" in command or "pytest" in command:
                pattern_parts.append("run")
            else:
                # Generic command - use first word
                first_word = command.split()[0] if command else ""
                if first_word:
                    pattern_parts.append(first_word)

        # Remove duplicates while preserving order
        seen = set()
        unique_parts = []
        for part in pattern_parts:
            if part not in seen:
                seen.add(part)
                unique_parts.append(part)

        return "|".join(unique_parts) if unique_parts else ""

    def _estimate_complexity(self, trace: HippocampusTrace) -> str:
        """
        Estimate the complexity of a trace.

        Args:
            trace: The execution trace

        Returns:
            Complexity level: low, medium, or high
        """
        step_count = len(trace.steps)
        avg_step_length = sum(len(s.command) for s in trace.steps) / max(step_count, 1)

        if step_count <= 2 and avg_step_length < 50:
            return "low"
        elif step_count <= 5 and avg_step_length < 100:
            return "medium"
        else:
            return "high"

    def _format_for_indexing(self, trace: HippocampusTrace) -> str:
        """
        Format trace for vector indexing.

        Args:
            trace: The execution trace

        Returns:
            Formatted string for embedding
        """
        # Include task description and command summary
        commands_summary = " → ".join(s.command.split()[0] for s in trace.steps[:5])
        return f"Task: {trace.task_description}\nCommands: {commands_summary}"

    async def _save_trace_to_disk(self, trace: HippocampusTrace) -> None:
        """
        Save trace JSON to disk.

        Args:
            trace: The execution trace to save
        """
        trace_path = self._trace_dir / f"{trace.trace_id}.json"

        try:
            trace_dict = trace.model_dump(mode="json")
            trace_path.write_text(json.dumps(trace_dict, indent=2, ensure_ascii=False))
            logger.debug(
                "hippocampus.trace_saved",
                trace_id=trace.trace_id,
                path=str(trace_path),
            )
        except Exception as e:
            logger.error(
                "hippocampus.trace_save_failed",
                trace_id=trace.trace_id,
                error=str(e),
            )
            raise

    async def _load_trace_from_disk(self, trace_id: str) -> HippocampusTrace | None:
        """
        Load trace from disk.

        Args:
            trace_id: The trace ID to load

        Returns:
            HippocampusTrace or None if not found
        """
        trace_path = self._trace_dir / f"{trace_id}.json"

        if not trace_path.exists():
            return None

        try:
            trace_dict = json.loads(trace_path.read_text())
            return HippocampusTrace.model_validate(trace_dict)
        except Exception as e:
            logger.error(
                "hippocampus.trace_load_failed",
                trace_id=trace_id,
                error=str(e),
            )
            return None

    async def get_stats(self) -> dict[str, Any]:
        """Get hippocampus statistics."""
        trace_count = len(list(self._trace_dir.glob("*.json")))

        try:
            vector_count = await self.vector_store.count(HIPPOCAMPUS_COLLECTION)
        except Exception:
            vector_count = -1

        return {
            "trace_count": trace_count,
            "vector_count": vector_count,
            "collection": HIPPOCAMPUS_COLLECTION,
            "trace_dir": str(self._trace_dir),
        }

    async def clear_all(self) -> int:
        """
        Clear all hippocampus data (for testing/reset).

        Returns:
            Number of trace files deleted
        """
        deleted = 0
        for trace_file in self._trace_dir.glob("*.json"):
            try:
                trace_file.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(
                    "hippocampus.delete_failed",
                    file=str(trace_file),
                    error=str(e),
                )

        # Invalidate vector cache
        self.vector_store.invalidate_cache(HIPPOCAMPUS_COLLECTION)

        logger.info("hippocampus.cleared", deleted_count=deleted)
        return deleted


# =============================================================================
# Convenience Functions
# =============================================================================

_hippocampus_instance: Hippocampus | None = None


def get_hippocampus() -> Hippocampus:
    """Get the singleton Hippocampus instance."""
    global _hippocampus_instance
    if _hippocampus_instance is None:
        _hippocampus_instance = Hippocampus()
    return _hippocampus_instance


async def create_hippocampus_trace(
    task_description: str,
    steps: list[dict[str, Any]],
    success: bool,
    domain: str = "general",
    tags: list[str] | None = None,
    env_fingerprint: dict[str, Any] | None = None,
) -> HippocampusTrace:
    """
    Factory function to create a HippocampusTrace from execution data.

    Args:
        task_description: Description of the task
        steps: List of step dicts with command, output, success, duration_ms
        success: Whether the overall execution was successful
        domain: Domain category
        tags: Optional tags for categorization
        env_fingerprint: Optional environment snapshot

    Returns:
        HippocampusTrace instance
    """
    trace_id = str(uuid.uuid4())
    total_duration = sum(s.get("duration_ms", 0) for s in steps)

    # Convert step dicts to ExecutionStep models
    execution_steps = [
        ExecutionStep(
            command=s.get("command", ""),
            output=s.get("output", ""),
            success=s.get("success", False),
            duration_ms=s.get("duration_ms", 0.0),
        )
        for s in steps
    ]

    return HippocampusTrace(
        trace_id=trace_id,
        task_description=task_description,
        steps=execution_steps,
        success=success,
        domain=domain,
        tags=tags or [],
        env_fingerprint=env_fingerprint or {},
        total_duration_ms=total_duration,
        timestamp=datetime.now(),
    )


__all__ = [
    "Hippocampus",
    "get_hippocampus",
    "create_hippocampus_trace",
    "HIPPOCAMPUS_COLLECTION",
]
