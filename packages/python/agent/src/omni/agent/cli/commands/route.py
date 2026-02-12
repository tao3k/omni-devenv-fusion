"""
route.py - Router Test Command

Test the Hybrid Router with semantic + keyword search and caching.

Usage:
    omni route test "git commit"           # Test routing for a query
    omni route test "git commit" --debug   # Show detailed scoring
    omni route test "git commit" --mcp     # Force use MCP server for embedding
    omni route test "git commit" --local   # Use local embedding (default)
    omni route stats                       # Show router statistics
    omni route cache                       # Show cache stats
    omni route schema                      # Export router settings JSON schema
"""

from __future__ import annotations

import json
import socket
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.asyncio import run_async_blocking

from ..console import err_console

route_app = typer.Typer(
    name="route",
    help="Router testing and diagnostics",
)

console = Console()

# Default embedding HTTP server port
EMBEDDING_HTTP_PORT = 18501
ROUTE_TEST_SCHEMA_V1 = "omni.router.route_test.v1"


def _profile_defaults() -> dict[str, float]:
    """Built-in defaults for confidence calibration profile."""
    return {
        "high_threshold": 0.75,
        "medium_threshold": 0.5,
        "high_base": 0.90,
        "high_scale": 0.05,
        "high_cap": 0.99,
        "medium_base": 0.60,
        "medium_scale": 0.30,
        "medium_cap": 0.89,
        "low_floor": 0.10,
    }


def _load_router_config():
    """Load validated router.search config from core schema."""
    from omni.core.router.config import load_router_search_config

    return load_router_search_config()


def _load_route_test_defaults() -> tuple[int, float]:
    """Load route-test defaults from router.search settings."""
    config = _load_router_config()
    return config.default_limit, config.default_threshold


def _default_confidence_profile() -> dict[str, float]:
    """Load active confidence profile from router.search.profiles."""
    merged = _profile_defaults()
    config = _load_router_config()
    selected = config.active_confidence_profile.model_dump()
    for key, value in selected.items():
        if key in merged:
            merged[key] = float(value)
    return merged


def _available_confidence_profiles() -> list[str]:
    config = _load_router_config()
    return sorted(config.profiles.keys())


def _load_named_confidence_profile(profile_name: str | None) -> dict[str, float] | None:
    """Resolve named profile from settings and merge with defaults."""
    if not profile_name:
        return None

    config = _load_router_config()
    selected = config.profiles.get(profile_name)
    if selected is None:
        return None

    merged = _default_confidence_profile()
    for key, value in selected.model_dump().items():
        if key in merged:
            merged[key] = float(value)
    return merged


def _build_route_test_json_payload(
    *,
    query: str,
    results: list[dict],
    threshold: float,
    limit: int,
    selected_profile_name: str | None,
    selected_profile_source: str,
    stats: dict[str, float] | None = None,
) -> dict:
    profile = {
        "name": selected_profile_name,
        "source": selected_profile_source,
    }
    stats_payload = {
        "semantic_weight": None,
        "keyword_weight": None,
        "rrf_k": None,
        "strategy": None,
    }
    if stats:
        stats_payload.update(
            {
                "semantic_weight": stats.get("semantic_weight"),
                "keyword_weight": stats.get("keyword_weight"),
                "rrf_k": stats.get("rrf_k"),
                "strategy": stats.get("strategy"),
            }
        )
    return {
        "schema": ROUTE_TEST_SCHEMA_V1,
        "query": query,
        "count": len(results),
        "threshold": threshold,
        "limit": limit,
        "confidence_profile": profile,
        "stats": stats_payload,
        "results": results,
    }


