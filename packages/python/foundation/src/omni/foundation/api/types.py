"""
types.py - Common API Types (Pillar A: Pydantic Shield)

Updated for ODF-EP v6.0 with Python 3.12 PEP 695:
- Modern type alias syntax using `type` keyword
- Simplified generics without TypeVar boilerplate

Features:
- Integrated orjson for high-performance serialization.
- Base CommandResult with Generics.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

import orjson
from pydantic import BaseModel, ConfigDict, Field, computed_field

# Type variable for CommandResult generic (required for Pydantic Generic[T])
T = TypeVar("T")

# Common type aliases using modern PEP 695 syntax (Python 3.12+)
type JsonBytes = bytes
type JsonStr = str
type ErrorMsg = str | None
type Metadata = dict[str, Any]
type DurationMs = float
type RetryCount = int


class OrjsonModel(BaseModel):
    """
    [Performance Core] Base model powered by orjson.

    Features:
    - 10x faster serialization than standard json.
    - Native support for datetime, numpy, etc.
    - Produces compact byte strings perfect for network transmission (MCP).
    """

    def model_dump_json_bytes(self, **kwargs) -> bytes:
        """Dump to JSON bytes using orjson (Ultra Fast)."""
        return orjson.dumps(self.model_dump(mode="json", **kwargs))

    def model_dump_json_str(self, **kwargs) -> str:
        """Dump to JSON string using orjson."""
        return orjson.dumps(self.model_dump(mode="json", **kwargs)).decode()


class CommandResult(OrjsonModel, Generic[T]):
    """
    Structured output for all skill commands using Pydantic V2 Generics.
    """

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    success: bool = Field(..., description="Execution success status")
    data: T = Field(..., description="Result payload (typed)")
    error: ErrorMsg = Field(None, description="Error message if failed")
    metadata: Metadata = Field(default_factory=dict, description="Execution context metadata")

    @computed_field
    @property
    def is_retryable(self) -> bool:
        """Check if the error is retryable (transient failure)."""
        if self.success or self.error is None:
            return False
        transient_errors = {
            "connection",
            "timeout",
            "network",
            "temporary",
            "rate limit",
            "503",
            "502",
            "504",
            "lock",
            "busy",
        }
        return any(t in self.error.lower() for t in transient_errors)

    @computed_field
    @property
    def retry_count(self) -> int:
        """Get retry count from metadata."""
        return self.metadata.get("retry_count", 0)

    @computed_field
    @property
    def duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        return self.metadata.get("duration_ms", 0.0)


__all__ = [
    # Classes
    "CommandResult",
    "OrjsonModel",
    # Type variable
    "T",
    # PEP 695 type aliases
    "JsonBytes",
    "JsonStr",
    "ErrorMsg",
    "Metadata",
    "DurationMs",
    "RetryCount",
]
