# capabilities/knowledge/ingestor.py
"""
Knowledge Ingestor - Loading project knowledge into Vector Memory

Phase 16: Neural Bridge
- Configuration-driven knowledge directories (from settings.yaml)
- Rich-powered terminal output

Phase 17: Repomix Integration
- Parse repomix-generated XML for standardized knowledge ingestion
- Output path: .data/project_knowledge.xml

Phase 32: Modularized from knowledge_ingestor.py

Usage:
    from agent.capabilities.knowledge.ingestor import ingest_all_knowledge

    # Ingest all knowledge files (reads directories from settings.yaml)
    await ingest_all_knowledge()

    # Ingest specific directory
    await ingest_directory("assets/knowledge", domain="knowledge")

    # Phase 17: Ingest from repomix XML
    await ingest_from_repomix_xml()
"""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from common.gitops import get_project_root
from common.mcp_core.rich_utils import console, panel, success, warning, info, section
from common.prj_dirs import PRJ_DATA

from agent.core.vector_store import get_vector_memory

# Phase 17: Repomix XML path (using PRJ_DATA for git-ignored runtime data)
REPOMIX_XML_PATH = PRJ_DATA("project_knowledge.xml")


def _get_default_knowledge_dirs() -> list[dict[str, str]]:
    """Load default knowledge directories from references.yaml (SSOT)."""
    # SSOT: references.yaml > knowledge_dirs
    return [
        {
            "path": "assets/knowledge",
            "domain": "knowledge",
            "description": "Project knowledge base",
        },
        {"path": "assets/how-to", "domain": "workflow", "description": "How-to guides"},
        {"path": "docs/explanation", "domain": "architecture", "description": "Architecture docs"},
        {
            "path": "assets/skills/knowledge/standards",
            "domain": "standards",
            "description": "Coding standards",
        },
    ]


def get_knowledge_dirs() -> list[dict[str, str]]:
    """
    Get knowledge directories from references.yaml (SSOT).
    Falls back to settings.yaml if references.yaml is not configured.

    SSOT: assets/references.yaml > knowledge_dirs
    """
    # First, try references.yaml (SSOT)
    try:
        from common.mcp_core.reference_library import ReferenceLibrary

        ref = ReferenceLibrary()
        ref_dirs = ref.get("knowledge_dirs", [])
        if ref_dirs and isinstance(ref_dirs, list) and len(ref_dirs) > 0:
            valid_dirs = []
            for d in ref_dirs:
                if isinstance(d, dict) and "path" in d and "domain" in d:
                    valid_dirs.append(
                        {
                            "path": d["path"],
                            "domain": d["domain"],
                            "description": d.get("description", d["path"]),
                        }
                    )
            if valid_dirs:
                return valid_dirs
    except Exception:
        pass

    # Fallback to settings.yaml
    try:
        from common.config.settings import get_setting

        settings_dirs = get_setting("knowledge.directories")
        if settings_dirs and isinstance(settings_dirs, list) and len(settings_dirs) > 0:
            valid_dirs = []
            for d in settings_dirs:
                if isinstance(d, dict) and "path" in d and "domain" in d:
                    valid_dirs.append(
                        {
                            "path": d["path"],
                            "domain": d["domain"],
                            "description": d.get("description", d["path"]),
                        }
                    )
            if valid_dirs:
                return valid_dirs
    except Exception:
        pass

    return _get_default_knowledge_dirs()


def extract_keywords(content: str) -> list[str]:
    """Extract keywords from markdown content for better searchability."""
    keywords = []

    if match := re.search(r"(?i)Keywords?:\s*(.+?)(?:\n|$)", content):
        keywords.extend(k.strip() for k in match.group(1).split(","))

    if match := re.search(r"^#\s+(.+?)$", content, re.MULTILINE):
        keywords.extend(w for w in match.group(1).split() if len(w) > 2)

    return keywords


async def ingest_file(
    file_path: Path, domain: str, collection: str | None = None
) -> dict[str, Any]:
    """Ingest a single markdown file into the vector store."""
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        content = file_path.read_text(encoding="utf-8")
        if not content.strip():
            return {"success": False, "error": "Empty file", "file": str(file_path)}

        title = content.split("\n")[0].lstrip("# ").strip()
        file_id = file_path.stem.lower().replace("-", "_").replace(" ", "_")

        vm = get_vector_memory()
        success_flag = await vm.add(
            documents=[content],
            ids=[f"{domain}-{file_id}"],
            collection=collection,
            metadatas=[
                {
                    "domain": domain,
                    "title": title,
                    "source_file": str(file_path),
                    "keywords": ", ".join(extract_keywords(content)),
                }
            ],
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
    dir_path: str, domain: str, collection: str | None = None, recursive: bool = False
) -> dict[str, Any]:
    """Ingest all markdown files from a directory."""
    project_root = get_project_root()
    full_path = project_root / dir_path

    if not full_path.exists():
        return {"success": False, "error": f"Directory not found: {dir_path}"}

    pattern = "**/*.md" if recursive else "*.md"
    md_files = [
        f
        for f in full_path.glob(pattern)
        if "test" not in f.name.lower() and "template" not in f.name.lower()
    ]

    if not md_files:
        return {"success": False, "error": "No markdown files", "directory": dir_path}

    results = await asyncio.gather(*(ingest_file(f, domain, collection) for f in sorted(md_files)))

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
            dir_path=config["path"], domain=config["domain"], collection="project_knowledge"
        )
        result["description"] = config["description"]
        results.append(result)

        if result.get("success"):
            success(f"{config['description']}: {result['ingested']} files")
        else:
            warning(f"{config['path']}: {result.get('error', 'Failed')}")

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
        console.print(
            panel(
                f"✅ Successfully indexed {total_ingested} documents",
                title="Knowledge Base Ready",
                style="green",
            )
        )
    else:
        console.print(
            panel(
                f"⚠️ Indexed {total_ingested} documents, {total_failed} failed",
                title="Knowledge Base Partial",
                style="yellow",
            )
        )

    return summary


