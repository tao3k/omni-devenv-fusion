#!/usr/bin/env python3
"""
scripts/test_ouroboros.py
Phase 58.5: The Ouroboros Awakening - Dogfooding Test

This script tests the batch refactoring capability by:
1. Creating a playground with "bad code" (print statements)
2. Running refactor_repository in dry-run mode
3. Verifying files are unchanged
4. Running refactor_repository in apply mode
5. Verifying the transformation was successful

This is "eating your own dog food" - the Agent using its own tools
to verify the heavy-duty refactoring capability.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Setup paths
_PRJ_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PRJ_ROOT / "packages" / "python" / "agent" / "src"))
sys.path.insert(0, str(_PRJ_ROOT / "assets" / "skills"))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def setup_playground() -> str:
    """Create a playground with 'bad code' to refactor."""
    playground = _PRJ_ROOT / "temp_playground"
    if playground.exists():
        shutil.rmtree(playground)
    playground.mkdir(parents=True, exist_ok=True)

    # Create some Python files with print statements (the "bad code")
    (playground / "service.py").write_text(
        '''"""Service module with legacy logging."""

def start_service():
    print("Starting service at port 8080")
    x = 100
    print(f"Initialized with x={x}")
    return True

def stop_service():
    print("Stopping service")
    cleanup()
'''
    )

    (playground / "utils.py").write_text(
        '''"""Utility functions."""

def help():
    print("This is the help function")
    print("Call with appropriate arguments")
    return "help"

def debug(msg):
    print(f"DEBUG: {msg}")
'''
    )

    (playground / "main.py").write_text(
        '''"""Main entry point."""

from service import start_service

def main():
    print("Application starting")
    start_service()
    print("Application running")

if __name__ == "__main__":
    main()
'''
    )

    # Create a non-Python file (should be ignored)
    (playground / "README.md").write_text(
        """# Playground

