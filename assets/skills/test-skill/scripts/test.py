"""
test-skill/scripts/test.py - Test Skill Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

from agent.skills.decorators import skill_script


@skill_script(
    name="example",
    category="read",
    description="An example command for the template skill.",
)
def example(param: str = "default") -> str:
    """
    An example command for the template skill.
    """
    from agent.skills._template.scripts import example as example_mod

    return example_mod.example_command(param)


@skill_script(
    name="example_with_options",
    category="read",
    description="Example command with optional parameters.",
)
def example_with_options(enabled: bool = True, value: int = 42) -> dict:
    """
    Example command with optional parameters.
    """
    from agent.skills._template.scripts import example as example_mod

    return example_mod.example_with_options(enabled=enabled, value=value)


@skill_script(
    name="process_data",
    category="write",
    description="Process a list of data strings.",
)
def process_data(data: list[str], filter_empty: bool = True) -> dict:
    """
    Process a list of data strings.
    """
    from agent.skills._template.scripts import example as example_mod

    result = example_mod.process_data(data, filter_empty=filter_empty)
    return {
        "processed": result,
        "count": len(result),
        "original_count": len(data),
    }
