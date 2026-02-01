from typing import Annotated, TypedDict, Union, List, Dict, Any
import operator


class Step(TypedDict):
    id: str
    description: str
    status: str  # "pending", "in_progress", "completed", "failed"
    result: str
    tool_calls: List[Dict[str, Any]]


class Plan(TypedDict):
    steps: List[Step]
    current_step_index: int


class ValidationResult(TypedDict):
    is_valid: bool
    feedback: str


class RobustTaskState(TypedDict):
    # Input
    user_request: str

    # Context
    clarified_goal: str
    context_files: List[str]
    discovered_tools: List[Dict[str, Any]]  # Tool definitions from skill.discover
    memory_context: str  # Retrieved knowledge from Memory Subgraph
    last_thought: str  # LLM reasoning from the latest step
    trace: Annotated[List[Dict[str, Any]], operator.add]  # Internal events trace

    # Human Interaction
    user_feedback: str  # Feedback provided by user during review
    approval_status: str  # "pending", "approved", "rejected", "modified"

    # Execution
    plan: Plan
    execution_history: Annotated[List[str], operator.add]

    # State
    status: str  # "clarifying", "planning", "executing", "validating", "completed", "failed"
    retry_count: int
    # Results
    validation_result: Dict[str, Any]
    final_summary: str  # Markdown summary of the entire session
    error: str  # Error message if task failed
