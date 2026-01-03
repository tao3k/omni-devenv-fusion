# mcp-server/reviewer.py
"""
Reviewer MCP Server - The "Immune System"

Responsible for code quality assurance BEFORE functionality testing.
It acts as a Tech Lead, enforcing style, security, and maintainability.

Tools:
- review_staged_changes: AI-powered code review of staged files against project standards.
"""
import asyncio
import subprocess
from pathlib import Path
from typing import Any, List

from common.mcp_core import log_decision, InferenceClient, setup_logging

logger = setup_logging(server_name="reviewer")

# =============================================================================
# Standards Loader (Local Helper)
# =============================================================================


def _scan_standards(file_extensions: List[str]) -> str:
    """
    Load relevant standards based on file extensions in the diff.
    e.g., if .py files changed, load lang-python.md
    Path resolved from references.yaml.
    """
    from common.mcp_core.reference_library import get_reference_path
    from common.mcp_core.gitops import get_project_root

    standards_dir = get_project_root() / get_reference_path("standards.dir")
    if not standards_dir.exists():
        return "No specific standards found."

    context = []

    # Global Standards
    if (standards_dir / "feature-lifecycle.md").exists():
        context.append(f"=== LIFECYCLE STANDARDS ===\n{(standards_dir / 'feature-lifecycle.md').read_text()}")

    # Language Specific Standards
    lang_map = {
        ".py": "lang-python.md",
        ".nix": "lang-nix.md",
        ".rs": "lang-rust.md",
        ".jl": "lang-julia.md"
    }

    # Dedupe needed standards
    needed_docs = set()
    for ext in file_extensions:
        if ext in lang_map:
            needed_docs.add(lang_map[ext])

    for doc in needed_docs:
        fpath = standards_dir / doc
        if fpath.exists():
            context.append(f"=== {doc.upper()} ===\n{fpath.read_text()}")

    return "\n\n".join(context)


def _get_staged_diff() -> tuple[str, List[str]]:
    """Get git diff --cached and list of changed extensions."""
    # Get content
    diff_proc = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True)
    diff = diff_proc.stdout.strip()

    # Get file names to determine extensions
    name_proc = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)
    files = name_proc.stdout.strip().split('\n')
    extensions = [Path(f).suffix for f in files if f]

    return diff, extensions


# =============================================================================
# MCP Tools
# =============================================================================


def register_reviewer_tools(mcp: Any) -> None:
    """Register reviewer tools with the MCP server."""

    @mcp.tool()
    async def review_staged_changes() -> str:
        """
        [Quality Gate] Performs a Tech Lead level code review on staged changes.

        Call this BEFORE running tests or committing.
        It checks for:
        1. Alignment with agent/standards/*
        2. Code Smells (Complexity, Naming, duplication)
        3. Security vulnerabilities
        4. Missing comments/docs
        """
        diff, extensions = _get_staged_diff()

        if not diff:
            return "No staged changes to review."

        # 1. Load Standards
        standards = _scan_standards(extensions)

        # 2. Prepare Context
        log_decision("review.start", {"files": len(extensions)}, logger)

        # 3. Consult AI
        client = InferenceClient()

        system_prompt = f"""You are the strict Tech Lead of this project.
Your job is to review the following Code Diff against the Project Standards.

--- STANDARDS ---
{standards}
--- END STANDARDS ---

CRITERIA:
1. **Style**: Does it follow the language standards provided?
2. **Safety**: Are there security risks?
3. **Clarity**: Are names descriptive? Is logic overly complex?
4. **Docs**: Are docstrings/comments present?

OUTPUT FORMAT:
- If PASS: Start with "APPROVE" followed by a brief summary.
- If FAIL: Start with "REQUEST CHANGES" followed by a bulleted list of specific issues (reference line numbers if possible).
"""

        user_prompt = f"""Review this diff:

```diff
{diff[:6000]}
```

(Diff truncated to last 6000 chars if too long)
"""

        result = await client.complete(system_prompt, user_prompt)

        if not result["success"]:
            return f"Error reviewing code: {result['error']}"

        review_content = result["content"]

        # Log result
        status = "approved" if "APPROVE" in review_content else "rejected"
        log_decision(f"review.{status}", {}, logger)

        return f"""--- The Immune System (Code Review) ---

{review_content}

---

**Guidance**:
* If REQUEST CHANGES: Use `coder` tools to fix the issues, then `git add`, then review again.
* If APPROVE: Proceed to `run_tests` or `smart_commit`.
"""
