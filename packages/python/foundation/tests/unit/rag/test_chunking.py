"""
Tests for omni.rag.chunking module.
"""

import pytest
import pytest_asyncio


class TestChunkDataclass:
    """Test Chunk dataclass."""

    def test_chunk_creation(self):
        """Test basic chunk creation."""
        from omni.rag.chunking import Chunk

        chunk = Chunk(text="Hello world", index=0)
        assert chunk.text == "Hello world"
        assert chunk.index == 0
        assert chunk.chunk_type == "semantic"
        assert chunk.metadata == {}

    def test_chunk_with_metadata(self):
        """Test chunk creation with metadata."""
        from omni.rag.chunking import Chunk

        chunk = Chunk(
            text="Test content",
            index=1,
            start_char=10,
            end_char=22,
            chunk_type="sentence",
            metadata={"source": "pdf"},
        )
        assert chunk.start_char == 10
        assert chunk.end_char == 22
        assert chunk.metadata["source"] == "pdf"

    def test_chunk_char_count(self):
        """Test chunk character count property."""
        from omni.rag.chunking import Chunk

        chunk = Chunk(text="Hello", index=0)
        assert chunk.char_count == 5

    def test_chunk_token_count(self):
        """Test chunk token count estimation."""
        from omni.rag.chunking import Chunk

        chunk = Chunk(text="Hello world test", index=0)
        # 17 chars / 4 = ~4 tokens
        assert chunk.token_count == 4


class TestSentenceChunker:
    """Test SentenceChunker class."""

    def test_default_initialization(self):
        """Test sentence chunker default values."""
        from omni.rag.chunking import SentenceChunker

        chunker = SentenceChunker()
        assert chunker.chunk_target_tokens == 512
        assert chunker.overlap_tokens == 50
        assert chunker.min_sentence_len == 20

    @pytest.mark.asyncio
    async def test_chunk_simple_text(self):
        """Test chunking simple text."""
        from omni.rag.chunking import SentenceChunker

        text = "This is sentence one. This is sentence two. This is sentence three."
        chunker = SentenceChunker(chunk_target_tokens=100, overlap_tokens=10)
        chunks = await chunker.chunk(text)

        assert len(chunks) >= 1
        assert chunks[0].chunk_type == "sentence"

    @pytest.mark.asyncio
    async def test_chunk_empty_text(self):
        """Test chunking empty text returns empty list."""
        from omni.rag.chunking import SentenceChunker

        chunker = SentenceChunker()
        chunks = await chunker.chunk("")
        assert chunks == []

    @pytest.mark.asyncio
    async def test_chunk_preserves_sentence_boundaries(self):
        """Test that chunks preserve sentence boundaries."""
        from omni.rag.chunking import SentenceChunker

        text = "First sentence. Second sentence. Third sentence."
        chunker = SentenceChunker(chunk_target_tokens=100, overlap_tokens=0)
        chunks = await chunker.chunk(text)

        # All sentences should be in some chunk
        combined = " ".join(c.text for c in chunks)
        assert "First sentence" in combined
        assert "Second sentence" in combined
        assert "Third sentence" in combined


class TestParagraphChunker:
    """Test ParagraphChunker class."""

    def test_default_initialization(self):
        """Test paragraph chunker default values."""
        from omni.rag.chunking import ParagraphChunker

        chunker = ParagraphChunker()
        assert chunker.max_chars == 2000
        assert chunker.min_chars == 50

    @pytest.mark.asyncio
    async def test_chunk_single_paragraph(self):
        """Test chunking single paragraph."""
        from omni.rag.chunking import ParagraphChunker

        # Create longer paragraphs (>= 50 chars each)
        text = (
            "This is a single paragraph that is long enough to be processed.\n\n"
            "It has two lines but should be treated as one paragraph structure."
        )
        chunker = ParagraphChunker()
        chunks = await chunker.chunk(text)

        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_chunk_multiple_paragraphs(self):
        """Test chunking multiple paragraphs."""
        from omni.rag.chunking import ParagraphChunker

        # Create longer paragraphs (>= 50 chars each)
        text = (
            "First paragraph with enough content to be processed by the chunker.\n\n"
            "Second paragraph also has sufficient length for the chunker.\n\n"
            "Third paragraph is also long enough to pass the minimum character check."
        )
        chunker = ParagraphChunker()
        chunks = await chunker.chunk(text)

        assert len(chunks) == 3
        for chunk in chunks:
            assert chunk.chunk_type == "paragraph"


