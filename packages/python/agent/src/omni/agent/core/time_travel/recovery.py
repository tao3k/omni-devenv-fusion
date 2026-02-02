"""AutoFixLoop - Anti-Fragile Workflow with Time-Travel Recovery.

Provides automatic recovery from failures by leveraging TimeTraveler
to fork from historical checkpoints and apply corrections.
Includes Context Pruning for memory-efficient recovery.

Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                        AutoFixLoop                                  │
    ├─────────────────────────────────────────────────────────────────────┤
    │  1. Execute workflow                                                │
    │  2. Validate output                                                 │
    │  3. If failed: Context Pruning (compress history)                   │
    │  4. TimeTravel to previous checkpoint                               │
    │  5. Apply correction patch                                          │
    │  6. Retry from forked state                                         │
    └─────────────────────────────────────────────────────────────────────┘

Features:
    - Uses Rust omni-tokenizer for fast token counting
    - Prunes old tool outputs to save context
    - Creates "Lesson Learned" summary instead of full error trace

Example:
    >>> from omni.agent.core.time_travel.recovery import AutoFixLoop
    >>> from omni.agent.core.time_travel.traveler import TimeTraveler
    >>> from omni.agent.core.context.pruner import ContextPruner
    >>> from omni.langgraph.checkpoint.lance import create_checkpointer
    >>>
    >>> checkpointer = create_checkpointer()
    >>> traveler = TimeTraveler(checkpointer)
    >>> pruner = ContextPruner(window_size=4)
    >>> fixer = AutoFixLoop(traveler, pruner, max_retries=2)
    >>>
    >>> result = await fixer.run(
    ...     graph,
    ...     {"task": "write code"},
    ...     config,
    ...     validator=lambda x: x.get("success")
    ... )
"""

import logging
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from langchain_core.runnables import RunnableConfig

from .traveler import TimeTraveler
from ..context.pruner import ContextPruner

# Type alias for correction strategy
CorrectionStrategy = Callable[
    [Exception, Dict[str, Any], Optional[List[Dict[str, str]]]], Dict[str, Any]
]

logger = logging.getLogger(__name__)


