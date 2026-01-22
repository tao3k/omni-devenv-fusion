"""
Test Dual-Layer Configuration Loading - Subprocess Isolation.

Uses subprocess to avoid singleton thread lock issues.
"""

from __future__ import annotations

import subprocess
import sys


def run_test(script: str) -> tuple[int, str, str]:
    """Run a test script in a subprocess and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd="/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion",
    )
    return result.returncode, result.stdout, result.stderr


def test_defaults_loaded():
    """Test 1: Defaults loaded from assets."""
    script = """
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    # Create assets with defaults
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "settings.yaml").write_text("core:\\n  timeout: 30\\n  mode: default")

    # Empty user config
    user_conf = tmp_path / ".config"
    user_conf.mkdir()

    with patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}):
        with patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path):
            from omni.foundation.config.settings import Settings
            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.timeout") == 30, f"Expected 30, got {settings.get('core.timeout')}"
            assert settings.get("core.mode") == "default", f"Expected default, got {settings.get('core.mode')}"
            print("PASS: test_defaults_loaded")
"""
    code, stdout, stderr = run_test(script)
    print(f"test_defaults_loaded: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_user_override():
    """Test 2: User config overrides defaults."""
    script = """
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    # Create assets with defaults
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "settings.yaml").write_text("core:\\n  timeout: 30\\n  mode: default")

    # User config with override
    user_conf = tmp_path / ".config"
    user_conf.mkdir()
    (user_conf / "settings.yaml").write_text("core:\\n  mode: turbo")

    with patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}):
        with patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path):
            from omni.foundation.config.settings import Settings
            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "turbo", f"Expected turbo, got {settings.get('core.mode')}"
            assert settings.get("core.timeout") == 30, f"Expected 30, got {settings.get('core.timeout')}"
            print("PASS: test_user_override")
"""
    code, stdout, stderr = run_test(script)
    print(f"test_user_override: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_deep_merge():
    """Test 3: Deep merge preserves nested structure."""
    script = """
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    # Create assets with nested defaults
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "settings.yaml").write_text("api:\\n  base_url: https://api.example.com\\n  timeout: 10")

    # User config with nested override
    user_conf = tmp_path / ".config"
    user_conf.mkdir()
    (user_conf / "settings.yaml").write_text("api:\\n  timeout: 60")

    with patch.dict(os.environ, {"PRJ_CONFIG_HOME": str(user_conf)}):
        with patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path):
            from omni.foundation.config.settings import Settings
            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("api.timeout") == 60, f"Expected 60, got {settings.get('api.timeout')}"
            assert settings.get("api.base_url") == "https://api.example.com", f"Expected URL, got {settings.get('api.base_url')}"
            print("PASS: test_deep_merge")
"""
    code, stdout, stderr = run_test(script)
    print(f"test_deep_merge: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


def test_cli_conf_flag():
    """Test 4: CLI --conf flag has highest priority."""
    script = """
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    # Create assets with defaults
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "settings.yaml").write_text("core:\\n  timeout: 30\\n  mode: default")

    # Custom config dir (from --conf)
    custom_conf = tmp_path / "custom_conf"
    custom_conf.mkdir()
    (custom_conf / "settings.yaml").write_text("core:\\n  mode: from-cli")

    # Default config dir (should be ignored)
    default_conf = tmp_path / ".config"
    default_conf.mkdir()
    (default_conf / "settings.yaml").write_text("core:\\n  mode: from-env")

    # Simulate CLI: python app.py --conf /path/to/custom_conf
    test_args = ["app.py", "--conf", str(custom_conf)]

    with patch.object(sys, "argv", test_args):
        with patch("omni.foundation.config.settings.get_project_root", return_value=tmp_path):
            from omni.foundation.config.settings import Settings
            Settings._instance = None
            Settings._loaded = False
            settings = Settings()

            assert settings.get("core.mode") == "from-cli", f"Expected from-cli, got {settings.get('core.mode')}"
            assert settings.get("core.timeout") == 30, f"Expected 30, got {settings.get('core.timeout')}"
            assert os.environ.get("PRJ_CONFIG_HOME") == str(custom_conf), f"Expected {custom_conf}, got {os.environ.get('PRJ_CONFIG_HOME')}"
            print("PASS: test_cli_conf_flag")
"""
    code, stdout, stderr = run_test(script)
    print(f"test_cli_conf_flag: {'PASS' if code == 0 else 'FAIL'}")
    if code != 0:
        print(f"  stderr: {stderr}")
    return code == 0


if __name__ == "__main__":
    print("=" * 60)
    print("Dual-Layer Configuration Loading Tests")
    print("=" * 60)

    results = [
        test_defaults_loaded(),
        test_user_override(),
        test_deep_merge(),
        test_cli_conf_flag(),
    ]

    passed = sum(results)
    total = len(results)

    print()
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    sys.exit(0 if all(results) else 1)
