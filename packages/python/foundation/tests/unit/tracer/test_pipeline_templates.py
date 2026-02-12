"""
test_pipeline_templates.py - Validate bundled pipeline YAML templates.
"""

from __future__ import annotations

from pathlib import Path

from omni.tracer import PipelineConfig, LangGraphPipelineBuilder


def test_ultrarag_complex_template_is_valid_and_compilable():
    template = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "omni"
        / "tracer"
        / "templates"
        / "ultrarag_complex.yaml"
    )
    config = PipelineConfig.from_yaml(template)
    builder = LangGraphPipelineBuilder(config)
    graph_def = builder.build()

    assert graph_def["entry_node"] is not None
    assert len(graph_def["nodes"]) > 0
    assert len(graph_def["conditional_edges"]) >= 1
    assert "retriever_hybrid_search" in graph_def["nodes"]
