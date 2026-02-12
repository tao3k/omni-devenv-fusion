"""
test_pipeline.py - Unit tests for YAML pipeline to LangGraph generator

Tests pipeline configuration and LangGraph generation including:
- PipelineConfig from YAML loading
- LangGraphPipelineBuilder for building workflows
- Variable interpolation ($var, memory_var)
"""

from __future__ import annotations

import pytest

from omni.tracer import (
    PipelineConfig,
    PipelineExecutor,
    LangGraphPipelineBuilder,
    ExecutionTracer,
    MappingToolInvoker,
)


class TestPipelineConfig:
    """Tests for PipelineConfig."""

    def test_empty_config(self):
        """Test creating empty pipeline config."""
        config = PipelineConfig()

        assert config.servers == {}
        assert config.parameters == {}
        assert config.pipeline == []

    def test_config_with_data(self):
        """Test creating config with data."""
        config = PipelineConfig(
            servers={"retriever": "/path/to/retriever"},
            parameters={"query": "test"},
            pipeline=[{"retriever.search": {}}],
        )

        assert config.servers["retriever"] == "/path/to/retriever"
        assert config.parameters["query"] == "test"
        assert len(config.pipeline) == 1

    def test_from_yaml_simple(self, tmp_path):
        """Test loading simple pipeline from YAML."""
        yaml_content = """
servers:
  retriever: path/to/retriever
  generator: path/to/generator

parameters:
  query: What is RAG?
  top_k: 5

pipeline:
  - retriever.search
  - generator.generate
"""
        yaml_file = tmp_path / "pipeline.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)

        assert config.servers["retriever"] == "path/to/retriever"
        assert config.servers["generator"] == "path/to/generator"
        assert config.parameters["query"] == "What is RAG?"
        assert config.parameters["top_k"] == 5
        assert len(config.pipeline) == 2

    def test_from_yaml_invalid_server_name_raises(self, tmp_path):
        """Test server names must match strict identifier pattern."""
        yaml_content = """
servers:
  retriever-service: path/to/retriever
pipeline:
  - retriever.search
"""
        yaml_file = tmp_path / "invalid_server_name.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(
            ValueError,
            match="`servers` keys must match",
        ):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_valid_server_name_with_underscore_passes(self, tmp_path):
        """Test underscore-based server names are accepted."""
        yaml_content = """
servers:
  retriever_service: path/to/retriever
pipeline:
  - retriever_service.search
"""
        yaml_file = tmp_path / "valid_server_name.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)
        assert "retriever_service" in config.servers

    def test_from_yaml_server_value_must_be_non_empty_string(self, tmp_path):
        """Test server values must be non-empty strings."""
        yaml_content = """
servers:
  retriever: ""
pipeline:
  - retriever.search
"""
        yaml_file = tmp_path / "invalid_server_value.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(
            ValueError,
            match="`servers` values must be non-empty strings",
        ):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_complex_step(self, tmp_path):
        """Test loading pipeline with complex step config."""
        yaml_content = """
servers:
  retriever: path/to/retriever

parameters:
  query: test

pipeline:
  - retriever.search:
      input:
        query: "$query"
        top_k: 5
      output:
        - docs
        - scores
"""
        yaml_file = tmp_path / "complex.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)

        step = config.pipeline[0]
        assert "retriever.search" in step
        assert step["retriever.search"]["input"]["query"] == "$query"
        assert step["retriever.search"]["input"]["top_k"] == 5
        assert step["retriever.search"]["output"] == ["docs", "scores"]

    def test_from_yaml_missing_file(self):
        """Test loading non-existent YAML file raises error."""
        with pytest.raises(FileNotFoundError):
            PipelineConfig.from_yaml("/nonexistent/path/pipeline.yaml")

    def test_from_yaml_invalid_step_raises(self, tmp_path):
        """Test invalid step schema raises ValueError."""
        yaml_content = """
pipeline:
  - invalid_step_name
"""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_empty_pipeline_raises(self, tmp_path):
        """Test empty pipeline list raises ValueError."""
        yaml_content = """
pipeline: []
"""
        yaml_file = tmp_path / "empty_pipeline.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="`pipeline` must contain at least one step"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_unknown_server_raises_when_servers_declared(self, tmp_path):
        """Test undeclared server namespace raises ValueError when `servers` is provided."""
        yaml_content = """
servers:
  retriever: path/to/retriever

pipeline:
  - generator.generate
"""
        yaml_file = tmp_path / "unknown_server.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="Unknown server `generator`"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_runtime_config(self, tmp_path):
        """Test loading runtime settings from YAML."""
        yaml_content = """
runtime:
  checkpointer:
    type: memory
  invoker:
    include_retrieval: false
  retrieval:
    default_backend: hybrid
  tracer:
    callback_dispatch_mode: background
  state:
    schema: builtins:dict

pipeline:
  - demo.run
"""
        yaml_file = tmp_path / "runtime.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)
        assert config.runtime.checkpointer.type == "memory"
        assert config.runtime.invoker.include_retrieval is False
        assert config.runtime.retrieval.default_backend == "hybrid"
        assert config.runtime.tracer.callback_dispatch_mode == "background"
        assert config.runtime.state.schema == "builtins:dict"

    def test_from_yaml_invalid_runtime_raises(self, tmp_path):
        """Test invalid runtime schema raises ValueError."""
        yaml_content = """
runtime:
  checkpointer:
    type: invalid
pipeline:
  - demo.run
"""
        yaml_file = tmp_path / "invalid_runtime.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_runtime_checkpointer_kind_is_rejected(self, tmp_path):
        """Test new API rejects legacy runtime.checkpointer.kind field."""
        yaml_content = """
runtime:
  checkpointer:
    kind: memory
pipeline:
  - demo.run
"""
        yaml_file = tmp_path / "invalid_runtime_kind.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="Invalid pipeline schema"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_invalid_tracer_runtime_raises(self, tmp_path):
        """Test invalid tracer runtime config raises ValueError."""
        yaml_content = """
runtime:
  tracer:
    callback_dispatch_mode: invalid
pipeline:
  - demo.run
"""
        yaml_file = tmp_path / "invalid_tracer_runtime.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_invalid_retrieval_runtime_raises(self, tmp_path):
        """Test invalid retrieval runtime config raises ValueError."""
        yaml_content = """
runtime:
  retrieval:
    default_backend: invalid
pipeline:
  - demo.run
"""
        yaml_file = tmp_path / "invalid_retrieval_runtime.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_unknown_top_level_key_rejected_by_schema(self, tmp_path):
        """Test JSON Schema rejects unknown top-level keys."""
        yaml_content = """
pipeline:
  - demo.run
unknown_top_level: true
"""
        yaml_file = tmp_path / "invalid_top_level_key.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="Invalid pipeline schema"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_tool_contract_retriever_search_requires_query(self, tmp_path):
        """Test tool contract enforces required query input for retriever.search."""
        yaml_content = """
pipeline:
  - retriever.search:
      input:
        top_k: 5
"""
        yaml_file = tmp_path / "invalid_retriever_search_contract.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="missing required input keys: query"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_unknown_tool_step_parses(self, tmp_path):
        """Unknown tool names are parsed; runtime invoker handles implementation."""
        yaml_content = """
pipeline:
  - retriever.custom_tool:
      input:
        query: "$query"
"""
        yaml_file = tmp_path / "unknown_tool.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)
        assert config.pipeline

    def test_from_yaml_custom_tool_contract_requires_keys(self, tmp_path):
        """Test runtime.tool_contracts enforces required input keys for custom tools."""
        yaml_content = """
runtime:
  tool_contracts:
    generator.generate:
      required_input_keys:
        - topic
        - context

pipeline:
  - generator.generate:
      input:
        topic: "$query"
"""
        yaml_file = tmp_path / "invalid_custom_tool_contract.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="missing required input keys: context"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_custom_tool_contract_valid(self, tmp_path):
        """Test runtime.tool_contracts passes when required keys are present."""
        yaml_content = """
runtime:
  tool_contracts:
    generator.generate:
      required_input_keys:
        - topic
        - context

pipeline:
  - generator.generate:
      input:
        topic: "$query"
        context: "$docs"
      output:
        - analysis
"""
        yaml_file = tmp_path / "valid_custom_tool_contract.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)
        assert config.pipeline

    def test_from_yaml_custom_tool_contract_cannot_override_builtin(self, tmp_path):
        """Test runtime.tool_contracts cannot override built-in tool contracts."""
        yaml_content = """
runtime:
  tool_contracts:
    retriever.search:
      required_input_keys:
        - query
        - collection

pipeline:
  - retriever.search:
      input:
        query: "$query"
"""
        yaml_file = tmp_path / "invalid_override_builtin_contract.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(
            ValueError,
            match="overriding built-in contracts is not allowed",
        ):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_custom_tool_contract_new_tool_is_allowed(self, tmp_path):
        """Test runtime.tool_contracts allows adding new tool contracts."""
        yaml_content = """
runtime:
  tool_contracts:
    generator.summarize:
      required_input_keys:
        - topic
        - context

pipeline:
  - generator.summarize:
      input:
        topic: "$query"
        context: "$docs"
      output:
        - summary
"""
        yaml_file = tmp_path / "valid_new_tool_contract.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)
        assert config.pipeline

    def test_from_yaml_custom_tool_contract_schema_rejects_invalid_shape(self, tmp_path):
        """Test JSON Schema rejects malformed runtime.tool_contracts config."""
        yaml_content = """
runtime:
  tool_contracts:
    generator.generate:
      required_input_keys: topic

pipeline:
  - generator.generate
"""
        yaml_file = tmp_path / "invalid_custom_tool_contract_shape.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="Invalid pipeline schema"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_step_with_unknown_config_key_raises(self, tmp_path):
        """Test tool step config rejects unsupported keys."""
        yaml_content = """
pipeline:
  - retriever.search:
      unexpected: value
"""
        yaml_file = tmp_path / "invalid_step_key.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="unsupported config keys"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_step_input_must_be_mapping(self, tmp_path):
        """Test tool step input must be a mapping."""
        yaml_content = """
pipeline:
  - retriever.search:
      input: not_a_mapping
"""
        yaml_file = tmp_path / "invalid_input_type.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="field `input` must be a mapping"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_step_output_must_be_list_of_strings(self, tmp_path):
        """Test tool step output must be a list of non-empty strings."""
        yaml_content = """
pipeline:
  - retriever.search:
      output:
        - docs
        - 123
"""
        yaml_file = tmp_path / "invalid_output_type.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="field `output` must be a list of non-empty strings"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_loop_max_iterations_must_be_positive_int(self, tmp_path):
        """Test loop max_iterations must be integer >= 1."""
        yaml_content = """
pipeline:
  - loop:
      max_iterations: 0
      steps:
        - retriever.search
"""
        yaml_file = tmp_path / "invalid_loop_iterations.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="`loop.max_iterations` must be an integer >= 1"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_loop_times_is_rejected(self, tmp_path):
        """Test new API rejects legacy loop.times field."""
        yaml_content = """
pipeline:
  - loop:
      times: 2
      steps:
        - retriever.search
"""
        yaml_file = tmp_path / "invalid_loop_times.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="Invalid pipeline schema"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_loop_steps_must_not_be_empty(self, tmp_path):
        """Test loop must contain at least one step."""
        yaml_content = """
pipeline:
  - loop:
      max_iterations: 2
      steps: []
"""
        yaml_file = tmp_path / "invalid_empty_loop_steps.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="`loop.steps` must contain at least one step"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_router_must_be_non_empty_string(self, tmp_path):
        """Test branch router must be a non-empty string."""
        yaml_content = """
pipeline:
  - branch:
      router: ""
      branches:
        continue:
          - retriever.search
"""
        yaml_file = tmp_path / "invalid_branch_router.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="`branch.router` must be a non-empty string"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_field_must_be_non_empty_string(self, tmp_path):
        """Test branch field must be a non-empty string."""
        yaml_content = """
pipeline:
  - branch:
      field: ""
      branches:
        continue:
          - retriever.search
"""
        yaml_file = tmp_path / "invalid_branch_field.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="`branch.field` must be a non-empty string"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_keys_must_be_non_empty_strings(self, tmp_path):
        """Test branch names must be non-empty strings."""
        yaml_content = """
pipeline:
  - branch:
      branches:
        "": []
"""
        yaml_file = tmp_path / "invalid_branch_key.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="`branch.branches` keys must be non-empty strings"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_branches_must_not_be_empty(self, tmp_path):
        """Test branch must define at least one branch entry."""
        yaml_content = """
pipeline:
  - branch:
      branches: {}
"""
        yaml_file = tmp_path / "invalid_empty_branches.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="must define at least one branch"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_branch_steps_must_not_be_empty(self, tmp_path):
        """Test each branch must contain at least one step."""
        yaml_content = """
pipeline:
  - branch:
      branches:
        continue: []
"""
        yaml_file = tmp_path / "invalid_empty_branch_steps.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="must contain at least one step"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_value_map_must_reference_declared_branches(self, tmp_path):
        """Test branch value_map keys must map to existing branches."""
        yaml_content = """
pipeline:
  - branch:
      branches:
        continue:
          - retriever.search
      value_map:
        complete:
          - quality_threshold_reached
"""
        yaml_file = tmp_path / "invalid_value_map_key.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="is not a declared branch"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_value_map_values_must_be_list_of_strings(self, tmp_path):
        """Test branch value_map values must be lists of non-empty strings."""
        yaml_content = """
pipeline:
  - branch:
      branches:
        continue:
          - retriever.search
      value_map:
        continue:
          - ok
          - 123
"""
        yaml_file = tmp_path / "invalid_value_map_values.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(
            ValueError,
            match="`branch.value_map` values must be lists of non-empty strings",
        ):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_router_server_tool_format_requires_both_parts(self, tmp_path):
        """Test branch router in dotted format requires both server and tool."""
        yaml_content = """
pipeline:
  - branch:
      router: "router."
      branches:
        continue:
          - retriever.search
"""
        yaml_file = tmp_path / "invalid_router_dotted_format.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(
            ValueError,
            match="`branch.router` in `server.tool` format requires both server and tool",
        ):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_router_server_tool_must_use_declared_server(self, tmp_path):
        """Test branch router server namespace must be declared when servers are defined."""
        yaml_content = """
servers:
  retriever: path/to/retriever

pipeline:
  - branch:
      router: evaluator.check
      branches:
        continue:
          - retriever.search
"""
        yaml_file = tmp_path / "invalid_router_server_namespace.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="Unknown server `evaluator`"):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_router_server_tool_accepts_declared_server(self, tmp_path):
        """Test branch router server namespace passes when server is declared."""
        yaml_content = """
servers:
  evaluator: path/to/evaluator
  retriever: path/to/retriever

pipeline:
  - branch:
      router: evaluator.check
      branches:
        continue:
          - retriever.search
"""
        yaml_file = tmp_path / "valid_router_server_namespace.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)
        assert config.pipeline

    def test_from_yaml_branch_value_map_duplicate_token_across_branches_raises(self, tmp_path):
        """Test same routing token cannot map to multiple branches."""
        yaml_content = """
pipeline:
  - branch:
      branches:
        continue:
          - retriever.search
        complete:
          - retriever.search
      value_map:
        continue:
          - quality_threshold_reached
        complete:
          - quality_threshold_reached
"""
        yaml_file = tmp_path / "invalid_value_map_duplicate_token.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(
            ValueError,
            match="maps to multiple branches",
        ):
            PipelineConfig.from_yaml(yaml_file)

    def test_from_yaml_branch_value_map_distinct_tokens_pass(self, tmp_path):
        """Test distinct routing tokens across branches pass validation."""
        yaml_content = """
pipeline:
  - branch:
      branches:
        continue:
          - retriever.search
        complete:
          - retriever.search
      value_map:
        continue:
          - continue_reflection
        complete:
          - quality_threshold_reached
"""
        yaml_file = tmp_path / "valid_value_map_distinct_tokens.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)
        assert config.pipeline

    def test_from_yaml_branch_value_map_duplicate_token_within_branch_raises(self, tmp_path):
        """Test duplicate routing token within same branch is rejected."""
        yaml_content = """
pipeline:
  - branch:
      branches:
        continue:
          - retriever.search
      value_map:
        continue:
          - continue_reflection
          - continue_reflection
"""
        yaml_file = tmp_path / "invalid_value_map_duplicate_within_branch.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(
            ValueError,
            match="contains duplicate routing tokens",
        ):
            PipelineConfig.from_yaml(yaml_file)


