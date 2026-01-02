"""
Pytest configuration and fixtures for stress tests.
"""
import pytest
from pathlib import Path

from stress import (
    StressConfig, load_config, set_config
)


@pytest.fixture
def stress_config() -> StressConfig:
    """Provide default stress test configuration."""
    return StressConfig()


@pytest.fixture
def stress_dir(tmp_path: Path) -> Path:
    """Provide a temporary stress test directory."""
    stress_dir = tmp_path / "stress_data"
    stress_dir.mkdir(parents=True)
    yield stress_dir


@pytest.fixture
async def stress_env(stress_dir: Path, stress_config: StressConfig):
    """Provide a fully setup stress test environment with generated files."""
    import shutil

    # Apply config
    set_config(stress_config)

    # Generate noise files
    for i in range(stress_config.noise_files):
        (stress_dir / f"noise_{i}.py").write_text(f"""def func_{i}():
    x = {i}
    return x * 2
""")

    # Generate target files
    for i in range(900, 900 + stress_config.target_files):
        (stress_dir / f"target_{i}.py").write_text(f"""def risky_logic_{i}():
    try:
        process_data({i})
        return True
    except ValueError:
        pass  # Silent Killer

def another_func_{i}():
    try:
        api_call()
    except Exception:
        pass  # Silent Killer

def normal_func_{i}():
    try:
        do_work()
    except ValueError as e:
        raise
""")

    yield stress_dir, stress_config

    # Cleanup
    if stress_config.cleanup_after and stress_dir.exists():
        shutil.rmtree(stress_dir)


@pytest.fixture
def silent_killer_pattern() -> str:
    """Pattern for finding try-except-pass blocks."""
    return """try:
  $$BODY
except $ERR:
  pass"""


@pytest.fixture
def nested_pattern() -> str:
    """Pattern for deep recursion testing."""
    return "call($A, call($B, call($C, $D)))"


@pytest.fixture
def broken_python_file(stress_dir: Path) -> Path:
    """Create a malformed Python file for stability testing."""
    broken = stress_dir / "broken.py"
    broken.write_text("def broken_syntax(:\n    print 'oops\n    if True:")
    return broken


@pytest.fixture
def binary_file(stress_dir: Path) -> Path:
    """Create a binary file for stability testing."""
    binary = stress_dir / "data.bin"
    binary.write_bytes(b"\x00\x01\x02\x03\x04\x05")
    return binary
