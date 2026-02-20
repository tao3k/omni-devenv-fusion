"""Backend contract for link-graph engines."""

from __future__ import annotations

from typing import Protocol

from .models import (
    LinkGraphDirection,
    LinkGraphMetadata,
    LinkGraphNeighbor,
    LinkGraphSearchOptions,
)


class LinkGraphBackend(Protocol):
    """Backend-agnostic contract for graph-first retrieval operations."""

    backend_name: str

    async def search_planned(
        self,
        query: str,
        limit: int = 20,
        options: LinkGraphSearchOptions | dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Search and return parsed query plan with effective options and hits."""

    async def refresh_with_delta(
        self,
        changed_paths: list[str] | None = None,
        *,
        force_full: bool = False,
    ) -> dict[str, object]:
        """Refresh backend index using delta paths, with optional full rebuild fallback."""

    async def neighbors(
        self,
        stem: str,
        *,
        direction: LinkGraphDirection = LinkGraphDirection.BOTH,
        hops: int = 1,
        limit: int = 50,
    ) -> list[LinkGraphNeighbor]:
        """Return neighbor stems connected to the input stem."""

    async def related(
        self,
        stem: str,
        *,
        max_distance: int = 2,
        limit: int = 20,
    ) -> list[LinkGraphNeighbor]:
        """Return related stems around input stem."""

    async def metadata(self, stem: str) -> LinkGraphMetadata | None:
        """Return metadata for a single stem."""

    async def toc(self, limit: int = 1000) -> list[dict[str, object]]:
        """Return table-of-contents rows for graph notes."""

    async def stats(self) -> dict[str, int]:
        """Return backend-level graph statistics for observability/CLI."""

    async def create_note(
        self,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
    ) -> object | None:
        """Create a graph note when backend supports writes."""


__all__ = [
    "LinkGraphBackend",
]
