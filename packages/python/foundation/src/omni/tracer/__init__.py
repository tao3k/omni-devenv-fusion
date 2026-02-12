"""
omni.tracer - UltraRAG-style execution tracing system

Fine-grained execution tracing for LangGraph + MCP.

Provides:
- Step-by-step execution tracking
- Thinking content capture (LLM streaming)
- Memory pool for variable history ($var, memory_var conventions)
- Callback system for custom processing
- LangGraph integration
- Pipeline configuration (YAML to LangGraph generator)
- Rich console UI with colored output

UltraRAG Memory Conventions:
- $variable: Read-only parameters (from parameter.yaml)
- variable: Global variables
- memory_variable: History-tracked variables

Usage:
    from omni.tracer import ExecutionTracer, TracingCallbackHandler
    from omni.tracer.ui import traced, TracedExecution

    tracer = ExecutionTracer(trace_id="session-123")
    handler = TracingCallbackHandler(tracer)

    # Use with LangGraph
    app = graph.compile(callbacks=[handler])

    # Or use context manager
    async with traced("my_task", trace_id="run_001") as t:
        t.set_param("$query", "...")
        step = t.start_step("planner", "NODE_START", {...})
        ...
"""

from .callbacks import CallbackManager, LoggingCallback, TracingCallback
from .async_utils import DispatchMode, dispatch_coroutine
from .engine import ExecutionTracer, traced_session
from .interfaces import ExecutionStep, ExecutionTrace, MemoryPool, StepType
from .langgraph import TracingCallbackHandler, create_traced_app, stream_with_trace
from .mcp_invoker import MCPToolClient, MCPToolInvoker
from .composite_invoker import CompositeToolInvoker
from .invoker_stack import create_default_invoker_stack
from .pipeline_checkpoint import create_in_memory_checkpointer, compile_workflow
from .node_factory import (
    ToolInvoker,
    NoOpToolInvoker,
    MappingToolInvoker,
    create_pipeline_node,
)
from .retrieval_invoker import RetrievalToolInvoker
from .pipeline_builder import LangGraphPipelineBuilder
from .pipeline_runtime import (
    PipelineExecutor,
    create_langgraph_from_pipeline,
    create_langgraph_from_pipeline_with_defaults,
    create_langgraph_from_yaml,
    create_pipeline_executor,
    load_pipeline,
)
from .graphflow import run_graphflow_pipeline
from .xml import escape_xml, extract_attr, extract_tag
from .pipeline_schema import (
    CheckpointerRuntimeConfig,
    InvokerRuntimeConfig,
    PipelineConfig,
    PipelineRuntimeConfig,
    PipelineState,
    RetrievalRuntimeConfig,
    StateRuntimeConfig,
    TracerRuntimeConfig,
)
from .storage import InMemoryTraceStorage, TraceStorage
from .ui import (
    TracedExecution,
    traced,
    console,
    print_header,
    print_step_start,
    print_step_end,
    print_thinking,
    print_memory,
    print_param,
    print_error,
    print_success,
    print_info,
    print_trace_summary,
    print_execution_path,
)

__version__ = "0.2.0"

__all__ = [
    # Core
    "ExecutionTracer",
    "ExecutionTrace",
    "ExecutionStep",
    "StepType",
    "MemoryPool",
    # Callbacks
    "CallbackManager",
    "LoggingCallback",
    "TracingCallback",
    "DispatchMode",
    "dispatch_coroutine",
    # LangGraph
    "TracingCallbackHandler",
    "create_traced_app",
    "stream_with_trace",
    # MCP Invoker
    "MCPToolClient",
    "MCPToolInvoker",
    "CompositeToolInvoker",
    "RetrievalToolInvoker",
    "create_default_invoker_stack",
    "create_in_memory_checkpointer",
    "compile_workflow",
    # Pipeline Node Factory
    "ToolInvoker",
    "NoOpToolInvoker",
    "MappingToolInvoker",
    "create_pipeline_node",
    # Pipeline
    "PipelineConfig",
    "PipelineRuntimeConfig",
    "CheckpointerRuntimeConfig",
    "InvokerRuntimeConfig",
    "RetrievalRuntimeConfig",
    "TracerRuntimeConfig",
    "StateRuntimeConfig",
    "PipelineExecutor",
    "PipelineState",
    "LangGraphPipelineBuilder",
    "create_langgraph_from_pipeline",
    "create_langgraph_from_pipeline_with_defaults",
    "create_langgraph_from_yaml",
    "create_pipeline_executor",
    "load_pipeline",
    "run_graphflow_pipeline",
    "escape_xml",
    "extract_attr",
    "extract_tag",
    # Storage
    "TraceStorage",
    "InMemoryTraceStorage",
    # Utilities
    "traced_session",
    # UI
    "TracedExecution",
    "traced",
    "console",
    "print_header",
    "print_step_start",
    "print_step_end",
    "print_thinking",
    "print_memory",
    "print_param",
    "print_error",
    "print_success",
    "print_info",
    "print_trace_summary",
    "print_execution_path",
]