class AutoFixLoop:
    """Executes a workflow with automatic time-travel recovery.

    This is the "Anti-Fragile" wrapper for LangGraph workflows with
    "Cognitive Re-anchoring" for memory-efficient recovery.

    When execution fails or validation fails, it automatically:
    1. Prunes context using Rust tokenizer
    2. Travels back to a historical checkpoint
    3. Applies a compressed correction patch
    4. Retries from the forked state

    Events emitted:
        - autofix/attempt: When a retry attempt starts
        - autofix/prune: When context pruning is applied
        - autofix/travel: When time travel is triggered
        - autofix/recover: When recovery is successful
        - autofix/fail: When all retries are exhausted

    Attributes:
        traveler: The TimeTraveler instance for checkpoint operations.
        pruner: The ContextPruner for memory-efficient recovery.
        max_retries: Maximum number of recovery attempts (default: 2).
        default_correction_strategy: Strategy for generating correction patches.
    """

    def __init__(
        self,
        traveler: TimeTraveler,
        pruner: Optional[ContextPruner] = None,
        max_retries: int = 2,
        default_correction_strategy: Optional[CorrectionStrategy] = None,
    ) -> None:
        """Initialize the AutoFixLoop.

        Args:
            traveler: TimeTraveler instance for checkpoint operations.
            pruner: Optional ContextPruner for memory-efficient recovery.
                    If not provided, creates a default one.
            max_retries: Maximum number of recovery attempts (default: 2).
            default_correction_strategy: Optional function to generate correction patches.
                Takes (exception, current_state) or (exception, current_state, pruned_messages)
                and returns patch dict.
        """
        self.traveler = traveler
        self.pruner = pruner or ContextPruner(window_size=4)
        self.max_retries = max_retries
        self.default_correction_strategy: CorrectionStrategy = (
            default_correction_strategy or self._default_strategy
        )

    def _default_strategy(
        self,
        error: Exception,
        current_state: Dict[str, Any],
        pruned_messages: Optional[List[Dict[str, str]]],
    ) -> Dict[str, Any]:
        """Default strategy for generating correction patches.

        Creates a compressed message patch that includes a "Lesson Learned"
        summary instead of the full error trace.

        Args:
            error: The exception that caused the failure.
            current_state: The current workflow state.
            pruned_messages: Optional pre-pruned messages from ContextPruner.

        Returns:
            A patch dictionary to apply to the forked checkpoint.
        """
        error_msg = str(error)
        error_type = type(error).__name__

        # Use pre-pruned messages if available
        messages = pruned_messages or current_state.get("messages", [])

        # Create "Lesson Learned" summary
        lesson = (
            f"[AUTO-FIX RECOVERY - Attempt Failed]\n"
            f"Error: {error_type}: {error_msg}\n\n"
            f"The previous attempt failed. We have rolled back to a previous checkpoint "
            f"and compressed the conversation history to save tokens.\n\n"
            f"Please analyze the error and try a different approach. "
            f"Consider what went wrong and how to avoid the same mistake."
        )

        return {
            "messages": messages
            + [
                {
                    "role": "user",
                    "content": lesson,
                }
            ]
        }

    def _prune_context(
        self,
        messages: List[Dict[str, str]],
        error: str,
    ) -> List[Dict[str, str]]:
        """Prune context using Rust tokenizer.

        Compresses the message history to save tokens while preserving
        important context (system messages, recent conversation).

        Args:
            messages: Current message history.
            error: The error that occurred.

        Returns:
            Pruned message list for retry.
        """
        logger.info(
            f"[AutoFixLoop] Pruning context before retry "
            f"(original: {self.pruner.count_messages(messages)} tokens)"
        )

        # Use the specialized prune_for_retry method
        pruned = self.pruner.prune_for_retry(messages, error)

        logger.info(
            f"[AutoFixLoop] Context pruned "
            f"(compressed: {self.pruner.count_messages(pruned)} tokens)"
        )

        return pruned

    async def run(
        self,
        graph: Any,
        input_data: Any,
        config: RunnableConfig,
        validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
        on_attempt: Optional[Callable[[int, Optional[Exception]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute workflow with automatic recovery and context pruning.

        Uses ContextPruner to compress history before retry.

        Args:
            graph: The LangGraph to execute.
            input_data: Initial input data.
            config: RunnableConfig with thread_id.
            validator: Optional function to validate output. Takes result dict,
                returns True if valid, False to trigger recovery.
            on_attempt: Optional callback called on each attempt (attempt_num, error).

        Returns:
            The final result dictionary.

        Raises:
            Exception: If all recovery attempts fail.
        """
        thread_id = config["configurable"]["thread_id"]
        current_config = config
        current_input = input_data
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            last_error = None

            try:
                # Execute workflow
                result = await graph.ainvoke(current_input, current_config)

                # Validate output
                if validator and not validator(result):
                    raise ValueError(f"Output validation failed: {result}")

                # Success!
                if attempt > 0:
                    compression = self.pruner.estimate_compression_ratio(result.get("messages", []))
                    logger.info(
                        f"[AutoFixLoop] Recovery successful on attempt {attempt + 1} "
                        f"(compression ratio: {compression:.2f}x)"
                    )
                return result

            except Exception as e:
                last_error = e
                if attempt >= self.max_retries:
                    logger.error(f"[AutoFixLoop] All {self.max_retries + 1} attempts failed")
                    raise

                logger.warning(
                    f"[AutoFixLoop] Attempt {attempt + 1} failed: {e}. "
                    f"Engaging time-travel recovery with context pruning..."
                )

                # Notify callback
                if on_attempt:
                    on_attempt(attempt, e)

                # Prune context before retry
                pruned_messages = None
                try:
                    # Get current state for message history
                    current_state = await graph.aget_state(current_config)
                    messages = current_state.values.get("messages", [])
                    if messages:
                        pruned_messages = self._prune_context(messages, str(e))
                        logger.debug(
                            f"[AutoFixLoop] Pruned {len(messages)} -> {len(pruned_messages)} messages"
                        )
                except Exception as prune_err:
                    logger.warning(f"[AutoFixLoop] Context pruning failed: {prune_err}")
                    pruned_messages = None

                # Generate correction patch
                try:
                    current_state = await graph.aget_state(current_config)
                    patch = self.default_correction_strategy(
                        e, dict(current_state.values), pruned_messages
                    )
                except Exception:
                    # Fallback if state retrieval fails
                    patch = self.default_correction_strategy(e, {}, pruned_messages)

                # Execute time travel
                try:
                    current_config = await self.traveler.fork_and_correct(
                        graph,
                        thread_id,
                        steps_back=1,
                        patch_state=patch,
                        reason=f"AutoFix: {type(e).__name__}",
                    )
                    current_input = None  # Resume from new state

                except Exception as travel_err:
                    logger.critical(f"[AutoFixLoop] Time travel failed: {travel_err}")
                    raise e

                # Notify recovery
                await self._emit_recovery_event(
                    "autofix/recover",
                    {
                        "attempt": attempt + 1,
                        "parent_checkpoint": current_config["configurable"]["checkpoint_id"],
                        "error": str(e),
                        "thread_id": thread_id,
                    },
                )

        # Should never reach here
        raise last_error or RuntimeError("Unknown error in AutoFixLoop")

    async def run_streaming(
        self,
        graph: Any,
        input_data: Any,
        config: RunnableConfig,
        validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute workflow with streaming and automatic recovery.

        Yields:
            Chunks from the graph execution.

        Raises:
            Exception: If all recovery attempts fail.
        """
        thread_id = config["configurable"]["thread_id"]
        current_config = config
        current_input = input_data
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            last_error = None

            try:
                async for chunk in graph.astream_events(current_input, current_config):
                    yield chunk

                # Get final result from config
                final_result = await graph.aget_state(current_config)

                # Validate
                if validator and not validator(final_result.values):
                    raise ValueError(f"Output validation failed")

                if attempt > 0:
                    logger.info(f"[AutoFixLoop] Recovery successful on attempt {attempt + 1}")
                return

            except Exception as e:
                last_error = e
                if attempt >= self.max_retries:
                    raise

                logger.warning(f"[AutoFixLoop] Streaming attempt {attempt + 1} failed: {e}")

                # Prune context
                try:
                    current_state = await graph.aget_state(current_config)
                    messages = current_state.values.get("messages", [])
                    if messages:
                        pruned_messages = self._prune_context(messages, str(e))
                        patch = self.default_correction_strategy(
                            e, dict(current_state.values), pruned_messages
                        )
                    else:
                        patch = self.default_correction_strategy(e, {}, None)
                except Exception:
                    patch = self.default_correction_strategy(e, {}, None)

                # Time travel
                current_config = await self.traveler.fork_and_correct(
                    graph,
                    thread_id,
                    steps_back=1,
                    patch_state=patch,
                    reason=f"AutoFix: {type(e).__name__}",
                )

                current_input = None

    async def _emit_recovery_event(
        self,
        topic: str,
        payload: Dict[str, Any],
    ) -> None:
        """Emit recovery event to TUI.

        Args:
            topic: Event topic.
            payload: Event payload.
        """
        try:
            await self.traveler._emit_tui_event(topic, payload)
        except Exception:
            pass  # Silently ignore TUI errors


async def create_recovery_workflow(
    graph: Any,
    thread_id: str,
    max_retries: int = 2,
    checkpointer=None,
    pruner: Optional[ContextPruner] = None,
) -> AutoFixLoop:
    """Factory function to create an AutoFixLoop with proper setup.

    Args:
        graph: The LangGraph to wrap.
        thread_id: The thread ID for checkpoint tracking.
        max_retries: Maximum recovery attempts.
        checkpointer: Optional custom checkpointer.
        pruner: Optional custom ContextPruner.

    Returns:
        Configured AutoFixLoop instance.
    """
    from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

    if checkpointer is None:
        checkpointer = RustLanceCheckpointSaver()

    traveler = TimeTraveler(checkpointer)
    pruner = pruner or ContextPruner(window_size=4)
    return AutoFixLoop(traveler, pruner, max_retries=max_retries)
