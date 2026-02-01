"""
prompts.py - LLM Prompts for Skill Evolution

Uses XML-tagged prompts for better LLM (Claude) comprehension.
Claude Cookbook best practice: XML > JSON for complex instruction following.
"""

from __future__ import annotations

import textwrap


# =============================================================================
# Harvester Prompts (XML-Enhanced)
# =============================================================================

SKILL_EXTRACTION_PROMPT = textwrap.dedent("""
    <system_prompt>
    You are the Skill Evolution Engine. Transform execution traces into reusable Omni Skills.

    Your output must be a valid JSON object matching the CandidateSkill schema.
    </system_prompt>

    <task_context>
        <description>{task}</description>
        <duration_ms>{duration}</duration_ms>
        <success>{success}</success>
    </task_context>

    <execution_trace>
    {commands_xml}
    </execution_trace>

    <execution_outputs>
    {outputs_xml}
    </execution_outputs>

    <extraction_requirements>
    1. Analyze the trace and identify a reusable pattern.
    2. Convert hardcoded values to parameters (e.g., "*.txt" → "$pattern").
    3. Generate 2-3 realistic usage scenarios.
    4. Generate 2-3 FAQ items that would help an LLM use this skill.
    5. Assess confidence score based on trace quality.
    </extraction_requirements>

    <output_format>
    Return a JSON object with:
    - suggested_name: snake_case skill name
    - description: one sentence summary
    - category: git|system|file|data|automation|other
    - nushell_script: optimized script with $param placeholders
    - parameters: {{"param_name": "description"}}
    - usage_scenarios: [{{"input": "...", "reasoning": "..."}}]
    - faq_items: [{{"q": "...", "a": "..."}}]
    - reasoning: why this is valuable
    - confidence_score: 0.0-1.0
    - estimated_complexity: low|medium|high

    If the trace is not worthy of a skill, return: {{"is_worthy": false, "skip_reason": "..."}}
    </output_format>
""")

COMPLEX_TASK_EXTRACTION_PROMPT = textwrap.dedent("""
    <system_prompt>
    You are analyzing a multi-step execution for skill extraction.
    Consolidate the workflow into a single reusable skill.
    </system_prompt>

    <execution_history>
    {history}
    </execution_history>

    <analysis_steps>
    1. Identify the high-level goal
    2. Extract common parameters across steps
    3. Create an optimized script that captures the essence
    4. Define the interface (parameters)
    5. Generate usage scenarios and FAQs
    </analysis_steps>

    <output_format>
    Same as SKILL_EXTRACTION_PROMPT, but with consolidated script.
    </output_format>
""")

# =============================================================================
# Factory Prompts
# =============================================================================

SKILL_CODE_GENERATION_PROMPT = textwrap.dedent("""
    <system_prompt>
    You are generating a Python skill implementation for Omni-Copilot.
    Follow the @skill_command decorator pattern.
    </system_prompt>

    <skill_specification>
    <name>{skill_name}</name>
    <description>{skill_description}</description>
    <category>{category}</category>
    <script>{nushell_script}</script>
    <parameters>
    {parameters}
    </parameters>
    </skill_specification>

    <requirements>
    1. Use @skill_command decorator from omni.core.skills.runtime.decorators
    2. Create async function with parameters matching the spec
    3. Use OmniCellRunner to execute the Nushell script
    4. Parameter types inferred from names (str, Path, int, bool)
    5. Add docstring with usage examples
    6. Include proper error handling
    7. Make idempotent where possible
    </requirements>

    <output>
    Return ONLY valid Python code, no markdown fences.
    """)
# Note: The closing tag and curly braces are escaped to prevent format() issues

SKILL_DOC_GENERATION_PROMPT = textwrap.dedent("""
    <system_prompt>
    Generate documentation for this skill in Markdown format.
    Include the XML usage guide section for LLM comprehension.
    </system_prompt>

    <skill_info>
    <name>{skill_name}</name>
    <description>{skill_description}</description>
    <category>{category}</category>
    <script>{nushell_script}</script>
    <parameters>{parameters}</parameters>
    <scenarios>{scenarios}</scenarios>
    <faqs>{faqs}</faqs>
    <original_context>{original_task}</original_context>
    <reasoning>{reasoning}</reasoning>
    </skill_info>

    <output_format>
    Markdown with:
    - Skill name and description
    - ## Usage section with Python example
    - ## XML Usage Guide section (for LLM)
    - ## Parameters table
    - ## FAQ section
    - ## Examples
    </output_format>
""")

# =============================================================================
# Evaluation Prompts
# =============================================================================

SKILL_QUALITY_ASSESSMENT_PROMPT = textwrap.dedent("""
    <system_prompt>
    Assess the quality of this proposed skill.
    </system_prompt>

    <skill_under_review>
    <name>{skill_name}</name>
    <description>{skill_description}</description>
    <script>{nushell_script}</script>
    <parameters>{parameters}</parameters>
    </skill_under_review>

    <evaluation_criteria>
    1. Clarity: Is the purpose clear? (1-5)
    2. Reusability: Can it be used in multiple contexts? (1-5)
    3. Safety: Does it avoid dangerous operations? (1-5)
    4. Completeness: Are edge cases handled? (1-5)
    5. Consistency: Does it follow Omni patterns? (1-5)
    </evaluation_criteria>

    <output_format>
    Return JSON:
    {{
        "score": 1-5,
        "strengths": ["..."],
        "weaknesses": ["..."],
        "suggestions": ["..."],
        "approved": true/false
    }}
    </output_format>
""")

# =============================================================================
# XML Guide Templates (For Factory Output)
# =============================================================================

XML_GUIDE_TEMPLATE = """\
<tool_augmentation name="{skill_name}">
  <description>{description}</description>
  <context>
    Auto-generated from trace: "{original_task}"
    Reasoning: {reasoning}
  </context>
  <scenarios>
{scenarios}
  </scenarios>
  <faq>
{faqs}
  </faq>
</tool_augmentation>"""

XML_SCENARIO_TEMPLATE = """\
    <scenario>
      <input>{input}</input>
      <reasoning>{reasoning}</reasoning>
    </scenario>"""

XML_FAQ_TEMPLATE = """\
    <item>
      <q>{question}</q>
      <a>{answer}</a>
    </item>"""


def render_xml_guide(
    skill_name: str,
    description: str,
    original_task: str,
    reasoning: str,
    scenarios: list[dict[str, str]],
    faqs: list[dict[str, str]],
) -> str:
    """Render the complete XML usage guide."""
    scenarios_xml = "\n".join(
        XML_SCENARIO_TEMPLATE.format(input=s.get("input", ""), reasoning=s.get("reasoning", ""))
        for s in scenarios
    )
    faqs_xml = "\n".join(
        XML_FAQ_TEMPLATE.format(question=f.get("q", ""), answer=f.get("a", "")) for f in faqs
    )

    return XML_GUIDE_TEMPLATE.format(
        skill_name=skill_name,
        description=description,
        original_task=original_task,
        reasoning=reasoning,
        scenarios=scenarios_xml,
        faqs=faqs_xml,
    )


__all__ = [
    "SKILL_EXTRACTION_PROMPT",
    "COMPLEX_TASK_EXTRACTION_PROMPT",
    "SKILL_CODE_GENERATION_PROMPT",
    "SKILL_DOC_GENERATION_PROMPT",
    "SKILL_QUALITY_ASSESSMENT_PROMPT",
    "XML_GUIDE_TEMPLATE",
    "render_xml_guide",
]
