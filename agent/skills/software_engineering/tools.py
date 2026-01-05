"""
agent/skills/software_engineering/tools.py
Software Engineering Skill - Architecture analysis and code navigation.

Phase 25: Omni CLI Architecture
Passive Skill Implementation - Exposes EXPOSED_COMMANDS dictionary.
"""

import os
import re
from pathlib import Path
from typing import List, Dict
from common.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Core Tools
# =============================================================================


async def analyze_project_structure(depth: int = 2) -> str:
    """
    Generate a tree-like view of the project structure to understand architecture.
    Ignores common noise (node_modules, .git, __pycache__).
    """
    root = get_project_root()
    exclude_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    output = [f"Project Root: {root.name}"]

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune directories in-place
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs and not d.startswith(".")]

        path = Path(dirpath)
        rel_path = path.relative_to(root)
        level = len(rel_path.parts)

        if level >= depth:
            continue

        indent = "  " * level
        if level > 0:
            output.append(f"{indent}📂 {path.name}/")

        # List key config files specifically at high levels
        for f in filenames:
            if level < depth and (
                f.endswith(".toml")
                or f.endswith(".json")
                or f.endswith(".yaml")
                or f.endswith(".md")
                or f == "Dockerfile"
            ):
                output.append(f"{indent}  📄 {f}")

    return "\n".join(output)


async def grep_codebase(pattern: str, file_extension: str = "", path: str = ".") -> str:
    """
    Universal content search (grep).
    Finds occurrences of a string or regex pattern in ANY file type.

    Args:
        pattern: Regex pattern to search.
        file_extension: Filter (e.g. '.py', '.rs', '.js'). Empty = all text files.
    """
    results = []
    root = get_project_root()
    try:
        target_path = (root / path).resolve()

        # Safety check
        if not str(target_path).startswith(str(root)):
            return "Access denied: Path outside project root."

        count = 0
        MAX_RESULTS = 50

        for r, d, f in os.walk(target_path):
            if ".git" in r or "node_modules" in r or "__pycache__" in r:
                continue

            for file in f:
                if file_extension and not file.endswith(file_extension):
                    continue

                file_path = Path(r) / file
                try:
                    # Quick check for binary
                    with open(file_path, "rb") as check:
                        if b"\0" in check.read(1024):
                            continue

                    # Read text
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    lines = content.splitlines()

                    for i, line in enumerate(lines):
                        if re.search(pattern, line):
                            rel = file_path.relative_to(root)
                            results.append(f"{rel}:{i + 1}: {line.strip()[:100]}")
                            count += 1
                            if count >= MAX_RESULTS:
                                break
                except:
                    continue
            if count >= MAX_RESULTS:
                break

        if not results:
            return f"No matches found for '{pattern}'."

        return f"Universal Grep Results ({len(results)} matches):\n" + "\n".join(results)
    except Exception as e:
        return f"Error: {e}"


async def detect_tech_stack() -> str:
    """
    Analyze the project to identify languages and frameworks used.
    """
    root = get_project_root()
    languages = {}
    frameworks = []

    # Simple heuristic based on extensions and config files
    for r, _, f in os.walk(root):
        if ".git" in r:
            continue
        for file in f:
            ext = Path(file).suffix
            if ext in [".py"]:
                languages["Python"] = languages.get("Python", 0) + 1
            elif ext in [".rs"]:
                languages["Rust"] = languages.get("Rust", 0) + 1
            elif ext in [".js", ".ts"]:
                languages["TypeScript/JS"] = languages.get("TS/JS", 0) + 1
            elif ext in [".go"]:
                languages["Go"] = languages.get("Go", 0) + 1

            if file == "pyproject.toml":
                frameworks.append("Python (Poetry/UV)")
            if file == "Cargo.toml":
                frameworks.append("Rust (Cargo)")
            if file == "package.json":
                frameworks.append("Node.js")
            if file == "docker-compose.yml":
                frameworks.append("Docker Compose")

    # Sort languages by file count
    sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)

    return f"""Tech Stack Detected:
Languages: {", ".join([f"{l} ({c} files)" for l, c in sorted_langs])}
Frameworks/Tools: {", ".join(set(frameworks))}
"""


# =============================================================================
# EXPOSED_COMMANDS - Omni CLI Entry Point
# =============================================================================

EXPOSED_COMMANDS = {
    "analyze_project_structure": {
        "func": analyze_project_structure,
        "description": "Generate a tree-like view of the project structure.",
        "category": "read",
    },
    "grep_codebase": {
        "func": grep_codebase,
        "description": "Universal content search (grep) for patterns in files.",
        "category": "read",
    },
    "detect_tech_stack": {
        "func": detect_tech_stack,
        "description": "Analyze the project to identify languages and frameworks.",
        "category": "read",
    },
}


# =============================================================================
# Legacy Export for Compatibility
# =============================================================================

__all__ = [
    "analyze_project_structure",
    "grep_codebase",
    "detect_tech_stack",
    "EXPOSED_COMMANDS",
]
