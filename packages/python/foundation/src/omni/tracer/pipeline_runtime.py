"""
pipeline_runtime.py - Runtime execution and LangGraph assembly for pipelines.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from .async_utils import DispatchMode
from .engine import ExecutionTracer
from .interfaces import StepType
from .node_factory import ToolInvoker, create_pipeline_node
from .pipeline_builder import LangGraphPipelineBuilder
from .pipeline_checkpoint import compile_workflow
from .pipeline_schema import PipelineConfig, PipelineState


class PipelineExecutor:
    """Executes pipelines with tracing support."""

    def __init__(
        self,
        pipeline_path: str | Path | PipelineConfig,
        tracer: ExecutionTracer | None = None,
    ):
        if isinstance(pipeline_path, PipelineConfig):
            self.config = pipeline_path
        else:
            self.config = PipelineConfig.from_yaml(pipeline_path)

        self.tracer = tracer
        self.builder = LangGraphPipelineBuilder(self.config, tracer)

    def build_graph(self) -> dict[str, Any]:
        return self.builder.build()

    async def run(self, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        params = {**self.config.parameters, **(parameters or {})}

        if self.tracer:
            for key, value in params.items():
                self.tracer.set_param(key, value)

        results: dict[str, Any] = {}
        for step_def in self.config.pipeline:
            if isinstance(step_def, str):
                server, tool = step_def.split(".", 1)
                results[f"{server}.{tool}"] = await self._execute_step(
                    server,
                    tool,
                    params,
                    results,
                )

        return results

    async def _execute_step(
        self,
        server: str,
        tool: str,
        parameters: dict[str, Any],
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        step_id = None
        if self.tracer:
            step_id = self.tracer.start_step(
                name=f"{server}.{tool}",
                step_type=StepType.TOOL_START,
                input_data={"server": server, "tool": tool},
            )

        input_data = self._resolve_variables(parameters, previous_results)
        result = {"status": "executed", "input": input_data}

        if self.tracer and step_id:
            self.tracer.end_step(step_id, output_data=result)

        return result

    def _resolve_variables(
        self,
        parameters: dict[str, Any],
        results: dict[str, Any],
    ) -> dict[str, Any]:
        del results
        resolved = {}
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$"):
                param_name = value[1:]
                resolved[key] = parameters.get(param_name, value)
            else:
                resolved[key] = value
        return resolved


def create_langgraph_from_pipeline(
    pipeline_config: PipelineConfig,
    tracer: ExecutionTracer | None = None,
    state_schema: type[PipelineState] | None = None,
    tool_invoker: ToolInvoker | None = None,
    *,
    checkpointer: Any | None = None,
    use_memory_saver: bool = False,
) -> Any:
    """Create a LangGraph from pipeline configuration."""
    from langgraph.graph import END, START, StateGraph

    builder = LangGraphPipelineBuilder(pipeline_config, tracer)
    graph_def = builder.build()

    schema = state_schema or PipelineState
    workflow = StateGraph(schema)

    for node_name, node_config in graph_def["nodes"].items():
        workflow.add_node(
            node_name,
            create_pipeline_node(
                node_name=node_name,
                node_config=node_config,
                tool_invoker=tool_invoker,
                tracer=tracer,
            ),
        )

    entry_node = graph_def.get("entry_node")
    if entry_node:
        workflow.add_edge(START, entry_node)

    for from_node, to_node in graph_def["edges"]:
        workflow.add_edge(from_node, to_node)

    for from_node, condition, destinations in graph_def["conditional_edges"]:
        workflow.add_conditional_edges(from_node, condition, destinations)

    for exit_node in graph_def.get("exit_nodes", []):
        workflow.add_edge(exit_node, END)

    return compile_workflow(
        workflow,
        checkpointer=checkpointer,
        use_memory_saver=use_memory_saver,
    )


def create_langgraph_from_pipeline_with_defaults(
    pipeline_config: PipelineConfig,
    tracer: ExecutionTracer | None = None,
    state_schema: type[PipelineState] | None = None,
    *,
    mcp_client: Any | None = None,
    mapping: dict[str, Any] | None = None,
    include_retrieval: bool = True,
    retrieval_default_backend: str = "lance",
    tool_invoker: ToolInvoker | None = None,
    checkpointer: Any | None = None,
    use_memory_saver: bool = False,
) -> Any:
    """Create a LangGraph with a default invoker stack."""
    if tool_invoker is None:
        from .invoker_stack import create_default_invoker_stack

        tool_invoker = create_default_invoker_stack(
            mcp_client=mcp_client,
            mapping=mapping,
            include_retrieval=include_retrieval,
            retrieval_default_backend=retrieval_default_backend,
        )

    return create_langgraph_from_pipeline(
        pipeline_config=pipeline_config,
        tracer=tracer,
        state_schema=state_schema,
        tool_invoker=tool_invoker,
        checkpointer=checkpointer,
        use_memory_saver=use_memory_saver,
    )


def load_pipeline(path: str | Path) -> PipelineConfig:
    """Load a pipeline configuration from YAML."""
    return PipelineConfig.from_yaml(path)


def create_pipeline_executor(
    path: str | Path | PipelineConfig,
    tracer: ExecutionTracer | None = None,
) -> PipelineExecutor:
    """Create a pipeline executor."""
    return PipelineExecutor(path, tracer)


def _resolve_state_schema(schema_path: str | None) -> type[PipelineState] | None:
    """Resolve dotted path `module:attr` into a state schema type."""
    if not schema_path:
        return None
    if ":" not in schema_path:
        raise ValueError("`runtime.state.schema` must use `module.path:ClassName` format")
    module_name, attr = schema_path.split(":", 1)
    module = importlib.import_module(module_name)
    schema = getattr(module, attr, None)
    if schema is None:
        raise ValueError(f"State schema `{attr}` not found in module `{module_name}`")
    if not isinstance(schema, type):
        raise ValueError("Resolved state schema must be a type")
    return schema


def create_langgraph_from_yaml(
    path: str | Path,
    tracer: ExecutionTracer | None = None,
    state_schema: type[PipelineState] | None = None,
    *,
    mcp_client: Any | None = None,
    mapping: dict[str, Any] | None = None,
    tool_invoker: ToolInvoker | None = None,
    checkpointer: Any | None = None,
    include_retrieval: bool | None = None,
    retrieval_default_backend: str | None = None,
    use_memory_saver: bool | None = None,
    callback_dispatch_mode: DispatchMode | str | None = None,
) -> Any:
    """Create a LangGraph directly from YAML, honoring runtime config defaults."""
    pipeline_config = load_pipeline(path)
    runtime = pipeline_config.runtime

    resolved_include_retrieval = (
        include_retrieval if include_retrieval is not None else runtime.invoker.include_retrieval
    )
    resolved_retrieval_default_backend = (
        retrieval_default_backend
        if retrieval_default_backend is not None
        else runtime.retrieval.default_backend
    )
    resolved_use_memory_saver = (
        use_memory_saver if use_memory_saver is not None else runtime.checkpointer.type == "memory"
    )
    resolved_state_schema = state_schema or _resolve_state_schema(runtime.state.schema)

    if tracer is not None:
        tracer.callback_dispatch_mode = DispatchMode(
            callback_dispatch_mode or runtime.tracer.callback_dispatch_mode
        )

    return create_langgraph_from_pipeline_with_defaults(
        pipeline_config=pipeline_config,
        tracer=tracer,
        state_schema=resolved_state_schema,
        mcp_client=mcp_client,
        mapping=mapping,
        include_retrieval=resolved_include_retrieval,
        retrieval_default_backend=resolved_retrieval_default_backend,
        tool_invoker=tool_invoker,
        checkpointer=checkpointer,
        use_memory_saver=resolved_use_memory_saver,
    )


__all__ = [
    "PipelineExecutor",
    "create_langgraph_from_pipeline",
    "create_langgraph_from_pipeline_with_defaults",
    "create_langgraph_from_yaml",
    "load_pipeline",
    "create_pipeline_executor",
    "_resolve_state_schema",
]
