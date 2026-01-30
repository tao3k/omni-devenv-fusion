# Spec: XML-Q&A Schema Augmentation for Skill Commands

> **Status**: Draft
> **Complexity**: L2
> **Owner**: @omni-coder
> **Reference**: Derived from `agentgateway` research (2026-01-29)

## 1. Context & Goal (Why)

_LLMs often struggle with complex JSON Schemas, leading to parameter misuse, incorrect type passing, or ignoring mandatory constraints. Traditional schemas define "what" but lack "how" and "context"._

- **Goal**: Augment standard JSON Schema with an XML-based Q&A and Contextual Guide to provide LLMs with higher-order reasoning anchors for tool calling.
- **Problem**:
  - LLM mixes up similar args (e.g., `path` vs `dir`).
  - LLM ignores semantic constraints described only in docstrings.
  - JSON nesting creates visual parsing fatigue for the model.
- **Solution**: Convert Pydantic-based metadata and docstrings into a structured `<usage_guide>` XML block that contains FAQ, Example Scenarios, and Explicit Constraints.

## 2. Architecture & Interface (What)

### 2.1 Schema Definition (XML Structure)

```xml
<tool_augmentation name="{command_name}">
  <context>
    High-level purpose and "Workflow Exclusive" warnings.
  </context>
  <faq>
    <item>
      <q>Question about common ambiguity</q>
      <a>Clear instruction on parameter choice</a>
    </item>
  </faq>
  <constraints>
    <rule param="{arg_name}">Semantic rule (e.g., "Must be absolute path")</rule>
  </constraints>
  <scenarios>
    <scenario description="Typical use case">
      <input>{ "arg": "value" }</input>
      <reasoning>Why these args were chosen.</reasoning>
    </scenario>
  </scenarios>
</tool_augmentation>
```

### 2.2 Skill Command Interface

A new command will be added to the `skill` skill to automate the generation of these guides.

```python
@skill_command(
    name="generate_usage_guide",
    description="Generate an XML-based Q&A usage guide for a specific skill command to improve LLM accuracy."
)
async def generate_usage_guide(
    skill_name: str,
    command_name: str | None = None,
    output_format: Literal["xml", "markdown"] = "xml"
) -> CommandResult:
    """
    1. Reflects on the specified skill/command.
    2. Extracts Pydantic schema and docstrings.
    3. Uses LLM to synthesize FAQ and Scenarios based on common failure modes.
    4. Returns formatted guide for injection into System Context.
    """
    pass
```

## 3. Implementation Plan (How)

1. [ ] **Metadata Extraction**: Enhance `omni.foundation.api.schema` to export not just JSON, but raw docstring segments.
2. [ ] **Guide Generator Logic**: Implement `UsageGuideGenerator` that takes a `skill_command` and produces the XML structure.
3. [ ] **LLM Bootstrap**: Optionally use an LLM-based "Teacher" to generate the first version of the `<faq>` and `<scenarios>` by analyzing the tool's implementation.
4. [ ] **Injection Point**: Update `InferenceClient` (or MCP Registry) to append this XML guide to the tool's description field during LLM calls.
5. [ ] **Cache Integration**: Store generated guides in `.cache/skills/usage_guides/` to avoid repeated synthesis.

## 4. Verification Plan (Test)

- [ ] **Schema Accuracy**: Verify XML tags correctly map to JSON Schema parameters.
- [ ] **LLM Performance (A/B Test)**: Test LLM tool-calling accuracy on a "fragile" tool (e.g., `filesystem.replace` with complex regex) with and without the XML Usage Guide.
- [ ] **Zero-Shot Test**: Provide the XML guide to a new LLM instance and ask it to generate valid tool calls for complex edge cases.
