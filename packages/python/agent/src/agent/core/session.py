"""
src/agent/core/session.py
Session Manager - The Black Box Recorder.

Phase 19: The Black Box
Handles persistence of the agent's stream of consciousness.

Features:
- Session event logging (JSONL format)
- Conversation history management
- Session resumption from disk
- Integration with telemetry for cost tracking

Event Types:
- "user": User input
- "router": Routing decision
- "agent_action": Agent execution result
- "tool": Tool execution
- "error": Error event

Usage:
    from agent.core.session import SessionManager, SessionEvent

    # Start new session
    session = SessionManager()
    session.log("user", "user", "Fix the bug")
    session.log("agent_action", "coder", "Fixed the bug by...")

    # Resume session
    session = SessionManager(session_id="abc123")
    # History is automatically replayed
"""

import json
import uuid
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from pydantic import BaseModel, Field

from common.gitops import get_project_root
from agent.core.telemetry import TokenUsage, SessionTelemetry

logger = structlog.get_logger()


def get_agent_storage_dir() -> Path:
    """
    Get the agent storage directory for sessions.

    Uses .cache/agent/sessions under project root.

    Returns:
        Path to session storage directory
    """
    project_root = get_project_root()
    storage_dir = project_root / ".cache" / "agent" / "sessions"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


