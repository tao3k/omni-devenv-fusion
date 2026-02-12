"""Tests for modular pipeline package boundaries and package-level exports."""

from __future__ import annotations

from omni.tracer import (
    PipelineConfig as PackagePipelineConfig,
    LangGraphPipelineBuilder as PackageBuilder,
    create_langgraph_from_pipeline as package_create_langgraph,
)
from omni.tracer.pipeline_builder import LangGraphPipelineBuilder
from omni.tracer.pipeline_runtime import create_langgraph_from_pipeline
from omni.tracer.pipeline_schema import PipelineConfig


def test_package_reexports_schema_class_identity() -> None:
    """Package should expose the exact schema class."""
    assert PackagePipelineConfig is PipelineConfig


def test_package_reexports_builder_identity() -> None:
    """Package should expose the exact builder class."""
    assert PackageBuilder is LangGraphPipelineBuilder


def test_package_reexports_runtime_factory_identity() -> None:
    """Package should expose the exact runtime factory function."""
    assert package_create_langgraph is create_langgraph_from_pipeline


def test_modular_builder_and_package_export_produce_equivalent_graph_defs() -> None:
    """Builder behavior should remain unchanged through package-level exports."""
    config = PipelineConfig(
        pipeline=[
            "retriever.search",
            {
                "branch": {
                    "router": "route",
                    "branches": {
                        "continue": ["generator.analyze"],
                        "complete": ["generator.finalize"],
                    },
                }
            },
        ]
    )

    direct = LangGraphPipelineBuilder(config).build()
    via_package = PackageBuilder(config).build()

    assert direct["entry_node"] == via_package["entry_node"]
    assert direct["exit_nodes"] == via_package["exit_nodes"]
    assert direct["nodes"].keys() == via_package["nodes"].keys()
    assert direct["edges"] == via_package["edges"]
    assert len(direct["conditional_edges"]) == len(via_package["conditional_edges"])
