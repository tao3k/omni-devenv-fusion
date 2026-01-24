"""
Knowledge Skill Tests - Trinity Architecture v2.0

Tests for knowledge skill commands using direct script imports.
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
SKILLS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SKILLS_ROOT))


class TestKnowledgeScripts:
    """Test knowledge skill scripts can be imported."""

    def test_context_script_imports(self):
        """Test context module imports successfully."""
        from knowledge.scripts import context

        assert hasattr(context, "get_development_context")

    def test_consult_architecture_doc(self):
        """Test consult_architecture_doc function exists."""
        from knowledge.scripts import context

        assert callable(getattr(context, "consult_architecture_doc", None))

    def test_consult_language_expert(self):
        """Test consult_language_expert function exists."""
        from knowledge.scripts import context

        assert callable(getattr(context, "consult_language_expert", None))


class TestKnowledgeCommands:
    """Test knowledge skill commands work correctly."""

    def test_get_development_context_is_callable(self):
        """Test that get_development_context is a callable function."""
        from knowledge.scripts import context

        assert callable(context.get_development_context)

    def test_consult_architecture_doc_signature(self):
        """Test that consult_architecture_doc accepts a topic parameter."""
        import inspect

        from knowledge.scripts import context

        sig = inspect.signature(context.consult_architecture_doc)
        assert "topic" in sig.parameters

    def test_consult_language_expert_signature(self):
        """Test that consult_language_expert accepts correct parameters."""
        import inspect

        from knowledge.scripts import context

        sig = inspect.signature(context.consult_language_expert)
        params = list(sig.parameters.keys())
        assert "file_path" in params
        assert "task_description" in params