class TestSlidingWindowChunker:
    """Test SlidingWindowChunker class."""

    def test_default_initialization(self):
        """Test sliding window chunker default values."""
        from omni.rag.chunking import SlidingWindowChunker

        chunker = SlidingWindowChunker()
        assert chunker.window_size == 512
        assert chunker.step_size == 256

    @pytest.mark.asyncio
    async def test_chunk_short_text(self):
        """Test chunking text shorter than window."""
        from omni.rag.chunking import SlidingWindowChunker

        text = "Short text."
        chunker = SlidingWindowChunker(window_size=512, step_size=256)
        chunks = await chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].chunk_type == "sliding_window"

    @pytest.mark.asyncio
    async def test_chunk_longer_text(self):
        """Test chunking text that requires multiple windows."""
        from omni.rag.chunking import SlidingWindowChunker

        text = "word " * 1000  # 5000 chars
        chunker = SlidingWindowChunker(window_size=500, step_size=250)
        chunks = await chunker.chunk(text)

        assert len(chunks) > 1
        assert chunks[0].chunk_type == "sliding_window"

    @pytest.mark.asyncio
    async def test_window_positions(self):
        """Test that windows have correct positions."""
        from omni.rag.chunking import SlidingWindowChunker

        # Create text that is 2x window size to force sliding
        text = "0123456789" * 20  # 200 chars
        chunker = SlidingWindowChunker(window_size=50, step_size=25)
        chunks = await chunker.chunk(text)

        # With window_size=50 and text=200 chars, we should have multiple chunks
        assert len(chunks) >= 2
        # Check that chunks have correct window metadata
        for chunk in chunks:
            assert "window_start" in chunk.metadata
            assert "window_end" in chunk.metadata
            assert chunk.metadata["window_start"] < chunk.metadata["window_end"]


class TestSemanticChunker:
    """Test SemanticChunker class."""

    def test_default_initialization(self):
        """Test semantic chunker default values."""
        from omni.rag.chunking import SemanticChunker

        chunker = SemanticChunker()
        assert chunker.chunk_target_tokens == 512
        assert chunker.overlap_tokens == 50

    @pytest.mark.asyncio
    async def test_chunk_without_llm_uses_fallback(self):
        """Test semantic chunker falls back to sentence chunking without LLM."""
        from omni.rag.chunking import SemanticChunker

        text = "This is a test. This is only a test."
        chunker = SemanticChunker(llm_complete_func=None)
        chunks = await chunker.chunk(text)

        # Should fall back to sentence chunking
        assert len(chunks) >= 1
        assert chunks[0].chunk_type == "sentence"

    @pytest.mark.asyncio
    async def test_chunk_empty_text(self):
        """Test chunking empty text returns empty list."""
        from omni.rag.chunking import SemanticChunker

        chunker = SemanticChunker()
        chunks = await chunker.chunk("")
        assert chunks == []


class TestChunkingFactoryFunctions:
    """Test module-level factory functions."""

    def test_create_chunker_sentence(self):
        """Test creating sentence chunker."""
        from omni.rag.chunking import create_chunker, SentenceChunker

        chunker = create_chunker("sentence")
        assert isinstance(chunker, SentenceChunker)

    def test_create_chunker_paragraph(self):
        """Test creating paragraph chunker."""
        from omni.rag.chunking import create_chunker, ParagraphChunker

        chunker = create_chunker("paragraph")
        assert isinstance(chunker, ParagraphChunker)

    def test_create_chunker_sliding_window(self):
        """Test creating sliding window chunker."""
        from omni.rag.chunking import create_chunker, SlidingWindowChunker

        chunker = create_chunker("sliding_window")
        assert isinstance(chunker, SlidingWindowChunker)

    def test_create_chunker_invalid(self):
        """Test creating invalid chunker raises error."""
        from omni.rag.chunking import create_chunker

        with pytest.raises(ValueError):
            create_chunker("invalid_strategy")

    @pytest.mark.asyncio
    async def test_chunk_text_convenience(self):
        """Test convenience chunk_text function."""
        from omni.rag.chunking import chunk_text

        text = "One sentence. Two sentence."
        chunks = await chunk_text(text, strategy="sentence")
        assert len(chunks) >= 1
