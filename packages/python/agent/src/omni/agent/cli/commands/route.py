"""
route.py - Router Test Command

Test the Hybrid Router with semantic + keyword search and caching.

This command provides debugging tools for the routing system.

Usage:
    omni route test "git commit"           # Test routing for a query
    omni route test "git commit" --debug   # Show detailed scoring
    omni route stats                       # Show router statistics
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.config.logging import get_logger

# route.py imports

route_app = typer.Typer(
    name="route",
    help="Router testing and diagnostics",
)

console = Console()


@route_app.command("test")
def test_route(
    query: str = typer.Argument(..., help="User intent to route"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Show scoring details"),
    limit: int = typer.Option(5, "-n", "--number", help="Maximum results"),
    threshold: float = typer.Option(0.1, "-t", "--threshold", help="Score threshold"),
) -> None:
    """
    Test the Hybrid Router logic for a query.

    Shows which tools/skills would be matched for the given query,
    along with their semantic and keyword scores.
    """
    try:
        from omni.core.router.main import OmniRouter, RouterRegistry
    except ImportError as e:
        console.print(f"[red]Error: Could not import router module: {e}[/]")
        raise typer.Exit(1)

    async def run_test():
        with console.status(f"[bold green]Routing: '{query}'..."):
            # Use cached router from registry (avoids re-indexing)
            router = RouterRegistry.get("route_test")

            # Check if we can use existing data (fast path)
            if not router._initialized:
                try:
                    # Check if LanceDB already has tools
                    from omni.foundation.bridge.rust_vector import get_vector_store

                    store = get_vector_store()
                    tools = await store.list_all_tools()

                    if tools:
                        from omni.foundation.config.dirs import get_vector_db_path

                        main_path = str(get_vector_db_path())

                        # Use the store that has the data (from get_vector_store at line 63-65)
                        store = get_vector_store()
                        if store is None:
                            console.print("[red]Error: Failed to get vector store[/]")
                            return

                        # Check if we already have data (fast path: LanceDB has data)
                        try:
                            count = store._inner.count("skills")
                        except Exception:
                            count = 0

                        if count >= len(tools) and count > 0:
                            # Data already indexed, just init keyword indexer (fast path)
                            logger = get_logger("omni.agent.cli.route")
                            logger.info(f"Using existing data in LanceDB ({count} tools)")

                            # Initialize indexer with existing store
                            from omni.core.router.indexer import SkillIndexer

                            if router._indexer._store is None:
                                router._indexer = SkillIndexer(main_path, dimension=384)
                                router._indexer.initialize()
                            router._indexer._store = store

                            router._hybrid._indexer = router._indexer
                            router._semantic._indexer = router._indexer
                            router._initialized = True
                        else:
                            # Need to re-index with real embeddings
                            logger = get_logger("omni.agent.cli.route")
                            logger.info(
                                f"Re-indexing {len(tools)} tools with real embeddings (count={count})"
                            )

                            from omni.foundation.services.embedding import get_embedding_service
                            import json

                            embed = get_embedding_service()

                            # Drop old table ONLY when re-indexing
                            try:
                                asyncio.run(store.drop_table("skills"))
                            except Exception:
                                pass

                            # Generate real embeddings for each tool
                            ids = []
                            vectors = []
                            contents = []
                            metadatas = []

                            for tool in tools:
                                tool_id = tool.get("id", "")
                                content = tool.get("content", "")
                                skill_name = tool.get("skill_name", "")

                                ids.append(tool_id)
                                contents.append(content)

                                query_vec = embed.embed(content)
                                if isinstance(query_vec[0], list):
                                    vectors.append(query_vec[0])
                                else:
                                    vectors.append(query_vec)

                                metadata = {
                                    "skill_name": skill_name,
                                    "command": tool_id.split(".", 1)[1] if "." in tool_id else "",
                                    "type": "command",
                                }
                                metadatas.append(json.dumps(metadata))

                            asyncio.run(
                                store.add_documents("skills", ids, vectors, contents, metadatas)
                            )

                            logger.info(f"Indexed {len(ids)} tools with real embeddings")

                            router._hybrid._indexer = router._indexer
                            router._semantic._indexer = router._indexer
                            router._initialized = True
                    else:
                        # Fallback: index from analyzer
                        from omni.core.skills.analyzer import get_analytics_dataframe

                        table = get_analytics_dataframe()

                        if table is None or table.num_rows == 0:
                            console.print("[yellow]No tools found in the database.[/]")
                            console.print(
                                "[cyan]Tip: Run 'omni skill reindex' to index your skills.[/]"
                            )
                            return

                        # Convert table to skill dicts format for indexing
                        skill_dicts = _table_to_skills(table)
                        await router.initialize(skill_dicts)
                except Exception as e:
                    console.print(f"[red]Error loading tools: {e}[/]")
                    return

            # Run hybrid routing
            results = await router.route_hybrid(
                query=query,
                limit=limit,
                threshold=threshold,
            )

        # Display results
        if not results:
            console.print("[yellow]No matches found for this query.[/]")
            console.print("[dim]Try lowering the threshold or using different keywords.[/dim]")
            return

        # Create results table
        table = Table(title=f"Routing Results for: {query}")
        table.add_column("Tool", style="cyan")
        table.add_column("Score", style="magenta")
        table.add_column("Confidence", style="blue")

        if debug:
            table.add_column("Details", style="dim")

        for result in results:
            # Format confidence with color
            conf_style = {
                "HIGH": "green",
                "MEDIUM": "yellow",
                "LOW": "red",
            }.get(result.confidence, "white")

            score_str = f"{result.score:.3f}"

            if debug:
                # Show breakdown - use full tool name (skill.command)
                tool_id = (
                    f"{result.skill_name}.{result.command_name}"
                    if result.command_name
                    else result.skill_name
                )
                table.add_row(
                    tool_id,
                    score_str,
                    f"[{conf_style}]{result.confidence}[/]",
                    f"sem={result.score * 0.7:.2f} | kw={result.score * 0.3:.2f}",
                )
            else:
                # Use full tool name (e.g., "git.commit" instead of just "commit")
                tool_id = (
                    f"{result.skill_name}.{result.command_name}"
                    if result.command_name
                    else result.skill_name
                )
                table.add_row(
                    tool_id,
                    score_str,
                    f"[{conf_style}]{result.confidence}[/]",
                )

        console.print(table)

        # Show cache stats
        stats = router.get_stats()
        console.print(f"\n[dim]Cache size: {stats['cache_stats']['size']} entries[/dim]")

    asyncio.run(run_test())


@route_app.command("stats")
def route_stats() -> None:
    """Show router statistics."""
    try:
        from omni.core.router.main import OmniRouter
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    router = OmniRouter()
    stats = router.get_stats()

    console.print(
        Panel.fit(
            f"[bold]Router Statistics[/]\n\n"
            f"Initialized: [cyan]{stats['initialized']}[/]\n"
            f"Ready: [cyan]{stats['is_ready']}[/]\n\n"
            f"[bold]Hybrid Search:[/]\n"
            f"  Semantic weight: {stats['hybrid_stats']['semantic_weight']}\n"
            f"  Keyword weight: {stats['hybrid_stats']['keyword_weight']}\n\n"
            f"[bold]Cache:[/]\n"
            f"  Size: {stats['cache_stats']['size']}/{stats['cache_stats']['max_size']}\n"
            f"  TTL: {stats['cache_stats']['ttl_seconds']}s\n"
            f"  Hit rate: {stats['cache_stats']['hit_rate']:.1%}",
            title="Router Stats",
            border_style="green",
        )
    )


@route_app.command("cache")
def route_cache(
    clear: bool = typer.Option(False, "-c", "--clear", help="Clear the cache"),
) -> None:
    """Manage router cache."""
    try:
        from omni.core.router.main import OmniRouter
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    router = OmniRouter()

    if clear:
        count = router.cache.clear()
        console.print(f"[green]Cleared {count} cache entries.[/green]")
    else:
        stats = router.cache.stats()
        console.print(
            Panel.fit(
                f"[bold]Search Cache[/]\n\n"
                f"Size: [cyan]{stats['size']}[/] / {stats['max_size']}\n"
                f"TTL: [cyan]{stats['ttl_seconds']}[/] seconds\n"
                f"Hit rate: [cyan]{stats['hit_rate']:.1%}[/]",
                title="Cache",
                border_style="blue",
            )
        )


def register_route_command(parent_app: typer.Typer):
    """Register the route command with the parent app."""
    parent_app.add_typer(route_app, name="route")


def _table_to_skills(table) -> list[dict]:
    """Convert PyArrow Table to skill dicts format for indexing.

    Takes the Arrow table from analyzer and converts it to the format
    expected by SkillIndexer.index_skills().
    """
    skills_by_name: dict[str, dict] = {}

    ids = table["id"].to_pylist()
    contents = table["content"].to_pylist()
    skill_names = table["skill_name"].to_pylist()

    for id_, content, skill_name in zip(ids, contents, skill_names):
        if skill_name not in skills_by_name:
            skills_by_name[skill_name] = {
                "name": skill_name,
                "description": content[:200] if content else f"{skill_name} skill",
                "commands": [],
            }

        # Add command to skill
        cmd_name = id_.split(".")[-1] if "." in id_ else id_
        skills_by_name[skill_name]["commands"].append(
            {
                "name": cmd_name,
                "description": content[:200] if content else f"Execute {cmd_name}",
            }
        )

    return list(skills_by_name.values())
