"""
sniffer - Modular Sniffer Extension Subsystem

Asset-driven detection system for skill activation.

Modules:
- decorators: Define @sniffer decorator for detection functions
- loader: Load sniffer functions from extensions/sniffer/ directory

Usage:
    from omni.core.skills.extensions.sniffer import sniffer, SnifferLoader

    # In extensions/sniffer/venv_check.py:
    from omni.core.skills.extensions.sniffer import sniffer

    @sniffer(name="detect_venv", priority=200)
    def check_venv(cwd: str) -> float:
        import os
        return 1.0 if os.path.exists(os.path.join(cwd, "venv")) else 0.0
"""

from .decorators import sniffer, SnifferFunc, SnifferResult
from .loader import SnifferLoader, load_sniffers_from_path

__all__ = [
    # Decorators
    "sniffer",
    "SnifferFunc",
    "SnifferResult",
    # Loader
    "SnifferLoader",
    "load_sniffers_from_path",
]
