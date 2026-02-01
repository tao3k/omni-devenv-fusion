from langgraph.graph import StateGraph, END
from .state import MemoryState
from .nodes import recall_node, synthesize_node, store_node


def build_memory_graph():
    workflow = StateGraph(MemoryState)

    workflow.add_node("recall", recall_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("store", store_node)

    # Conditional Entry Point
    def route_start(state: MemoryState) -> str:
        if state["mode"] == "store":
            return "store"
        return "recall"

    workflow.set_conditional_entry_point(route_start, {"recall": "recall", "store": "store"})

    workflow.add_edge("recall", "synthesize")
    workflow.add_edge("synthesize", END)
    workflow.add_edge("store", END)

    return workflow.compile()
