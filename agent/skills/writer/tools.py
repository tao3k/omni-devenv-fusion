"""
Writer Skill Tools

Writing quality enforcement. All rules are in prompts.md.
Python only executes - no business logic.

Philosophy: "Code is Mechanism, Prompt is Policy"
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

from mcp.server.fastmcp import FastMCP

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# WritingStyleCache - Singleton Cache for Writing Guidelines
# =============================================================================


class WritingStyleCache:
    """
    Singleton cache for writing style guidelines loaded from skills/writer/writing-style/*.md

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
        """Load all writing style guidelines from skills/writer/writing-style/*.md"""
        # Use Path traversal to find the skill directory
        skill_dir = Path(__file__).parent
        style_dir = skill_dir / "writing-style"

        if not style_dir.exists():
            WritingStyleCache._guidelines = ""
            WritingStyleCache._loaded = True
            return

        combined_content = []
        style_files = sorted(style_dir.glob("*.md"))

        for style_file in style_files:
            try:
                content = style_file.read_text(encoding="utf-8")
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
            _ = cls()
            cls._instance._load_styles()
        return cls._guidelines

    @classmethod
    def get_guidelines_dict(cls) -> Dict[str, str]:
        """Get guidelines as dict for structured access."""
        if not cls._loaded:
            _ = cls()
            cls._instance._load_styles()
        return cls._guidelines_dict.copy()

    @classmethod
    def get_guidelines_for_prompt(cls) -> str:
        """Get formatted guidelines for LLM context injection."""
        if not cls._loaded:
            _ = cls()
        guidelines = cls.get_guidelines_dict()
        if not guidelines:
            return "No writing guidelines found."

        key_rules = []
        for filename, content in guidelines.items():
            lines = content.split("\n")
            for line in lines:
                if line.startswith("## "):
                    key_rules.append(f"[{filename}] {line[3:]}")
                elif line.startswith("- ") and len(line) < 100:
                    key_rules.append(f"  {line}")

        return "\n".join(key_rules[:20])


# =============================================================================
# Constants from writing-style/02_mechanics.md
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
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(match.group(0))
    return violations


# =============================================================================
# Core Tools
# =============================================================================


async def lint_writing_style(text: str) -> str:
    """
    Check text against Module 02 (Rosenberg Mechanics) style guide.

    Rules (from prompts.md):
    - Strip clutter words (utilize -> use)
    - Use active voice
    - Avoid weak language

    Returns:
        JSON string with violations and suggestions
    """
    violations: List[Dict[str, Any]] = []
    lines = text.split("\n")

    for i, line in enumerate(lines, 1):
        line_num = i

        # Check Clutter Words
        for pattern, replacement in CLUTTER_WORDS.items():
            matches = list(re.finditer(pattern, line, re.IGNORECASE))
            for match in matches:
                violations.append(
                    {
                        "type": "clutter_word",
                        "line": line_num,
                        "text": match.group(0),
                        "suggestion": replacement,
                        "rule": "02_mechanics.md - Strip Clutter",
                    }
                )

        # Check Passive Voice
        passive_matches = _check_passive_voice(line)
        for pmatch in passive_matches:
            violations.append(
                {
                    "type": "passive_voice",
                    "line": line_num,
                    "text": pmatch,
                    "suggestion": "Use Active Voice",
                    "rule": "02_mechanics.md - Active Voice",
                }
            )

        # Check weak language
        weak_patterns = [
            (r"\bbasically\b", "Delete or be specific"),
            (r"\bessentially\b", "Delete or be specific"),
            (r"\bvery\s+\w+", "Use stronger adjective"),
            (r"\breally\b", "Delete or be specific"),
        ]
        for pattern, suggestion in weak_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append(
                    {
                        "type": "weak_language",
                        "line": line_num,
                        "text": pattern.replace(r"\b", ""),
                        "suggestion": suggestion,
                        "rule": "02_mechanics.md - Strip Clutter",
                    }
                )

    if not violations:
        return json.dumps(
            {
                "status": "clean",
                "message": "No mechanical style violations found.",
                "violations": [],
            }
        )

    return json.dumps(
        {
            "status": "violations",
            "message": f"Found {len(violations)} style violation(s)",
            "violations": violations,
        },
        indent=2,
    )


async def check_markdown_structure(text: str) -> str:
    """
    Check Markdown structure against Module 03 (Structure & AI).

    Rules (from prompts.md):
    - H1 uniqueness (only one # at top)
    - No hierarchy jumping (H2 -> H4 not allowed)
    - Code blocks need language tags
    - Proper spacing

    Returns:
        JSON string with structure violations
    """
    violations: List[Dict[str, Any]] = []
    lines = text.split("\n")
    header_levels: List[int] = []
    h1_count = 0
    in_code_block = False
    code_lang = None

    for i, line in enumerate(lines, 1):
        line_num = i

        # Track code blocks
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line.strip()[3:].strip() or None
                continue
            else:
                in_code_block = False
                code_lang = None
                continue

        # Check headers
        if line.startswith("#"):
            level = len(line.split(" ")[0])
            header_levels.append(level)

            # H1 check
            if level == 1:
                h1_count += 1
                if h1_count > 1:
                    violations.append(
                        {
                            "type": "multiple_h1",
                            "line": line_num,
                            "text": line.strip(),
                            "suggestion": "Use only one H1 per file",
                            "rule": "03_structure_and_ai.md - H1 Uniqueness",
                        }
                    )

            # Hierarchy jumping check
            if len(header_levels) >= 2:
                prev_level = header_levels[-2]
                if level > prev_level + 1:
                    violations.append(
                        {
                            "type": "hierarchy_jump",
                            "line": line_num,
                            "text": f"H{prev_level} -> H{level}",
                            "suggestion": f"Change to H{prev_level + 1} or lower",
                            "rule": "03_structure_and_ai.md - No Header Skipping",
                        }
                    )

        # Check code block without language
        if in_code_block and not code_lang and not line.strip().startswith("//"):
            violations.append(
                {
                    "type": "code_without_lang",
                    "line": line_num,
                    "text": line[:50] + "..." if len(line) > 50 else line,
                    "suggestion": "Add language tag to code block",
                    "rule": "03_structure_and_ai.md - Code Labels",
                }
            )

    if not violations:
        return json.dumps(
            {
                "status": "clean",
                "message": "Markdown structure is valid.",
                "violations": [],
            }
        )

    return json.dumps(
        {
            "status": "violations",
            "message": f"Found {len(violations)} structure violation(s)",
            "violations": violations,
        },
        indent=2,
    )


async def polish_text(text: str) -> str:
    """
    Polish text using writing guidelines from skills/writer/writing-style/.

    Combines lint_writing_style and check_markdown_structure.
    This is the primary function for auto-checking on save.

    Returns:
        JSON string with polished text and any style issues found
    """
    guidelines = WritingStyleCache.get_guidelines_for_prompt()
    lint_result = await lint_writing_style(text)
    structure_result = await check_markdown_structure(text)

    lint_data = json.loads(lint_result)
    structure_data = json.loads(structure_result)

    all_violations = lint_data.get("violations", []) + structure_data.get("violations", [])

    return json.dumps(
        {
            "status": "needs_polish" if all_violations else "clean",
            "message": f"Found {len(all_violations)} style issue(s) to address",
            "violations": all_violations,
            "guidelines_used": guidelines,
            "lint_violations": lint_data.get("violations", []),
            "structure_violations": structure_data.get("violations", []),
        },
        indent=2,
    )


async def load_writing_memory() -> str:
    """
    Load writing guidelines into LLM context.

    Reads from skills/writer/writing-style/*.md
    Call this at the start of a writing task.

    Returns:
        JSON with writing guidelines
    """
    guidelines_dict = WritingStyleCache.get_guidelines_dict()
    full_content = "\n\n".join(guidelines_dict.values())

    return json.dumps(
        {
            "status": "loaded",
            "source": "skills/writer/writing-style/*.md",
            "files_loaded": list(guidelines_dict.keys()),
            "total_files": len(guidelines_dict),
            "content": full_content,
            "note": "Full writing guidelines loaded into context. Apply these rules.",
        },
        indent=2,
    )


async def run_vale_check(file_path: str) -> str:
    """
    Run Vale CLI on a markdown file.

    Args:
        file_path: Path to the markdown file

    Returns:
        JSON string with Vale linting results
    """
    try:
        subprocess.run(["vale", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return json.dumps(
            {
                "status": "error",
                "message": "Vale CLI not found. Install with: brew install vale",
                "violations": [],
            }
        )

    try:
        result = subprocess.run(
            ["vale", "--output=JSON", file_path],
            capture_output=True,
            text=True,
        )

        vale_results = json.loads(result.stdout) if result.stdout else {}

        violations = []
        for file_path_key, alerts in vale_results.items():
            for alert in alerts:
                violations.append(
                    {
                        "type": "vale",
                        "file": file_path_key,
                        "line": alert.get("Line", 0),
                        "severity": alert.get("Severity", "info"),
                        "message": alert.get("Message", ""),
                        "check": alert.get("Check", ""),
                    }
                )

        return json.dumps(
            {
                "status": "success",
                "message": f"Vale found {len(violations)} issue(s)",
                "violations": violations,
            },
            indent=2,
        )

    except json.JSONDecodeError:
        return json.dumps(
            {
                "status": "error",
                "message": "Failed to parse Vale output",
                "violations": [],
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "message": f"Vale error: {str(e)}",
                "violations": [],
            }
        )


# =============================================================================
# Registration
# =============================================================================


def register(mcp: FastMCP):
    """Register Writer skill tools."""

    @mcp.tool()
    async def lint_writing_style_tool(text: str) -> str:
        return await lint_writing_style(text)

    @mcp.tool()
    async def check_markdown_structure_tool(text: str) -> str:
        return await check_markdown_structure(text)

    @mcp.tool()
    async def polish_text_tool(text: str) -> str:
        return await polish_text(text)

    @mcp.tool()
    async def load_writing_memory_tool() -> str:
        return await load_writing_memory()

    @mcp.tool()
    async def run_vale_check_tool(file_path: str) -> str:
        return await run_vale_check(file_path)

    logger.info("Writer skill tools registered")
