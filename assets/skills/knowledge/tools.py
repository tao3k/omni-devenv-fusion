"""
agent/skills/knowledge/tools.py
Knowledge Skill - The Project Cortex.

Phase 25: Omni CLI Architecture
Skill implementation with @skill_command decorators.

Role:
  Does NOT execute commands.
  Does NOT edit files.
  ONLY reads project constraints, rules, and status to "enlighten" the LLM.

Philosophy:
  "Knowledge is power." This skill fetches that knowledge.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import structlog

from agent.skills.decorators import skill_command
from common.gitops import get_project_root
from common.skills_path import SKILLS_DIR

logger = structlog.get_logger(__name__)


# =============================================================================
# Language Expert System (Migrated from lang_expert.py)
# =============================================================================

# File extension to language mapping
EXT_TO_LANG = {
    ".nix": "nix",
    ".py": "python",
    ".rs": "rust",
    ".jl": "julia",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
}

# Language display names
LANG_NAMES = {
    "nix": "Nix",
    "python": "Python",
    "rust": "Rust",
    "julia": "Julia",
    "toml": "TOML",
    "yaml": "YAML",
}


class StandardsCache:
    """Singleton cache for language standards loaded from skills/knowledge/standards/."""

    _instance: Optional["StandardsCache"] = None
    _loaded: bool = False
    _standards: Dict[str, str] = {}

    def __new__(cls) -> "StandardsCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not StandardsCache._loaded:
            self._load_standards()
            StandardsCache._loaded = True

    def _load_standards(self) -> None:
        """Load all language standards from skills/knowledge/standards/."""
        # SSOT: Use SKILLS_DIR for path resolution
        skill_dir = SKILLS_DIR("knowledge")
        standards_dir = skill_dir / "standards"

        if not standards_dir.exists():
            return

        for std_file in standards_dir.glob("lang-*.md"):
            lang = std_file.stem.replace("lang-", "")
            try:
                self._standards[lang] = std_file.read_text()
            except Exception:
                pass

    def get_standard(self, lang: str) -> str:
        """Get standards for a language."""
        return self._standards.get(lang, "")

    def get_all_standards(self) -> Dict[str, str]:
        """Get all loaded standards."""
        return self._standards.copy()


_standards_cache = StandardsCache()


def _get_language_from_path(file_path: str) -> Optional[str]:
    """Detect language from file extension."""
    path = Path(file_path)
    ext = path.suffix.lower()
    return EXT_TO_LANG.get(ext)


def _extract_relevant_standards(standard: str, task: str) -> Optional[str]:
    """Extract standards sections relevant to the task."""
    task_words = set(re.findall(r"\w+", task.lower()))
    common_words = {"the", "a", "an", "to", "for", "in", "add", "file", "use", "code"}

    lines = standard.split("\n")
    relevant_lines = []

    for line in lines:
        if line.startswith("##"):
            if relevant_lines and len(relevant_lines) > 2:
                section_text = " ".join(relevant_lines).lower()
                overlap = task_words & set(re.findall(r"\w+", section_text)) - common_words
                if overlap:
                    relevant_lines.append(line)
                elif any(
                    kw in section_text for kw in ["forbidden", "anti-pattern", "correct", "wrong"]
                ):
                    relevant_lines.append(line)
                else:
                    relevant_lines = [line]
            else:
                relevant_lines = [line]
        elif relevant_lines:
            relevant_lines.append(line)

    if relevant_lines:
        section_text = " ".join(relevant_lines).lower()
        overlap = task_words & set(re.findall(r"\w+", section_text)) - common_words
        if not overlap and len(relevant_lines) < 5:
            return None

    return "\n".join(relevant_lines[:30]) if relevant_lines else None


# =============================================================================
# Internal Helpers (Pure Execution - No Business Logic)
# =============================================================================


def _get_project_name() -> str:
    """Extract project name from pyproject.toml."""
    # SSOT: Use get_project_root() for path resolution
    project_root = get_project_root()
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("name", "unknown")
        except Exception:
            pass
    return "omni-devenv-fusion"


def _load_scopes() -> List[str]:
    """Load valid git scopes from cog.toml."""
    from common.settings import get_setting

    try:
        # SSOT: get_setting() auto-resolves paths with project_root
        cog_toml_path = Path(get_setting("config.cog_toml", "cog.toml"))

        if cog_toml_path.exists():
            with open(cog_toml_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("scopes", [])
    except Exception:
        pass
    return ["core"]


def _analyze_lefthook() -> List[Dict[str, str]]:
    """Analyze lefthook configuration to determine active guardrails."""
    from common.settings import get_setting

    hooks = []

    # SSOT: get_setting() auto-resolves paths with project_root
    lefthook_yaml = Path(get_setting("config.lefhook_yaml", "lefthook.yml"))

    if lefthook_yaml.exists():
        try:
            content = lefthook_yaml.read_text()
            hook_map = [
                ("nixfmt", "nixfmt", "Format Nix code"),
                ("vale", "vale", "Writing style check"),
                ("ruff", "ruff", "Python linting"),
                ("shellcheck", "shellcheck", "Shell script analysis"),
            ]
            for hook_name, keyword, description in hook_map:
                if keyword in content:
                    hooks.append({"name": hook_name, "description": description})
        except Exception:
            pass

    return hooks


def _get_writing_style() -> Dict[str, Any]:
    """Get writing style configuration."""
    return {
        "language": "english_only",
        "commit_language": "english_only",
        "max_sentence_length": 25,
        "list_max_items": 4,
    }


def _get_architecture_summary() -> Dict[str, str]:
    """Get high-level architecture description."""
    return {
        "pattern": "Skill-Centric Architecture",
        "mcp_servers": ["orchestrator", "coder"],
        "key_directories": {
            "assets/": "LLM context (how-to, standards, specs)",
            "assets/skills/": "Skill modules",
            "docs/": "User documentation",
            "packages/": "Python packages",
        },
    }


def _search_docs(topic: str) -> str:
    """Search documentation for a topic."""
    from common.gitops import get_project_root

    # SSOT: Use get_project_root() for path resolution
    docs_dir = get_project_root() / "docs"
    if not docs_dir.exists():
        return f"No docs directory found for topic '{topic}'."

    topic_lower = topic.lower().replace(" ", "-").replace("_", "-")
    matches = []

    project_root = get_project_root()
    for md_file in docs_dir.rglob("*.md"):
        if topic_lower in md_file.name.lower():
            content = _read_file_content(str(md_file))
            if content:
                matches.append(f"=== {md_file.relative_to(project_root)} ===\n{content[:1000]}...")

    if not matches:
        agent_dir = project_root / "agent"
        for md_file in agent_dir.rglob("*.md"):
            if (
                topic_lower in md_file.name.lower()
                or topic_lower in md_file.read_text().lower()[:2000]
            ):
                content = _read_file_content(str(md_file))
                if content:
                    matches.append(
                        f"=== {md_file.relative_to(project_root)} ===\n{content[:1000]}..."
                    )

    if matches:
        return f"\n\n---\n\n".join(matches[:3])

    return f"No documentation found for '{topic}'. Try: 'git', 'nix', 'writing', 'architecture'"


def _read_file_content(path: str) -> str:
    """Read file content safely."""
    from common.gitops import get_project_root

    try:
        # SSOT: Use get_project_root() for path resolution
        project_root = get_project_root()
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = project_root / file_path

        if file_path.exists():
            return file_path.read_text().strip()
    except Exception:
        pass
    return ""


# =============================================================================
# Core Tools
# =============================================================================


@skill_command(
    name="knowledge_get_development_context",
    category="read",
    description="[Cognition] Load the Rules of Engagement for this project.",
)
async def get_development_context() -> str:
    """
    [Cognition] Loads the "Rules of Engagement" for this project.

    Call this BEFORE:
    - Writing code
    - Making commits
    - Creating documentation

    Returns:
        - Valid Git Scopes (from cog.toml)
        - Project Standards (from docs)
        - Active Guardrails (Lefthook checks)
        - Writing Style Rules
    """
    context = {
        "project": _get_project_name(),
        "git_rules": {
            "types": [
                "feat",
                "fix",
                "docs",
                "style",
                "refactor",
                "perf",
                "test",
                "build",
                "ci",
                "chore",
            ],
            "scopes": _load_scopes(),
            "message_format": "<type>(<scope>): <description>",
            "policy": "Conventional Commits + Atomic Steps",
        },
        "guardrails": _analyze_lefthook(),
        "writing_style": _get_writing_style(),
        "architecture": _get_architecture_summary(),
    }
    return json.dumps(context, indent=2)


@skill_command(
    name="knowledge_consult_architecture_doc",
    category="read",
    description="[RAG] Semantic search for documentation.",
)
async def consult_architecture_doc(topic: str) -> str:
    """
    [RAG] Semantic search for documentation.

    Usage:
    - consult_architecture_doc("writing style") -> Writing standards
    - consult_architecture_doc("git workflow") -> Commit rules
    - consult_architecture_doc("nix") -> Nix configuration

    Returns relevant documentation sections without token waste.
    """
    return _search_docs(topic)


@skill_command(
    name="knowledge_consult_language_expert",
    category="read",
    description="[Language Expert] Consult language-specific standards.",
)
async def consult_language_expert(file_path: str, task_description: str) -> str:
    """
    [Language Expert] Consult language-specific standards and code examples.

    This is the primary tool for Router-Augmented Coding:
    1. Reads L1a: Language standards (skills/knowledge/standards/lang-*.md)
    2. Queries L2: Case law (tool-router/data/examples/*.jsonl)

    Usage:
    - consult_language_expert(file_path="units/modules/python.nix", task="extend generator")

    Args:
        file_path: Path to the file being edited
        task_description: Description of the coding task

    Returns:
        JSON with language standards and matching examples
    """
    lang = _get_language_from_path(file_path)

    if not lang:
        return json.dumps(
            {
                "status": "skipped",
                "reason": f"No language expert for extension: {Path(file_path).suffix}",
                "supported_extensions": list(EXT_TO_LANG.keys()),
            },
            indent=2,
        )

    result = {
        "language": LANG_NAMES.get(lang, lang),
        "file": file_path,
        "task": task_description,
    }

    # Load Standards
    standard = _standards_cache.get_standard(lang)
    if standard:
        relevant_std = _extract_relevant_standards(standard, task_description)
        result["standards"] = relevant_std or standard[:500]
        result["standards_source"] = f"skills/knowledge/standards/lang-{lang}.md"
    else:
        result["standards"] = None
        result["standards_warning"] = f"No standards found for {lang}"

    return json.dumps(result, indent=2)


@skill_command(
    name="knowledge_get_language_standards",
    category="read",
    description="[Standards] Get language-specific coding standards.",
)
async def get_language_standards(lang: str) -> str:
    """
    [Standards] Get language-specific coding standards.

    Usage:
    - get_language_standards("nix") -> Nix formatting rules
    - get_language_standards("python") -> Python style guide

    Returns:
        JSON with full standards document from skills/knowledge/standards/lang-{lang}.md
    """
    lang = lang.lower()
    lang_name = LANG_NAMES.get(lang, lang.title())

    standard = _standards_cache.get_standard(lang)

    if not standard:
        return json.dumps(
            {
                "status": "not_found",
                "language": lang_name,
                "available_languages": list(LANG_NAMES.keys()),
            },
            indent=2,
        )

    return json.dumps(
        {
            "status": "success",
            "language": lang_name,
            "source": f"skills/knowledge/standards/lang-{lang}.md",
            "content": standard,
        },
        indent=2,
    )


@skill_command(
    name="knowledge_list_supported_languages",
    category="read",
    description="List all supported languages with their standards.",
)
async def list_supported_languages() -> str:
    """
    List all supported languages with their standards.

    Returns:
        JSON list of supported languages
    """
    languages = []
    # SSOT: Use SKILLS_DIR for path resolution
    skill_dir = SKILLS_DIR("knowledge")
    standards_dir = skill_dir / "standards"

    for lang_id, lang_name in LANG_NAMES.items():
        std_path = standards_dir / f"lang-{lang_id}.md"
        languages.append(
            {
                "id": lang_id,
                "name": lang_name,
                "standards_exists": std_path.exists(),
                "file_extensions": [k for k, v in EXT_TO_LANG.items() if v == lang_id],
            }
        )

    return json.dumps(
        {"status": "success", "languages": languages, "total": len(languages)}, indent=2
    )
