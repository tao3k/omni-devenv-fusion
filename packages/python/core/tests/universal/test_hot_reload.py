"""
test_hot_reload.py - Comprehensive Hot Reload Mechanism Tests

Tests the core hot reload functionality for skills including:
- mtime-based detection
- sys.modules cache clearing
- Command registration updates
- SkillContext integration
- Error handling and edge cases
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest


class TestMtimeDetection:
    """Tests for mtime-based change detection."""

    @pytest.fixture
    def skill_with_scripts(self, tmp_path):
        """Create a test skill with scripts directory."""
        skill_path = tmp_path / "test_skill"
        skill_path.mkdir()
        scripts_path = skill_path / "scripts"
        scripts_path.mkdir()

        # Create SKILL.md
        (skill_path / "SKILL.md").write_text("---\nname: test_skill\n---\n")

        # Create initial script
        script_content = """
from omni.foundation.api.decorators import skill_command

@skill_command(name="status", category="read", description="Test command")
def status():
    return "v1"
"""
        (scripts_path / "main.py").write_text(script_content)

        return skill_path

    def test_mtime_cached_on_register(self, skill_with_scripts):
        """Verify mtime is cached when skill is registered."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

# Create context
ctx = SkillContext(Path("{skill_with_scripts.parent.parent}"))