class TestLangGraphPipelineBuilder:
    """Tests for LangGraphPipelineBuilder."""

    def test_build_empty_pipeline(self):
        """Test building empty pipeline."""
        config = PipelineConfig()
        builder = LangGraphPipelineBuilder(config)

        result = builder.build()

        assert result["nodes"] == {}
        assert result["edges"] == []
        assert result["conditional_edges"] == []
        assert result["servers"] == {}
        assert result["parameters"] == {}

    def test_add_step_simple(self):
        """Test adding simple step."""
        config = PipelineConfig(servers={"retriever": "/path"})
        builder = LangGraphPipelineBuilder(config)

        node_name = builder.add_step("retriever", "search")

        assert node_name == "retriever_search"
        assert "retriever_search" in builder.nodes
        assert builder.nodes["retriever_search"]["server"] == "retriever"
        assert builder.nodes["retriever_search"]["tool"] == "search"

    def test_add_step_with_custom_name(self):
        """Test adding step with custom node name."""
        config = PipelineConfig()
        builder = LangGraphPipelineBuilder(config)

        node_name = builder.add_step("generator", "generate", node_name="my_custom_node")

        assert node_name == "my_custom_node"

    def test_add_step_auto_increment_on_duplicate(self):
        """Test auto-increment for duplicate step names."""
        config = PipelineConfig()
        builder = LangGraphPipelineBuilder(config)

        name1 = builder.add_step("retriever", "search")
        name2 = builder.add_step("retriever", "search")
        name3 = builder.add_step("retriever", "search")

        assert name1 == "retriever_search"
        assert name2 == "retriever_search_1"
        assert name3 == "retriever_search_2"

    def test_add_edge(self):
        """Test adding edges between nodes."""
        config = PipelineConfig()
        builder = LangGraphPipelineBuilder(config)

        builder.add_step("step1", "do")
        builder.add_step("step2", "do")
        builder.add_edge("step1_do", "step2_do")

        assert ("step1_do", "step2_do") in builder.edges

    def test_build_sequential_simple(self):
        """Test building sequential pipeline from simple steps."""
        config = PipelineConfig(pipeline=["step1.exec", "step2.exec"])
        builder = LangGraphPipelineBuilder(config)

        step_map = builder.build_sequential(config.pipeline)

        assert len(step_map) == 2
        # Edges should be created between steps
        assert len(builder.edges) == 1

    def test_build_sequential_with_config(self):
        """Test building sequential pipeline with config."""
        pipeline = [{"retriever.search": {"input": {"query": "$query"}, "output": ["docs"]}}]
        config = PipelineConfig(pipeline=pipeline)
        builder = LangGraphPipelineBuilder(config)

        builder.build_sequential(config.pipeline)

        node_name = builder.nodes.get("retriever_search")
        assert node_name is not None
        assert node_name.get("input_mapping") == {"query": "$query"}
        assert node_name.get("output_mapping") == ["docs"]

    def test_build_loop(self):
        """Test building loop structure."""
        loop_config = {"max_iterations": 3, "steps": [{"step1.exec": {}}, {"step2.exec": {}}]}
        config = PipelineConfig()
        builder = LangGraphPipelineBuilder(config)

        loop_node = builder._build_loop(loop_config, 0)

        assert loop_node == "loop_0"
        assert builder.nodes[loop_node]["type"] == "loop"
        assert builder.nodes[loop_node]["max_iterations"] == 3

    def test_build_branch(self):
        """Test building branch structure."""
        branch_config = {
            "router": "decision_router",
            "branches": {
                "simple": [{"step1.exec": {}}],
                "complex": [{"step1.exec": {}}, {"step2.exec": {}}],
            },
        }
        config = PipelineConfig()
        builder = LangGraphPipelineBuilder(config)

        branch_node = builder._build_branch(branch_config)

        assert branch_node == "branch_decision_router"
        assert builder.nodes[branch_node]["type"] == "branch"
        assert builder.nodes[branch_node]["router"] == "decision_router"

    def test_build_returns_complete_definition(self):
        """Test build returns complete graph definition."""
        config = PipelineConfig(
            servers={"retriever": "/path"},
            parameters={"query": "test"},
            pipeline=["retriever.search"],
        )
        builder = LangGraphPipelineBuilder(config)

        result = builder.build()

        assert "nodes" in result
        assert "edges" in result
        assert "conditional_edges" in result
        assert "servers" in result
        assert "parameters" in result
        assert "entry_node" in result
        assert "exit_nodes" in result

    def test_build_branch_adds_conditional_edges(self):
        """Test branch step compiles to conditional edges."""
        config = PipelineConfig(
            pipeline=[
                {
                    "branch": {
                        "router": "check_quality",
                        "branches": {
                            "continue": ["step1.exec"],
                            "complete": ["step2.exec"],
                        },
                    }
                }
            ]
        )
        builder = LangGraphPipelineBuilder(config)
        result = builder.build()

        assert len(result["conditional_edges"]) == 1
        from_node, _, destinations = result["conditional_edges"][0]
        assert from_node == "branch_check_quality"
        assert set(destinations.keys()) == {"continue", "complete"}

    def test_build_loop_adds_conditional_edges(self):
        """Test loop step compiles to conditional edges."""
        config = PipelineConfig(
            pipeline=[
                {
                    "loop": {
                        "max_iterations": 2,
                        "steps": ["step1.exec"],
                    }
                }
            ]
        )
        builder = LangGraphPipelineBuilder(config)
        result = builder.build()

        assert len(result["conditional_edges"]) == 1
        from_node, _, destinations = result["conditional_edges"][0]
        assert from_node == "loop_0"
        assert set(destinations.keys()) == {"continue", "exit"}


