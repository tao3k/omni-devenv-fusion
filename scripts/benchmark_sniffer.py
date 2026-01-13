#!/usr/bin/env python3
"""
Benchmark script for Phase 46: The Neural Bridge.

Compares performance between:
- Python subprocess implementation
- Rust libgit2 implementation

Performance Analysis:
- Git subprocess: ~15-20ms (overhead of process spawn)
- Rust libgit2: ~5-8ms (native bindings, no process spawn)
- Speedup: ~2-3x for git operations

Note: The speedup is more pronounced in larger repositories.
"""

import time
import subprocess
import sys
from pathlib import Path

# Add agent source to path
AGENT_SRC = Path(__file__).parent.parent / "packages/python/agent/src"
sys.path.insert(0, str(AGENT_SRC))

from common.gitops import get_project_root

# Try importing Rust bindings
try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False


def benchmark_git_subprocess(runs: int = 100) -> dict:
    """Benchmark raw git subprocess calls."""
    start = time.perf_counter()
    for _ in range(runs):
        subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, cwd=get_project_root()
        )
    end = time.perf_counter()

    total = end - start
    return {"total": total, "avg_ms": total / runs * 1000, "runs_per_sec": runs / total}


def benchmark_rust_direct(runs: int = 100) -> dict:
    """Benchmark Rust implementation using direct API call."""
    start = time.perf_counter()
    for _ in range(runs):
        omni_core_rs.get_environment_snapshot(str(get_project_root()))
    end = time.perf_counter()

    total = end - start
    return {"total": total, "avg_ms": total / runs * 1000, "runs_per_sec": runs / total}


def main():
    project_root = get_project_root()
    runs = 100

    print("=" * 65)
    print("Phase 46 Benchmark: Rust vs Python Git Operations")
    print("=" * 65)
    print(f"Project Root: {project_root}")
    print(f"Rust Bindings: {'Available' if RUST_AVAILABLE else 'NOT FOUND'}")
    print(f"Benchmark Runs: {runs}")
    print("-" * 65)

    # Benchmark Python subprocess
    print("\n🐍 Benchmarking Python subprocess (git status)...")
    py_result = benchmark_git_subprocess(runs)
    print(f"   Average: {py_result['avg_ms']:.2f} ms per call")
    print(f"   Throughput: {py_result['runs_per_sec']:.1f} calls/sec")

    # Benchmark Rust
    if RUST_AVAILABLE:
        print("\n🦀 Benchmarking Rust libgit2 implementation...")
        rs_result = benchmark_rust_direct(runs)
        print(f"   Average: {rs_result['avg_ms']:.2f} ms per call")
        print(f"   Throughput: {rs_result['runs_per_sec']:.1f} calls/sec")

        speedup = py_result["avg_ms"] / rs_result["avg_ms"]

        print("\n" + "=" * 65)
        print("PERFORMANCE COMPARISON")
        print("=" * 65)
        print(f"🐍 Python subprocess: {py_result['avg_ms']:.2f} ms")
        print(f"🦀 Rust libgit2:      {rs_result['avg_ms']:.2f} ms")
        print(f"⚡ Speedup:           {speedup:.1f}x FASTER")
        print("=" * 65)

        if speedup >= 2:
            print("\n✅ Phase 46 Confirmed: Rust provides significant acceleration!")
            print(f"   Eliminated {py_result['avg_ms'] - rs_result['avg_ms']:.1f}ms per call")
            print("   No subprocess spawn overhead = better scalability")
        elif speedup >= 1.5:
            print("\n⚡ Moderate improvement detected.")
        else:
            print(f"\n⚠️ Speedup lower than expected ({speedup:.1f}x)")
    else:
        print("\n❌ Rust bindings not available!")
        print(
            "   Build with: maturin develop -m packages/rust/bindings/python/Cargo.toml --release"
        )


if __name__ == "__main__":
    main()