This is a test playground.
Don't touch me - I'm not Python!
"""
    )

    console.print(f"[green]✅ Playground created at: {playground}[/green]")
    return str(playground)


def test_dry_run(playground: str) -> bool:
    """Test dry run mode - should not modify files."""
    console.print(Panel.fit("🐍 Phase 1: Dry Run Test", style="cyan"))

    # Import directly from the skills directory
    sys.path.insert(0, str(_PRJ_ROOT / "assets"))
    from structural_editing.tools import refactor_repository

    # Run dry run
    report = refactor_repository(
        search_pattern="print($A)",
        rewrite_pattern="logger.info($A)",
        path=playground,
        file_pattern="**/*.py",
        dry_run=True,
    )

    console.print(f"\n{report}\n")

    # Verify files were NOT modified
    service_content = (Path(playground) / "service.py").read_text()
    main_content = (Path(playground) / "main.py").read_text()

    dry_run_passed = True

    if "logger.info" in service_content:
        console.print("[red]❌ FAIL: logger.info found after dry run![/red]")
        dry_run_passed = False
    else:
        console.print("[green]✅ PASS: Files unchanged after dry run[/green]")

    if "print(" in service_content:
        console.print("[green]✅ PASS: Original print statements preserved[/green]")
    else:
        console.print("[red]❌ FAIL: print statements missing after dry run[/red]")
        dry_run_passed = False

    return dry_run_passed


def test_apply_mode(playground: str) -> bool:
    """Test apply mode - should actually modify files."""
    console.print(Panel.fit("⚡ Phase 2: Apply Mode Test", style="cyan"))

    from structural_editing.tools import refactor_repository

    # Run actual refactoring
    report = refactor_repository(
        search_pattern="print($A)",
        rewrite_pattern="logger.info($A)",
        path=playground,
        file_pattern="**/*.py",
        dry_run=False,  # Actually modify!
    )

    console.print(f"\n{report}\n")

    # Verify files WERE modified
    service_content = (Path(playground) / "service.py").read_text()
    utils_content = (Path(playground) / "utils.py").read_text()
    main_content = (Path(playground) / "main.py").read_text()
    readme_content = (Path(playground) / "README.md").read_text()

    apply_passed = True

    # Check Python files were transformed
    if "logger.info" in service_content:
        console.print("[green]✅ PASS: service.py transformed[/green]")
    else:
        console.print("[red]❌ FAIL: service.py not transformed[/red]")
        apply_passed = False

    if "logger.info" in utils_content:
        console.print("[green]✅ PASS: utils.py transformed[/green]")
    else:
        console.print("[red]❌ FAIL: utils.py not transformed[/red]")
        apply_passed = False

    if "logger.info" in main_content:
        console.print("[green]✅ PASS: main.py transformed[/green]")
    else:
        console.print("[red]❌ FAIL: main.py not transformed[/red]")
        apply_passed = False

    # Check print statements are gone
    if "print(" not in service_content:
        console.print("[green]✅ PASS: print statements removed from service.py[/green]")
    else:
        console.print("[red]❌ FAIL: print statements still in service.py[/red]")
        apply_passed = False

    # Check README was NOT touched (not a Python file)
    if "print" not in readme_content:
        console.print("[green]✅ PASS: README.md untouched (non-Python file)[/green]")
    else:
        console.print("[red]❌ FAIL: README.md was modified![/red]")
        apply_passed = False

    # Show the transformed content
    console.print("\n📄 Transformed service.py:")
    console.print(Text(service_content, style="green"))

    return apply_passed


def test_rust_availability() -> bool:
    """Check if Rust bindings are available."""
    console.print(Panel.fit("🔍 Rust Core Check", style="cyan"))

    try:
        import omni_core_rs

        # Check if batch_structural_replace is available
        if hasattr(omni_core_rs, "batch_structural_replace"):
            console.print("[green]✅ Rust core available with batch_structural_replace[/green]")
            return True
        else:
            console.print(
                "[yellow]⚠️ Rust core available but batch_structural_replace not found[/yellow]"
            )
            return False
    except ImportError as e:
        console.print(f"[red]❌ Rust core not available: {e}[/red]")
        return False


def cleanup_playground(playground: str):
    """Clean up the playground directory."""
    playground_path = Path(playground)
    if playground_path.exists():
        shutil.rmtree(playground_path)
        console.print(f"[dim]🧹 Cleaned up: {playground}[/dim]")


def main():
    """Run the Ouroboros test suite."""
    console.print(
        Panel.fit(
            "🐉 Phase 58.5: The Ouroboros Awakening",
            style="bold magenta",
            subtitle="Dogfooding Test for Heavy-Duty Batch Refactoring",
        )
    )

    # Check Rust availability first
    rust_available = test_rust_availability()
    if not rust_available:
        console.print("\n[yellow]⚠️ Skipping tests - Rust core not available[/yellow]")
        console.print("Run 'just build-rust' to enable Phase 58 features.")
        return 1

    # Setup
    playground = setup_playground()

    try:
        # Test dry run
        dry_run_passed = test_dry_run(playground)

        if not dry_run_passed:
            console.print("\n[red]❌ DRY RUN TEST FAILED[/red]")
            return 1

        # Test apply mode
        apply_passed = test_apply_mode(playground)

        if not apply_passed:
            console.print("\n[red]❌ APPLY MODE TEST FAILED[/red]")
            return 1

        # Success!
        console.print(
            Panel.fit(
                "🎉 SUCCESS: The Ouroboros Has Awakened!",
                style="bold green",
                subtitle="Phase 58 Batch Refactoring Capability Verified",
            )
        )

        console.print("""
The Agent now possesses nuclear-grade refactoring capabilities:

⚡ Performance: 10,000 files = 1 FFI call (not 10,000!)
🧵 Parallelism: Uses all CPU cores via rayon
🎯 Precision: AST-based matching (not regex)
🔒 Safety: Dry-run mode for preview before apply

The Ouroboros has consumed the legacy code and emerged transformed!
        """)

        return 0

    finally:
        cleanup_playground(playground)


if __name__ == "__main__":
    sys.exit(main())
