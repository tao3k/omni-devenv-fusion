"""
Research Tools - Deep research capabilities for analyzing external code repositories.

Provides tools for:
- clone_repo: Clone remote repositories to sandbox workspace
- repomix_map: Generate lightweight file tree for project overview
- repomix_compress: Pack code context into LLM-friendly format
- save_report: Persist research findings to knowledge base
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.dirs import PRJ_CACHE, get_data_dir


def _get_workspace() -> Path:
    """Get the research workspace directory."""
    workspace = Path(PRJ_CACHE("research"))
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _get_repo_path(url: str) -> Path:
    """Derive local path from Git URL."""
    repo_name = url.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    return _get_workspace() / repo_name


@skill_command(
    name="clone_repo",
    description="""
    Clone a remote Git repository to a temporary research workspace.

    Use this when you need to analyze an external codebase from GitHub/GitLab.

    Args:
        url: The Git URL of the repository to clone.
        branch: Optional specific branch to clone (defaults to main/default).

    Returns:
        dict with 'path' key containing the local path to the cloned repository.
    """,
)
def clone_repo(url: str, branch: str | None = None) -> dict[str, Any]:
    """
    Clone a remote git repository to a temporary research workspace.

    Args:
        url: The Git URL of the repository.
        branch: Optional specific branch to clone.

    Returns:
        dict with 'path' key containing local path to cloned repo.
    """
    repo_path = _get_repo_path(url)

    # Clean previous analysis if exists
    if repo_path.exists():
        shutil.rmtree(repo_path)

    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["-b", branch])
    cmd.extend([url, str(repo_path)])

    subprocess.run(cmd, check=True, capture_output=True)

    return {"path": str(repo_path)}


@skill_command(
    name="repomix_map",
    description="""
    Generate a lightweight ASCII file tree of the repository.

    **Use this FIRST** to understand project layout before reading code.

    **Parameters**:
    - `path` (required): Local path to the repository root
    - `max_depth` (optional, default: 5): Maximum directory depth to show (max: 10)

    **Returns**: dict with `tree` key containing ASCII representation.
    """,
)
def repomix_map(path: str, max_depth: int = 5) -> dict[str, Any]:
    """
    Generate a lightweight file tree structure of the repository.

    Use this FIRST to understand the project layout before reading code.

    Args:
        path: Local path to the repository.
        max_depth: Maximum depth to traverse (default: 5).

    Returns:
        dict with 'tree' key containing ASCII representation.
    """
    repo_path = Path(path)
    if not repo_path.exists():
        return {"error": f"Path {path} does not exist."}

    # Ensure max_depth is an integer (handle string input from LLM)
    max_depth = int(max_depth)

    lines = [f"Repository: {repo_path.name}", ""]

    def walk_directory(current_path: Path, depth: int, prefix: str = "") -> None:
        """Recursively walk directory and build tree representation."""
        if depth > max_depth:
            return

        items = []
        subdirs = []
        files = []

        for item in current_path.iterdir():
            if item.name.startswith("."):
                continue
            if item.is_dir():
                subdirs.append(item)
            else:
                files.append(item)

        # Sort: directories first, then files
        for i, subdir in enumerate(sorted(subdirs)):
            is_last = i == len(subdirs) - 1 and len(files) == 0
            new_prefix = prefix + ("└── " if is_last else "├── ")
            items.append((f"📂 {subdir.name}/", new_prefix))

            child_prefix = prefix + ("    " if is_last else "│   ")
            walk_directory(subdir, depth + 1, child_prefix)

        for i, file in enumerate(sorted(files)):
            is_last = i == len(files) - 1
            marker = "└── " if is_last else "├── "
            lines.append(f"{prefix}{marker}📄 {file.name}")

    walk_directory(repo_path, 0)
    tree_content = "\n".join(lines)

    return {
        "tree": tree_content,
        "path": path,
        "depth_used": max_depth,
    }


@skill_command(
    name="repomix_compress",
    description="""
    Compress selected files into a single context-friendly XML block for LLM analysis.

    Use after repomix_map to read actual code of interest. Generates Repomix output
    that wraps code with syntax-aware markers.

    Args:
        path: Local path to the repository root.
        targets: List of file patterns or directories to include (e.g., ["src/*.py"]).
        ignore: Optional list of patterns to exclude (e.g., ["**/test_*"]).
        remove_comments: Optional, remove code comments to reduce noise (default: false).
        remove_empty_lines: Optional, remove blank lines for compact output (default: true).

    Returns:
        dict with 'xml_content' key containing the Repomix XML output.
    """,
)
def repomix_compress(
    path: str,
    targets: list[str],
    ignore: list[str] | None = None,
    remove_comments: bool = False,
    remove_empty_lines: bool = True,
) -> dict[str, Any]:
    """
    Compress selected files into a single context-friendly XML block.

    Use after repomix_map to read actual code of interest.

    Args:
        path: Local path to the repository.
        targets: List of file patterns or directories to include.
        ignore: List of patterns to exclude.
        remove_comments: Remove code comments to reduce noise.
        remove_empty_lines: Remove blank lines for compact output.

    Returns:
        dict with 'xml_content' key containing Repomix output.
    """
    repo_path = Path(path)
    if not repo_path.exists():
        return {"error": f"Path {path} does not exist."}

    output_file = repo_path / "repomix-output.xml"

    # Find repomix: try direct path first, fallback to npx
    repomix_cmd = shutil.which("repomix") or "npx"

    # Build repomix command
    cmd = [
        repomix_cmd,
        "--style",
        "xml",
        "--output",
        str(output_file),
    ]
    cmd.extend(["--include", ",".join(targets)])

    # Add noise reduction options
    if remove_comments:
        cmd.append("--remove-comments")
    if remove_empty_lines:
        cmd.append("--remove-empty-lines")

    if ignore:
        cmd.extend(["--ignore", ",".join(ignore)])
    else:
        # Default ignores for clean output
        cmd.extend(
            [
                "--ignore",
                "**/*.lock,**/*.png,**/*.svg,**/node_modules/**,"
                "**/__pycache__/**,**/*.pyc,**/.git/**",
            ]
        )

    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return {"error": f"Repomix failed: {result.stderr}"}

        if output_file.exists():
            content = output_file.read_text(encoding="utf-8")
            # Clean up temp file
            output_file.unlink()
            return {
                "xml_content": content,
                "targets": targets,
                "char_count": len(content),
                "remove_comments": remove_comments,
                "remove_empty_lines": remove_empty_lines,
            }
        else:
            return {"error": "Repomix failed to generate output file."}

    except FileNotFoundError:
        # npx not available, fallback to simple concatenation
        return _fallback_compress(repo_path, targets)


def _fallback_compress(repo_path: Path, targets: list[str]) -> dict[str, Any]:
    """Fallback: Simple file concatenation when repomix is unavailable."""
    content_parts = []

    for pattern in targets:
        path = repo_path / pattern
        if path.is_file():
            content_parts.append(f"=== {pattern} ===\n{path.read_text()}")
        elif path.is_dir():
            for file in sorted(path.rglob("*")):
                if file.is_file() and not file.name.startswith("."):
                    rel = file.relative_to(repo_path)
                    content_parts.append(f"=== {rel} ===\n{file.read_text()}")

    combined = "\n\n".join(content_parts)
    return {
        "xml_content": combined,
        "targets": targets,
        "char_count": len(combined),
        "warning": "Generated without repomix (fallback mode)",
    }


@skill_command(
    name="save_report",
    description="""
    Save research findings to the harvested knowledge directory.

    Use this at the end of a research session to persist your analysis
    to the Omni knowledge base for future retrieval.

    Args:
        repo_name: Name of the repository analyzed (used in filename).
        content: Markdown content of the analysis to save.
        category: Category of research (default: "architecture").

    Returns:
        dict with 'report_path' key containing the path to the saved report.
    """,
)
def save_report(
    repo_name: str,
    content: str,
    category: str = "architecture",
) -> dict[str, Any]:
    """
    Save research findings to the harvested knowledge directory.

    Args:
        repo_name: Name of the repository analyzed.
        content: Markdown content of the analysis.
        category: Category of research (default: "architecture").

    Returns:
        dict with 'report_path' key.
    """
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{date_str}-{category}-analysis-{repo_name}.md"

    harvest_dir = get_data_dir("harvested")
    harvest_dir.mkdir(parents=True, exist_ok=True)

    file_path = harvest_dir / filename
    file_path.write_text(content, encoding="utf-8")

    return {"report_path": str(file_path)}
