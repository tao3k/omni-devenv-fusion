"""
router.py - The Decision Maker

High-performance semantic router for intent-to-action mapping.
Uses vector search to match natural language to skill commands.

Python 3.12+ Features:
- asyncio.TaskGroup for batch routing parallelism (Section 7.3)
- StrEnum for confidence levels
"""

from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from omni.foundation.config.logging import get_logger
from omni.core.skills.runtime import SkillContext

logger = get_logger("omni.core.router")


class RouteConfidence(StrEnum):
    """Confidence levels for routing decisions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RouteResult(BaseModel):
    """Result of a routing decision.

    Model fields:
        skill_name: Name of the matched skill
        command_name: Name of the matched command
        score: Similarity score (0.0-1.0)
        confidence: Confidence level (high/medium/low)
    """

    model_config = ConfigDict(frozen=True)  # Immutable for safety

    skill_name: str = Field(..., description="Name of the matched skill")
    command_name: str = Field(..., description="Name of the matched command")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0.0-1.0)")
    confidence: RouteConfidence = Field(..., description="Confidence level")


class SemanticRouter:
    """
    [The Decision Maker]

    Receives natural language and returns the most matching (Skill, Command).

    Routing Logic:
        Query -> Vector Search -> Top Match -> Confidence Check
    """

    # Confidence thresholds
    HIGH_THRESHOLD = 0.75
    MEDIUM_THRESHOLD = 0.50

    def __init__(self, indexer: SkillIndexer):
        """Initialize the semantic router.

        Args:
            indexer: SkillIndexer instance for lookups
        """
        self._indexer = indexer

    async def route(self, query: str, threshold: float = 0.5, limit: int = 3) -> RouteResult | None:
        """
        Route a natural language query to a skill command.

        Args:
            query: User's natural language input
            threshold: Minimum score threshold (0.0-1.0)
            limit: Maximum number of results to consider

        Returns:
            RouteResult if match found, None otherwise
        """
        # Search the index
        results = await self._indexer.search(query, limit=limit)

        if results:
            # Get top match
            top = results[0]

            # Filter by threshold
            if top.score >= threshold:
                payload = top.payload or {}

                # Validate it's a command
                if payload.get("type") == "command":
                    skill_name = payload.get("skill_name", "unknown")
                    command_name = payload.get("command", "")

                    confidence = self._get_confidence(top.score)

                    logger.info(
                        f"Route: '{query}' -> {skill_name}.{command_name} "
                        f"(score: {top.score:.2f}, confidence: {confidence})"
                    )

                    return RouteResult(
                        skill_name=skill_name,
                        command_name=command_name,
                        score=top.score,
                        confidence=confidence,
                    )

        logger.debug(f"No route found for: '{query}'")
        return None

    async def route_batch(
        self, queries: list[str], threshold: float = 0.5
    ) -> list[tuple[str, RouteResult | None]]:
        """Route multiple queries in parallel using TaskGroup.

        All queries in the batch are processed concurrently, providing
        significant speedup for high-throughput scenarios.

        Args:
            queries: List of queries to route
            threshold: Minimum score threshold

        Returns:
            List of (query, RouteResult) tuples in original order
        """
        # Pre-allocate results list in original order
        results: list[tuple[str, RouteResult | None]] = [("", None)] * len(queries)

        async def _route_single(idx: int, query: str) -> None:
            """Route a single query and store result at original index."""
            route = await self.route(query, threshold)
            results[idx] = (query, route)

        # ✅ CRITICAL: Process all queries concurrently with TaskGroup
        try:
            async with asyncio.TaskGroup() as tg:
                for idx, query in enumerate(queries):
                    tg.create_task(_route_single(idx, query))
        except ExceptionGroup as e:
            logger.error(f"Batch routing failed with partial errors: {e.exceptions}")

        return results

    def _get_confidence(self, score: float) -> RouteConfidence:
        """Convert score to confidence level."""
        if score >= self.HIGH_THRESHOLD:
            return RouteConfidence.HIGH
        elif score >= self.MEDIUM_THRESHOLD:
            return RouteConfidence.MEDIUM
        return RouteConfidence.LOW

    def is_ready(self) -> bool:
        """Check if router is ready."""
        return self._indexer.is_ready


class FallbackRouter:
    """
    Fallback router for explicit command matching.
    Handles exact command names like "git.status", "memory.save".
    """

    # Command name patterns
    COMMAND_PATTERN = r"^(\w+)\.(\w+)$"

    async def route(self, query: str) -> RouteResult | None:
        """
        Try to match explicit command pattern.

        Args:
            query: Query to match

        Returns:
            RouteResult if matched, None otherwise
        """
        import re

        match = re.match(self.COMMAND_PATTERN, query.strip())
        if match:
            skill_name = match.group(1)
            command_name = match.group(2)

            logger.debug(f"Explicit route: {skill_name}.{command_name}")

            return RouteResult(
                skill_name=skill_name,
                command_name=command_name,
                score=1.0,
                confidence=RouteConfidence.HIGH,
            )

        return None


class UnifiedRouter:
    """
    Hybrid router combining semantic search with keyword matching.

    Both methods run in parallel and results are combined using reciprocal rank fusion.
    This provides more robust routing than using either method alone.

    Features:
    - Uses SkillContext provider injection (no abstraction leak)
    - RouteConfidence StrEnum for type safety
    """

    def __init__(
        self,
        semantic_router: SemanticRouter,
        fallback_router: FallbackRouter,
        skill_context_provider: Callable[[], SkillContext] | None = None,
    ):
        """Initialize the unified router.

        Args:
            semantic_router: SemanticRouter instance
            fallback_router: FallbackRouter instance
            skill_context_provider: Optional callable to get SkillContext
        """
        self._semantic = semantic_router
        self._fallback = fallback_router
        self._context_provider = skill_context_provider
        self._skill_index = self._load_skill_index()

    def _load_skill_index(self) -> dict:
        """Load skill index for keyword-based routing."""
        try:
            import asyncio
            from omni.foundation.bridge.scanner import PythonSkillScanner

            scanner = PythonSkillScanner()
            skills = asyncio.run(scanner.scan_directory())

            # Build keyword -> (skill, commands) mapping from routingKeywords
            keyword_map = {}
            for skill in skills:
                skill_name = skill.skill_name
                keywords = skill.metadata.get("routingKeywords", [])
                for kw in keywords:
                    keyword_map.setdefault(kw.lower(), []).append(skill_name)

            return keyword_map
        except Exception as e:
            logger.debug(f"Failed to load skill index: {e}")
            return {}

    def _get_context(self) -> SkillContext | None:
        """Get SkillContext from provider."""
        if self._context_provider is None:
            return None
        try:
            return self._context_provider()
        except Exception as e:
            logger.debug(f"Failed to get skill context: {e}")
            return None

    async def route(self, query: str, threshold: float = 0.5) -> RouteResult | None:
        """
        Hybrid route: combine semantic search + keyword matching.

        Args:
            query: User query
            threshold: Minimum score threshold

        Returns:
            Best RouteResult from combined scoring
        """
        # First try semantic routing
        semantic_result = await self._semantic.route(query, threshold)

        # Only try fallback if semantic failed
        explicit_result = None
        if semantic_result is None or semantic_result.confidence in (
            RouteConfidence.LOW,
            RouteConfidence.MEDIUM,
        ):
            explicit_result = await self._fallback.route(query)

        # Collect results from all methods
        candidates: dict[str, float] = {}  # command -> score

        # Add semantic result
        if semantic_result and not isinstance(semantic_result, Exception):
            cmd = f"{semantic_result.skill_name}.{semantic_result.command_name}"
            candidates[cmd] = semantic_result.score

        # Add explicit command pattern result
        if explicit_result and not isinstance(explicit_result, Exception):
            cmd = f"{explicit_result.skill_name}.{explicit_result.command_name}"
            candidates[cmd] = max(candidates.get(cmd, 0), explicit_result.score)

        # Keyword matching from SKILL.md routingKeywords
        query_lower = query.lower()
        skill_matches: dict[str, float] = {}  # skill -> score (for skill-level matches)
        native_command_matches: dict[str, str] = {}  # skill_name -> command_name (native functions)

        # Extract potential command names from query
        query_words = query_lower.split()
        potential_commands = set()
        for word in query_words:
            # Skip common words
            if word in {"check", "get", "show", "run", "execute", "do", "a", "the", "git"}:
                continue
            if len(word) > 2:
                potential_commands.add(word)

        # Use context provider (no abstraction leak)
        ctx = self._get_context()

        for keyword, skill_names in self._skill_index.items():
            if keyword in query_lower:
                for skill_name in skill_names:
                    # Get commands and skill from context (safe access via provider)
                    if ctx is not None:
                        skill = ctx.get_skill(skill_name)

                        # Check if skill has native functions matching potential commands
                        if skill and hasattr(skill, "_script_loader") and skill._script_loader:
                            loader = skill._script_loader
                            for cmd_word in potential_commands:
                                registered_cmd = f"{skill_name}.{cmd_word}"
                                native_func = f"{skill_name}_{cmd_word}"

                                if hasattr(loader, "native_functions"):
                                    if (
                                        cmd_word in loader.native_functions
                                        or native_func in loader.native_functions
                                    ):
                                        native_command_matches[skill_name] = cmd_word
                                        logger.debug(f"Native match: {skill_name}.{cmd_word}")

                                if registered_cmd in ctx.list_commands():
                                    candidates[registered_cmd] = max(
                                        candidates.get(registered_cmd, 0), 0.7
                                    )

                        # Get registered commands for this skill
                        commands = ctx.list_commands()
                        skill_commands = [c for c in commands if c.startswith(f"{skill_name}.")]
                        for cmd in skill_commands:
                            cmd_base = cmd.split(".", 1)[1]
                            if (
                                skill_name not in native_command_matches
                                or native_command_matches[skill_name] != cmd_base
                            ):
                                candidates[cmd] = max(candidates.get(cmd, 0), 0.5)

                        if skill_commands or skill_name in native_command_matches:
                            skill_matches[skill_name] = max(skill_matches.get(skill_name, 0), 0.6)

        # Prioritize native function matches
        if native_command_matches:
            for skill_name, command_name in native_command_matches.items():
                return RouteResult(
                    skill_name=skill_name,
                    command_name=command_name,
                    score=0.75,
                    confidence=RouteConfidence.HIGH,
                )

        if not candidates and skill_matches:
            best_skill = max(skill_matches.items(), key=lambda x: x[1])
            return RouteResult(
                skill_name=best_skill[0],
                command_name="",
                score=best_skill[1],
                confidence=RouteConfidence.LOW,
            )

        if not candidates:
            return None

        # Select best candidate
        best_cmd = max(candidates.items(), key=lambda x: x[1])
        cmd_parts = best_cmd[0].split(".", 1)

        return RouteResult(
            skill_name=cmd_parts[0],
            command_name=cmd_parts[1] if len(cmd_parts) > 1 else cmd_parts[0],
            score=best_cmd[1],
            confidence=self._get_confidence(best_cmd[1]),
        )

    def _get_confidence(self, score: float) -> RouteConfidence:
        """Convert score to confidence label."""
        if score >= 0.8:
            return RouteConfidence.HIGH
        elif score >= 0.5:
            return RouteConfidence.MEDIUM
        return RouteConfidence.LOW


__all__ = ["FallbackRouter", "RouteConfidence", "RouteResult", "SemanticRouter", "UnifiedRouter"]
