# agent/cli/commands/skill/generate.py
"""
Generate command for skill CLI - AI-Powered Skill Generation

Uses Meta-Agent Adaptation Factory to create new skills from natural language.
Delegates to the factory extension in assets/skills/skill/extensions/factory/
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import typer
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from .base import skill_app, err_console, SKILLS_DIR


def _get_factory_path() -> Path:
    """Dynamically resolve the factory extension path."""
    # Factory lives in assets/skills/skill/extensions/factory/
    return Path("assets/skills/skill/extensions/factory").resolve()


def _load_factory_module():
    """Hot-load the factory module from assets."""
    factory_path = _get_factory_path()
    if not factory_path.exists():
        raise FileNotFoundError(f"Factory extension not found at: {factory_path}")

    # Add the factory's parent (extensions) to sys.path for imports
    extensions_path = factory_path.parent
    if str(extensions_path) not in sys.path:
        sys.path.insert(0, str(extensions_path))

    # Add the skill root to sys.path for agent.skills imports
    skill_root = (
        factory_path.parent.parent.parent
    )  # .../extensions/factory -> .../skill -> .../assets
    if str(skill_root) not in sys.path:
        sys.path.insert(0, str(skill_root))

    try:
        import importlib

        module = importlib.import_module("factory.core")
        importlib.reload(module)  # Ensure latest code
        return module
    except ImportError as e:
        raise ImportError(f"Failed to load factory module: {e}")


@skill_app.command("generate", short_help="Generate a new skill using AI")
def skill_generate(
    requirement: str = typer.Argument(
        ...,
        help="Natural language description of the skill you need",
    ),
    auto_load: bool = typer.Option(
        True,
        "--auto-load/--no-load",
        "-l/-L",
        help="Automatically load the generated skill",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """
    Generate and load a new skill using AI (Meta-Agent Adaptation Factory).

    This command uses the Build-Test-Improve loop to create a working skill
    from natural language requirements.

    Examples:
        omni skill generate "Parse CSV files and convert to JSON"
        omni skill generate "Search for text in files and return line numbers"
        omni skill generate "Extract specific columns from Excel files"
    """

    async def _run():
        err_console.print(Panel(Text("🔧 Meta-Agent Adaptation Factory", style="bold green")))

        # Dynamically load factory from assets
        factory_path = _get_factory_path()
        err_console.print(f"📂 Factory: {factory_path}")

        start_time = time.perf_counter()

        try:
            # Load factory module from assets
            factory = _load_factory_module()
            MetaAgent = factory.MetaAgent
            GenerationResult = factory.GenerationResult

            # Initialize Meta-Agent
            meta = MetaAgent()
            err_console.print(f"📝 Requirement: {requirement}\n")

            # Generate the skill
            result = await meta.generate_skill(requirement)

            duration_ms = (time.perf_counter() - start_time) * 1000

            if result.success:
                # Success panel
                success_panel = Table.grid(expand=True)
                success_panel.add_column()
                success_panel.add_row(
                    f"✅ Skill Generated: [bold cyan]{result.skill_name}[/bold cyan]"
                )
                success_panel.add_row(f"⏱️  Duration: {duration_ms:.0f}ms")
                if result.skill_code:
                    code_preview = (
                        result.skill_code[:200] + "..."
                        if len(result.skill_code) > 200
                        else result.skill_code
                    )
                    success_panel.add_row(f"📄 Code preview:\n[dim]{code_preview}[/dim]")

                err_console.print(
                    Panel(
                        success_panel,
                        title="✨ Generation Successful",
                        border_style="green",
                        expand=False,
                    )
                )

                # Auto-load if requested
                if auto_load:
                    err_console.print("\n🔄 Loading skill into registry...")
                    try:
                        from agent.core.skill_registry.jit import jit_load_local_skill

                        # Use underscored directory name (hyphens not valid in Python imports)
                        skill_name_underscored = result.skill_name.replace("-", "_")
                        skill_path = SKILLS_DIR(skill_name_underscored)
                        load_result = jit_load_local_skill(skill_path)

                        if load_result["success"]:
                            err_console.print(
                                Panel(
                                    f"✅ Skill '[bold]{result.skill_name}[/bold]' is now ACTIVE!",
                                    title="🎯 Ready to Use",
                                    border_style="blue",
                                )
                            )
                        else:
                            err_console.print(
                                Panel(
                                    f"⚠️  Skill saved but failed to auto-load.\nError: {load_result.get('error')}\nUse: omni skill reload {result.skill_name}",
                                    title="⚠️  Manual Action Required",
                                    border_style="yellow",
                                )
                            )
                    except Exception as e:
                        err_console.print(
                            Panel(
                                f"Failed to auto-load skill: {e}\nUse: omni skill reload {result.skill_name}",
                                title="⚠️  Manual Action Required",
                                border_style="yellow",
                            )
                        )
                else:
                    err_console.print(
                        Panel(
                            f"Run '[bold]omni skill reload {result.skill_name}[/bold]' to activate",
                            title="💡 Next Step",
                            border_style="blue",
                        )
                    )

                # Show usage hint
                err_console.print(
                    f'\n📖 Usage: @omni("{result.skill_name.replace("-", "_")}.your_command")'
                )

            else:
                # Failure panel
                err_console.print(
                    Panel(
                        Text.from_markup(
                            f"❌ Generation Failed\n\n"
                            f"[bold]Error:[/] {result.error or 'Unknown error'}\n"
                            f"[bold]Skill:[/] {result.skill_name or 'N/A'}\n"
                            f"[bold]Duration:[/] {duration_ms:.0f}ms"
                        ),
                        title="🚨 Generation Failed",
                        border_style="red",
                        expand=False,
                    )
                )
                sys.exit(1)

        except FileNotFoundError as e:
            err_console.print(
                Panel(
                    f"Factory extension not found. Please ensure the factory is installed at:\n{factory_path}",
                    title="🏗️ Factory Not Found",
                    border_style="red",
                )
            )
            sys.exit(1)
        except ImportError as e:
            err_console.print(
                Panel(
                    f"Failed to load factory: {e}",
                    title="📦 Import Error",
                    border_style="red",
                )
            )
            if verbose:
                import traceback

                err_console.print(traceback.format_exc())
            sys.exit(1)
        except KeyboardInterrupt:
            err_console.print("\n⚠️  Generation cancelled by user")
            sys.exit(130)
        except Exception as e:
            err_console.print(
                Panel(
                    f"Unexpected error: {e}",
                    title="💥 Critical Error",
                    border_style="red",
                )
            )
            if verbose:
                import traceback

                err_console.print(traceback.format_exc())
            sys.exit(1)

    asyncio.run(_run())


@skill_app.command("evolve", short_help="Analyze usage and suggest improvements")
def skill_evolve(
    min_frequency: int = typer.Option(
        2,
        "--min-freq",
        "-m",
        help="Minimum pattern frequency to suggest",
    ),
    limit: int = typer.Option(
        5,
        "--limit",
        "-l",
        help="Maximum suggestions to return",
    ),
    auto_create: bool = typer.Option(
        False,
        "--auto-create",
        "-a",
        help="Automatically create suggested skills",
    ),
):
    """
    Analyze usage patterns and suggest new skills (Harvester).

    Scans session history to find frequently used patterns that could
    be extracted into reusable skills.
    """

    async def _run():
        err_console.print(
            Panel(
                Text("🌱 Skill Harvester - Analyzing Patterns", style="bold green"),
            )
        )

        try:
            # Try to load harvester from factory (not yet implemented in v2)
            err_console.print(
                Panel(
                    "Harvester is not yet implemented in the factory extension v2.0.",
                    title="🚧 Coming Soon",
                    border_style="yellow",
                )
            )
            return

        except Exception as e:
            err_console.print(
                Panel(
                    f"Harvester error: {e}",
                    title="💥 Error",
                    border_style="red",
                )
            )

    asyncio.run(_run())


__all__ = []
