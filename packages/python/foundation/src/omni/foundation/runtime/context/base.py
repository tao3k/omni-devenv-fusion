"""
context/base.py
Base classes for project-specific context.

Protocol-based design with slots=True.

Provides ProjectContext base class for language-specific contexts.
"""

from __future__ import annotations

from abc import ABC


class ProjectContext(ABC):
    """Base class for project-specific language context.

    Subclass this to add support for a new language:

    class PythonContext(ProjectContext):
        LANG_ID = "python"
        CATEGORIES = ["tooling", "patterns", "architecture", "conventions"]

        def _load_tooling(self) -> str:
            return "## 🛠️ Tooling\n- Use `uv mod` for dependencies..."

        def _load_patterns(self) -> str:
            return "## 🔄 Common Patterns\n- Singleton pattern..."

    ContextRegistry.register(PythonContext())
    """

    # Override these in subclass
    LANG_ID: str = ""
    CATEGORIES: list[str] = ["tooling"]

    def __init__(self) -> None:
        """Initialize context cache."""
        self._cache: dict[str, str] = {}
        self._loaded: bool = False

    def _ensure_loaded(self) -> None:
        """Lazy load all categories."""
        if self._loaded:
            return
        for cat in self.CATEGORIES:
            loader = getattr(self, f"_load_{cat}", lambda: "")
            self._cache[cat] = loader()
        self._loaded = True

    def get(self, category: str | None = None) -> str:
        """Get context for a category or all categories.

        Args:
            category: Specific category, or None for all.

        Returns:
            Context string.
        """
        self._ensure_loaded()
        if category:
            return self._cache.get(category, "")
        return "\n\n".join(self._cache.values())

    def has_category(self, category: str) -> bool:
        """Check if category exists.

        Args:
            category: Category name.

        Returns:
            True if category exists.
        """
        return category in self.CATEGORIES

    @property
    def lang_id(self) -> str:
        """Get language ID."""
        return self.LANG_ID

    @property
    def categories(self) -> list[str]:
        """Get all category names."""
        return self.CATEGORIES.copy()

    # Override these in subclass for each category
    def _load_tooling(self) -> str:
        """Load tooling context."""
        return ""

    def _load_patterns(self) -> str:
        """Load patterns context."""
        return ""

    def _load_architecture(self) -> str:
        """Load architecture context."""
        return ""

    def _load_conventions(self) -> str:
        """Load conventions context."""
        return ""


__all__ = ["ProjectContext"]
