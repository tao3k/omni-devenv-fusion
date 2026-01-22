#!/usr/bin/env python3
"""
benchmark_rust_core.py - Rust Core Performance Benchmarks

The Hardening - Benchmark Rust vs Python implementations.

Usage:
    python scripts/benchmark_rust_core.py
    python scripts/benchmark_rust_core.py --category io
    python scripts/benchmark_rust_core.py --category tokenizer
    python scripts/benchmark_rust_core.py --category vector
    python scripts/benchmark_rust_core.py --all

Benchmark Categories:
1. IO Benchmark: Read 14MB file - Rust vs Python
2. Tokenizer Benchmark: Count tokens - omni-tokenizer vs tiktoken
3. Vector Search Benchmark: Insert/Search 10k vectors
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Setup import paths
_PRJ_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PRJ_ROOT / "packages" / "python" / "agent" / "src"))
sys.path.insert(0, str(_PRJ_ROOT / "packages" / "python" / "common" / "src"))

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    category: str
    rust_time_ms: float
    python_time_ms: float
    speedup: float
    iterations: int


@dataclass
class BenchmarkCategory:
    """A category of benchmarks."""

    name: str
    description: str
    benchmarks: list[Callable[[], BenchmarkResult]]


def format_duration(ms: float) -> str:
    """Format duration in appropriate units."""
    if ms < 1:
        return f"{ms * 1000:.2f} μs"
    elif ms < 1000:
        return f"{ms:.2f} ms"
    else:
        return f"{ms / 1000:.2f} s"


def format_speedup(speedup: float) -> str:
    """Format speedup with color."""
    if speedup > 1:
        return f"[green]{speedup:.2f}x[/green]"
    elif speedup < 1:
        return f"[red]{speedup:.2f}x[/red]"
    else:
        return f"{speedup:.2f}x"


# =============================================================================
# IO Benchmarks - Rust vs Python file reading
# =============================================================================


def benchmark_file_read_rust(file_path: Path, iterations: int = 100) -> float:
    """Read file using Rust omni-core-rs read_file_safe."""
    try:
        # Use omni_core_rs.read_file_safe
        import omni_core_rs

        total_time = 0.0
        for _ in range(iterations):
            start = time.perf_counter()
            # read_file_safe takes path and max_bytes (use larger limit)
            content = omni_core_rs.read_file_safe(str(file_path), 104857600)
            end = time.perf_counter()
            total_time += (end - start) * 1000  # Convert to ms

        return total_time / iterations
    except ImportError:
        return float("inf")


def benchmark_file_read_python(file_path: Path, iterations: int = 100) -> float:
    """Read file using standard Python."""
    total_time = 0.0
    for _ in range(iterations):
        start = time.perf_counter()
        content = file_path.read_text(encoding="utf-8")
        end = time.perf_counter()
        total_time += (end - start) * 1000

    return total_time / iterations


def run_io_benchmark() -> BenchmarkResult:
    """Run IO benchmark: Rust vs Python file reading."""
    # Create a test file (within Rust limit - 10MB)
    test_file = _PRJ_ROOT / ".cache" / "benchmark_test.txt"
    if not test_file.exists():
        # Create ~5MB test file
        test_file.parent.mkdir(parents=True, exist_ok=True)
        content = "benchmark test content\n" * 40000  # ~2.2MB per iteration
        test_file.write_text(content * 2, encoding="utf-8")  # ~4.4MB total

    file_size_mb = test_file.stat().st_size / (1024 * 1024)
    console.print(f"[dim]Test file size: {file_size_mb:.2f} MB[/dim]")

    iterations = 50

    rust_time = benchmark_file_read_rust(test_file, iterations)
    python_time = benchmark_file_read_python(test_file, iterations)

    speedup = python_time / rust_time if rust_time > 0 else 1.0

    return BenchmarkResult(
        name="File Reading (4.5MB)",
        category="IO",
        rust_time_ms=rust_time,
        python_time_ms=python_time,
        speedup=speedup,
        iterations=iterations,
    )


# =============================================================================
# Tokenizer Benchmarks - Rust vs Python tokenization
# =============================================================================


def benchmark_tokenize_rust(text: str, iterations: int = 100) -> float:
    """Tokenize using Rust omni-core-rs count_tokens."""
    try:
        # Use omni_core_rs.count_tokens
        import omni_core_rs

        # Warm-up: First call initializes the BPE cache
        _ = omni_core_rs.count_tokens(text)

        total_time = 0.0
        for _ in range(iterations):
            start = time.perf_counter()
            count = omni_core_rs.count_tokens(text)
            end = time.perf_counter()
            total_time += (end - start) * 1000

        return total_time / iterations
    except ImportError:
        return float("inf")


def benchmark_tokenize_tiktoken(text: str, iterations: int = 100) -> float:
    """Tokenize using tiktoken."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")

        # Warm-up: First call to ensure encoding is loaded
        _ = enc.encode(text)

        total_time = 0.0
        for _ in range(iterations):
            start = time.perf_counter()
            tokens = enc.encode(text)
            count = len(tokens)
            end = time.perf_counter()
            total_time += (end - start) * 1000

        return total_time / iterations
    except ImportError:
        return float("inf")


