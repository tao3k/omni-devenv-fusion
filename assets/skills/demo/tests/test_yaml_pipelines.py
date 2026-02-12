# =============================================================================
# YAML Pipeline Integration Tests
# =============================================================================
"""
Integration tests for YAML pipeline compilation and execution.

Run with:
    uv run pytest -k yaml_pipelines -v
"""

import pytest
from omni.foundation.config.skills import SKILLS_DIR
from omni.test_kit.fixtures.files import temp_yaml_file

PIPELINE_TYPES = ("simple", "loop", "branch", "rag")


class TestYAMLPipelineFiles:
    """Test YAML pipeline files exist and are valid."""

    @pytest.fixture
    def pipelines_dir(self):
        """Get pipelines directory."""
        return SKILLS_DIR(skill="demo", path="pipelines")

    @pytest.mark.parametrize("pipeline_type", PIPELINE_TYPES)
    def test_yaml_exists(self, pipelines_dir, pipeline_type):
        """Pipeline file exists."""
        assert (pipelines_dir / f"{pipeline_type}.yaml").exists()


class TestYAMLPipelineParsing:
    """Test YAML pipeline parsing and configuration."""

    @staticmethod
    def _pipeline_path(pipeline_type: str):
        return SKILLS_DIR(skill="demo", path=f"pipelines/{pipeline_type}.yaml")

    @pytest.mark.parametrize("pipeline_type", PIPELINE_TYPES)
    def test_parse_pipeline(self, pipeline_type):
        """Parse pipeline."""
        from omni.tracer import load_pipeline

        config = load_pipeline(self._pipeline_path(pipeline_type))
        assert len(config.pipeline) >= 2
        assert config.runtime.checkpointer.type == "memory"
        if pipeline_type == "rag":
            assert config.runtime.invoker.include_retrieval is True


class TestYAMLPipelineCompilation:
    """Test YAML pipeline compilation with NoOpToolInvoker."""

    @pytest.fixture
    def tracer(self):
        """Create tracer for tests."""
        from omni.tracer import ExecutionTracer

        return ExecutionTracer(trace_id="test_compile")

    @pytest.mark.parametrize("pipeline_type", PIPELINE_TYPES)
    def test_compile_pipeline(self, tracer, pipeline_type):
        """Compile pipeline."""
        from omni.tracer import create_langgraph_from_yaml, NoOpToolInvoker

        graph = create_langgraph_from_yaml(
            str(SKILLS_DIR(skill="demo", path=f"pipelines/{pipeline_type}.yaml")),
            tracer=tracer,
            tool_invoker=NoOpToolInvoker(),
        )
        assert graph is not None


class TestYAMLPipelineRuntimeConfig:
    """Test runtime configuration from YAML."""

    def test_runtime_checkpointer_kind(self):
        """Test checkpointer kind from YAML."""
        from omni.tracer import load_pipeline

        config = load_pipeline(SKILLS_DIR(skill="demo", path="pipelines/simple.yaml"))
        assert config.runtime.checkpointer.type == "memory"

    def test_runtime_callback_mode(self):
        """Test callback dispatch mode from YAML."""
        from omni.tracer import load_pipeline

        config = load_pipeline(SKILLS_DIR(skill="demo", path="pipelines/simple.yaml"))
        assert config.runtime.tracer.callback_dispatch_mode == "inline"

    def test_runtime_retrieval_flag(self):
        """Test retrieval inclusion flag from YAML."""
        from omni.tracer import load_pipeline

        config = load_pipeline(SKILLS_DIR(skill="demo", path="pipelines/rag.yaml"))
        assert config.runtime.invoker.include_retrieval is True


class TestPipelineValidation:
    """Test YAML configuration validation."""

    def test_invalid_pipeline_structure(self, temp_yaml_file):
        """Invalid pipeline structure raises error."""
        from omni.tracer import load_pipeline

        yaml_path = temp_yaml_file("invalid_structure.yaml", "pipeline: invalid_not_list")
        with pytest.raises(ValueError):
            load_pipeline(str(yaml_path))

    def test_invalid_step_format(self, temp_yaml_file):
        """Invalid step format raises error."""
        from omni.tracer import load_pipeline

        yaml_path = temp_yaml_file("invalid_step.yaml", "pipeline:\n  - no_server_dot_tool")
        with pytest.raises(ValueError):
            load_pipeline(str(yaml_path))


# =============================================================================
# Real Execution Tests (Requires LLM)
# =============================================================================


class TestRealExecution:
    """Test real LLM execution via demo.run_langgraph command."""

    @pytest.mark.parametrize(
        ("scenario", "min_steps"),
        [("simple", 3), ("complex", 6)],
    )
    def test_run_scenario(self, scenario, min_steps):
        """Run real graphflow scenario through demo skill wrapper."""
        from omni.test_kit.skill import SkillCommandTester

        result = SkillCommandTester().run(
            "demo",
            "scripts.tracer",
            "run_langgraph",
            scenario=scenario,
        )

        assert result["status"] == "success"
        assert result["scenario"] == scenario
        assert result.get("trace", {}).get("step_count", 0) >= min_steps
        assert "memory_pool" in result
        memory = result.get("memory_pool", {})
        assert "reflection_labels" in memory or len(memory) > 0


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_config():
    """Simple pipeline config."""
    from omni.tracer import load_pipeline

    return load_pipeline(SKILLS_DIR(skill="demo", path="pipelines/simple.yaml"))


@pytest.fixture
def loop_config():
    """Loop pipeline config."""
    from omni.tracer import load_pipeline

    return load_pipeline(SKILLS_DIR(skill="demo", path="pipelines/loop.yaml"))


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
