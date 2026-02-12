"""Public API surface tests for omni.core.skills.discovery."""

from __future__ import annotations

import inspect

from omni.core.skills.discovery import SkillDiscoveryService, generate_usage_template


def test_discover_all_has_no_compat_locations_parameter() -> None:
    sig = inspect.signature(SkillDiscoveryService.discover_all)
    params = list(sig.parameters.keys())
    assert params == ["self"]


def test_generate_usage_template_accepts_only_tool_name_and_input_schema() -> None:
    sig = inspect.signature(generate_usage_template)
    params = list(sig.parameters.keys())
    assert params == ["tool_name", "input_schema"]
