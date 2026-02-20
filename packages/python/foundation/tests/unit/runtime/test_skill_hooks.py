"""Unit tests for skill execution lifecycle hooks."""

from __future__ import annotations

import pytest

from omni.foundation.skill_hooks import (
    register_after_skill_execute,
    register_before_skill_execute,
    run_after_skill_execute,
    run_before_skill_execute,
)


class TestSkillHooks:
    """Register and run before/after skill execute callbacks."""

    def test_run_before_after_with_no_callbacks_succeeds(self):
        """Running with no callbacks registered does nothing."""
        run_before_skill_execute()
        run_after_skill_execute()

    def test_run_before_executes_registered_callback(self):
        """run_before_skill_execute runs registered callbacks."""
        seen = []

        def cb1():
            seen.append(1)

        def cb2():
            seen.append(2)

        register_before_skill_execute(cb1)
        register_before_skill_execute(cb2)
        run_before_skill_execute()
        assert 1 in seen and 2 in seen

    def test_run_after_executes_registered_callback(self):
        """run_after_skill_execute runs registered callbacks."""
        seen = []

        def cb():
            seen.append("after")

        register_after_skill_execute(cb)
        run_after_skill_execute()
        assert "after" in seen

    def test_exception_in_callback_does_not_stop_others(self):
        """If one callback raises, others still run."""
        seen = []

        def bad():
            raise ValueError("expected")

        def good():
            seen.append("ok")

        register_before_skill_execute(bad)
        register_before_skill_execute(good)
        run_before_skill_execute()
        assert "ok" in seen
