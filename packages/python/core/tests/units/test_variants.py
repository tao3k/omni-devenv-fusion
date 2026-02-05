"""
test_variants.py - Unit tests for Provider Variant System

Tests for VariantProvider, VariantRegistry, and variant loading.

Marker: unit (pure unit tests with mocks)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from omni.core.skills.variants import (
    VariantProvider,
    VariantRegistry,
    VariantStatus,
    VariantInfo,
    get_variant_registry,
    register_variant,
    get_variant,
    get_best_variant,
)


class DummyVariant(VariantProvider):
    """Dummy variant for testing."""

    def __init__(self, name: str = "dummy", priority: int = 100):
        self._name = name
        self._priority = priority
        self._status = VariantStatus.AVAILABLE
        self._executed = False

    @property
    def variant_name(self) -> str:
        return self._name

    @property
    def variant_description(self) -> str:
        return f"Dummy {self._name} implementation"

    @property
    def variant_status(self) -> VariantStatus:
        return self._status

    @property
    def variant_priority(self) -> int:
        return self._priority

    async def execute(self, **kwargs):
        from omni.core.responses import ToolResponse

        self._executed = True
        return ToolResponse.success(data={"variant": self._name, "executed": True})


class DegradedVariant(VariantProvider):
    """Degraded variant for testing."""

    @property
    def variant_name(self) -> str:
        return "degraded"

    @property
    def variant_status(self) -> VariantStatus:
        return VariantStatus.DEGRADED

    async def execute(self, **kwargs):
        from omni.core.responses import ToolResponse

        return ToolResponse.success(data={"status": "degraded"})


class TestVariantProvider:
    """Tests for VariantProvider base class."""

    def test_default_properties(self):
        """Test default property values."""
        variant = DummyVariant()
        assert variant.variant_name == "dummy"
        assert variant.variant_description == "Dummy dummy implementation"
        assert variant.variant_status == VariantStatus.AVAILABLE
        assert variant.variant_priority == 100

    def test_custom_properties(self):
        """Test custom property values."""
        variant = DummyVariant(name="rust", priority=10)
        assert variant.variant_name == "rust"
        assert variant.variant_priority == 10

    async def test_execute(self):
        """Test execute method."""
        variant = DummyVariant()
        result = await variant.execute(query="test")
        assert result.is_success
        assert result.data["variant"] == "dummy"
        assert variant._executed

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check method."""
        variant = DummyVariant()
        assert await variant.health_check() is True

        variant._status = VariantStatus.UNAVAILABLE
        assert await variant.health_check() is False

    async def test_initialize(self):
        """Test initialize method."""
        variant = DummyVariant()
        assert await variant.initialize() is True


