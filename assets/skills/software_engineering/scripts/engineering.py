"""
Software Engineering Skill (Refactored)

Philosophy:
- Orchestration: High-level tasks that compose other skills/tools.
- Zero Config: Relies on Standard Interface (Make/Nix/Just).
- Security: All operations constrained to ConfigPaths.project_root.

Commands:
- run_tests: Run project test suite
- analyze_project_structure: Generate tree-like view
- detect_tech_stack: Identify languages and frameworks
- grep_codebase: Content search (fallback to code_tools.search_code)
"""

import subprocess
from pathlib import Path
from typing import Any

# Modern Foundation API
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.software_engineering")


# =============================================================================
# Build & Test Orchestration
# =============================================================================


@skill_command(
    name="run_tests",
    description="Run project test suite.",
    autowire=True,
)
def run_tests(
    test_path: str = "",
    # Injected
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Run tests using standard discovery.
    Prioritizes: 'just test', 'make test', or 'pytest'.
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root

    # Discovery Logic (Smart Defaults)
    cmd = []
    if (root / "justfile").exists():
        cmd = ["just", "test"]
    elif (root / "Makefile").exists():
        cmd = ["make", "test"]
    else:
        cmd = ["pytest"]

    if test_path:
        cmd.append(test_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
        )
        return {
            "success": result.returncode == 0,
            "command": " ".join(cmd),
            "output": result.stdout + result.stderr,
        }
    except FileNotFoundError:
        return {"success": False, "error": f"Command not found: {cmd[0]}"}


# =============================================================================
# Project Analysis
# =============================================================================


@skill_command(
    name="analyze_project_structure",
    description="Generate a tree-like view of the project structure.",
    autowire=True,
)
def analyze_project_structure(
    depth: int = 2,
    paths: ConfigPaths | None = None,
) -> str:
    """
    Generate a tree-like view of the project structure to understand architecture.
    Ignores common noise (node_modules, .git, __pycache__).
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    exclude_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    output = [f"Project Root: {root.name}"]

    import os

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
            output.append(f"{indent}  {path.name}/")

        # List key config files specifically at high levels
        for f in filenames:
            if level < depth and (
                f.endswith(".toml")
                or f.endswith(".json")
                or f.endswith(".yaml")
                or f.endswith(".md")
                or f == "Dockerfile"
            ):
                output.append(f"{indent}    {f}")

    return "\n".join(output)


@skill_command(
    name="detect_tech_stack",
    description="Analyze the project to identify languages and frameworks.",
    autowire=True,
)
def detect_tech_stack(paths: ConfigPaths | None = None) -> str:
    """
    Analyze the project to identify languages and frameworks used.
    """
    import os

    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
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

    return (
        f"Tech Stack Detected:\n"
        f"Languages: {', '.join([f'{l} ({c} files)' for l, c in sorted_langs])}\n"
        f"Frameworks/Tools: {', '.join(set(frameworks))}\n"
    )


__all__ = ["run_tests", "analyze_project_structure", "detect_tech_stack"]