def run_tokenizer_benchmark() -> BenchmarkResult:
    """Run tokenizer benchmark: omni-tokenizer vs tiktoken.

    NOTE: This benchmark compares two Rust implementations!
    - Python tiktoken calls tiktoken-rs directly (optimized FFI)
    - Rust omni_tokenizer calls tiktoken-rs then crosses PyO3 boundary

    The PyO3 boundary overhead makes Rust wrapper slower for this case.
    omni_tokenizer's value is in providing consistent caching and error handling,
    not raw speed for this specific operation.
    """
    # Create test text (simulate typical code file)
    test_text = (
        """
    def hello_world():
        '''A simple hello world function'''
        print("Hello, World!")
        return True

    class MyClass:
        def __init__(self, name):
            self.name = name

        def greet(self):
            return f"Hello, {self.name}!"
    """
        * 1000
    )  # Repeat to make it substantial

    iterations = 100

    rust_time = benchmark_tokenize_rust(test_text, iterations)
    python_time = benchmark_tokenize_tiktoken(test_text, iterations)

    speedup = python_time / rust_time if rust_time > 0 else 1.0

    return BenchmarkResult(
        name="Token Count (cl100k_base)",
        category="Tokenizer",
        rust_time_ms=rust_time,
        python_time_ms=python_time,
        speedup=speedup,
        iterations=iterations,
    )


# =============================================================================
# Vector Search Benchmarks - Rust vs Python
# =============================================================================


def benchmark_vector_search_rust(n_vectors: int = 1000, dim: int = 768) -> float:
    """Insert and search vectors using Rust omni-vector-rs.

    NOTE: This tests full database operations including disk I/O.
    LanceDB persists data to disk for durability, unlike pure numpy in-memory ops.
    For production use, this is the fair comparison (database vs database).
    """
    try:
        # Use omni_vector_rs.create_vector_store
        # Merged into omni_core_rs
        import omni_core_rs

        # Use temp directory for test with unique name
        import tempfile
        import uuid

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create store with specified dimension
            store = omni_core_rs.create_vector_store(tmpdir, dim)

            # Generate test vectors
            import numpy as np

            vectors = np.random.rand(n_vectors, dim).tolist()
            ids = [f"vec_{i}" for i in range(n_vectors)]
            contents = [f"Document {i}" for i in range(n_vectors)]
            metadatas = [json.dumps({"index": i}) for i in range(n_vectors)]

            # Use unique table name to avoid conflicts
            table_name = f"bench_{uuid.uuid4().hex[:8]}"

            # Warm-up: Create table and add initial data
            store.add_documents(table_name, [ids[0]], [vectors[0]], [contents[0]], [metadatas[0]])
            _ = store.search(table_name, vectors[0], 1)

            # Time the insert (rest of vectors)
            start = time.perf_counter()
            store.add_documents(table_name, ids[1:], vectors[1:], contents[1:], metadatas[1:])
            insert_time = (time.perf_counter() - start) * 1000

            # Time the search
            query_vec = np.random.rand(dim).tolist()
            start = time.perf_counter()
            _ = store.search(table_name, query_vec, 10)
            search_time = (time.perf_counter() - start) * 1000

            return insert_time + search_time
    except ImportError:
        return float("inf")


def benchmark_vector_search_python(n_vectors: int = 1000, dim: int = 768) -> float:
    """Insert and search vectors using Python (numpy)."""
    import numpy as np

    # Generate test vectors
    vectors = np.random.rand(n_vectors, dim)
    ids = [f"vec_{i}" for i in range(n_vectors)]

    # Time the insert (numpy array creation)
    start = time.perf_counter()
    arr = np.array(vectors)
    insert_time = (time.perf_counter() - start) * 1000

    # Time the search (cosine similarity)
    query_vec = np.random.rand(dim)
    start = time.perf_counter()
    similarities = np.dot(arr, query_vec) / (
        np.linalg.norm(arr, axis=1) * np.linalg.norm(query_vec) + 1e-10
    )
    top_k = np.argsort(similarities)[-10:]
    search_time = (time.perf_counter() - start) * 1000

    return insert_time + search_time


