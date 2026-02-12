"""
CLI Tab Completion Command

Provides shell completion for omni CLI commands.
Supports bash, zsh, and fish shells.
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Optional

import typer
from rich.console import Console

if TYPE_CHECKING:
    from typer import Typer

console = Console()

COMPLETION_SCRIPT_BASH = """# omni bash completion
_omni_completions() {
    local cur prev words cword
    _init_completion || return

    case "$cur" in
        -*)
            COMPREPLY=($(compgen -W "--help --verbose --conf --version" -- "$cur"))
            ;;
        *)
            COMPREPLY=($(compgen -W "$(omni commands 2>/dev/null)" -- "$cur"))
            ;;
    esac
}
complete -F _omni_completions omni
"""

COMPLETION_SCRIPT_ZSH = """#compdef _omni

_omni_commands() {
    local -a commands
    commands=(
        "completions:Generate shell completion scripts"
        "db:Query and manage databases"
        "knowledge:Manage knowledge base"
        "mcp:Start MCP server"
        "reindex:Reindex vector databases"
        "route:Router testing and diagnostics"
        "run:Execute a task through the Omni Loop"
        "skill:Skill management"
        "sync:Synchronize system state"
        "version:Display version information"
    )
    _describe -t commands 'omni commands' commands
}

_omni_completions() {
    local -A opt_args

    _arguments \\
        '1: :_omni_commands' \\
        '*::arg:->args'

    if [[ $state == args ]]; then
        case $opt_args[1] in
            completions)
                _arguments \\
                    '1:shell:(bash zsh fish)' \\
                    '-o+[Output file path]:file:_files' \\
                    '--output=[Output file path]:file:_files'
                ;;
            db)
                _path_files -W "$HOME/.omni"
                ;;
            mcp)
                _arguments \\
                    '--name=[Server name]:name:' \\
                    '--port=[Port number]:port:'
                ;;
            reindex)
                _arguments \\
                    '--force[Force reindex]'
                ;;
            skill)
                _arguments \\
                    '1:action:(list create sync uninstall update)'
                ;;
            sync)
                _arguments \\
                    '--force[Force sync]'
                ;;
            route)
                _arguments \\
                    '1:action:(test stats cache schema)' \\
                    '--debug[Show detailed routing scores]' \\
                    '--number=[Maximum result count]:number:' \\
                    '--threshold=[Minimum score threshold]:threshold:' \\
                    '--confidence-profile=[Named confidence profile]:name:' \\
                    '--mcp[Use MCP embedding path]' \\
                    '--local[Use local embedding path]' \\
                    '--clear[Clear cache entries]' \\
                    '--path=[Schema output path]:file:_files' \\
                    '--stdout[Print schema JSON to stdout]' \\
                    '--json[Emit command result as JSON]'
                ;;
        esac
    fi
}

compdef _omni_completions omni
"""

COMPLETION_SCRIPT_FISH = """# omni fish completion
complete -c omni -f -a "(omni commands 2>/dev/null)"
complete -c omni -l help -d "Show help"
complete -c omni -l verbose -d "Enable debug logging"
complete -c omni -l conf -d "Custom configuration directory"
"""


def _completions_command(
    shell: str,
    output: Optional[str],
) -> None:
    """Generate shell completion script for omni CLI.

    Args:
        shell: Shell type (bash, zsh, fish)
        output: Output file path (None = print to stdout)
    """
    shell = shell.lower()

    if shell == "bash":
        script = COMPLETION_SCRIPT_BASH
    elif shell == "zsh":
        script = COMPLETION_SCRIPT_ZSH
    elif shell == "fish":
        script = COMPLETION_SCRIPT_FISH
    else:
        console.print(f"[red]Unsupported shell: {shell}[/red]")
        console.print("Supported shells: bash, zsh, fish")
        raise typer.Exit(1)

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script)
        console.print(f"[green]Completion script written to: {output_path}[/green]")
        console.print(f"\nAdd to your shell config:")
        if shell == "bash":
            console.print(f"  echo 'source {output}' >> ~/.bashrc")
        elif shell == "zsh":
            console.print(f"  # For zsh, add to your fpath:")
            console.print(f"  fpath=( {output_path.parent} $fpath )")
            console.print(f"  autoload -Uz compinit")
            console.print(f"  compinit")
            console.print(f"  ")
            console.print(f"  # Or source directly:")
            console.print(f"  echo 'source {output}' >> ~/.zshrc")
        elif shell == "fish":
            console.print(f"  echo 'source {output}' >> ~/.config/fish/config.fish")
    else:
        console.print(script)


def _commands_list() -> None:
    """List all available omni CLI commands."""
    commands = [
        "completions",
        "db",
        "knowledge",
        "mcp",
        "reindex",
        "route",
        "run",
        "skill",
        "sync",
        "version",
    ]

    for cmd in sorted(commands):
        typer.echo(cmd)


def register_completions_command(app: "Typer") -> None:
    """Register completions command with the main app."""

    @app.command("completions")
    def completions(
        shell: str = typer.Argument(
            ...,
            help="Shell type: bash, zsh, or fish",
            case_sensitive=False,
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Output file path (default: print to stdout)",
        ),
    ):
        """Generate shell completion script for omni CLI.

        Examples:
            # Print bash completions to stdout
            omni completions bash

            # Save bash completions to file
            omni completions bash --output ~/.bash_completion.d/omni

            # Print zsh completions
            omni completions zsh

            # Print fish completions
            omni completions fish
        """
        _completions_command(shell, output)

    @app.command("commands")
    def commands():
        """List all available omni CLI commands.

        Used by shell completion scripts.
        """
        _commands_list()


__all__ = ["register_completions_command"]
