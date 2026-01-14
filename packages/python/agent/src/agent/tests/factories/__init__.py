"""
Test Data Factories

集中管理所有测试数据生成器 (Pydantic Factories with polyfactory).

Usage:
    from agent.tests.factories import SkillManifestFactory

    # Generate valid test data
    manifest = SkillManifestFactory.build()

    # With overrides
    manifest = SkillManifestFactory.build(name="custom")

    # Batch generation
    manifests = SkillManifestFactory.batch(size=5)
"""

# Lazy imports to avoid import errors when polyfactory not available
_lazy_imports = {
    "SkillManifestFactory": ("agent.tests.factories.manifest_factory", "SkillManifestFactory"),
    "AgentContextFactory": ("agent.tests.factories.context_factory", "AgentContextFactory"),
    "MCPToolFactory": ("agent.tests.factories.mcp_factory", "MCPToolFactory"),
    "MCPResourceFactory": ("agent.tests.factories.mcp_factory", "MCPResourceFactory"),
    "SkillManifest": ("agent.core.schema.skill", "SkillManifest"),
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
    "SkillManifestFactory",
    "AgentContextFactory",
    "MCPToolFactory",
    "MCPResourceFactory",
    "SkillManifest",
]
