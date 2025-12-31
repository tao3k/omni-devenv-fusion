# mcp-server/product_owner.py
"""
Product Owner - Feature Lifecycle Integrity Enforcement

Tools for enforcing docs/standards/feature-lifecycle.md:
- assess_feature_complexity: LLM-powered complexity assessment (L1-L4)
- verify_design_alignment: Check alignment with design/roadmap/philosophy
- get_feature_requirements: Return complete requirements for a feature
- check_doc_sync: Verify docs are updated with code changes

Usage:
    @omni-orchestrator assess_feature_complexity code_diff="..." files_changed=[...]
    @omni-orchestrator verify_design_alignment feature_description="..."
    @omni-orchestrator check_doc_sync changed_files=[...]

Performance: Uses singleton caching - design docs loaded once per session.
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

# =============================================================================
# Singleton Cache - Design docs loaded once per MCP session
# =============================================================================

class DesignDocsCache:
    """
    Singleton cache for design documents.
    Design docs are loaded from design/ directory on first access,
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
        """Load design documents from design/ directory."""
        self._docs = {}

        design_dir = Path("design")
        if not design_dir.exists():
            return

        # Load key design documents
        key_docs = [
            "writing-style/01_philosophy",
            "mcp-architecture-roadmap",
            "why-custom-mcp-architecture"
        ]

        for doc_name in key_docs:
            doc_path = design_dir / f"{doc_name}.md"
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


# =============================================================================
# Constants from feature-lifecycle.md
# =============================================================================

COMPLEXITY_LEVELS = {
    "L1": {
        "name": "Trivial",
        "definition": "Typos, config tweaks, doc updates",
        "tests": "None (linting only)",
        "examples": "Fix typo, update README, change comment"
    },
    "L2": {
        "name": "Minor",
        "definition": "New utility function, minor tweak",
        "tests": "Unit Tests",
        "examples": "Add helper function, refactor internal method"
    },
    "L3": {
        "name": "Major",
        "definition": "New module, API, or DB schema change",
        "tests": "Unit + Integration Tests",
        "examples": "New MCP tool, add API endpoint, DB migration"
    },
    "L4": {
        "name": "Critical",
        "definition": "Core logic, Auth, Payments, breaking changes",
        "tests": "Unit + Integration + E2E Tests",
        "examples": "Auth system, breaking API changes, security fixes"
    }
}

TEST_REQUIREMENTS = {
    "L1": "just lint (no test needed)",
    "L2": "just test-unit",
    "L3": "just test-unit && just test-int",
    "L4": "just test-unit && just test-int && manual E2E"
}

# Files that indicate critical functionality
CRITICAL_PATTERNS = [
    "auth", "login", "password", "credential",
    "payment", "billing", "subscription",
    "security", "encryption", "token",
    "breaking", "migration", "schema"
]

# =============================================================================
# Helper Functions
# =============================================================================

def get_git_diff(staged: bool = True) -> str:
    """Get git diff for analysis."""
    try:
        cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except Exception:
        return ""


def get_changed_files() -> List[str]:
    """Get list of changed files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except Exception:
        return []


def load_design_doc(filename: str) -> str:
    """Load a design document (uses cache for performance)."""
    # Remove .md extension if present
    if filename.endswith('.md'):
        filename = filename[:-3]
    return _design_cache.get_doc(filename)


def heuristic_complexity(files: List[str], diff: str) -> str:
    """
    Fast heuristic-based complexity assessment.
    Used as fallback when LLM is unavailable or as quick check.
    """
    files_str = " ".join(files).lower() + " " + diff.lower()

    # Check for critical patterns (L4)
    for pattern in CRITICAL_PATTERNS:
        if pattern in files_str:
            return "L4"

    # Check for new MCP tools (L3)
    if any("mcp-server/" in f for f in files) and "test" not in files_str:
        return "L3"

    # Check for new modules (L3)
    if any(f.startswith("units/modules/") or f.startswith("mcp-server/") for f in files):
        if len(diff.split('\n')) > 50:
            return "L3"

    # Check for documentation only (L1)
    if all(f.endswith('.md') or f.startswith('docs/') for f in files):
        return "L1"

    # Check for nix config changes (L2-L3)
    if any(f.endswith('.nix') for f in files):
        return "L2"

    # Check for general code changes (L2)
    if any(f.endswith('.py') for f in files):
        return "L2"

    return "L2"  # Default to L2


# =============================================================================
# MCP Tools
# =============================================================================

def register_product_owner_tools(mcp: Any) -> None:
    """Register all product owner tools with the MCP server."""

    @mcp.tool()
    async def assess_feature_complexity(
        code_diff: str = "",
        files_changed: List[str] = None,
        feature_description: str = ""
    ) -> str:
        """
        Assess feature complexity level (L1-L4) using LLM analysis.

        Analyzes the proposed changes and returns the Required Testing Level
        based on docs/standards/feature-lifecycle.md.

        Args:
            code_diff: Git diff or code changes to analyze
            files_changed: List of files that will be modified
            feature_description: Natural language description of the feature

        Returns:
            JSON with complexity level, test requirements, and rationale
        """
        files_changed = files_changed or []
        diff = code_diff or get_git_diff()

        # Check for API key availability
        api_key = None
        try:
            from mcp_core import InferenceClient
            api_key = InferenceClient(api_key="", base_url="").api_key
        except Exception:
            pass

        # Try LLM analysis if API key available
        if api_key or feature_description:
            try:
                from mcp_core import InferenceClient

                inference = InferenceClient(
                    api_key=api_key or "",
                    base_url="https://api.minimax.io/anthropic"
                )

                prompt = f"""Analyze the following code changes for complexity classification.

