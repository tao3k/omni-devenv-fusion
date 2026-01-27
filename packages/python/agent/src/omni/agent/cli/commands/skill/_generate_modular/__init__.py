"""
generate - Modular Skill Generation Package

Submodules:
    rag: RAG retrieval from Semantic Cortex
    verify: Code verification and self-correction
    prompts: LLM prompt templates

Usage:
    from omni.agent.cli.commands.skill.generate import (
        retrieve_similar_skills,
        verify_skill_code,
        fix_skill_code,
    )
"""

from __future__ import annotations

from .rag import format_rag_context, retrieve_similar_skills
from .prompts import generate_commands_prompt, generate_readme_prompt
from .verify import fix_skill_code, generate_fix_prompt, verify_skill_code

__all__ = [
    # RAG
    "retrieve_similar_skills",
    "format_rag_context",
    # Prompts
    "generate_commands_prompt",
    "generate_readme_prompt",
    # Verify
    "verify_skill_code",
    "fix_skill_code",
    "generate_fix_prompt",
]
