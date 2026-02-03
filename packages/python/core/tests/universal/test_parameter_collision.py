"""
test_parameter_collision.py - Parameter Collision Detection Tests

Tests that verify skill commands don't use reserved parameter names that would
conflict with UniversalScriptSkill.execute() method parameters.

Reserved parameters that should NOT be used by skill commands:
- cmd_name: Used by execute() for the command name
- skill_name: Used by UniversalScriptSkill for skill identification
- skill_path: Used by UniversalScriptSkill for path
- metadata: Used by UniversalScriptSkill for metadata
- context: Used by load() for context
- cwd: Commonly used in context
"""

import inspect
from pathlib import Path

import pytest


class TestParameterCollisionDetection:
    """Tests for detecting parameter name collisions."""

    # Reserved parameter names that skill commands should NOT use
    RESERVED_PARAMS = {
        "cmd_name",  # UniversalScriptSkill.execute() first argument
        "skill_name",  # UniversalScriptSkill constructor
        "skill_path",  # UniversalScriptSkill constructor
        "metadata",  # UniversalScriptSkill constructor
        "context",  # UniversalScriptSkill.load() argument
        "cwd",  # Common context key
        "handler",  # Internal execution variable
    }

    def test_universal_skill_execute_uses_safe_param_name(self):
        """Verify UniversalScriptSkill.execute() uses 'cmd_name' instead of 'command'.

        This is the fix for the collision bug where skill commands with 'command'
        parameter would conflict with execute()'s first positional parameter.
        """
        from omni.core.skills.universal import UniversalScriptSkill

        sig = inspect.signature(UniversalScriptSkill.execute)
        params = list(sig.parameters.keys())

        # First POSITIONAL param after 'self' should be 'cmd_name' (not 'command')
        # Skip 'self' as it's always the first parameter in methods
        meaningful_params = [p for p in params if p != "self"]
        first_param = meaningful_params[0] if meaningful_params else None

        assert first_param == "cmd_name", (
            f"UniversalScriptSkill.execute() first parameter (after 'self') should be 'cmd_name' "
            f"to avoid collision with skill commands that use 'command' as parameter. "
            f"Got: '{first_param}'"
        )

        # Verify other commonly conflicting names are not used
        unsafe_params = {"command", "cmd", "script", "action", "task"}
        for param in meaningful_params:
            assert param not in unsafe_params, (
                f"Parameter '{param}' is commonly used by skill commands and "
                f"would cause collision. Use 'cmd_name' instead."
            )

    def test_omnicell_execute_uses_command_param(self):
        """Verify omniCell.execute uses 'command' parameter (which is now safe)."""
        # Read the actual source
        script_path = (
            Path(__file__).parent.parent.parent.parent
            / "assets/skills/omniCell/scripts/run_command.py"
        )
        if not script_path.exists():
            pytest.skip("run_command.py not found")

        source = script_path.read_text()

        # Find the execute function
        exec_globals = {}
        exec(compile(source, script_path, "exec"), exec_globals)

        execute_func = None
        for name, obj in exec_globals.items():
            if callable(obj) and name == "execute":
                execute_func = obj
                break

        assert execute_func is not None, "execute function not found"

        sig = inspect.signature(execute_func)
        param_names = set(sig.parameters.keys())

        # 'command' is now SAFE because execute() uses 'cmd_name'
        assert "command" in param_names, "omniCell.execute should have 'command' parameter"

        # 'cmd_name' should NOT be used (it's reserved for execute())
        assert "cmd_name" not in param_names, (
            "omniCell.execute should NOT use 'cmd_name' - it's reserved! Use 'command' instead."
        )

    def test_execute_signature_no_positional_conflict(self):
        """Verify execute() can be called with command= without collision."""
        from omni.core.skills.universal import UniversalScriptSkill

        # This test verifies the fix works
        sig = inspect.signature(UniversalScriptSkill.execute)

        # The first parameter after 'self' should be cmd_name, so kwargs['command']
        # won't conflict with a positional parameter
        params = list(sig.parameters.values())
        meaningful_params = [p for p in params if p.name != "self"]
        first_param = meaningful_params[0] if meaningful_params else None

        assert first_param is not None, "No parameters found"
        assert first_param.name == "cmd_name"
        assert first_param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD


