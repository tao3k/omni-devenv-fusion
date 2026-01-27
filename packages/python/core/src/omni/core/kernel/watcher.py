"""
omni.core.kernel.watcher - Rust-Native Hot Reload

Monitors the skills directory (via SKILLS_DIR()) and triggers Kernel reloads.
Uses Rust omni-io notify bindings for high-performance file watching
with EventBus integration and continuous event polling.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import omni_core_rs as rs

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.watcher")

# Skip these file patterns (mirrors Rust exclude patterns)
SKIP_PATTERNS = {".pyc", ".pyo", ".pyd", ".swp", ".swo", ".tmp", "__pycache__", ".git"}


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
