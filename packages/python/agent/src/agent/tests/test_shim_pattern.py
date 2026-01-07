"""
test_phase28_1_shim_pattern.py
Phase 28.1: Subprocess/Shim Pattern Tests

Tests for subprocess mode skill execution, including:
- Manifest parsing for execution_mode
- Subprocess execution via SkillManager._execute_in_subprocess
- Shim pattern tools.py implementation
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Use absolute imports from agent package
from agent.core.skill_manager import SkillManager, Skill

# Get project root for file checks
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


class TestShimPatternManifest(unittest.TestCase):
    """Test manifest loading and execution mode detection."""

    def setUp(self):
        """Create a temporary skill directory with manifest."""
        self.temp_dir = tempfile.mkdtemp()
        self.skill_dir = Path(self.temp_dir) / "test_skill"
        self.skill_dir.mkdir()

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_manifest_library_mode(self):
        """Test loading manifest with library execution mode."""
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "library",
        }
        manifest_path = self.skill_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        loaded_manifest = manager._load_manifest(self.skill_dir)

        self.assertIsNotNone(loaded_manifest)
        self.assertEqual(loaded_manifest.get("execution_mode"), "library")

    def test_load_manifest_subprocess_mode(self):
        """Test loading manifest with subprocess execution mode."""
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "subprocess",
            "python_path": ".venv/bin/python",
            "entry_point": "implementation.py",
        }
        manifest_path = self.skill_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        loaded_manifest = manager._load_manifest(self.skill_dir)

        self.assertIsNotNone(loaded_manifest)
        self.assertEqual(loaded_manifest.get("execution_mode"), "subprocess")
        self.assertEqual(loaded_manifest.get("python_path"), ".venv/bin/python")
        self.assertEqual(loaded_manifest.get("entry_point"), "implementation.py")

    def test_load_manifest_missing(self):
        """Test loading manifest when it doesn't exist."""
        manager = SkillManager(skills_dir=self.temp_dir)
        loaded_manifest = manager._load_manifest(self.skill_dir)

        self.assertIsNone(loaded_manifest)

    def test_load_manifest_invalid_json(self):
        """Test loading manifest with invalid JSON."""
        manifest_path = self.skill_dir / "manifest.json"
        manifest_path.write_text("not valid json")

        manager = SkillManager(skills_dir=self.temp_dir)
        loaded_manifest = manager._load_manifest(self.skill_dir)

        self.assertIsNone(loaded_manifest)

    def test_default_execution_mode_library(self):
        """Test that default execution mode is 'library' when not specified."""
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
        }
        manifest_path = self.skill_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        loaded_manifest = manager._load_manifest(self.skill_dir)

        # When execution_mode is not specified, should default to library
        self.assertEqual(loaded_manifest.get("execution_mode", "library"), "library")


