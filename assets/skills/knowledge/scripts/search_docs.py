"""
Knowledge Skill (Modernized)

Responsibilities:
- Search documentation and references.
- Retrieve project standards (The Librarian).
- Uses 'rg' under the hood for speed.
"""

import subprocess
import shutil
import json
from pathlib import Path
from typing import Any
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.knowledge.search_docs")


@skill_command(
    name="search_documentation",
    description="Search markdown documentation and references for specific topics.",
    autowire=True,
)
def search_documentation(
    query: str,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Search documentation and reference files for specific topics."""
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root

    # Env Check
    rg_exec = shutil.which("rg")
    if not rg_exec:
        return {"success": False, "error": "ripgrep (rg) not found in PATH."}

    # Define Knowledge Base directories
    knowledge_bases = [
        root / "docs",
        root / "assets" / "references",
        root / "assets" / "skills",
        root / "README.md",
    ]

    targets = [str(p) for p in knowledge_bases if p.exists()]

    if not targets:
        return {"success": False, "error": "No documentation directories found in project."}

    # Execute Search using ripgrep with JSON output
    cmd = [rg_exec, "--json", "-t", "markdown", "-i", query] + targets

    try:
        process = subprocess.Popen(
            cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()

        if process.returncode > 1:
            return {"success": False, "error": f"ripgrep failed: {stderr}"}

        # Parse JSON output
        matches = []
        for line in stdout.splitlines():
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    file_path = data["data"]["path"]["text"]
                    line_num = data["data"]["line_number"]
                    content = data["data"]["lines"]["text"].strip()

                    matches.append(
                        {
                            "file": file_path,
                            "line": line_num,
                            "content": content,
                            "header": _find_nearest_header(Path(file_path), line_num),
                        }
                    )
            except (json.JSONDecodeError, KeyError):
                continue

        # Group results by file (deduplicate and limit)
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

        return {
            "success": True,
            "query": query,
            "count": len(matches),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Documentation search failed: {e}")
        return {"success": False, "error": str(e)}


@skill_command(
    name="search_standards",
    description="Search for coding standards and engineering guidelines.",
    autowire=True,
)
def search_standards(
    topic: str,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Search specifically in docs/reference/ for engineering standards."""
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    ref_dir = root / "docs" / "reference"

    if not ref_dir.exists():
        return {"success": False, "error": "docs/reference/ directory not found."}

    rg_exec = shutil.which("rg")
    if not rg_exec:
        return {"success": False, "error": "ripgrep (rg) not found."}

    cmd = [rg_exec, "--json", "-t", "markdown", "-i", topic, str(ref_dir)]

    try:
        process = subprocess.Popen(
            cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()

        matches = []
        for line in stdout.splitlines():
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    file_path = data["data"]["path"]["text"]
                    matches.append(
                        {
                            "file": file_path,
                            "line": data["data"]["line_number"],
                            "content": data["data"]["lines"]["text"].strip(),
                        }
                    )
            except (json.JSONDecodeError, KeyError):
                continue

        grouped: dict[str, list[str]] = {}
        for m in matches:
            if m["file"] not in grouped:
                grouped[m["file"]] = []
            if len(grouped[m["file"]]) < 2:
                grouped[m["file"]].append(m["content"])

        results = [{"file": k, "snippets": v} for k, v in list(grouped.items())[:5]]

        return {"success": True, "topic": topic, "count": len(matches), "results": results}

    except Exception as e:
        return {"success": False, "error": str(e)}


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


__all__ = ["search_documentation", "search_standards"]
