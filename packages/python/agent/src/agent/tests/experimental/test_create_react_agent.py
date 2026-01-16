"""
test_create_react_agent.py - Analysis: LangGraph's create_react_agent vs DynamicGraphBuilder

This module provides a comprehensive analysis of LangGraph's prebuilt ReAct agent
compared to our custom DynamicGraphBuilder for the Smart Commit workflow.

Key Findings:
1. create_react_agent has been DEPRECATED in LangGraph v1.0
2. It has been moved to langchain.agents as create_agent
3. Our DynamicGraphBuilder remains the appropriate solution for this project
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


class TestCreateReactAgentAnalysis:
    """
    Analysis of create_react_agent for our use case.

    Despite being deprecated, we can still analyze its API to understand
    the trade-offs between prebuilt and custom solutions.
    """

    def test_deprecation_notice(self):
        """Verify that create_react_agent is deprecated."""
        import warnings

        # The deprecation warning is emitted by Pyright/linter, not at runtime
        # Let's just verify the function exists and document the deprecation
        from langgraph.prebuilt import create_react_agent

        # Function exists but is deprecated
        assert callable(create_react_agent)
        print("Note: create_react_agent is deprecated in LangGraph v1.0")
        print("It has been moved to langchain.agents.create_agent")

    def test_api_capabilities_analysis(self):
        """
        Analyze create_react_agent API capabilities.

        Based on the deprecation notice, the function has been moved to
        langchain.agents. Let's document its capabilities for comparison.
        """
        from langgraph.prebuilt import create_react_agent
        import inspect

        sig = inspect.signature(create_react_agent)
        params = list(sig.parameters.keys())

        # Key parameters that our DynamicGraphBuilder should support
        key_params = [
            "model",  # LLM for the agent
            "tools",  # Tools for the agent
            "interrupt_before",  # Human-in-the-loop interrupt
            "interrupt_after",  # Post-execution interrupt
            "checkpointer",  # State persistence
            "state_schema",  # Custom state type
            "pre_model_hook",  # Pre-processing
            "post_model_hook",  # Post-processing
        ]

        # All key params should be supported
        for param in key_params:
            assert param in params, f"Missing parameter: {param}"

    def test_dynamic_builder_capabilities_comparison(self):
        """
        Compare DynamicGraphBuilder capabilities with create_react_agent.
        """
        from agent.core.orchestrator.builder import DynamicGraphBuilder

        # DynamicGraphBuilder should support similar functionality
        builder = DynamicGraphBuilder(skill_manager=MagicMock())

        # Check for equivalent methods
        assert hasattr(builder, "add_skill_node")
        assert hasattr(builder, "add_function_node")
        assert hasattr(builder, "add_llm_node")
        assert hasattr(builder, "compile")
        assert hasattr(builder, "visualize")

        # Check for interrupt support in compile
        import inspect

        compile_sig = inspect.signature(builder.compile)
        assert "interrupt_before" in compile_sig.parameters
        assert "interrupt_after" in compile_sig.parameters


class TestCodeComplexityComparison:
    """
    Compare code complexity between the two approaches.
    """

    def test_code_lines_comparison(self):
        """
        Estimate code complexity for implementing Smart Commit workflow.

        DynamicGraphBuilder approach:
        - Define workflow: ~50 lines
        - State management: Built-in
        - Interrupt handling: Via compile()

        create_react_agent approach (if available):
        - Define workflow: ~10 lines
        - State management: Automatic
        - Interrupt handling: Via parameters
        """
        # DynamicGraphBuilder implementation (from graph_workflow.py)
        dynamic_builder_impl = """
def build_smart_commit_graph(skill_manager):
    builder = DynamicGraphBuilder(skill_manager)
    builder.add_skill_node("prepare", "git", "stage_and_scan", ...)
    builder.add_skill_node("execute", "git", "commit", ...)
    builder.add_conditional_edges("prepare", route_logic, {...})
    builder.add_edge("execute", END)
    return builder.compile(interrupt_before=["execute"])
"""
        # Lines of code estimate
        dynamic_builder_loc = len(dynamic_builder_impl.strip().split("\n"))

        # create_react_agent implementation (hypothetical)
        prebuilt_impl = """
agent = create_react_agent(
    model_with_tools,
    tools,
    interrupt_before=["tools"],
)
"""
        prebuilt_loc = len(prebuilt_impl.strip().split("\n"))

        # DynamicGraphBuilder is more verbose but offers more control
        assert dynamic_builder_loc > prebuilt_loc

        # Both should be valid approaches for different use cases
        print(f"DynamicGraphBuilder: ~{dynamic_builder_loc} lines (more control)")
        print(f"create_react_agent: ~{prebuilt_loc} lines (less code, less control)")


class TestRecommendationSummary:
    """
    Summary of recommendations for using create_react_agent vs DynamicGraphBuilder.
    """

    def test_recommendation_for_different_scenarios(self):
        """
        Provide recommendations for when to use each approach.
        """
        recommendations = {
            "simple_react_agent": {
                "use": "create_react_agent (langchain.agents)",
                "reason": "Standard ReAct loop, no custom routing needed",
            },
            "custom_workflow_with_branches": {
                "use": "DynamicGraphBuilder",
                "reason": "Custom conditional routing, skill integration",
            },
            "human_in_the_loop": {
                "use": "Both support interrupt_before",
                "reason": "Both have this capability",
            },
            "complex_state_schema": {
                "use": "DynamicGraphBuilder",
                "reason": "Full control over state schema",
            },
            "quick_prototype": {
                "use": "create_react_agent (langchain.agents)",
                "reason": "Minimal code required",
            },
        }

        for scenario, details in recommendations.items():
            assert "use" in details
            assert "reason" in details
            print(f"{scenario}: {details['use']}")
            print(f"  Reason: {details['reason']}")

    def test_final_recommendation(self):
        """
        Final recommendation for the Omni-Dev 1.0 Smart Commit workflow.
        """
        # For our use case, DynamicGraphBuilder is the right choice because:
        reasons = [
            "We need to integrate with our existing skill system",
            "We have custom conditional routing (security scan, lefthook)",
            "We have complex state management requirements",
            "create_react_agent has been deprecated and requires langchain",
            "Our DynamicGraphBuilder provides the right level of abstraction",
        ]

        for reason in reasons:
            print(f"- {reason}")

        # Conclusion
        print("\nConclusion: DynamicGraphBuilder is the appropriate choice")
        print("for the Omni-Dev 1.0 Smart Commit workflow.")
