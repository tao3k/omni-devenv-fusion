# common/mcp_core/writing.py
"""
Writing Quality Tools - Shared utilities for documentation linting.

This module provides writing quality checking functions that can be used
by any MCP server (executor, coder, etc.) for auto-checking on save.

Functions:
- lint_writing_style: Check for clutter words (Module 02 - Rosenberg)
- check_markdown_structure: Validate header hierarchy (Module 03)
- polish_text: Combined lint + structure check

Usage:
    from mcp_core.writing import polish_text

    # In save_file tool for auto-checking
    result = await polish_text(content)
"""
import asyncio
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


# =============================================================================
# WritingStyleCache - Singleton Cache for Writing Guidelines
# =============================================================================

class WritingStyleCache:
    """
    Singleton cache for writing style guidelines loaded from agent/writing-style/*.md

    Pattern: Follows GitRulesCache singleton pattern with lazy loading.
    Loaded once, reused across all polish_text calls.
    """
    _instance: Optional["WritingStyleCache"] = None
    _loaded: bool = False
    _guidelines: str = ""
    _guidelines_dict: Dict[str, str] = {}

    def __new__(cls) -> "WritingStyleCache":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not WritingStyleCache._loaded:
            self._load_styles()

    def _load_styles(self) -> None:
        """Load all writing style guidelines from agent/writing-style/*.md"""
        from .gitops import get_project_root
        project_root = get_project_root()
        style_dir = project_root / "agent" / "writing-style"

        if not style_dir.exists():
            WritingStyleCache._guidelines = ""
            WritingStyleCache._loaded = True
            return

        combined_content = []
        style_files = sorted(style_dir.glob("*.md"))

        for style_file in style_files:
            try:
                content = style_file.read_text(encoding="utf-8")
                # Extract title from first line (format: # Title)
                title_match = content.strip().split('\n')[0] if content.strip() else ""
                combined_content.append(f"\n--- {style_file.name} ---\n{content}")
            except Exception:
                continue

        WritingStyleCache._guidelines = "\n".join(combined_content)

        # Also build a dict for quick lookups
        for style_file in style_files:
            try:
                content = style_file.read_text(encoding="utf-8")
                WritingStyleCache._guidelines_dict[style_file.name] = content
            except Exception:
                continue

        WritingStyleCache._loaded = True

    @classmethod
    def get_guidelines(cls) -> str:
        """Get combined guidelines text for injection into polish_text."""
        if not cls._loaded:
            _ = cls()  # Ensure instance exists
            cls._instance._load_styles()
        return cls._guidelines

    @classmethod
    def get_guidelines_dict(cls) -> Dict[str, str]:
        """Get guidelines as dict for structured access."""
        if not cls._loaded:
            _ = cls()  # Ensure instance exists
            cls._instance._load_styles()
        return cls._guidelines_dict.copy()

    @classmethod
    def get_guidelines_for_prompt(cls) -> str:
        """
        Get formatted guidelines for LLM context injection.

        Returns concise bullet points for embedding in prompts.
        """
        if not cls._loaded:
            _ = cls()  # Ensure instance exists
        guidelines = cls.get_guidelines_dict()
        if not guidelines:
            return "No writing guidelines found."

        # Extract key rules from each file
        key_rules = []
        for filename, content in guidelines.items():
            # Extract headings and bullet points
            lines = content.split('\n')
            for line in lines:
                if line.startswith('## '):
                    key_rules.append(f"[{filename}] {line[3:]}")
                elif line.startswith('- ') and len(line) < 100:
                    key_rules.append(f"  {line}")

        return '\n'.join(key_rules[:20])  # Limit to top 20 rules

    @classmethod
    def reload(cls) -> None:
        """Force reload of guidelines (for testing)."""
        cls._loaded = False
        cls._guidelines = ""
        cls._guidelines_dict = {}
        cls._instance._load_styles()


# =============================================================================
# Constants from agent/writing-style/02_mechanics.md
# =============================================================================

CLUTTER_WORDS: Dict[str, str] = {
    r"\butilize\b": "use",
    r"\bfacilitate\b": "help",
    r"\bin order to\b": "to",
    r"\bat this point in time\b": "now",
    r"\bis capable of\b": "can",
    r"\bbasically\b": "[DELETE]",
    r"\bessentially\b": "[DELETE]",
    r"\bvery\b": "[DELETE]",
    r"\breally\b": "[DELETE]",
    r"\bfunctionality\b": "feature",
    r"\bcommence\b": "start",
    r"\bterminate\b": "end",
    r"\bimplement\b": "do",
    r"\bmodification\b": "change",
    r"\bsubsequently\b": "then",
    r"\baccordingly\b": "so",
    r"\bconsequently\b": "so",
    r"\bnevertheless\b": "but",
    r"\bnotwithstanding\b": "despite",
}

PASSIVE_VOICE_PATTERNS = [
    r"\b(is|are|was|were|be|been|being)\s+\w+ed\b",
    r"\b(has|have|had)\s+been\s+\w+ed\b",
]


# =============================================================================
# Helper Functions
# =============================================================================

def _check_passive_voice(line: str) -> List[str]:
    """Detect passive voice in a line."""
    violations = []
    for pattern in PASSIVE_VOICE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            # Extract the passive construction
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(match.group(0))
    return violations


# =============================================================================
# Core Functions (Async for MCP compatibility)
# =============================================================================