async def _select_confidence_profile(
    query: str,
    explicit_profile_name: str | None,
) -> tuple[dict[str, float] | None, str | None, str]:
    """Select confidence profile (explicit > LLM auto > active_profile fallback)."""
    if explicit_profile_name:
        selected = _load_named_confidence_profile(explicit_profile_name)
        if selected is None:
            return None, explicit_profile_name, "invalid"
        return selected, explicit_profile_name, "explicit"

    config = _load_router_config()
    if not config.profiles:
        return None, None, "none-configured"

    names = list(config.profiles.keys())
    active_profile = config.active_profile
    auto_select = config.auto_profile_select
    if not auto_select:
        selected = _load_named_confidence_profile(active_profile)
        if selected is not None:
            return selected, active_profile, "active-profile"
        fallback_name = names[0]
        return _load_named_confidence_profile(fallback_name), fallback_name, "first-profile"

    try:
        from omni.foundation.services.llm import get_llm_provider

        provider = get_llm_provider()
        if provider.is_available():
            prompt = (
                "Choose one profile name for router confidence calibration.\n"
                f"Available profiles: {', '.join(names)}\n"
                f"Query: {query}\n"
                "Return only the profile name."
            )
            response = await provider.complete(
                "You select routing calibration profiles.",
                prompt,
                max_tokens=32,
            )
            if response.success:
                candidate = (response.content or "").strip().lower()
                normalized_map = {name.lower(): name for name in names}
                if candidate in normalized_map:
                    resolved = normalized_map[candidate]
                    selected = _load_named_confidence_profile(resolved)
                    if selected is not None:
                        return selected, resolved, "llm"
    except Exception:
        pass

    selected = _load_named_confidence_profile(active_profile)
    if selected is not None:
        return selected, active_profile, "active-profile"
    fallback_name = names[0]
    return _load_named_confidence_profile(fallback_name), fallback_name, "first-profile"


