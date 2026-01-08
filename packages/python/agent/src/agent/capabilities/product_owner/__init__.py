# capabilities/product_owner
"""
Product Owner - Feature Lifecycle Integrity Enforcement & Spec Management

Phase 32: Modularized subpackage.

Modules:
- spec.py: Spec management (start_spec, verify_spec_completeness)
- complexity.py: Complexity levels and assessment
- alignment.py: Design alignment checking

Usage:
    # New modular imports (recommended)
    from agent.capabilities.product_owner.complexity import assess_feature_complexity
    from agent.capabilities.product_owner.alignment import verify_design_alignment

    # Old imports (still work for backward compatibility)
    from agent.capabilities.product_owner import assess_feature_complexity
"""

from .spec import (
    _get_spec_path_from_name,
    _analyze_spec_gap,
    _load_spec_template,
    _save_spec,
    _check_spec_completeness,
)

from .complexity import (
    COMPLEXITY_LEVELS,
    TEST_REQUIREMENTS,
    CRITICAL_PATTERNS,
    heuristic_complexity,
    get_git_diff,
    get_changed_files,
    _get_checklist,
)

from .alignment import (
    DesignDocsCache,
    load_design_doc,
    _scan_standards,
    _get_recommendations,
    verify_design_alignment,
    get_feature_requirements,
    check_doc_sync,
)

# Backward compatibility: Re-export everything from submodules
__all__ = [
    # From spec
    "_get_spec_path_from_name",
    "_analyze_spec_gap",
    "_load_spec_template",
    "_save_spec",
    "_check_spec_completeness",
    # From complexity
    "COMPLEXITY_LEVELS",
    "TEST_REQUIREMENTS",
    "CRITICAL_PATTERNS",
    "heuristic_complexity",
    "get_git_diff",
    "get_changed_files",
    "_get_checklist",
    # From alignment
    "DesignDocsCache",
    "load_design_doc",
    "_scan_standards",
    "_get_recommendations",
    "verify_design_alignment",
    "get_feature_requirements",
    "check_doc_sync",
]
