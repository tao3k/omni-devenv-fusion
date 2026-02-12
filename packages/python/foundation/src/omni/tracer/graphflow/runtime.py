# =============================================================================
# Graphflow Runtime - UltraRAG Style
# =============================================================================
"""
UltraRAG-style execution tracing runtime with LangGraph.

Features:
- LangGraph state machine with typed schema
- Memory pool (analysis, reflections, draft, final)
- Conditional edges (should we reflect again?)
- Reflection loops
- Checkpoint persistence
- Rich execution tracing output

Skill usage entrypoint:
    omni skill run demo.run_langgraph '{"scenario": "simple"}'
    omni skill run demo.run_langgraph '{"scenario": "loop"}'
    omni skill run demo.run_langgraph '{"scenario": "complex"}'
"""

from datetime import datetime
from .ui import console, ultra_header, ultra_memory_pool, ultra_summary
from .llm_service import get_llm_service
from .tracer import LangGraphTracer
from .types import DemoState
from .builders import (
    apply_parameter_overrides,
    create_initial_state,
    default_parameters_for_scenario,
    register_scenario_graph,
)


async def run_graphflow_pipeline(
    scenario: str = "complex",
    quality_threshold: float | None = None,
    quality_gate_novelty_threshold: float | None = None,
    quality_gate_coverage_threshold: float | None = None,
    quality_gate_min_evidence_count: int | None = None,
    quality_gate_require_tradeoff: bool | None = None,
    quality_gate_max_fail_streak: int | None = None,
) -> dict[str, object]:
    """Run LangGraph demo with execution tracing.

    Args:
        scenario: Pipeline type - "simple", "loop", or "complex"
        quality_threshold: Optional override for target quality to stop
        quality_gate_novelty_threshold: Optional override for novelty gate
        quality_gate_coverage_threshold: Optional override for critique coverage gate
        quality_gate_min_evidence_count: Optional override for minimum evidence gate
        quality_gate_require_tradeoff: Optional override for tradeoff requirement gate
        quality_gate_max_fail_streak: Optional override for max consecutive gate failures

    Returns:
        Dict with trace_id, execution details, and memory pool
    """
    import time

    # Lazy import langgraph to avoid triggering embedding during skill loading
    from langgraph.graph import END, StateGraph
    from langgraph.checkpoint.memory import MemorySaver

    timestamp = datetime.now().strftime("%H%M%S")
    trace_id = f"ultrarag_{scenario}_{timestamp}"
    thread_id = f"session_{scenario}_{timestamp}"

    # Print UltraRAG header
    console.print(ultra_header(trace_id, thread_id, scenario))

    # Initialize tracer
    tracer = LangGraphTracer(trace_id, thread_id, scenario)
    get_llm_service().reset_runtime_state()

    parameters = default_parameters_for_scenario(scenario)
    parameters = apply_parameter_overrides(
        parameters,
        quality_threshold=quality_threshold,
        quality_gate_novelty_threshold=quality_gate_novelty_threshold,
        quality_gate_coverage_threshold=quality_gate_coverage_threshold,
        quality_gate_min_evidence_count=quality_gate_min_evidence_count,
        quality_gate_require_tradeoff=quality_gate_require_tradeoff,
        quality_gate_max_fail_streak=quality_gate_max_fail_streak,
    )

    # Print memory pool initialization
    console.print(
        ultra_memory_pool(
            [
                {"name": "topic", "type": "input", "source": "-", "status": "[green]READY[/green]"},
                {
                    "name": "analysis",
                    "type": "memory (LLM)",
                    "source": "analyzer.analyze",
                    "status": "[yellow]pending[/yellow]",
                },
                {
                    "name": "reflection_labels",
                    "type": "memory (LLM)",
                    "source": "reflector.reflect",
                    "status": "[yellow]pending[/yellow]",
                },
                {
                    "name": "quality_evaluations",
                    "type": "memory (LLM)",
                    "source": "evaluator.evaluate",
                    "status": "[yellow]pending[/yellow]",
                },
                {
                    "name": "memory_thinking",
                    "type": "memory (LLM)",
                    "source": "all nodes",
                    "status": "[yellow]pending[/yellow]",
                },
                {
                    "name": "draft",
                    "type": "memory (LLM)",
                    "source": "drafter.draft",
                    "status": "[yellow]pending[/yellow]",
                },
                {
                    "name": "final",
                    "type": "memory (LLM)",
                    "source": "drafter.finalize",
                    "status": "[yellow]pending[/yellow]",
                },
            ]
        )
    )

    # Memory pool initialization
    tracer.record_memory("topic", parameters["topic"], step="input", metadata={})

    # Create LangGraph
    workflow = StateGraph(DemoState)

    register_scenario_graph(workflow, scenario, tracer, END)
    initial_state = create_initial_state(parameters, scenario)

    # Compile with checkpoint
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

    # Execute
    start_time = time.time()
    result = await app.ainvoke(
        DemoState(**initial_state), config={"configurable": {"thread_id": thread_id}}
    )
    execution_time_ms = round((time.time() - start_time) * 1000, 2)

    # Finalize trace
    tracer.finalize()
    memory_output_path = tracer.write_memory_output()

    # Print execution summary
    console.print(
        ultra_summary(
            trace_id=trace_id,
            thread_id=thread_id,
            scenario=scenario,
            status="SUCCESS",
            duration_ms=execution_time_ms,
            steps=len(tracer.trace.steps),
            memory={
                "topic": result["topic"],
                "analysis": result["analysis"],
                "reflections": result["reflection_labels"],
                "quality_eval_last": result["quality_evaluations"][-1]
                if result["quality_evaluations"]
                else "",
                "routing_reason": result["routing_reason"],
                "draft": result["draft"],
                "final": result["final"],
            },
            tracer=tracer,
        )
    )

    return {
        "status": "success",
        "trace_id": trace_id,
        "thread_id": thread_id,
        "scenario": scenario,
        "provider_disabled": get_llm_service()._provider_disabled,
        "provider_failure_reason": get_llm_service()._provider_failure_reason,
        "memory_output_path": memory_output_path,
        "execution": {
            "duration_ms": execution_time_ms,
            "steps_count": len(tracer.trace.steps),
        },
        "memory_pool": {
            "topic": result["topic"],
            "analysis": result["analysis"],
            "reflections_count": len(result["reflection_labels"]),
            "quality_evaluations_count": len(result["quality_evaluations"]),
            "routing_reason": result["routing_reason"],
            "draft": result["draft"],
            "final": result["final"],
        },
        "trace": tracer.trace.to_dict(),
    }
