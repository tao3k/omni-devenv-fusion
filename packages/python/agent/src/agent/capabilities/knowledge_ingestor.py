"""
Knowledge Ingestor - Module for loading project knowledge into Vector Memory

Phase 16: Neural Bridge
- Configuration-driven knowledge directories (from settings.yaml)
- Rich-powered terminal output

Usage:
    from agent.capabilities.knowledge_ingestor import ingest_all_knowledge

    # Ingest all knowledge files (reads directories from settings.yaml)
    await ingest_all_knowledge()

    # Ingest specific directory
    await ingest_directory("agent/knowledge", domain="knowledge")
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from common.mcp_core.gitops import get_project_root
from common.mcp_core.rich_utils import console, panel, success, error, warning, info, section

from agent.core.vector_store import get_vector_memory

# Default knowledge directories (fallback when settings.yaml not configured)
DEFAULT_KNOWLEDGE_DIRS = [
    {"path": "agent/knowledge", "domain": "knowledge", "description": "Project knowledge base"},
    {"path": "agent/how-to", "domain": "workflow", "description": "How-to guides"},
    {"path": "docs/explanation", "domain": "architecture", "description": "Architecture docs"},
    {"path": "agent/skills/knowledge/standards", "domain": "standards", "description": "Coding standards"},
]


def get_knowledge_dirs() -> list[dict[str, str]]:
    """
    Get knowledge directories from settings.yaml or defaults.

    Reads from: settings.knowledge.directories

    Returns:
        List of directory configs with path, domain, description
    """
    try:
        from common.mcp_core.settings import get_setting

        # Try to read from settings.yaml
        settings_dirs = get_setting("knowledge.directories")
        if settings_dirs and isinstance(settings_dirs, list) and len(settings_dirs) > 0:
            # Validate structure
            valid_dirs = []
            for d in settings_dirs:
                if isinstance(d, dict) and "path" in d and "domain" in d:
                    valid_dirs.append({
                        "path": d["path"],
                        "domain": d["domain"],
                        "description": d.get("description", d["path"])
                    })
            if valid_dirs:
                return valid_dirs
    except Exception:
        pass  # Fall back to defaults

    return DEFAULT_KNOWLEDGE_DIRS


def extract_keywords(content: str) -> list[str]:
    """Extract keywords from markdown content for better searchability."""
    keywords = []

    # Extract from Keywords: line
    if match := re.search(r'(?i)Keywords?:\s*(.+?)(?:\n|$)', content):
        keywords.extend(k.strip() for k in match.group(1).split(','))

    # Extract from title (# ...)
    if match := re.search(r'^#\s+(.+?)$', content, re.MULTILINE):
        keywords.extend(w for w in match.group(1).split() if len(w) > 2)

    return keywords


async def ingest_file(file_path: Path, domain: str, collection: str | None = None) -> dict[str, Any]:
    """Ingest a single markdown file into the vector store."""
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        content = file_path.read_text(encoding="utf-8")
        if not content.strip():
            return {"success": False, "error": "Empty file", "file": str(file_path)}

        # Extract title from first H1
        title = content.split('\n')[0].lstrip('# ').strip()

        # Generate unique ID
        file_id = file_path.stem.lower().replace('-', '_').replace(' ', '_')

        # Ingest into vector store
        vm = get_vector_memory()
        success_flag = await vm.add(
            documents=[content],
            ids=[f"{domain}-{file_id}"],
            collection=collection,
            metadatas=[{
                "domain": domain,
                "title": title,
                "source_file": str(file_path),
                "keywords": ", ".join(extract_keywords(content)),
            }]
        )

        return {
            "success": success_flag,
            "file": str(file_path),
            "id": f"{domain}-{file_id}",
            "title": title,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "file": str(file_path)}


async def ingest_directory(
    dir_path: str,
    domain: str,
    collection: str | None = None,
    recursive: bool = False
) -> dict[str, Any]:
    """Ingest all markdown files from a directory."""
    project_root = get_project_root()
    full_path = project_root / dir_path

    if not full_path.exists():
        return {"success": False, "error": f"Directory not found: {dir_path}"}

    # Find markdown files
    pattern = "**/*.md" if recursive else "*.md"
    md_files = [f for f in full_path.glob(pattern)
                if "test" not in f.name.lower() and "template" not in f.name.lower()]

    if not md_files:
        return {"success": False, "error": "No markdown files", "directory": dir_path}

    # Ingest concurrently
    results = await asyncio.gather(*(
        ingest_file(f, domain, collection) for f in sorted(md_files)
    ))

    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful

    return {
        "success": failed == 0,
        "directory": dir_path,
        "total": len(results),
        "ingested": successful,
        "failed": failed,
        "details": [r for r in results if not r.get("success")][:3],
    }


async def ingest_all_knowledge() -> dict[str, Any]:
    """Ingest all project knowledge files into the vector store."""
    vm = get_vector_memory()

    if not vm.client:
        return {"success": False, "error": "Vector memory not available"}

    knowledge_dirs = get_knowledge_dirs()
    results = []

    section("📚 Knowledge Ingestion")

    for config in knowledge_dirs:
        result = await ingest_directory(
            dir_path=config["path"],
            domain=config["domain"],
            collection="project_knowledge"
        )
        result["description"] = config["description"]
        results.append(result)

        # Rich output
        if result.get("success"):
            success(f"{config['description']}: {result['ingested']} files")
        else:
            warning(f"{config['path']}: {result.get('error', 'Failed')}")

    # Summary
    total_ingested = sum(r.get("ingested", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)

    summary = {
        "total_directories": len(results),
        "total_ingested": total_ingested,
        "total_failed": total_failed,
        "directories": results,
    }

    console.print()
    if total_failed == 0:
        console.print(panel(
            f"✅ Successfully indexed {total_ingested} documents",
            title="Knowledge Base Ready",
            style="green"
        ))
    else:
        console.print(panel(
            f"⚠️ Indexed {total_ingested} documents, {total_failed} failed",
            title="Knowledge Base Partial",
            style="yellow"
        ))

    return summary


async def ingest_thread_specific_knowledge() -> dict[str, Any]:
    """Ingest thread/deadlock-related knowledge."""
    return await ingest_directory(
        dir_path="agent/knowledge",
        domain="threading",
        collection="threading_knowledge"
    )


async def ingest_git_workflow_knowledge() -> dict[str, Any]:
    """Ingest git workflow documentation."""
    project_root = get_project_root()
    results = []

    for path in ["agent/how-to/gitops.md", "agent/knowledge/gitops-cache.md"]:
        if (project_root / path).exists():
            results.append(await ingest_file(project_root / path, domain="git"))

    successful = sum(1 for r in results if r.get("success"))

    return {
        "success": successful == len(results),
        "total": len(results),
        "ingested": successful,
        "details": results
    }


# CLI entry point
def main():
    """Run knowledge ingestion from command line."""
    info("Starting knowledge ingestion...")
    results = asyncio.run(ingest_all_knowledge())

    console.print(panel(
        f"Directories: {results.get('total_directories', 0)}\n"
        f"Indexed: {results.get('total_ingested', 0)}\n"
        f"Failed: {results.get('total_failed', 0)}",
        title="📊 Ingestion Summary",
        style="cyan"
    ))


if __name__ == "__main__":
    main()
