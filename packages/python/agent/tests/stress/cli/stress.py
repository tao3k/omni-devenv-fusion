"""
cli/stress.py - Stress Test CLI Entry Point

Standalone CLI for running stress tests.
Can be executed without loading the full agent stack.

Usage:
    python -m stress.cli.stress run --turns 20
    python -m stress.cli.stress quick --turns 10
"""

from __future__ import annotations

import asyncio
import sys
import os

# Ensure stress package is importable by adding its parent (tests/)
_STRESS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _STRESS_DIR not in sys.path:
    sys.path.insert(0, _STRESS_DIR)

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()

stress_app = typer.Typer(
    name="stress",
    help="Run system stress and stability tests",
    no_args_is_help=True,
    add_completion=False,
)


def _print_banner():
    """Print stress test banner."""
    banner = Panel(
        "[bold red]STRESS & STABILITY TEST SUITE[/bold red]\n"
        "[dim]Memory endurance, Rust/Python boundary tests[/dim]",
        title="Omni Dev Fusion",
        border_style="red",
    )
    console.print(banner)


@stress_app.command("run")
def stress_run(
    turns: int = typer.Option(50, "-t", "--turns", help="Number of test turns"),
    warmup: int = typer.Option(3, "-w", "--warmup", help="Warm-up turns"),
    test: str = typer.Option(
        "all", "-T", "--test", help="Specific test to run (memory, context, rust, all)"
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
    fail_threshold: float = typer.Option(
        100.0, "-f", "--fail-threshold", help="Fail if memory growth exceeds this (MB)"
    ),
):
    """
    Run stress tests.
    """
    _print_banner()

    from stress.core.runner import StressRunner, StressConfig
    from stress.tests.memory import MemoryEnduranceTest, ContextPruningTest, RustBridgeMemoryTest

    config = StressConfig(
        turns=turns,
        warm_up_turns=warmup,
        verbose=verbose,
        fail_threshold_mb=fail_threshold,
    )

    runner = StressRunner(config=config)

    # Register tests based on selection
    if test in ("all", "memory"):
        runner.register(MemoryEnduranceTest)
    if test in ("all", "context"):
        runner.register(ContextPruningTest)
    if test in ("all", "rust"):
        runner.register(RustBridgeMemoryTest)

    if not runner._tests:
        console.print(f"[red]No tests selected. Available: memory, context, rust, all[/red]")
        raise typer.Exit(1)

    try:
        results = asyncio.run(runner.run())
        console.print("\n[bold green]Stress tests completed.[/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user.[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1)


@stress_app.command("quick")
def stress_quick(
    turns: int = typer.Option(20, "-t", "--turns", help="Number of test turns"),
):
    """
    Quick memory sanity check (no full agent initialization).
    """
    _print_banner()

    from stress.core.metrics import MetricsCollector, MemoryThresholdChecker
    import gc

    console.print(f"[bold]Quick Memory Test ({turns} turns)[/bold]\n")

    collector = MetricsCollector()
    thresholds = MemoryThresholdChecker()

    async def dummy_task():
        """Simulate work."""
        gc.collect()
        _ = [object() for _ in range(100)]
        await asyncio.sleep(0.01)

    # Warm-up
    console.print("[yellow]Warm-up...[/yellow]")
    for _ in range(3):
        asyncio.run(dummy_task())

    # Test
    console.print("[bold red]Testing...[/bold red]")
    collector.start()
    collector.snapshot(0)

    for i in range(turns):
        asyncio.run(dummy_task())
        collector.snapshot(i + 1)

        if (i + 1) % 10 == 0:
            last = collector._snapshots[-1]
            console.print(f"  Turn {i + 1}/{turns} | Mem: {last.rss_mb:.1f} MB")

    metrics = collector.stop()
    growth = metrics.memory_growth_mb()
    passed, msg = thresholds.check(growth)

    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Start: {collector._snapshots[0].rss_mb:.1f} MB")
    console.print(f"  End: {collector._snapshots[-1].rss_mb:.1f} MB")
    console.print(f"  Growth: +{growth:.1f} MB")
    console.print(f"  {msg}")

    if passed:
        console.print("\n[bold green]✓ Memory stable[/bold green]")
    else:
        console.print("\n[bold red]✗ Memory growth detected[/bold red]")
        raise typer.Exit(1)


@stress_app.command("list")
def stress_list():
    """
    List available stress tests.
    """
    console.print("[bold]Available Stress Tests:[/bold]\n")
    console.print("  [cyan]memory[/cyan]       - Memory endurance test for OmniLoop")
    console.print("  [cyan]context[/cyan]      - Context pruning effectiveness test")
    console.print("  [cyan]rust[/cyan]         - Rust/Python bridge memory integrity")
    console.print("  [cyan]all[/cyan]          - Run all tests")


def register_stress_command(parent_app: typer.Typer):
    """Register stress command with parent app."""
    parent_app.add_typer(stress_app, name="stress")


if __name__ == "__main__":
    stress_app()