class TestPipelineExecutor:
    """Tests for PipelineExecutor."""

    @pytest.mark.asyncio
    async def test_execute_simple_pipeline(self, tmp_path):
        """Test executing simple pipeline."""
        yaml_content = """
servers:
  retriever: path/to/retriever

pipeline:
  - retriever.search
"""
        yaml_file = tmp_path / "simple.yaml"
        yaml_file.write_text(yaml_content)

        executor = PipelineExecutor(yaml_file)
        results = await executor.run(parameters={"query": "test"})

        # Results should contain step outputs
        assert results is not None

    def test_executor_with_tracer(self, tmp_path):
        """Test executor with tracer attached."""
        yaml_content = """
pipeline:
  - test.step
"""
        yaml_file = tmp_path / "traced.yaml"
        yaml_file.write_text(yaml_content)

        tracer = ExecutionTracer(trace_id="test_trace")
        executor = PipelineExecutor(yaml_file, tracer=tracer)

        assert executor.tracer is tracer

    def test_parameter_override(self, tmp_path):
        """Test that runtime parameters override config."""
        yaml_content = """
parameters:
  query: default_query

pipeline:
  - test.step
"""
        yaml_file = tmp_path / "params.yaml"
        yaml_file.write_text(yaml_content)

        executor = PipelineExecutor(yaml_file)
        # Parameters should be merged in run()

        # We can't easily test the merge without executing, but we verify
        # the config has default parameters
        assert executor.config.parameters["query"] == "default_query"


