from typing import Any, Dict
from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import think_node, act_node, reflect_node


def build_react_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("think", think_node)
    workflow.add_node("act", act_node)
    workflow.add_node("reflect", reflect_node)

    workflow.set_entry_point("think")

    def route_think(state: AgentState) -> str:
        if state.get("exit_reason"):
            return END
        if state.get("tool_calls"):
            return "act"
        return END  # No tool calls = done (or just chat)

    workflow.add_conditional_edges("think", route_think, {"act": "act", END: END})

    workflow.add_edge("act", "reflect")

    def route_reflect(state: AgentState) -> str:
        if state.get("exit_reason"):
            return END
        return "think"

    workflow.add_conditional_edges("reflect", route_reflect, {"think": "think", END: END})

    return workflow.compile()
