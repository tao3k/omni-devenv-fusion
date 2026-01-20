"""
layers/__init__.py - Context Layers for ContextOrchestrator.

Each layer provides a specific type of context for the agent.
"""

from .layer_base import ContextLayer
from .layer1_persona import Layer1_SystemPersona
from .layer2_skills import Layer2_AvailableSkills
from .layer3_knowledge import Layer3_Knowledge
from .layer4_memories import Layer4_AssociativeMemories
from .layer5_env import Layer5_Environment
from .layer6_maps import Layer6_CodeMaps
from .layer7_code import Layer7_RawCode
from .layer1_5_memory import Layer1_5_SkillMemory

__all__ = [
    "ContextLayer",
    "Layer1_SystemPersona",
    "Layer2_AvailableSkills",
    "Layer3_Knowledge",
    "Layer4_AssociativeMemories",
    "Layer5_Environment",
    "Layer6_CodeMaps",
    "Layer7_RawCode",
    "Layer1_5_SkillMemory",
]
