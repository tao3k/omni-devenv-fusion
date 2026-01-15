# capabilities/product_owner/alignment.py
"""
Product Owner - Design Alignment

Design document loading and alignment checking:
- DesignDocsCache: Singleton cache for design documents
- load_design_doc: Load a design document
- verify_design_alignment: Check alignment with design documents
- get_feature_requirements: Get requirements for complexity level
- check_doc_sync: Verify docs are updated with code changes

Phase 32: Modularized from product_owner.py
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config.settings import get_setting
from common.mcp_core.reference_library import get_reference_path


# =============================================================================
# Design Docs Cache
# =============================================================================


class DesignDocsCache:
    """
    Singleton cache for design documents.
    Design docs are loaded from docs/ directory on first access,
    then cached in memory for the lifetime of the MCP server.
    """

    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not DesignDocsCache._loaded:
            self._load_design_docs()
            DesignDocsCache._loaded = True

    def _load_design_docs(self):
        """Load design documents from docs/ directory (SSOT: references.yaml)."""
        self._docs = {}

        # SSOT: references.yaml for design docs directory
        from common.gitops import get_project_root

        docs_dir = get_project_root() / get_reference_path("design_docs.dir")
        if not docs_dir.exists():
            return

        explanation_dir = docs_dir / "explanation"
        key_docs = [
            ("design-philosophy", "design-philosophy.md"),
            ("mcp-architecture-roadmap", "mcp-architecture-roadmap.md"),
            ("why-custom-mcp-architecture", "why-custom-mcp-architecture.md"),
        ]

        for doc_name, doc_file in key_docs:
            doc_path = explanation_dir / doc_file
            if not doc_path.exists():
                doc_path = docs_dir / doc_file
            if doc_path.exists():
                try:
                    self._docs[doc_name] = doc_path.read_text()
                except Exception:
                    pass

    def get_doc(self, doc_name: str) -> str:
        """Get a design document by name (without extension)."""
        return self._docs.get(doc_name, "")

    def get_all_docs(self) -> Dict[str, str]:
        """Get all loaded design documents."""
        return self._docs.copy()

    def reload(self):
        """Force reload design docs (for debugging/testing)."""
        self._load_design_docs()


# Global cache instance
_design_cache = DesignDocsCache()


def load_design_doc(filename: str) -> str:
    """Load a design document (uses cache for performance)."""
    if filename.endswith(".md"):
        filename = filename[:-3]
    return _design_cache.get_doc(filename)


def _scan_standards() -> str:
    """Load all markdown standards from standards.dir."""
    from common.gitops import get_project_root
    from common.mcp_core.reference_library import get_reference_path

    standards_dir = get_project_root() / get_reference_path("standards.dir")
    if not standards_dir.exists():
        return "No specific standards found."

    context = []
    priority_files = ["feature-lifecycle.md", "lang-python.md", "lang-nix.md"]

    for fname in priority_files:
        fpath = standards_dir / fname
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            context.append(f"=== STANDARD: {fname} ===\n{content}\n")

    return "\n".join(context) if context else "No standards found."


def _get_reference_docs() -> list[str]:
    """Get reference document paths (SSOT: references.yaml)."""
    from common.gitops import get_project_root

    base = get_project_root()
    return [
        str(base / get_reference_path("design_docs.dir") / "design-philosophy.md"),
        str(base / get_reference_path("design_docs.dir") / "mcp-architecture-roadmap.md"),
        get_reference_path("standards.feature_lifecycle"),
    ]


def _get_recommendations(results: Dict) -> List[str]:
    """Generate recommendations based on alignment results."""
    recs = []

    if not results["philosophy"]["aligned"]:
        recs.append("Review docs/explanation/design-philosophy.md - simplify if possible")

    if results["roadmap"]["in_roadmap"] is False:
        recs.append("Feature not in roadmap - consider adding to docs/index.md")

    if not results["architecture"]["aligned"]:
        recs.append("Review docs/mcp-architecture-roadmap.md - ensure architecture fit")

    if all(r["aligned"] for r in results.values()):
        recs.append("Feature is well-aligned with design documents")

    return recs


async def verify_design_alignment(
    feature_description: str,
    check_philosophy: bool = True,
    check_roadmap: bool = True,
    check_architecture: bool = True,
) -> str:
    """
    Verify feature alignment with design documents.

    Checks if the feature aligns with:
    - Philosophy (docs/explanation/design-philosophy.md)
    - Roadmap (docs/explanation/*.md)
    - Architecture (docs/explanation/mcp-architecture-roadmap.md)
    """
    from common.gitops import get_project_root

    results = {
        "philosophy": {"aligned": True, "notes": []},
        "roadmap": {"aligned": True, "in_roadmap": None, "notes": []},
        "architecture": {"aligned": True, "notes": []},
    }

    # Check philosophy
    if check_philosophy:
        philosophy = load_design_doc("design-philosophy")
        if philosophy:
            desc_lower = feature_description.lower()
            anti_patterns = ["overcomplicated", "unnecessary", "complex"]
            if any(p in desc_lower for p in anti_patterns):
                results["philosophy"]["aligned"] = False
                results["philosophy"]["notes"].append("Feature description suggests complexity")

    # Check roadmap
    if check_roadmap:
        docs_path = get_project_root() / get_reference_path("design_docs.dir")
        roadmap_files = list(docs_path.glob("*roadmap*")) + list(docs_path.glob("*vision*"))
        in_roadmap = False
        for rf in roadmap_files:
            content = rf.read_text().lower()
            if feature_description.lower() in content or any(
                kw in content for kw in feature_description.lower().split()[:3]
            ):
                in_roadmap = True
                break
        results["roadmap"]["in_roadmap"] = in_roadmap
        if not in_roadmap:
            results["roadmap"]["aligned"] = False
            results["roadmap"]["notes"].append(
                "Feature not explicitly in roadmap - consider updating docs/"
            )

    # Check architecture
    if check_architecture:
        architecture = load_design_doc("mcp-architecture-roadmap")
        if architecture:
            desc_lower = feature_description.lower()
            if "dual" in desc_lower or "orchestrator" in desc_lower or "coder" in desc_lower:
                results["architecture"]["notes"].append(
                    "Orchestrator features should be in mcp-server/orchestrator.py"
                )

    overall_aligned = all(r["aligned"] for r in results.values())

    return json.dumps(
        {
            "aligned": overall_aligned,
            "feature": feature_description,
            "checks": results,
            "recommendations": _get_recommendations(results),
            "reference_docs": _get_reference_docs(),  # SSOT: references.yaml
        },
        indent=2,
    )


async def get_feature_requirements(complexity_level: str = "L2") -> str:
    """Get complete requirements for implementing a feature of given complexity."""
    from .complexity import COMPLEXITY_LEVELS, TEST_REQUIREMENTS, _get_checklist

    level = complexity_level.upper()
    if level not in ["L1", "L2", "L3", "L4"]:
        level = "L2"

    return json.dumps(
        {
            "complexity": level,
            "complexity_name": COMPLEXITY_LEVELS[level]["name"],
            "definition": COMPLEXITY_LEVELS[level]["definition"],
            "test_requirements": {
                "command": TEST_REQUIREMENTS[level],
                "coverage_target": "100% for new logic" if level in ["L3", "L4"] else "80%+",
            },
            "documentation_required": level in ["L3", "L4"],
            "design_review_required": level in ["L3", "L4"],
            "integration_tests_required": level in ["L3", "L4"],
            "e2e_tests_required": level == "L4",
            "checklist": _get_checklist(level),
            "reference": get_setting(
                "standards.feature_lifecycle", "assets/standards/feature-lifecycle.md"
            ),
        },
        indent=2,
    )


async def check_doc_sync(changed_files: Optional[List[str]] = None) -> str:
    """Verify that documentation is updated when code changes."""
    from .complexity import get_changed_files

    changed_files = changed_files or get_changed_files()

    code_files = [f for f in changed_files if not f.endswith(".md")]
    doc_files = [f for f in changed_files if f.endswith(".md") or f.startswith("assets/")]

    sync_status = "ok"
    recommendations = []
    required_docs = []

    for f in code_files:
        if f.startswith("mcp-server/"):
            if not any(d in doc_files for d in ["mcp-server/README.md", "CLAUDE.md"]):
                sync_status = "warning"
                required_docs.append(
                    {
                        "file": "mcp-server/README.md and/or CLAUDE.md",
                        "reason": f"mcp-server code changed: {f}",
                        "action": "Add new tool to tool tables",
                    }
                )
        elif f.startswith("units/modules/"):
            required_docs.append(
                {
                    "file": "docs/ or infrastructure docs",
                    "reason": f"Nix module changed: {f}",
                    "action": "Update infrastructure documentation",
                }
            )
        elif f == "justfile":
            required_docs.append(
                {
                    "file": "docs/ and/or command help",
                    "reason": "justfile changed",
                    "action": "Update command documentation",
                }
            )

    spec_files = [f for f in changed_files if f.startswith("assets/specs/")]
    if spec_files:
        if "assets/standards/feature-lifecycle.md" not in doc_files:
            sync_status = "warning"
            required_docs.append(
                {
                    "file": "assets/standards/feature-lifecycle.md",
                    "reason": f"Spec added/modified: {spec_files[0]}",
                    "action": "Update workflow diagrams if needed",
                }
            )

    std_files = [f for f in changed_files if f.startswith("assets/standards/")]
    if std_files and not doc_files:
        sync_status = "warning"
        recommendations.append(f"Standards changed: {std_files}. Update related docs if needed.")

    if code_files and not doc_files and not required_docs:
        sync_status = "ok"
        recommendations.append("Documentation is in sync")

    if required_docs:
        recommendations = [f"Update {d['file']}: {d['action']}" for d in required_docs]

    return json.dumps(
        {
            "status": sync_status,
            "code_files_changed": len(code_files),
            "doc_files_changed": len(doc_files),
            "required_docs": required_docs,
            "recommendations": recommendations if recommendations else ["Documentation is in sync"],
            "reference": "assets/how-to/documentation-workflow.md",
        },
        indent=2,
    )


__all__ = [
    "DesignDocsCache",
    "load_design_doc",
    "_scan_standards",
    "_get_recommendations",
    "verify_design_alignment",
    "get_feature_requirements",
    "check_doc_sync",
]
