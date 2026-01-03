# agent/capabilities/knowledge_ingestor.py
"""
Knowledge Ingestor - Module for loading project knowledge into Vector Memory

This module provides functions to ingest existing documentation files
into the vector store for RAG-powered retrieval.

Usage:
    from agent.capabilities.knowledge_ingestor import ingest_all_knowledge

    # Ingest all knowledge files
    await ingest_all_knowledge()

    # Ingest specific directory
    await ingest_directory("agent/knowledge", domain="knowledge")
"""
import asyncio
from pathlib import Path
from typing import Optional

# In uv workspace, 'common' package is available via workspace members
from common.mcp_core.gitops import get_project_root

from agent.core.vector_store import get_vector_memory
import structlog

logger = structlog.get_logger(__name__)


# Directories to ingest knowledge from
KNOWLEDGE_DIRS = [
    {
        "path": "agent/knowledge",
        "domain": "knowledge",
        "description": "Project knowledge base (troubleshooting, patterns)"
    },
    {
        "path": "agent/how-to",
        "domain": "workflow",
        "description": "How-to guides and workflows"
    },
    {
        "path": "docs/explanation",
        "domain": "architecture",
        "description": "Architectural decisions and philosophy"
    },
]


def extract_keywords_from_content(content: str) -> list[str]:
    """Extract keywords from markdown content for better searchability."""
    import re

    # Extract keywords from first paragraph/section
    keywords = []

    # Extract from Keywords: line
    keyword_match = re.search(r'(?i)Keywords?:\s*(.+?)(?:\n|$)', content)
    if keyword_match:
        keywords.extend([k.strip() for k in keyword_match.group(1).split(',')])

    # Extract from title (# ...)
    title_match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
    if title_match:
        title = title_match.group(1)
        keywords.extend([w for w in title.split() if len(w) > 2])

    return keywords


async def ingest_file(
    file_path: Path,
    domain: str,
    collection: Optional[str] = None
) -> dict:
    """
    Ingest a single markdown file into the vector store.

    Args:
        file_path: Path to the markdown file
        domain: Domain tag for the document
        collection: Optional collection name

    Returns:
        Dict with success status and details
    """
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        content = file_path.read_text(encoding="utf-8")

        # Extract title from first H1
        title = content.split('\n')[0].lstrip('# ').strip()

        # Generate unique ID from filename
        file_id = file_path.stem.lower().replace('-', '_').replace(' ', '_')

        # Extract keywords
        keywords = extract_keywords_from_content(content)

        vm = get_vector_memory()

        success = await vm.add(
            documents=[content],
            ids=[f"{domain}-{file_id}"],
            collection=collection,
            metadatas=[{
                "domain": domain,
                "title": title,
                "source_file": str(file_path),
                "keywords": ", ".join(keywords) if keywords else "",
            }]
        )

        return {
            "success": success,
            "file": str(file_path),
            "id": f"{domain}-{file_id}",
            "title": title,
        }

    except Exception as e:
        logger.error(f"Failed to ingest file: {file_path}", error=str(e))
        return {"success": False, "error": str(e), "file": str(file_path)}


async def ingest_directory(
    dir_path: str,
    domain: str,
    collection: Optional[str] = None,
    recursive: bool = False
) -> dict:
    """
    Ingest all markdown files from a directory.

    Args:
        dir_path: Path to directory (relative to project root)
        domain: Domain tag for documents
        collection: Optional collection name
        recursive: Whether to search recursively

    Returns:
        Dict with success status and count of ingested files
    """
    project_root = get_project_root()  # Uses: git rev-parse --show-toplevel
    full_path = project_root / dir_path

    if not full_path.exists():
        return {"success": False, "error": f"Directory not found: {dir_path}"}

    # Find all markdown files
    pattern = "**/*.md" if recursive else "*.md"
    md_files = list(full_path.glob(pattern))

    if not md_files:
        return {"success": False, "error": f"No markdown files found in {dir_path}"}

    results = []
    for md_file in sorted(md_files):
        # Skip test files and templates
        if "test" in md_file.name.lower() or "template" in md_file.name.lower():
            continue

        result = await ingest_file(md_file, domain, collection)
        results.append(result)

    successful = sum(1 for r in results if r.get("success"))
    failed = len(results) - successful

    return {
        "success": failed == 0,
        "directory": dir_path,
        "total_files": len(results),
        "ingested": successful,
        "failed": failed,
        "details": results[:5]  # First 5 results for debugging
    }


async def ingest_all_knowledge() -> dict:
    """
    Ingest all project knowledge files into the vector store.

    This function loads documentation from:
    - agent/knowledge/ - Troubleshooting, patterns, best practices
    - agent/how-to/ - Workflows and guides
    - docs/explanation/ - Architecture and philosophy

    Returns:
        Dict with summary of all ingestion results
    """
    vm = get_vector_memory()

    if not vm.client:
        return {
            "success": False,
            "error": "Vector memory not available"
        }

    all_results = []

    for config in KNOWLEDGE_DIRS:
        result = await ingest_directory(
            dir_path=config["path"],
            domain=config["domain"],
            collection="project_knowledge"
        )
        result["description"] = config["description"]
        all_results.append(result)

    total_ingested = sum(r.get("ingested", 0) for r in all_results)
    total_failed = sum(r.get("failed", 0) for r in all_results)

    summary = {
        "success": total_failed == 0,
        "total_directories": len(KNOWLEDGE_DIRS),
        "total_ingested": total_ingested,
        "total_failed": total_failed,
        "directories": all_results,
    }

    logger.info(
        "Knowledge ingestion complete",
        ingested=total_ingested,
        failed=total_failed
    )

    return summary


async def ingest_thread_specific_knowledge() -> dict:
    """
    Ingest thread/deadlock-related knowledge specifically.

    This includes:
    - threading-lock-deadlock.md
    - uv-workspace-config.md

    Returns:
        Dict with ingestion results
    """
    return await ingest_directory(
        dir_path="agent/knowledge",
        domain="threading",
        collection="threading_knowledge"
    )


async def ingest_git_workflow_knowledge() -> dict:
    """
    Ingest git workflow documentation.

    Returns:
        Dict with ingestion results
    """
    results = []

    # Ingest gitops.md
    project_root = get_project_root()
    gitops_path = project_root / "agent/how-to/gitops.md"
    if gitops_path.exists():
        results.append(await ingest_file(gitops_path, domain="git"))

    # Ingest gitops-cache.md
    gitops_cache = project_root / "agent/knowledge/gitops-cache.md"
    if gitops_cache.exists():
        results.append(await ingest_file(gitops_cache, domain="git"))

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
    import json

    print("🚀 Starting knowledge ingestion...")
    print("=" * 60)

    results = asyncio.run(ingest_all_knowledge())

    print("\n📊 Ingestion Summary:")
    print(f"  Directories processed: {results.get('total_directories', 0)}")
    print(f"  Total files ingested: {results.get('total_ingested', 0)}")
    print(f"  Failed: {results.get('total_failed', 0)}")

    print("\n📁 By Directory:")
    for r in results.get("directories", []):
        status = "✅" if r.get("success") else "❌"
        print(f"  {status} {r.get('directory')}: {r.get('ingested', 0)} files")

    print("\n" + "=" * 60)

    if results.get("total_failed", 0) > 0:
        print("\n❌ Some files failed to ingest:")
        for r in results.get("directories", []):
            for detail in r.get("details", []):
                if not detail.get("success"):
                    print(f"  - {detail.get('file')}: {detail.get('error')}")

    return results


if __name__ == "__main__":
    main()
