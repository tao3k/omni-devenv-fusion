"""DB path resolver: app instance, DB↔table mappings, and store factory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from omni.foundation.config import get_database_path, get_database_paths
from omni.foundation.utils.common import setup_import_paths

setup_import_paths()

db_app = typer.Typer(
    name="db",
    help="Query and manage Omni databases (knowledge, skills, memory)",
    invoke_without_command=False,
)

_console = Console()

DB_TO_DEFAULT_TABLE = {
    "knowledge": "knowledge_chunks",
    "skills": "skills",
    "memory": "memory_chunks",
}

TABLE_TO_DB = {
    "knowledge_chunks": "knowledge",
    "knowledge": "knowledge",
    "skills": "skills",
    "skills_data": "skills",
    "memory": "memory",
    "memory_chunks": "memory",
}


def _list_databases() -> list[dict[str, Any]]:
    """Get list of all databases with their paths and status."""
    databases = []
    db_paths = get_database_paths()

    for db_name, db_path in db_paths.items():
        path = Path(db_path)
        info: dict[str, Any] = {
            "name": db_name,
            "path": str(path),
            "exists": path.exists(),
            "size_mb": 0.0,
        }
        if path.exists() and path.is_dir():
            try:
                total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                info["size_mb"] = round(total_size / (1024 * 1024), 2)
            except Exception:
                pass
        databases.append(info)

    return databases


def _get_table_count(db_path: str, table_name: str) -> int:
    """Get count of records in a table using Rust store."""
    try:
        from omni_core_rs import PyVectorStore

        store = PyVectorStore(db_path, 384, False)
        return store.count(table_name)
    except Exception:
        return -1


def _get_rust_store(db_name: str):
    """Create a RustVectorStore bound to a specific database path."""
    from omni.foundation.bridge.rust_vector import RustVectorStore

    db_path = get_database_path(db_name)
    return RustVectorStore(db_path, 1024, True)


def _resolve_db_and_table(database: str | None, table: str) -> tuple[str, str]:
    """Resolve database + table pair with sensible defaults."""
    table_key = table.lower()
    db_name = database.lower() if database else TABLE_TO_DB.get(table_key, table_key)
    return db_name, table
