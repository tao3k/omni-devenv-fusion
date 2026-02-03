"""
omni.core.kernel.watcher - Reactive Skill Watcher (Live-Wire)

Monitors the skills directory (via SKILLS_DIR()) and triggers incremental
indexing upon changes. Uses Rust omni-io notify bindings for high-performance
file watching with EventBus integration.

Features:
- Debouncing: Avoids duplicate events for the same file
- Pattern filtering: Only processes relevant file types
- Callback support: Fires callbacks when skills change (for MCP notifications)
- Kernel integration: Automatically reloads skills when scripts change

This is the "Live-Wire" that connects Rust Sniffer to Python Indexer,
enabling hot-reload of tools without restarting the Agent.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import omni_core_rs as rs

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.watcher")

# Skip these file patterns (mirrors Rust exclude patterns)
SKIP_PATTERNS = {".pyc", ".pyo", ".pyd", ".swp", ".swo", ".tmp", "__pycache__", ".git"}


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
    def from_tuple(cls, data: tuple[str, str]) -> "FileChangeEvent":
        """Create from (event_type, path) tuple."""
        return cls(
            event_type=FileChangeType(data[0]),
            path=data[1],
            is_directory=False,
        )


# ============================================================================
# Reactive Skill Watcher (Live-Wire)
# ============================================================================

from omni.core.skills.indexer import SkillIndexer


class ReactiveSkillWatcher:
    """
    Monitors the skill directory and triggers incremental indexing upon changes.

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
        kernel: "Kernel | None" = None,
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
        # skills_dir from config (user-configurable via settings.yaml -> assets.skills_dir)
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

        # Rust watcher config - watch skills_dir (user-configurable)
        self.config = rs.PyWatcherConfig()
        self.config.paths = [str(self.skills_dir)]
        self.config.recursive = True
        self.config.debounce_ms = int(debounce_seconds * 1000)
        self.config.patterns = self.patterns
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

    async def start(self):
        """Start watching for file changes."""
        if self._running:
            logger.warning("ReactiveSkillWatcher already running")
            return

        logger.info(
            f"👀 Reactive Skill Watcher started",
            skills_dir=str(self.skills_dir),
            patterns=self.patterns,
        )

        # Start Rust file watcher
        try:
            self._watcher_handle = rs.py_start_file_watcher(self.config)
            logger.info("Rust file watcher started successfully")
        except Exception as e:
            logger.error(f"Failed to start Rust file watcher: {e}")
            raise

        self._running = True
        self._task = asyncio.create_task(self._poll_events())

    async def stop(self):
        """Stop the watcher gracefully."""
        if not self._running:
            return

        logger.info("Stopping Reactive Skill Watcher...")

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Stop Rust watcher
        if self._watcher_handle:
            try:
                self._watcher_handle.stop()
            except Exception as e:
                logger.warning(f"Error stopping watcher handle: {e}")

        logger.info("Reactive Skill Watcher stopped")

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
        logger.info(f"🗑️ [BATCH] Received {len(events)} events")
        for event in events:
            logger.info(f"🗑️ [BATCH] Processing event: {event.event_type.value} {event.path}")
            # Filter to skill-related paths
            if not self._is_skill_related(event.path):
                logger.info(f"🗑️ [BATCH] Skipped (not skill-related): {event.path}")
                continue

            # Debounce duplicate events
            if self._should_debounce(event):
                logger.debug(f"Debounced event: {event.path}")
                continue

            logger.info(f"🗑️ [BATCH] Calling _handle_event for {event.event_type.value}")
            try:
                await self._handle_event(event)
            except Exception as e:
                logger.warning(f"Failed to process event for {event.path}: {e}")

    def _is_skill_related(self, path: str) -> bool:
        """Check if the path is relevant to skills."""
        p = Path(path)

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
        if any(part in p.parts for part in ["__pycache__", ".git", "target", ".venv"]):
            return False

        return True

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

    async def _handle_event(self, event: FileChangeEvent):
        """Handle a single file change event."""
        path = Path(event.path)
        filename = path.name

        logger.debug(f"Processing {event.event_type.value}: {filename}")

        should_notify = False

        # [WORKAROUND] Rust watcher may send created/changed instead of deleted
        # when a file is deleted. Check file existence for these event types.
        effective_event_type = event.event_type
        if event.event_type in (FileChangeType.CREATED, FileChangeType.CHANGED, FileChangeType.MODIFIED):
            if not path.exists():
                logger.info(f"🗑️ [WORKAROUND] File doesn't exist for {event.event_type.value}, treating as DELETED")
                effective_event_type = FileChangeType.DELETED

        if effective_event_type == FileChangeType.CREATED:
            count = await self.indexer.index_file(event.path)
            if count > 0:
                logger.info(f"⚡ Added {count} tools from {filename}")
                should_notify = True

        elif effective_event_type in (FileChangeType.MODIFIED, FileChangeType.CHANGED):
            count = await self.indexer.reindex_file(event.path)
            if count > 0:
                logger.info(f"⚡ Hot-reloaded {count} tools from {filename}")
                should_notify = True
            else:
                logger.debug(f"No tools indexed for modified file: {filename}")

        elif effective_event_type == FileChangeType.DELETED:
            # Always notify on deletion - even if remove returns 0,
            # the file change itself is significant
            logger.info(f"🗑️ Processing DELETED event for {filename}")
            count = await self.indexer.remove_file(event.path)
            if count > 0:
                logger.info(f"🗑️ Removed {count} tools for {filename}")
            else:
                logger.info(f"🗑️ File deleted: {filename}")
            should_notify = True
            logger.info(f"🗑️ should_notify set to True for DELETED event")

        elif event.event_type == FileChangeType.ERROR:
            logger.warning(f"File watcher error: {event.path}")

        # Bridge to Kernel for skill reload (Live-Wire Discovery Loop)
        skill_name = self._extract_skill_name(event.path)
        logger.info(f"🗑️ [DEBUG] skill_name={skill_name}, _kernel={self._kernel is not None}")
        if skill_name and self._kernel is not None:
            try:
                logger.info(f"🗑️ [DEBUG] Calling kernel.reload_skill({skill_name})")
                await self._kernel.reload_skill(skill_name)
                logger.info(f"🗑️ [DEBUG] kernel.reload_skill({skill_name}) completed")
            except Exception as e:
                logger.warning(f"Failed to reload skill {skill_name}: {e}")

        # Notify MCP clients if tools were added/modified/removed
        logger.info(f"🗑️ [DEBUG] should_notify={should_notify}, callback={self._on_change_callback is not None}")
        if should_notify and self._on_change_callback:
            # Use effective_event_type for accurate logging
            log_event_type = effective_event_type.value
            logger.info(f"🔔 Triggering on_change_callback for {log_event_type}: {filename}")
            try:
                # Support both sync and async callbacks
                callback = self._on_change_callback
                logger.info(f"🔔 [DEBUG] callback type: {type(callback).__name__}")
                if asyncio.iscoroutinefunction(callback):
                    logger.info(f"🔔 [DEBUG] Creating task for async callback")
                    # Run async callback in background task
                    asyncio.create_task(callback())
                else:
                    logger.info(f"🔔 [DEBUG] Calling sync callback directly")
                    callback()
            except Exception as e:
                logger.warning(f"Error in on_change callback: {e}")

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
            "running": self._running,
            "poll_interval": self.poll_interval,
        }
