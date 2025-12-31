# mcp-server/writer.py
"""
DocuSmith - Writing Quality Tools

Tools for enforcing writing standards from design/writing-style/:
- lint_writing_style: Check for clutter words (Module 02 - Rosenberg)
- check_markdown_structure: Validate header hierarchy (Module 03)
- run_vale_check: Wrapper for Vale CLI linting

Usage:
    from mcp.server.fastmcp import FastMCP
    from .writer import register_writer_tools

    mcp = FastMCP("my-server")
    register_writer_tools(mcp)
"""
import asyncio
import json
import re
import subprocess
from typing import List, Dict, Any

# =============================================================================
# Constants from design/writing-style/02_mechanics.md
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

def _load_rules_from_file(file_path: str) -> Dict[str, str]:
    """Load clutter words from a JSON file (for extensibility)."""
    try:
        path = Path(file_path)
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return CLUTTER_WORDS


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
# MCP Tools
# =============================================================================

def register_writer_tools(mcp: Any) -> None:
    """Register all writer tools with the MCP server."""

    @mcp.tool()
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

    @mcp.tool()
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

    @mcp.tool()
    async def run_vale_check(file_path: str) -> str:
        """
        Run Vale CLI on a markdown file and return JSON results.

        Args:
            file_path: Path to the markdown file to lint

        Returns:
            JSON string with Vale linting results
        """
        import subprocess

        # Check if vale is available
        try:
            subprocess.run(
                ["vale", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return json.dumps({
                "status": "error",
                "message": "Vale CLI not found. Install with: brew install vale",
                "violations": [],
            })

        # Run vale in JSON format
        try:
            result = subprocess.run(
                ["vale", "--output=JSON", file_path],
                capture_output=True,
                text=True,
            )

            # Parse Vale JSON output
            if result.returncode == 0:
                vale_results = json.loads(result.stdout) if result.stdout else {}
            else:
                # Vale returns non-zero when errors found
                vale_results = json.loads(result.stdout) if result.stdout else {}

            # Extract files from Vale output
            violations = []
            for file_path_key, alerts in vale_results.items():
                for alert in alerts:
                    violations.append({
                        "type": "vale",
                        "file": file_path_key,
                        "line": alert.get("Line", 0),
                        "severity": alert.get("Severity", "info"),
                        "message": alert.get("Message", ""),
                        "check": alert.get("Check", ""),
                    })

            return json.dumps({
                "status": "success",
                "message": f"Vale found {len(violations)} issue(s)",
                "violations": violations,
            }, indent=2)

        except json.JSONDecodeError:
            return json.dumps({
                "status": "error",
                "message": "Failed to parse Vale output",
                "violations": [],
            })
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Vale error: {str(e)}",
                "violations": [],
            })


# =============================================================================
# Export
# =============================================================================

__all__ = ["register_writer_tools", "CLUTTER_WORDS", "lint_writing_style", "check_markdown_structure"]