Feature Description: {feature_description}
Files Changed: {', '.join(files_changed) if files_changed else 'N/A'}
Code Diff: {diff[:3000]}...

Classify complexity (L1-L4) based on docs/standards/feature-lifecycle.md:
- L1 (Trivial): Typos, config tweaks, doc updates
- L2 (Minor): Utility function, minor tweak
- L3 (Major): New module, API, DB schema change
- L4 (Critical): Auth, Payments, breaking changes

Return JSON with:
{{"level": "L1-L4", "name": "Complexity name", "rationale": "Why this level", "test_requirements": "Required tests"}}
"""

                result = await inference.complete(
                    prompt=prompt,
                    system_prompt="You are a software architect. Analyze code changes and classify complexity. Return only valid JSON.",
                    max_tokens=500
                )

                # Try to parse LLM response
                try:
                    llm_result = json.loads(result.content)
                    level = llm_result.get("level", "L2")
                    # Validate level
                    if level not in ["L1", "L2", "L3", "L4"]:
                        level = "L2"
                except (json.JSONDecodeError, AttributeError):
                    level = "L2"

            except Exception as e:
                # Fallback to heuristics on error
                level = heuristic_complexity(files_changed, diff)
        else:
            # Use heuristics only
            level = heuristic_complexity(files_changed, diff)

        # Get level details
        level_info = COMPLEXITY_LEVELS.get(level, COMPLEXITY_LEVELS["L2"])
        test_req = TEST_REQUIREMENTS.get(level, "just test")

        return json.dumps({
            "level": level,
            "name": level_info["name"],
            "definition": level_info["definition"],
            "test_requirements": test_req,
            "examples": level_info["examples"],
            "rationale": f"Based on {len(files_changed)} file(s) changed and diff analysis",
            "reference": "docs/standards/feature-lifecycle.md"
        }, indent=2)

    @mcp.tool()
    async def verify_design_alignment(
        feature_description: str,
        check_philosophy: bool = True,
        check_roadmap: bool = True,
        check_architecture: bool = True
    ) -> str:
        """
        Verify feature alignment with design documents.

        Checks if the feature aligns with:
        - Philosophy (design/writing-style/01_philosophy.md)
        - Roadmap (design/*.md)
        - Architecture (design/mcp-architecture-roadmap.md)

        Args:
            feature_description: Description of the feature to verify
            check_philosophy: Check alignment with writing philosophy
            check_roadmap: Check if in roadmap
            check_architecture: Check architecture fit

        Returns:
            JSON with alignment status and references
        """
        results = {
            "philosophy": {"aligned": True, "notes": []},
            "roadmap": {"aligned": True, "in_roadmap": None, "notes": []},
            "architecture": {"aligned": True, "notes": []}
        }

        # Check philosophy
        if check_philosophy:
            philosophy = load_design_doc("writing-style/01_philosophy.md")
            if philosophy:
                # Quick heuristic check
                desc_lower = feature_description.lower()
                anti_patterns = ["overcomplicated", "unnecessary", "complex"]
                if any(p in desc_lower for p in anti_patterns):
                    results["philosophy"]["aligned"] = False
                    results["philosophy"]["notes"].append("Feature description suggests complexity")

        # Check roadmap
        if check_roadmap:
            # Look for roadmap files
            roadmap_files = list(Path("design").glob("*roadmap*")) + list(Path("design").glob("*vision*"))
            in_roadmap = False
            for rf in roadmap_files:
                content = rf.read_text().lower()
                if feature_description.lower() in content or any(kw in content for kw in feature_description.lower().split()[:3]):
                    in_roadmap = True
                    break
            results["roadmap"]["in_roadmap"] = in_roadmap
            if not in_roadmap:
                results["roadmap"]["aligned"] = False
                results["roadmap"]["notes"].append("Feature not explicitly in roadmap - consider updating design/")

        # Check architecture
        if check_architecture:
            architecture = load_design_doc("mcp-architecture-roadmap.md")
            if architecture:
                # Check for architecture conflicts
                desc_lower = feature_description.lower()
                if "dual" in desc_lower or "orchestrator" in desc_lower or "coder" in desc_lower:
                    if "orchestrator" in desc_lower and "mcp-server/orchestrator.py" not in " ".join([]):
                        results["architecture"]["notes"].append("Orchestrator features should be in mcp-server/orchestrator.py")

        # Overall alignment
        overall_aligned = all(r["aligned"] for r in results.values())

        return json.dumps({
            "aligned": overall_aligned,
            "feature": feature_description,
            "checks": results,
            "recommendations": _get_recommendations(results),
            "reference_docs": [
                "design/writing-style/01_philosophy.md",
                "design/mcp-architecture-roadmap.md",
                "docs/standards/feature-lifecycle.md"
            ]
        }, indent=2)

    @mcp.tool()
    async def get_feature_requirements(complexity_level: str = "L2") -> str:
        """
        Get complete requirements for implementing a feature of given complexity.

        Args:
            complexity_level: L1, L2, L3, or L4

        Returns:
            JSON with all requirements for this complexity level
        """
        level = complexity_level.upper()
        if level not in ["L1", "L2", "L3", "L4"]:
            level = "L2"

        return json.dumps({
            "complexity": level,
            "complexity_name": COMPLEXITY_LEVELS[level]["name"],
            "definition": COMPLEXITY_LEVELS[level]["definition"],
            "test_requirements": {
                "command": TEST_REQUIREMENTS[level],
                "coverage_target": "100% for new logic" if level in ["L3", "L4"] else "80%+"
            },
            "documentation_required": level in ["L3", "L4"],
            "design_review_required": level in ["L3", "L4"],
            "integration_tests_required": level in ["L3", "L4"],
            "e2e_tests_required": level == "L4",
            "checklist": _get_checklist(level),
            "reference": "docs/standards/feature-lifecycle.md"
        }, indent=2)

    @mcp.tool()
    async def check_doc_sync(changed_files: List[str] = None) -> str:
        """
        Verify that documentation is updated when code changes.

        Args:
            changed_files: List of code files that changed

        Returns:
            JSON with sync status and recommendations
        """
        changed_files = changed_files or get_changed_files()

        code_files = [f for f in changed_files if not f.endswith('.md')]
        doc_files = [f for f in changed_files if f.endswith('.md') or f.startswith('docs/')]

        sync_status = "ok"
        recommendations = []

        # Check if code changes require doc updates
        code_needs_doc = any(
            f.startswith(prefix) for f in code_files
            for prefix in [
                "mcp-server/",
                "units/modules/",
                "justfile",
                "lefthook"
            ]
        )

        if code_needs_doc and not doc_files:
            sync_status = "warning"
            recommendations.append("Code changes detected but no docs updated. Update relevant docs/ files.")

        # Check if only docs changed (ok)
        if code_files and not doc_files and not code_needs_doc:
            sync_status = "ok"

        return json.dumps({
            "status": sync_status,
            "code_files_changed": len(code_files),
            "doc_files_changed": len(doc_files),
            "recommendations": recommendations if recommendations else ["Documentation is in sync"],
            "reference": "docs/standards/feature-lifecycle.md#53-documentation-sync"
        }, indent=2)


def _get_recommendations(results: dict) -> list:
    """Generate recommendations based on alignment results."""
    recs = []

    if not results["philosophy"]["aligned"]:
        recs.append("Review design/writing-style/01_philosophy.md - simplify if possible")

    if results["roadmap"]["in_roadmap"] is False:
        recs.append("Feature not in roadmap - consider adding to design/roadmap.md")

    if not results["architecture"]["aligned"]:
        recs.append("Review design/mcp-architecture-roadmap.md - ensure architecture fit")

    if all(r["aligned"] for r in results.values()):
        recs.append("Feature is well-aligned with design documents")

    return recs


def _get_checklist(level: str) -> list:
    """Get checklist for a complexity level."""
    checklist = ["Code follows writing style (design/writing-style/)"]

    if level in ["L2", "L3", "L4"]:
        checklist.append("Unit tests added/updated")
        checklist.append("Test coverage maintained or improved")

    if level in ["L3", "L4"]:
        checklist.append("Integration tests added")
        checklist.append("Documentation updated in docs/")
        checklist.append("Design reviewed (if L4)")

    if level == "L4":
        checklist.append("E2E tests verified")
        checklist.append("Security review (if applicable)")
        checklist.append("Breaking changes documented")

    return checklist


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "register_product_owner_tools",
    "COMPLEXITY_LEVELS",
    "TEST_REQUIREMENTS",
    "heuristic_complexity"
]
