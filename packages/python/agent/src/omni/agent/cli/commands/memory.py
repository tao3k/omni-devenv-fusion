"""Memory CLI commands for testing self-evolving memory."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from omni.agent.services.memory import (
    MemoryService,
    MemoryConfig,
    get_memory_service,
    reset_memory_service,
)

console = Console()
memory_app = typer.Typer()


@memory_app.command()
def test():
    """Test the memory service with sample data."""
    reset_memory_service()
    service = MemoryService(MemoryConfig(embedding_dim=128))

    console.print("[bold cyan]Self-Evolving Memory Test[/bold cyan]")

    # Store some episodes
    episodes = [
        ("debug network timeout", "Checked DNS and firewall rules", "success"),
        ("fix memory leak", "Found unbounded HashMap, replaced with LRU cache", "success"),
        ("handle async error", "Added try-catch and error boundary", "success"),
        ("optimize database query", "Added index but still slow", "failure"),
        ("debug connection refused", "Service was down, restarted it", "success"),
    ]

    # Store and track IDs
    episode_ids = []
    for intent, exp, outcome in episodes:
        ep_id = service.store_episode(intent=intent, experience=exp, outcome=outcome)
        episode_ids.append(ep_id)

    console.print(f"\n[green]Stored {service.len()} episodes[/green]")

    # Show all episodes
    table = Table(title="Stored Episodes")
    table.add_column("ID", style="dim")
    table.add_column("Intent")
    table.add_column("Experience")
    table.add_column("Outcome")

    for ep in service.get_all_episodes():
        table.add_row(ep.id[:8], ep.intent[:30], ep.experience[:30], ep.outcome)

    console.print(table)

    # Update Q-values based on outcome (simulate learning)
    for i, ep_id in enumerate(episode_ids):
        if episodes[i][2] == "success":
            service.update_q_value(ep_id, 1.0)
        else:
            service.update_q_value(ep_id, 0.0)

    console.print("\n[bold]Q-values after learning:[/bold]")
    for ep in service.get_all_episodes():
        console.print(f"  {ep.intent[:30]:30s} q={ep.q_value:.2f}")

    # Test semantic recall
    console.print("\n[bold]Semantic Recall (debug network)[/bold]")
    results = service.recall("debug network", k=3)
    for ep, score in results:
        console.print(f"  {ep.intent[:40]:40s} (sim: {score:.3f})")

    # Test two-phase recall with different Q-weights
    console.print("\n[bold]Two-Phase Recall (q_weight=0.3 - semantic heavy)[/bold]")
    results = service.two_phase_recall("debug network", q_weight=0.3)
    for ep, score in results:
        console.print(f"  {ep.intent[:40]:40s} (score: {score:.3f})")

    console.print("\n[bold]Two-Phase Recall (q_weight=0.7 - Q-learning heavy)[/bold]")
    results = service.two_phase_recall("debug network", q_weight=0.7)
    for ep, score in results:
        console.print(f"  {ep.intent[:40]:40s} (score: {score:.3f})")

    console.print("\n[bold green]Test completed![/bold green]")


@memory_app.command()
def stats():
    """Show memory statistics."""
    service = get_memory_service()
    console.print(f"Episodes: {service.len()}")
    console.print(f"Empty: {service.is_empty()}")


if __name__ == "__main__":
    memory_app()