async def _embed_via_http(
    texts: list[str], port: int = EMBEDDING_HTTP_PORT
) -> list[list[float]] | None:
    """Get embeddings via embedding HTTP server.

    Args:
        texts: List of texts to embed
        port: Embedding HTTP server port (default: 18501)

    Returns None if server is not available.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"http://127.0.0.1:{port}/embed/batch",
                json={"texts": texts},
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("vectors")
            return None
    except Exception:
        return None


async def _detect_embedding_server() -> int:
    """Detect if embedding HTTP server is running.

    Checks if port 18501 is available and responds to health check.
    Returns the port number if server is running, 0 otherwise.
    """
    # First check if port is in use
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(("127.0.0.1", EMBEDDING_HTTP_PORT))
        if result != 0:
            return 0  # Port not in use
    except Exception:
        return 0
    finally:
        sock.close()

    # Port is in use, try health check
    try:
        import httpx

        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"http://127.0.0.1:{EMBEDDING_HTTP_PORT}/health")
            if response.status_code == 200:
                return EMBEDDING_HTTP_PORT
    except Exception:
        pass

    return 0


async def _embed_via_mcp(texts: list[str], port: int = 3001) -> list[list[float]] | None:
    """Try to get embeddings via MCP server.

    Args:
        texts: List of texts to embed
        port: MCP server port (default: 3001)

    Returns None if MCP server is not available.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            request = {
                "jsonrpc": "2.0",
                "id": "route-test",
                "method": "tools/call",
                "params": {
                    "name": "embedding.embed_texts",
                    "arguments": {"texts": texts},
                },
            }
            response = await client.post(
                f"http://127.0.0.1:{port}/message",
                json=request,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            if "result" in result and result["result"]:
                content = result["result"].get("content", [])
                if content and isinstance(content, list):
                    text_content = content[0].get("text", "")
                    if text_content:
                        data = json.loads(text_content)
                        if data.get("success"):
                            return data.get("vectors")
            return None
    except Exception:
        return None


async def _detect_mcp_port() -> int:
    """Detect the MCP server port for embedding.

    Tries embedding HTTP server (18501) first, then MCP ports (3001, 3000).
    Returns the port number that responds successfully.
    """
    # First check embedding HTTP server
    embedding_port = await _detect_embedding_server()
    if embedding_port > 0:
        return embedding_port

    # Fall back to MCP ports
    for port in [3001, 3000]:
        vectors = await _embed_via_mcp(["[DETECT]"], port=port)
        if vectors is not None:
            return port

    return 0  # No server available


@route_app.command("test")
def test_route(
    query: str = typer.Argument(..., help="User intent to route"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Show detailed scoring"),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON payload with full routing metadata",
    ),
    limit: int | None = typer.Option(
        None, "-n", "--number", help="Maximum results (default from settings)"
    ),
    threshold: float | None = typer.Option(
        None,
        "-t",
        "--threshold",
        help="Score threshold (default from settings; 0.4+ for high quality)",
    ),
    confidence_profile_name: str | None = typer.Option(
        None,
        "--confidence-profile",
        help="Named confidence profile from settings (router.search.profiles.<name>)",
    ),
    use_mcp: bool = typer.Option(
        False, "--mcp", "-m", help="Use MCP server for embedding (faster if MCP is running)"
    ),
    use_local: bool = typer.Option(
        False, "--local", "-l", help="Use local embedding model (default behavior)"
    ),
) -> None:
    """
    Test hybrid routing for a required query intent.

    QUERY is required and should be quoted when it contains spaces.

    Examples:
        omni route test "git commit"
        omni route test "search python symbols" --threshold 0.45 --number 5
        omni route test "refactor rust module" --debug
        omni route test "index knowledge docs" --mcp
    """
    try:
        from omni.core.router.hybrid_search import HybridSearch
    except ImportError as e:
        console.print(f"[red]Error: Could not import router module: {e}[/]")
        raise typer.Exit(1)

    default_limit, default_threshold = _load_route_test_defaults()
    resolved_limit = default_limit if limit is None else limit
    resolved_threshold = default_threshold if threshold is None else threshold
    confidence_profile, selected_profile_name, selected_profile_source = run_async_blocking(
        _select_confidence_profile(query, confidence_profile_name)
    )
    if confidence_profile_name and confidence_profile is None:
        available = ", ".join(_available_confidence_profiles()) or "(none configured)"
        err_console.print(
            f"Unknown confidence profile '{confidence_profile_name}'. Available: {available}"
        )
        raise typer.Exit(2)

    async def run_test():
        search = HybridSearch()

        # Decide embedding method
        if use_mcp:
            if not json_output:
                console.print(f"[dim]Using MCP server for embedding...[/dim]")
            # Inject MCP embedding function
            search._embed_func = _embed_via_mcp
        elif use_local:
            if not json_output:
                console.print(f"[dim]Using local embedding model...[/dim]")
            # Use default local embedding
            search._embed_func = None
        else:
            # Auto-detect: try embedding HTTP server first (18501), then MCP ports
            if not json_output:
                console.print(f"[dim]Auto-detecting embedding source...[/dim]")
            mcp_port = await _detect_mcp_port()
            if mcp_port > 0:
                if mcp_port == EMBEDDING_HTTP_PORT:
                    if not json_output:
                        console.print(
                            f"[green]✓ Embedding HTTP server found on port {mcp_port} (model preloaded)[/green]"
                        )
                    search._embed_func = _embed_via_http
                else:
                    if not json_output:
                        console.print(
                            f"[green]✓ MCP server found on port {mcp_port} (model preloaded)[/green]"
                        )
                    search._embed_func = lambda texts: _embed_via_mcp(texts, port=mcp_port)
            else:
                if not json_output:
                    console.print(
                        f"[yellow]⚠ No embedding server available, using local model[/yellow]"
                    )
                search._embed_func = None

        if not json_output:
            console.print(f"[dim]Searching for: '{query}'[/dim]")
            if selected_profile_name:
                console.print(
                    f"[dim]Confidence profile: {selected_profile_name} ({selected_profile_source})[/dim]"
                )
        results = await search.search(
            query=query,
            limit=resolved_limit,
            min_score=resolved_threshold,
            confidence_profile=confidence_profile,
        )

        # Display results
        if not results:
            if json_output:
                payload = _build_route_test_json_payload(
                    query=query,
                    results=[],
                    threshold=resolved_threshold,
                    limit=resolved_limit,
                    selected_profile_name=selected_profile_name,
                    selected_profile_source=selected_profile_source,
                )
                print(json.dumps(payload), flush=True)
            else:
                console.print("[yellow]No matches found for this query.[/]")
                console.print("[dim]Try lowering the threshold or using different keywords.[/dim]")
            return

        stats = search.stats()
        if json_output:
            payload = _build_route_test_json_payload(
                query=query,
                results=results,
                threshold=resolved_threshold,
                limit=resolved_limit,
                selected_profile_name=selected_profile_name,
                selected_profile_source=selected_profile_source,
                stats=stats,
            )
            print(json.dumps(payload), flush=True)
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
                "high": "green",
                "medium": "yellow",
                "low": "red",
            }.get(result.get("confidence", ""), "white")

            score_str = f"{result.get('score', 0):.3f}"

            # Use full tool name (skill.command)
            tool_id = f"{result.get('skill_name', '')}.{result.get('command', '')}"
            if result.get("command") and not result.get("skill_name"):
                tool_id = result.get("id", result.get("command", ""))

            if debug:
                final_score = result.get("final_score")
                final_score_str = (
                    f"{final_score:.3f}" if isinstance(final_score, int | float) else "n/a"
                )
                schema_raw = str(result.get("input_schema", "")).strip()
                schema_present = schema_raw not in ("", "{}", "null", "None")
                vector_score = result.get("vector_score")
                keyword_score = result.get("keyword_score")
                if isinstance(vector_score, int | float) or isinstance(keyword_score, int | float):
                    vector_part = (
                        f"{vector_score:.3f}" if isinstance(vector_score, int | float) else "n/a"
                    )
                    keyword_part = (
                        f"{keyword_score:.3f}" if isinstance(keyword_score, int | float) else "n/a"
                    )
                    detail = (
                        f"raw={result.get('score', 0):.3f} | final={final_score_str} | "
                        f"vec={vector_part} | kw={keyword_part} | schema={'yes' if schema_present else 'no'}"
                    )
                else:
                    detail = (
                        f"raw={result.get('score', 0):.3f} | final={final_score_str} | "
                        f"schema={'yes' if schema_present else 'no'}"
                    )
                table.add_row(
                    tool_id,
                    score_str,
                    f"[{conf_style}]{result.get('confidence', 'unknown')}[/]",
                    detail,
                )
            else:
                table.add_row(
                    tool_id,
                    score_str,
                    f"[{conf_style}]{result.get('confidence', 'unknown')}[/]",
                )

        console.print(table)

        # Show filtered count if threshold was used
        if resolved_threshold > 0:
            high_med_count = sum(1 for r in results if r.get("confidence") in ("high", "medium"))
            if high_med_count < len(results):
                console.print(
                    f"[dim]Showing {len(results)} results ({high_med_count} high/medium confidence). "
                    f"Use -t 0 to show all results.[/dim]"
                )

        # Show stats
        console.print(
            f"\n[dim]Search weights: semantic={stats['semantic_weight']}, keyword={stats['keyword_weight']}[/dim]"
        )

    run_async_blocking(run_test())


