"""
Stress Test Suite - Modular Framework

Uses the modular stress test framework from stress/.

Run: just stress-test
"""
import sys
from pathlib import Path

# Add mcp-server to path for imports
_mcp_path = Path(__file__).parent.parent
if str(_mcp_path) not in sys.path:
    sys.path.insert(0, str(_mcp_path))

# Import Phase 9 tests
from stress.suites.phase9 import (
    test_phase9_benchmarks,
    test_phase9_logic_depth,
    test_phase9_stability,
    test_phase9_full_suite
)

__all__ = [
    "test_phase9_benchmarks",
    "test_phase9_logic_depth",
    "test_phase9_stability",
    "test_phase9_full_suite",
]
