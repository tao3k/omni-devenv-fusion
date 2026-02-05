"""
Research Tools V2.0 - Turbo-charged Deep Research Capabilities

Optimizations:
1. Smart Clone: Incremental update instead of fresh clone
2. Native Binary: Use system repomix, skip npx overhead
3. Native Tree: Pure Python tree generation (no subprocess)

Functions:
- clone_repo: Smart clone with incremental update
- repomix_map: Native Python file tree generation
- repomix_compress_shard: Compress shard with optimized repomix
- init_harvest_structure: Setup harvested output directory
- save_shard_result: Save individual shard analysis
- save_index: Generate master index for all shards
"""

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.config.dirs import PRJ_CACHE, get_data_dir


def _get_workspace() -> Path:
    """Get the research workspace directory."""
    workspace = Path(PRJ_CACHE("research"))
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def parse_repo_url(url: str) -> tuple[str, str]:
    """
    Parse owner and repo name from a Git URL.

    Args:
        url: Git repository URL (e.g., https://github.com/owner/repo)

    Returns:
        (owner, repo_name) tuple

    Examples:
        >>> parse_repo_url("https://github.com/anthropics/claude-code")
        ("anthropics", "claude-code")
        >>> parse_repo_url("https://github.com/tao3k/omni-dev-fusion.git")
        ("tao3k", "omni-dev-fusion")
    """
    # Clean URL
    url = url.strip().rstrip("/")

    # Handle different URL formats
    patterns = [
        r"github\.com[/:]([^/]+)/([^/.]+)",  # github.com/owner/repo
        r"github\.com[/:]([^/]+)/([^/.]+)\.git",  # github.com/owner/repo.git
        r"raw\.githubusercontent\.com[/:]([^/]+)/([^/]+)",  # raw.githubusercontent.com
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)

    # Fallback: simple split
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1].replace(".git", "")

    # Last resort: use whole URL as repo name
    return "unknown", url.split("/")[-1].replace(".git", "")


def _find_repomix_cmd() -> str:
    """Find repomix executable - prefer system binary, skip npx."""
    # Check if in PATH first (fastest)
    cmd = shutil.which("repomix")
    if cmd:
        return cmd

    # Check nix store
    for p in Path("/nix/store").iterdir():
        repomix_path = p / "bin" / "repomix"
        if repomix_path.exists():
            return str(repomix_path)

    # Fallback to npx
    return "npx"


