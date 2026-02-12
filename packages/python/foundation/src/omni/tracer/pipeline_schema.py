"""
pipeline_schema.py - Typed pipeline configuration and validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import yaml

from omni.foundation.config.logging import get_logger
from .pipeline_json_schema import validate_pipeline_schema, validate_pipeline_tool_contracts

logger = get_logger("omni.tracer.pipeline")


class PipelineState(TypedDict, total=False):
    """State type for pipeline execution."""


@dataclass
class Segment:
    """Compiled segment with a single entry and one or more exits."""

    entry: str
    exits: list[str]


@dataclass
class StepConfig:
    """Configuration for a single step."""

    server: str
    tool: str
    input_mapping: dict[str, str] = field(default_factory=dict)
    output_mapping: dict[str, str] = field(default_factory=dict)


@dataclass
class LoopConfig:
    """Configuration for a loop."""

    steps: list[dict[str, Any]] = field(default_factory=list)
    max_iterations: int = 3


@dataclass
class BranchConfig:
    """Configuration for branching."""

    router: str
    branches: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass
class CheckpointerRuntimeConfig:
    """Runtime checkpointer configuration."""

    type: str = "none"  # none | memory


@dataclass
class InvokerRuntimeConfig:
    """Runtime invoker stack configuration."""

    include_retrieval: bool = True


@dataclass
class RetrievalRuntimeConfig:
    """Runtime retrieval backend configuration."""

    default_backend: str = "lance"  # lance | hybrid


@dataclass
class TracerRuntimeConfig:
    """Runtime tracer behavior configuration."""

    callback_dispatch_mode: str = "inline"  # inline | background


@dataclass
class StateRuntimeConfig:
    """Runtime state schema resolution configuration."""

    schema: str | None = None


@dataclass
class PipelineRuntimeConfig:
    """Runtime options loaded from YAML `runtime` section."""

    checkpointer: CheckpointerRuntimeConfig = field(default_factory=CheckpointerRuntimeConfig)
    invoker: InvokerRuntimeConfig = field(default_factory=InvokerRuntimeConfig)
    retrieval: RetrievalRuntimeConfig = field(default_factory=RetrievalRuntimeConfig)
    tracer: TracerRuntimeConfig = field(default_factory=TracerRuntimeConfig)
    state: StateRuntimeConfig = field(default_factory=StateRuntimeConfig)


@dataclass
class PipelineConfig:
    """Full pipeline configuration."""

    servers: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    pipeline: list[dict[str, Any]] = field(default_factory=list)
    runtime: PipelineRuntimeConfig = field(default_factory=PipelineRuntimeConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        """Load pipeline from YAML file."""
        path = Path(path) if isinstance(path, str) else path

        with path.open() as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("Pipeline YAML must be a mapping at top level")
        cls._validate(data)
        # Keep JSON Schema as a second validation layer for structural constraints
        # not covered by semantic checks (e.g. unknown top-level/runtime keys).
        validate_pipeline_schema(data)
        validate_pipeline_tool_contracts(data)

        config = cls()
        config.servers = data.get("servers", {})
        config.parameters = data.get("parameters", {})
        config.pipeline = data.get("pipeline", [])
        config.runtime = cls._parse_runtime(data.get("runtime", {}))

        logger.info(
            "pipeline_config_loaded",
            path=str(path),
            server_count=len(config.servers),
            step_count=len(config.pipeline),
        )

        return config

    @staticmethod
    def _validate(data: dict[str, Any]) -> None:
        """Validate top-level pipeline schema with strict structural checks."""
        servers = data.get("servers", {})
        parameters = data.get("parameters", {})
        pipeline = data.get("pipeline", [])
        runtime = data.get("runtime", {})
        if not isinstance(servers, dict):
            raise ValueError("`servers` must be a mapping")
        for server_name, server_value in servers.items():
            if not isinstance(server_name, str) or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                server_name,
            ):
                raise ValueError("`servers` keys must match `[A-Za-z_][A-Za-z0-9_]*`")
            if not isinstance(server_value, str) or not server_value.strip():
                raise ValueError("`servers` values must be non-empty strings")
        if not isinstance(parameters, dict):
            raise ValueError("`parameters` must be a mapping")
        if not isinstance(pipeline, list):
            raise ValueError("`pipeline` must be a list")
        if not pipeline:
            raise ValueError("`pipeline` must contain at least one step")
        if not isinstance(runtime, dict):
            raise ValueError("`runtime` must be a mapping")
        declared_servers = set(servers.keys())
        for step in pipeline:
            PipelineConfig._validate_step(step, declared_servers)
        PipelineConfig._validate_runtime(runtime)

    @staticmethod
    def _validate_runtime(runtime: dict[str, Any]) -> None:
        checkpointer = runtime.get("checkpointer", {})
        invoker = runtime.get("invoker", {})
        retrieval = runtime.get("retrieval", {})
        tracer = runtime.get("tracer", {})
        state = runtime.get("state", {})

        if not isinstance(checkpointer, dict):
            raise ValueError("`runtime.checkpointer` must be a mapping")
        if not isinstance(invoker, dict):
            raise ValueError("`runtime.invoker` must be a mapping")
        if not isinstance(retrieval, dict):
            raise ValueError("`runtime.retrieval` must be a mapping")
        if not isinstance(tracer, dict):
            raise ValueError("`runtime.tracer` must be a mapping")
        if not isinstance(state, dict):
            raise ValueError("`runtime.state` must be a mapping")

        kind = str(checkpointer.get("type", "none")).lower()
        if kind not in {"none", "memory"}:
            raise ValueError("`runtime.checkpointer.type` must be one of: none, memory")

        include_retrieval = invoker.get("include_retrieval", True)
        if not isinstance(include_retrieval, bool):
            raise ValueError("`runtime.invoker.include_retrieval` must be a boolean")

        default_backend = str(retrieval.get("default_backend", "lance")).lower()
        if default_backend not in {"lance", "hybrid"}:
            raise ValueError("`runtime.retrieval.default_backend` must be one of: lance, hybrid")

        dispatch_mode = str(tracer.get("callback_dispatch_mode", "inline")).lower()
        if dispatch_mode not in {"inline", "background"}:
            raise ValueError(
                "`runtime.tracer.callback_dispatch_mode` must be one of: inline, background"
            )

        schema = state.get("schema")
        if schema is not None and not isinstance(schema, str):
            raise ValueError("`runtime.state.schema` must be a string")

    @staticmethod
    def _parse_runtime(runtime: dict[str, Any]) -> PipelineRuntimeConfig:
        checkpointer = runtime.get("checkpointer", {})
        invoker = runtime.get("invoker", {})
        retrieval = runtime.get("retrieval", {})
        tracer = runtime.get("tracer", {})
        state = runtime.get("state", {})
        kind = str(checkpointer.get("type", "none")).lower()
        default_backend = str(retrieval.get("default_backend", "lance")).lower()
        dispatch_mode = str(tracer.get("callback_dispatch_mode", "inline")).lower()
        state_schema = state.get("schema")

        return PipelineRuntimeConfig(
            checkpointer=CheckpointerRuntimeConfig(type=kind),
            invoker=InvokerRuntimeConfig(
                include_retrieval=bool(invoker.get("include_retrieval", True))
            ),
            retrieval=RetrievalRuntimeConfig(default_backend=default_backend),
            tracer=TracerRuntimeConfig(callback_dispatch_mode=dispatch_mode),
            state=StateRuntimeConfig(
                schema=state_schema if isinstance(state_schema, str) else None
            ),
        )

    @staticmethod
    def _validate_step(step: Any, declared_servers: set[str]) -> None:
        """Validate a pipeline step recursively."""
        if isinstance(step, str):
            if "." not in step:
                raise ValueError(f"Step `{step}` must use `server.tool` format")
            PipelineConfig._validate_server_reference(step, declared_servers)
            return
        if not isinstance(step, dict) or len(step) != 1:
            raise ValueError("Step object must be a single-key mapping")

        key, value = next(iter(step.items()))
        if key == "loop":
            if not isinstance(value, dict):
                raise ValueError("`loop` must be a mapping")
            max_iterations = value.get("max_iterations", 3)
            if not isinstance(max_iterations, int) or max_iterations < 1:
                raise ValueError("`loop.max_iterations` must be an integer >= 1")
            steps = value.get("steps", [])
            if not isinstance(steps, list):
                raise ValueError("`loop.steps` must be a list")
            if not steps:
                raise ValueError("`loop.steps` must contain at least one step")
            for child in steps:
                PipelineConfig._validate_step(child, declared_servers)
            return

        if key == "branch":
            if not isinstance(value, dict):
                raise ValueError("`branch` must be a mapping")
            router = value.get("router", "default_router")
            if not isinstance(router, str) or not router.strip():
                raise ValueError("`branch.router` must be a non-empty string")
            if "." in router:
                server, tool = router.split(".", 1)
                if not server or not tool:
                    raise ValueError(
                        "`branch.router` in `server.tool` format requires both server and tool"
                    )
                PipelineConfig._validate_server_reference(router, declared_servers)
            field = value.get("field", "route")
            if not isinstance(field, str) or not field.strip():
                raise ValueError("`branch.field` must be a non-empty string")
            branches = value.get("branches", {})
            if not isinstance(branches, dict):
                raise ValueError("`branch.branches` must be a mapping")
            if not branches:
                raise ValueError("`branch.branches` must define at least one branch")
            for branch_name, branch_steps in branches.items():
                if not isinstance(branch_name, str) or not branch_name.strip():
                    raise ValueError("`branch.branches` keys must be non-empty strings")
                if not isinstance(branch_steps, list):
                    raise ValueError("Each branch value must be a list of steps")
                if not branch_steps:
                    raise ValueError(
                        f"`branch.branches.{branch_name}` must contain at least one step"
                    )
                for child in branch_steps:
                    PipelineConfig._validate_step(child, declared_servers)

            value_map = value.get("value_map", {})
            if not isinstance(value_map, dict):
                raise ValueError("`branch.value_map` must be a mapping")
            branch_names = set(branches.keys())
            token_to_branch: dict[str, str] = {}
            for mapped_branch, mapped_values in value_map.items():
                if mapped_branch not in branch_names:
                    valid = ", ".join(sorted(branch_names)) or "<none>"
                    raise ValueError(
                        f"`branch.value_map` key `{mapped_branch}` is not a declared branch; "
                        f"valid branches: {valid}"
                    )
                if not isinstance(mapped_values, list) or any(
                    not isinstance(item, str) or not item for item in mapped_values
                ):
                    raise ValueError("`branch.value_map` values must be lists of non-empty strings")
                if len(set(mapped_values)) != len(mapped_values):
                    raise ValueError(
                        f"`branch.value_map` branch `{mapped_branch}` contains duplicate routing tokens"
                    )
                for token in mapped_values:
                    previous_branch = token_to_branch.get(token)
                    if previous_branch and previous_branch != mapped_branch:
                        raise ValueError(
                            f"`branch.value_map` token `{token}` maps to multiple branches: "
                            f"`{previous_branch}` and `{mapped_branch}`"
                        )
                    token_to_branch[token] = mapped_branch
            return

        if "." not in key:
            raise ValueError(f"Unknown step type `{key}`")
        PipelineConfig._validate_server_reference(key, declared_servers)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"Step `{key}` config must be a mapping")
        if isinstance(value, dict):
            PipelineConfig._validate_step_config(key, value)

    @staticmethod
    def _validate_step_config(step_name: str, config: dict[str, Any]) -> None:
        """Validate per-step config schema for tool steps."""
        allowed_keys = {"input", "output"}
        unknown = set(config.keys()) - allowed_keys
        if unknown:
            unknown_list = ", ".join(sorted(unknown))
            raise ValueError(
                f"Step `{step_name}` contains unsupported config keys: {unknown_list}; "
                "only `input` and `output` are allowed"
            )

        input_mapping = config.get("input", {})
        if not isinstance(input_mapping, dict):
            raise ValueError(f"Step `{step_name}` field `input` must be a mapping")

        output_mapping = config.get("output", [])
        if not isinstance(output_mapping, list) or any(
            not isinstance(item, str) or not item for item in output_mapping
        ):
            raise ValueError(
                f"Step `{step_name}` field `output` must be a list of non-empty strings"
            )

    @staticmethod
    def _validate_server_reference(step_name: str, declared_servers: set[str]) -> None:
        """
        Validate `server.tool` server namespace.

        Rules:
        - If no servers are declared, allow implicit server namespaces.
        - If servers are declared, every `server.tool` must reference a declared server.
        """
        if not declared_servers:
            return
        server, _ = step_name.split(".", 1)
        if server not in declared_servers:
            valid = ", ".join(sorted(declared_servers))
            raise ValueError(
                f"Unknown server `{server}` in step `{step_name}`; "
                f"declare it under `servers` (valid: {valid})"
            )


__all__ = [
    "PipelineState",
    "Segment",
    "StepConfig",
    "LoopConfig",
    "BranchConfig",
    "CheckpointerRuntimeConfig",
    "InvokerRuntimeConfig",
    "RetrievalRuntimeConfig",
    "TracerRuntimeConfig",
    "StateRuntimeConfig",
    "PipelineRuntimeConfig",
    "PipelineConfig",
]