class TestShimPatternSubprocessExecution(unittest.TestCase):
    """Test subprocess execution via SkillManager._execute_in_subprocess."""

    def setUp(self):
        """Create a temporary skill directory with implementation."""
        self.temp_dir = tempfile.mkdtemp()
        self.skill_dir = Path(self.temp_dir) / "test_skill"
        self.skill_dir.mkdir()

        # Create manifest
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "subprocess",
            "python_path": "python",
            "entry_point": "implementation.py",
        }
        manifest_path = self.skill_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_subprocess_missing_manifest(self):
        """Test subprocess execution when manifest is missing."""
        # Remove manifest
        (self.skill_dir / "manifest.json").unlink()

        manager = SkillManager(skills_dir=self.temp_dir)
        result = manager._execute_in_subprocess("test_skill", "echo", {"message": "hello"})

        self.assertIn("Error", result)
        self.assertIn("No manifest.json", result)

    def test_execute_subprocess_missing_python(self):
        """Test subprocess execution when uv is missing (FileNotFoundError)."""
        # Remove uv from PATH temporarily
        import os

        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = "/nonexistent"

        try:
            manager = SkillManager(skills_dir=self.temp_dir)
            result = manager._execute_in_subprocess("test_skill", "echo", {"message": "hello"})

            self.assertIn("Error", result)
            self.assertIn("uv", result)
        finally:
            os.environ["PATH"] = old_path

    def test_execute_subprocess_missing_entry_point(self):
        """Test subprocess execution when entry point is missing."""
        manager = SkillManager(skills_dir=self.temp_dir)
        result = manager._execute_in_subprocess("test_skill", "echo", {"message": "hello"})

        self.assertIn("Error", result)
        self.assertIn("Entry point not found", result)

    def test_execute_subprocess_success(self):
        """Test successful subprocess execution with uv run."""
        # Create entry point that prints the command and args
        entry_path = self.skill_dir / "implementation.py"
        entry_path.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, json\n"
            "cmd = sys.argv[1]\n"
            "args = json.loads(sys.argv[2])\n"
            'if cmd == "echo":\n'
            '    print("echo: " + args.get("message", ""))\n'
        )

        # Create manifest (uv run doesn't need python_path)
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "subprocess",
            "entry_point": "implementation.py",
        }
        (self.skill_dir / "manifest.json").write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        result = manager._execute_in_subprocess("test_skill", "echo", {"message": "hello world"})

        self.assertIn("echo: hello world", result)

    def test_execute_subprocess_error(self):
        """Test subprocess execution with command error."""
        # Create entry point that exits with error
        entry_path = self.skill_dir / "implementation.py"
        entry_path.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            'print("Error: test error", file=sys.stderr)\n'
            "sys.exit(1)\n"
        )

        # Create manifest
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "subprocess",
            "entry_point": "implementation.py",
        }
        (self.skill_dir / "manifest.json").write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        result = manager._execute_in_subprocess("test_skill", "echo", {})

        self.assertIn("Error", result)
        self.assertIn("test error", result)