class SessionEvent(BaseModel):
    """A single event in the session stream."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = Field(default_factory=time.time)
    type: str  # "user", "router", "agent_action", "tool", "error"
    source: str  # "user", "hive_router", "coder", "reviewer"
    content: Any
    usage: Optional[TokenUsage] = None
    metadata: Optional[Dict[str, Any]] = None


class SessionState(BaseModel):
    """Complete state snapshot for session resumption."""

    session_id: str
    mission_id: Optional[str] = None
    current_agent: Optional[str] = None
    attempt_number: int = 1
    history: List[Dict[str, Any]] = Field(default_factory=list)
    telemetry: TokenUsage = Field(default_factory=TokenUsage)


class SessionManager:
    """
    Phase 19: The Black Box.

    Manages session persistence and provides:
    - Append-only event logging to JSONL
    - Conversation history for LLM context
    - Session resumption from disk
    - Telemetry accumulation

    The Black Box records:
    1. User inputs
    2. Router decisions (with reasoning)
    3. Agent actions and outputs
    4. Tool executions
    5. Errors and retries
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        mission_id: Optional[str] = None,
    ):
        """
        Initialize SessionManager.

        Args:
            session_id: Optional session ID (auto-generated if not provided)
            mission_id: Optional mission ID for grouping sessions
        """
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.mission_id = mission_id
        self.storage_dir = get_agent_storage_dir()
        self.file_path = self.storage_dir / f"{self.session_id}.jsonl"

        # Runtime state
        self.telemetry = SessionTelemetry()
        self.history: List[Dict[str, Any]] = []  # For LLM context
        self.events: List[Dict] = []  # In-memory event cache

        # Session state for resumption
        self.state = SessionState(session_id=self.session_id, mission_id=mission_id)

        # If resuming, load from disk
        if self.file_path.exists():
            self._replay_history()
        else:
            logger.info("📼 New session started", session_id=self.session_id)

        # Write latest session symlink
        self._update_latest_session()

    def log(
        self,
        type: str,
        source: str,
        content: Any,
        usage: Optional[TokenUsage] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionEvent:
        """
        Log an atomic event to the session.

        Args:
            type: Event type ("user", "router", "agent_action", "tool", "error")
            source: Event source ("user", "hive_router", "coder", etc.)
            content: Event content (any serializable type)
            usage: Optional token usage for cost tracking
            metadata: Optional additional metadata

        Returns:
            The created SessionEvent
        """
        event = SessionEvent(
            type=type,
            source=source,
            content=content,
            usage=usage,
            metadata=metadata,
        )

        # 1. Write to disk (append-only, crash-safe)
        self._append_to_file(event)

        # 2. Update memory
        self.events.append(event.model_dump())
        if usage:
            self.telemetry.add_usage(usage)

        # 3. Maintain conversation history for context
        self._update_history(type, source, content)

        # 4. Update session state
        self._update_state(type, source, content)

        return event

    def _append_to_file(self, event: SessionEvent) -> None:
        """Append event to JSONL file."""
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception as e:
            logger.error("Failed to write session event", error=str(e))

    def _update_history(self, type: str, source: str, content: Any) -> None:
        """Update conversation history for LLM context."""
        content_str = str(content)

        if type == "user":
            self.history.append({"role": "user", "content": content_str})
        elif type == "agent_action":
            self.history.append({"role": "assistant", "content": content_str})
        elif type == "router":
            # Add routing decision as system message
            self.history.append({"role": "system", "content": f"[Router] {content_str}"})

    def _update_state(self, type: str, source: str, content: Any) -> None:
        """Update session state for resumption."""
        if type == "router" and isinstance(content, dict):
            if content.get("target_agent"):
                self.state.current_agent = content["target_agent"]
        elif type == "user":
            self.state.attempt_number = 1
        elif type == "agent_action":
            if "rejected" in str(content).lower() or "failed" in str(content).lower():
                self.state.attempt_number += 1

    def _replay_history(self) -> None:
        """Replay session history from disk for resumption."""
        logger.info("🔄 Resuming session", session_id=self.session_id)

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    data = json.loads(line)
                    event = SessionEvent(**data)

                    # Accumulate telemetry
                    if event.usage:
                        self.telemetry.add_usage(event.usage)

                    # Replay conversation history
                    if event.type == "user":
                        self.history.append({"role": "user", "content": str(event.content)})
                    elif event.type == "agent_action":
                        self.history.append({"role": "assistant", "content": str(event.content)})

                    self.events.append(data)

            logger.info(
                "✅ Session replayed",
                session_id=self.session_id,
                events=len(self.events),
                cost_usd=self.telemetry.total_usage.cost_usd,
            )
        except Exception as e:
            logger.error("Failed to replay session", error=str(e))

    def _update_latest_session(self) -> None:
        """Update the latest session symlink."""
        try:
            latest_path = self.storage_dir / "latest"
            if latest_path.is_symlink() or latest_path.exists():
                latest_path.unlink()
            latest_path.symlink_to(self.file_path)
        except Exception:
            pass  # Non-critical

    def get_summary(self) -> str:
        """Get human-readable session summary."""
        return (
            f"Session: {self.session_id} | "
            f"Requests: {self.telemetry.request_count} | "
            f"Cost: ${self.telemetry.total_usage.cost_usd:.4f} | "
            f"Rate: {self.telemetry.get_cost_rate()}"
        )

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Get detailed telemetry summary."""
        return self.telemetry.get_summary()

    def get_events(self, limit: Optional[int] = None) -> List[Dict]:
        """Get recent events."""
        if limit:
            return self.events[-limit:]
        return self.events

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history for LLM context."""
        if limit:
            return self.history[-limit:]
        return self.history

    def get_state(self) -> SessionState:
        """Get current session state for resumption."""
        return self.state

    @classmethod
    def list_sessions(cls) -> List[Dict[str, Any]]:
        """List all sessions in storage."""
        storage_dir = get_agent_storage_dir()
        sessions = []

        for path in storage_dir.glob("*.jsonl"):
            if path.name == "latest":
                continue

            try:
                stat = path.stat()
                # Count lines
                with open(path, "r") as f:
                    lines = sum(1 for _ in f)

                sessions.append(
                    {
                        "session_id": path.stem,
                        "file_path": str(path),
                        "events": lines,
                        "modified": stat.st_mtime,
                    }
                )
            except Exception:
                continue

        # Sort by modification time
        sessions.sort(key=lambda x: x["modified"], reverse=True)
        return sessions

    @classmethod
    def get_latest_session_id(cls) -> Optional[str]:
        """Get the latest session ID."""
        storage_dir = get_agent_storage_dir()
        latest_path = storage_dir / "latest"

        if latest_path.is_symlink():
            return latest_path.resolve().stem
        return None


def create_session_manager(session_id: Optional[str] = None) -> SessionManager:
    """
    Factory function for SessionManager.

    Args:
        session_id: Optional session ID to resume

    Returns:
        SessionManager instance
    """
    return SessionManager(session_id=session_id)
