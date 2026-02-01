"""
Memory package - Long-term memory storage and retrieval.

Components:
- archiver: Flushes messages from RAM to Vector DB (LanceDB)
- retrospective: Post-execution memory distillation
- hippocampus: Experience-driven reasoning for long-term memory
- schemas: Pydantic models for memory data structures
"""

from .archiver import MemoryArchiver
from .retrospective import (
    create_session_retrospective,
    format_retrospective,
    extract_knowledge_to_save,
)
from .hippocampus import (
    Hippocampus,
    get_hippocampus,
    create_hippocampus_trace,
    HIPPOCAMPUS_COLLECTION,
)
from .schemas import (
    ExecutionStep,
    HippocampusTrace,
    ExperienceMetadata,
    ExperienceRecallResult,
)

__all__ = [
    "MemoryArchiver",
    "create_session_retrospective",
    "format_retrospective",
    "extract_knowledge_to_save",
    "Hippocampus",
    "get_hippocampus",
    "create_hippocampus_trace",
    "HIPPOCAMPUS_COLLECTION",
    "ExecutionStep",
    "HippocampusTrace",
    "ExperienceMetadata",
    "ExperienceRecallResult",
]
