"""
Knowledge Search Commands

Unified text search across documentation and references.
Integrates: search_documentation, search_standards, search_knowledge_base

Commands:
- search: Unified text search across docs, references, and skills
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths

logger = get_logger("skill.knowledge.search")


def _find_nearest_header(file_path: Path, line_num: int) -> str:
    """Find the nearest markdown header above a line."""
    try:
        lines = file_path.read_text().splitlines()
        for i in range(min(line_num, len(lines)) - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith("#"):
                return line.lstrip("# ").strip()
    except Exception:
        pass
    return ""


def _get_header_for_file(file_path: str, matches: list[dict]) -> str:
    """Get the header for a file from the first match."""
    for m in matches:
        if m["file"] == file_path:
            return m.get("header", "")
    return ""


def _run_ripgrep(query: str, targets: list[str], root: Path) -> list[dict]:
    """Execute ripgrep search and return parsed results."""
    rg_exec = shutil.which("rg")
    if not rg_exec:
        raise RuntimeError("ripgrep (rg) not found in PATH.")

    cmd = [rg_exec, "--json", "-t", "markdown", "-i", query] + targets

    try:
        process = subprocess.Popen(
            cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()

        if process.returncode > 1:
            raise RuntimeError(f"ripgrep failed: {stderr}")

        matches = []
        for line in stdout.splitlines():
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    matches.append(
                        {
                            "file": data["data"]["path"]["text"],
                            "line": data["data"]["line_number"],
                            "content": data["data"]["lines"]["text"].strip(),
                        }
                    )
            except (json.JSONDecodeError, KeyError):
                continue
        return matches

    except Exception as e:
        logger.error(f"Ripgrep search failed: {e}")
        raise


@skill_command(
    name="search",
    category="search",
    description="""
    Unified text search across documentation, references, and knowledge base.

    Searches in:
    - docs/ - Project documentation
    - assets/references/ - Reference materials
    - assets/skills/ - Skill documentation
    - README.md - Project readme

    Args:
        - query: str - The search term or topic to find (required)
        - scope: str = "all" - Search scope: "docs", "references", "skills", or "all"

    Returns:
        Dictionary with query, count, and results (file, snippets, header).
    """,
    autowire=True,
)
def search(
    query: str,
    scope: str = "all",
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Unified search across documentation and references."""
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root

    # Define search targets based on scope
    targets = []
    if scope in ("all", "docs"):
        if (root / "docs").exists():
            targets.append(str(root / "docs"))
        targets.append(str(root / "README.md"))

    if scope in ("all", "references"):
        ref_dir = root / "assets" / "references"
        if ref_dir.exists():
            targets.append(str(ref_dir))

    if scope in ("all", "skills"):
        skills_dir = root / "assets" / "skills"
        if skills_dir.exists():
            targets.append(str(skills_dir))

    if not targets:
        raise RuntimeError(f"No valid targets for scope '{scope}'.")

    try:
        matches = _run_ripgrep(query, targets, root)

        # Group results by file
        grouped: dict[str, list[str]] = {}
        for m in matches:
            if m["file"] not in grouped:
                grouped[m["file"]] = []
            if len(grouped[m["file"]]) < 3:
                grouped[m["file"]].append(m["content"])

        results = [
            {"file": k, "snippets": v, "header": _get_header_for_file(k, matches)}
            for k, v in list(grouped.items())[:10]
        ]

        return {"query": query, "count": len(matches), "results": results, "scope": scope}

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise


__all__ = ["search"]
