"""
agent/core/context_orchestrator.py
Step 4: Async Trinity Orchestrator.

Evolution:
- Phase 55: Synchronous, string concatenation.
- Step 3: XML Context + Skill Index.
- Step 4 (Current): Fully Async, Parallel Retrieval, Active Memory.

Context Pyramid (Priority Order):
1. System Persona (XML) - The "Soul"
2. Available Skills (JSON) - The "Hands"
3. Project Knowledge (Docs) - The "Textbook"
4. Associative Memories (Vector) - The "Experience"
5. Environment State (Sniffer) - The "Eyes"
6. Code Maps (Tags) - The "Map"
7. Raw Code (File) - The "Ground Truth"
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

import structlog
import tiktoken

from common.gitops import get_project_root
from common.mcp_core.reference_library import get_reference_path

logger = structlog.get_logger(__name__)

# Tokenizer
_ENCODER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_ENCODER.encode(text))


def _truncate_tokens(text: str, max_tokens: int) -> str:
    if not text:
        return ""
    tokens = _ENCODER.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _ENCODER.decode(tokens[:max_tokens])


class ContextLayer:
    """Base class for async context layers."""

    name: str = "base"
    priority: int = 100

    async def assemble(
        self,
        task: str,
        history: List[dict[str, str]],
        budget: int,
    ) -> Tuple[str, int]:
        """
        Asynchronously assemble this layer's context.
        Returns: (content_string, tokens_used)
        """
        raise NotImplementedError


# =============================================================================
# Layer 1: System Persona (The "Soul")
# =============================================================================
class Layer1_SystemPersona(ContextLayer):
    name = "system_persona"
    priority = 1

    # Class-level cache for system context
    _cached_context: str | None = None
    _cached_at: float = 0
    _cached_mtime: float = 0
    _cache_ttl: float = 300.0  # 5 minutes

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        import time

        project_root = get_project_root()

        # 1. Load System Context XML (SSOT: references.yaml)
        sys_ctx_path = project_root / get_reference_path("context.system_context")
        base_prompt = ""

        if sys_ctx_path.exists():
            current_mtime = sys_ctx_path.stat().st_mtime

            if (
                self._cached_context is not None
                and self._cached_mtime == current_mtime
                and time.time() - self._cached_at < self._cache_ttl
            ):
                base_prompt = self._cached_context
                logger.debug("Using cached system_context.xml")
            else:
                content = sys_ctx_path.read_text(encoding="utf-8")
                self._cached_context = content
                self._cached_mtime = current_mtime
                self._cached_at = time.time()
                base_prompt = content
                logger.debug("Loaded and cached system_context.xml")
        else:
            # Fallback for bootstrapping
            base_prompt = """<system_context>
  <role>Omni-Dev: Advanced Cognitive Code Agent</role>
  <architecture>Trinity (CCA)</architecture>
