"""
src/agent/core/context_compressor.py
Context Compression Utilities for MCP Server.

Phase 19.7 → Phase 21: Migrated from ClaudeCodeAdapter to MCP Server.
Now serves as the "Token Gatekeeper" for RAG search results.

Configuration:
- Reads from settings.yaml: context_compression.enabled
- Reads from settings.yaml: context_compression.max_context_tokens
- Reads from settings.yaml: context_compression.method
"""

from common.mcp_core.settings import get_setting

# Default settings (fallbacks when settings.yaml not available)
DEFAULT_MAX_CONTEXT_TOKENS = 4000
DEFAULT_MAX_FILE_SIZE_KB = 50


class ContextCompressor:
    """
    Lightweight context compression for MCP server RAG results.

    Prevents token explosion and attention dilution when Claude
    queries the knowledge base via MCP tools.
    """

    def __init__(
        self,
        max_tokens: int = None,
        compression_method: str = None,
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

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation: 1 token ≈ 4 chars)."""
        return len(text) // 4

    def compress(self, text: str, max_tokens: int = None) -> str:
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
        current_tokens = self.estimate_tokens(text)

        if current_tokens <= limit:
            return text

        # Simple truncation for now (LLM summarization is a future enhancement)
        if self.method == "truncate":
            max_chars = limit * 4
            return text[:max_chars] + "\n... [Truncated for context limit]"

        # Fallback: truncate
        max_chars = limit * 4
        return text[:max_chars] + "\n... [Truncated]"


def get_compressor() -> ContextCompressor:
    """Get a ContextCompressor instance with default settings."""
    return ContextCompressor()
