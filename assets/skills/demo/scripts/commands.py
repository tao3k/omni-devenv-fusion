# =============================================================================

# Demo Command - Simple Hot Reload Test + YAML Pipeline Tests
# =============================================================================
"""
Demo skill command for testing hot reload functionality and YAML pipelines.

This command demonstrates the @skill_command pattern and can be modified
without running `omni skill sync` - the Live-Wire watcher should detect
changes automatically.

Usage:
    omni skill run demo.hello --name "World"
    omni skill run demo.hello
    omni skill run demo.test_yaml_pipeline
    omni skill run demo.test_yaml_pipeline --pipeline_type "rag"
"""

from datetime import datetime
from typing import Literal

from omni.foundation.api.decorators import skill_command
from omni.foundation.api.response_payloads import build_status_error_response
from omni.foundation.config.skills import SKILLS_DIR


@skill_command(
    name="hello",
    description="Simple demo command for testing hot reload.",
    read_only=True,
    destructive=False,
    idempotent=True,
    open_world=False,
)
async def hello(name: str = "Guest") -> dict[str, object]:
    """Say hello with a timestamp.

    Args:
        name: Name to greet (default: "Guest")

    Returns:
        Dict with greeting message and timestamp
    """
    timestamp = datetime.now().isoformat()

    return {
        "message": f"[V2] Hello {name}!",
        "timestamp": timestamp,
        "greeted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@skill_command(
    name="echo",
    description="Echo back the input message.",
    read_only=True,
    destructive=False,
    idempotent=True,
    open_world=False,
)
async def echo(message: str = "Hello!") -> dict[str, object]:
    """Echo the input message with a timestamp.

    Args:
        message: Message to echo (default: "Hello!")

    Returns:
        Dict with echoed message and timestamp
    """
    return {
        "original_message": message,
        "echoed_message": f"Echo: {message}",
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# YAML Pipeline Tests (using omni.tracer)
# =============================================================================


@skill_command(
    name="test_yaml_pipeline",
    description="Test YAML pipeline compilation and execution with omni.tracer.",
    read_only=True,
    destructive=False,
    idempotent=True,
    open_world=False,
)
async def test_yaml_pipeline(
    pipeline_type: Literal["simple", "loop", "branch", "rag"] = "simple",
) -> dict[str, object]:
    """Test YAML pipeline functionality.

    Args:
        pipeline_type: Type of pipeline to test
            - simple: Sequential pipeline (analyze → draft → finalize)
            - loop: Pipeline with iteration loop (analyze → evaluate → reflect)
            - branch: Pipeline with conditional branching
            - rag: Full RAG pipeline with retrieval

    Returns:
        Dict with pipeline execution results and trace
    """
    from omni.tracer import (
        ExecutionTracer,
        NoOpToolInvoker,
        console,
        create_langgraph_from_yaml,
        load_pipeline,
    )
    from omni.tracer.ui import print_header, print_success

    # Get pipeline YAML path
    pipelines_dir = SKILLS_DIR(skill="demo", path="pipelines")
    yaml_path = pipelines_dir / f"{pipeline_type}.yaml"

    if not yaml_path.exists():
        return build_status_error_response(
            error=f"Pipeline file not found: {yaml_path}",
            extra={
                "pipeline_type": pipeline_type,
                "available_types": ["simple", "loop", "branch", "rag"],
            },
        )

    # Create tracer
    trace_id = f"test_{pipeline_type}_{datetime.now().strftime('%H%M%S')}"
    tracer = ExecutionTracer(trace_id=trace_id)

    print_header(f"YAML Pipeline Test: {pipeline_type.upper()}")
    console.print(f"[dim]Trace ID: {trace_id}[/dim]")
    console.print(f"[dim]Pipeline file: {yaml_path}[/dim]")

    try:
        # Load pipeline config
        config = load_pipeline(yaml_path)
        console.print(f"[green]✓ Loaded pipeline with {len(config.pipeline)} steps[/green]")
        console.print(
            f"[green]✓ Runtime config: checkpointer={config.runtime.checkpointer.type}, "
            f"retrieval={config.runtime.invoker.include_retrieval}[/green]"
        )

        # Create LangGraph with NoOp tool invoker (no actual LLM calls)
        # This tests YAML loading, compilation, and graph structure
        create_langgraph_from_yaml(
            str(yaml_path),
            tracer=tracer,
            tool_invoker=NoOpToolInvoker(),
        )
        console.print("[green]✓ Compiled LangGraph from YAML[/green]")

        # Get trace summary
        memory_summary = tracer.get_memory_summary()
        step_count = len(tracer.trace.steps)

        print_success("YAML pipeline compiled successfully (NoOp mode)")

        return {
            "status": "success",
            "pipeline_type": pipeline_type,
            "trace_id": trace_id,
            "yaml_path": str(yaml_path),
            "steps_configured": len(config.pipeline),
            "steps_tracked": step_count,
            "memory_pool_summary": memory_summary,
            "runtime_defaults_used": {
                "checkpointer": config.runtime.checkpointer.type,
                "include_retrieval": config.runtime.invoker.include_retrieval,
                "callback_mode": config.runtime.tracer.callback_dispatch_mode,
            },
            "note": "Compiled with NoOpToolInvoker. For full execution, provide real tool invoker.",
        }

    except Exception as e:
        console.print(f"[red]✗ Pipeline test failed: {e}[/red]")
        return build_status_error_response(
            error=str(e),
            extra={
                "pipeline_type": pipeline_type,
                "trace_id": trace_id,
            },
        )


@skill_command(
    name="list_pipeline_examples",
    description="List available YAML pipeline examples.",
    read_only=True,
    destructive=False,
    idempotent=True,
    open_world=False,
)
async def list_pipeline_examples() -> dict[str, object]:
    """List available YAML pipeline test examples.

    Returns:
        Dict with available pipeline types and their descriptions
    """
    examples = {
        "simple": {
            "description": "Sequential pipeline: analyze → draft → finalize",
            "steps": 3,
            "features": ["basic flow", "memory checkpointer"],
        },
        "loop": {
            "description": "Iterative pipeline with quality evaluation",
            "steps": "3 + loop iterations",
            "features": ["loop control", "conditional branch", "quality routing"],
        },
        "branch": {
            "description": "Conditional branching based on quality",
            "steps": "variable (2-4)",
            "features": ["branch router", "quality threshold"],
        },
        "rag": {
            "description": "Full RAG pipeline with retrieval",
            "steps": 3,
            "features": ["retrieval", "generation", "evaluation"],
        },
    }

    return {
        "status": "success",
        "examples": examples,
        "usage": "omni skill run demo.test_yaml_pipeline --pipeline_type <type>",
    }
