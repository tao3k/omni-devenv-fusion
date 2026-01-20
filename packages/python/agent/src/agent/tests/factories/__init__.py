"""
Test Data Factories

集中管理所有测试数据生成器 (Pydantic Factories with polyfactory).

Usage:
    from agent.tests.factories import SkillMetadataFactory, AgentContextFactory

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
        "agent.tests.factories.skill_metadata_factory",
        "SkillMetadataFactory",
    ),
    "MinimalSkillMetadataFactory": (
        "agent.tests.factories.skill_metadata_factory",
        "MinimalSkillMetadataFactory",
    ),
    "ValidSkillMetadataFactory": (
        "agent.tests.factories.skill_metadata_factory",
        "ValidSkillMetadataFactory",
    ),
    "GitSkillMetadataFactory": (
        "agent.tests.factories.skill_metadata_factory",
        "GitSkillMetadataFactory",
    ),
    "FilesystemSkillMetadataFactory": (
        "agent.tests.factories.skill_metadata_factory",
        "FilesystemSkillMetadataFactory",
    ),
    "KnowledgeSkillMetadataFactory": (
        "agent.tests.factories.skill_metadata_factory",
        "KnowledgeSkillMetadataFactory",
    ),
    # Context factories
    "AgentContextFactory": ("agent.tests.factories.context_factory", "AgentContextFactory"),
    "AgentResultFactory": ("agent.tests.factories.context_factory", "AgentResultFactory"),
    "SessionStateFactory": ("agent.tests.factories.context_factory", "SessionStateFactory"),
    "SessionEventFactory": ("agent.tests.factories.context_factory", "SessionEventFactory"),
    "AuditResultFactory": ("agent.tests.factories.context_factory", "AuditResultFactory"),
    # MCP factories
    "MCPToolFactory": ("agent.tests.factories.mcp_factory", "MCPToolFactory"),
    "MCPResourceFactory": ("agent.tests.factories.mcp_factory", "MCPResourceFactory"),
    "MCPPromptFactory": ("agent.tests.factories.mcp_factory", "MCPPromptFactory"),
    "MCPResponseFactory": ("agent.tests.factories.mcp_factory", "MCPResponseFactory"),
    "GitToolFactory": ("agent.tests.factories.mcp_factory", "GitToolFactory"),
    "FileToolFactory": ("agent.tests.factories.mcp_factory", "FileToolFactory"),
    # Core factories
    "TaskFactory": ("agent.tests.factories.core_factories", "TaskFactory"),
    "MinimalTaskFactory": ("agent.tests.factories.core_factories", "MinimalTaskFactory"),
    "PlanFactory": ("agent.tests.factories.core_factories", "PlanFactory"),
    "PlanWithTasksFactory": ("agent.tests.factories.core_factories", "PlanWithTasksFactory"),
    "EpisodeFactory": ("agent.tests.factories.core_factories", "EpisodeFactory"),
    "SubprocessResultFactory": ("agent.tests.factories.core_factories", "SubprocessResultFactory"),
    "SuccessResultFactory": ("agent.tests.factories.core_factories", "SuccessResultFactory"),
    "ErrorResultFactory": ("agent.tests.factories.core_factories", "ErrorResultFactory"),
    # Router factories
    "AgentRouteFactory": ("agent.tests.factories.router_factories", "AgentRouteFactory"),
    "CoderAgentRouteFactory": ("agent.tests.factories.router_factories", "CoderAgentRouteFactory"),
    "ReviewerAgentRouteFactory": (
        "agent.tests.factories.router_factories",
        "ReviewerAgentRouteFactory",
    ),
    "RoutingResultFactory": ("agent.tests.factories.router_factories", "RoutingResultFactory"),
    "AgentResponseFactory": ("agent.tests.factories.router_factories", "AgentResponseFactory"),
    "ToolCallFactory": ("agent.tests.factories.router_factories", "ToolCallFactory"),
    "TaskBriefFactory": ("agent.tests.factories.router_factories", "TaskBriefFactory"),
    # Re-exports
    "SkillMetadata": ("agent.core.schema.skill", "SkillMetadata"),
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
