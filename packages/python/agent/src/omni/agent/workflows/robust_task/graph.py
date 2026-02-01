from langgraph.graph import StateGraph, END
from .state import RobustTaskState
from .nodes import (
    clarify_node,
    discovery_node,
    plan_node,
    execute_node,
    validate_node,
    advance_step,
    check_execution_progress,
    summary_node,
)
from .reflection.node import reflection_node
from .review.node import review_node


def build_graph(checkpointer=None):
    workflow = StateGraph(RobustTaskState)

    workflow.add_node("discovery", discovery_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("review", review_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("advance", advance_step)
    workflow.add_node("validate", validate_node)
    workflow.add_node("reflect", reflection_node)
    workflow.add_node("summary", summary_node)

    workflow.set_entry_point("discovery")

    workflow.add_edge("discovery", "clarify")

    def route_clarify(state: RobustTaskState) -> str:
        status = state.get("status")
        if status == "planning":
            return "plan"
        elif status == "clarifying":
            return "clarify"
        else:  # failed
            return "summary"

    workflow.add_conditional_edges(
        "clarify", route_clarify, {"plan": "plan", "clarify": "clarify", "summary": "summary"}
    )

    workflow.add_edge("plan", "execute")

    workflow.add_conditional_edges(
        "execute",
        check_execution_progress,
        {
            "continue": "advance",
            "validate": "review",  # Review happens BEFORE validation/finalization
        },
    )

    workflow.add_edge("advance", "execute")

    def route_review(state: RobustTaskState) -> str:
        status = state.get("approval_status")
        if status == "approved":
            return "validate"
        elif status == "modified":  # User provided feedback/changes
            return "plan"  # Re-plan with feedback
        elif status == "rejected":
            return "summary"
        else:  # "pending" or "waiting_for_user"
            return "review"  # Loop (or wait for interrupt)

    workflow.add_conditional_edges(
        "review",
        route_review,
        {"validate": "validate", "plan": "plan", "summary": "summary", "review": "review"},
    )

    def route_validate(state: RobustTaskState) -> str:
        status = state.get("status")
        if status == "completed":
            return "summary"
        elif state.get("retry_count", 0) < 3:  # Allow 3 retries
            return "reflect"
        else:
            return "summary"

    workflow.add_conditional_edges(
        "validate", route_validate, {"summary": "summary", "reflect": "reflect"}
    )

    def route_reflect(state: RobustTaskState) -> str:
        # After reflection, we go back to planning to adjust
        return "plan"

    workflow.add_edge("reflect", "plan")
    workflow.add_edge("summary", END)

    # We must compile with interrupt_before=["review"] to pause execution
    # This allows us to inspect state and provide input
    return workflow.compile(interrupt_before=["review"], checkpointer=checkpointer)
