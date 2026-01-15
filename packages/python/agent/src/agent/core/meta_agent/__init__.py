"""
agent/core/meta_agent/__init__.py
 The Meta-Agent (Self-Evolution & JIT)

Meta-Agent enables the Agent to:
1. Generate new skills on-demand using LLM
2. Harvest frequently-used patterns from session notes
3. Self-evolve by identifying missing capabilities

Usage:
    from agent.core.meta_agent import MetaAgent, SkillHarvester

    meta = MetaAgent()
    skill = await meta.generate_skill("I need a skill to convert CSV to JSON")
"""

from .prompt import MetaAgentPrompt
from .harvester import SkillHarvester

__all__ = [
    "MetaAgentPrompt",
    "SkillHarvester",
]
