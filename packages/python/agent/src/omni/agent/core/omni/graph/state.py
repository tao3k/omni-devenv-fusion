from typing import TypedDict, List, Dict, Any, Annotated
import operator


class AgentState(TypedDict):
    # Input
    user_query: str

    # Context (Long-term & Session)
    system_prompt: str
    messages: Annotated[List[Dict[str, Any]], operator.add]

    # Tool Management
    available_tools: List[Dict[str, Any]]

    # Execution State
    step_count: int
    tool_calls_count: int
    consecutive_errors: int
    tool_hash_history: List[str]

    # Current Turn Data
    last_response: str
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]

    # Flow Control
    status: str  # "thinking", "acting", "reflecting", "done", "failed"
    exit_reason: str
