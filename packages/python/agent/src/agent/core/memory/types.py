"""
agent/core/memory/types.py
 The Memory Mesh - Memory Schema Definitions

Defines structured types for episodic memory storage in LanceDB.

Usage:
    from agent.core.memory.types import InteractionLog

    log = InteractionLog(
        user_query="git commit fail",
        tool_calls=["git.commit"],
        outcome="failure",
        error_msg="lock file exists",
        reflection="Solution: rm .git/index.lock"
    )
    record = log.to_vector_record()
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid


class InteractionLog(BaseModel):
    """
    Episode: 描述 Agent 的一次交互经历。

    用于存储结构化的"输入 -> 工具 -> 结果 -> 反思"链条。
    这些记录会被向量化和存储，用于检索相关的历史经验。
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique UUID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="ISO 8601 timestamp"
    )

    # Context - 用户意图
    user_query: str = Field(..., description="User's original intent/query")
    session_id: Optional[str] = Field(None, description="Session identifier for grouping")

    # Action - 执行轨迹
    tool_calls: List[str] = Field(
        default_factory=list, description="List of tools that were called"
    )

    # Consequence - 执行结果
    outcome: str = Field(..., description="'success' or 'failure'")
    error_msg: Optional[str] = Field(None, description="Error message if failed")

    # Knowledge - 经验总结 (核心检索字段)
    reflection: str = Field(..., description="Synthesized lesson learned from this interaction")

    def to_vector_record(self) -> dict:
        """
        转换为 LanceDB 存储格式。

        Returns:
            Dict with fields:
            - id: Record ID
            - text: Combined text for embedding (query + reflection)
            - metadata: Full JSON dump of the record
            - type: Record type ("memory")
            - timestamp: ISO timestamp
        """
        # 构建用于向量化的文本
        # 组合用户查询和反思，便于匹配"类似问题"和"解决方案"
        text_parts = [f"Query: {self.user_query}", f"Reflection: {self.reflection}"]

        if self.error_msg:
            text_parts.append(f"Error: {self.error_msg}")

        text = "\n".join(text_parts)

        return {
            "id": self.id,
            "text": text,
            "metadata": self.model_dump(mode="json"),
            "type": "memory",
            "timestamp": self.timestamp,
            "outcome": self.outcome,
        }

    def to_summary(self) -> str:
        """生成简短的摘要字符串，用于日志输出。"""
        status = "✓" if self.outcome == "success" else "✗"
        return f"[{status}] {self.user_query[:50]} -> {self.reflection[:50]}"


class MemoryQuery(BaseModel):
    """记忆查询参数。"""

    query: str = Field(..., description="Search query")
    limit: int = Field(default=3, ge=1, le=10, description="Max results")
    outcome_filter: Optional[str] = Field(None, description="Filter by outcome")


__all__ = [
    "InteractionLog",
    "MemoryQuery",
]
