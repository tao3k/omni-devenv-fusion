"""
omni.core.kernel.watcher - Rust-Native Hot Reload

Monitors the skills directory (via SKILLS_DIR()) and triggers Kernel reloads.
Uses Rust omni-io notify bindings for high-performance file watching
with EventBus integration and continuous event polling.

Also provides ReactiveSkillWatcher for skill indexing integration.
"""

from __future__ import annotations

import asyncio
import os
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


class RustKernelWatcher:
    """Manages Rust-based file watcher for Kernel-native hot reload.

    Uses omni-core-rs bindings to omni-io notify for efficient file watching
    with EventBus integration. Continuously polls for file events in a
    background task and triggers callbacks for skill changes.

    This replaces the previous watchdog-based implementation with a
    Rust-native solution for better performance and integration.
    """

    def __init__(
        self,
        skills_dir: Path,
        callback: Callable[[str], None],
        *,
        debounce_seconds: float = 0.5,
    ) -> None:
        self.skills_dir = skills_dir
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_trigger: dict[str, float] = {}
        self._watcher_handle: rs.PyFileWatcherHandle | None = None
        self._running = False
        self._watch_task: asyncio.Task[None] | None = None
        self._event_receiver: rs.PyFileEventReceiver | None = None  # Persistent receiver

    def _extract_skill_name(self, path: str) -> str | None:
        """Extract skill name from file path."""
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
                # Fallback for some edge cases where resolve() might behave differently
                # but usually resolve() fixes the /var vs /private/var issue
                return None

            relative = path_obj.relative_to(skills_dir_resolved)
            if len(relative.parts) >= 1:
                return relative.parts[0]
        except ValueError:
            pass
        return None

    def _trigger(self, skill_name: str) -> None:
        """Trigger reload with debouncing."""
        now = time.time()
        last = self._last_trigger.get(skill_name, 0)

        if now - last < self.debounce_seconds:
            return

        self._last_trigger[skill_name] = now
        logger.info(f"Detected change in skill: {skill_name}")

        # Bridge to async callback
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(lambda: self._safe_callback(skill_name))
        except RuntimeError:
            # No running loop - callback will be handled when loop starts
            pass

    def _safe_callback(self, skill_name: str) -> None:
        """Safely invoke the callback."""
        try:
            self.callback(skill_name)
        except Exception as e:
            logger.error(f"Error in hot reload callback for {skill_name}: {e}")

    async def _poll_events(self) -> None:
        """Background task to poll for file events from EventBus."""
        logger.debug("Event polling started")

        while self._running:
            try:
                # Use persistent receiver to not miss events
                if self._event_receiver is not None:
                    events = self._event_receiver.try_recv()

                    for event_type, path in events:
                        if skill_name := self._extract_skill_name(path):
                            self._trigger(skill_name)
            except Exception as e:
                logger.debug(f"Error polling file events: {e}")

            # Small sleep to prevent busy loop
            await asyncio.sleep(0.05)

        logger.debug("Event polling stopped")

    def start(self) -> None:
        """Start watching for changes using Rust bindings."""
        if not self.skills_dir.exists():
            logger.warning(f"Watcher cannot start: {self.skills_dir} does not exist.")
            return

        logger.info(f"Watching skills at (Rust): {self.skills_dir}")

        # Create persistent event receiver BEFORE starting watcher
        # This ensures we don't miss any events
        try:
            self._event_receiver = rs.PyFileEventReceiver()
        except Exception as e:
            logger.error(f"Failed to create event receiver: {e}")
            return

        # Use Rust watcher with exclude patterns matching Python side
        config = rs.PyWatcherConfig(paths=[str(self.skills_dir)])
        config.recursive = True
        config.debounce_ms = int(self.debounce_seconds * 1000)
        config.exclude = [f"**/{p}/**" if p == "__pycache__" else f"**/{p}" for p in SKIP_PATTERNS]

        try:
            self._watcher_handle = rs.py_start_file_watcher(config)
            self._running = True
            logger.info("Rust file watcher started successfully")

            # Start background polling task
            self._watch_task = asyncio.create_task(self._poll_events())
        except Exception as e:
            logger.error(f"Failed to start Rust watcher: {e}")
            self._running = False

    def stop(self) -> None:
        """Stop watching."""
        if self._running:
            logger.info("Stopping Rust watcher...")
            self._running = False

            # Cancel polling task
            if self._watch_task is not None:
                try:
                    self._watch_task.cancel()
                    # Schedule cleanup in event loop if running
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._cleanup_task())
                    except RuntimeError:
                        pass
                except Exception as e:
                    logger.debug(f"Error canceling poll task: {e}")
                self._watch_task = None

            # Stop Rust watcher
            if self._watcher_handle is not None:
                try:
                    self._watcher_handle.stop()
                except Exception as e:
                    logger.debug(f"Error stopping Rust watcher: {e}")
                self._watcher_handle = None

            logger.info("Rust watcher stopped")

    async def _cleanup_task(self) -> None:
        """Cleanup task after cancellation."""
        try:
            if self._watch_task is not None:
                await self._watch_task
        except Exception:
            pass

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        if self._watcher_handle is not None:
            return self._watcher_handle.is_running
        return self._running


