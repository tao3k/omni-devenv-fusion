"""
layer2_skills.py - Layer 2: Available Skills (The "Hands").
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Tuple

import structlog

from common.skills_path import SKILLS_DIR
from common.gitops import get_project_root
from common.mcp_core.reference_library import get_reference_path

from .layer_base import ContextLayer

logger = structlog.get_logger(__name__)

_ENCODER = None


def _get_encoder():
    """Lazy import tiktoken encoder."""
    global _ENCODER
    if _ENCODER is None:
        import tiktoken

        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _get_encoder()
    return len(encoder.encode(text))


class Layer2_AvailableSkills(ContextLayer):
    """Layer 2: Available Skills - The Hands of the agent."""

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


__all__ = ["Layer2_AvailableSkills"]
