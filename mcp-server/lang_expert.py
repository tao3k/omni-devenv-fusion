# mcp-server/lang_expert.py
"""
Language Expert System - Router-Augmented Coding

Implements "Static Standards (Law)" + "Dynamic Examples (Case Law)" pattern:

L1: Standards (agent/standards/lang-*.md) - Project-specific language conventions
L2: Examples (tool-router/data/examples/*.jsonl) - Concrete syntax patterns

Usage:
    @omni-orchestrator consult_language_expert file_path="units/modules/python.nix" task="extend generator"

Performance: Uses singleton caching for standards docs.
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

# =============================================================================
# Singleton Cache - Standards loaded once per MCP session
# =============================================================================

class StandardsCache:
    """
    Singleton cache for language standards.
    Standards are loaded from agent/standards/ on first access,
    then cached in memory for the lifetime of the MCP server.
    """
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not StandardsCache._loaded:
            self._load_standards()
            StandardsCache._loaded = True

    def _load_standards(self):
        """Load all language standards from agent/standards/."""
        self._standards = {}
        standards_dir = Path("agent/standards")

        if not standards_dir.exists():
            return

        # Load lang-*.md files
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

    def reload(self):
        """Force reload standards (for debugging/testing)."""
        self._load_standards()


# Global cache instance
_standards_cache = StandardsCache()


# =============================================================================
# Language Mapping
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


# =============================================================================
# Helper Functions
# =============================================================================

def get_language_from_path(file_path: str) -> Optional[str]:
    """Detect language from file extension."""
    path = Path(file_path)
    ext = path.suffix.lower()
    return EXT_TO_LANG.get(ext)


def search_examples(jsonl_path: Path, task_description: str, limit: int = 3) -> List[Dict]:
    """
    Search tool-router examples for relevant patterns.

    Uses simple keyword matching. Could be upgraded to semantic search.
    """
    matches = []

    if not jsonl_path.exists():
        return matches

    try:
        with open(jsonl_path, 'r') as f:
            task_lower = task_description.lower()

            for line in f:
                try:
                    entry = json.loads(line)

                    # Build searchable text from entry
                    search_text = " ".join([
                        entry.get("intent", ""),
                        entry.get("syntax_focus", ""),
                        entry.get("description", ""),
                    ]).lower()

                    # Keyword matching
                    task_words = set(re.findall(r'\w+', task_lower))
                    entry_words = set(re.findall(r'\w+', search_text))

                    # Calculate overlap
                    overlap = task_words & entry_words

                    # Score by overlap (ignore common words)
                    common = {"the", "a", "an", "to", "for", "in", "add", "file", "use"}
                    meaningful_overlap = overlap - common

                    if meaningful_overlap:
                        entry["_score"] = len(meaningful_overlap)
                        matches.append(entry)

                except json.JSONDecodeError:
                    continue

        # Sort by score and return top matches
        matches.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return matches[:limit]

    except Exception:
        return []


def format_examples(matches: List[Dict]) -> str:
    """Format matched examples for output."""
    if not matches:
        return ""

    formatted = ["\n### 💡 Relevant Examples (Case Law)"]

    for i, m in enumerate(matches, 1):
        formatted.append(f"\n**Case {i}:** {m.get('intent', 'Unknown')}")
        formatted.append(f"- **Syntax Focus:** {', '.join(m.get('syntax_focus', []))}")

        if m.get('do_not'):
            formatted.append(f"- **⚠️ DO NOT:** {'; '.join(m.get('do_not'))}")

        if m.get('allowed_edits'):
            edits = m.get('allowed_edits', [])
            formatted.append(f"- **✅ Allowed Edits:** {edits[0] if edits else 'See JSONL'}")

        if m.get('example'):
            formatted.append(f"\n```\n{m['example']}\n```")

    return "\n".join(formatted)


# =============================================================================
# MCP Tools
# =============================================================================

def register_lang_expert_tools(mcp: Any) -> None:
    """Register all language expert tools with the MCP server."""

    @mcp.tool()
    async def consult_language_expert(
        file_path: str,
        task_description: str
    ) -> str:
        """
        Consult language-specific standards and relevant code examples.

        This is the primary tool for Router-Augmented Coding:
        1. Reads L1: Project standards (agent/standards/lang-*.md)
        2. Queries L2: Case law (tool-router/data/examples/*.jsonl)

        Usage:
            @omni-orchestrator consult_language_expert file_path="units/modules/python.nix" task="extend generator"

        Returns:
            JSON with standards context and matching examples.
        """
        lang = get_language_from_path(file_path)

        if not lang:
            return json.dumps({
                "status": "skipped",
                "reason": f"No language expert for extension: {Path(file_path).suffix}",
                "supported_extensions": list(EXT_TO_LANG.keys())
            }, indent=2)

        result = {
            "language": LANG_NAMES.get(lang, lang),
            "file": file_path,
            "task": task_description,
            "sources": {
                "standards": f"agent/standards/lang-{lang}.md",
                "examples": f"tool-router/data/examples/{lang}.edit.jsonl"
            }
        }

        # L1: Load Standards
        standard = _standards_cache.get_standard(lang)
        if standard:
            # Extract relevant sections based on task
            relevant_std = _extract_relevant_standards(standard, task_description)
            result["standards"] = relevant_std
            result["standards_source"] = "agent/standards"
        else:
            result["standards"] = None
            result["standards_warning"] = f"No standards found for {lang}"

        # L2: Query Examples
        jsonl_path = Path(f"tool-router/data/examples/{lang}.edit.jsonl")
        examples = search_examples(jsonl_path, task_description)

        if examples:
            result["examples"] = format_examples(examples)
            result["examples_count"] = len(examples)
        else:
            result["examples"] = None
            result["examples_note"] = "No matching examples found in tool-router"

        # Summary
        has_content = result.get("standards") or result.get("examples")
        result["status"] = "complete" if has_content else "partial"

        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_language_standards(lang: str) -> str:
        """
        Get full standards document for a language.

        Args:
            lang: Language ID (nix, python, rust, julia)

        Returns:
            JSON with full standards document
        """
        lang = lang.lower()
        lang_name = LANG_NAMES.get(lang, lang.title())

        standard = _standards_cache.get_standard(lang)

        if not standard:
            return json.dumps({
                "status": "not_found",
                "language": lang_name,
                "available_languages": list(LANG_NAMES.keys())
            }, indent=2)

        return json.dumps({
            "status": "success",
            "language": lang_name,
            "source": f"agent/standards/lang-{lang}.md",
            "content": standard
        }, indent=2)

    @mcp.tool()
    async def list_supported_languages() -> str:
        """
        List all supported languages with their standards.

        Returns:
            JSON list of supported languages and their standard files
        """
        languages = []

        for lang_id, lang_name in LANG_NAMES.items():
            std_path = Path(f"agent/standards/lang-{lang_id}.md")
            jsonl_path = Path(f"tool-router/data/examples/{lang_id}.edit.jsonl")

            languages.append({
                "id": lang_id,
                "name": lang_name,
                "standards_exists": std_path.exists(),
                "examples_exists": jsonl_path.exists(),
                "file_extensions": [k for k, v in EXT_TO_LANG.items() if v == lang_id]
            })

        return json.dumps({
            "status": "success",
            "languages": languages,
            "total": len(languages)
        }, indent=2)


def _extract_relevant_standards(standard: str, task: str) -> str:
    """Extract standards sections relevant to the task."""
    # Simple keyword-based extraction
    task_words = set(re.findall(r'\w+', task.lower()))
    common_words = {"the", "a", "an", "to", "for", "in", "add", "file", "use", "code"}

    # Find sections that contain task-related keywords
    lines = standard.split('\n')
    relevant_lines = []
    in_relevant_section = False

    for line in lines:
        # Section headers are markdown headers
        if line.startswith('##'):
            # Check previous section for relevance
            if relevant_lines and len(relevant_lines) > 2:
                # Keep the section if it has task keywords
                section_text = ' '.join(relevant_lines).lower()
                overlap = task_words & set(re.findall(r'\w+', section_text)) - common_words
                if overlap:
                    relevant_lines.append(line)
                elif any(kw in section_text for kw in ["forbidden", "anti-pattern", "correct", "wrong"]):
                    # Always include anti-pattern sections
                    relevant_lines.append(line)
                else:
                    relevant_lines = [line]  # Start new section
            else:
                relevant_lines = [line]
        elif relevant_lines:
            relevant_lines.append(line)

    # Handle last section
    if relevant_lines:
        section_text = ' '.join(relevant_lines).lower()
        overlap = task_words & set(re.findall(r'\w+', section_text)) - common_words
        if not overlap and len(relevant_lines) < 5:
            return None

    return '\n'.join(relevant_lines[:30]) if relevant_lines else None


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "register_lang_expert_tools",
    "StandardsCache",
    "EXT_TO_LANG",
    "LANG_NAMES"
]
