"""
Pytest configuration for stress tests.

Stress tests are separated from the main test suite for performance reasons.
Run them separately with: just test-stress
"""

import pytest
import sys
from pathlib import Path

# Use common.skills_path and common.gitops instead of common.lib
from common.skills_path import SKILLS_DIR
from common.gitops import get_project_root

_PROJECT_ROOT = get_project_root()
