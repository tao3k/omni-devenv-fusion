"""Omni Test Kit - Testing framework for Omni Dev Fusion.

A comprehensive testing framework providing fixtures, decorators, and utilities
for writing robust, maintainable tests across the Omni ecosystem.

Features:
    - Auto-loaded pytest fixtures (core, git, scanner, watchers)
    - Skill testing utilities (builder, tester, result)
    - Data-driven testing support
    - Testing layer markers (unit, integration, cloud, etc.)
    - Assertion helpers for common patterns

Usage:
    # Enable all fixtures in conftest.py
    pytest_plugins = ["omni.test_kit"]

    # Use fixtures directly in tests
    def test_something(project_root, skill_test_suite):
        ...

    # Use decorators
    @data_driven("test_cases.json")
    def test_skill(case):
        assert case.expected == case.input

    # Use assertion helpers
    from omni.test_kit.asserts import assert_response_ok, assert_has_error
"""

from __future__ import annotations

__version__ = "0.1.0"
