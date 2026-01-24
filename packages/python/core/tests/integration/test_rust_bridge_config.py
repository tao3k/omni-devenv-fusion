"""
Rust Bridge Config Sync Tests

Tests that Rust side correctly respects environment variables set by
Python Agent Bootstrap, preventing Split-Brain scenarios.

PRJ_SPEC Compliance:
- PRJ_CONFIG_HOME: Configuration directory
- PRJ_DATA_HOME: Data directory
- PRJ_CACHE_HOME: Cache directory

Cross-Language Sync:
- Python sets os.environ["PRJ_CONFIG_HOME"] during bootstrap
- Rust reads the same environment variable via omni-io::PrjDirs
- Both sides use the same configuration path

Note: Tests run in subprocess to avoid OnceLock caching issues.
"""

import subprocess
import sys

from omni.foundation.runtime.gitops import get_project_root


def run_rust_test(script: str) -> tuple[int, str, str]:
    """Run a test script in a subprocess."""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(get_project_root()),
    )
    return result.returncode, result.stdout, result.stderr


def test_rust_respects_python_env_config_home():
    """Verify Rust sees PRJ_CONFIG_HOME when Python sets it."""
    script = """
import os
import omni_core_rs as rs

custom_conf = "/tmp/omni_custom_config_test"
os.environ["PRJ_CONFIG_HOME"] = custom_conf

rust_seen_path = rs.get_config_home()

if rust_seen_path == custom_conf:
    print(f"PASS: Rust saw '{rust_seen_path}' = Python set '{custom_conf}'")
else:
    print(f"FAIL: Rust saw '{rust_seen_path}' but Python set '{custom_conf}'")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_rust_respects_python_env_config_home: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_rust_respects_python_env_data_home():
    """Verify Rust sees PRJ_DATA_HOME when Python sets it."""
    script = """
import os
import omni_core_rs as rs

custom_data = "/custom/data/path"
os.environ["PRJ_DATA_HOME"] = custom_data

rust_seen_path = rs.get_data_home()

if rust_seen_path == custom_data:
    print(f"PASS: Rust saw '{rust_seen_path}' = Python set '{custom_data}'")
else:
    print(f"FAIL: Rust saw '{rust_seen_path}' but Python set '{custom_data}'")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_rust_respects_python_env_data_home: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_rust_respects_python_env_cache_home():
    """Verify Rust sees PRJ_CACHE_HOME when Python sets it."""
    script = """
import os
import omni_core_rs as rs

custom_cache = "/custom/cache/path"
os.environ["PRJ_CACHE_HOME"] = custom_cache

rust_seen_path = rs.get_cache_home()

if rust_seen_path == custom_cache:
    print(f"PASS: Rust saw '{rust_seen_path}' = Python set '{custom_cache}'")
else:
    print(f"FAIL: Rust saw '{rust_seen_path}' but Python set '{custom_cache}'")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_rust_respects_python_env_cache_home: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_rust_fallback_to_default():
    """Verify Rust falls back to defaults when env var is not set."""
    script = """
import os
import omni_core_rs as rs

if "PRJ_CONFIG_HOME" in os.environ:
    del os.environ["PRJ_CONFIG_HOME"]

rust_seen_path = rs.get_config_home()

if ".config" in rust_seen_path:
    print(f"PASS: Rust fallback includes '.config': {rust_seen_path}")
else:
    print(f"FAIL: Expected '.config' in path, got: {rust_seen_path}")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_rust_fallback_to_default: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_relative_path_resolution():
    """Verify Rust correctly resolves relative paths against project root."""
    script = """
import os
import omni_core_rs as rs

os.environ["PRJ_CONFIG_HOME"] = ".omni_custom"
os.environ["PRJ_ROOT"] = "/test/project"

rust_seen_path = rs.get_config_home()

expected = "/test/project/.omni_custom"
if rust_seen_path == expected:
    print(f"PASS: Relative path resolved correctly: {rust_seen_path}")
else:
    print(f"FAIL: Expected '{expected}', got '{rust_seen_path}'")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_relative_path_resolution: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_consistency_with_python_dirs():
    """Verify Rust and Python return consistent paths."""
    script = """
import os
from omni.foundation.config.dirs import PRJ_DIRS
import omni_core_rs as rs

test_conf = "/shared/config"
os.environ["PRJ_CONFIG_HOME"] = test_conf

rust_path = rs.get_config_home()
python_path = str(PRJ_DIRS.config_home)

if rust_path == python_path == test_conf:
    print(f"PASS: Rust={rust_path}, Python={python_path}, Expected={test_conf}")
else:
    print(f"FAIL: Inconsistent paths: Rust={rust_path}, Python={python_path}, Expected={test_conf}")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_consistency_with_python_dirs: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_bootstrap_to_rust_path():
    """End-to-end test: Python bootstrap -> Rust path."""
    script = """
import os
import omni_core_rs as rs

custom_conf = "/etc/omni"
os.environ["PRJ_CONFIG_HOME"] = custom_conf

rust_config = rs.get_config_home()

if rust_config == custom_conf:
    print(f"PASS: Bootstrap->Rust path verified: {rust_config}")
else:
    print(f"FAIL: Expected '{custom_conf}', got '{rust_config}'")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_bootstrap_to_rust_path: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_multiple_env_vars_consistency():
    """Test multiple environment variables are consistent."""
    script = """
import os
import omni_core_rs as rs

os.environ["PRJ_CONFIG_HOME"] = "/etc/omni"
os.environ["PRJ_DATA_HOME"] = "/var/omni/data"
os.environ["PRJ_CACHE_HOME"] = "/var/omni/cache"

config = rs.get_config_home()
data = rs.get_data_home()
cache = rs.get_cache_home()

if config == "/etc/omni" and data == "/var/omni/data" and cache == "/var/omni/cache":
    print(f"PASS: config={config}, data={data}, cache={cache}")
else:
    print(f"FAIL: Expected specific paths, got config={config}, data={data}, cache={cache}")
    exit(1)
"""
    code, stdout, stderr = run_rust_test(script)
    print(f"test_multiple_env_vars_consistency: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


if __name__ == "__main__":
    print("=" * 60)
    print("Rust Bridge Config Sync Tests")
    print("=" * 60)

    results = [
        test_rust_respects_python_env_config_home(),
        test_rust_respects_python_env_data_home(),
        test_rust_respects_python_env_cache_home(),
        test_rust_fallback_to_default(),
        test_relative_path_resolution(),
        test_consistency_with_python_dirs(),
        test_bootstrap_to_rust_path(),
        test_multiple_env_vars_consistency(),
    ]

    passed = sum(results)
    total = len(results)

    print()
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    sys.exit(0 if all(results) else 1)
