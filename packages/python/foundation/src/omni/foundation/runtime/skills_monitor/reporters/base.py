"""Base reporter protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import MonitorReport


class Reporter(ABC):
    """Output format for monitor reports."""

    @abstractmethod
    def emit(self, report: MonitorReport) -> None:
        """Emit the report (print, write to file, etc.)."""
        ...
