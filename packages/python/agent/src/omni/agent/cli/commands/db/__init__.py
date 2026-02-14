"""db CLI command package.

Sub-modules by concern:
- query: list, query, search operations
- inspect: table-info, versions, fragments, health, validate-schema
- admin: compact, index, partition, DDL operations
- stats: stats, count
"""

from ._resolver import db_app

# Import sub-modules to register their @db_app.command() decorators
from . import query as _query  # noqa: F401
from . import inspect as _inspect  # noqa: F401
from . import admin as _admin  # noqa: F401
from . import stats as _stats  # noqa: F401

import typer


def register_db_command(parent_app: typer.Typer) -> None:
    """Register the db command with the parent app."""
    parent_app.add_typer(db_app, name="db")


__all__ = ["db_app", "register_db_command"]
