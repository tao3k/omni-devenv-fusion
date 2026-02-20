"""
Declarative load requirements for CLI commands.

Each command group declares what bootstrap services it needs. The entry_point
uses this registry to load only what's required, keeping light commands fast.

Usage (in register_*_command):
    from omni.agent.cli.load_requirements import register_requirements

    def register_skill_command(app_instance: typer.Typer) -> None:
        register_requirements("skill", ollama=False, embedding_index=False)
        app_instance.add_typer(skill_app, name="skill")

When adding a new command:
    1. Call register_requirements(name, ...) in your register_*_command.
    2. Default is ollama=True, embedding_index=True (full bootstrap).
    3. Set to False for commands that don't need that service.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadRequirements:
    """Declarative bootstrap requirements for a command group.

    Attributes:
        ollama: If True, ensure Ollama is running for embedding (skip for route/skill/reindex).
        embedding_index: If True, run ensure_embedding_index_compatibility (skip for skill/reindex).
    """

    ollama: bool = True
    embedding_index: bool = True


# Default: full bootstrap for unknown commands
_DEFAULT = LoadRequirements()

_REGISTRY: dict[str, LoadRequirements] = {}


def register_requirements(
    command: str, *, ollama: bool | None = None, embedding_index: bool | None = None
) -> None:
    """Declare load requirements for a command group.

    Call this from register_*_command before adding the typer. Only specified
    fields are overridden; others keep default (True).

    Args:
        command: Top-level command name (e.g. "skill", "route", "reindex").
        ollama: Whether to ensure Ollama for embedding. False for light commands.
        embedding_index: Whether to run embedding index compatibility check. False for light commands.
    """
    current = _REGISTRY.get(command, _DEFAULT)
    _REGISTRY[command] = LoadRequirements(
        ollama=current.ollama if ollama is None else ollama,
        embedding_index=current.embedding_index if embedding_index is None else embedding_index,
    )


def get_requirements(command: str | None) -> LoadRequirements:
    """Get load requirements for a command. Returns default (full bootstrap) if unknown."""
    if not command:
        return _DEFAULT
    return _REGISTRY.get(command, _DEFAULT)


def get_registry() -> dict[str, LoadRequirements]:
    """Return a copy of the registry (for tests/inspection)."""
    return dict(_REGISTRY)
