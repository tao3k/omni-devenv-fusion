"""
Meta Skill: Refiner Logic
Uses the injected InferenceClient to fix broken code.
"""

from pathlib import Path

from agent.skills.decorators import skill_script


@skill_script(
    description="Analyze test failure and generate fixed code",
    category="evolution",
    inject_root=True,  # To read the prompt file
)
async def refine_code(
    inference_client,
    project_root: str,
    requirement: str,
    code: str,
    error: str,
) -> str:
    """
    Refines code based on error output using the 'refiner.md' prompt.

    Args:
        inference_client: The injected AI inference client
        project_root: Root directory of the project
        requirement: The original requirement for the code
        code: The current implementation that failed
        error: The error message from test execution

    Returns:
        Fixed Python code
    """
    # 1. Load System Prompt
    prompt_path = Path(project_root) / "assets/skills/meta/prompts/refiner.md"
    if not prompt_path.exists():
        return f"# Error: Refiner prompt not found at {prompt_path}"

    system_prompt = prompt_path.read_text(encoding="utf-8")

    # 2. Build User Context
    user_content = f"""--- REQUIREMENT ---
{requirement}

--- BROKEN CODE ---
{code}

--- ERROR OUTPUT ---
{error}

Please provide the FIXED code now:
"""

    # 3. Call LLM using complete() API
    try:
        result = await inference_client.complete(
            system_prompt=system_prompt,
            user_query=user_content,
            temperature=0.1,  # Low temperature for deterministic fixes
        )

        if not result.get("success"):
            return f"# Critical Error during refinement: {result.get('error', 'Unknown error')}"

        raw_content = result["content"]

        # 4. Clean Output (Strip Markdown)
        return _clean_code_block(raw_content)

    except Exception as e:
        return f"# Critical Error during refinement: {e}"


def _clean_code_block(content: str) -> str:
    """Helper to strip markdown fences if present."""
    content = content.strip()

    # Strip ```python or ``` prefix
    if content.startswith("```python"):
        content = content[9:]
    elif content.startswith("```"):
        content = content[3:]

    # Strip ``` suffix
    if content.endswith("```"):
        content = content[:-3]

    return content.strip()
