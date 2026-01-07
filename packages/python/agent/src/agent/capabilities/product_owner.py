# mcp-server/product_owner.py
"""
Product Owner - Feature Lifecycle Integrity Enforcement & Spec Management

Tools for enforcing assets/standards/feature-lifecycle.md and Spec-Driven Development:
- start_spec: [Gatekeeper] Enforces spec exists before coding new work (Phase 11 PydanticAI)
- assess_feature_complexity: LLM-powered complexity assessment (L1-L4)
- draft_feature_spec: Create a structured implementation plan from a description
- verify_spec_completeness: Ensure spec is ready for coding (auto-detects from start_spec)
- verify_design_alignment: Check alignment with docs/roadmap/philosophy
- get_feature_requirements: Return complete requirements for a feature
- check_doc_sync: Verify docs are updated with code changes

Phase 11 Enhancement: Uses PydanticAI for type-safe agent outputs.

Usage:
    @omni-orchestrator start_spec(name="Feature Name")  # Returns LegislationDecision
    @omni-orchestrator assess_feature_complexity code_diff="..." files_changed=[...]
    @omni-orchestrator draft_feature_spec title="..." description="..."
    @omni-orchestrator verify_spec_completeness  # Auto-detects spec_path from start_spec

Performance: Uses singleton caching - design docs loaded once per session from docs/.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

# Phase 11: PydanticAI imports (lazy loaded for backward compatibility)
try:
    from pydantic import BaseModel

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore

# Import project_memory for spec_path auto-detection
from common.mcp_core.memory import ProjectMemory

# =============================================================================
# Singleton Cache - Design docs loaded once per MCP session
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
        """Load design documents from docs/ directory."""
        self._docs = {}

        # Load from docs/explanation/ (primary) with fallback to root
        docs_dir = Path("docs")
        if not docs_dir.exists():
            return

        # Load key design documents from explanation/
        explanation_dir = docs_dir / "explanation"
        key_docs = [
            ("design-philosophy", "design-philosophy.md"),  # docs/explanation/design-philosophy.md
            (
                "mcp-architecture-roadmap",
                "mcp-architecture-roadmap.md",
            ),  # docs/explanation/mcp-architecture-roadmap.md
            (
                "why-custom-mcp-architecture",
                "why-custom-mcp-architecture.md",
            ),  # docs/explanation/why-custom-mcp-architecture.md
        ]

        for doc_name, doc_file in key_docs:
            # First try docs/explanation/
            doc_path = explanation_dir / doc_file
            if not doc_path.exists():
                # Fallback to root (for backward compatibility)
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


# =============================================================================
# Constants from feature-lifecycle.md
# =============================================================================

COMPLEXITY_LEVELS = {
    "L1": {
        "name": "Trivial",
        "definition": "Typos, config tweaks, doc updates",
        "tests": "None (linting only)",
        "examples": "Fix typo, update README, change comment",
    },
    "L2": {
        "name": "Minor",
        "definition": "New utility function, minor tweak",
        "tests": "Unit Tests",
        "examples": "Add helper function, refactor internal method",
    },
    "L3": {
        "name": "Major",
        "definition": "New module, API, or DB schema change",
        "tests": "Unit + Integration Tests",
        "examples": "New MCP tool, add API endpoint, DB migration",
    },
    "L4": {
        "name": "Critical",
        "definition": "Core logic, Auth, Payments, breaking changes",
        "tests": "Unit + Integration + E2E Tests",
        "examples": "Auth system, breaking API changes, security fixes",
    },
}

TEST_REQUIREMENTS = {
    "L1": "just lint (no test needed)",
    "L2": "just test-unit",
    "L3": "just test-unit && just test-int",
    "L4": "just test-unit && just test-int && manual E2E",
}

# Files that indicate critical functionality
CRITICAL_PATTERNS = [
    "auth",
    "login",
    "password",
    "credential",
    "payment",
    "billing",
    "subscription",
    "security",
    "encryption",
    "token",
    "breaking",
    "migration",
    "schema",
]

# =============================================================================
# Phase 11: PydanticAI Schemas (Type-Safe Outputs)
# =============================================================================


def _get_spec_path_from_name(name: str) -> Optional[str]:
    """
    Find spec file path from feature name using GitOps and advanced pattern matching.

    Uses the same logic as start_spec in main.py for consistency.
    Path resolved from references.yaml.
    """
    import re
    from pathlib import Path

    # GitOps - Get project root using single source of truth
    from common.gitops import get_project_root
    from common.mcp_core.reference_library import get_reference_path

    project_root = get_project_root()
    spec_dir = project_root / get_reference_path("specs.dir")

    # Generate candidate filenames (same logic as main.py)
    candidates = set()

    # Candidate 1: Normalize with underscores
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    candidates.add(normalized)

    # Candidate 2: Compact (no underscores)
    compact = re.sub(r"[^a-z0-9]+", "", name.lower())
    candidates.add(compact)

    # Candidate 3: Handle "Phase X" prefix
    phase_match = re.search(r"phase\s*(\d+)", name.lower())
    if phase_match:
        phase_num = phase_match.group(1)
        remaining = re.sub(r"phase\s*\d+\s*", "", name.lower())
        remaining_underscore = re.sub(r"[^a-z0-9]+", "_", remaining)
        remaining_underscore = re.sub(r"_+", "_", remaining_underscore).strip("_")
        phase_style = f"phase{phase_num}_{remaining_underscore}"
        candidates.add(phase_style)
        candidates.add(f"phase{phase_num}{remaining_underscore}")

    # Try to find matching file
    for c in candidates:
        for pattern in [f"{c}.md", f"{c.replace('_', '')}.md"]:
            matches = list(spec_dir.glob(pattern))
            if matches:
                return str(matches[0])

    return None


def _analyze_spec_gap(spec_path: Optional[str]) -> Dict[str, Any]:
    """
    Analyze spec completeness gaps.

    Returns dict matching SpecGapAnalysis schema.
    """
    if not spec_path:
        return {
            "spec_exists": False,
            "spec_path": None,
            "completeness_score": 0,
            "missing_sections": ["all"],
            "has_template_placeholders": False,
            "test_plan_defined": False,
        }

    path = Path(spec_path)
    if not path.exists():
        return {
            "spec_exists": False,
            "spec_path": None,
            "completeness_score": 0,
            "missing_sections": ["file not found"],
            "has_template_placeholders": False,
            "test_plan_defined": False,
        }

    content = path.read_text(encoding="utf-8")
    issues = []

    # Check for placeholders
    placeholders = ["[ ] Step", "function_name", "{FEATURE_NAME}", "TODO"]
    has_placeholders = any(p in content for p in placeholders)

    # Check for required sections
    required_sections = [
        ("## 1. Context", "Context & Goal"),
        ("## 2. Architecture", "Architecture"),
        ("## 3. Implementation", "Implementation Plan"),
        ("## 4. Verification", "Verification Plan"),
    ]
    missing = []
    for section, name in required_sections:
        if section not in content:
            missing.append(name)

    # Check for test plan
    test_plan_keywords = ["Test", "Verify", "test", "verify"]
    has_test_plan = any(kw in content for kw in test_plan_keywords)

    # Calculate score
    score = 100
    score -= len(missing) * 20
    score -= 10 if has_placeholders else 0
    score -= 10 if not has_test_plan else 0
    score = max(0, score)

    return {
        "spec_exists": True,
        "spec_path": spec_path,
        "completeness_score": score,
        "missing_sections": missing,
        "has_template_placeholders": has_placeholders,
        "test_plan_defined": has_test_plan,
    }


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
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except Exception:
        return []


def load_design_doc(filename: str) -> str:
    """Load a design document (uses cache for performance)."""
    # Remove .md extension if present
    if filename.endswith(".md"):
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
        if len(diff.split("\n")) > 50:
            return "L3"

    # Check for documentation only (L1)
    if all(f.endswith(".md") or f.startswith("assets/") for f in files):
        return "L1"

    # Check for nix config changes (L2-L3)
    if any(f.endswith(".nix") for f in files):
        return "L2"

    # Check for general code changes (L2)
    if any(f.endswith(".py") for f in files):
        return "L2"

    return "L2"  # Default to L2


# =============================================================================
# Spec Management Functions
# =============================================================================


def _load_spec_template() -> str:
    """Load the Spec template (from references.yaml)."""
    from common.mcp_core.reference_library import get_reference_path
    from common.gitops import get_project_root

    template_path = get_project_root() / get_reference_path("specs.template")
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "# Spec: {FEATURE_NAME}\n\n## Context\n...\n## Plan\n..."


def _save_spec(title: str, content: str) -> str:
    """Save a spec file (to specs.dir from references.yaml)."""
    from common.mcp_core.reference_library import get_reference_path
    from common.gitops import get_project_root

    filename = title.lower().replace(" ", "_").replace("/", "-") + ".md"
    specs_dir = get_project_root() / get_reference_path("specs.dir")
    path = specs_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _scan_standards() -> str:
    """
    Load all markdown standards from standards.dir.
    Returns a formatted string context for the LLM.
    Path resolved from references.yaml.
    """
    from common.mcp_core.reference_library import get_reference_path
    from common.gitops import get_project_root

    standards_dir = get_project_root() / get_reference_path("standards.dir")
    if not standards_dir.exists():
        return "No specific standards found."

    context = []
    # Priority standards
    priority_files = ["feature-lifecycle.md", "lang-python.md", "lang-nix.md"]

    for fname in priority_files:
        fpath = standards_dir / fname
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            context.append(f"=== STANDARD: {fname} ===\n{content}\n")

    return "\n".join(context) if context else "No standards found."


def _check_spec_completeness(content: str) -> List[str]:
    """Static check for common spec completeness issues."""
    issues = []

    # Check for template placeholders
    if "[ ] Step 1: ..." in content:
        issues.append("Implementation Plan contains template placeholders")
    if "function_name(arg: Type)" in content:
        issues.append("API Signatures contain template placeholders")
    if "{FEATURE_NAME}" in content:
        issues.append("Template placeholder {FEATURE_NAME} not replaced")

    # Check for required sections
    if "## 1. Context & Goal" not in content and "## Context" not in content:
        issues.append("Missing Context section")
    if "## 2. Architecture" not in content and "## Interface" not in content:
        issues.append("Missing Architecture/Interface section")
    if "## 3. Implementation" not in content and "## Plan" not in content:
        issues.append("Missing Implementation Plan section")
    if "## 4. Verification" not in content and "## Test" not in content:
        issues.append("Missing Verification Plan section")

    # Check for meaningful content
    lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith(">")]
    if len(lines) < 10:
        issues.append("Spec appears too short - missing detail")

    return issues


# =============================================================================
# MCP Tools
# =============================================================================


def register_product_owner_tools(mcp: Any) -> None:
    """Register all product owner tools with the MCP server."""

    # -------------------------------------------------------------------------
    # Phase 11: assess_feature_complexity
    # -------------------------------------------------------------------------

    @mcp.tool()
    async def assess_feature_complexity(
        code_diff: str = "", files_changed: List[str] = None, feature_description: str = ""
    ) -> str:
        """
        Assess feature complexity level (L1-L4) using LLM analysis.

        Analyzes the proposed changes and returns the Required Testing Level
        based on agent/standards/feature-lifecycle.md.

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
            from common.mcp_core import InferenceClient

            api_key = InferenceClient(api_key="", base_url="").api_key
        except Exception:
            pass

        # Try LLM analysis if API key available
        if api_key or feature_description:
            try:
                from common.mcp_core import InferenceClient

                inference = InferenceClient(
                    api_key=api_key or "", base_url="https://api.minimax.io/anthropic"
                )

                prompt = f"""Analyze the following code changes for complexity classification.

Feature Description: {feature_description}
Files Changed: {", ".join(files_changed) if files_changed else "N/A"}
Code Diff: {diff[:3000]}...

Classify complexity (L1-L4) based on agent/standards/feature-lifecycle.md:
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
                    max_tokens=500,
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

        return json.dumps(
            {
                "level": level,
                "name": level_info["name"],
                "definition": level_info["definition"],
                "test_requirements": test_req,
                "examples": level_info["examples"],
                "rationale": f"Based on {len(files_changed)} file(s) changed and diff analysis",
                "reference": get_setting(
                    "standards.feature_lifecycle", "assets/standards/feature-lifecycle.md"
                ),
            },
            indent=2,
        )

    @mcp.tool()
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
            "architecture": {"aligned": True, "notes": []},
        }

        # Check philosophy
        if check_philosophy:
            philosophy = load_design_doc("design-philosophy")
            if philosophy:
                # Quick heuristic check
                desc_lower = feature_description.lower()
                anti_patterns = ["overcomplicated", "unnecessary", "complex"]
                if any(p in desc_lower for p in anti_patterns):
                    results["philosophy"]["aligned"] = False
                    results["philosophy"]["notes"].append("Feature description suggests complexity")

        # Check roadmap
        if check_roadmap:
            # Look for roadmap files in docs/
            roadmap_files = list(Path("docs").glob("*roadmap*")) + list(
                Path("docs").glob("*vision*")
            )
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
                # Check for architecture conflicts
                desc_lower = feature_description.lower()
                if "dual" in desc_lower or "orchestrator" in desc_lower or "coder" in desc_lower:
                    if (
                        "orchestrator" in desc_lower
                        and "mcp-server/orchestrator.py" not in " ".join([])
                    ):
                        results["architecture"]["notes"].append(
                            "Orchestrator features should be in mcp-server/orchestrator.py"
                        )

        # Overall alignment
        overall_aligned = all(r["aligned"] for r in results.values())

        return json.dumps(
            {
                "aligned": overall_aligned,
                "feature": feature_description,
                "checks": results,
                "recommendations": _get_recommendations(results),
                "reference_docs": [
                    "docs/explanation/design-philosophy.md",
                    "docs/explanation/mcp-architecture-roadmap.md",
                    "assets/standards/feature-lifecycle.md",
                ],
            },
            indent=2,
        )

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

    @mcp.tool()
    async def check_doc_sync(changed_files: List[str] = None) -> str:
        """
        Verify that documentation is updated when code changes.

        Reference: agent/how-to/documentation-workflow.md

        Args:
            changed_files: List of code files that changed

        Returns:
            JSON with sync status and recommendations
        """
        changed_files = changed_files or get_changed_files()

        code_files = [f for f in changed_files if not f.endswith(".md")]
        doc_files = [f for f in changed_files if f.endswith(".md") or f.startswith("assets/")]

        sync_status = "ok"
        recommendations = []
        required_docs = []

        # Check if code changes require doc updates
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

        # Check for spec changes
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

        # Check for agent/standards changes
        std_files = [f for f in changed_files if f.startswith("assets/standards/")]
        if std_files and not doc_files:
            sync_status = "warning"
            recommendations.append(
                f"Standards changed: {std_files}. Update related docs if needed."
            )

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
                "recommendations": recommendations
                if recommendations
                else ["Documentation is in sync"],
                "reference": "assets/how-to/documentation-workflow.md",
            },
            indent=2,
        )


def _get_recommendations(results: dict) -> list:
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


def _get_checklist(level: str) -> list:
    """Get checklist for a complexity level."""
    checklist = ["Code follows writing style (docs/explanation/design-philosophy.md)"]

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
    "COMPLEXITY_LEVELS",
    "TEST_REQUIREMENTS",
    "heuristic_complexity",
    # Phase 11 exports
    "start_spec",
    "_get_spec_path_from_name",
    "_analyze_spec_gap",
    # One Tool compatible functions
    "assess_feature_complexity",
    "verify_design_alignment",
    "get_feature_requirements",
    "check_doc_sync",
    "validate_prerequisites",
]
