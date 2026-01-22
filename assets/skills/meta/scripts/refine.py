"""
Meta Skill: Refiner Logic
Uses the injected InferenceClient to fix broken code.
"""

from pathlib import Path

from omni.core.skills.script_loader import skill_command


@skill_command(
    name="refine_code",
    category="evolution",
    description="""
    Analyzes test failure and generates fixed code using AI.

    Uses the `refiner.md` prompt from skills/meta/prompts/ to guide the LLM
    in understanding the requirement and fixing the broken implementation.

    Args:
        inference_client: The injected AI inference client.
        project_root: Root directory of the project.
        requirement: The original requirement for the code.
        code: The current implementation that failed.
        error: The error message from test execution.

    Returns:
        Fixed Python code with markdown fences stripped.

    Example:
        @omni("meta.refine_code", {"requirement": "Add two numbers", "code": "def add(a, b):\\n    return a + b", "error": "NameError: name 'a' not defined"})
    """,
    inject_root=True,
)
async def refine_code(
    inference_client,
    project_root: str,
    requirement: str,
    code: str,
    error: str,
) -> str:
    prompt_path = Path(project_root) / "assets/skills/meta/prompts/refiner.md"
    if not prompt_path.exists():
        return f"# Error: Refiner prompt not found at {prompt_path}"

    system_prompt = prompt_path.read_text(encoding="utf-8")

    user_content = f"""--- REQUIREMENT ---
{requirement}

--- BROKEN CODE ---
{code}

--- ERROR OUTPUT ---
{error}

Please provide the FIXED code now:
"""

    try:
        result = await inference_client.complete(
            system_prompt=system_prompt,
            user_query=user_content,
            temperature=0.1,
        )

        if not result.get("success"):
            return f"# Critical Error during refinement: {result.get('error', 'Unknown error')}"

        raw_content = result["content"]

        return _clean_code_block(raw_content)

    except Exception as e:
        return f"# Critical Error during refinement: {e}"


def _clean_code_block(content: str) -> str:
    """Helper to strip markdown fences if present."""
    content = content.strip()

    if content.startswith("```python"):
        content = content[9:]
    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    return content.strip()
