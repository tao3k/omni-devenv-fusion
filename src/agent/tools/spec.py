# agent/tools/spec.py
"""
Specification Management Tools

Provides spec drafting, verification, and archiving tools.

Tools:
- start_spec: Gatekeeper for new work
- draft_feature_spec: Draft new spec from description
- verify_spec_completeness: Review spec quality
- archive_spec_to_doc: Archive completed spec to docs
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in path
_project_root = Path(__file__).parent.parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server.fastmcp import FastMCP
from common.mcp_core import log_decision
from common.mcp_core.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)

# Path resolution
PROJECT_ROOT = get_project_root()
SPECS_DIR = PROJECT_ROOT / "agent/specs"
ARCHIVE_DIR = PROJECT_ROOT / "agent/specs.archive"


def register_spec_tools(mcp: FastMCP) -> None:
    """Register all specification management tools."""

    @mcp.tool()
    async def start_spec(name: str) -> str:
        """
        [Gatekeeper] Enforce spec exists before coding new work.

        This is the FIRST tool to call when you judge the user is requesting NEW work:
        - New feature or capability
        - Refactoring that changes public APIs
        - Any work that doesn't have an existing spec

        Phase 11 Enhancement: Uses PydanticAI-inspired type-safe output pattern.

        Args:
            name: Descriptive name for the new work (e.g. "user_authentication")

        Returns:
            JSON with status and guidance:
            - "allowed": Spec exists and is complete -> Proceed to coding
            - "blocked": Spec missing or incomplete -> Must create/update spec

        Examples:
            @omni-orchestrator start_spec(name="user_authentication")
            @omni-orchestrator start_spec(name="api_rate_limiting")
        """
        # Ensure specs directory exists
        SPECS_DIR.mkdir(parents=True, exist_ok=True)

        spec_path = SPECS_DIR / f"{name.replace(' ', '_')}.md"

        if spec_path.exists():
            spec_content = spec_path.read_text(encoding="utf-8")

            # Check if spec is complete (has implementation plan)
            if "## 3. Implementation Plan" in spec_content or "## Implementation" in spec_content:
                log_decision("spec.start.allowed", {"name": name}, logger)
                return json.dumps({
                    "status": "allowed",
                    "message": f"✅ Spec exists and is complete: {spec_path.name}",
                    "spec_path": str(spec_path),
                    "guidance": "Proceed to coding phase."
                })
            else:
                log_decision("spec.start.incomplete", {"name": name}, logger)
                return json.dumps({
                    "status": "blocked",
                    "message": f"⚠️ Spec exists but is incomplete: {spec_path.name}",
                    "spec_path": str(spec_path),
                    "guidance": "Fill in all required sections before proceeding."
                })
        else:
            log_decision("spec.start.missing", {"name": name}, logger)
            return json.dumps({
                "status": "blocked",
                "message": f"❌ No spec found for: {name}",
                "spec_path": str(spec_path),
                "guidance": "Create a spec using @omni-orchestrator draft_feature_spec before coding."
            })

    @mcp.tool()
    async def draft_feature_spec(
        title: str,
        description: str,
        context_files: Optional[list[str]] = None,
    ) -> str:
        """
        Draft a new Feature Spec based on agent/specs/TEMPLATE.md.

        Enforces project standards from agent/standards/.
        Uses LLM to fill out the template based on natural language description.

        Args:
            title: Short name of the feature (e.g. "auth_login_flow")
            description: Detailed description of what needs to be built
            context_files: Optional list of existing files to reference

        Returns:
            JSON with spec path and status
        """
        # Import here to avoid eager loading
        from mcp_core.inference import InferenceClient

        # Load template
        template_path = PROJECT_ROOT / "agent/specs/template.md"
        if not template_path.exists():
            return json.dumps({
                "success": False,
                "error": f"Template not found: {template_path}"
            })

        template = template_path.read_text(encoding="utf-8")

        # Generate spec content using LLM
        try:
            client = InferenceClient()
            context = ""
            if context_files:
                for cf in context_files or []:
                    cf_path = PROJECT_ROOT / cf
                    if cf_path.exists():
                        context += f"\n\n=== {cf} ===\n{cf_path.read_text(encoding='utf-8')}"

            prompt = f"""{description}

Context files:{context}

Please fill out the spec template below. Use the pattern from agent/standards/feature-lifecycle.md for complexity levels.

TEMPLATE:
{template}

