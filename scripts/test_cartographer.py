#!/usr/bin/env python3
"""
scripts/test_cartographer.py
Phase 50.5: The Map Room - AX Efficiency Verification

Demonstrates the efficiency gains of AST-based code navigation using
the omni-tags Rust library (ast-grep-core 0.40.5) compared to full file reads.

AX Philosophy: "Map over Territory"
- Full content: ~5000 tokens for a large file
- Outline only: ~50 tokens (100x reduction)

Usage:
    python scripts/test_cartographer.py [--target <file>]

Example:
    python scripts/test_cartographer.py --target packages/python/agent/src/agent/core/agents/base.py
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages/python/agent/src"))

from agent.core.context_compressor import count_tokens

# Import Rust bindings (omni-tags via omni_core_rs)
try:
    import omni_core_rs

    RUST_AVAILABLE = True
except ImportError as e:
    RUST_AVAILABLE = False
    print(f"[WARNING] omni_core_rs not available: {e}")
    print("[INFO] Run 'just build-rust' to compile the Rust bindings.")


def test_ax_efficiency(
    target_file: str = "packages/python/agent/src/agent/core/agents/base.py",
) -> dict:
    """
    Test AX efficiency by comparing full read vs Rust-based outline.

    Uses omni-tags (ast-grep-core 0.40.5) for AST-based symbol extraction.

    Returns a dictionary with efficiency metrics.
    """
    target_path = PROJECT_ROOT / target_file

    if not target_path.exists():
        return {"error": f"File not found: {target_path}"}

    # Full Content (Old Way - 5800 tokens)
    with open(target_path, "r") as f:
        full_content = f.read()
    cost_full = count_tokens(full_content)

    # Map (New Way - 50 tokens) using Rust omni-tags library
    if RUST_AVAILABLE:
        try:
            outline = omni_core_rs.get_file_outline(str(target_path))  # type: ignore[attr-defined]
        except AttributeError:
            return {
                "error": "get_file_outline not found in omni_core_rs",
                "hint": "Rebuild Rust bindings: cd packages/rust/bindings/python && maturin develop",
                "full_tokens": cost_full,
            }
    else:
        return {
            "error": "omni_core_rs not available",
            "hint": "Build Rust bindings first",
            "full_tokens": cost_full,
            "target": str(target_path),
        }

    cost_map = count_tokens(outline)
    compression_rate = cost_full / max(1, cost_map)

    return {
        "target": str(target_path),
        "full_tokens": cost_full,
        "outline_tokens": cost_map,
        "compression_rate": compression_rate,
        "outline": outline,
        "engine": "ast-grep-core 0.40.5 (Rust)",
    }


def format_result(result: dict) -> str:
    """Format the result for display."""
    if "error" in result:
        lines = [
            "=" * 60,
            "Phase 50.5: The Map Room - Error",
            "=" * 60,
            f"Error: {result['error']}",
        ]
        if "hint" in result:
            lines.append(f"Hint: {result['hint']}")
        if "full_tokens" in result:
            lines.append(f"Full content cost: {result['full_tokens']:,} tokens")
        lines.append("=" * 60)
        return "\n".join(lines)

    lines = [
        "=" * 60,
        "Phase 50.5: The Map Room - AX Efficiency Analysis",
        "=" * 60,
        "",
        f"Target: {result['target']}",
        f"Engine: {result['engine']}",
        "",
        f"  Full Read Cost:  {result['full_tokens']:,} tokens",
        f"  Outline Cost:    {result['outline_tokens']:,} tokens",
        f"  Compression:     {result['compression_rate']:.1f}x",
        "",
        "  Outline Preview:",
        "  " + "-" * 50,
    ]

    # Show first 10 lines of outline
    outline_lines = result["outline"].split("\n")
    for line in outline_lines[:10]:
        lines.append(f"  {line}")
    if len(outline_lines) > 10:
        lines.append(f"  ... and {len(outline_lines) - 10} more lines")

    lines.extend(
        [
            "  " + "-" * 50,
            "",
            "AX Efficiency: Agent can understand file structure with",
            f"{result['compression_rate']:.1f}x less context usage.",
            "",
            "The Cartographer Principle: 'A good map is worth a thousand lines.'",
            "=" * 60,
        ]
    )

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Test AX efficiency of AST-based code navigation (omni-tags Rust library)"
    )
    parser.add_argument(
        "--target",
        default="packages/python/agent/src/agent/core/agents/base.py",
        help="Target file to analyze (relative to project root)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    args = parser.parse_args()

    result = test_ax_efficiency(args.target)

    if args.json:
        import json

        print(json.dumps(result, indent=2))
    else:
        print(format_result(result))

    # Return exit code based on compression rate
    if "compression_rate" in result and result["compression_rate"] >= 10:
        return 0  # Good efficiency
    return 1  # Could be better


if __name__ == "__main__":
    sys.exit(main())