</system_context>"""

        # 2. Load Scratchpad (Current Plan)
        scratchpad = ""
        scratchpad_path = project_root / "SCRATCHPAD.md"
        if scratchpad_path.exists():
            content = scratchpad_path.read_text(encoding="utf-8")
            scratchpad = f"\n<current_plan>\n{content}\n</current_plan>"

        final_content = f"{base_prompt}{scratchpad}"
        return final_content, _count_tokens(final_content)


# =============================================================================
# Layer 2: Available Skills (The "Hands")
# =============================================================================
class Layer2_AvailableSkills(ContextLayer):
    name = "skills"
    priority = 2

    # Class-level cache
    _cached_content: str | None = None
    _cached_tokens: int = 0
    _cached_at: float = 0
    _cache_ttl: float = 60.0  # 60 seconds

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        import time
        from common.skills_path import SKILLS_DIR

        # Check cache freshness
        if self._cached_content is not None and time.time() - self._cached_at < self._cache_ttl:
            logger.debug(f"Layer2: Using cached skills ({time.time() - self._cached_at:.1f}s old)")
            return self._cached_content, self._cached_tokens

        # Try primary path: assets/skills/skill_index.json
        index_path = SKILLS_DIR() / "skill_index.json"

        # Fallback path if generated in docs (SSOT: references.yaml)
        if not index_path.exists():
            project_root = get_project_root()
            index_path = project_root / get_reference_path("context.skill_index")

        skills_content = ""
        tokens = 0

        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))

                # Convert list to compact XML for context efficiency
                skill_lines = []
                for skill in sorted(data, key=lambda x: x.get("name", "").lower()):
                    name = skill.get("name", "unknown")
                    desc = skill.get("description", "")
                    version = skill.get("version", "1.0.0")
                    skill_lines.append(f'  <skill name="{name}" version="{version}">{desc}</skill>')

                skills_content = (
                    "\n<available_skills>\n" + "\n".join(skill_lines) + "\n</available_skills>"
                )
                tokens = _count_tokens(skills_content)

                # Update cache
                self._cached_content = skills_content
                self._cached_tokens = tokens
                self._cached_at = time.time()

                logger.debug(
                    f"Layer2: Built and cached skills ({len(data)} skills, {tokens} tokens)"
                )

            except Exception as e:
                logger.warning(f"Failed to parse skill index: {e}")
                skills_content = "<available_skills error='parse_failed' />"
                tokens = _count_tokens(skills_content)
        else:
            skills_content = "<available_skills status='scanning_required' />"
            tokens = _count_tokens(skills_content)

        return skills_content, tokens


# =============================================================================
# Layer 3: Knowledge & Docs (The "Textbook")
# =============================================================================
class Layer3_Knowledge(ContextLayer):
    name = "knowledge"
    priority = 3

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 500:
            return "", 0

        project_root = get_project_root()
        # SSOT: references.yaml for architecture docs directory
        docs_dir = project_root / get_reference_path("context.architecture_docs_dir")

        relevant_docs = []
        keywords = task.lower().split()

        if docs_dir.exists():
            for doc in docs_dir.glob("*.md"):
                # Very naive relevance check
                if any(k in doc.name.lower() for k in keywords if len(k) > 4):
                    try:
                        content = doc.read_text(encoding="utf-8")
                        truncated = _truncate_tokens(content, 500)  # Cap each doc
                        relevant_docs.append(f"<doc name='{doc.name}'>\n{truncated}\n</doc>")
                    except Exception as e:
                        logger.warning(f"Failed to read doc {doc.name}: {e}")

        if not relevant_docs:
            return "", 0

        content = (
            "\n<relevant_documentation>\n"
            + "\n".join(relevant_docs)
            + "\n</relevant_documentation>"
        )
        return content, _count_tokens(content)


# =============================================================================
# Layer 4: Associative Memories (The "Experience")
# =============================================================================
class Layer4_AssociativeMemories(ContextLayer):
    name = "memories"
    priority = 4

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 300:
            return "", 0

        try:
            # Async Vector Search!
            from agent.core.vector_store import get_vector_memory

            vm = get_vector_memory()

            # Construct query from task + last user message
            query = task
            if history:
                query += f" {history[-1].get('content', '')}"

            # Search specifically for past lessons/reflections
            results = await vm.search(query, n_results=3)

            if not results:
                return "", 0

            memories = []
            for res in results:
                # Format: similarity_score | content
                score = res.get("score", 0.0)
                text = res.get("content", "").strip()
                if text and score > 0.7:  # Only high relevance
                    memories.append(f"<memory score='{score:.2f}'>{text}</memory>")

            if not memories:
                return "", 0

            content = "\n<associative_memory>\n" + "\n".join(memories) + "\n</associative_memory>"
            return content, _count_tokens(content)

        except Exception as e:
            logger.warning(f"Layer 4 Memory search failed: {e}")
            return "", 0


# =============================================================================
# Layer 5: Environment (The "Eyes")
# =============================================================================
class Layer5_Environment(ContextLayer):
    name = "environment"
    priority = 5

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        try:
            # Try to use omni_core_rs for Rust-accelerated sniffer
            omni = None
            try:
                import omni_core_rs

                omni = omni_core_rs
            except ImportError:
                pass

            if omni is None:
                return "", 0

            # Run sync sniffer in thread to not block event loop
            def _scan():
                return omni.get_environment_snapshot(str(get_project_root()))

            snapshot = await asyncio.to_thread(_scan)
            content = f"\n<environment_state>\n{snapshot}\n</environment_state>"
            return content, _count_tokens(content)

        except Exception as e:
            logger.warning(f"Sniffer failed: {e}")
            return "", 0


# =============================================================================
# Layer 6: Code Maps (The "Map")
# =============================================================================
class Layer6_CodeMaps(ContextLayer):
    name = "code_maps"
    priority = 6

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 200:
            return "", 0

        try:
            omni = None
            try:
                import omni_core_rs

                omni = omni_core_rs
            except ImportError:
                pass

            if omni is None:
                return "", 0

            project_root = get_project_root()
            content_parts = ["\n<code_maps>"]

            # Get outline of key files
            key_files = [
                project_root / "packages/python/agent/src/agent/main.py",
                project_root / "packages/python/agent/src/agent/core/orchestrator/core.py",
            ]

            for file_path in key_files:
                if file_path.exists():
                    try:
                        outline = omni.get_file_outline(str(file_path))
                        if outline and "Error" not in outline:
                            rel_path = file_path.relative_to(project_root)
                            content_parts.append(f"\n### {rel_path}\n{outline}")
                    except Exception:
                        pass

            content_parts.append("\n</code_maps>")
            content = "".join(content_parts)
            return content, _count_tokens(content)

        except Exception as e:
            logger.warning(f"Code maps failed: {e}")
            return "", 0


# =============================================================================
# Layer 7: Raw Code (The "Ground Truth")
# =============================================================================
class Layer7_RawCode(ContextLayer):
    name = "raw_code"
    priority = 7

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 100:
            return "", 0

        try:
            # Read the most recently mentioned file in history
            if history:
                last_msg = history[-1].get("content", "")
                import re

                paths = re.findall(r"([a-zA-Z0-9_/.-]+\.py)", last_msg)

                if paths:
                    file_path = Path(paths[0])
                    if not file_path.is_absolute():
                        file_path = get_project_root() / file_path

                    if file_path.exists():
                        content = file_path.read_text(encoding="utf-8")
                        # Truncate to remaining budget
                        truncated = _truncate_tokens(content, budget)
                        rel_path = file_path.relative_to(get_project_root())

                        added_note = ""
                        if len(truncated) < len(content):
                            added_note = f"\n\n[... Content truncated, {len(content) - len(truncated)} chars hidden ...]"

                        return (
                            f"\n\n## Active File: {rel_path}\n```{truncated}```{added_note}",
                            _count_tokens(truncated),
                        )

            return "", 0

        except Exception as e:
            logger.warning(f"Raw code read failed: {e}")
            return "", 0


# =============================================================================
# ContextOrchestrator: The Async Conductor
# =============================================================================
class ContextOrchestrator:
    """
    The Async Conductor.
    Orchestrates parallel retrieval of context layers.
    """

    def __init__(self, max_tokens: int = 128000, output_ratio: float = 0.2):
        self.max_tokens = max_tokens
        self.input_budget = int(max_tokens * (1 - output_ratio))

        # Initialize layers in priority order
        self.layers: List[ContextLayer] = [
            Layer1_SystemPersona(),  # System Persona (XML)
            Layer2_AvailableSkills(),  # Available Skills (JSON)
            Layer3_Knowledge(),  # Project Knowledge (Docs)
            Layer4_AssociativeMemories(),  # Associative Memories (Vector)
            Layer5_Environment(),  # Environment State (Sniffer)
            Layer6_CodeMaps(),  # Code Maps (Tags)
            Layer7_RawCode(),  # Raw Code (File)
        ]

        logger.info(
            "ContextOrchestrator initialized",
            max_tokens=max_tokens,
            input_budget=self.input_budget,
            layers=len(self.layers),
        )

    async def build_prompt(self, task: str, history: List[dict[str, str]]) -> str:
        """
        Builds the prompt by executing layers in sequence (respecting budget).
        Note: We run layers sequentially to respect token budget constraints.
        """
        current_budget = self.input_budget
        final_parts = []

        logger.info("ContextOrchestrator: Assembling async context", task=task[:50])

        for layer in self.layers:
            if current_budget <= 0:
                logger.info(f"Budget exhausted before layer {layer.name}")
                break

            try:
                # Await the layer!
                content, used = await layer.assemble(task, history, current_budget)

                if content and used > 0:
                    final_parts.append(content)
                    current_budget -= used
                    logger.debug(f"Layer {layer.name} added {used} tokens")

            except Exception as e:
                logger.error(f"Layer {layer.name} crashed", error=str(e))

        prompt = "\n".join(final_parts)

        total_tokens = _count_tokens(prompt)
        logger.info(
            "Context assembled",
            total_tokens=total_tokens,
            budget_remaining=current_budget,
        )

        return prompt

    def get_context_stats(self, prompt: str) -> dict[str, Any]:
        count = _count_tokens(prompt)
        return {
            "total_tokens": count,
            "max_tokens": self.max_tokens,
            "utilization": count / self.max_tokens,
        }


# Singleton
_orchestrator: Optional[ContextOrchestrator] = None


def get_context_orchestrator(max_tokens: int = 128000) -> ContextOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ContextOrchestrator(max_tokens)
    return _orchestrator


def build_context(task: str, history: List[dict[str, str]]) -> str:
    """
    Synchronous wrapper for legacy code.
    Use async build_prompt() for new code.
    """
    orch = get_context_orchestrator()
    try:
        loop = asyncio.get_running_loop()
        # If we are already in a loop, we can't block.
        return "ERROR: build_context called from async context. Use await orchestrator.build_prompt() instead."
    except RuntimeError:
        return asyncio.run(orch.build_prompt(task, history))


__all__ = [
    "ContextOrchestrator",
    "get_context_orchestrator",
    "build_context",
    "ContextLayer",
    "Layer1_SystemPersona",
    "Layer2_AvailableSkills",
    "Layer3_Knowledge",
    "Layer4_AssociativeMemories",
    "Layer5_Environment",
    "Layer6_CodeMaps",
    "Layer7_RawCode",
]
