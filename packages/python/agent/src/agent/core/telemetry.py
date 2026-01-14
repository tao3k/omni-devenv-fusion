"""
src/agent/core/telemetry.py
Telemetry Module - Token Usage and Cost Estimation.

Phase 19: The Black Box
Phase 57: Updated to use direct tiktoken for accurate BPE counting.

Features:
- Token usage tracking (input/output/total)
- Cost estimation based on model pricing
- Support for multiple LLM providers (Claude, GPT-4)

Usage:
    from agent.core.telemetry import CostEstimator, TokenUsage

    usage = CostEstimator.estimate(
        text_input="Hello, world!",
        text_output="Hi there!",
        model="claude-3-5-sonnet"
    )
    print(f"Cost: ${usage.cost_usd:.4f}")
"""

import time
from typing import Optional

import tiktoken
from pydantic import BaseModel

# [Phase 57] Direct tiktoken - faster than Rust wrapper via PyO3
_ENCODER = tiktoken.get_encoding("cl100k_base")


class TokenUsage(BaseModel):
    """Token usage and cost for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Add two TokenUsage instances."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )


class CostEstimator:
    """
    Estimate LLM call costs based on token usage.

    [Phase 57] Uses direct tiktoken for accurate BPE counting.
    Uses cl100k_base encoding (GPT-4/3.5 standard).

    Default pricing based on Claude 3.5 Sonnet:
    - Input: $3.00 per 1M tokens
    - Output: $15.00 per 1M tokens
    """

    # Pricing per 1M tokens (USD)
    PRICING = {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "default": {"input": 3.0, "output": 15.0},
    }

    @classmethod
    def _count_tokens(cls, text: str) -> int:
        """
        Count tokens using direct tiktoken (accurate BPE counting).

        [Phase 57] Updated from heuristic estimation to accurate BPE counting.
        Uses cl100k_base encoding (GPT-4/3.5 standard) directly.

        Args:
            text: Input text

        Returns:
            Accurate token count
        """
        if not text:
            return 0
        return len(_ENCODER.encode(text))

    @classmethod
    def estimate(
        cls,
        text_input: str,
        text_output: str,
        model: str = "default",
        use_api_usage: bool = False,
        api_usage: Optional[dict] = None,
    ) -> TokenUsage:
        """
        Estimate token usage and cost for an LLM call.

        Args:
            text_input: Input text/prompt
            text_output: Expected or actual output text
            model: Model name for pricing lookup
            use_api_usage: If True, use api_usage data instead of estimation
            api_usage: Dict with 'input_tokens' and 'output_tokens' from API

        Returns:
            TokenUsage instance with counts and estimated cost
        """
        if use_api_usage and api_usage:
            # Use actual API usage data (most accurate)
            input_tokens = api_usage.get("input_tokens", 0)
            output_tokens = api_usage.get("output_tokens", 0)
        else:
            # Estimate from text (lightweight fallback)
            input_tokens = cls._count_tokens(text_input)
            output_tokens = cls._count_tokens(text_output)

        total_tokens = input_tokens + output_tokens

        # Get pricing for model
        rates = cls.PRICING.get(model, cls.PRICING["default"])
        cost_usd = (input_tokens / 1_000_000 * rates["input"]) + (
            output_tokens / 1_000_000 * rates["output"]
        )

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        )

    @classmethod
    def estimate_from_usage(cls, usage: dict, model: str = "default") -> TokenUsage:
        """
        Create TokenUsage from API usage dict.

        Args:
            usage: Dict with 'input_tokens' and 'output_tokens'
            model: Model name for pricing

        Returns:
            TokenUsage with accurate token counts and estimated cost
        """
        return cls.estimate(
            text_input="",  # Not used when using API usage
            text_output="",
            model=model,
            use_api_usage=True,
            api_usage=usage,
        )


class SessionTelemetry:
    """
    Accumulate telemetry across a session.

    Phase 19: Tracks total cost and token usage for the entire session.
    """

    def __init__(self):
        self.total_usage = TokenUsage()
        self.start_time = time.time()
        self.request_count = 0

    def add_usage(self, usage: TokenUsage) -> None:
        """Add token usage to session totals."""
        self.total_usage = self.total_usage + usage
        self.request_count += 1

    def get_summary(self) -> dict:
        """Get session summary."""
        elapsed = time.time() - self.start_time
        return {
            "session_duration_seconds": round(elapsed, 2),
            "total_requests": self.request_count,
            "total_input_tokens": self.total_usage.input_tokens,
            "total_output_tokens": self.total_usage.output_tokens,
            "total_tokens": self.total_usage.total_tokens,
            "total_cost_usd": round(self.total_usage.cost_usd, 4),
        }

    def get_cost_rate(self) -> str:
        """Get cost rate as dollars per minute."""
        elapsed = time.time() - self.start_time
        if elapsed < 1:
            return "$0.00/min"
        cost_per_minute = (self.total_usage.cost_usd / elapsed) * 60
        return f"${cost_per_minute:.2f}/min"
