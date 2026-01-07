"""
Pytest configuration for stress tests.

Stress tests are separated from the main test suite for performance reasons.
Run them separately with: just test-stress
"""

import pytest
import sys
from pathlib import Path

# Ensure project root is in path for imports
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_AGENT_SRC = _PROJECT_ROOT / "packages" / "python" / "agent" / "src"
_COMMON_SRC = _PROJECT_ROOT / "packages" / "python" / "common" / "src"

if str(_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_AGENT_SRC))
if str(_COMMON_SRC) not in sys.path:
    sys.path.insert(0, str(_COMMON_SRC))
