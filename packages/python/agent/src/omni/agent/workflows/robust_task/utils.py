import re
import json
from typing import Any, Dict, List, Optional


def parse_xml_tag(content: str, tag: str) -> str:
    """
    Robustly extract content from XML-like tags.
    Handles:
    - Multi-line content
    - Attributes in tags (e.g. <step id="1">)
    - Missing closing tags (best effort, though risky)
    """
    # Pattern explanation:
    # <tag[^>]*>  : Matches opening tag with optional attributes
    # (.*?)       : Non-greedy match for content
    # </tag>      : Closing tag
    pattern = f"<{tag}[^>]*>(.*?)</{tag}>"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def parse_xml_steps(plan_xml: str) -> List[Dict[str, Any]]:
    """
    Parse <step> tags specifically, handling attributes.
    Returns a list of step dictionaries.
    """
    steps = []
    # Regex to find all steps with id and description
    # Matches: <step id="1">Desc</step> OR <step>Desc</step>
    step_pattern = re.compile(
        r'<step(?:\s+id=["\"]?(\w+)["\"]?)?[^>]*>\s*<description>(.*?)</description>\s*</step>',
        re.DOTALL,
    )

    matches = step_pattern.finditer(plan_xml)

    for i, match in enumerate(matches):
        step_id = match.group(1) or str(i + 1)
        description = match.group(2).strip()
        steps.append(
            {
                "id": step_id,
                "description": description,
                "status": "pending",
                "result": "",
                "tool_calls": [],
            }
        )

    return steps


def extract_json_from_action(action_content: str) -> Dict[str, Any]:
    """
    Extracts and parses JSON from within an <action> tag or markdown block.
    """
    # Remove markdown code blocks if present
    cleaned = re.sub(r"```(?:json)?", "", action_content).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: Try to find the first '{' and last '}'
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {}


def map_action_data(data: Dict[str, Any]) -> tuple[Optional[str], Dict[str, Any]]:
    """
    Maps various JSON formats to a standard (tool_name, tool_args) tuple.
    Supports:
    - tool/name/function -> tool_name
    - args/arguments/parameters/input -> tool_args
    """
    if not data:
        return None, {}

    # Potential keys for tool name
    name_keys = ["tool", "name", "function", "action"]
    # Potential keys for arguments
    args_keys = ["args", "arguments", "parameters", "input", "params"]

    tool_name = None
    tool_args = {}
    args_found = False

    for k in name_keys:
        if k in data:
            tool_name = data[k]
            break

    for k in args_keys:
        if k in data:
            tool_args = data[k]
            args_found = True
            break

    # Handle direct parameters if no args key found but tool name is present
    if tool_name and not args_found:
        # Assume all other keys are arguments
        tool_args = {k: v for k, v in data.items() if k not in name_keys}

    return tool_name, tool_args


class OutputCompressor:
    """Compresses large observations to prevent context overflow."""

    @staticmethod
    def compress(content: str, max_len: int = 2000) -> str:
        """Compress content if it exceeds max length."""
        if len(content) <= max_len:
            return content

        head = content[: max_len // 2]
        tail = content[-(max_len // 2) :]
        return (
            f"{head}\n"
            f"... [Output Truncated: {len(content) - max_len} chars hidden] ...\n"
            f"{tail}\n"
            "(Hint: Use a specific tool to read the hidden section if needed)"
        )
