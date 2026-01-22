"""
Knowledge Skill - Best Practices (The Architect)

Responsibilities:
- Bridge the gap between Documentation (Theory) and Codebase (Practice).
- Provide "Gold Standard" examples by searching both docs and actual usage.

Commands:
- get_best_practice: Retrieve documentation AND code examples for a topic.
"""

import subprocess
import shutil
import json
from pathlib import Path
from typing import Any
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.knowledge.best_practices")


def _parse_rg_json_output(stdout: str) -> list[dict[str, Any]]:
    """Parse ripgrep JSON output into structured results."""
    results = []
    for line in stdout.splitlines():
        try:
            data = json.loads(line)
            if data["type"] == "match":
                file_path = data["data"]["path"]["text"]
                # Skip irrelevant directories
                if any(
                    x in file_path for x in ["egg-info", "__pycache__", ".git", ".venv", "venv"]
                ):
                    continue
                results.append(
                    {
                        "file": file_path,
                        "line": data["data"]["line_number"],
                        "content": data["data"]["lines"]["text"].strip(),
                    }
                )
        except (json.JSONDecodeError, KeyError):
            continue
    return results


def _run_ripgrep(
    query: str, root: Path, targets: list[str], file_types: list[str]
) -> list[dict[str, Any]]:
    """Execute ripgrep search and return parsed results."""
    rg_exec = shutil.which("rg")
    if not rg_exec:
        return []

    cmd = [rg_exec, "--json", "-i", query] + ["-t" + ft for ft in file_types] + targets

    try:
        process = subprocess.Popen(
            cmd, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()
        if process.returncode > 1:
            logger.warning(f"ripgrep error: {stderr}")
            return []
        return _parse_rg_json_output(stdout)
    except Exception as e:
        logger.warning(f"ripgrep execution failed: {e}")
        return []


@skill_command(
    name="get_best_practice",
    description="Retrieve documentation AND code examples for a specific topic. The Architect's tool for bridging theory and practice.",
    autowire=True,
)
def get_best_practice(
    topic: str,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Bridge Documentation (Theory) and Codebase (Practice).

    This command provides a comprehensive view of how a concept is
    defined in documentation AND how it's actually used in the codebase.

    Args:
        topic: The concept/pattern to search for (e.g., "@skill_command", "async def").
        paths: ConfigPaths instance (auto-injected).

    Returns:
        dict with:
        - success: bool
        - topic: str
        - theory: dict with count and snippets (from docs)
        - practice: dict with count and examples (from code)
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root

    rg_exec = shutil.which("rg")
    if not rg_exec:
        return {"success": False, "error": "ripgrep (rg) not found in PATH."}

    # --- Step 1: Search Documentation (Theory) ---
    doc_targets = []
    for p in ["docs", "assets/references", "README.md"]:
        path = root / p
        if path.exists():
            doc_targets.append(str(path))

    theory_results = _run_ripgrep(topic, root, doc_targets, ["md", "markdown"])

    # --- Step 2: Search Code Implementation (Practice) ---
    code_targets = []
    for p in ["packages", "assets/skills"]:
        path = root / p
        if path.exists():
            code_targets.append(str(path))

    # Exclude tests to find "production" usage patterns
    practice_results = _run_ripgrep(topic, root, code_targets, ["py", "rust"])

    # Filter out test files from practice results
    practice_results = [
        r for r in practice_results if "/tests/" not in r["file"] and "test_" not in r["file"]
    ]

    # --- Step 3: Synthesis ---
    return {
        "success": True,
        "topic": topic,
        "theory": {
            "count": len(theory_results),
            "snippets": theory_results[:3],  # Top 3 doc hits
        },
        "practice": {
            "count": len(practice_results),
            "examples": practice_results[:5],  # Top 5 code usages
        },
    }


__all__ = ["get_best_practice"]
