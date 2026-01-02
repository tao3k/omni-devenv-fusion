"""
Phase 9 Specific Stress Tests

Standalone tests for Phase 9 (Code Intelligence / ast-grep).
Uses the modular stress test framework internally.

Run:
    just stress-test          # Run all suites (recommended)
    python test_phase9_stress.py  # Run Phase 9 only
"""
import sys
from pathlib import Path

# Run the main stress test framework which includes Phase 9
sys.path.insert(0, str(Path(__file__).parent))

# Import and run the main framework
from test_stress import main

if __name__ == "__main__":
    sys.exit(main())