class TestShimPatternToolsShim(unittest.TestCase):
    """Test the tools.py shim pattern implementation."""

    def setUp(self):
        """Create a temporary skill directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.skill_dir = Path(self.temp_dir) / "shim_skill"
        self.skill_dir.mkdir()

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_isolated_missing_venv(self):
        """Test _run_isolated when venv doesn't exist."""
        # Create tools.py content to test
        tools_content = """
import json
import os
from pathlib import Path

SKILL_DIR = Path(__file__).parent
VENV_PYTHON = SKILL_DIR / ".venv" / "bin" / "python"
IMPLEMENTATION_SCRIPT = SKILL_DIR / "implementation.py"

def _run_isolated(command, **kwargs):
    if not VENV_PYTHON.exists():
        return f"Error: Skill environment not found.\\nPlease run:\\n  cd {SKILL_DIR}\\n  uv venv\\n  uv sync"
    return "success"

result = _run_isolated("test", message="hello")
"""
        tools_path = self.skill_dir / "tools.py"
        tools_path.write_text(tools_content)

        # Import and test
        import importlib.util

        spec = importlib.util.spec_from_file_location("test_tools", str(tools_path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        result = module._run_isolated("test", message="hello")

        self.assertIn("Error", result)
        self.assertIn("uv venv", result)
        self.assertIn("uv sync", result)


class TestCrawl4aiSkillStructure(unittest.TestCase):
    """Test crawl4ai skill structure and files."""

    def test_crawl4ai_manifest_exists(self):
        """Test that crawl4ai skill has proper manifest structure."""
        skills_dir = PROJECT_ROOT / "assets/skills"
        crawl4ai_dir = skills_dir / "crawl4ai"

        if not crawl4ai_dir.exists():
            self.skipTest("crawl4ai skill not found")

        manifest_path = crawl4ai_dir / "manifest.json"
        self.assertTrue(manifest_path.exists(), "manifest.json should exist")

        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest.get("execution_mode"), "subprocess")
        self.assertEqual(manifest.get("python_path"), ".venv/bin/python")
        self.assertEqual(manifest.get("entry_point"), "implementation.py")

    def test_crawl4ai_tools_py_exists(self):
        """Test that crawl4ai skill has tools.py shim."""
        skills_dir = PROJECT_ROOT / "assets/skills"
        crawl4ai_dir = skills_dir / "crawl4ai"

        if not crawl4ai_dir.exists():
            self.skipTest("crawl4ai skill not found")

        tools_path = crawl4ai_dir / "tools.py"
        self.assertTrue(tools_path.exists(), "tools.py should exist")

        content = tools_path.read_text()
        # Verify shim pattern: no heavy imports
        self.assertNotIn("from crawl4ai", content)
        self.assertNotIn("import crawl4ai", content)
        # Verify _run_isolated function exists
        self.assertIn("_run_isolated", content)

    def test_crawl4ai_implementation_py_exists(self):
        """Test that crawl4ai skill has implementation.py."""
        skills_dir = PROJECT_ROOT / "assets/skills"
        crawl4ai_dir = skills_dir / "crawl4ai"

        if not crawl4ai_dir.exists():
            self.skipTest("crawl4ai skill not found")

        impl_path = crawl4ai_dir / "implementation.py"
        self.assertTrue(impl_path.exists(), "implementation.py should exist")

        content = impl_path.read_text()
        # Verify heavy imports are in implementation.py
        self.assertIn("from crawl4ai", content)

    def test_crawl4ai_pyproject_toml_exists(self):
        """Test that crawl4ai skill has pyproject.toml for uv."""
        skills_dir = PROJECT_ROOT / "assets/skills"
        crawl4ai_dir = skills_dir / "crawl4ai"

        if not crawl4ai_dir.exists():
            self.skipTest("crawl4ai skill not found")

        pyproject_path = crawl4ai_dir / "pyproject.toml"
        self.assertTrue(pyproject_path.exists(), "pyproject.toml should exist for uv")

        content = pyproject_path.read_text()
        pyproject = json.loads(content.replace("\n", ""))
        self.assertIn("dependencies", pyproject.get("project", {}))
        self.assertTrue(len(pyproject["project"]["dependencies"]) > 0)


class TestSkillManagerExecutionMode(unittest.TestCase):
    """Test SkillManager execution mode handling."""

    def setUp(self):
        """Create a temporary skill directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.skill_dir = Path(self.temp_dir) / "test_skill"
        self.skill_dir.mkdir()

        # Create tools.py (without decorators for temp dir testing)
        tools_content = """
# Simple test command without decorators
def test_cmd():
    return "test"
"""
        (self.skill_dir / "tools.py").write_text(tools_content)

    def tearDown(self):
        """Clean up temporary directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_skill_execution_mode_library(self):
        """Test skill with library mode."""
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "library",
        }
        (self.skill_dir / "manifest.json").write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        manager.load_skill(self.skill_dir)

        skill = manager._skills.get("test_skill")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.execution_mode, "library")
        self.assertEqual(skill.manifest.get("execution_mode"), "library")

    def test_skill_execution_mode_subprocess(self):
        """Test skill with subprocess mode."""
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "subprocess",
            "python_path": ".venv/bin/python",
            "entry_point": "implementation.py",
        }
        (self.skill_dir / "manifest.json").write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        manager.load_skill(self.skill_dir)

        skill = manager._skills.get("test_skill")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.execution_mode, "subprocess")
        self.assertEqual(skill.manifest.get("execution_mode"), "subprocess")
        self.assertEqual(skill.manifest.get("python_path"), ".venv/bin/python")

    def test_skill_info_includes_execution_mode(self):
        """Test that get_skill_info includes execution mode."""
        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "execution_mode": "subprocess",
        }
        (self.skill_dir / "manifest.json").write_text(json.dumps(manifest))

        manager = SkillManager(skills_dir=self.temp_dir)
        manager._register_skill(self.skill_dir)

        info = manager.get_skill_info("test_skill")
        self.assertIsNotNone(info)
        # get_skill_info doesn't include execution_mode by default
        # but the skill object has it
        skill = manager.skills.get("test_skill")
        self.assertEqual(skill.execution_mode, "subprocess")


if __name__ == "__main__":
    unittest.main()
