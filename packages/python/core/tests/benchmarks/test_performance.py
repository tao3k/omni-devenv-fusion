"""
test_performance.py - Benchmark Tests for Rust-Coupled Performance

This module contains performance benchmarks that measure the critical
paths of the Rust-Python integration layer.

Run with:
    uv run pytest packages/python/core/tests/benchmarks/ -v --benchmark-only -n 0
"""

from __future__ import annotations

import pytest
import asyncio
import json
from pathlib import Path


class TestCortexBenchmarks:
    """Benchmarks for Cortex (Vector Store) operations."""

    @pytest.mark.benchmark(group="cortex")
    @pytest.mark.asyncio
    async def test_benchmark_vector_search(self, benchmark, temp_lancedb):
        """
        Benchmark: Vector similarity search via Rust LanceDB.
        Target: < 5ms for 10 nearest neighbors.
        """
        from omni.foundation.bridge import RustVectorStore

        # Setup: Initialize vector store and add test vectors
        store = RustVectorStore(str(temp_lancedb), dimension=384)

        # Add test vectors
        test_ids = [f"doc_{i}" for i in range(100)]
        test_vectors = [[0.1 * i] * 384 for i in range(100)]
        test_contents = [f"Document {i} content" for i in range(100)]
        test_metadatas = [json.dumps({"id": i}) for i in range(100)]

        await store.add_documents(
            table_name="test",
            ids=test_ids,
            vectors=test_vectors,
            contents=test_contents,
            metadatas=test_metadatas,
        )

        async def _search():
            return await store.search("test query", limit=10)

        results = await benchmark.pedantic(_search, iterations=3, rounds=20)
        assert len(results) <= 10

    @pytest.mark.benchmark(group="cortex")
    @pytest.mark.asyncio
    async def test_benchmark_vector_upsert(self, benchmark, temp_lancedb):
        """
        Benchmark: Single vector upsert with metadata.
        Target: < 10ms per operation.
        """
        from omni.foundation.bridge import RustVectorStore

        store = RustVectorStore(str(temp_lancedb), dimension=384)

        async def _upsert():
            await store.add_documents(
                table_name="test",
                ids=["single_doc"],
                vectors=[[0.5] * 384],
                contents=["Single document"],
                metadatas=['{"test": true}'],
            )

        result = await benchmark.pedantic(_upsert, iterations=1, rounds=30)
        assert result is None  # add_documents returns None


class TestBrainBenchmarks:
    """Benchmarks for Brain (Checkpoint/Persistence) operations."""

    @pytest.mark.benchmark(group="brain")
    @pytest.mark.asyncio
    async def test_benchmark_checkpoint_save(self, benchmark, temp_lancedb):
        """
        Benchmark: State persistence (Write).
        Target: < 10ms per checkpoint.
        """
        from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

        saver = RustLanceCheckpointSaver(base_path=str(temp_lancedb))
        config = {"configurable": {"thread_id": "bench_thread"}}
        checkpoint = {"id": "step_1", "v": 1}
        metadata = {"ts": 123456.0}

        async def _save():
            await saver.aput(config, checkpoint, metadata, {})

        await benchmark.pedantic(_save, iterations=1, rounds=20)

    @pytest.mark.benchmark(group="brain")
    @pytest.mark.asyncio
    async def test_benchmark_checkpoint_read(self, benchmark, temp_lancedb):
        """
        Benchmark: State persistence (Read).
        Target: < 5ms per read.
        """
        from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

        saver = RustLanceCheckpointSaver(base_path=str(temp_lancedb))
        config = {"configurable": {"thread_id": "bench_read_thread"}}
        # Pre-save one item
        await saver.aput(config, {"id": "1", "v": 1}, {}, {})

        async def _read():
            return await saver.aget_tuple(config)

        result = await benchmark.pedantic(_read, iterations=1, rounds=50)
        assert result is not None


class TestSnifferBenchmarks:
    """Benchmarks for Sniffer (Skill Scanner) operations."""

    @pytest.mark.benchmark(group="sniffer")
    @pytest.mark.asyncio
    async def test_benchmark_skill_scan_from_db(self, benchmark, temp_lancedb):
        """
        Benchmark: Skill scanning from LanceDB (Rust-backed).
        Target: < 20ms for all skills.
        """
        from omni.foundation.bridge.scanner import PythonSkillScanner

        # Pre-populate vector store with tools for scanning
        from omni.foundation.bridge import RustVectorStore

        store = RustVectorStore(str(temp_lancedb), dimension=384)
        # Add some test tools
        for i in range(20):
            await store.add_documents(
                table_name="skills",
                ids=[f"tool_{i}"],
                vectors=[[0.1 * i] * 384],
                contents=[f"Tool {i} for skill test_skill_{i % 3}"],
                metadatas=[
                    json.dumps(
                        {
                            "skill_name": f"test_skill_{i % 3}",
                            "tool_name": f"tool_{i}",
                            "description": f"Description for tool {i}",
                        }
                    )
                ],
            )

        scanner = PythonSkillScanner()

        async def _scan():
            return scanner.scan_directory()

        result = await benchmark.pedantic(_scan, iterations=3, rounds=20)
        assert result is not None

    @pytest.mark.benchmark(group="sniffer")
    def test_benchmark_skill_scan_per_skill(self, benchmark, skills_path):
        """
        Benchmark: Single skill metadata parsing.
        Target: < 5ms per skill.
        """
        from omni.foundation.bridge.scanner import PythonSkillScanner

        # Create test skill
        skill_dir = skills_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test_skill
version: 1.0.0
description: Test skill
""")
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "test.py").write_text('"""Test command."""')

        scanner = PythonSkillScanner()

        def _scan():
            return scanner.parse_skill_metadata(str(skill_dir))

        result = benchmark(_scan)
        assert result is not None


class TestKernelBenchmarks:
    """Benchmarks for Kernel operations."""

    @pytest.mark.benchmark(group="kernel")
    @pytest.mark.asyncio
    async def test_benchmark_checkpointer_creation(self, benchmark, temp_lancedb):
        """
        Benchmark: Checkpointer creation.
        Target: < 50ms for checkpointer instantiation.
        """
        from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

        async def _create():
            saver = RustLanceCheckpointSaver(base_path=str(temp_lancedb))
            return saver

        saver = await benchmark.pedantic(_create, iterations=1, rounds=10)
        assert saver is not None

    @pytest.mark.benchmark(group="kernel")
    @pytest.mark.asyncio
    async def test_benchmark_vector_store_creation(self, benchmark, temp_lancedb):
        """
        Benchmark: Vector store creation.
        Target: < 50ms for store instantiation.
        """
        from omni.foundation.bridge import RustVectorStore

        async def _create():
            store = RustVectorStore(str(temp_lancedb), dimension=384)
            return store

        store = await benchmark.pedantic(_create, iterations=1, rounds=10)
        assert store is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only", "-n", "0"])
