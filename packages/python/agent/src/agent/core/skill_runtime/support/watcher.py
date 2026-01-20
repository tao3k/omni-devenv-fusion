"""
src/agent/core/skill_manager/watcher.py
 Reactive Indexing - File system watcher for auto-sync.

Uses watchdog to detect file changes in skills directory and
automatically triggers incremental sync via sync_skills().

Usage:
    omni skill watch                    # Blocking mode
    # Or integrated via MCP server lifespan
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import structlog
from ....core.vector_store import get_vector_memory
from common.skills_path import SKILLS_DIR

logger = structlog.get_logger(__name__)

# Global lock to prevent overlapping syncs
_watcher_sync_lock = False

# Thread pool for sync operations (avoids blocking watchdog thread)
_sync_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="sync")


def _shutdown_executor() -> None:
    """Shutdown the sync executor."""
    global _sync_executor
    _sync_executor.shutdown(wait=False)
    _sync_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="sync")


def _do_sync(skills_dir: str) -> dict:
    """Perform sync in thread pool (blocking but non-async)."""
    vm = get_vector_memory()
    # sync_skills is async, run it in the event loop
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(vm.sync_skills(skills_dir, "skills"))
    finally:
        loop.close()


class SkillSyncHandler(FileSystemEventHandler):
    """
    Watchdog handler that triggers incremental sync on file changes.

    Features:
    - Ignores directories and non-Python files
    - Debounces rapid changes (1s cooldown)
    - Uses thread pool for sync (non-blocking watchdog callback)
    - Prevents overlapping syncs with global lock
    """

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.last_sync = 0
        self.cooldown = 1.0  # 1 second debounce

    def on_any_event(self, event):
        global _watcher_sync_lock

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

        # Prevent overlapping syncs
        if _watcher_sync_lock:
            logger.debug("Watcher sync skipped - sync already in progress")
            return

        self.last_sync = current_time
        rel_path = str(src_path.relative_to(self.skills_dir))
        logger.info(f"file_change_detected: {rel_path}")

        _watcher_sync_lock = True
        try:
            # Syntax check pre-flight - catches SyntaxError without crashing
            if not self._validate_syntax(src_path):
                _watcher_sync_lock = False
                return

            # Submit sync to thread pool (fire-and-forget, non-blocking)
            future = _sync_executor.submit(_do_sync, self.skills_dir)

            # Log result when ready (non-blocking callback)
            future.add_done_callback(lambda f: self._on_sync_done(f, self.skills_dir))

            # Unlock immediately since we're not waiting
            _watcher_sync_lock = False
        except SyntaxError as e:
            logger.warning(f"syntax_error_in_sync: {e}")
        except Exception as e:
            logger.error(f"auto_sync_failed: {e}")
        finally:
            _watcher_sync_lock = False

    def _validate_syntax(self, file_path: Path) -> bool:
        """
        Validate Python syntax before sync.

        Returns True if the file has valid Python syntax, False if it has
        SyntaxError (which should be ignored to prevent Watcher crash).
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            compile(source, str(file_path), "exec")
            return True
        except SyntaxError as e:
            logger.warning(f"syntax_error_detected_ignoring: {file_path} - {e}")
            return False

    def _on_sync_done(self, future: concurrent.futures.Future, skills_dir: str) -> None:
        """Callback when sync completes (runs in thread pool thread)."""
        try:
            stats = future.result()
            if any(
                v > 0
                for v in [stats.get("added", 0), stats.get("modified", 0), stats.get("deleted", 0)]
            ):
                logger.info(
                    f"auto_sync_complete: +{stats.get('added', 0)} ~{stats.get('modified', 0)} -{stats.get('deleted', 0)}"
                )
        except Exception as e:
            logger.error(f"auto_sync_callback_failed: {e}")


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
        self._start_lock = threading.Lock()

    def start(self, skills_path: Optional[str] = None) -> None:
        """
        Start the watcher in a background thread.

        Args:
            skills_path: Path to skills directory. Defaults to SKILLS_DIR().
        """
        if self._running:
            logger.warning("Watcher already running")
            return

        with self._start_lock:
            # Double-check inside lock
            if self._running:
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

            # Start observer in a background thread (daemon)
            # This is needed because observer.start() can block on some platforms
            def _start_observer():
                self.observer.start()

            observer_thread = threading.Thread(
                target=_start_observer, name="watcher-observer", daemon=True
            )
            observer_thread.start()

            self._running = True
            # Show path relative to project root
            skills_path_obj = Path(skills_path)
            # Get the last 2 components: "assets/skills"
            parts = (
                skills_path_obj.parts[-2:]
                if len(skills_path_obj.parts) >= 2
                else skills_path_obj.parts
            )
            logger.info(f"👀 [Watcher] Watching: {'/'.join(parts)}")

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
            # Join with timeout
            self.observer.join(timeout=1.0)
            self.observer = None

        # Shutdown executor
        _shutdown_executor()

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
