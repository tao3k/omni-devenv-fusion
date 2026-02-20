"""
omni.core.kernel.watcher - Reactive Skill Watcher (Live-Wire)

Monitors skill scripts (via SKILLS_DIR()) and LinkGraph markdown roots, then
triggers incremental index updates on changes. Uses Rust omni-io notify
bindings for high-performance file watching with EventBus integration.

Features:
- Debouncing: Avoids duplicate events for the same file
- Pattern filtering: Only processes relevant file types
- Callback support: Fires callbacks when skills change (for MCP notifications)
- Kernel integration: Automatically reloads skills when scripts change
- LinkGraph refresh: Triggers common backend delta refresh for markdown changes

This is the "Live-Wire" that connects Rust Sniffer to Python Indexer,
enabling hot-reload of tools without restarting the Agent.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import omni_core_rs as rs

from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting

logger = get_logger("omni.core.watcher")

# Skip these file patterns (mirrors Rust exclude patterns)
SKIP_PATTERNS = {".pyc", ".pyo", ".pyd", ".swp", ".swo", ".tmp", "__pycache__", ".git"}
DEFAULT_LINK_GRAPH_PATTERNS = ["**/*.md", "**/*.markdown", "**/*.mdx", "**/SKILL.md"]
DEFAULT_LINK_GRAPH_WATCH_DIRS = ["assets/knowledge", "docs", ".data/harvested"]

if TYPE_CHECKING:
    from collections.abc import Callable

    from omni.core.kernel.engine import Kernel
    from omni.core.skills.indexer import SkillIndexer


class FileChangeType(str, Enum):
    """File change event types."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    ERROR = "error"
    CHANGED = "changed"  # Some watchers send "changed" instead of "modified"


@dataclass
class FileChangeEvent:
    """A file change event from the watcher."""

    event_type: FileChangeType
    path: str
    is_directory: bool = False

    @classmethod
    def from_tuple(cls, data: tuple[str, str]) -> FileChangeEvent:
        """Create from (event_type, path) tuple."""
        return cls(
            event_type=FileChangeType(data[0]),
            path=data[1],
            is_directory=False,
        )