@route_app.command("stats")
def route_stats() -> None:
    """Show router statistics."""
    try:
        from omni.core.router.hybrid_search import HybridSearch
        from omni.core.router.config import load_router_search_config
    except ImportError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    search = HybridSearch()
    stats = search.stats()
    config = load_router_search_config()

    console.print(
        Panel.fit(
            f"[bold]Router Statistics[/]\n\n"
            f"[bold]Hybrid Search:[/]\n"
            f"  Semantic weight: {stats['semantic_weight']}\n"
            f"  Keyword weight: {stats['keyword_weight']}\n"
            f"  RRF smoothing (k): {stats['rrf_k']}\n"
            f"  Strategy: {stats['strategy']}\n\n"
            f"[bold]Field Boosting:[/]\n"
            f"  Name token boost: {stats['field_boosting']['name_token_boost']}\n"
            f"  Exact phrase boost: {stats['field_boosting']['exact_phrase_boost']}\n\n"
            f"[bold]Confidence Profile (settings-driven):[/]\n"
            f"  active_profile: {config.active_profile}\n"
            f"  high_threshold: {config.profiles[config.active_profile].high_threshold}\n"
            f"  medium_threshold: {config.profiles[config.active_profile].medium_threshold}\n"
            f"  low_floor: {config.profiles[config.active_profile].low_floor}",
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

    from omni.core.router.main import RouterRegistry

    router = RouterRegistry.get("route_cache")

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


@route_app.command("schema")
def route_schema(
    path: str | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Output path for schema file (default: from settings + --conf directory)",
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Print schema JSON to stdout instead of writing to file",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON output for command result",
    ),
) -> None:
    """Export or print router search settings schema."""
    try:
        from omni.core.router import (
            resolve_router_schema_path,
            router_search_json_schema,
            write_router_search_json_schema,
        )
    except ImportError as e:
        console.print(f"[red]Error: Could not import router schema module: {e}[/]")
        raise typer.Exit(1)

    if stdout:
        schema = router_search_json_schema()
        print(json.dumps(schema), flush=True)
        return

    output_path = write_router_search_json_schema(path)
    if json_output:
        payload = {
            "status": "success",
            "path": str(output_path),
            "resolved_from": str(resolve_router_schema_path(path)),
        }
        print(json.dumps(payload), flush=True)
        return

    console.print(
        Panel.fit(
            f"[bold]Router Search Schema Exported[/]\n\n"
            f"Path: [cyan]{output_path}[/]\n"
            f"Resolution: [dim]settings.yaml + --conf override[/dim]",
            title="Router Schema",
            border_style="green",
        )
    )


def register_route_command(parent_app: typer.Typer) -> None:
    """Register the route command with the parent app."""
    parent_app.add_typer(route_app, name="route")


__all__ = ["route_app", "register_route_command"]