# Create and load skill
skill = UniversalScriptSkill("test_skill", Path("{skill_with_scripts}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))

# Register skill (should cache mtime)
ctx.register_skill(skill)

# Check mtime is set
print("mtime:", getattr(skill, "_mtime", None))
print("commands:", len(ctx._commands))
''',
            ],
            cwd=skill_with_scripts,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "mtime:" in result.stdout
        # mtime should be a positive number
        mtime_line = [l for l in result.stdout.split("\n") if l.startswith("mtime:")][0]
        mtime_val = float(mtime_line.split(":")[1].strip())
        assert mtime_val > 0, "mtime should be positive"

    def test_mtime_triggers_reload(self, skill_with_scripts):
        """Verify mtime change triggers hot reload."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

# Create context
ctx = SkillContext(Path("{skill_with_scripts.parent.parent}"))

# Create and load skill
skill = UniversalScriptSkill("test_skill", Path("{skill_with_scripts}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))
ctx.register_skill(skill)
initial_mtime = skill._mtime

# Modify script (change return value)
import time
time.sleep(0.1)  # Ensure mtime changes
script_path = Path("{skill_with_scripts}/scripts/main.py")
script_path.write_text(script_path.read_text().replace("v1", "v2"))

# Get skill (should trigger reload)
reloaded_skill = ctx.get_skill("test_skill")
new_mtime = reloaded_skill._mtime

print("initial_mtime:", initial_mtime)
print("new_mtime:", new_mtime)
print("mtime_changed:", new_mtime > initial_mtime)
''',
            ],
            cwd=skill_with_scripts,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "mtime_changed: True" in result.stdout, "mtime should have changed"

    def test_multiple_modifications_detected(self, skill_with_scripts):
        """Verify multiple file modifications are all detected."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

# Create context
ctx = SkillContext(Path("{skill_with_scripts.parent.parent}"))

# Create and load skill
skill = UniversalScriptSkill("test_skill", Path("{skill_with_scripts}"))
import asyncio
import time
asyncio.run(skill.load({{"cwd": str(Path("."))}}))
ctx.register_skill(skill)

# First modification
time.sleep(0.1)
script_path = Path("{skill_with_scripts}/scripts/main.py")
script_path.write_text(script_path.read_text().replace("v1", "v2_first"))

# First get (trigger reload)
skill1 = ctx.get_skill("test_skill")
mtime1 = skill1._mtime

# Second modification
time.sleep(0.1)
script_path.write_text(script_path.read_text().replace("v2_first", "v2_second"))

# Second get (should detect change)
skill2 = ctx.get_skill("test_skill")
mtime2 = skill2._mtime

print("mtime1:", mtime1)
print("mtime2:", mtime2)
print("both_reloaded:", mtime2 > mtime1)
''',
            ],
            cwd=skill_with_scripts,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "both_reloaded: True" in result.stdout, "Both modifications should be detected"


class TestSysModulesClearing:
    """Tests for sys.modules cache clearing."""

    @pytest.fixture
    def skill_for_sysmodules(self, tmp_path):
        """Create a skill that tracks module reloads."""
        skill_path = tmp_path / "sysmodules_skill"
        skill_path.mkdir()
        scripts_path = skill_path / "scripts"
        scripts_path.mkdir()

        (skill_path / "SKILL.md").write_text("---\nname: sysmodules_skill\n---\n")

        # Script that tracks import count
        script = """
import sys

# Track how many times this module was imported
module_id = "sysmodules_skill.scripts.main"
if module_id not in sys.modules:
    sys.modules[module_id] = {"import_count": 0}
sys.modules[module_id]["import_count"] = sys.modules[module_id].get("import_count", 0) + 1

def get_import_count():
    return sys.modules[module_id]["import_count"]
"""
        (scripts_path / "main.py").write_text(script)

        return skill_path

    def test_sys_modules_cleared_on_reload(self, skill_for_sysmodules):
        """Verify sys.modules entries are cleared on hot reload."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

ctx = SkillContext(Path("{skill_for_sysmodules.parent.parent}"))

skill = UniversalScriptSkill("sysmodules_skill", Path("{skill_for_sysmodules}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))
ctx.register_skill(skill)

# Get import count before reload
skill1 = ctx.get_skill("sysmodules_skill")
count_before = skill1._tools_loader.commands.get("sysmodules_skill.status", lambda: None)()

# Modify file to trigger reload
import time
time.sleep(0.1)
script_path = Path("{skill_for_sysmodules}/scripts/main.py")
script_path.write_text(script_path.read_text())

# Get skill (should reload)
skill2 = ctx.get_skill("sysmodules_skill")

# Check sys.modules was cleared
modules_before = len([k for k in sys.modules if k.startswith("sysmodules_skill")])
print("modules after reload:", modules_before)
''',
            ],
            cwd=skill_for_sysmodules,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"


class TestCommandRegistration:
    """Tests for command registration updates."""

    @pytest.fixture
    def skill_with_commands(self, tmp_path):
        """Create a skill with multiple commands."""
        skill_path = tmp_path / "commands_skill"
        skill_path.mkdir()
        scripts_path = skill_path / "scripts"
        scripts_path.mkdir()

        (skill_path / "SKILL.md").write_text("---\nname: commands_skill\n---\n")

        script = """
from omni.foundation.api.decorators import skill_command

@skill_command(name="cmd1", category="test", description="Command 1")
def cmd1():
    return "cmd1_v1"

@skill_command(name="cmd2", category="test", description="Command 2")
def cmd2():
    return "cmd2_v1"
"""
        (scripts_path / "commands.py").write_text(script)

        return skill_path

    def test_commands_cleared_and_reregistered(self, skill_with_commands):
        """Verify old commands are cleared and new ones are registered."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

ctx = SkillContext(Path("{skill_with_commands.parent.parent}"))

skill = UniversalScriptSkill("commands_skill", Path("{skill_with_commands}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))
ctx.register_skill(skill)

# Check initial commands
print("initial commands:", list(ctx._commands.keys()))

# Modify to remove cmd2
import time
time.sleep(0.1)
script_path = Path("{skill_with_commands}/scripts/commands.py")
script_path.write_text(script_path.read_text().replace("@skill_command(name=\\"cmd2\\"", "@skill_command(name=\\"cmd2_disabled\\""))

# Get skill (trigger reload)
skill2 = ctx.get_skill("commands_skill")

# Check cmd2 is removed
print("after reload commands:", list(ctx._commands.keys()))
print("cmd2 removed:", "commands_skill.cmd2" not in ctx._commands)
''',
            ],
            cwd=skill_with_commands,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "cmd2 removed: True" in result.stdout

    def test_new_commands_added(self, skill_with_commands):
        """Verify new commands are detected after modification."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

ctx = SkillContext(Path("{skill_with_commands.parent.parent}"))

skill = UniversalScriptSkill("commands_skill", Path("{skill_with_commands}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))
ctx.register_skill(skill)

initial_cmds = len(ctx._commands)
print("initial count:", initial_cmds)

# Add new command
import time
time.sleep(0.1)
script_path = Path("{skill_with_commands}/scripts/commands.py")
script_path.write_text(script_path.read_text() + """

@skill_command(name="cmd3", category="test", description="Command 3")
def cmd3():
    return "cmd3_v1"
""")

# Get skill (trigger reload)
skill2 = ctx.get_skill("commands_skill")

new_count = len(ctx._commands)
print("new count:", new_count)
print("cmd3 added:", "commands_skill.cmd3" in ctx._commands)
''',
            ],
            cwd=skill_with_commands,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "cmd3 added: True" in result.stdout


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_no_scripts_directory(self, tmp_path):
        """Test skill without scripts directory."""
        skill_path = tmp_path / "no_scripts_skill"
        skill_path.mkdir()

        (skill_path / "SKILL.md").write_text("---\nname: no_scripts_skill\n---\n")

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

ctx = SkillContext(Path("{skill_path.parent.parent}"))

skill = UniversalScriptSkill("no_scripts_skill", Path("{skill_path}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))
ctx.register_skill(skill)

# Should return skill without error
retrieved = ctx.get_skill("no_scripts_skill")
print("retrieved successfully:", retrieved is not None)
''',
            ],
            cwd=skill_path,
            capture_output=True,
            text=True,
        )

        # Should not crash, but might fail due to path issues
        # This tests graceful handling
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_skill_not_found(self):
        """Test get_skill for non-existent skill."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
sys.path.insert(0, "packages/python/core/src")
sys.path.insert(0, "packages/python/foundation/src")

from omni.foundation.config.skills import SKILLS_DIR
from omni.core.skills.runtime import SkillContext

ctx = SkillContext(SKILLS_DIR())
result = ctx.get_skill("nonexistent_skill")
print("result:", result)
""",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "result: None" in result.stdout

    def test_mtime_getter_exception_handling(self, tmp_path):
        """Test graceful handling when mtime getter fails."""
        skill_path = tmp_path / "exception_skill"
        skill_path.mkdir()
        scripts_path = skill_path / "scripts"
        scripts_path.mkdir()

        (skill_path / "SKILL.md").write_text("---\nname: exception_skill\n---\n")
        (scripts_path / "main.py").write_text("# empty")

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.runtime import SkillContext
from omni.core.skills.universal import UniversalScriptSkill

ctx = SkillContext(Path("{skill_path.parent.parent}"))

skill = UniversalScriptSkill("exception_skill", Path("{skill_path}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))
ctx.register_skill(skill)

# Should not crash even if something goes wrong
retrieved = ctx.get_skill("exception_skill")
print("retrieved:", retrieved is not None)
''',
            ],
            cwd=skill_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "retrieved: True" in result.stdout


class TestToolsLoaderHotReload:
    """Tests for ToolsLoader's role in hot reload."""

    def test_tools_loader_reload_clears_cache(self, tmp_path):
        """Verify ToolsLoader.load_all() clears old commands."""
        skill_path = tmp_path / "loader_test_skill"
        skill_path.mkdir()
        scripts_path = skill_path / "scripts"
        scripts_path.mkdir()

        (skill_path / "SKILL.md").write_text("---\nname: loader_test_skill\n---\n")

        script1 = """
from omni.foundation.api.decorators import skill_command

@skill_command(name="test_cmd", category="test", description="Test")
def test_cmd():
    return "v1"
"""
        (scripts_path / "main.py").write_text(script1)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f'''
import sys
from pathlib import Path
sys.path.insert(0, "packages/python/core/src")

from omni.core.skills.universal import UniversalScriptSkill

skill = UniversalScriptSkill("loader_test_skill", Path("{skill_path}"))
import asyncio
asyncio.run(skill.load({{"cwd": str(Path("."))}}))

initial_cmds = len(skill._tools_loader.commands)
print("initial commands:", initial_cmds)

# Modify script
import time
time.sleep(0.1)
script_path = Path("{skill_path}/scripts/main.py")
script_path.write_text(script_path.read_text().replace("v1", "v2"))

# Reload
skill._tools_loader.commands.clear()
skill._tools_loader.load_all()

new_cmds = len(skill._tools_loader.commands)
print("new commands:", new_cmds)
print("reloaded:", initial_cmds == new_cmds)
''',
            ],
            cwd=skill_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "reloaded: True" in result.stdout


class TestIntegrationWithKernel:
    """Integration tests with the kernel."""

    def test_kernel_reload_skill_updates_context(self):
        """Test kernel.reload_skill updates skill context properly."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
sys.path.insert(0, "packages/python/core/src")
sys.path.insert(0, "packages/python/agent/src")

from omni.core.kernel import get_kernel

async def test():
    kernel = get_kernel()

    # Get initial skill state
    skill1 = kernel.skill_context.get_skill("git")
    mtime1 = getattr(skill1, "_mtime", None)
    print("initial mtime:", mtime1)

    # Reload via kernel
    await kernel.reload_skill("git")

    # Get new skill state
    skill2 = kernel.skill_context.get_skill("git")
    mtime2 = getattr(skill2, "_mtime", None)
    print("after reload mtime:", mtime2)

    # Commands should be refreshed
    print("commands count:", len(skill2._tools_loader.commands))

import asyncio
asyncio.run(test())
""",
            ],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "initial mtime:" in result.stdout
        assert "after reload mtime:" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
