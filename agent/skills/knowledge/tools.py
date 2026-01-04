"""
knowledge Skill - The Project Cortex

Role:
  Does NOT execute commands.
  Does NOT edit files.
  ONLY reads project constraints, rules, and status to "enlighten" the LLM.

Philosophy:
  "Knowledge is power." This skill fetches that knowledge.

Rules (from prompts.md):
  - Call get_development_context() BEFORE writing code or committing
  - Call consult_architecture_doc() when you need to understand a topic
  - Return structured data, never execute operations
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def register(mcp: Any) -> None:
    """Register all knowledge tools."""

    @mcp.tool()
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
                "types": ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore"],
                "scopes": _load_scopes(),
                "message_format": "<type>(<scope>): <description>",
                "policy": "Conventional Commits + Atomic Steps"
            },
            "guardrails": _analyze_lefthook(),
            "writing_style": _get_writing_style(),
            "architecture": _get_architecture_summary()
        }
        return json.dumps(context, indent=2)

    @mcp.tool()
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

    @mcp.tool()
    async def get_writing_memory() -> str:
        """
        [Memory] Loads the project's writing style guide.

        Call this BEFORE:
        - Writing documentation
        - Editing markdown files
        - Creating commit messages

        Returns structured writing rules from agent/writing-style/
        """
        rules = {
            "commit_messages": _read_file_content("agent/writing-style/02_mechanics.md"),
            "writing_principles": _read_file_content("agent/writing-style/01_principles.md"),
            "style_checklist": [
                "Use English only for commits and docs",
                "Prefer active voice",
                "Keep sentences under 25 words",
                "Use lists sparingly (4 items max)",
                "Code is mechanism, prompt is policy"
            ]
        }
        return json.dumps(rules, indent=2)

    @mcp.tool()
    async def get_language_standards(lang: str) -> str:
        """
        [Standards] Get language-specific coding standards.

        Usage:
        - get_language_standards("nix") -> Nix formatting rules
        - get_language_standards("python") -> Python style guide
        - get_language_standards("markdown") -> Doc formatting rules
        """
        lang_file = f"agent/standards/lang-{lang}.md"
        content = _read_file_content(lang_file)
        if content:
            return content
        return f"No specific standards found for '{lang}'. Check agent/standards/ for available languages."


# ============================================================================
# Internal Helpers (Pure Execution - No Business Logic)
# ============================================================================

def _get_project_name() -> str:
    """Extract project name from pyproject.toml."""
    pyproject = Path.cwd() / "pyproject.toml"
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
    try:
        if (Path.cwd() / "cog.toml").exists():
            with open("cog.toml", "rb") as f:
                data = tomllib.load(f)
                return data.get("scopes", [])
    except Exception:
        pass
    return ["core"]  # Fallback


def _analyze_lefthook() -> List[Dict[str, str]]:
    """Analyze lefthook configuration to determine active guardrails."""
    hooks = []

    lefthook_nix = Path.cwd() / "units" / "modules" / "lefthook.nix"
    if lefthook_nix.exists():
        try:
            content = lefthook_nix.read_text()
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
        "list_max_items": 4
    }


def _get_architecture_summary() -> Dict[str, str]:
    """Get high-level architecture description."""
    return {
        "pattern": "Skill-Centric Architecture",
        "mcp_servers": ["orchestrator", "coder"],
        "key_directories": {
            "agent/": "LLM context (how-to, standards, specs)",
            "agent/skills/": "Skill modules",
            "docs/": "User documentation",
            "packages/": "Python packages"
        }
    }


def _search_docs(topic: str) -> str:
    """Search documentation for a topic."""
    docs_dir = Path.cwd() / "docs"
    if not docs_dir.exists():
        return f"No docs directory found for topic '{topic}'."

    topic_lower = topic.lower().replace(" ", "-").replace("_", "-")
    matches = []

    for md_file in docs_dir.rglob("*.md"):
        if topic_lower in md_file.name.lower():
            content = _read_file_content(str(md_file))
            if content:
                # Extract first 1000 chars for relevance check
                matches.append(f"=== {md_file.relative_to(Path.cwd())} ===\n{content[:1000]}...")

    if not matches:
        # Try searching in agent/ directory
        agent_dir = Path.cwd() / "agent"
        for md_file in agent_dir.rglob("*.md"):
            if topic_lower in md_file.name.lower() or topic_lower in md_file.read_text().lower()[:2000]:
                content = _read_file_content(str(md_file))
                if content:
                    matches.append(f"=== {md_file.relative_to(Path.cwd())} ===\n{content[:1000]}...")

    if matches:
        return f"\n\n---\n\n".join(matches[:3])  # Limit to 3 results

    return f"No documentation found for '{topic}'. Try: 'git', 'nix', 'writing', 'architecture'"


def _read_file_content(path: str) -> str:
    """Read file content safely."""
    try:
        file_path = Path.cwd() / path
        if file_path.exists():
            return file_path.read_text().strip()
    except Exception:
        pass
    return ""
