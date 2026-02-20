"""Gateway and agent commands: single-loop stdio and/or HTTP webhook with shared kernel."""

from __future__ import annotations

import os
from contextlib import suppress
from typing import Annotated

import typer
from rich.console import Console

from omni.agent.workflows.run_entry import execute_task_with_session
from omni.foundation.config.settings import get_setting
from omni.foundation.utils.common import setup_import_paths

setup_import_paths()
console = Console()

# Default session for stdio
STDIO_SESSION_ID = "stdio:default"


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


async def _webhook_loop(port: int, host: str = "127.0.0.1") -> None:
    """Run HTTP webhook server: one kernel, POST /message with session_id + message."""
    import uvicorn

    from omni.agent.gateway import create_webhook_app
    from omni.core.kernel.engine import get_kernel

    kernel = get_kernel()
    await kernel.initialize()
    await kernel.start()
    app = create_webhook_app(kernel=kernel, enable_cors=True)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def _stdio_loop(session_id: str) -> None:
    """Run message loop: read from stdin, execute_task_with_session, print response. One kernel for all turns."""
    from omni.core.kernel.engine import get_kernel

    # Keep stdio legacy helper minimal; runtime entrypoints are Rust-only.
    with suppress(Exception):
        from omni.agent.cli.mcp_embed import detect_mcp_port

        await detect_mcp_port()

    kernel = get_kernel()
    await kernel.initialize()
    await kernel.start()
    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if line.lower() in ("exit", "quit", "q"):
                console.print("[yellow]Goodbye.[/yellow]")
                break
            if not line:
                continue
            result = await execute_task_with_session(
                session_id,
                line,
                kernel=kernel,
                max_steps=20,
                verbose=False,
                use_memory=True,
            )
            out = result.get("output", "")
            if out:
                console.print(out)
    finally:
        await kernel.shutdown()


def register_gateway_command(parent_app: typer.Typer) -> None:
    """Register `omni gateway`: Rust-only gateway interface."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("gateway", ollama=True, embedding_index=True)

    @parent_app.command()
    def gateway(
        session_id: Annotated[
            str,
            typer.Option("--session", "-s", help="Session ID (default: stdio:default)"),
        ] = STDIO_SESSION_ID,
        webhook_port: Annotated[
            int | None,
            typer.Option(
                "--webhook-port",
                "-w",
                help="Start HTTP webhook on this port (e.g. 8080); POST /message",
            ),
        ] = None,
        webhook_host: Annotated[
            str,
            typer.Option("--webhook-host", help="Bind webhook to this host (default: 127.0.0.1)"),
        ] = "127.0.0.1",
    ):
        """Run Rust gateway (`omni-agent`) in stdio or webhook mode."""
        if webhook_port is not None:
            bind = f"{webhook_host}:{webhook_port}"
            args = ["gateway", "--bind", bind]
        else:
            args = ["stdio", "--session-id", session_id]
        _exec_omni_agent(args)


def register_agent_command(parent_app: typer.Typer) -> None:
    """Register `omni agent`: Rust-only interactive chat interface."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("agent", ollama=True, embedding_index=True)

    @parent_app.command()
    def agent(
        session_id: Annotated[
            str,
            typer.Option("--session", "-s", help="Session ID (default: stdio:default)"),
        ] = STDIO_SESSION_ID,
    ):
        """Interactive chat via Rust `omni-agent repl`."""
        _exec_omni_agent(["repl", "--session-id", session_id])


def register_channel_command(parent_app: typer.Typer) -> None:
    """Register `omni channel`: run Telegram channel (Rust agent only)."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("channel", ollama=True, embedding_index=True)

    @parent_app.command()
    def channel(
        bot_token: Annotated[
            str | None,
            typer.Option(
                "--bot-token", "-t", help="Telegram bot token (or TELEGRAM_BOT_TOKEN env)"
            ),
        ] = None,
        allowed_users: Annotated[
            str | None,
            typer.Option(
                "--allowed-users",
                "-u",
                help="Allowed usernames/user_ids (comma-separated; empty = deny all, * = allow all)",
            ),
        ] = None,
        allowed_groups: Annotated[
            str | None,
            typer.Option(
                "--allowed-groups",
                "-g",
                help="Allowed group chat_ids (comma-separated, negative IDs e.g. -200123)",
            ),
        ] = None,
    ):
        """Run Telegram channel via Rust `omni-agent channel`."""
        token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            console.print(
                "[red]Telegram bot token not found.[/red]\n"
                "Set one of:\n"
                "  • [bold]--bot-token[/bold] or [bold]-t[/bold]\n"
                "  • [bold]TELEGRAM_BOT_TOKEN[/bold] env"
            )
            raise typer.Exit(1)
        setting_users = get_setting("telegram.allowed_users")
        setting_groups = get_setting("telegram.allowed_groups")
        users = allowed_users if allowed_users is not None else (setting_users or "")
        groups = allowed_groups if allowed_groups is not None else (setting_groups or "")
        max_rounds = get_setting("telegram.max_tool_rounds") or 30
        os.environ["OMNI_AGENT_MAX_TOOL_ROUNDS"] = str(int(max_rounds))
        args = [
            "channel",
            "--bot-token",
            token,
            "--allowed-users",
            users,
            "--allowed-groups",
            groups,
        ]
        _exec_omni_agent(args)


__all__ = ["register_agent_command", "register_channel_command", "register_gateway_command"]
