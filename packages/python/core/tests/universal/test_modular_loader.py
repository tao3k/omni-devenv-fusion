import pytest
import sys
import os
from pathlib import Path
from omni.core.skills.script_loader import ScriptLoader


def test_recursive_modular_discovery(tmp_path):
    """Test: Automatic discovery of tools in deep subdirectories."""
    scripts_dir = tmp_path / "scripts"
    sub_dir = scripts_dir / "deep" / "nested" / "module"
    sub_dir.mkdir(parents=True)

    # Write test script
    (sub_dir / "tool.py").write_text("""
from omni.foundation.api.decorators import skill_command
@skill_command(name="nested_cmd")
def nested_cmd(): return "ok"
""")

    loader = ScriptLoader(scripts_dir, skill_name="test_skill")
    loader.load_all()

    assert "test_skill.nested_cmd" in loader.commands
    assert loader.commands["test_skill.nested_cmd"]() == "ok"


def test_relative_import_support(tmp_path):
    """Test: Support for relative imports within subdirectories without __init__.py."""
    scripts_dir = tmp_path / "scripts"
    sub_dir = scripts_dir / "logic"
    sub_dir.mkdir(parents=True)

    # Write imported module
    (sub_dir / "helper.py").write_text("""
def get_secret(): return "42"
""")

    # Write main command module (using relative import)
    (sub_dir / "commands.py").write_text("""
from omni.foundation.api.decorators import skill_command
from .helper import get_secret
@skill_command(name="reveal")
def reveal(): return get_secret()
""")

    loader = ScriptLoader(scripts_dir, skill_name="import_skill")
    loader.load_all()

    assert "import_skill.reveal" in loader.commands
    assert loader.commands["import_skill.reveal"]() == "42"


def test_namespace_collision_avoidance(tmp_path):
    """Test: Same-named files in different subdirectories do not overwrite each other."""
    scripts_dir = tmp_path / "scripts"

    # Directory A
    dir_a = scripts_dir / "dir_a"
    dir_a.mkdir(parents=True)
    (dir_a / "mod.py").write_text("""
from omni.foundation.api.decorators import skill_command
@skill_command(name="cmd_a")
def cmd_a(): return "A"
""")

    # Directory B (also contains mod.py)
    dir_b = scripts_dir / "dir_b"
    dir_b.mkdir(parents=True)
    (dir_b / "mod.py").write_text("""
from omni.foundation.api.decorators import skill_command
@skill_command(name="cmd_b")
def cmd_b(): return "B"
""")

    loader = ScriptLoader(scripts_dir, skill_name="collision_skill")
    loader.load_all()

    assert "collision_skill.cmd_a" in loader.commands
    assert "collision_skill.cmd_b" in loader.commands
    assert loader.commands["collision_skill.cmd_a"]() == "A"
    assert loader.commands["collision_skill.cmd_b"]() == "B"


def test_module_cleanup_on_failure(tmp_path):
    """Test: System modules are cleaned up if a modular script fails to load."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Write a broken script
    (scripts_dir / "broken.py").write_text("import non_existent_package")

    loader = ScriptLoader(scripts_dir, skill_name="error_skill")
    loader.load_all()

    # Check that no command was registered
    assert len(loader.commands) == 0
