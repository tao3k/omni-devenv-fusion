"""
core/runner.py - Stress Test Runner Module

Modular test runner that can execute different test types.
Designed to be independent from the main agent codebase.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Type, Callable, Any, Awaitable

from .metrics import MetricsCollector, TestMetrics, MemoryThresholdChecker
from rich.console import Console
from rich.table import Table


console = Console()


@dataclass
class StressConfig:
    """Configuration for stress test runner."""

    turns: int = 50
    warm_up_turns: int = 3
    verbose: bool = False
    fail_threshold_mb: float = 100.0
    warning_threshold_mb: float = 50.0
    output_format: str = "rich"  # rich, json, simple


class StressTest(ABC):
    """Abstract base class for stress tests."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Test identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Test description for reporting."""
        ...

    @abstractmethod
    async def setup(self) -> None:
        """Initialize test resources."""
        ...

    @abstractmethod
    async def execute_turn(self, turn_number: int) -> bool:
        """
        Execute a single test turn.

        Args:
            turn_number: Current turn (1-indexed)

        Returns:
            True if successful, False to abort
        """
        ...

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up test resources."""
        ...


class StressRunner:
    """
    Modular stress test runner.

    Usage:
        runner = StressRunner(config=StressConfig(turns=50))
        runner.register(MyStressTest)
        result = await runner.run()
    """

    def __init__(self, config: StressConfig | None = None):
        self.config = config or StressConfig()
        self._tests: List[Type[StressTest]] = []
        self._results: List[TestMetrics] = []
        self._collector = MetricsCollector()
        self._thresholds = MemoryThresholdChecker(
            warning_threshold_mb=self.config.warning_threshold_mb,
            error_threshold_mb=self.config.fail_threshold_mb,
        )

    def register(self, test_class: Type[StressTest]) -> None:
        """Register a stress test class."""
        self._tests.append(test_class)

    async def run_single(self, test_class: Type[StressTest]) -> TestMetrics:
        """Run a single stress test."""
        # Create test instance first to access properties
        test = test_class()
        test_name = test.name
        console.print(f"\n[bold cyan]Running: {test_name}[/bold cyan]")
        console.print(f"[dim]{test.description}[/dim]")

        # Setup
        await test.setup()

        # Warm-up phase
        console.print(f"[yellow]Warm-up ({self.config.warm_up_turns} turns)...[/yellow]")
        for i in range(self.config.warm_up_turns):
            await test.execute_turn(i + 1)
            if self.config.verbose:
                console.print(f"  Warm-up turn {i + 1} complete")

        # Capture baseline after warm-up
        self._collector.start()
        baseline = self._collector.snapshot(turn=0)
        console.print(f"[bold green]Baseline: {baseline.rss_mb:.1f} MB[/bold green]")

        # Main test loop
        console.print(f"[bold red]Test phase ({self.config.turns} turns)...[/bold red]")
        all_success = True

        for turn in range(1, self.config.turns + 1):
            success = await test.execute_turn(turn + self.config.warm_up_turns)
            if not success:
                all_success = False
                console.print(f"[yellow]Turn {turn} returned failure[/yellow]")

            # Capture memory
            self._collector.snapshot(turn=turn)

            # Progress indicator
            if turn % 10 == 0 or turn == self.config.turns:
                last = self._collector._snapshots[-1]
                delta = last.rss_mb - baseline.rss_mb
                color = "green" if delta < 30 else "yellow" if delta < 70 else "red"
                console.print(
                    f"  Turn {turn}/{self.config.turns} | Mem: {last.rss_mb:.1f}MB ([{color}]+{delta:.1f}[/{color}])"
                )

        # Stop collection (pass test_name directly)
        metrics = self._collector.stop(test_name)

        # Teardown
        await test.teardown()

        return metrics

    async def run(self) -> List[TestMetrics]:
        """Run all registered stress tests."""
        console.print("\n[bold red]╔══════════════════════════════════════════╗[/bold red]")
        console.print("[bold red]║     STRESS & STABILITY TEST SUITE        ║[/bold red]")
        console.print("[bold red]╚══════════════════════════════════════════╝[/bold red]")
        console.print(
            f"[dim]Turns: {self.config.turns}, Warm-up: {self.config.warm_up_turns}[/dim]\n"
        )

        self._results = []

        for test_class in self._tests:
            metrics = await self.run_single(test_class)
            self._results.append(metrics)

        # Print summary
        self._print_summary()

        return self._results

    def _print_summary(self) -> None:
        """Print test summary."""
        console.print("\n[bold]══════════════════════════════════════════[/bold]")
        console.print("[bold]                 TEST SUMMARY              [/bold]")
        console.print("[bold]══════════════════════════════════════════[/bold]\n")

        table = Table(title="Stress Test Results")
        table.add_column("Test", style="cyan")
        table.add_column("Duration", style="magenta")
        table.add_column("Memory Δ", style="yellow")
        table.add_column("Peak", style="red")
        table.add_column("Status", style="green")

        all_passed = True

        for metrics in self._results:
            growth = metrics.memory_growth_mb()
            passed, _ = self._thresholds.check(growth)

            if not passed:
                all_passed = False

            status = "✓ PASS" if passed else "✗ FAIL"
            color = "green" if passed else "red"

            table.add_row(
                metrics.test_name,
                f"{metrics.duration_seconds:.1f}s",
                f"+{growth:.1f} MB",
                f"{metrics.peak_memory_mb:.1f} MB",
                f"[{color}]{status}[/{color}]",
            )

        console.print(table)

        # Final verdict
        console.print()
        if all_passed:
            console.print("[bold green]✓ ALL TESTS PASSED[/bold green]")
        else:
            console.print("[bold red]✗ SOME TESTS FAILED[/bold red]")


class SimpleStressRunner:
    """
    Simplified runner for quick tests without registering classes.

    Usage:
        runner = SimpleStressRunner(turns=20)
        runner.add("name", async def(): do_work())
        await runner.run()
    """

    def __init__(self, turns: int = 20, warm_up: int = 2):
        self.turns = turns
        self.warm_up = warm_up
        self._tests: List[tuple[str, Callable[..., Awaitable[Any]]]] = []

    def add(self, name: str, coro: Callable[..., Awaitable[Any]]) -> None:
        """Add an async test function."""
        self._tests.append((name, coro))

    async def run(self) -> None:
        """Run all tests."""
        from .metrics import MetricsCollector, MemoryThresholdChecker

        collector = MetricsCollector()
        thresholds = MemoryThresholdChecker()

        for name, coro in self._tests:
            console.print(f"\n[bold cyan]Testing: {name}[/bold cyan]")

            # Warm-up
            for _ in range(self.warm_up):
                await coro()

            # Test
            collector.start()
            collector.snapshot(0)

            for i in range(self.turns):
                await coro()
                collector.snapshot(i + 1)

            metrics = collector.stop()

            growth = metrics.memory_growth_mb()
            passed, msg = thresholds.check(growth)

            console.print(
                f"  Memory: {metrics.memory_snapshots[0].rss_mb:.1f} → {metrics.memory_snapshots[-1].rss_mb:.1f} MB"
            )
            console.print(f"  Growth: +{growth:.1f} MB | {msg}")


__all__ = [
    "StressConfig",
    "StressTest",
    "StressRunner",
    "SimpleStressRunner",
]