Fill in all sections with appropriate detail. Return ONLY the filled template content."""

            spec_content = await client.complete(prompt=prompt, max_tokens=4000)

            # Clean up spec content
            # Remove template markers if present
            for marker in ["```markdown", "```", "---"]:
                if spec_content.startswith(marker):
                    spec_content = spec_content[len(marker):].strip()
                if marker in spec_content and spec_content.count(marker) >= 2:
                    # Remove all markdown code block markers
                    spec_content = spec_content.replace(marker, "")

            # Save spec
            safe_name = title.replace(" ", "_").lower()
            spec_path = SPECS_DIR / f"{safe_name}.md"
            spec_path.write_text(spec_content, encoding="utf-8")

            log_decision("spec.drafted", {"title": title, "path": str(spec_path)}, logger)

            return json.dumps({
                "success": True,
                "spec_path": str(spec_path),
                "message": f"✅ Spec drafted: {spec_path.name}"
            })

        except Exception as e:
            log_decision("spec.draft_failed", {"error": str(e)}, logger)
            return json.dumps({
                "success": False,
                "error": str(e)
            })

    @mcp.tool()
    async def verify_spec_completeness(spec_path: Optional[str] = None) -> str:
        """
        Review a Spec file to ensure it's ready for implementation.

        Checks for:
        1. Empty sections (TODOs)
        2. Missing test plans
        3. Vague interface definitions

        Args:
            spec_path: Path to the spec file. If not provided, auto-detects from start_spec.

        Returns:
            JSON with verification status and issues
        """
        # Auto-detect spec if not provided
        if not spec_path:
            # Try to find the most recent spec
            specs = sorted(SPECS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not specs:
                return json.dumps({
                    "success": False,
                    "error": "No specs found. Use start_spec first."
                })
            spec_path = str(specs[0])

        path = PROJECT_ROOT / spec_path
        if not path.exists():
            return json.dumps({
                "success": False,
                "error": f"Spec not found: {spec_path}"
            })

        content = path.read_text(encoding="utf-8")
        issues = []

        # Check for empty sections
        empty_sections = []
        import re
        section_pattern = r"^##\s+(.+)$"
        current_section = "Start"
        for line in content.split("\n"):
            match = re.match(section_pattern, line)
            if match:
                current_section = match.group(1)
            # Check for TODO placeholders
            if "TODO" in line or "[ ]" in line or "fill in" in line.lower():
                if current_section not in empty_sections:
                    empty_sections.append(current_section)

        if empty_sections:
            issues.append(f"Empty/incomplete sections: {', '.join(empty_sections)}")

        # Check for test plan
        if "## Test Plan" not in content and "## 4. Test Plan" not in content:
            if "## Testing" not in content and "## 5." not in content:
                issues.append("Missing Test Plan section")

        # Check for implementation details
        if "def " not in content and "class " not in content and "interface" not in content.lower():
            if "API" not in content and "endpoint" not in content.lower():
                issues.append("Vague interface - consider adding function/class definitions")

        # Determine status
        is_complete = len(issues) == 0
        status = "complete" if is_complete else "needs_work"

        result = {
            "success": True,
            "status": status,
            "spec_path": spec_path,
            "issues": issues,
            "message": "✅ Spec is complete and ready for implementation" if is_complete else f"⚠️ Spec needs work: {len(issues)} issue(s) found"
        }

        log_decision("spec.verified", {"spec_path": spec_path, "status": status}, logger)

        return json.dumps(result, indent=2)

    @mcp.tool()
    async def archive_spec_to_doc(
        spec_path: str,
        target_category: str = "explanation",
    ) -> str:
        """
        [Lifecycle Tool] Archives a completed Spec and converts it into permanent documentation.

        Use this when a feature is DONE (Code Merged + Tests Passed).

        Paths resolved from references.yaml.

        Args:
            spec_path: Path to the spec
            target_category: "explanation" (concepts), "reference" (APIs), or "how-to" (guides)

        Returns:
            JSON with archive status

        Examples:
            @omni-orchestrator archive_spec_to_doc(spec_path="agent/specs/auth_module.md")
        """
        # Validate target category
        valid_categories = ["explanation", "reference", "how-to"]
        if target_category not in valid_categories:
            return json.dumps({
                "success": False,
                "error": f"Invalid category: {target_category}. Valid: {valid_categories}"
            })

        src_path = PROJECT_ROOT / spec_path
        if not src_path.exists():
            return json.dumps({
                "success": False,
                "error": f"Spec not found: {spec_path}"
            })

        # Create archive directory
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        # Copy to archive
        archive_path = ARCHIVE_DIR / src_path.name
        content = src_path.read_text(encoding="utf-8")
        archive_path.write_text(content, encoding="utf-8")

        # Move to docs category
        docs_dir = PROJECT_ROOT / "docs" / target_category
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Convert filename to docs format
        docs_name = src_path.stem.replace("_", "-") + ".md"
        docs_path = docs_dir / docs_name

        # Add category header if needed
        if "category:" not in content.lower():
            category_header = f"""category: {target_category}

"""
            content = content.replace("---\n", f"---\n{category_header}", 1)

        docs_path.write_text(content, encoding="utf-8")

        # Remove original spec
        src_path.unlink()

        log_decision("spec.archived", {
            "from": str(src_path),
            "to": str(docs_path)
        }, logger)

        return json.dumps({
            "success": True,
            "archived_to": str(docs_path),
            "message": f"✅ Spec archived: {docs_path.name}"
        })

    log_decision("spec_tools.registered", {}, logger)