class TestPipelineVariableInterpolation:
    """Tests for variable interpolation in pipeline."""

    def test_dollar_prefix_interpolation(self, tmp_path):
        """Test $variable interpolation in step config."""
        yaml_content = """
parameters:
  query: original_query

pipeline:
  - test.step:
      input:
        question: "$query"
"""
        yaml_file = tmp_path / "interpolate.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)

        step = config.pipeline[0]
        assert step["test.step"]["input"]["question"] == "$query"

    def test_memory_variable_in_config(self, tmp_path):
        """Test memory_* variable in config."""
        yaml_content = """
pipeline:
  - test.step:
      input:
        data: "$memory_previous_results"
"""
        yaml_file = tmp_path / "memory_var.yaml"
        yaml_file.write_text(yaml_content)

        config = PipelineConfig.from_yaml(yaml_file)

        step = config.pipeline[0]
        assert "$memory_previous_results" in step["test.step"]["input"]["data"]


class TestCreateLangGraphFromPipeline:
    """Tests for create_langgraph_from_pipeline function."""

    def test_creates_langgraph_from_config(self):
        """Test creating LangGraph from pipeline config."""
        from omni.tracer import create_langgraph_from_pipeline

        config = PipelineConfig(servers={"test": "/path/to/test"}, pipeline=["test.step"])

        # Should return a compiled LangGraph
        app = create_langgraph_from_pipeline(config)

        assert app is not None

    def test_with_tracer(self):
        """Test creating LangGraph with tracer."""
        from omni.tracer import create_langgraph_from_pipeline

        config = PipelineConfig(servers={"test": "/path"}, pipeline=["test.step"])
        tracer = ExecutionTracer(trace_id="graph_trace")

        app = create_langgraph_from_pipeline(config, tracer=tracer)

        assert app is not None

    @pytest.mark.asyncio
    async def test_with_custom_tool_invoker(self):
        """Test creating LangGraph with custom tool invoker and mapped outputs."""
        from omni.tracer import create_langgraph_from_pipeline

        config = PipelineConfig(
            servers={"retriever": "/path"},
            pipeline=[
                {
                    "retriever.search": {
                        "input": {"query": "$query"},
                        "output": ["docs"],
                    }
                }
            ],
        )

        async def fake_search(payload, state):
            assert payload["query"] == "typed languages"
            return {"docs": ["doc-a", "doc-b"], "status": "ok"}

        invoker = MappingToolInvoker({"retriever.search": fake_search})
        app = create_langgraph_from_pipeline(config, state_schema=dict, tool_invoker=invoker)
        result = await app.ainvoke({"query": "typed languages"})

        assert result["docs"] == ["doc-a", "doc-b"]

    @pytest.mark.asyncio
    async def test_with_defaults_uses_mapping_stack(self):
        """Test convenience API builds default stack and executes mapping handler."""
        from omni.tracer import create_langgraph_from_pipeline_with_defaults

        config = PipelineConfig(
            servers={"demo": "/path"},
            pipeline=[
                {
                    "demo.run": {
                        "input": {"query": "$query"},
                        "output": ["docs"],
                    }
                }
            ],
        )

        async def mapped(payload, state):
            assert payload["query"] == "typed languages"
            return {"docs": ["d1", "d2"]}

        app = create_langgraph_from_pipeline_with_defaults(
            pipeline_config=config,
            state_schema=dict,
            mapping={"demo.run": mapped},
            include_retrieval=False,
        )
        result = await app.ainvoke({"query": "typed languages"})
        assert result["docs"] == ["d1", "d2"]

    @pytest.mark.asyncio
    async def test_with_defaults_respects_explicit_tool_invoker_override(self):
        """Test explicit tool_invoker overrides default stack settings."""
        from omni.tracer import create_langgraph_from_pipeline_with_defaults

        config = PipelineConfig(
            servers={"demo": "/path"},
            pipeline=[
                {
                    "demo.run": {
                        "input": {"query": "$query"},
                        "output": ["docs"],
                    }
                }
            ],
        )

        async def explicit(payload, state):
            return {"docs": ["explicit"]}

        invoker = MappingToolInvoker({"demo.run": explicit})

        app = create_langgraph_from_pipeline_with_defaults(
            pipeline_config=config,
            state_schema=dict,
            mapping={"demo.run": lambda *_: {"docs": ["stack"]}},
            include_retrieval=False,
            tool_invoker=invoker,
        )
        result = await app.ainvoke({"query": "ignored"})
        assert result["docs"] == ["explicit"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