class TestVariantRegistry:
    """Tests for VariantRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        global _default_registry
        _default_registry = None
        self.registry = VariantRegistry()

    def test_register_provider(self):
        """Test registering a variant provider."""
        variant = DummyVariant(name="local")
        self.registry.register("code_search", variant)

        assert "code_search" in self.registry.list_commands()
        assert "local" in self.registry.list_variants("code_search")

    def test_register_factory(self):
        """Test registering a factory function."""

        def create_variant():
            return DummyVariant(name="rust")

        self.registry.register("code_search", create_variant, variant_name="rust")

        assert "rust" in self.registry.list_variants("code_search")

    def test_get_specific_variant(self):
        """Test getting a specific variant."""
        local = DummyVariant(name="local")
        rust = DummyVariant(name="rust")

        self.registry.register("code_search", local)
        self.registry.register("code_search", rust)

        result = self.registry.get("code_search", "rust")
        assert result is not None
        assert result.variant_name == "rust"

    def test_get_nonexistent_variant(self):
        """Test getting a nonexistent variant."""
        result = self.registry.get("code_search", "nonexistent")
        assert result is None

    def test_get_nonexistent_command(self):
        """Test getting a variant for nonexistent command."""
        result = self.registry.get("nonexistent", "local")
        assert result is None

    def test_get_best_variant(self):
        """Test getting the best available variant."""
        local = DummyVariant(name="local", priority=100)
        rust = DummyVariant(name="rust", priority=10)  # Higher priority

        self.registry.register("code_search", local)
        self.registry.register("code_search", rust)

        best = self.registry.get_best("code_search")
        assert best is not None
        assert best.variant_name == "rust"

    def test_get_best_excludes_variants(self):
        """Test that get_best can exclude variants."""
        local = DummyVariant(name="local", priority=10)
        rust = DummyVariant(name="rust", priority=10)

        self.registry.register("code_search", local)
        self.registry.register("code_search", rust)

        best = self.registry.get_best("code_search", exclude=["rust"])
        assert best is not None
        assert best.variant_name == "local"

    def test_status_priority_selection(self):
        """Test that status affects variant selection."""
        available = DummyVariant(name="available", priority=100)
        degraded = DummyVariant(name="degraded")
        degraded._status = VariantStatus.DEGRADED

        self.registry.register("code_search", degraded)
        self.registry.register("code_search", available)

        best = self.registry.get_best("code_search")
        assert best is not None
        assert best.variant_name == "available"

    def test_list_variants(self):
        """Test listing variants for a command."""
        self.registry.register("code_search", DummyVariant(name="local"))
        self.registry.register("code_search", DummyVariant(name="rust"))

        variants = self.registry.list_variants("code_search")
        assert len(variants) == 2
        assert "local" in variants
        assert "rust" in variants

    def test_unregister_variant(self):
        """Test unregistering a variant."""
        self.registry.register("code_search", DummyVariant(name="local"))

        assert self.registry.unregister("code_search", "local")
        assert "local" not in self.registry.list_variants("code_search")

    def test_unregister_nonexistent(self):
        """Test unregistering a nonexistent variant."""
        assert self.registry.unregister("code_search", "nonexistent") is False

    def test_get_info(self):
        """Test getting variant info."""
        variant = DummyVariant(name="local")
        self.registry.register("code_search", variant)

        info = self.registry.get_info("code_search", "local")
        assert info is not None
        assert info.variant_name == "local"


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def setup_method(self):
        """Reset registry before each test."""
        global _default_registry
        _default_registry = None

    def test_get_variant_registry(self):
        """Test getting the default registry."""
        registry = get_variant_registry()
        assert registry is not None
        assert isinstance(registry, VariantRegistry)

    def test_register_variant(self):
        """Test convenience registration function."""
        register_variant("code_search", DummyVariant(name="rust"))

        registry = get_variant_registry()
        assert "rust" in registry.list_variants("code_search")

    def test_get_variant(self):
        """Test convenience get function."""
        register_variant("code_search", DummyVariant(name="local"))

        variant = get_variant("code_search", "local")
        assert variant is not None
        assert variant.variant_name == "local"

    def test_get_best_variant(self):
        """Test convenience get_best function."""
        register_variant("code_search", DummyVariant(name="local", priority=100))
        register_variant("code_search", DummyVariant(name="rust", priority=10))

        best = get_best_variant("code_search")
        assert best is not None
        assert best.variant_name == "rust"


class TestVariantInfo:
    """Tests for VariantInfo class."""

    def test_is_available(self):
        """Test is_available property."""
        # Create an unavailable provider
        provider = DummyVariant()
        provider._status = VariantStatus.UNAVAILABLE

        info = VariantInfo(provider=provider, command_name="code_search")

        # Create another available variant
        available_provider = DummyVariant()
        available_provider._status = VariantStatus.AVAILABLE
        available_info = VariantInfo(provider=available_provider, command_name="code_search")

        assert info.is_available is False
        assert available_info.is_available is True

    def test_factory_info(self):
        """Test VariantInfo with factory."""

        def create():
            return DummyVariant(name="rust")

        provider = DummyVariant()  # Dummy for initialization
        provider._is_dummy = True

        info = VariantInfo(provider=provider, command_name="code_search", factory=create)
        assert info.factory is not None
