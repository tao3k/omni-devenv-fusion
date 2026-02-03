"""Service Locator Pattern for Core Services.

Provides thread-safe global access to core services (Librarian, SkillManager, etc.)
for stateless skill functions.

Usage:
    from omni.core.runtime.services import get_librarian

    @skill_command(...)
    async def my_skill():
        librarian = get_librarian()
        if librarian:
            results = librarian.query("...")
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, Optional

logger = __import__("logging").getLogger(__name__)

T = TypeVar("T")


class ServiceRegistry:
    """Thread-safe service registry using Service Locator pattern.

    Allows stateless skills to access core services without direct dependencies.
    """

    _instance: "ServiceRegistry | None" = None
    _services: dict[str, Any] = {}
    _lock: __import__("threading").Lock = __import__("threading").Lock()

    def __new__(cls) -> "ServiceRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, name: str, service: Any) -> None:
        """Register a core service singleton.

        Args:
            name: Service identifier (e.g., "librarian", "skill_manager")
            service: Service instance
        """
        with cls._lock:
            cls._services[name] = service
        logger.debug(f"Service registered: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """Retrieve a service by name.

        Args:
            name: Service identifier

        Returns:
            Service instance or None if not registered
        """
        with cls._lock:
            service = cls._services.get(name)

        if service is None:
            logger.warning(f"Service '{name}' requested but not found in registry.")
        return service

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove a service from the registry.

        Args:
            name: Service identifier
        """
        with cls._lock:
            cls._services.pop(name, None)
        logger.debug(f"Service unregistered: {name}")

    @classmethod
    def clear(cls) -> None:
        """Remove all registered services."""
        with cls._lock:
            cls._services.clear()
        logger.debug("Service registry cleared")

    @classmethod
    def list_services(cls) -> list[str]:
        """List all registered service names."""
        with cls._lock:
            return list(cls._services.keys())


# =============================================================================
# Convenience Accessors
# =============================================================================


def get_librarian() -> Optional["Librarian"]:
    """Get the global Librarian service.

    Returns:
        Librarian instance or None
    """
    from omni.core.knowledge.librarian import Librarian

    service = ServiceRegistry.get("librarian")
    if service is not None and not isinstance(service, Librarian):
        logger.warning(f"Service 'librarian' is not a Librarian instance")
        return None
    return service


def get_skill_manager() -> Optional["SkillManager"]:
    """Get the global SkillManager service.

    Returns:
        SkillManager instance or None
    """
    from omni.core.services.skill_manager import SkillManager

    service = ServiceRegistry.get("skill_manager")
    if service is not None and not isinstance(service, SkillManager):
        logger.warning(f"Service 'skill_manager' is not a SkillManager instance")
        return None
    return service


def get_embedding_service() -> Optional["EmbeddingService"]:
    """Get the global EmbeddingService.

    Returns:
        EmbeddingService instance or None
    """
    from omni.foundation.services.embedding import EmbeddingService

    service = ServiceRegistry.get("embedding")
    if service is not None and not isinstance(service, EmbeddingService):
        logger.warning(f"Service 'embedding' is not an EmbeddingService instance")
        return None
    return service


# =============================================================================
# Lazy Initialization Helpers
# =============================================================================


def ensure_librarian(project_root: str = ".") -> "Librarian":
    """Get or create the global Librarian service.

    Args:
        project_root: Project root directory

    Returns:
        Librarian instance
    """
    librarian = get_librarian()
    if librarian is None:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(project_root=project_root)
        ServiceRegistry.register("librarian", librarian)
    return librarian


def ensure_skill_manager() -> "SkillManager":
    """Get or create the global SkillManager service.

    Returns:
        SkillManager instance
    """
    manager = get_skill_manager()
    if manager is None:
        from omni.core.services.skill_manager import SkillManager

        manager = SkillManager()
        ServiceRegistry.register("skill_manager", manager)
    return manager


# Re-exports
__all__ = [
    "ServiceRegistry",
    "get_librarian",
    "get_skill_manager",
    "get_embedding_service",
    "ensure_librarian",
    "ensure_skill_manager",
]
