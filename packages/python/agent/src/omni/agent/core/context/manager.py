"""
manager.py - Context Lifecycle Management

Orchestrates memory retention, pruning, and state updates.
Provides a clean API for the omni_loop to manage conversation history.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from .pruner import ContextPruner


class Turn(BaseModel):
    """Represents a single conversation turn (user + assistant)."""

    user_message: dict[str, Any]
    assistant_message: dict[str, Any]
    timestamp: datetime = datetime.now()
    metadata: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "user": self.user_message,
            "assistant": self.assistant_message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ContextManager:
    """
    Manages conversation context with smart pruning and lifecycle tracking.

    Design Principles:
    - Separate system prompts from chat history
    - Track turns for coherent pruning
    - Provide snapshot capability for serialization
    """

    def __init__(
        self,
        pruner: ContextPruner | None = None,
        system_prompts: list[dict[str, Any]] | None = None,
    ):
        """
        Initialize the context manager.

        Args:
            pruner: ContextPruner instance. Creates default if None.
            system_prompts: Initial system messages to preload.
        """
        self.pruner = pruner or ContextPruner()
        self.system_prompts: list[dict[str, Any]] = system_prompts or []
        self.turns: list[Turn] = []
        self._turn_count = 0
        self.summary: str | None = None  # Persistent summary from compression

    @property
    def turn_count(self) -> int:
        """Get total number of completed turns."""
        return self._turn_count

    def add_system_message(self, content: str, **kwargs) -> None:
        """Add a system message to the persistent system context."""
        msg = {"role": "system", "content": content, **kwargs}
        self.system_prompts.append(msg)

    def get_system_prompt(self) -> str | None:
        """
        Get the primary system prompt content.

        Returns:
            The content of the first system message, or None if no system prompts exist.
        """
        if self.system_prompts:
            return self.system_prompts[0].get("content")
        return None

    def add_user_message(self, content: str, **kwargs) -> None:
        """Add a user message (opens a new turn)."""
        turn = Turn(
            user_message={"role": "user", "content": content, **kwargs},
            assistant_message={"role": "assistant", "content": ""},  # Placeholder
        )
        self.turns.append(turn)

    def update_last_assistant(self, content: str, **kwargs) -> None:
        """Update the assistant message for the most recent turn."""
        if not self.turns:
            raise RuntimeError("No active turn to update. Call add_user_message first.")
        self.turns[-1].assistant_message = {"role": "assistant", "content": content, **kwargs}
        self._turn_count += 1

    def add_turn(self, user_content: str, assistant_content: str, **kwargs) -> None:
        """Add a complete User-AI turn in one call."""
        turn = Turn(
            user_message={"role": "user", "content": user_content, **kwargs},
            assistant_message={"role": "assistant", "content": assistant_content, **kwargs},
        )
        self.turns.append(turn)
        self._turn_count += 1

    def get_active_context(
        self,
        strategy: Literal["pruned", "full", "recent"] = "pruned",
    ) -> list[dict[str, Any]]:
        """
        Get the context ready for LLM inference.

        Args:
            strategy: Context retrieval strategy.
                - "pruned": Apply smart trimming (default)
                - "full": Return all messages (may exceed context window)
                - "recent": Return only last N turns (no system)

        Returns:
            Message list ready for LLM (user/assistant roles only).
            System prompts are handled separately via get_system_prompt().
        """
        # Build message list with user/assistant roles only
        # System prompts are managed separately and passed via system_prompt param
        messages: list[dict[str, Any]] = []

        # Add chat messages as flat list
        for turn in self.turns:
            messages.append(turn.user_message)
            if turn.assistant_message["content"]:  # Only if assistant has responded
                messages.append(turn.assistant_message)

        if strategy == "full":
            return messages

        if strategy == "recent":
            retain = self.pruner.config.retained_turns
            # Keep only last N turns (2 messages per turn)
            cutoff = len(messages) - (retain * 2)
            if cutoff > 0:
                return messages[-retain * 2 :]
            return messages

        # Default: pruned strategy
        return self.pruner.prune(messages)

    def get_summary_candidates(self, max_candidates: int = 5) -> list[dict[str, Any]]:
        """Get messages that are good candidates for summarization."""
        messages = self.get_active_context(strategy="full")
        return self.pruner.get_summary_candidates(messages, max_candidates)

    def prune_with_summary(
        self,
        summary_content: str,
        preserve_turns: int | None = None,
    ) -> int:
        """
        Prune old turns and insert a summary.

        Args:
            summary_content: The summary text to insert.
            preserve_turns: Number of recent turns to keep. Uses config default if None.

        Returns:
            Number of messages pruned.
        """
        old_count = len(self.turns)
        retain = preserve_turns or self.pruner.config.retained_turns

        if len(self.turns) > retain:
            # Keep only recent turns
            self.turns = self.turns[-retain:]

            # Add summary as a system message
            summary_msg = {
                "role": "system",
                "content": f"[Conversation Summary]\n{summary_content}",
            }
            # Insert after system prompts
            self.system_prompts.append(summary_msg)

        return old_count - len(self.turns)

    def snapshot(self) -> dict[str, Any]:
        """
        Create a serializable snapshot of the current context.

        Returns:
            Dictionary representation suitable for persistence.
        """
        return {
            "system_prompts": self.system_prompts,
            "turns": [t.to_dict() for t in self.turns],
            "turn_count": self._turn_count,
            "summary": self.summary,
            "pruner_config": {
                "max_tokens": self.pruner.config.max_tokens,
                "retained_turns": self.pruner.config.retained_turns,
            },
        }

    def load_snapshot(self, data: dict[str, Any]) -> None:
        """
        Load context from a snapshot.

        Args:
            data: Snapshot dictionary from snapshot().
        """
        self.system_prompts = data.get("system_prompts", [])
        self._turn_count = data.get("turn_count", 0)
        self.summary = data.get("summary")

        self.turns = []
        for turn_data in data.get("turns", []):
            turn = Turn(
                user_message=turn_data["user"],
                assistant_message=turn_data["assistant"],
                timestamp=datetime.fromisoformat(turn_data["timestamp"]),
                metadata=turn_data.get("metadata", {}),
            )
            self.turns.append(turn)

    def clear(self) -> None:
        """Clear all context (reset to initial state)."""
        self.turns = []
        self._turn_count = 0
        # Keep system prompts, clear the rest
        self.system_prompts = []
        self.summary = None

    def stats(self) -> dict[str, Any]:
        """Get statistics about the current context."""
        messages = self.get_active_context(strategy="full")
        return {
            "turn_count": self._turn_count,
            "system_messages": len(self.system_prompts),
            "total_messages": len(messages),
            "estimated_tokens": self.pruner.estimate_tokens(messages),
            "pruner_config": {
                "max_tokens": self.pruner.config.max_tokens,
                "retained_turns": self.pruner.config.retained_turns,
            },
            "has_summary": self.summary is not None,
        }

    def segment(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Segment current context into three parts for compression.

        Returns:
            Tuple of (system, to_summarize, recent) message lists.
            - system: System prompts from system_prompts
            - to_summarize: Old user/assistant messages to compress
            - recent: Recent user/assistant messages to keep
        """
        # Get system prompts directly
        system_msgs = list(self.system_prompts)

        # Get chat messages (user/assistant only)
        chat_messages = self.get_active_context(strategy="full")

        # Delegate to pruner for segmentation
        return self.pruner.segment(chat_messages, system_msgs)

    async def compress(self) -> bool:
        """
        Compress old context into a summary using NoteTaker skill.

        This implements semantic compression:
        1. Segment messages into (system, to_summarize, recent)
        2. Format old messages into trajectory structure
        3. Call NoteTaker to generate summary
        4. Store summary and trim history

        Returns:
            True if compression occurred, False if no compression needed.
        """
        # Get current context
        messages = self.get_active_context(strategy="full")

        # Segment into three parts
        system_msgs, to_summarize, recent_msgs = self.pruner.segment(messages)

        # Check if there's anything to summarize
        if not to_summarize:
            return False

        # Format messages for NoteTaker trajectory
        trajectory = self._messages_to_trajectory(to_summarize)

        # Try to call NoteTaker skill
        try:
            from assets.skills.note_taker.scripts.session_summarizer import summarize

            session_id = f"ctx-{uuid.uuid4().hex[:8]}"
            summary_path = summarize(session_id=session_id, trajectory=trajectory)

            # Read the generated summary
            from pathlib import Path

            summary_text = Path(summary_path).read_text()

            # Extract just the summary content (without markdown headers)
            self.summary = self._extract_summary_content(summary_text)

        except Exception:
            # Fallback: simple extraction-based summary
            self.summary = self._simple_summarize(to_summarize)

        # Compress: keep system + recent, replace older with summary
        self._apply_compression(system_msgs, recent_msgs)

        return True

    def _messages_to_trajectory(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert message list to NoteTaker trajectory format.

        Args:
            messages: List of chat messages to convert.

        Returns:
            Trajectory structure for NoteTaker summarization.
        """
        trajectory = []

        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))

            if role == "user":
                trajectory.append(
                    {
                        "type": "goal",
                        "content": content[:200],  # Truncate long content
                    }
                )
            elif role == "assistant":
                trajectory.append(
                    {
                        "type": "decision",
                        "title": f"Step {i // 2 + 1}",
                        "context": "",
                        "choice": content[:500],
                        "rationale": "Assistant response",
                        "alternatives": [],
                    }
                )

        return trajectory

    def _extract_summary_content(self, markdown: str) -> str:
        """
        Extract pure summary content from NoteTaker markdown output.

        Args:
            markdown: Full markdown output from NoteTaker.

        Returns:
            Cleaned summary text without markdown formatting.
        """
        # Extract key sections
        lines = markdown.split("\n")
        summary_lines = []

        in_summary_section = False
        in_decision_path = False

        for line in lines:
            if line.startswith("## Summary"):
                in_summary_section = True
                continue
            if line.startswith("## Decision Path"):
                in_summary_section = False
                in_decision_path = True
                continue
            if line.startswith("##"):
                in_summary_section = False
                in_decision_path = False

            if in_summary_section and line.strip():
                summary_lines.append(line.strip())
            elif in_decision_path and line.startswith("###"):
                summary_lines.append(f"  - {line.replace('###', '').strip()}")

        return " ".join(summary_lines)[:2000]  # Limit summary size

    def _simple_summarize(self, messages: list[dict[str, Any]]) -> str:
        """
        Create a simple extractive summary from messages.

        Args:
            messages: Messages to summarize.

        Returns:
            Simple text summary of message contents.
        """
        if not messages:
            return ""

        # Extract key content
        summaries = []
        for msg in messages:
            role = msg.get("role", "")
            content = str(msg.get("content", ""))

            # Skip empty or very short messages
            if len(content) < 20:
                continue

            # Truncate and summarize
            if len(content) > 300:
                content = content[:300] + "..."

            summaries.append(f"[{role}]: {content}")

        return f"Summarized {len(messages)} messages:\n" + "\n".join(summaries[-10:])

    def _apply_compression(
        self,
        system_msgs: list[dict[str, Any]],
        recent_msgs: list[dict[str, Any]],
    ) -> None:
        """
        Apply compression by replacing old messages with summary.

        Args:
            system_msgs: System messages to preserve.
            recent_msgs: Recent messages to keep.
        """
        # Clear current state
        self.turns = []
        self.system_prompts = list(system_msgs)

        # Add summary as a system message
        if self.summary:
            self.system_prompts.append(
                {
                    "role": "system",
                    "content": f"[Context Summary]\n{self.summary}",
                    "_is_summary": True,
                }
            )

        # Rebuild turns from recent messages
        current_turn: Turn | None = None

        for msg in recent_msgs:
            role = msg.get("role", "")

            if role == "user":
                # Start new turn
                current_turn = Turn(
                    user_message=msg,
                    assistant_message={"role": "assistant", "content": ""},
                )
            elif role == "assistant" and current_turn:
                # Complete the turn
                current_turn.assistant_message = msg
                self.turns.append(current_turn)
                current_turn = None

        # Update turn count
        self._turn_count = len(self.turns)
