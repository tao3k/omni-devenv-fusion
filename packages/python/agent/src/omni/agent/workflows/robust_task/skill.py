from omni.foundation.api.decorators import skill_command
from .graph import build_graph


@skill_command(
    name="robust_task",
    category="workflow",
    description="Executes a robust task workflow with LangGraph and XML Q&A",
)
async def run_robust_task(request: str) -> str:
    """
    Run the robust task workflow.
    """
    app = build_graph()

    initial_state = {"user_request": request, "execution_history": [], "retry_count": 0}

    print(f"Starting workflow for: {request}")
    final_state = await app.ainvoke(initial_state)

    return f"Workflow Completed. Result: {final_state.get('validation_result')}"
