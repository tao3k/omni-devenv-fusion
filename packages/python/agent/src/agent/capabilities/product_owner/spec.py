# capabilities/product_owner/spec.py
"""
Product Owner - Spec Management

Feature lifecycle enforcement and spec management tools:
- start_spec: Enforces spec exists before coding
- verify_spec_completeness: Check spec readiness
- draft_feature_spec: Create structured implementation plan

Phase 32: Modularized from product_owner.py
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.gitops import get_project_root
from common.mcp_core.memory import ProjectMemory


def _get_spec_path_from_name(name: str) -> Optional[str]:
    """Find spec file path from feature name using GitOps."""
    from common.mcp_core.reference_library import get_reference_path

    project_root = get_project_root()
    spec_dir = project_root / get_reference_path("specs.dir")

    candidates = set()
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    candidates.add(normalized)

    compact = re.sub(r"[^a-z0-9]+", "", name.lower())
    candidates.add(compact)

    phase_match = re.search(r"phase\s*(\d+)", name.lower())
    if phase_match:
        phase_num = phase_match.group(1)
        remaining = re.sub(r"phase\s*\d+\s*", "", name.lower())
        remaining_underscore = re.sub(r"[^a-z0-9]+", "_", remaining)
        remaining_underscore = re.sub(r"_+", "_", remaining_underscore).strip("_")
        phase_style = f"phase{phase_num}_{remaining_underscore}"
        candidates.add(phase_style)
        candidates.add(f"phase{phase_num}{remaining_underscore}")

    for c in candidates:
        for pattern in [f"{c}.md", f"{c.replace('_', '')}.md"]:
            matches = list(spec_dir.glob(pattern))
            if matches:
                return str(matches[0])

    return None


def _analyze_spec_gap(spec_path: Optional[str]) -> Dict[str, Any]:
    """Analyze spec completeness gaps."""
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

    placeholders = ["[ ] Step", "function_name", "{FEATURE_NAME}", "TODO"]
    has_placeholders = any(p in content for p in placeholders)

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

    test_plan_keywords = ["Test", "Verify", "test", "verify"]
    has_test_plan = any(kw in content for kw in test_plan_keywords)

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


def _load_spec_template() -> str:
    """Load the Spec template."""
    from common.mcp_core.reference_library import get_reference_path

    template_path = get_project_root() / get_reference_path("specs.template")
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "# Spec: {FEATURE_NAME}\n\n## Context\n...\n## Plan\n..."


def _save_spec(title: str, content: str) -> str:
    """Save a spec file."""
    from common.mcp_core.reference_library import get_reference_path

    filename = title.lower().replace(" ", "_").replace("/", "-") + ".md"
    specs_dir = get_project_root() / get_reference_path("specs.dir")
    path = specs_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _check_spec_completeness(content: str) -> List[str]:
    """Static check for common spec completeness issues."""
    issues = []

    if "[ ] Step 1: ..." in content:
        issues.append("Implementation Plan contains template placeholders")
    if "function_name(arg: Type)" in content:
        issues.append("API Signatures contain template placeholders")
    if "{FEATURE_NAME}" in content:
        issues.append("Template placeholder {FEATURE_NAME} not replaced")

    if "## 1. Context & Goal" not in content and "## Context" not in content:
        issues.append("Missing Context section")
    if "## 2. Architecture" not in content and "## Interface" not in content:
        issues.append("Missing Architecture/Interface section")
    if "## 3. Implementation" not in content and "## Plan" not in content:
        issues.append("Missing Implementation Plan section")
    if "## 4. Verification" not in content and "## Test" not in content:
        issues.append("Missing Verification Plan section")

    lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith(">")]
    if len(lines) < 10:
        issues.append("Spec appears too short - missing detail")

    return issues


__all__ = [
    "_get_spec_path_from_name",
    "_analyze_spec_gap",
    "_load_spec_template",
    "_save_spec",
    "_check_spec_completeness",
]
