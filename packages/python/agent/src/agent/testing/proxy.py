"""
Skill proxy classes for testing.

Provides wrappers for skill objects and command results.
"""

import asyncio


class _CommandResultWrapper:
    """
    Wrapper for command execution results.

    Handles:
    - ExecutionResult: from SkillCommand.execute() with output field
    - CommandResult: from @skill_command decorator with data field
    """

    def __init__(self, result):
        self._result = result

        # Handle ExecutionResult (from SkillCommand.execute)
        if hasattr(result, "output"):
            self.success = result.success
            self.output = result.output
            self.error = result.error
            self.metadata = {"duration_ms": getattr(result, "duration_ms", 0.0)}
            self.data = self.output  # Backward compatibility
        # Handle CommandResult (from @skill_command decorator)
        elif hasattr(result, "data"):
            self.success = result.success
            self.data = result.data
            self.error = result.error
            self.metadata = result.metadata
            self.output = str(self.data) if self.data else ""
        else:
            # Fallback for unknown result types
            self.success = True
            self.output = str(result)
            self.error = None
            self.metadata = {}
            self.data = self.output

    def __repr__(self):
        return f"CommandResult(success={self.success}, output={self.output!r})"

    def __str__(self):
        return self.output


class SkillProxy:
    """
    Proxy wrapper for skill objects that exposes commands as direct methods.

    This provides backward compatibility with tests that expect methods like
    git.status(), git.commit(), etc. directly on the skill fixture.
    """

    def __init__(self, skill):
        self._skill = skill
        self._name = skill.name
        self._manifest = skill.manifest
        self._commands = skill.commands

        # Expose all commands as direct methods
        for cmd_name, cmd in skill.commands.items():
            # Strip skill prefix for cleaner API: git_commit -> commit
            method_name = cmd_name
            if cmd_name.startswith(f"{skill.name}_"):
                method_name = cmd_name[len(skill.name) + 1 :]
            elif cmd_name.startswith(f"{skill.name}."):
                method_name = cmd_name[len(skill.name) + 1 :]

            # Create bound method that calls the command
            setattr(self, method_name, self._create_command_method(cmd))
            # Also keep the full name for compatibility
            if method_name != cmd_name:
                setattr(self, cmd_name, self._create_command_method(cmd))

    def _create_command_method(self, cmd):
        """Create a method that executes the command and returns a result wrapper."""

        async def _execute(**kwargs):
            result = await cmd.execute(kwargs)
            return _CommandResultWrapper(result)

        def _sync_execute(**kwargs):
            import asyncio

            return asyncio.run(_execute(**kwargs))

        # Return a callable that works with both sync and async contexts
        def _method_wrapper(**kwargs):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return _execute(**kwargs)
            except RuntimeError:
                pass
            return _sync_execute(**kwargs)

        return _method_wrapper

    def __repr__(self):
        return f"SkillProxy({self._name})"

    @property
    def name(self):
        return self._name

    @property
    def manifest(self):
        return self._manifest
