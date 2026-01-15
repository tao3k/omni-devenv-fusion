"""
src/agent/core/skill_manager/watcher.py
Phase 65: Reactive Indexing - File system watcher for auto-sync.

Uses watchdog to detect file changes in skills directory and
automatically triggers incremental sync via sync_skills().

Usage:
    omni skill watch                    # Blocking mode
    # Or integrated via MCP server lifespan
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ...core.vector_store import get_vector_memory
from common.skills_path import SKILLS_DIR

logger = logging.getLogger(__name__)


class SkillSyncHandler(FileSystemEventHandler):
    """
    Watchdog handler that triggers incremental sync on file changes.

    Features:
    - Ignores directories and non-Python files
    - Debounces rapid changes (1s cooldown)
    - Thread-safe: uses fresh VectorStore instance per sync
    """

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.last_sync = 0
        self.cooldown = 1.0  # 1 second debounce

    def on_any_event(self, event):
        if event.is_directory:
            return

        src_path = Path(event.src_path)
        filename = src_path.name

        # Ignore non-Python files and special files
        if not filename.endswith(".py"):
            return
        if filename.startswith("_") or filename.startswith("."):
            return

        # Debounce: ignore events within cooldown period
        current_time = time.time()
        if current_time - self.last_sync < self.cooldown:
            return

        self.last_sync = current_time
        rel_path = str(src_path.relative_to(self.skills_dir))
        logger.info(f"file_change_detected: {rel_path}")

        try:
            # Use fresh VectorStore instance (thread-safe)
            # Note: sync_skills is async, so we need to run it in an event loop
            vm = get_vector_memory()
            stats = asyncio.run(vm.sync_skills(self.skills_dir, "skills"))

            if any(
                v > 0
                for v in [stats.get("added", 0), stats.get("modified", 0), stats.get("deleted", 0)]
            ):
                logger.info(
                    f"auto_sync_complete: +{stats.get('added', 0)} ~{stats.get('modified', 0)} -{stats.get('deleted', 0)}"
                )
        except Exception as e:
            logger.error(f"auto_sync_failed: {e}")


class BackgroundWatcher:
    """
    Manages the watchdog observer lifecycle.

    Can be used in two modes:
    1. Blocking: run() blocks until KeyboardInterrupt
    2. Daemon: start() runs in background thread
    """

    def __init__(self):
        self.observer: Optional[Observer] = None
        self._running = False

    def start(self, skills_path: Optional[str] = None) -> None:
        """
        Start the watcher in a background thread.

        Args:
            skills_path: Path to skills directory. Defaults to SKILLS_DIR().
        """
        if self._running:
            logger.warning("Watcher already running")
            return

        if skills_path is None:
            skills_path = str(SKILLS_DIR())

        skills_dir = Path(skills_path)
        if not skills_dir.exists():
            logger.warning(f"skills_dir_not_found: {skills_path}")
            return

        # Create handler and observer
        event_handler = SkillSyncHandler(skills_path)
        self.observer = Observer()
        self.observer.schedule(event_handler, skills_path, recursive=True)
        self.observer.start()

        self._running = True
        logger.info(f"Skill Watcher started: {skills_path}")

    def run(self, skills_path: Optional[str] = None) -> None:
        """
        Run the watcher in blocking mode (until KeyboardInterrupt).

        Args:
            skills_path: Path to skills directory.
        """
        self.start(skills_path)

        logger.info("Skill Watcher running (Ctrl+C to stop)...")
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop the watcher and join the observer thread."""
        if not self._running:
            return

        logger.info("Stopping Skill Watcher...")
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        self._running = False
        logger.info("Skill Watcher stopped")

    @property
    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._running


# Singleton instance for MCP server integration
_watcher_instance: Optional[BackgroundWatcher] = None


def get_watcher() -> BackgroundWatcher:
    """Get the global watcher instance."""
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = BackgroundWatcher()
    return _watcher_instance


def start_global_watcher() -> BackgroundWatcher:
    """Start the global watcher instance."""
    watcher = get_watcher()
    watcher.start()
    return watcher


def stop_global_watcher() -> None:
    """Stop the global watcher instance."""
    global _watcher_instance
    if _watcher_instance is not None:
        _watcher_instance.stop()
        _watcher_instance = None


__all__ = [
    "SkillSyncHandler",
    "BackgroundWatcher",
    "get_watcher",
    "start_global_watcher",
    "stop_global_watcher",
]