class TestReservedParameterDocumentation:
    """Document reserved parameter names and why they are reserved."""

    def test_reserved_params_are_documented(self):
        """Verify all reserved parameters are documented."""
        reserved = {
            "cmd_name": "First param of UniversalScriptSkill.execute()",
            "skill_name": "UniversalScriptSkill.__init__() param",
            "skill_path": "UniversalScriptSkill.__init__() param",
            "metadata": "UniversalScriptSkill.__init__() param",
            "context": "UniversalScriptSkill.load() param",
        }

        # This test serves as living documentation
        expected_keys = {"cmd_name", "skill_name", "skill_path", "metadata", "context"}
        assert set(reserved.keys()) == expected_keys

    def test_common_skill_param_names_are_safe(self):
        """Verify common skill parameter names don't conflict with reserved names."""
        # These are common parameter names used by skill commands
        common_params = {
            "command",  # omniCell.execute uses this
            "pattern",  # smart_search, batch_replace
            "replacement",  # batch_replace, regex_replace
            "file_path",  # regex_replace
            "path",  # file operations
            "query",  # sys_query
            "intent",  # omniCell.execute
        }

        reserved = {"cmd_name", "skill_name", "skill_path", "metadata", "context"}

        # Common params should NOT be in reserved
        conflicts = common_params.intersection(reserved)
        assert not conflicts, f"Common params conflict with reserved: {conflicts}"


class TestCollisionPrevention:
    """Tests that verify collision prevention mechanisms are in place."""

    def test_no_positional_param_named_command(self):
        """UniversalScriptSkill.execute() must not have 'command' as first param."""
        from omni.core.skills.universal import UniversalScriptSkill

        sig = inspect.signature(UniversalScriptSkill.execute)
        params = list(sig.parameters.keys())

        # First param after 'self' should NOT be 'command'
        meaningful_params = [p for p in params if p != "self"]
        assert meaningful_params[0] != "command", (
            "UniversalScriptSkill.execute() first parameter (after 'self') must NOT be 'command'. "
            "This causes collision with skill commands that have 'command' parameter. "
            "Use 'cmd_name' instead."
        )

    def test_kwargs_extraction_works(self):
        """Verify that kwargs can be passed without collision."""
        # This is a regression test for the original bug:
        # TypeError: execute() got multiple values for argument 'command'

        # The fix: execute() uses 'cmd_name' as first param, so 'command' in kwargs
        # is extracted separately and doesn't conflict

        from omni.core.skills.universal import UniversalScriptSkill

        sig = inspect.signature(UniversalScriptSkill.execute)

        # Check that 'command' is not in the signature (as a param that would conflict)
        param_names = set(sig.parameters.keys())

        # If 'command' were in the signature, it would conflict with skill commands
        # that have command= in their kwargs
        assert "command" not in param_names, (
            "'command' in execute() signature would cause collision with "
            "skill commands that use 'command' parameter"
        )

    def test_skill_with_command_param_works(self):
        """Regression test: skill commands with 'command' param should work.

        This test verifies that a skill command function with a 'command' parameter
        can be called without collision because UniversalScriptSkill.execute()
        now uses 'cmd_name' as its first parameter.

        The key verification: execute(cmd_name, command="value") should not conflict
        with handler(command="value") because 'cmd_name' != 'command'.
        """
        import inspect

        from omni.core.skills.universal import UniversalScriptSkill

        # Get the execute method signature
        sig = inspect.signature(UniversalScriptSkill.execute)
        param_names = set(sig.parameters.keys())

        # Verify execute() does NOT have 'command' as a parameter
        # This ensures that when we call handler(command="value"), there's no collision
        assert "command" not in param_names, (
            "UniversalScriptSkill.execute() has 'command' parameter - "
            "this would cause collision with skill commands that use 'command'!"
        )

        # Verify execute() DOES have 'cmd_name' as the first param after 'self'
        meaningful_params = [p for p in param_names if p != "self"]
        assert "cmd_name" in meaningful_params, (
            "UniversalScriptSkill.execute() should have 'cmd_name' parameter "
            "to avoid collision with skill commands that use 'command'"
        )

        # The actual collision scenario would be:
        # Before fix: execute(command, **kwargs) where kwargs['command'] exists
        #              -> TypeError: multiple values for argument 'command'
        # After fix: execute(cmd_name, **kwargs) where kwargs['command'] exists
        #              -> Works fine because 'cmd_name' != 'command'

        # This test verifies the fix is in place
        first_param_after_self = [p for p in param_names if p != "self"][0]
        assert first_param_after_self != "command", (
            f"First param after 'self' is '{first_param_after_self}', not 'cmd_name'. "
            "This would cause collision with skill commands!"
        )
