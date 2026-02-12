"""
chunking.py - Semantic Chunking Module

Provides intelligent text chunking that preserves semantic boundaries for optimal
RAG retrieval performance.

Chunking Strategies:
- SemanticChunker: LLM-based semantic boundary detection
- SentenceChunker: Sentence-aware fixed-size chunking
- ParagraphChunker: Paragraph-based chunking
- SlidingWindowChunker: Sliding window with overlap

Usage:
    from omni.rag.chunking import SemanticChunker

    chunker = SemanticChunker()
    chunks = await chunker.chunk(content)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Chunk:
    """Represents a text chunk with metadata.

    Attributes:
        text: The chunk text content.
        index: Position in the chunk sequence.
        start_char: Starting character position in original text.
        end_char: Ending character position in original text.
        chunk_type: Type of chunk (semantic, sentence, paragraph, etc.)
        metadata: Additional metadata dict.
    """

    text: str
    index: int
    start_char: int = 0
    end_char: int = 0
    chunk_type: str = "semantic"
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def char_count(self) -> int:
        """Get the character count of the chunk."""
        return len(self.text)

    @property
    def token_count(self) -> int:
        """Estimate token count (rough approximation)."""
        return len(self.text) // 4


class ChunkingStrategy(ABC):
    """Abstract base class for chunking strategies."""

    @abstractmethod
    async def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Chunk the input text.

        Args:
            text: Input text to chunk.
            **kwargs: Strategy-specific options.

        Returns:
            List of Chunk objects.
        """
        pass


