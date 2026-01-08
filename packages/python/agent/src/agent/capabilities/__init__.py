# capabilities
"""
Agent Capabilities Module

Phase 32: Modularized subpackages.

Subpackages:
- product_owner: Feature lifecycle, specs, complexity, alignment
- knowledge: Knowledge ingestion and RAG queries
- learning: Learning loop (The Harvester)

Usage:
    # New modular imports (recommended)
    from agent.capabilities.product_owner.complexity import heuristic_complexity
    from agent.capabilities.knowledge.librarian import consult_knowledge_base

    # Old imports (still work for backward compatibility)
    from agent.capabilities import heuristic_complexity
    from agent.capabilities import consult_knowledge_base
"""

# Re-export from product_owner subpackage
from .product_owner import (
    _get_spec_path_from_name,
    _analyze_spec_gap,
    _load_spec_template,
    _save_spec,
    _check_spec_completeness,
    COMPLEXITY_LEVELS,
    TEST_REQUIREMENTS,
    CRITICAL_PATTERNS,
    heuristic_complexity,
    get_git_diff,
    get_changed_files,
    _get_checklist,
    DesignDocsCache,
    load_design_doc,
    _scan_standards,
    _get_recommendations,
    verify_design_alignment,
    get_feature_requirements,
    check_doc_sync,
)

# Re-export from knowledge subpackage
from .knowledge import (
    REPOMIX_XML_PATH,
    DEFAULT_KNOWLEDGE_DIRS,
    get_knowledge_dirs,
    extract_keywords,
    ingest_file,
    ingest_directory,
    ingest_all_knowledge,
    ingest_thread_specific_knowledge,
    ingest_git_workflow_knowledge,
    ingest_from_repomix_xml,
    main,
    consult_knowledge_base,
    ingest_knowledge,
    bootstrap_knowledge,
    list_knowledge_domains,
    search_project_rules,
)

# Re-export from learning subpackage
from .learning import (
    harvest_session_insight,
    list_harvested_knowledge,
    get_scratchpad_summary,
    harvest_session_insight_tool,
    list_harvested_knowledge_tool,
    get_scratchpad_summary_tool,
)

# Backward compatibility: Complete exports
__all__ = [
    # From product_owner
    "_get_spec_path_from_name",
    "_analyze_spec_gap",
    "_load_spec_template",
    "_save_spec",
    "_check_spec_completeness",
    "COMPLEXITY_LEVELS",
    "TEST_REQUIREMENTS",
    "CRITICAL_PATTERNS",
    "heuristic_complexity",
    "get_git_diff",
    "get_changed_files",
    "_get_checklist",
    "DesignDocsCache",
    "load_design_doc",
    "_scan_standards",
    "_get_recommendations",
    "verify_design_alignment",
    "get_feature_requirements",
    "check_doc_sync",
    # From knowledge (ingestor)
    "REPOMIX_XML_PATH",
    "DEFAULT_KNOWLEDGE_DIRS",
    "get_knowledge_dirs",
    "extract_keywords",
    "ingest_file",
    "ingest_directory",
    "ingest_all_knowledge",
    "ingest_thread_specific_knowledge",
    "ingest_git_workflow_knowledge",
    "ingest_from_repomix_xml",
    "main",
    # From knowledge (librarian)
    "consult_knowledge_base",
    "ingest_knowledge",
    "bootstrap_knowledge",
    "list_knowledge_domains",
    "search_project_rules",
    # From learning
    "harvest_session_insight",
    "list_harvested_knowledge",
    "get_scratchpad_summary",
    "harvest_session_insight_tool",
    "list_harvested_knowledge_tool",
    "get_scratchpad_summary_tool",
]
