"""
writer/scripts/text.py - Writer Skill Commands
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

import structlog

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.skills import SKILLS_DIR

logger = structlog.get_logger(__name__)


class WritingStyleCache:
    """
    Singleton cache for writing style guidelines loaded from skills/writer/writing-style/*.md
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
        skill_dir = SKILLS_DIR("writer")
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

        for style_file in style_files:
            try:
                content = style_file.read_text(encoding="utf-8")
                WritingStyleCache._guidelines_dict[style_file.name] = content
            except Exception:
                continue

        WritingStyleCache._loaded = True

    @classmethod
    def get_guidelines(cls) -> str:
        """Get combined guidelines text."""
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


def _check_passive_voice(line: str) -> List[str]:
    """Detect passive voice in a line."""
    violations = []
    for pattern in PASSIVE_VOICE_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                violations.append(match.group(0))
    return violations


@skill_command(
    name="lint_writing_style",
    category="read",
    description="""
    Checks text against Module 02 (Rosenberg Mechanics) style guide.

    Detects:
    - Clutter words (utilize -> use, facilitate -> help)
    - Passive voice usage
    - Weak language (basically, essentially, very)

    Args:
        text: The text content to check for style violations.

    Returns:
        JSON string with status (`clean` or `violations`), message,
        and list of violations with line numbers and suggestions.

    Example:
        @omni("writer.lint_writing_style", {"text": "This is basically very useful."})
    """,
)
async def lint_writing_style(text: str) -> str:
    violations: List[Dict[str, Any]] = []
    lines = text.split("\n")

    for i, line in enumerate(lines, 1):
        line_num = i

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


@skill_command(
    name="check_markdown_structure",
    category="read",
    description="""
    Checks Markdown structure against Module 03 (Structure & AI) style guide.

    Validates:
    - Single H1 per file
    - No header hierarchy jumps (e.g., H1 -> H3)
    - Code blocks with language tags

    Args:
        text: The markdown text to validate.

    Returns:
        JSON string with status (`clean` or `violations`), message,
        and list of structure violations.

    Example:
        @omni("writer.check_markdown_structure", {"text": "# Title\n## Sub"})
    """,
)
async def check_markdown_structure(text: str) -> str:
    violations: List[Dict[str, Any]] = []
    lines = text.split("\n")
    header_levels: List[int] = []
    h1_count = 0
    in_code_block = False
    code_lang = None

    for i, line in enumerate(lines, 1):
        line_num = i

        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lang = line.strip()[3:].strip() or None
                continue
            else:
                in_code_block = False
                code_lang = None
                continue

        if line.startswith("#"):
            level = len(line.split(" ")[0])
            header_levels.append(level)

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


@skill_command(
    name="polish_text",
    category="read",
    description="""
    Polishes text using writing guidelines.

    Combines lint_writing_style and check_markdown_structure checks
    to provide comprehensive writing feedback.

    Args:
        text: The text to polish and check.

    Returns:
        JSON string with status (`clean` or `needs_polish`),
        total violation count, and separate lint/structure violations.

    Example:
        @omni("writer.polish_text", {"text": "This is basically very active text."})
    """,
)
async def polish_text(text: str) -> str:
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
            "lint_violations": lint_data.get("violations", []),
            "structure_violations": structure_data.get("violations", []),
        },
        indent=2,
    )


@skill_command(
    name="load_writing_memory",
    category="read",
    description="""
    Loads writing guidelines into LLM context.

    Reads from skills/writer/writing-style/*.md and returns all guidelines
    as a single content string. Call this at the start of a writing task.

    Args:
        None

    Returns:
        JSON string with status (`loaded`), source path, files loaded count,
        and full guidelines content.
    """,
)
async def load_writing_memory() -> str:
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


@skill_command(
    name="run_vale_check",
    category="read",
    description="""
    Runs Vale CLI on a markdown file for professional writing checks.

    Args:
        file_path: Path to the markdown file to check.

    Returns:
        JSON string with status (`success`, `error`), message,
        and list of Vale violations with line, severity, and check name.

    Note:
        Requires Vale CLI to be installed (`brew install vale`).
    """,
)
async def run_vale_check(file_path: str) -> str:
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
