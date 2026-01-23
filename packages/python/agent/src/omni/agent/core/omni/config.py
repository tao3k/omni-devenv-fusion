"""
config.py - OmniLoop Configuration

 dataclass for configuring OmniLoop behavior.
"""

from dataclasses import dataclass


@dataclass
class OmniLoopConfig:
    """Configuration for the OmniLoop.

    Attributes:
        max_tokens: Maximum tokens for context (default: 128K)
        retained_turns: Number of conversation turns to retain (default: 10)
        auto_summarize: Enable automatic context summarization
        max_tool_calls: Max tool calls per turn for safety (default: 10)
        verbose: Enable verbose logging with DEBUG output
    """

    max_tokens: int = 128000
    retained_turns: int = 10
    auto_summarize: bool = False
    max_tool_calls: int = 10
    verbose: bool = False
