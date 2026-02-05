"""
Interactive Search Graph - LangGraph Workflow

Orchestrates parallel search execution with:
- Intent classification for strategy selection
- Parallel AST/Vector/Grep execution
- Result synthesis and XML formatting
- State persistence via Checkpoint (for future time-travel)
"""

from datetime import datetime
from typing import List

from langgraph.graph import StateGraph, END

from .state import SearchGraphState
from .nodes import classifier, engines, formatter


def create_search_graph() -> StateGraph:
    """Create the Interactive Search Graph.

    Flow:
        Input -> Classify -> Parallel Exec -> Synthesize -> Output
                      |              |
                      +-> AST ------+
                      +-> Vector ----+
                      +-> Grep ------+
    """
    # Create the state graph
    workflow = StateGraph(SearchGraphState)

    # Add nodes
    workflow.add_node("classify", classifier.classify_intent)
    workflow.add_node("run_ast", engines.node_run_ast_search)
    workflow.add_node("run_vector", engines.node_run_vector_search)
    workflow.add_node("run_grep", engines.node_run_grep_search)
    workflow.add_node("synthesize", formatter.synthesize_results)

    # Set entry point
    workflow.set_entry_point("classify")

    # Classify -> Route to appropriate engines (parallel)
    def route_after_classify(state: SearchGraphState) -> List[str]:
        """Route to search engines based on classification."""
        strategies = state.get("strategies", [])
        branches = []
        if "ast" in strategies:
            branches.append("run_ast")
        if "vector" in strategies:
            branches.append("run_vector")
        if "grep" in strategies:
            branches.append("run_grep")

        # Fallback to vector if no strategies
        if not branches:
            branches.append("run_vector")

        return branches

    workflow.add_conditional_edges(
        "classify", route_after_classify, ["run_ast", "run_vector", "run_grep"]
    )

    # Parallel branches -> Synthesize
    for node in ["run_ast", "run_vector", "run_grep"]:
        workflow.add_edge(node, "synthesize")

    # Synthesize -> END
    workflow.add_edge("synthesize", END)

    return workflow


def create_initial_state(query: str, thread_id: str = "default") -> SearchGraphState:
    """Create initial state for the search graph."""
    return {
        "query": query,
        "strategies": [],  # Filled by classifier
        "raw_results": [],
        "iteration": 0,
        "needs_clarification": False,
        "clarification_prompt": "",
        "final_output": "",
        "thread_id": thread_id,
        "timestamp": datetime.now().isoformat(),
    }


# Global compiled graph (lazily initialized)
_search_graph = None


def get_search_graph() -> StateGraph:
    """Get or create the compiled search graph."""
    global _search_graph
    if _search_graph is None:
        workflow = create_search_graph()
        _search_graph = workflow
    return _search_graph


async def execute_search(query: str, thread_id: str = "default") -> dict:
    """Execute the search graph asynchronously.

    Args:
        query: Search query
        thread_id: Session ID for checkpointing

    Returns:
        Final state with formatted output
    """
    from langgraph.checkpoint.memory import MemorySaver

    graph = get_search_graph()

    # Compile with in-memory checkpointing
    # Note: For production, use Rust LanceDB checkpointer
    memory = MemorySaver()
    compiled = graph.compile(checkpointer=memory)

    # Create initial state
    state = create_initial_state(query, thread_id)

    # Execute the graph
    final_state = await compiled.ainvoke(state, config={"configurable": {"thread_id": thread_id}})

    return final_state
