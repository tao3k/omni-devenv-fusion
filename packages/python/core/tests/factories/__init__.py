"""
Test Data Factories

集中管理所有测试数据生成器 (Pydantic Factories with polyfactory).

Usage:
    from omni.core.tests.factories import SkillMetadataFactory, AgentContextFactory

    # Generate valid test data
    metadata = SkillMetadataFactory.build()
    context = AgentContextFactory.build()

    # With overrides
    metadata = SkillMetadataFactory.build(name="custom")

    # Batch generation
    metadata_list = SkillMetadataFactory.batch(size=5)
"""

# Lazy imports to avoid import errors when polyfactory not available
_lazy_imports = {
    # SkillMetadata factories
    "SkillMetadataFactory": (
        "omni.agent.tests.factories.skill_metadata_factory",
        "SkillMetadataFactory",
    ),
    "MinimalSkillMetadataFactory": (
        "omni.agent.tests.factories.skill_metadata_factory",
        "MinimalSkillMetadataFactory",
    ),
    "ValidSkillMetadataFactory": (
        "omni.agent.tests.factories.skill_metadata_factory",
        "ValidSkillMetadataFactory",
    ),
    "GitSkillMetadataFactory": (
        "omni.agent.tests.factories.skill_metadata_factory",
        "GitSkillMetadataFactory",
    ),
    "FilesystemSkillMetadataFactory": (
        "omni.agent.tests.factories.skill_metadata_factory",
        "FilesystemSkillMetadataFactory",
    ),
    "KnowledgeSkillMetadataFactory": (
        "omni.agent.tests.factories.skill_metadata_factory",
        "KnowledgeSkillMetadataFactory",
    ),
    # Context factories
    "AgentContextFactory": ("omni.agent.tests.factories.context_factory", "AgentContextFactory"),
    "AgentResultFactory": ("omni.agent.tests.factories.context_factory", "AgentResultFactory"),
    "SessionStateFactory": ("omni.agent.tests.factories.context_factory", "SessionStateFactory"),
    "SessionEventFactory": ("omni.agent.tests.factories.context_factory", "SessionEventFactory"),
    "AuditResultFactory": ("omni.agent.tests.factories.context_factory", "AuditResultFactory"),
    # MCP factories
    "MCPToolFactory": ("omni.agent.tests.factories.mcp_factory", "MCPToolFactory"),
    "MCPResourceFactory": ("omni.agent.tests.factories.mcp_factory", "MCPResourceFactory"),
    "MCPPromptFactory": ("omni.agent.tests.factories.mcp_factory", "MCPPromptFactory"),
    "MCPResponseFactory": ("omni.agent.tests.factories.mcp_factory", "MCPResponseFactory"),
    "GitToolFactory": ("omni.agent.tests.factories.mcp_factory", "GitToolFactory"),
    "FileToolFactory": ("omni.agent.tests.factories.mcp_factory", "FileToolFactory"),
    # Core factories
    "TaskFactory": ("omni.agent.tests.factories.core_factories", "TaskFactory"),
    "MinimalTaskFactory": ("omni.agent.tests.factories.core_factories", "MinimalTaskFactory"),
    "PlanFactory": ("omni.agent.tests.factories.core_factories", "PlanFactory"),
    "PlanWithTasksFactory": ("omni.agent.tests.factories.core_factories", "PlanWithTasksFactory"),
    "EpisodeFactory": ("omni.agent.tests.factories.core_factories", "EpisodeFactory"),
    "SubprocessResultFactory": (
        "omni.agent.tests.factories.core_factories",
        "SubprocessResultFactory",
    ),
    "SuccessResultFactory": ("omni.agent.tests.factories.core_factories", "SuccessResultFactory"),
    "ErrorResultFactory": ("omni.agent.tests.factories.core_factories", "ErrorResultFactory"),
    # Router factories
    "AgentRouteFactory": ("omni.agent.tests.factories.router_factories", "AgentRouteFactory"),
    "CoderAgentRouteFactory": (
        "omni.agent.tests.factories.router_factories",
        "CoderAgentRouteFactory",
    ),
    "ReviewerAgentRouteFactory": (
        "omni.agent.tests.factories.router_factories",
        "ReviewerAgentRouteFactory",
    ),
    "RoutingResultFactory": ("omni.agent.tests.factories.router_factories", "RoutingResultFactory"),
    "AgentResponseFactory": ("omni.agent.tests.factories.router_factories", "AgentResponseFactory"),
    "ToolCallFactory": ("omni.agent.tests.factories.router_factories", "ToolCallFactory"),
    "TaskBriefFactory": ("omni.agent.tests.factories.router_factories", "TaskBriefFactory"),
    # Re-exports
    "SkillMetadata": ("omni.agent.core.schema.skill", "SkillMetadata"),
    "ModelFactory": ("polyfactory.factories.pydantic_factory", "ModelFactory"),
}


def __getattr__(name):
    if name in _lazy_imports:
        module_path, attr_name = _lazy_imports[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Return list of available exports."""
    return list(__all__)


# Re-export for convenience
__all__ = [
    # SkillMetadata factories
    "SkillMetadataFactory",
    "MinimalSkillMetadataFactory",
    "ValidSkillMetadataFactory",
    "GitSkillMetadataFactory",
    "FilesystemSkillMetadataFactory",
    "KnowledgeSkillMetadataFactory",
    # Context factories
    "AgentContextFactory",
    "AgentResultFactory",
    "SessionStateFactory",
    "SessionEventFactory",
    "AuditResultFactory",
    # MCP factories
    "MCPToolFactory",
    "MCPResourceFactory",
    "MCPPromptFactory",
    "MCPResponseFactory",
    "GitToolFactory",
    "FileToolFactory",
    # Core factories
    "TaskFactory",
    "MinimalTaskFactory",
    "PlanFactory",
    "PlanWithTasksFactory",
    "EpisodeFactory",
    "SubprocessResultFactory",
    "SuccessResultFactory",
    "ErrorResultFactory",
    # Router factories
    "AgentRouteFactory",
    "CoderAgentRouteFactory",
    "ReviewerAgentRouteFactory",
    "RoutingResultFactory",
    "AgentResponseFactory",
    "ToolCallFactory",
    "TaskBriefFactory",
    # Re-exports
    "SkillMetadata",
]