class SemanticChunker(ChunkingStrategy):
    """LLM-based semantic chunking.

    Uses an LLM to detect semantic boundaries in text, producing chunks
    that preserve meaning and context. This produces higher quality chunks
    but requires LLM calls.

    Attributes:
        llm_complete_func: LLM completion function for boundary detection.
        chunk_target_tokens: Target token count per chunk (default: 512).
        overlap_tokens: Token overlap between chunks (default: 50).
    """

    DEFAULT_PROMPT = """Analyze the following text and identify semantic boundaries where content shifts to a new topic, section, or idea. Return the character positions (start, end) for each semantic chunk.

Text:
{text}

Respond with JSON array of chunks:
[{{"start": 0, "end": 150, "reason": "Introduction and overview"}}, ...]

Only return valid JSON, no other text."""

    def __init__(
        self,
        llm_complete_func: callable | None = None,
        chunk_target_tokens: int = 512,
        overlap_tokens: int = 50,
    ):
        """Initialize the semantic chunker.

        Args:
            llm_complete_func: Optional LLM function for boundary detection.
            chunk_target_tokens: Target tokens per chunk.
            overlap_tokens: Overlap tokens between chunks.
        """
        self.llm_complete = llm_complete_func
        self.chunk_target_tokens = chunk_target_tokens
        self.overlap_tokens = overlap_tokens
        self._chunking_prompt = self.DEFAULT_PROMPT

    def set_prompt(self, prompt: str) -> None:
        """Set a custom chunking prompt.

        Args:
            prompt: Custom prompt template with {text} placeholder.
        """
        self._chunking_prompt = prompt

    async def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Chunk text using LLM-based semantic boundary detection.

        Args:
            text: Input text to chunk.
            **kwargs: Additional options (prompt override via 'prompt').

        Returns:
            List of semantic chunks.
        """
        if not text:
            return []

        if self.llm_complete is None:
            # Fallback to sentence-based chunking (this is expected when no LLM is configured)
            logger.debug(
                "Semantic chunker: No LLM function provided, using sentence-based fallback"
            )
            fallback = SentenceChunker(
                chunk_target_tokens=self.chunk_target_tokens,
                overlap_tokens=self.overlap_tokens,
            )
            return await fallback.chunk(text)

        try:
            # Use LLM to find semantic boundaries
            prompt = kwargs.get("prompt", self._chunking_prompt)
            prompt = prompt.format(text=text[:15000])  # Limit text size

            response = await self.llm_complete(prompt)
            boundaries = self._parse_boundaries(response)

            if not boundaries:
                # Fallback if LLM parsing fails
                fallback = SentenceChunker(
                    chunk_target_tokens=self.chunk_target_tokens,
                    overlap_tokens=self.overlap_tokens,
                )
                return await fallback.chunk(text)

            # Extract chunks based on boundaries
            chunks = []
            for i, (start, end) in enumerate(boundaries):
                chunk_text = text[start:end]
                chunk = Chunk(
                    text=chunk_text.strip(),
                    index=i,
                    start_char=start,
                    end_char=end,
                    chunk_type="semantic",
                    metadata={"reason": f"Boundary {i}"},
                )
                chunks.append(chunk)

            logger.info(
                "Semantic chunking completed",
                chunks=len(chunks),
                avg_chars=sum(c.char_count for c in chunks) / len(chunks) if chunks else 0,
            )

            return chunks

        except Exception as e:
            logger.error("Semantic chunking failed", error=str(e))
            # Fallback to sentence-based
            fallback = SentenceChunker(
                chunk_target_tokens=self.chunk_target_tokens,
                overlap_tokens=self.overlap_tokens,
            )
            return await fallback.chunk(text)

    def _parse_boundaries(self, response: str) -> list[tuple[int, int]]:
        """Parse LLM response to extract boundary positions.

        Args:
            response: LLM response text.

        Returns:
            List of (start, end) tuples.
        """
        boundaries = []
        try:
            # Try to extract JSON
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                import json

                data = json.loads(json_match.group())
                for item in data:
                    if "start" in item and "end" in item:
                        boundaries.append((item["start"], item["end"]))
        except Exception as e:
            logger.debug("Failed to parse boundaries", error=str(e))

        return sorted(boundaries, key=lambda x: x[0])


class SentenceChunker(ChunkingStrategy):
    """Sentence-aware chunking with token limits.

    Splits text into chunks based on sentences, then merges sentences
    to reach target token counts. Good balance of quality and speed.

    Attributes:
        chunk_target_tokens: Target tokens per chunk.
        overlap_tokens: Overlap tokens between chunks.
        min_sentence_len: Minimum sentence length to split on.
    """

    # Common sentence-ending punctuation
    SENTENCE_ENDINGS = re.compile(r"[.!?]\s+")
    PARAGRAPH_BREAK = re.compile(r"\n\n+")

    def __init__(
        self,
        chunk_target_tokens: int = 512,
        overlap_tokens: int = 50,
        min_sentence_len: int = 20,
    ):
        """Initialize the sentence chunker.

        Args:
            chunk_target_tokens: Target tokens per chunk.
            overlap_tokens: Overlap tokens between chunks.
            min_sentence_len: Minimum sentence length for splitting.
        """
        self.chunk_target_tokens = chunk_target_tokens
        self.overlap_tokens = overlap_tokens
        self.min_sentence_len = min_sentence_len
        # Rough tokens per character estimate
        self.chars_per_token = 4

    async def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Chunk text using sentence-aware splitting.

        Args:
            text: Input text to chunk.
            **kwargs: Additional options (max_tokens override).

        Returns:
            List of sentence-based chunks.
        """
        if not text:
            return []

        max_tokens = kwargs.get("max_tokens", self.chunk_target_tokens)
        overlap = kwargs.get("overlap", self.overlap_tokens)

        # Split into sentences with position tracking (O(n) instead of O(n²))
        sentences_with_pos = self._split_into_sentences_with_positions(text)

        if not sentences_with_pos:
            return [Chunk(text=text, index=0, chunk_type="sentence")]

        # Merge sentences into chunks using pre-computed positions
        chunks = []
        current_start = 0
        current_end = 0
        current_sentences = []

        for sent_start, sent_end, sentence_text in sentences_with_pos:
            # Estimate tokens for current chunk + this sentence
            new_start = current_start
            new_end = sent_end
            if current_sentences:
                new_text = text[current_start:sent_end]
            else:
                new_text = sentence_text

            est_tokens = len(new_text) // self.chars_per_token

            # Check if adding this sentence would exceed max tokens
            if est_tokens > max_tokens and current_sentences:
                # Finalize current chunk
                chunk_text = text[current_start:current_end].strip()
                chunk = Chunk(
                    text=chunk_text,
                    index=len(chunks),
                    start_char=current_start,
                    end_char=current_end,
                    chunk_type="sentence",
                    metadata={"sentences": len(current_sentences)},
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                overlap_text = self._get_overlap(text[current_start:current_end], overlap)
                current_sentences = [overlap_text, sentence_text]
                current_start = sent_start - len(overlap_text)
                current_end = sent_end
            else:
                if current_sentences:
                    current_sentences.append(sentence_text)
                else:
                    current_sentences = [sentence_text]
                current_end = sent_end

        # Add final chunk
        if current_sentences:
            chunk_text = text[current_start:current_end].strip()
            chunk = Chunk(
                text=chunk_text,
                index=len(chunks),
                start_char=current_start,
                end_char=current_end,
                chunk_type="sentence",
                metadata={"sentences": len(current_sentences)},
            )
            chunks.append(chunk)

        # Re-index chunks
        for i, chunk in enumerate(chunks):
            chunk.index = i

        logger.info(
            "Sentence chunking completed",
            chunks=len(chunks),
            avg_tokens=sum(c.token_count for c in chunks) / len(chunks) if chunks else 0,
        )

        return chunks

    def _split_into_sentences_with_positions(self, text: str) -> list[tuple[int, int, str]]:
        """Split text into sentences with (start, end, text) tuples.

        Optimized to avoid O(n²) complexity by pre-scanning positions.

        Args:
            text: Input text.

        Returns:
            List of (start, end, sentence_text) tuples.
        """
        sentences = []

        # Find paragraph boundaries first
        paragraphs = self.PARAGRAPH_BREAK.split(text)

        current_pos = 0
        for paragraph in paragraphs:
            if not paragraph.strip():
                current_pos += len(paragraph) + 2  # +2 for \n\n
                continue

            # Check if paragraph is already a reasonable chunk size
            if len(paragraph) < self.chunk_target_tokens * self.chars_per_token:
                para_start = text.find(paragraph, current_pos)
                if para_start != -1:
                    sentences.append((para_start, para_start + len(paragraph), paragraph))
                current_pos = para_start + len(paragraph) + 2 if para_start != -1 else current_pos
                continue

            # Split paragraph into sentences
            splits = self.SENTENCE_ENDINGS.split(paragraph)
            for split in splits:
                split = split.strip()
                if len(split) < self.min_sentence_len:
                    continue

                # Find position in original text (only search from current_pos)
                pos = text.find(split, current_pos)
                if pos != -1:
                    sentences.append((pos, pos + len(split), split))
                    current_pos = pos + len(split)
                else:
                    # Fallback: append without position
                    sentences.append((current_pos, current_pos + len(split), split))
                    current_pos += len(split) + 1

        return sentences

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Input text.

        Returns:
            List of sentences.
        """
        # First try paragraph splitting for longer texts
        paragraphs = self.PARAGRAPH_BREAK.split(text)
        sentences = []

        for paragraph in paragraphs:
            if not paragraph.strip():
                continue

            # Check if paragraph is already a reasonable chunk size
            if len(paragraph) < self.chunk_target_tokens * self.chars_per_token:
                sentences.append(paragraph)
                continue

            # Split paragraph into sentences
            splits = self.SENTENCE_ENDINGS.split(paragraph)
            for split in splits:
                split = split.strip()
                if len(split) >= self.min_sentence_len:
                    sentences.append(split)

        return sentences

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        return len(text) // self.chars_per_token

    def _get_overlap(self, text: str, max_overlap_tokens: int) -> str:
        """Get overlapping text from the end.

        Args:
            text: Text to extract overlap from.
            max_overlap_tokens: Maximum tokens for overlap.

        Returns:
            Overlap text.
        """
        max_chars = max_overlap_tokens * self.chars_per_token
        if len(text) <= max_chars:
            return text

        # Get last N characters
        overlap = text[-max_chars:]
        # Try to start at a sentence boundary
        match = self.SENTENCE_ENDINGS.search(overlap)
        if match:
            overlap = overlap[match.end() :]

        return overlap.strip()


class ParagraphChunker(ChunkingStrategy):
    """Paragraph-based chunking.

    Splits text at paragraph boundaries. Each paragraph becomes a chunk.
    Good for structured documents with clear section breaks.

    Attributes:
        max_chars: Maximum characters per chunk (default: 2000).
        min_chars: Minimum characters for a valid paragraph.
    """

    def __init__(self, max_chars: int = 2000, min_chars: int = 50):
        """Initialize the paragraph chunker.

        Args:
            max_chars: Maximum characters per chunk.
            min_chars: Minimum characters for a valid paragraph.
        """
        self.max_chars = max_chars
        self.min_chars = min_chars

    async def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Chunk text at paragraph boundaries.

        Args:
            text: Input text to chunk.
            **kwargs: Additional options (max_chars override).

        Returns:
            List of paragraph-based chunks.
        """
        if not text:
            return []

        max_chars = kwargs.get("max_chars", self.max_chars)

        # Split into paragraphs
        paragraphs = re.split(r"\n{2,}", text)
        chunks = []

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if len(para) < self.min_chars:
                continue

            if len(para) <= max_chars:
                chunks.append(
                    Chunk(
                        text=para,
                        index=len(chunks),
                        chunk_type="paragraph",
                        metadata={"paragraph_num": i},
                    )
                )
            else:
                # Paragraph too long, split further
                subchunks = await SentenceChunker().chunk(para)
                for subchunk in subchunks:
                    subchunk.metadata["parent_paragraph"] = i
                chunks.extend(subchunks)

        logger.info(
            "Paragraph chunking completed",
            chunks=len(chunks),
        )

        return chunks


class SlidingWindowChunker(ChunkingStrategy):
    """Sliding window chunking with configurable overlap.

    Creates chunks by sliding a window across the text. Ensures all
    content is covered but may produce redundant chunks.

    Attributes:
        window_size: Window size in tokens.
        step_size: Step size in tokens (overlap = window_size - step_size).
    """

    def __init__(self, window_size: int = 512, step_size: int = 256):
        """Initialize the sliding window chunker.

        Args:
            window_size: Window size in tokens.
            step_size: Step size in tokens.
        """
        self.window_size = window_size
        self.step_size = step_size
        self.chars_per_token = 4

    async def chunk(self, text: str, **kwargs) -> list[Chunk]:
        """Chunk text using sliding window.

        Args:
            text: Input text to chunk.
            **kwargs: Additional options (window_size, step_size overrides).

        Returns:
            List of window-based chunks.
        """
        if not text:
            return []

        window_size = kwargs.get("window_size", self.window_size)
        step_size = kwargs.get("step_size", self.step_size)

        window_chars = window_size * self.chars_per_token
        step_chars = step_size * self.chars_per_token

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + window_chars, len(text))
            chunk_text = text[start:end]

            chunks.append(
                Chunk(
                    text=chunk_text,
                    index=len(chunks),
                    start_char=start,
                    end_char=end,
                    chunk_type="sliding_window",
                    metadata={"window_start": start, "window_end": end},
                )
            )

            start += step_chars

        logger.info(
            "Sliding window chunking completed",
            chunks=len(chunks),
            window_size=window_size,
            step_size=step_size,
        )

        return chunks


