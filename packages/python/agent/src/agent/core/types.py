"""
agent/core/types.py
 The Knowledge Matrix - Type Definitions

Common types for vector store tables and knowledge management.
"""

from enum import Enum


class VectorTable(str, Enum):
    """Vector store table names."""

    SKILLS = "skills"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"


class ChunkStrategy(str, Enum):
    """Strategies for chunking documents."""

    FILE = "file"  # Whole file as one chunk
    SECTION = "section"  # Split by headers (##)
    PARAGRAPH = "paragraph"  # Split by paragraphs


# Type aliases for clarity
ToolRecord = dict[str, str | list[str] | dict[str, str]]
KnowledgeRecord = dict[str, str | dict[str, str]]