def run_vector_benchmark() -> BenchmarkResult:
    """Run vector search benchmark: omni-vector vs numpy."""
    n_vectors = 1000
    dim = 768

    rust_time = benchmark_vector_search_rust(n_vectors, dim)
    python_time = benchmark_vector_search_python(n_vectors, dim)

    speedup = python_time / rust_time if rust_time > 0 else 1.0

    return BenchmarkResult(
        name=f"Vector Search ({n_vectors} vectors, dim={dim})",
        category="Vector",
        rust_time_ms=rust_time,
        python_time_ms=python_time,
        speedup=speedup,
        iterations=1,
    )


# =============================================================================
# Benchmark Runner
# =============================================================================


def run_benchmarks(categories: list[str] | None = None) -> list[BenchmarkResult]:
    """Run all selected benchmarks."""
    results = []

    available_categories = {
        "io": [("File Reading", run_io_benchmark)],
        "tokenizer": [("Token Count", run_tokenizer_benchmark)],
        "vector": [("Vector Search", run_vector_benchmark)],
    }

    selected = categories if categories else list(available_categories.keys())

    for cat in selected:
        if cat not in available_categories:
            console.print(f"[yellow]Unknown category: {cat}, skipping...[/yellow]")
            continue

        console.print(f"\n[bold]Running {cat.upper()} benchmarks...[/bold]")

        for name, benchmark_fn in available_categories[cat]:
            try:
                result = benchmark_fn()
                result.name = name
                results.append(result)
                console.print(
                    f"  [dim]✓ {name}: Rust={format_duration(result.rust_time_ms)}, "
                    f"Python={format_duration(result.python_time_ms)}, "
                    f"Speedup={result.speedup:.2f}x[/dim]"
                )
            except Exception as e:
                console.print(f"  [red]✗ {name}: {e}[/red]")

    return results


def print_results_table(results: list[BenchmarkResult]) -> None:
    """Print benchmark results in a formatted table."""
    if not results:
        console.print("[yellow]No results to display.[/yellow]")
        return

    # Group by category
    by_category: dict[str, list[BenchmarkResult]] = {}
    for r in results:
        by_category.setdefault(r.category, []).append(r)

    for category, items in by_category.items():
        table = Table(
            title=f"{category} Benchmarks",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Benchmark")
        table.add_column("Rust Time")
        table.add_column("Python Time")
        table.add_column("Speedup")
        table.add_column("Status")

        for r in items:
            status = "✓ Rust Faster" if r.speedup > 1 else "≈ Equal"
            table.add_row(
                r.name,
                format_duration(r.rust_time_ms),
                format_duration(r.python_time_ms),
                format_speedup(r.speedup),
                status,
            )

        console.print(table)


def print_summary(results: list[BenchmarkResult]) -> None:
    """Print summary of benchmark results."""
    if not results:
        return

    avg_speedup = sum(r.speedup for r in results) / len(results)
    rust_wins = sum(1 for r in results if r.speedup > 1.1)

    console.print("\n[bold]Summary[/bold]")
    console.print(f"  Average Speedup: {avg_speedup:.2f}x")
    console.print(f"  Rust Wins: {rust_wins}/{len(results)} benchmarks")

    if avg_speedup > 1:
        console.print("  [green]✓ Rust Core shows performance advantage[/green]")
    else:
        console.print("  [yellow]→ Python implementation comparable or better[/yellow]")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Rust Core Performance Benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--category",
        "-c",
        action="append",
        choices=["io", "tokenizer", "vector"],
        help="Run specific benchmark category",
    )
    parser.add_argument("--all", "-a", action="store_true", help="Run all benchmarks (default)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    console.print("[bold cyan]Rust Core Performance Benchmarks[/bold cyan]")
    console.print("[dim]The Hardening[/dim]\n")

    categories = args.category if args.category else None

    results = run_benchmarks(categories)

    if args.json:
        output = {
            "timestamp": time.time(),
            "results": [
                {
                    "name": r.name,
                    "category": r.category,
                    "rust_time_ms": r.rust_time_ms,
                    "python_time_ms": r.python_time_ms,
                    "speedup": r.speedup,
                }
                for r in results
            ],
        }
        console.print(json.dumps(output, indent=2))
    else:
        print_results_table(results)
        print_summary(results)


if __name__ == "__main__":
    main()
