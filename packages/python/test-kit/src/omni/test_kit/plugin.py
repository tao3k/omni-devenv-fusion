import sys
from pathlib import Path
import pytest
from omni.test_kit.decorators import load_test_cases

# Register fixtures from fixtures.py
pytest_plugins = [
    "omni.test_kit.fixtures",
    "omni.test_kit.mcp",
    "omni.test_kit.langgraph",
    "omni.test_kit.core",
]


def pytest_load_initial_conftests(early_config, parser, args):
    """
    Hook to set up environment before tests start.
    Adds assets/skills to sys.path to allow direct imports in skill tests.
    """
    # Find project root (assuming this file is in packages/python/test-kit/src/omni/test_kit)
    # We need to go up 5 levels to reach root from src/omni/test_kit/plugin.py
    # .../omni-dev-fusion/packages/python/test-kit/src/omni/test_kit/plugin.py

    # Alternatively, locate based on 'assets' existence
    current = Path(__file__).resolve()
    # traverse up until we find 'assets' directory
    root = None
    for parent in current.parents:
        if (parent / "assets" / "skills").exists():
            root = parent
            break

    if root:
        skills_dir = root / "assets" / "skills"
        if str(skills_dir) not in sys.path:
            sys.path.insert(0, str(skills_dir))


def pytest_generate_tests(metafunc):
    """
    Custom parametrization logic for Omni Test Kit.

    Handles @data_driven marker by loading files relative to the test module.
    """
    marker = metafunc.definition.get_closest_marker("omni_data_driven")
    if marker:
        data_path = marker.kwargs.get("data_path")
        if data_path:
            # Resolve relative to the test file
            test_dir = Path(metafunc.module.__file__).parent
            full_path = test_dir / data_path

            cases = load_test_cases(str(full_path))
            if cases:
                metafunc.parametrize("case", cases, ids=[c.name for c in cases])


def pytest_configure(config):
    """Register markers."""
    config.addinivalue_line(
        "markers", "omni_data_driven: mark tests for data-driven execution with Omni test-kit"
    )
    config.addinivalue_line("markers", "omni_skill: mark tests for a specific Omni skill")