def create_chunker(strategy: str = "sentence", **kwargs) -> ChunkingStrategy:
    """Factory function to create a chunker by strategy name.

    Args:
        strategy: Strategy name (semantic, sentence, paragraph, sliding_window).
        **kwargs: Strategy-specific options.

    Returns:
        Configured ChunkingStrategy instance.
    """
    strategies = {
        "semantic": SemanticChunker,
        "sentence": SentenceChunker,
        "paragraph": ParagraphChunker,
        "sliding_window": SlidingWindowChunker,
    }

    if strategy not in strategies:
        raise ValueError(
            f"Unknown chunking strategy: {strategy}. Available: {list(strategies.keys())}"
        )

    return strategies[strategy](**kwargs)


async def chunk_text(
    text: str,
    strategy: str = "sentence",
    **kwargs,
) -> list[Chunk]:
    """Convenience function to chunk text.

    Args:
        text: Input text to chunk.
        strategy: Chunking strategy to use.
        **kwargs: Additional options.

    Returns:
        List of Chunk objects.
    """
    chunker = create_chunker(strategy, **kwargs)
    return await chunker.chunk(text, **kwargs)


__all__ = [
    "Chunk",
    "ChunkingStrategy",
    "SemanticChunker",
    "SentenceChunker",
    "ParagraphChunker",
    "SlidingWindowChunker",
    "create_chunker",
    "chunk_text",
]