# ============================================================================
# Reactive Skill Watcher (Live-Wire)
class ReactiveSkillWatcher:
    """
    Monitors skill directories and LinkGraph markdown roots for reactive updates.

    Uses Rust-based file watching (omni-io) for high-performance event capture,
    then dispatches to the SkillIndexer for knowledge updates.

    Features:
    - Debouncing: Avoids duplicate events for the same file
    - Pattern filtering: Only processes relevant file types
    - Graceful shutdown: Clean stop of watcher threads
    - Callback support: Fires callbacks when skills change (for MCP notifications)
    - Kernel integration: Automatically reloads skills when scripts change

    This is the "Live-Wire" that connects Rust Sniffer to Python Indexer,
    enabling hot-reload of tools without restarting the Agent.
    """

    def __init__(
        self,
        indexer: SkillIndexer,
        patterns: list[str] | None = None,
        debounce_seconds: float = 0.5,
        poll_interval: float = 0.5,
        kernel: Kernel | None = None,
    ):
        """Initialize the reactive skill watcher.

        Args:
            indexer: SkillIndexer instance for processing events
            patterns: File patterns to watch (default: ["**/*.py"])
            debounce_seconds: Debounce delay in seconds
            poll_interval: How often to poll for events (seconds)
            kernel: Optional Kernel instance for skill reload integration
        """
        from omni.foundation.config.skills import SKILLS_DIR
        from omni.foundation.runtime.gitops import get_project_root

        # Use get_project_root() to get project root (reads PRJ_ROOT from direnv via git)
        self.project_root = get_project_root()
        # skills_dir from config (settings: system packages/conf/settings.yaml, user $PRJ_CONFIG_HOME -> assets.skills_dir)
        self.skills_dir = SKILLS_DIR()
        self.indexer = indexer
        self.poll_interval = poll_interval
        self.debounce_seconds = debounce_seconds
        self._kernel = kernel  # Kernel bridge for skill reload

        # Build exclude patterns for common noise
        exclude_patterns = [
            "**/*.pyc",
            "**/__pycache__/**",
            "**/.git/**",
            "**/target/**",
            "**/.venv/**",
            "**/node_modules/**",
        ]

        # File patterns to include
        self.patterns = patterns or ["**/*.py"]
        self._link_graph_patterns = self._resolve_link_graph_patterns()
        self._link_graph_watch_roots = self._resolve_link_graph_watch_roots()

        watch_paths = [self.skills_dir]
        for root in self._link_graph_watch_roots:
            if root.exists() and root.is_dir():
                watch_paths.append(root)
        dedup_paths: list[str] = []
        seen_paths: set[str] = set()
        for entry in watch_paths:
            text = str(entry)
            if text in seen_paths:
                continue
            seen_paths.add(text)
            dedup_paths.append(text)

        combined_patterns = [*self.patterns, *self._link_graph_patterns]
        dedup_patterns: list[str] = []
        seen_patterns: set[str] = set()
        for pattern in combined_patterns:
            token = str(pattern or "").strip()
            if not token or token in seen_patterns:
                continue
            seen_patterns.add(token)
            dedup_patterns.append(token)

        # Rust watcher config - watch skills_dir (user-configurable)
        self.config = rs.PyWatcherConfig()
        self.config.paths = dedup_paths
        self.config.recursive = True
        self.config.debounce_ms = int(debounce_seconds * 1000)
        self.config.patterns = dedup_patterns
        self.config.exclude = exclude_patterns

        # Event receiver (uses EventBus subscription)
        self._event_receiver = rs.PyFileEventReceiver()

        # State
        self._running = False
        self._watcher_handle = None
        self._task: asyncio.Task[None] | None = None

        # Debounce state
        self._last_event: FileChangeEvent | None = None
        self._last_event_time: float = 0.0

        # Callback for skill changes (used by SkillManager for MCP notifications)
        self._on_change_callback: Callable[[], None] | None = None

    def set_on_change_callback(self, callback: Callable[[], None]) -> None:
        """Set a callback to be invoked when skills change.

        This callback is used by SkillManager to notify MCP clients
        when tools are added/modified/removed.

        Args:
            callback: Synchronous callback function (no args, no return)
        """
        self._on_change_callback = callback
        logger.debug("Change callback registered")

    @staticmethod
    def _normalize_relative_dir_entries(raw: Any) -> list[str]:
        if isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, (list, tuple, set)):
            values = [str(item) for item in raw]
        else:
            values = []
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = str(value or "").strip().replace("\\", "/").strip("/")
            if not normalized or normalized == ".":
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            out.append(normalized)
        return out

    @staticmethod
    def _normalize_glob_entries(raw: Any) -> list[str]:
        if isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, (list, tuple, set)):
            values = [str(item) for item in raw]
        else:
            values = []
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            token = str(value or "").strip()
            if not token:
                continue
            if token in seen:
                continue
            seen.add(token)
            out.append(token)
        return out

    def _resolve_link_graph_patterns(self) -> list[str]:
        configured = self._normalize_glob_entries(
            get_setting("link_graph.watch_patterns", DEFAULT_LINK_GRAPH_PATTERNS)
        )
        if configured:
            return configured
        return list(DEFAULT_LINK_GRAPH_PATTERNS)

    def _resolve_link_graph_root(self) -> Path:
        raw = str(get_setting("link_graph.root_dir", "") or "").strip()
        if raw:
            candidate = Path(raw).expanduser()
            if candidate.exists() and candidate.is_dir():
                return candidate.resolve()
        return self.project_root.resolve()

    def _resolve_link_graph_watch_roots(self) -> list[Path]:
        base_root = self._resolve_link_graph_root()
        explicit_watch_dirs = self._normalize_relative_dir_entries(
            get_setting("link_graph.watch_dirs", [])
        )
        if explicit_watch_dirs:
            resolved = []
            for item in explicit_watch_dirs:
                path = Path(item).expanduser()
                if not path.is_absolute():
                    path = self.project_root / item
                resolved.append(path.resolve())
            return resolved

        include_dirs = self._normalize_relative_dir_entries(
            get_setting("link_graph.include_dirs", [])
        )
        if not include_dirs and bool(get_setting("link_graph.include_dirs_auto", True)):
            include_dirs = [
                item
                for item in self._normalize_relative_dir_entries(
                    get_setting(
                        "link_graph.include_dirs_auto_candidates", DEFAULT_LINK_GRAPH_WATCH_DIRS
                    )
                )
                if (base_root / item).is_dir()
            ]

        if include_dirs:
            return [
                (base_root / item).resolve() for item in include_dirs if (base_root / item).is_dir()
            ]
        return [base_root]

    async def start(self):
        """Start watching for file changes."""
        if self._running:
            logger.warning("ReactiveSkillWatcher already running")
            return

        logger.info(
            f"[hot-reload] Watcher started (skills_dir={self.skills_dir}, patterns={self.patterns})"
        )

        # Start Rust file watcher
        try:
            self._watcher_handle = rs.py_start_file_watcher(self.config)
            logger.debug("[hot-reload] Rust file watcher started")
        except Exception as e:
            logger.error(f"Failed to start Rust file watcher: {e}")
            raise

        self._running = True
        self._task = asyncio.create_task(self._poll_events())

    async def stop(self):
        """Stop the watcher gracefully."""
        if not self._running:
            return

        logger.info("[hot-reload] Stopping watcher...")

        self._running = False

        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

        # Stop Rust watcher
        if self._watcher_handle:
            try:
                self._watcher_handle.stop()
            except Exception as e:
                logger.warning(f"Error stopping watcher handle: {e}")

        logger.info("[hot-reload] Watcher stopped")

    async def _poll_events(self):
        """Poll for file events from the Rust receiver."""
        while self._running:
            try:
                # Try to receive events (non-blocking)
                raw_events = self._event_receiver.try_recv()

                if raw_events:
                    # Process batch of events
                    events = [FileChangeEvent.from_tuple(e) for e in raw_events]
                    await self._process_batch(events)

                # Yield control and sleep
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in watcher poll loop: {e}")
                await asyncio.sleep(1.0)  # Back off on error

    async def _process_batch(self, events: list[FileChangeEvent]):
        """Process a batch of file change events."""
        logger.debug(f"[hot-reload] Batch received: {len(events)} events")
        for event in events:
            is_skill_event = self._is_skill_related(event.path)
            is_link_graph_event = self._is_link_graph_related(event.path)
            if not is_skill_event and not is_link_graph_event:
                logger.debug(f"[hot-reload] Skip (not tracked): {event.path}")
                continue

            if self._should_debounce(event):
                logger.debug(f"[hot-reload] Debounced: {event.path}")
                continue

            try:
                if is_skill_event:
                    await self._handle_event(event)
                else:
                    await self._handle_link_graph_only_event(event)
            except Exception as e:
                logger.warning(f"[hot-reload] Event failed for {event.path}: {e}")

    def _is_skill_related(self, path: str) -> bool:
        """Check if the path is relevant to skills."""
        p = Path(path)

        if not self._is_under_skills_dir(p):
            return False

        # Skip directories
        if p.is_dir():
            return False

        # Skip non-Python files (unless it's a skill metadata file)
        if p.suffix != ".py" and p.name != "SKILL.md":
            return False

        # Skip test files and private modules
        if "test" in p.name.lower() or p.name.startswith("_"):
            return False

        # Skip paths with __pycache__, .git, etc.
        return not any(part in p.parts for part in ["__pycache__", ".git", "target", ".venv"])

    def _is_under_skills_dir(self, path: Path) -> bool:
        """Whether path belongs to configured skills root."""
        try:
            resolved = path.expanduser().resolve()
            skills_root = self.skills_dir.expanduser().resolve()
            return resolved == skills_root or resolved.is_relative_to(skills_root)
        except Exception:
            return False

    def _is_under_link_graph_watch_roots(self, path: Path) -> bool:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            resolved = path.expanduser()
        for root in self._link_graph_watch_roots:
            try:
                if resolved == root or resolved.is_relative_to(root):
                    return True
            except ValueError:
                continue
        return False

    def _is_link_graph_related(self, path: str) -> bool:
        path_obj = Path(path)
        if not self._is_link_graph_candidate(path_obj):
            return False
        return self._is_under_link_graph_watch_roots(path_obj)

    def _extract_skill_name(self, path: str) -> str | None:
        """Extract skill name from file path for ReactiveSkillWatcher.

        Uses self.skills_dir (configurable) to resolve skill paths.
        """
        try:
            path_obj = Path(path).resolve()
            skills_dir_resolved = self.skills_dir.resolve()

            if path_obj.name.startswith("."):
                return None
            if path_obj.suffix in SKIP_PATTERNS:
                return None
            if "__pycache__" in path_obj.parts:
                return None

            if not path_obj.is_relative_to(skills_dir_resolved):
                return None

            relative = path_obj.relative_to(skills_dir_resolved)
            if len(relative.parts) >= 1:
                return relative.parts[0]
        except ValueError:
            pass
        return None

    def _should_debounce(self, event: FileChangeEvent) -> bool:
        """Check if event should be debounced.

        Important: DELETED events should NOT be debounced because:
        - File deletion is a unique event
        - Re-creation of a deleted file should be processed
        - We want to notify clients that the file is gone
        """
        now = time.monotonic()

        # DELETED events are never debounced (file deletion is significant)
        if event.event_type == FileChangeType.DELETED:
            return False

        # Reset debounce if enough time has passed
        if now - self._last_event_time > self.debounce_seconds:
            self._last_event = None

        # Check if this is a duplicate of the last event
        if self._last_event == event:
            self._last_event_time = now
            return True

        # Record this event
        self._last_event = event
        self._last_event_time = now
        return False

    @staticmethod
    def _is_link_graph_candidate(path: Path) -> bool:
        """Whether file changes should trigger LinkGraph delta refresh."""
        if path.name == "SKILL.md":
            return True
        return path.suffix.lower() in {".md", ".markdown", ".mdx"}

    async def _refresh_link_graph_for_event(
        self,
        path: str,
        *,
        event_type: FileChangeType,
    ) -> None:
        """Refresh LinkGraph index via common backend delta API."""
        path_obj = Path(path)
        if not self._is_link_graph_candidate(path_obj):
            return
        if event_type not in {
            FileChangeType.CREATED,
            FileChangeType.MODIFIED,
            FileChangeType.CHANGED,
            FileChangeType.DELETED,
        }:
            return
        try:
            from omni.rag.link_graph import get_link_graph_backend

            backend = get_link_graph_backend(notebook_dir=str(self.project_root))
            refresh_fn = getattr(backend, "refresh_with_delta", None)
            if not callable(refresh_fn):
                return
            result = refresh_fn([path], force_full=False)
            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, dict):
                logger.debug(
                    "[hot-reload] LinkGraph refresh: mode=%s changed=%s fallback=%s file=%s",
                    str(result.get("mode", "")),
                    int(result.get("changed_count", 0) or 0),
                    bool(result.get("fallback", False)),
                    path_obj.name,
                )
            else:
                logger.debug("[hot-reload] LinkGraph refresh complete: file=%s", path_obj.name)
        except Exception as e:
            logger.warning(f"[hot-reload] LinkGraph refresh failed for {path_obj.name}: {e}")

    async def _handle_link_graph_only_event(self, event: FileChangeEvent) -> None:
        """Handle markdown-only events for LinkGraph refresh (without skill indexing)."""
        path = Path(event.path)
        filename = path.name
        effective_event_type = event.event_type
        if (
            event.event_type
            in (
                FileChangeType.CREATED,
                FileChangeType.CHANGED,
                FileChangeType.MODIFIED,
            )
            and not path.exists()
        ):
            logger.debug(
                f"[hot-reload] File missing for {event.event_type.value}, treating as DELETED"
            )
            effective_event_type = FileChangeType.DELETED

        logger.info(f"[hot-reload] LinkGraph file change: {effective_event_type.value} {filename}")
        await self._refresh_link_graph_for_event(event.path, event_type=effective_event_type)

    async def _handle_event(self, event: FileChangeEvent):
        """Handle a single file change event."""
        path = Path(event.path)
        filename = path.name

        logger.debug(f"Processing {event.event_type.value}: {filename}")

        should_notify = False

        # [WORKAROUND] Rust watcher may send created/changed instead of deleted
        # when a file is deleted. Check file existence for these event types.
        effective_event_type = event.event_type
        if (
            event.event_type
            in (
                FileChangeType.CREATED,
                FileChangeType.CHANGED,
                FileChangeType.MODIFIED,
            )
            and not path.exists()
        ):
            logger.debug(
                f"[hot-reload] File missing for {event.event_type.value}, treating as DELETED"
            )
            effective_event_type = FileChangeType.DELETED

        skill_name = self._extract_skill_name(event.path)
        if skill_name:
            logger.info(
                f"[hot-reload] File change: {effective_event_type.value} {filename} -> skill {skill_name}"
            )

        if effective_event_type == FileChangeType.CREATED:
            count = await self.indexer.index_file(event.path)
            if count > 0:
                logger.info(f"[hot-reload] Indexed {count} tools from {filename}")
                should_notify = True

            if self._kernel is not None:
                try:
                    from omni.core.skills.discovery import SkillDiscoveryService
                    from omni.foundation.config.skills import SKILLS_DIR

                    await self.indexer.store.index_skill_tools(str(SKILLS_DIR()), "skills")
                    discovery = SkillDiscoveryService()
                    await discovery._refresh_cache()
                    logger.debug("[hot-reload] Skill discovery cache refreshed")
                except Exception as e:
                    logger.warning(f"[hot-reload] Discovery refresh failed: {e}")

        elif effective_event_type in (FileChangeType.MODIFIED, FileChangeType.CHANGED):
            count = await self.indexer.reindex_file(event.path)
            if count > 0:
                logger.info(f"[hot-reload] Reindexed {count} tools from {filename}")
                should_notify = True

        elif effective_event_type == FileChangeType.DELETED:
            count = await self.indexer.remove_file(event.path)
            try:
                has_count = count > 0
            except TypeError:
                has_count = True
            if has_count:
                logger.info(f"[hot-reload] Removed {count} tools for {filename}")
            else:
                logger.info(f"[hot-reload] File deleted: {filename}")
            should_notify = True

        elif event.event_type == FileChangeType.ERROR:
            logger.warning(f"[hot-reload] Watcher error: {event.path}")

        await self._refresh_link_graph_for_event(event.path, event_type=effective_event_type)

        if skill_name and self._kernel is not None:
            try:
                await self._kernel.reload_skill(skill_name)
            except Exception as e:
                logger.warning(f"[hot-reload] Reload failed for {skill_name}: {e}")

        if should_notify and self._on_change_callback:
            try:
                callback = self._on_change_callback
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
                logger.debug("[hot-reload] MCP clients notified")
            except Exception as e:
                logger.warning(f"[hot-reload] On-change callback error: {e}")

    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running

    async def get_stats(self) -> dict[str, Any]:
        """Get watcher statistics."""
        return {
            "project_root": str(self.project_root),
            "skills_dir": str(self.skills_dir),
            "patterns": self.patterns,
            "watch_paths": list(self.config.paths),
            "watch_patterns": list(self.config.patterns),
            "link_graph_watch_roots": [str(path) for path in self._link_graph_watch_roots],
            "running": self._running,
            "poll_interval": self.poll_interval,
        }
