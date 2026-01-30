from typing import Dict, Any, List
from ..state import RobustTaskState
from ..nodes import call_llm
from ..utils import parse_xml_tag

REFLECTION_PROMPT = """
You are a senior engineer conducting a retrospective.
Analyze the execution history and the validation result.

Goal: {goal}
History:
{history}

Validation Feedback:
{feedback}

Identify the root cause of failure or potential improvements.
If failed, suggest a specific strategy to fix it in the next attempt.

Output format:
<analysis>
Detailed analysis of what happened.
</analysis>

<strategy>
Specific adjustment for the next attempt (e.g., "Use a different tool", "Change parameters", "Break down the step").
</strategy>
"""

async def reflection_node(state: RobustTaskState) -> Dict[str, Any]:
    # print("--- Reflection Node ---")
    
    validation = state.get("validation_result", {})
    history_str = "\n".join(state.get("execution_history", []))
    
    prompt = REFLECTION_PROMPT.format(
        goal=state["clarified_goal"],
        history=history_str,
        feedback=validation.get("feedback", "Unknown failure")
    )
    
    response = await call_llm(prompt, system="You are a senior engineer.")
    
    analysis = parse_xml_tag(response, "analysis")
    strategy = parse_xml_tag(response, "strategy")
    thought = parse_xml_tag(response, "thought") # If prompt is updated to include it
    
    # Store reflection in history for context in next loop
    reflection_entry = f"REFLECTION: {analysis}\nSTRATEGY: {strategy}"
    
    return {
        "execution_history": [reflection_entry],
        "retry_count": state.get("retry_count", 0) + 1,
        "last_thought": analysis # Using analysis as thought for reflection
    }

