"""JSON reporter for machine-readable output."""

from __future__ import annotations

import json
import sys

from .base import Reporter


class JsonReporter(Reporter):
    """Prints JSON report to stdout."""

    def __init__(self, stream: object = sys.stdout, indent: int = 2) -> None:
        self._stream = stream
        self._indent = indent

    def emit(self, report: object) -> None:
        """Print JSON report."""
        d = report.to_dict() if hasattr(report, "to_dict") else report
        print(json.dumps(d, indent=self._indent), file=self._stream)
