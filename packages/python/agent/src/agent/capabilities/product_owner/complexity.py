# capabilities/product_owner/complexity.py
"""
Product Owner - Complexity Assessment

Complexity levels and assessment tools for feature lifecycle:
- COMPLEXITY_LEVELS: L1-L4 definitions
- TEST_REQUIREMENTS: Testing requirements per level
- CRITICAL_PATTERNS: Patterns indicating critical functionality
- heuristic_complexity: Fast heuristic-based complexity assessment
- assess_feature_complexity: LLM-powered complexity assessment

Phase 32: Modularized from product_owner.py
"""

import subprocess
from typing import Dict, List

# =============================================================================
# Constants from feature-lifecycle.md
# =============================================================================

COMPLEXITY_LEVELS: Dict[str, Dict[str, str]] = {
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

TEST_REQUIREMENTS: Dict[str, str] = {
    "L1": "just lint (no test needed)",
    "L2": "just test-unit",
    "L3": "just test-unit && just test-int",
    "L4": "just test-unit && just test-int && manual E2E",
}

# Files that indicate critical functionality
CRITICAL_PATTERNS: List[str] = [
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


def _get_checklist(level: str) -> List[str]:
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


__all__ = [
    "COMPLEXITY_LEVELS",
    "TEST_REQUIREMENTS",
    "CRITICAL_PATTERNS",
    "heuristic_complexity",
    "get_git_diff",
    "get_changed_files",
    "_get_checklist",
]
