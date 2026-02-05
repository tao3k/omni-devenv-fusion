"""
variants.py - Provider Variant System

Provider pattern for skill commands supporting multiple implementations
(e.g., local Python vs Rust-accelerated).

Usage:
    from omni.core.skills.variants import VariantProvider, VariantRegistry

    class RustCodeSearch(VariantProvider):
        variant_name = "rust"

        async def execute(self, query: str, **kwargs) -> ToolResponse:
            # Rust-accelerated implementation
            ...

    registry = VariantRegistry()
    registry.register("code_search", RustCodeSearch())
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from omni.core.responses import ToolResponse


class VariantStatus(str, Enum):
    """Variant availability status."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"  # Available but with limitations


class VariantProvider(ABC):
    """Abstract base class for skill command variants.

    A variant is an alternative implementation of a command.
    For example, code_search can have:
    - "local": Pure Python implementation
    - "rust": Rust-accelerated implementation
    - "remote": Cloud API implementation
    """

    @property
    @abstractmethod
    def variant_name(self) -> str:
        """Return unique identifier for this variant."""

    @property
    def variant_description(self) -> str:
        """Return description of this variant."""
        return f"{self.variant_name} implementation"

    @property
    def variant_status(self) -> VariantStatus:
        """Return availability status of this variant."""
        return VariantStatus.AVAILABLE

    @property
    def variant_priority(self) -> int:
        """Return priority for automatic selection (lower = higher priority)."""
        return 100

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResponse:
        """Execute the command with this variant.

        Args:
            **kwargs: Command arguments

        Returns:
            ToolResponse with execution result
        """

    async def initialize(self) -> bool:
        """Initialize the variant (e.g., load models, check dependencies).

        Returns:
            True if initialization successful
        """
        return True

    async def health_check(self) -> bool:
        """Check if variant is healthy and ready.

        Returns:
            True if healthy
        """
        return self.variant_status == VariantStatus.AVAILABLE


class VariantInfo:
    """Metadata about a registered variant."""

    def __init__(
        self,
        provider: VariantProvider,
        command_name: str,
        factory: Callable[[], VariantProvider] | None = None,
    ):
        self.provider = provider
        self.command_name = command_name
        self.factory = factory  # Lazy instantiation function
        self.variant_name = provider.variant_name
        self.variant_description = provider.variant_description
        self.variant_status = provider.variant_status
        self.variant_priority = provider.variant_priority

    @property
    def is_available(self) -> bool:
        """Check if variant is available."""
        return self.variant_status != VariantStatus.UNAVAILABLE