async def lint_writing_style(text: str) -> str:
    """
    Check text against Module 02 (Rosenberg Mechanics) style guide.

    Checks for:
    - Clutter words (utilize -> use, facilitate -> help)
    - Passive voice
    - Weak language (basically, essentially)

    Args:
        text: The text to lint

    Returns:
        JSON string with violations and suggestions
    """
    violations: List[Dict[str, Any]] = []
    lines = text.split('\n')

    for i, line in enumerate(lines, 1):
        line_num = i

        # 1. Check Clutter Words
        for pattern, replacement in CLUTTER_WORDS.items():
            matches = list(re.finditer(pattern, line, re.IGNORECASE))
            for match in matches:
                violations.append({
                    "type": "clutter_word",
                    "line": line_num,
                    "text": match.group(0),
                    "suggestion": replacement,
                    "rule": "02_mechanics.md - Strip Clutter",
                })

        # 2. Check Passive Voice
        passive_matches = _check_passive_voice(line)
        for pmatch in passive_matches:
            violations.append({
                "type": "passive_voice",
                "line": line_num,
                "text": pmatch,
                "suggestion": "Use Active Voice",
                "rule": "02_mechanics.md - Active Voice",
            })

        # 3. Check for weak language
        weak_patterns = [
            (r"\bbasically\b", "Delete or be specific"),
            (r"\bessentially\b", "Delete or be specific"),
            (r"\bvery\s+\w+", "Use stronger adjective"),
            (r"\breally\b", "Delete or be specific"),
        ]
        for pattern, suggestion in weak_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append({
                    "type": "weak_language",
                    "line": line_num,
                    "text": pattern.replace(r"\b", ""),
                    "suggestion": suggestion,
                    "rule": "02_mechanics.md - Strip Clutter",
                })

    # Build response
    if not violations:
        return json.dumps({
            "status": "clean",
            "message": "No mechanical style violations found.",
            "violations": [],
        })

    return json.dumps({
        "status": "violations",
        "message": f"Found {len(violations)} style violation(s)",
        "violations": violations,
    }, indent=2)


async def check_markdown_structure(text: str) -> str:
    """
    Check Markdown structure against Module 03 (Structure & AI).

    Checks for:
    - H1 uniqueness (only one # at top)
    - Hierarchy jumping (H2 -> H4 not allowed)
    - Code block labels (Input/Output style)
    - Proper spacing

    Args:
        text: The markdown text to check

    Returns:
        JSON string with structure violations
    """
    violations: List[Dict[str, Any]] = []
    lines = text.split('\n')
    header_levels: List[int] = []
    h1_count = 0
    in_code_block = False
    code_lang = None

    for i, line in enumerate(lines, 1):
        line_num = i

        # Track code blocks
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_lang = line.strip()[3:].strip() or None
                continue
            else:
                in_code_block = False
                code_lang = None
                continue

        # Check headers
        if line.startswith('#'):
            level = len(line.split(' ')[0])
            header_levels.append(level)

            # H1 check
            if level == 1:
                h1_count += 1
                if h1_count > 1:
                    violations.append({
                        "type": "multiple_h1",
                        "line": line_num,
                        "text": line.strip(),
                        "suggestion": "Use only one H1 per file",
                        "rule": "03_structure_and_ai.md - H1 Uniqueness",
                    })

            # Hierarchy jumping check
            if len(header_levels) >= 2:
                prev_level = header_levels[-2]
                if level > prev_level + 1:
                    violations.append({
                        "type": "hierarchy_jump",
                        "line": line_num,
                        "text": f"H{prev_level} -> H{level}",
                        "suggestion": f"Change to H{prev_level + 1} or lower",
                        "rule": "03_structure_and_ai.md - No Header Skipping",
                    })

        # Check for code block without language
        if in_code_block and not code_lang and not line.strip().startswith('//'):
            violations.append({
                "type": "code_without_lang",
                "line": line_num,
                "text": line[:50] + "..." if len(line) > 50 else line,
                "suggestion": "Add language tag to code block",
                "rule": "03_structure_and_ai.md - Code Labels",
            })

    # Build response
    if not violations:
        return json.dumps({
            "status": "clean",
            "message": "Markdown structure is valid.",
            "violations": [],
        })

    return json.dumps({
        "status": "violations",
        "message": f"Found {len(violations)} structure violation(s)",
        "violations": violations,
    }, indent=2)


async def polish_text(text: str) -> str:
    """
    Polish text using writing guidelines from agent/writing-style/.

    Combines lint_writing_style and check_markdown_structure checks.
    This is the primary function for auto-checking on save.

    Args:
        text: The text to polish

    Returns:
        JSON string with polished text and any style issues found
    """
    # Get guidelines for context injection
    guidelines = WritingStyleCache.get_guidelines_for_prompt()

    # Run both mechanical and structural checks
    lint_result = await lint_writing_style(text)
    structure_result = await check_markdown_structure(text)

    # Parse results
    lint_data = json.loads(lint_result)
    structure_data = json.loads(structure_result)

    all_violations = lint_data.get("violations", []) + structure_data.get("violations", [])

    return json.dumps({
        "status": "needs_polish" if all_violations else "clean",
        "message": f"Found {len(all_violations)} style issue(s) to address",
        "violations": all_violations,
        "guidelines_used": guidelines,
        "lint_violations": lint_data.get("violations", []),
        "structure_violations": structure_data.get("violations", []),
    }, indent=2)


# =============================================================================
# Singleton Instance for Eager Loading
# =============================================================================
_writing_style_cache = WritingStyleCache()


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "WritingStyleCache",
    "CLUTTER_WORDS",
    "lint_writing_style",
    "check_markdown_structure",
    "polish_text",
]