# ============================================================================
# Reactive Skill Watcher (New for Holographic Registry Integration)
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

    This is the "Live-Wire" that connects Rust Sniffer to Python Indexer,
    enabling hot-reload of tools without restarting the Agent.
    """

    def __init__(
        self,
        root_dir: str,
        indexer: SkillIndexer,
        patterns: list[str] | None = None,
        debounce_seconds: float = 0.5,
        poll_interval: float = 0.5,
    ):
        """Initialize the reactive skill watcher.

        Args:
            root_dir: Directory to watch for skill changes
            indexer: SkillIndexer instance for processing events
            patterns: File patterns to watch (default: ["**/*.py"])
            debounce_seconds: Debounce delay in seconds
            poll_interval: How often to poll for events (seconds)
        """
        self.root_dir = Path(root_dir).resolve()
        self.indexer = indexer
        self.poll_interval = poll_interval
        self.debounce_seconds = debounce_seconds

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

        # Rust watcher config
        self.config = rs.PyWatcherConfig()
        self.config.paths = [str(self.root_dir)]
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

    async def start(self):
        """Start watching for file changes."""
        if self._running:
            logger.warning("ReactiveSkillWatcher already running")
            return

        logger.info(
            f"👀 Reactive Skill Watcher started",
            root=str(self.root_dir),
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
        for event in events:
            # Filter to skill-related paths
            if not self._is_skill_related(event.path):
                continue

            # Debounce duplicate events
            if self._should_debounce(event):
                logger.debug(f"Debounced event: {event.path}")
                continue

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

    def _should_debounce(self, event: FileChangeEvent) -> bool:
        """Check if event should be debounced."""
        now = time.monotonic()

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

        if event.event_type == FileChangeType.CREATED:
            count = await self.indexer.index_file(event.path)
            if count > 0:
                logger.info(f"⚡ Added {count} tools from {filename}")

        elif event.event_type in (FileChangeType.MODIFIED, FileChangeType.CHANGED):
            count = await self.indexer.reindex_file(event.path)
            if count > 0:
                logger.info(f"⚡ Hot-reloaded {count} tools from {filename}")
            else:
                logger.debug(f"No tools indexed for modified file: {filename}")

        elif event.event_type == FileChangeType.DELETED:
            count = await self.indexer.remove_file(event.path)
            logger.info(f"🗑️ Removed tools for {filename}")

        elif event.event_type == FileChangeType.ERROR:
            logger.warning(f"File watcher error: {event.path}")

    @property
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running

    async def get_stats(self) -> dict[str, Any]:
        """Get watcher statistics."""
        return {
            "root_dir": str(self.root_dir),
            "patterns": self.patterns,
            "running": self._running,
            "poll_interval": self.poll_interval,
        }
