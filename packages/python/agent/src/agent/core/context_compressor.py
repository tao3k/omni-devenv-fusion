"""
src/agent/core/context_compressor.py
Context Compression Utilities for MCP Server.

Phase 48: Hyper-Context Compressor (Rust Accelerated).
Phase 19.7 → Phase 21: Migrated from ClaudeCodeAdapter to MCP Server.
Now serves as the "Token Gatekeeper" for RAG search results.

[Phase 48.1] Updated: Use direct tiktoken instead of omni_core_rs wrapper.
Reason: tiktoken is already Rust, PyO3 wrapper adds ~18x overhead.

[Phase 57] Architecture Note:
- Python tiktoken calls tiktoken-rs directly (optimized FFI)
- omni_tokenizer Rust crate still exists for internal Rust operations
- Fused operations (read+count+truncate) implemented in Rust when needed
"""

from typing import List, Tuple, Optional
import tiktoken

from common.config.settings import get_setting

# [Phase 48.1] Direct tiktoken - faster than Rust wrapper via PyO3
_ENCODER = tiktoken.get_encoding("cl100k_base")

# Default settings (fallbacks when settings.yaml not available)
DEFAULT_MAX_CONTEXT_TOKENS = 4000


class ContextCompressor:
    """
    Lightweight context compression for MCP server RAG results.

    Phase 48: Uses direct tiktoken (Rust) for accurate BPE tokenization.
    Phase 48.1: Removed omni_core_rs wrapper - direct FFI is faster.

    Prevents token explosion and attention dilution when Claude
    queries the knowledge base via MCP tools.
    """

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        compression_method: Optional[str] = None,
    ):
        """
        Initialize compressor with settings from config or defaults.

        Args:
            max_tokens: Maximum tokens before compression
            compression_method: "truncate" (only supported for now)
        """
        self.max_tokens = max_tokens or get_setting(
            "context_compression.max_context_tokens", DEFAULT_MAX_CONTEXT_TOKENS
        )
        self.method = compression_method or get_setting("context_compression.method", "truncate")
        self.enabled = get_setting("context_compression.enabled", True)

    def count_tokens(self, text: str) -> int:
        """
        [Phase 48.1] Accurate token counting using direct tiktoken.
        Uses cl100k_base encoding (GPT-4/3.5 standard).
        Direct FFI to tiktoken-rs is faster than PyO3 wrapper.
        """
        if not text:
            return 0
        return len(_ENCODER.encode(text))

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Delegates to count_tokens for accuracy.
        """
        return self.count_tokens(text)

    def truncate(self, text: str, max_tokens: int) -> str:
        """
        [Phase 48.1] Precision token-level truncation using direct tiktoken.
        Truncates at BPE boundary (no UTF-8 corruption).
        """
        if not text:
            return ""

        current = self.count_tokens(text)
        if current <= max_tokens:
            return text

        # Encode and truncate at token boundary
        tokens = _ENCODER.encode(text)
        truncated_tokens = tokens[:max_tokens]
        return _ENCODER.decode(truncated_tokens)

    def compress(self, text: str, max_tokens: Optional[int] = None) -> str:
        """
        Compress text to fit within token limit.

        Args:
            text: Original text
            max_tokens: Override for max tokens (uses instance default if None)

        Returns:
            Compressed text (or original if under threshold)
        """
        if not self.enabled:
            return text

        limit = max_tokens or self.max_tokens
        current_tokens = self.count_tokens(text)

        if current_tokens <= limit:
            return text

        # Precision truncation at token boundary
        if self.method == "truncate":
            return self.truncate(text, limit)

        return text

    def fit_to_budget(self, sections: List[Tuple[str, str, int]], total_budget: int) -> str:
        """
        Assemble context sections into a final string fitting the budget.
        Sections are sorted by priority (higher priority kept first).

        Args:
            sections: List of (header, content, priority) tuples
            total_budget: Maximum tokens allowed

        Returns:
            Assembled context string within budget
        """
        if not sections:
            return ""

        # Sort by priority (descending) - higher priority first
        sorted_sections = sorted(sections, key=lambda x: x[2], reverse=True)

        final_context = []
        current_tokens = 0

        for header, content, _ in sorted_sections:
            header_tokens = self.count_tokens(header)
            content_tokens = self.count_tokens(content)
            entry_tokens = header_tokens + content_tokens + 5  # ~5 tokens for newlines

            if current_tokens + entry_tokens <= total_budget:
                final_context.append((header, content))
                current_tokens += entry_tokens
            else:
                # Try to fit partial content
                remaining = total_budget - current_tokens - header_tokens - 5
                if remaining > 50:  # Only if worth it
                    truncated_content = self.truncate(content, remaining)
                    final_context.append((header, truncated_content))
                break

        # Build final string
        result_parts = []
        for header, content in final_context:
            result_parts.append(f"\n{header}\n{content}\n")

        return "".join(result_parts)


def get_compressor() -> ContextCompressor:
    """Get a ContextCompressor instance with default settings."""
    return ContextCompressor()


# Convenience functions
def count_tokens(text: str) -> int:
    """Quick token count using default compressor."""
    return get_compressor().count_tokens(text)


def truncate_text(text: str, max_tokens: int) -> str:
    """Quick truncate using default compressor."""
    return get_compressor().truncate(text, max_tokens)