class VariantRegistry:
    """Registry for skill command variants.

    Manages registration and selection of variants for commands.

    Usage:
        registry = VariantRegistry()

        # Register a variant
        registry.register("code_search", RustCodeSearch())

        # Get best available variant
        variant = registry.get_best("code_search")

        # Get specific variant
        variant = registry.get("code_search", "rust")
    """

    def __init__(self):
        self._variants: dict[str, dict[str, VariantInfo]] = {}
        self._factories: dict[str, list[tuple[str, Callable[[], VariantProvider]]]] = {}

    def register(
        self,
        command_name: str,
        provider_or_factory: VariantProvider | Callable[[], VariantProvider],
        variant_name: str | None = None,
        priority: int | None = None,
    ) -> None:
        """Register a variant for a command.

        Args:
            command_name: Name of the command (e.g., "code_search")
            provider_or_factory: VariantProvider instance or factory function
            variant_name: Override variant name (use provider.variant_name if None)
            priority: Override priority (use provider.variant_priority if None)
        """
        if command_name not in self._variants:
            self._variants[command_name] = {}

        if callable(provider_or_factory) and not isinstance(provider_or_factory, VariantProvider):
            # It's a factory function
            factory = provider_or_factory
            # Create a dummy provider to get variant name
            try:
                dummy = factory()
                actual_variant_name = variant_name or dummy.variant_name
                actual_priority = priority if priority is not None else dummy.variant_priority
                self._factories.setdefault(command_name, []).append((actual_variant_name, factory))
                self._variants[command_name][actual_variant_name] = VariantInfo(
                    provider=dummy,
                    command_name=command_name,
                    factory=factory,
                )
            except Exception as e:
                raise ValueError(f"Factory function failed: {e}")
        else:
            # It's a provider instance
            provider = provider_or_factory
            actual_variant_name = variant_name or provider.variant_name
            actual_priority = priority if priority is not None else provider.variant_priority

            self._variants[command_name][actual_variant_name] = VariantInfo(
                provider=provider,
                command_name=command_name,
            )

        # Update priority if specified
        if actual_priority is not None:
            self._variants[command_name][actual_variant_name].variant_priority = actual_priority

    def get(
        self,
        command_name: str,
        variant_name: str,
        instantiate: bool = True,
    ) -> VariantProvider | None:
        """Get a specific variant for a command.

        Args:
            command_name: Name of the command
            variant_name: Name of the variant
            instantiate: If True, instantiate lazy providers

        Returns:
            VariantProvider or None if not found
        """
        if command_name not in self._variants:
            return None

        info = self._variants[command_name].get(variant_name)
        if not info:
            return None

        provider = info.provider
        # If provider is a dummy (from factory), instantiate it
        if hasattr(provider, "_is_dummy") and provider._is_dummy:
            for var_name, factory in self._factories.get(command_name, []):
                if var_name == variant_name:
                    return factory()

        return provider

    def get_best(
        self,
        command_name: str,
        exclude: list[str] | None = None,
    ) -> VariantProvider | None:
        """Get the best available variant for a command.

        Selection criteria:
        1. Available status (AVAILABLE > DEGRADED > UNAVAILABLE)
        2. Priority (lower = higher priority)

        Args:
            command_name: Name of the command
            exclude: List of variant names to exclude

        Returns:
            Best available VariantProvider or None
        """
        if command_name not in self._variants:
            return None

        exclude = exclude or []
        variants = self._variants[command_name]

        # Instantiate lazy providers first
        for variant_name in list(variants.keys()):
            info = variants[variant_name]
            if hasattr(info.provider, "_is_dummy"):
                for var_name, factory in self._factories.get(command_name, []):
                    if var_name == variant_name:
                        info.provider = factory()
                        break

        # Filter and sort by status then priority
        available = [
            (name, info)
            for name, info in variants.items()
            if name not in exclude and info.is_available
        ]

        if not available:
            return None

        # Sort by: status priority first, then variant priority
        status_order = {
            VariantStatus.AVAILABLE: 0,
            VariantStatus.DEGRADED: 1,
            VariantStatus.UNAVAILABLE: 2,
        }

        available.sort(
            key=lambda x: (status_order.get(x[1].variant_status, 3), x[1].variant_priority)
        )

        return available[0][1].provider

    def list_variants(self, command_name: str) -> list[str]:
        """List all registered variant names for a command."""
        if command_name not in self._variants:
            return []
        return list(self._variants[command_name].keys())

    def list_commands(self) -> list[str]:
        """List all commands with registered variants."""
        return list(self._variants.keys())

    def get_info(self, command_name: str, variant_name: str) -> VariantInfo | None:
        """Get metadata about a variant."""
        if command_name not in self._variants:
            return None
        return self._variants[command_name].get(variant_name)

    def unregister(self, command_name: str, variant_name: str) -> bool:
        """Unregister a variant."""
        if command_name not in self._variants:
            return False

        if variant_name in self._variants[command_name]:
            del self._variants[command_name][variant_name]
            # Also remove from factories
            if command_name in self._factories:
                self._factories[command_name] = [
                    (name, factory)
                    for name, factory in self._factories[command_name]
                    if name != variant_name
                ]
            return True
        return False


# Global registry instance
_default_registry: VariantRegistry | None = None


def get_variant_registry() -> VariantRegistry:
    """Get the default variant registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = VariantRegistry()
    return _default_registry


def register_variant(
    command_name: str,
    provider_or_factory: VariantProvider | Callable[[], VariantProvider],
    variant_name: str | None = None,
    priority: int | None = None,
) -> None:
    """Convenience function to register a variant with the default registry."""
    get_variant_registry().register(command_name, provider_or_factory, variant_name, priority)


def get_variant(
    command_name: str,
    variant_name: str,
) -> VariantProvider | None:
    """Convenience function to get a variant from the default registry."""
    return get_variant_registry().get(command_name, variant_name)


def get_best_variant(command_name: str, exclude: list[str] | None = None) -> VariantProvider | None:
    """Convenience function to get the best variant from the default registry."""
    return get_variant_registry().get_best(command_name, exclude)
