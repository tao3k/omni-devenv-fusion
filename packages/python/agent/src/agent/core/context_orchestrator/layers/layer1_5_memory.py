"""
layer1_5_memory.py - Layer 1.5: Skill Memory (The "Skill Protocols").

Inject SKILL.md content for both Core Skills (persistent) and Active Skills (task-relevant).

Supports SKILL.md syntax for auto-loading references:
```markdown
<!-- require_refs:
- assets/skills/writer/references/writing-style/00_index.md
- assets/skills/writer/references/writing-style/01_philosophy.md
-->
```
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

import structlog

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


# Regex for parsing require_refs in SKILL.md
_REQUIRE_REFS_PATTERN = re.compile(
    r"<!--\s*require_refs:\s*\n((?:\s*-\s*[^\n]+\n)+)\s*-->", re.MULTILINE
)


class Layer1_5_SkillMemory(ContextLayer):
    """
    Layer 1.5: Skill Memory - Skill Protocols for the agent.

    Injects:
    - Core Skills: Preloaded skills (git, memory, knowledge) - always present
    - Active Skills: Skills relevant to the current task
    - Required References: Files declared in SKILL.md via `<!-- require_refs: -->`
    """

    name = "skill_memory"
    priority = 15  # Between Layer1 (1) and Layer2 (2)

    def __init__(self, skill_prompts: Dict[str, str] | None = None) -> None:
        """
        Initialize Skill Memory layer.

        Args:
            skill_prompts: Dict mapping skill_name -> SKILL.md content
        """
        self.skill_prompts = skill_prompts or {}

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        parts = []

        # 1. Parse required references from SKILL.md and inject them
        required_refs = self._parse_required_refs()
        if required_refs:
            ref_content = self._load_required_refs(required_refs)
            if ref_content:
                parts.append(f"\n<skill_references>\n{ref_content}\n</skill_references>")
                logger.debug(f"Layer1.5: Loaded {len(required_refs)} required references")

        # 2. Skill Protocols
        if self.skill_prompts:
            sorted_skills = sorted(self.skill_prompts.keys())
            parts.append("\n<skill_protocols>")

            for skill_name in sorted_skills:
                content = self.skill_prompts[skill_name]
                parts.append(f'\n<protocol name="{skill_name}">')
                parts.append(content)
                parts.append(f"</protocol>")

            parts.append("\n</skill_protocols>")

        full_text = "".join(parts)
        tokens = _count_tokens(full_text)

        if self.skill_prompts:
            logger.debug(f"Layer1.5: {len(self.skill_prompts)} protocols, {tokens} tokens")

        return full_text, tokens

    def _parse_required_refs(self) -> List[str]:
        """Parse require_refs declarations from all SKILL.md content."""
        refs = []
        for skill_name, content in self.skill_prompts.items():
            matches = _REQUIRE_REFS_PATTERN.findall(content)
            for match in matches:
                # Parse YAML-like list
                for line in match.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("- "):
                        ref_path = line[2:].strip()
                        if ref_path and ref_path not in refs:
                            refs.append(ref_path)
                            logger.debug(f"Layer1.5: Found require_ref in {skill_name}: {ref_path}")
        return refs

    def _load_required_refs(self, ref_paths: List[str]) -> str | None:
        """Load and concatenate required reference files."""
        parts = []
        for ref_path in ref_paths:
            try:
                # Try absolute path first
                path = Path(ref_path)
                if not path.is_absolute():
                    # Try relative to project root
                    from common.gitops import get_project_root

                    root = get_project_root()
                    path = root / ref_path

                if path.exists():
                    content = path.read_text(encoding="utf-8")
                    rel_path = path.relative_to(Path.cwd()) if path.is_absolute() else path
                    parts.append(f"\n### {rel_path}\n{content}")
                    logger.debug(f"Layer1.5: Loaded reference {ref_path}")
                else:
                    logger.warning(f"Layer1.5: Reference not found: {ref_path}")
            except Exception as e:
                logger.warning(f"Layer1.5: Failed to load reference {ref_path}: {e}")

        return "".join(parts) if parts else None


__all__ = ["Layer1_5_SkillMemory"]
