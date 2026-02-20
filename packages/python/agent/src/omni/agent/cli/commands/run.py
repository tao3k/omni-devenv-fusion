"""run.py - Rust-only dispatcher for `omni run`."""

from __future__ import annotations

import os
from typing import Annotated

import typer
from rich.console import Console

from omni.foundation.utils.common import setup_import_paths

setup_import_paths()
console = Console()


def _exec_omni_agent(args: list[str]) -> None:
    """Replace current process with `omni-agent` from PATH."""
    try:
        os.execvp("omni-agent", ["omni-agent", *args])
    except FileNotFoundError as exc:
        console.print(
            "[red]omni-agent not found in PATH.[/red] "
            "Build/install it first (for example: [bold]cargo build -p omni-agent[/bold])."
        )
        raise typer.Exit(1) from exc


def _unsupported_flags(
    *,
    json_output: bool,
    graph: bool,
    omega: bool,
    fast: bool,
) -> list[str]:
    flags: list[str] = []
    if json_output:
        flags.append("--json")
    if graph:
        flags.append("--graph")
    if omega:
        flags.append("--omega")
    if fast:
        flags.append("--fast")
    return flags


def register_run_command(parent_app: typer.Typer):
    """Register the run command with the parent app."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("run", ollama=True, embedding_index=True)

    @parent_app.command()
    def run(
        task: Annotated[str | None, typer.Argument(help="Task description or query")] = None,
        steps: Annotated[
            int | None,
            typer.Option("-s", "--steps", help="Max steps (default: runtime setting)"),
        ] = None,
        json_output: Annotated[
            bool,
            typer.Option("--json", "-j", help="Not supported in Rust-only `omni run`"),
        ] = False,
        repl: Annotated[bool, typer.Option("--repl", help="Enter interactive REPL mode")] = False,
        graph: Annotated[
            bool,
            typer.Option("--graph", help="Not supported in Rust-only `omni run`"),
        ] = False,
        omega: Annotated[
            bool,
            typer.Option("--omega", "-O", help="Not supported in Rust-only `omni run`"),
        ] = False,
        fast: Annotated[
            bool,
            typer.Option("--fast", help="Not supported in Rust-only `omni run`"),
        ] = False,
        tui_socket: Annotated[
            str,
            typer.Option("--socket", help="Not used in Rust-only `omni run`"),
        ] = "/tmp/omni-omega.sock",
        verbose: Annotated[
            bool,
            typer.Option("--verbose/--quiet", "-v/-q", help="Set Rust logging verbosity"),
        ] = True,
    ):
        """Execute a task via Rust `omni-agent` only."""
        del tui_socket

        unsupported = _unsupported_flags(
            json_output=json_output,
            graph=graph,
            omega=omega,
            fast=fast,
        )
        if unsupported:
            joined = ", ".join(unsupported)
            console.print(
                f"[red]Unsupported flags in Rust-only `omni run`:[/red] {joined}\n"
                "Use `omni-agent` subcommands directly for advanced runtime modes."
            )
            raise typer.Exit(2)

        if steps is not None:
            os.environ["OMNI_AGENT_MAX_TOOL_ROUNDS"] = str(max(1, int(steps)))

        if verbose and "RUST_LOG" not in os.environ:
            os.environ["RUST_LOG"] = "debug"

        args = ["repl"]
        if task and not repl:
            args.extend(["--query", task])
        _exec_omni_agent(args)


__all__ = ["register_run_command"]