def clone_repo(url: str, branch: str | None = None) -> dict:
    """
    Smart Clone/Update - Accelerates workflow by updating existing repos.

    - If repo exists with .git: git fetch + reset --hard (incremental update)
    - If no .git or update fails: fresh clone

    Returns:
        dict with 'path' (local path) and 'revision' (git commit hash)
    """
    import subprocess

    repo_name = url.split("/")[-1].replace(".git", "")
    repo_path = _get_workspace() / repo_name

    # Try incremental update first
    if repo_path.exists() and (repo_path / ".git").exists():
        print(f"⚡ [Tool] Updating existing repo: {repo_name}...")

        # Fetch latest (shallow)
        fetch_result = subprocess.run(
            ["git", "fetch", "--depth", "1"],
            cwd=repo_path,
            capture_output=True,
        )

        if fetch_result.returncode == 0:
            try:
                # Get current branch and reset to remote
                subprocess.run(
                    ["git", "reset", "--hard", "FETCH_HEAD"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                )
                # Clean untracked files for purity
                subprocess.run(
                    ["git", "clean", "-fdx"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                )
                print(f"✅ [Tool] Repo updated: {repo_name}")
                return _get_repo_info(repo_path)
            except subprocess.CalledProcessError:
                pass  # Fall through to fresh clone

        print("⚠️ [Tool] Update failed, falling back to fresh clone...")

    # Fresh clone
    if repo_path.exists():
        shutil.rmtree(repo_path)

    print(f"⬇️ [Tool] Cloning fresh repo: {repo_name}...")
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["-b", branch])
    cmd.extend([url, str(repo_path)])

    subprocess.run(cmd, check=True, capture_output=True)
    print(f"✅ [Tool] Repo cloned: {repo_name}")
    return _get_repo_info(repo_path)


def _get_repo_info(repo_path: Path) -> dict:
    """Get git revision info for a repository."""
    import subprocess

    try:
        # Get short commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        commit_hash = hash_result.stdout.strip()[:8] if hash_result.returncode == 0 else "unknown"

        # Get commit date
        date_result = subprocess.run(
            ["git", "log", "-1", "--format=%ci", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        commit_date = date_result.stdout.strip() if date_result.returncode == 0 else ""

        # Get branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

        return {
            "path": str(repo_path),
            "revision": commit_hash,
            "date": commit_date,
            "branch": branch,
        }
    except Exception:
        return {
            "path": str(repo_path),
            "revision": "unknown",
            "date": "",
            "branch": "unknown",
        }


def repomix_map(path: str, max_depth: int = 4) -> str:
    """
    Native Python file tree generation - Fast, cross-platform.

    Generates a lightweight ASCII tree representation of the repository.
    Skips .git, node_modules, and other noise.

    Args:
        path: Local path to the repository root.
        max_depth: Maximum depth to traverse (default: 4).

    Returns:
        str: ASCII representation of the directory tree.
    """
    repo_path = Path(path)
    if not repo_path.exists():
        raise ValueError(f"Path {path} does not exist.")

    lines = [f"Repository: {repo_path.name}", ""]

    def walk_directory(current_path: Path, depth: int, prefix: str = "") -> None:
        """Native Python directory traversal."""
        if depth > max_depth:
            return

        items = {"dirs": [], "files": []}

        for item in current_path.iterdir():
            # Skip common noise
            if item.name.startswith("."):
                continue
            if item.name in ["node_modules", "__pycache__", "target", "build", "dist"]:
                continue

            if item.is_dir():
                items["dirs"].append(item)
            else:
                items["files"].append(item)

        # Sort: dirs first, then files
        for i, subdir in enumerate(sorted(items["dirs"])):
            is_last = i == len(items["dirs"]) - 1 and len(items["files"]) == 0
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}📂 {subdir.name}/")

            # Recurse with proper indentation
            child_prefix = prefix + ("    " if is_last else "│   ")
            walk_directory(subdir, depth + 1, child_prefix)

        for i, file in enumerate(sorted(items["files"])):
            is_last = i == len(items["files"]) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}📄 {file.name}")

    walk_directory(repo_path, 0)
    return "\n".join(lines)


def repomix_compress_shard(
    path: str,
    targets: list[str],
    shard_name: str,
) -> dict[str, Any]:
    """
    Compress a specific shard with optimized repomix call.

    Uses system binary directly to avoid npx overhead.
    """
    repo_path = Path(path)
    safe_name = "".join(c for c in shard_name if c.isalnum() or c in "_ -")
    safe_name = safe_name[:30]  # Limit length
    config_file = repo_path / f"repomix.{safe_name}.json"
    output_file = repo_path / f"context.{safe_name}.xml"

    config = {
        "output": {
            "style": "xml",
            "filePath": str(output_file),
            "removeComments": True,
            "removeEmptyLines": True,
            "headerText": f"Shard: {shard_name}",
        },
        "include": targets,
        "ignore": {
            "patterns": [
                "**/*.lock",
                "**/node_modules/**",
                "**/.git/**",
                "**/*.png",
                "**/*.svg",
                "**/*.jpg",
                "**/*.ico",
                "**/dist/**",
                "**/build/**",
                "**/target/**",
            ]
        },
    }

    config_file.write_text(json.dumps(config, indent=2))

    # Use system binary (fast) or npx (fallback)
    repomix_cmd = _find_repomix_cmd()
    cmd = [repomix_cmd, "--config", str(config_file)]

    result = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    # Cleanup config
    config_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Repomix shard failed: {result.stderr}")

    if output_file.exists():
        content = output_file.read_text(encoding="utf-8")
        output_file.unlink(missing_ok=True)
        return {
            "xml_content": content,
            "token_count": len(content) // 4,
        }
    else:
        raise RuntimeError(f"Repomix shard '{shard_name}' failed to generate output.")


def init_harvest_structure(owner: str, repo_name: str) -> Path:
    """
    Setup .data/harvested/<owner>/<repo_name>/ directory structure.

    Standardized storage format:
    - Old: .data/harvested/YYYYMMDD-repo_name (messy, hard to organize)
    - New: .data/harvested/<owner>/<repo_name>/ (clean, organized by source)

    Args:
        owner: Repository owner/organization (e.g., "anthropics", "tao3k")
        repo_name: Repository name (e.g., "claude-code", "skills")
    """
    base_dir = get_data_dir("harvested") / owner / repo_name

    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "shards").mkdir()

    return base_dir


