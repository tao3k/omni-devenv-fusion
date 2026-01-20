"""
result.py
 Meta-Agent Result Types

Defines result dataclasses for skill generation and validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GenerationResult:
    """Result of skill generation attempt."""

    success: bool
    skill_name: str
    skill_code: str | None = None
    test_code: str | None = None
    path: Path | None = None
    validation_success: bool = False
    duration_ms: float = 0.0
    error: str | None = None


__all__ = [
    "GenerationResult",
]
