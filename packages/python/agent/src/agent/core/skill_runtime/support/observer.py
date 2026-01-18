"""
src/agent/core/skill_manager/observer.py
/36.5: Observer pattern and debounced notifications.

Contains:
- Observer pattern for hot-reload change notifications
- Debounced notifications (200ms batching)
- GC protection for background tasks
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable


class ObserverMixin:
    """
    Mixin providing observer pattern and debounced notifications.

    Used by SkillManager to notify subscribers of skill changes.
    """

    # These should be defined in the parent class __slots__
    _observers: list[Callable[[dict[str, str]], Any]]
    _pending_change_task: asyncio.Task | None
    _pending_changes: list[tuple[str, str]]
    _background_tasks: set[asyncio.Task]

    def subscribe(self, callback: Callable[[dict[str, str]], Any]) -> None:
        """
        Register a callback to be invoked when skills change.

        The callback will be called after:
        - A skill is loaded (load_skill)
        - A skill is unloaded (unload)
        - A skill is reloaded (reload)

        Callback signature: callback(skill_changes: dict[str, str]) -> None
        - skill_changes: Dict mapping skill_name to change_type ("load", "unload", "reload")
          The callback receives a batch of all changes, not individual notifications.

        Args:
            callback: Callable that takes a dict of skill changes. Can be sync or async.
        """
        from ..protocols import _get_logger

        # Prevent duplicate registrations
        if callback in self._observers:
            _get_logger().debug("Observer already registered, skipping duplicate")
            return

        self._observers.append(callback)
        _get_logger().info("Observer subscribed", total=len(self._observers))

    def _fire_and_forget(self, coro: asyncio.coroutine) -> asyncio.Task:
        """
         Fire-and-forget with GC protection.

        Creates a background task and adds it to _background_tasks set.
        When the task completes, it's automatically removed from the set.
        This prevents Python's GC from collecting the task prematurely.

        Args:
            coro: The coroutine to execute

        Returns:
            The created Task (can be ignored if not needed)
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _debounced_notify(self) -> None:
        """
         Actually notify all observers after debounce delay.

        This is called after 200ms debounce delay to batch multiple
        skill changes into a single notification.
        """
        from ..protocols import _get_logger

        await asyncio.sleep(0.2)  # 200ms debounce

        # Check if there are still observers to notify
        if not self._observers:
            self._pending_changes.clear()
            return

        # Get the unique skill changes (deduped by skill_name)
        # Group by skill_name, keeping only the last change_type for each skill
        skill_changes: dict[str, str] = {}
        for skill_name, change_type in self._pending_changes:
            skill_changes[skill_name] = change_type
        self._pending_changes.clear()

        _get_logger().info("🔔 [Debounce] Notifying observers", skills=list(skill_changes.keys()))

        # Call each observer ONCE with the batch of changes
        for cb in self._observers:
            try:
                if asyncio.iscoroutinefunction(cb):
                    # Pass the batch of changes to the callback
                    # Callback receives: dict of skill_name -> change_type
                    self._fire_and_forget(cb(skill_changes))
                else:
                    cb(skill_changes)
            except Exception as e:
                _get_logger().error("Observer callback failed", error=str(e))

        self._pending_change_task = None

    def _notify_change(self, skill_name: str, change_type: str = "load") -> None:
        """
         Debounced notification of skill change.

        Instead of notifying immediately, this batches multiple rapid
        skill changes (e.g., loading 10 skills) into a single notification
        after 200ms delay.

        Args:
            skill_name: Name of the skill that changed
            change_type: "load", "unload", or "reload"

        This triggers MCP Server to send_tool_list_changed() so Claude
        refreshes its available tools.
        """
        from ..protocols import _get_logger

        # Add to pending changes
        self._pending_changes.append((skill_name, change_type))

        # Cancel any pending notification
        if self._pending_change_task is not None:
            self._pending_change_task.cancel()
            self._pending_change_task = None

        # Schedule new debounced notification
        try:
            loop = asyncio.get_running_loop()
            self._pending_change_task = loop.create_task(self._debounced_notify())
        except RuntimeError:
            # No event loop running - notify immediately
            for cb in self._observers:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        # Run in new event loop
                        asyncio.run(cb(skill_name, change_type))
                    else:
                        cb(skill_name, change_type)
                except Exception as e:
                    _get_logger().error("Observer callback failed", error=str(e))


__all__ = [
    "ObserverMixin",
]