def save_shard_result(base_dir: Path, shard_id: int, title: str, content: str) -> Path:
    """
    Save a shard analysis to shards/<id>_<title>.md.
    """
    # Sanitize title: remove or replace path separators to prevent nested dirs
    safe_title = title.replace("/", "_").replace("\\", "_")
    filename = f"{shard_id:02d}_{safe_title.lower().replace(' ', '_')}.md"
    shard_dir = base_dir / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)  # Ensure shards dir exists
    file_path = shard_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return file_path


def save_index(
    base_dir: Path,
    title: str,
    repo_url: str,
    request: str,
    shard_summaries: list[str],
    revision: str = "",
    revision_date: str = "",
) -> Path:
    """
    Generate and save index.md for the harvested research.

    Includes YAML frontmatter with source revision info for traceability.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    total_shards = len(shard_summaries)

    # Build YAML frontmatter with source revision
    frontmatter_lines = ["---"]
    frontmatter_lines.append(f"title: Research Analysis: {title}")
    frontmatter_lines.append(f"source: {repo_url}")
    if revision:
        frontmatter_lines.append(f"revision: {revision}")
    if revision_date:
        frontmatter_lines.append(f"revision_date: {revision_date}")
    frontmatter_lines.append(f"generated: {date_str}")
    frontmatter_lines.append(f"shards: {total_shards}")
    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines)

    index_content = f"""{frontmatter}

# Research Analysis: {title}

**Date:** {date_str}
**Source:** [{repo_url}]({repo_url})
**Revision:** `{revision}` {f"({revision_date})" if revision_date else ""}
**Total Shards:** {total_shards}
**Generated by:** Omni-Dev Fusion Researcher V2.0 (Turbo)

---

## Research Goal

> {request}

---

## Module Analysis

Each shard represents a subsystem of the codebase, analyzed in depth:

{chr(10).join(shard_summaries)}

---

## Architecture Overview

| Shard | Description |
|-------|-------------|
"""

    # Add table with descriptions
    for i, summary in enumerate(shard_summaries, 1):
        desc_match = re.search(r"\]\([^)]+\)\s*:\s*(.+?)(?:\s*~)", summary)
        desc = desc_match.group(1).strip() if desc_match else ""
        if len(desc) > 50:
            desc = desc[:50] + "..."
        index_content += f"| {i:02d} | {desc} |\n"

    index_content += """
---

## Usage

1. **Read index.md** for the complete overview
2. **Browse shards/** for detailed subsystem analysis
3. **Cross-reference** between shards to understand interactions

---

*Generated by Omni-Dev Fusion Researcher (Sharded Deep Research V2.0)*
"""

    index_path = base_dir / "index.md"
    index_path.write_text(index_content, encoding="utf-8")
    return index_path


__all__ = [
    "clone_repo",
    "init_harvest_structure",
    "repomix_compress_shard",
    "repomix_map",
    "save_index",
    "save_shard_result",
]
