"""Public API surface tests for omni.core.skills registry exports."""

from __future__ import annotations


def test_registry_module_exposes_only_runtime_registry_surface() -> None:
    import omni.core.skills.registry as registry

    assert hasattr(registry, "SkillRegistry")
    assert hasattr(registry, "get_skill_registry")
    assert not hasattr(registry, "install_remote_skill")
    assert not hasattr(registry, "update_remote_skill")
    assert not hasattr(registry, "jit_install_skill")
    assert not hasattr(registry, "discover_skills")
    assert not hasattr(registry, "suggest_skills_for_task")


def test_core_skills_module_does_not_reexport_removed_remote_helpers() -> None:
    import omni.core.skills as skills

    assert not hasattr(skills, "install_remote_skill")
    assert not hasattr(skills, "update_remote_skill")
    assert not hasattr(skills, "jit_install_skill")
    assert not hasattr(skills, "discover_skills")
