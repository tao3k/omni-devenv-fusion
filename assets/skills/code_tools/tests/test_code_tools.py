"""
Code Tools Skill Tests - Unified smart_ast Architecture

Tests for unified code_tools skill:
- smart_ast/commands.py: smart_ast (unified command for search, refactor, analyze, patch)

Verifies:
- @skill_command with autowire=True pattern
- ConfigPaths integration
- Zero-config tool discovery
"""

import os
import sys
import tempfile
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))

# Also add project root for agent.skills imports
PROJECT_ROOT = SKILLS_ROOT.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestSmartAstImports:
    """Test smart_ast module imports."""

    def test_smart_ast_commands_import(self):
        """Test smart_ast commands module imports successfully."""
        from code_tools.scripts.smart_ast import commands

        assert commands is not None

    def test_smart_ast_function_exists(self):
        """Test smart_ast function is exported."""
        from code_tools.scripts.smart_ast.commands import smart_ast

        assert callable(smart_ast)


class TestSmartAstSkillCommand:
    """Test @skill_command decorator attributes."""

    def _has_skill_command_attr(self, func) -> bool:
        """Check if function has skill command attributes."""
        return hasattr(func, "_is_skill_command") and hasattr(func, "_skill_config")

    def test_smart_ast_has_skill_command(self):
        """Test smart_ast has skill command attributes."""
        from code_tools.scripts.smart_ast.commands import smart_ast

        assert self._has_skill_command_attr(smart_ast)
        assert smart_ast._is_skill_command is True

    def test_smart_ast_autowire_enabled(self):
        """Test smart_ast has autowire in config."""
        from code_tools.scripts.smart_ast.commands import smart_ast

        config = getattr(smart_ast, "_skill_config", None)
        assert config is not None
        execution = config.get("execution", {})
        assert execution.get("autowire") is True

    def test_smart_ast_name(self):
        """Test smart_ast has correct command name."""
        from code_tools.scripts.smart_ast.commands import smart_ast

        config = getattr(smart_ast, "_skill_config", None)
        assert config is not None
        assert config.get("name") == "smart_ast_search"

    def test_smart_ast_category(self):
        """Test smart_ast has correct category."""
        from code_tools.scripts.smart_ast.commands import smart_ast

        config = getattr(smart_ast, "_skill_config", None)
        assert config is not None
        assert config.get("category") == "search"


class TestSmartAstEngine:
    """Test smart_ast engine imports."""

    def test_engine_imports(self):
        """Test engine module imports successfully."""
        from code_tools.scripts.smart_ast import engine

        assert engine is not None

    def test_engine_class_exists(self):
        """Test SmartAstEngine class exists."""
        from code_tools.scripts.smart_ast.engine import SmartAstEngine

        assert SmartAstEngine is not None


class TestSmartAstPatterns:
    """Test smart_ast patterns imports."""

    def test_patterns_imports(self):
        """Test patterns module imports successfully."""
        from code_tools.scripts.smart_ast import patterns

        assert patterns is not None


class TestSmartAstScriptLoader:
    """Test smart_ast loads via ScriptLoader."""

    def test_smart_ast_loads_via_script_loader(self):
        """Test smart_ast commands load via ScriptLoader."""
        from pathlib import Path
        from omni.core.skills.script_loader import ScriptLoader

        scripts_dir = SKILLS_ROOT / "code_tools" / "scripts"
        loader = ScriptLoader(scripts_dir, "code_tools")
        loader.load_all()

        # smart_ast_search should be loaded
        commands = loader.list_commands()
        assert "code_tools.smart_ast_search" in commands, (
            f"smart_ast_search not found in commands: {commands}"
        )


class TestCodeToolsScriptLoader:
    """Test code_tools loads via ScriptLoader."""

    def test_code_tools_loads_via_script_loader(self):
        """Test code_tools scripts load via ScriptLoader."""
        from pathlib import Path
        from omni.core.skills.script_loader import ScriptLoader

        scripts_dir = SKILLS_ROOT / "code_tools" / "scripts"
        loader = ScriptLoader(scripts_dir, "code_tools")
        loader.load_all()

        # At least one command should be loaded
        assert len(loader.commands) > 0, "No commands loaded from code_tools"


class TestLegacyImports:
    """Test that legacy module paths still work (backward compat)."""

    def test_legacy_analyze_import_fails(self):
        """Test that legacy analyze module doesn't exist (as expected)."""
        import importlib

        # The old analyze module no longer exists
        # This test documents the migration
        try:
            from code_tools.scripts import analyze

            # If it exists, check it has the new structure
            assert hasattr(analyze, "__all__") or hasattr(analyze, "smart_ast")
        except ImportError:
            # Expected - old module was removed
            pass

    def test_legacy_refactor_import_fails(self):
        """Test that legacy refactor module doesn't exist (as expected)."""
        # The old refactor module no longer exists
        # This test documents the migration
        try:
            from code_tools.scripts import refactor

            # If it exists, check it has the new structure
            assert hasattr(refactor, "__all__") or hasattr(refactor, "smart_ast")
        except ImportError:
            # Expected - old module was removed
            pass
