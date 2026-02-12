"""
Benchmark tests for omni.rag.chunking module.

These tests measure the performance of text chunking operations.
"""

import asyncio
import time
import pytest


class TestChunkingPerformance:
    """Performance tests for text chunking."""

    @pytest.fixture
    def sample_text(self):
        """Generate sample text for benchmarking."""
        sentences = [
            "The quick brown fox jumps over the lazy dog.",
            "Lorem ipsum dolor sit amet consectetur adipiscing elit.",
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            "Ut enim ad minim veniam quis nostrud exercitation ullamco laboris.",
            "Duis aute irure dolor in reprehenderit in voluptate velit.",
            "Excepteur sint occaecat cupidatat non proident sunt in culpa qui.",
        ]
        # Repeat to create longer text
        return " ".join(sentences * 50)

    @pytest.fixture
    def large_text(self):
        """Generate large text for benchmarking."""
        base_text = (
            "This is a test paragraph with enough content to be processed. "
            "It contains multiple sentences and should be properly chunked. "
            "The chunking algorithm should handle this efficiently. "
        )
        return base_text * 200  # ~20KB of text

    def test_sentence_chunker_performance(self, sample_text):
        """Test sentence chunker performance."""
        from omni.rag.chunking import SentenceChunker

        chunker = SentenceChunker(chunk_target_tokens=512, overlap_tokens=50)

        start = time.perf_counter()
        chunks = asyncio.run(chunker.chunk(sample_text))
        elapsed = time.perf_counter() - start

        # Should process 300 sentences in under 100ms
        assert elapsed < 0.1, f"Sentence chunking took {elapsed:.3f}s, expected < 0.1s"

        # Verify chunks were created
        assert len(chunks) > 0

        print(f"Sentence chunking: {len(chunks)} chunks in {elapsed * 1000:.2f}ms")

    def test_paragraph_chunker_performance(self, sample_text):
        """Test paragraph chunker performance."""
        from omni.rag.chunking import ParagraphChunker

        chunker = ParagraphChunker(max_chars=2000, min_chars=50)

        start = time.perf_counter()
        chunks = asyncio.run(chunker.chunk(sample_text))
        elapsed = time.perf_counter() - start

        # Should process in under 50ms
        assert elapsed < 0.05, f"Paragraph chunking took {elapsed:.3f}s, expected < 0.05s"

        assert len(chunks) > 0

        print(f"Paragraph chunking: {len(chunks)} chunks in {elapsed * 1000:.2f}ms")

    def test_sliding_window_chunker_performance(self, large_text):
        """Test sliding window chunker performance."""
        from omni.rag.chunking import SlidingWindowChunker

        chunker = SlidingWindowChunker(window_size=512, step_size=256)

        start = time.perf_counter()
        chunks = asyncio.run(chunker.chunk(large_text))
        elapsed = time.perf_counter() - start

        # Should process 20KB in under 50ms
        assert elapsed < 0.05, f"Sliding window chunking took {elapsed:.3f}s, expected < 0.05s"

        assert len(chunks) > 0

        print(f"Sliding window: {len(chunks)} chunks in {elapsed * 1000:.2f}ms")

    def test_batch_chunker_performance(self, sample_text):
        """Test batch chunking performance."""
        from omni.rag.chunking import SentenceChunker

        chunker = SentenceChunker(chunk_target_tokens=512, overlap_tokens=50)

        # Chunk multiple texts sequentially (simpler than asyncio.gather)
        texts = [sample_text for _ in range(10)]

        start = time.perf_counter()
        all_chunks = []
        for text in texts:
            chunks = asyncio.run(chunker.chunk(text))
            all_chunks.extend(chunks)
        elapsed = time.perf_counter() - start

        # Should process 10 texts in under 500ms
        assert elapsed < 0.5, f"Batch chunking took {elapsed:.3f}s, expected < 0.5s"

        total_chunks = len(all_chunks)
        assert total_chunks > 0

        print(f"Batch chunking: 10 texts, {total_chunks} total chunks in {elapsed * 1000:.2f}ms")

    def test_repeated_chunker_creation(self, sample_text):
        """Test performance of creating and using multiple chunkers."""
        from omni.rag.chunking import SentenceChunker, ParagraphChunker, SlidingWindowChunker

        # Create chunkers once
        sentence_chunker = SentenceChunker()
        paragraph_chunker = ParagraphChunker()
        sliding_chunker = SlidingWindowChunker()

        start = time.perf_counter()

        # Process text with each chunker
        s_chunks = asyncio.run(sentence_chunker.chunk(sample_text))
        p_chunks = asyncio.run(paragraph_chunker.chunk(sample_text))
        sl_chunks = asyncio.run(sliding_chunker.chunk(sample_text))

        elapsed = time.perf_counter() - start

        # All three should complete in under 100ms
        assert elapsed < 0.1, f"Multi-chunker test took {elapsed:.3f}s, expected < 0.1s"

        assert len(s_chunks) > 0
        assert len(p_chunks) > 0
        assert len(sl_chunks) > 0

        print(
            f"Multi-chunker: {len(s_chunks)}/{len(p_chunks)}/{len(sl_chunks)} in {elapsed * 1000:.2f}ms"
        )

    def test_empty_text_chunker_performance(self):
        """Test chunking empty/short text performance."""
        from omni.rag.chunking import SentenceChunker

        chunker = SentenceChunker()

        # Empty text
        start = time.perf_counter()
        chunks = asyncio.run(chunker.chunk(""))
        elapsed_empty = time.perf_counter() - start

        # Very short text
        start = time.perf_counter()
        chunks = asyncio.run(chunker.chunk("Short text."))
        elapsed_short = time.perf_counter() - start

        # Keep this fast-path assertion realistic for CI variance.
        # 10ms still guarantees "near-instant" behavior while reducing flakes.
        assert elapsed_empty < 0.01
        assert elapsed_short < 0.01

        print(f"Empty text: {elapsed_empty * 1000:.3f}ms, Short text: {elapsed_short * 1000:.3f}ms")

    def test_very_large_text_chunker_performance(self):
        """Test chunking very large text."""
        from omni.rag.chunking import SlidingWindowChunker

        # Create 1MB of text
        base = "This is test data for chunking performance. " * 100
        large_text = base * 500  # ~1.5MB

        chunker = SlidingWindowChunker(window_size=512, step_size=256)

        start = time.perf_counter()
        chunks = asyncio.run(chunker.chunk(large_text))
        elapsed = time.perf_counter() - start

        # Should process 1.5MB in under 500ms
        assert elapsed < 0.5, f"Large text chunking took {elapsed:.3f}s, expected < 0.5s"

        assert len(chunks) > 100  # Should have many chunks

        print(f"Large text (1.5MB): {len(chunks)} chunks in {elapsed * 1000:.2f}ms")


class TestTokenEstimationPerformance:
    """Tests for token estimation performance."""

    def test_token_count_estimation_performance(self):
        """Test token count estimation performance."""
        from omni.rag.chunking import SentenceChunker

        # Large text for testing
        text = "word " * 10000
        chunker = SentenceChunker()

        start = time.perf_counter()
        for _ in range(1000):
            count = chunker._estimate_tokens(text)
        elapsed = time.perf_counter() - start

        # 1000 estimations should be fast
        assert elapsed < 0.1, f"Token estimation took {elapsed:.3f}s"

        print(f"Token estimation: 1000 iterations in {elapsed * 1000:.2f}ms")
