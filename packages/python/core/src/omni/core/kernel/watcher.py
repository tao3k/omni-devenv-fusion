"""
omni.core.kernel.watcher - Kernel Native Hot Reload

Monitors the assets/skills directory and triggers Kernel reloads.
Handles the bridge between watchdog's threading model and asyncio.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.watcher")

# Skip these file patterns
SKIP_PATTERNS = {".pyc", ".pyo", ".pyd", ".swp", ".swo", ".tmp", "__pycache__", ".git"}


class SkillChangeHandler(FileSystemEventHandler):
    """Handles file system events in the skills directory."""

    def __init__(
        self, skills_dir: Path, callback: Callable[[str], None], *, debounce_seconds: float = 0.5
    ) -> None:
        self.skills_dir = skills_dir
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_trigger: dict[str, float] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop | None:
        """Get the current event loop safely."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        return self._loop

    def _should_skip(self, path: Path) -> bool:
        """Check if the file should be skipped."""
        if path.name.startswith("."):
            return True
        if path.suffix in SKIP_PATTERNS:
            return True
        if "__pycache__" in path.parts:
            return True
        return False

    def _process(self, event: FileSystemEvent) -> None:
        """Process a file system event."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if self._should_skip(path):
            return

        # Determine which skill changed
        # path format: .../assets/skills/<skill_name>/...
        try:
            relative = path.relative_to(self.skills_dir)
            if len(relative.parts) >= 1:
                skill_name = relative.parts[0]
                self._trigger(skill_name)
        except ValueError:
            pass  # Not in skills dir

    def _trigger(self, skill_name: str) -> None:
        """Trigger reload with debouncing."""
        now = time.time()
        last = self._last_trigger.get(skill_name, 0)

        if now - last < self.debounce_seconds:
            return

        self._last_trigger[skill_name] = now
        logger.info(f"⚡ Detected change in skill: {skill_name}")

        # Bridge to async callback
        loop = self._get_loop()
        if loop and loop.is_running():
            loop.call_soon_threadsafe(lambda: self._safe_callback(skill_name))
        else:
            # No loop running - schedule for when loop is available
            logger.debug(f"No running loop for hot reload of {skill_name}")

    def _safe_callback(self, skill_name: str) -> None:
        """Safely invoke the callback."""
        try:
            self.callback(skill_name)
        except Exception as e:
            logger.error(f"Error in hot reload callback for {skill_name}: {e}")

    def on_modified(self, event: FileSystemEvent) -> None:
        self._process(event)

    def on_created(self, event: FileSystemEvent) -> None:
        self._process(event)


class KernelWatcher:
    """Manages the watchdog observer for Kernel-native hot reload."""

    def __init__(
        self,
        skills_dir: Path,
        callback: Callable[[str], None],
        *,
        debounce_seconds: float = 0.5,
    ) -> None:
        self.observer = Observer()
        self.handler = SkillChangeHandler(skills_dir, callback, debounce_seconds=debounce_seconds)
        self.skills_dir = skills_dir
        self._running = False

    def start(self) -> None:
        """Start watching for changes."""
        if not self.skills_dir.exists():
            logger.warning(f"Watcher cannot start: {self.skills_dir} does not exist.")
            return

        logger.info(f"👀 Watching skills at: {self.skills_dir}")
        self.observer.schedule(self.handler, str(self.skills_dir), recursive=True)
        self.observer.start()
        self._running = True

    def stop(self) -> None:
        """Stop watching."""
        if self._running:
            logger.info("👀 Stopping watcher...")
            self.observer.stop()
            self.observer.join()
            self._running = False

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running
