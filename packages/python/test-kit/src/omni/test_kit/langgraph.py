from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock
import pytest
from omni.langgraph.graph import OmniGraph, GraphState


class LangGraphTester:
    """
    Dedicated Tester for LangGraph workflows.
    """

    def __init__(self):
        self.inference = AsyncMock()
        self.skill_runner = AsyncMock()
        self.router = AsyncMock()
        self.checkpointer = MagicMock()  # Mock checkpointer by default
        self.graph = OmniGraph(
            inference_client=self.inference,
            skill_runner=self.skill_runner,
            router=self.router,
            checkpointer=self.checkpointer,
            use_rust_checkpointer=False,  # Disable Rust checkpointer for unit tests
        )

    def mock_inference_response(self, content: str, confidence: float = 0.9):
        """Mock the LLM inference response."""
        self.inference.complete.return_value = {"content": content, "confidence": confidence}

    def mock_router_response(self, target_agent: str, task_brief: str = "task"):
        """Mock the router response."""
        self.router.route.return_value = {
            "target_agent": target_agent,
            "task_brief": task_brief,
            "confidence": 0.9,
        }

    def mock_skill_execution(self, result: str):
        """Mock skill execution result."""
        self.skill_runner.run.return_value = result

    async def run_step(self, node_name: str, state: GraphState) -> Dict[str, Any]:
        """Run a single node with the given state."""
        # This requires accessing internal methods of OmniGraph, which is fine for testing
        if node_name == "plan":
            return await self.graph._plan_node(state)
        elif node_name == "execute":
            return await self.graph._execute_node(state)
        elif node_name == "reflect":
            return await self.graph._reflect_node(state)
        elif node_name == "recall":
            return await self.graph._recall_node(state)
        else:
            raise ValueError(f"Unknown node: {node_name}")

    async def run_workflow(self, user_query: str, thread_id: str = "test-thread") -> Any:
        """Run the full workflow."""
        return await self.graph.run(user_query, thread_id)


@pytest.fixture
def langgraph_tester():
    """Fixture to provide LangGraphTester instance."""
    return LangGraphTester()