async def ingest_thread_specific_knowledge() -> dict[str, Any]:
    """Ingest thread/deadlock-related knowledge."""
    from common.config.settings import get_setting

    return await ingest_directory(
        dir_path=get_setting("knowledge.base_dir", "assets/knowledge"),
        domain="threading",
        collection="threading_knowledge",
    )


async def ingest_git_workflow_knowledge() -> dict[str, Any]:
    """Ingest git workflow documentation."""
    from common.config.settings import get_setting

    project_root = get_project_root()
    results = []

    for path in [
        get_setting("knowledge.gitops_file", "assets/how-to/gitops.md"),
        get_setting("knowledge.gitops_cache", str(PRJ_DATA("knowledge", "gitops-cache.md"))),
    ]:
        if (project_root / path).exists():
            results.append(await ingest_file(project_root / path, domain="git"))

    successful = sum(1 for r in results if r.get("success"))

    return {
        "success": successful == len(results),
        "total": len(results),
        "ingested": successful,
        "details": results,
    }


async def ingest_from_repomix_xml(xml_path: str | None = None) -> dict[str, Any]:
    """
    Phase 17: Ingest knowledge from repomix-generated XML.

    Repomix creates a standardized XML file from markdown documents.
    This function parses the XML and ingests each file into VectorStore.
    """
    if xml_path is None:
        xml_path = REPOMIX_XML_PATH

    project_root = get_project_root()
    full_path = project_root / xml_path

    if not full_path.exists():
        return {
            "success": False,
            "error": f"Repomix XML not found: {xml_path}",
            "hint": "Run 'repomix' in agent/knowledge to generate the XML",
        }

    info(f"📚 Parsing repomix XML: {xml_path}")

    try:
        tree = ET.parse(full_path)
        root = tree.getroot()

        file_nodes = root.findall(".//file")

        if not file_nodes:
            return {"success": False, "error": "No file nodes found in XML"}

        results = []
        for file_node in file_nodes:
            file_path = file_node.get("path")
            content = file_node.text or ""

            if not content.strip():
                continue

            title = ""
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#"):
                    title = line.lstrip("# ").strip()
                    break

            file_id = Path(file_path).stem.lower().replace("-", "_").replace(" ", "_")

            domain = "knowledge"
            if "standards" in file_path:
                domain = "standards"
            elif "how-to" in file_path:
                domain = "workflow"
            elif "docs" in file_path:
                domain = "architecture"

            vm = get_vector_memory()
            success_flag = await vm.add(
                documents=[content],
                ids=[f"{domain}-{file_id}"],
                collection="project_knowledge",
                metadatas=[
                    {
                        "domain": domain,
                        "title": title,
                        "source_file": file_path,
                        "keywords": ", ".join(extract_keywords(content)),
                    }
                ],
            )

            results.append(
                {
                    "success": success_flag,
                    "file": file_path,
                    "id": f"{domain}-{file_id}",
                    "title": title,
                }
            )

        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful

        return {
            "success": failed == 0,
            "total": len(results),
            "ingested": successful,
            "failed": failed,
            "xml_path": str(full_path),
            "details": [r for r in results if not r.get("success")][:3],
        }

    except ET.ParseError as e:
        return {"success": False, "error": f"XML parse error: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# CLI entry point
def main():
    """Run knowledge ingestion from command line."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--repomix":
        info("Starting knowledge ingestion from repomix XML...")
        results = asyncio.run(ingest_from_repomix_xml())
        console.print(
            panel(
                f"XML: {results.get('xml_path', 'N/A')}\n"
                f"Indexed: {results.get('total_ingested', 0)}\n"
                f"Failed: {results.get('total_failed', 0)}",
                title="📊 Repomix Ingestion Summary",
                style="cyan",
            )
        )
        return

    info("Starting knowledge ingestion...")
    results = asyncio.run(ingest_all_knowledge())

    console.print(
        panel(
            f"Directories: {results.get('total_directories', 0)}\n"
            f"Indexed: {results.get('total_ingested', 0)}\n"
            f"Failed: {results.get('total_failed', 0)}",
            title="📊 Ingestion Summary",
            style="cyan",
        )
    )


if __name__ == "__main__":
    main()


__all__ = [
    "REPOMIX_XML_PATH",
    "_get_default_knowledge_dirs",
    "get_knowledge_dirs",
    "extract_keywords",
    "ingest_file",
    "ingest_directory",
    "ingest_all_knowledge",
    "ingest_thread_specific_knowledge",
    "ingest_git_workflow_knowledge",
    "ingest_from_repomix_xml",
    "main",
]
