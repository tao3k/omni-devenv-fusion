# mcp-server/product_owner.py
"""
Product Owner - Feature Lifecycle Integrity Enforcement & Spec Management

Tools for enforcing agent/standards/feature-lifecycle.md and Spec-Driven Development:
- assess_feature_complexity: LLM-powered complexity assessment (L1-L4)
- draft_feature_spec: Create a structured implementation plan from a description
- verify_spec_completeness: Ensure spec is ready for coding (auto-detects from start_spec)
- verify_design_alignment: Check alignment with design/roadmap/philosophy
- get_feature_requirements: Return complete requirements for a feature
- check_doc_sync: Verify docs are updated with code changes

Usage:
    @omni-orchestrator assess_feature_complexity code_diff="..." files_changed=[...]
    @omni-orchestrator draft_feature_spec title="..." description="..."
    @omni-orchestrator verify_spec_completeness  # Auto-detects spec_path from start_spec

Performance: Uses singleton caching - design docs loaded once per session.
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

# Import project_memory for spec_path auto-detection
from mcp_core.memory import ProjectMemory

# =============================================================================
# Singleton Cache - Design docs loaded once per MCP session
# =============================================================================

class DesignDocsCache:
    """
    Singleton cache for design documents.
    Design docs are loaded from design/ directory on first access,
    then cached in memory for the lifetime of the MCP server.
    """
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not DesignDocsCache._loaded:
            self._load_design_docs()
            DesignDocsCache._loaded = True

    def _load_design_docs(self):
        """Load design documents from design/ directory."""
        self._docs = {}

        design_dir = Path("design")
        if not design_dir.exists():
            return

        # Load key design documents
        key_docs = [
            "writing-style/01_philosophy",
            "mcp-architecture-roadmap",
            "why-custom-mcp-architecture"
        ]

        for doc_name in key_docs:
            doc_path = design_dir / f"{doc_name}.md"
            if doc_path.exists():
                try:
                    self._docs[doc_name] = doc_path.read_text()
                except Exception:
                    pass

    def get_doc(self, doc_name: str) -> str:
        """Get a design document by name (without extension)."""
        return self._docs.get(doc_name, "")

    def get_all_docs(self) -> Dict[str, str]:
        """Get all loaded design documents."""
        return self._docs.copy()

    def reload(self):
        """Force reload design docs (for debugging/testing)."""
        self._load_design_docs()


# Global cache instance
_design_cache = DesignDocsCache()


# =============================================================================
# Constants from feature-lifecycle.md
# =============================================================================

COMPLEXITY_LEVELS = {
    "L1": {
        "name": "Trivial",
        "definition": "Typos, config tweaks, doc updates",
        "tests": "None (linting only)",
        "examples": "Fix typo, update README, change comment"
    },
    "L2": {
        "name": "Minor",
        "definition": "New utility function, minor tweak",
        "tests": "Unit Tests",
        "examples": "Add helper function, refactor internal method"
    },
    "L3": {
        "name": "Major",
        "definition": "New module, API, or DB schema change",
        "tests": "Unit + Integration Tests",
        "examples": "New MCP tool, add API endpoint, DB migration"
    },
    "L4": {
        "name": "Critical",
        "definition": "Core logic, Auth, Payments, breaking changes",
        "tests": "Unit + Integration + E2E Tests",
        "examples": "Auth system, breaking API changes, security fixes"
    }
}

TEST_REQUIREMENTS = {
    "L1": "just lint (no test needed)",
    "L2": "just test-unit",
    "L3": "just test-unit && just test-int",
    "L4": "just test-unit && just test-int && manual E2E"
}

# Files that indicate critical functionality
CRITICAL_PATTERNS = [
    "auth", "login", "password", "credential",
    "payment", "billing", "subscription",
    "security", "encryption", "token",
    "breaking", "migration", "schema"
]

# =============================================================================
# Helper Functions
# =============================================================================

def get_git_diff(staged: bool = True) -> str:
    """Get git diff for analysis."""
    try:
        cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except Exception:
        return ""


def get_changed_files() -> List[str]:
    """Get list of changed files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except Exception:
        return []


def load_design_doc(filename: str) -> str:
    """Load a design document (uses cache for performance)."""
    # Remove .md extension if present
    if filename.endswith('.md'):
        filename = filename[:-3]
    return _design_cache.get_doc(filename)


def heuristic_complexity(files: List[str], diff: str) -> str:
    """
    Fast heuristic-based complexity assessment.
    Used as fallback when LLM is unavailable or as quick check.
    """
    files_str = " ".join(files).lower() + " " + diff.lower()

    # Check for critical patterns (L4)
    for pattern in CRITICAL_PATTERNS:
        if pattern in files_str:
            return "L4"

    # Check for new MCP tools (L3)
    if any("mcp-server/" in f for f in files) and "test" not in files_str:
        return "L3"

    # Check for new modules (L3)
    if any(f.startswith("units/modules/") or f.startswith("mcp-server/") for f in files):
        if len(diff.split('\n')) > 50:
            return "L3"

    # Check for documentation only (L1)
    if all(f.endswith('.md') or f.startswith('agent/') for f in files):
        return "L1"

    # Check for nix config changes (L2-L3)
    if any(f.endswith('.nix') for f in files):
        return "L2"

    # Check for general code changes (L2)
    if any(f.endswith('.py') for f in files):
        return "L2"

    return "L2"  # Default to L2


# =============================================================================
# Spec Management Functions
# =============================================================================

def _load_spec_template() -> str:
    """Load the Spec template."""
    template_path = Path("agent/specs/TEMPLATE.md")
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return "# Spec: {FEATURE_NAME}\n\n## Context\n...\n## Plan\n..."


def _save_spec(title: str, content: str) -> str:
    """Save a spec file to agent/specs/."""
    filename = title.lower().replace(" ", "_").replace("/", "-") + ".md"
    path = Path("agent/specs") / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _scan_standards() -> str:
    """
    Load all markdown standards from agent/standards/.
    Returns a formatted string context for the LLM.
    """
    standards_dir = Path("agent/standards")
    if not standards_dir.exists():
        return "No specific standards found."

    context = []
    # Priority standards
    priority_files = ["feature-lifecycle.md", "lang-python.md", "lang-nix.md"]

    for fname in priority_files:
        fpath = standards_dir / fname
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            context.append(f"=== STANDARD: {fname} ===\n{content}\n")

    return "\n".join(context) if context else "No standards found."


def _check_spec_completeness(content: str) -> List[str]:
    """Static check for common spec completeness issues."""
    issues = []

    # Check for template placeholders
    if "[ ] Step 1: ..." in content:
        issues.append("Implementation Plan contains template placeholders")
    if "function_name(arg: Type)" in content:
        issues.append("API Signatures contain template placeholders")
    if "{FEATURE_NAME}" in content:
        issues.append("Template placeholder {FEATURE_NAME} not replaced")

    # Check for required sections
    if "## 1. Context & Goal" not in content and "## Context" not in content:
        issues.append("Missing Context section")
    if "## 2. Architecture" not in content and "## Interface" not in content:
        issues.append("Missing Architecture/Interface section")
    if "## 3. Implementation" not in content and "## Plan" not in content:
        issues.append("Missing Implementation Plan section")
    if "## 4. Verification" not in content and "## Test" not in content:
        issues.append("Missing Verification Plan section")

    # Check for meaningful content
    lines = [l for l in content.split('\n') if l.strip() and not l.strip().startswith('>')]
    if len(lines) < 10:
        issues.append("Spec appears too short - missing detail")

    return issues


# =============================================================================
# MCP Tools
# =============================================================================

def register_product_owner_tools(mcp: Any) -> None:
    """Register all product owner tools with the MCP server."""

    @mcp.tool()
    async def assess_feature_complexity(
        code_diff: str = "",
        files_changed: List[str] = None,
        feature_description: str = ""
    ) -> str:
        """
        Assess feature complexity level (L1-L4) using LLM analysis.

        Analyzes the proposed changes and returns the Required Testing Level
        based on agent/standards/feature-lifecycle.md.

        Args:
            code_diff: Git diff or code changes to analyze
            files_changed: List of files that will be modified
            feature_description: Natural language description of the feature

        Returns:
            JSON with complexity level, test requirements, and rationale
        """
        files_changed = files_changed or []
        diff = code_diff or get_git_diff()

        # Check for API key availability
        api_key = None
        try:
            from mcp_core import InferenceClient
            api_key = InferenceClient(api_key="", base_url="").api_key
        except Exception:
            pass

        # Try LLM analysis if API key available
        if api_key or feature_description:
            try:
                from mcp_core import InferenceClient

                inference = InferenceClient(
                    api_key=api_key or "",
                    base_url="https://api.minimax.io/anthropic"
                )

                prompt = f"""Analyze the following code changes for complexity classification.

Feature Description: {feature_description}
Files Changed: {', '.join(files_changed) if files_changed else 'N/A'}
Code Diff: {diff[:3000]}...

Classify complexity (L1-L4) based on agent/standards/feature-lifecycle.md:
- L1 (Trivial): Typos, config tweaks, doc updates
- L2 (Minor): Utility function, minor tweak
- L3 (Major): New module, API, DB schema change
- L4 (Critical): Auth, Payments, breaking changes

Return JSON with:
{{"level": "L1-L4", "name": "Complexity name", "rationale": "Why this level", "test_requirements": "Required tests"}}
"""

                result = await inference.complete(
                    prompt=prompt,
                    system_prompt="You are a software architect. Analyze code changes and classify complexity. Return only valid JSON.",
                    max_tokens=500
                )

                # Try to parse LLM response
                try:
                    llm_result = json.loads(result.content)
                    level = llm_result.get("level", "L2")
                    # Validate level
                    if level not in ["L1", "L2", "L3", "L4"]:
                        level = "L2"
                except (json.JSONDecodeError, AttributeError):
                    level = "L2"

            except Exception as e:
                # Fallback to heuristics on error
                level = heuristic_complexity(files_changed, diff)
        else:
            # Use heuristics only
            level = heuristic_complexity(files_changed, diff)

        # Get level details
        level_info = COMPLEXITY_LEVELS.get(level, COMPLEXITY_LEVELS["L2"])
        test_req = TEST_REQUIREMENTS.get(level, "just test")

        return json.dumps({
            "level": level,
            "name": level_info["name"],
            "definition": level_info["definition"],
            "test_requirements": test_req,
            "examples": level_info["examples"],
            "rationale": f"Based on {len(files_changed)} file(s) changed and diff analysis",
            "reference": "agent/standards/feature-lifecycle.md"
        }, indent=2)

    @mcp.tool()
    async def verify_design_alignment(
        feature_description: str,
        check_philosophy: bool = True,
        check_roadmap: bool = True,
        check_architecture: bool = True
    ) -> str:
        """
        Verify feature alignment with design documents.

        Checks if the feature aligns with:
        - Philosophy (design/writing-style/01_philosophy.md)
        - Roadmap (design/*.md)
        - Architecture (design/mcp-architecture-roadmap.md)

        Args:
            feature_description: Description of the feature to verify
            check_philosophy: Check alignment with writing philosophy
            check_roadmap: Check if in roadmap
            check_architecture: Check architecture fit

        Returns:
            JSON with alignment status and references
        """
        results = {
            "philosophy": {"aligned": True, "notes": []},
            "roadmap": {"aligned": True, "in_roadmap": None, "notes": []},
            "architecture": {"aligned": True, "notes": []}
        }

        # Check philosophy
        if check_philosophy:
            philosophy = load_design_doc("writing-style/01_philosophy.md")
            if philosophy:
                # Quick heuristic check
                desc_lower = feature_description.lower()
                anti_patterns = ["overcomplicated", "unnecessary", "complex"]
                if any(p in desc_lower for p in anti_patterns):
                    results["philosophy"]["aligned"] = False
                    results["philosophy"]["notes"].append("Feature description suggests complexity")

        # Check roadmap
        if check_roadmap:
            # Look for roadmap files
            roadmap_files = list(Path("design").glob("*roadmap*")) + list(Path("design").glob("*vision*"))
            in_roadmap = False
            for rf in roadmap_files:
                content = rf.read_text().lower()
                if feature_description.lower() in content or any(kw in content for kw in feature_description.lower().split()[:3]):
                    in_roadmap = True
                    break
            results["roadmap"]["in_roadmap"] = in_roadmap
            if not in_roadmap:
                results["roadmap"]["aligned"] = False
                results["roadmap"]["notes"].append("Feature not explicitly in roadmap - consider updating design/")

        # Check architecture
        if check_architecture:
            architecture = load_design_doc("mcp-architecture-roadmap.md")
            if architecture:
                # Check for architecture conflicts
                desc_lower = feature_description.lower()
                if "dual" in desc_lower or "orchestrator" in desc_lower or "coder" in desc_lower:
                    if "orchestrator" in desc_lower and "mcp-server/orchestrator.py" not in " ".join([]):
                        results["architecture"]["notes"].append("Orchestrator features should be in mcp-server/orchestrator.py")

        # Overall alignment
        overall_aligned = all(r["aligned"] for r in results.values())

        return json.dumps({
            "aligned": overall_aligned,
            "feature": feature_description,
            "checks": results,
            "recommendations": _get_recommendations(results),
            "reference_docs": [
                "design/writing-style/01_philosophy.md",
                "design/mcp-architecture-roadmap.md",
                "agent/standards/feature-lifecycle.md"
            ]
        }, indent=2)

    @mcp.tool()
    async def get_feature_requirements(complexity_level: str = "L2") -> str:
        """
        Get complete requirements for implementing a feature of given complexity.

        Args:
            complexity_level: L1, L2, L3, or L4

        Returns:
            JSON with all requirements for this complexity level
        """
        level = complexity_level.upper()
        if level not in ["L1", "L2", "L3", "L4"]:
            level = "L2"

        return json.dumps({
            "complexity": level,
            "complexity_name": COMPLEXITY_LEVELS[level]["name"],
            "definition": COMPLEXITY_LEVELS[level]["definition"],
            "test_requirements": {
                "command": TEST_REQUIREMENTS[level],
                "coverage_target": "100% for new logic" if level in ["L3", "L4"] else "80%+"
            },
            "documentation_required": level in ["L3", "L4"],
            "design_review_required": level in ["L3", "L4"],
            "integration_tests_required": level in ["L3", "L4"],
            "e2e_tests_required": level == "L4",
            "checklist": _get_checklist(level),
            "reference": "agent/standards/feature-lifecycle.md"
        }, indent=2)

    @mcp.tool()
    async def check_doc_sync(changed_files: List[str] = None) -> str:
        """
        Verify that documentation is updated when code changes.

        Reference: agent/how-to/documentation-workflow.md

        Args:
            changed_files: List of code files that changed

        Returns:
            JSON with sync status and recommendations
        """
        changed_files = changed_files or get_changed_files()

        code_files = [f for f in changed_files if not f.endswith('.md')]
        doc_files = [f for f in changed_files if f.endswith('.md') or f.startswith('agent/')]

        sync_status = "ok"
        recommendations = []
        required_docs = []

        # Check if code changes require doc updates
        for f in code_files:
            if f.startswith("mcp-server/"):
                if not any(d in doc_files for d in ["mcp-server/README.md", "CLAUDE.md"]):
                    sync_status = "warning"
                    required_docs.append({
                        "file": "mcp-server/README.md and/or CLAUDE.md",
                        "reason": f"mcp-server code changed: {f}",
                        "action": "Add new tool to tool tables"
                    })
            elif f.startswith("units/modules/"):
                required_docs.append({
                    "file": "docs/ or infrastructure docs",
                    "reason": f"Nix module changed: {f}",
                    "action": "Update infrastructure documentation"
                })
            elif f == "justfile":
                required_docs.append({
                    "file": "docs/ and/or command help",
                    "reason": "justfile changed",
                    "action": "Update command documentation"
                })

        # Check for spec changes
        spec_files = [f for f in changed_files if f.startswith("agent/specs/")]
        if spec_files:
            if "agent/standards/feature-lifecycle.md" not in doc_files:
                sync_status = "warning"
                required_docs.append({
                    "file": "agent/standards/feature-lifecycle.md",
                    "reason": f"Spec added/modified: {spec_files[0]}",
                    "action": "Update workflow diagrams if needed"
                })

        # Check for agent/standards changes
        std_files = [f for f in changed_files if f.startswith("agent/standards/")]
        if std_files and not doc_files:
            sync_status = "warning"
            recommendations.append(f"Standards changed: {std_files}. Update related docs if needed.")

        if code_files and not doc_files and not required_docs:
            sync_status = "ok"
            recommendations.append("Documentation is in sync")

        if required_docs:
            recommendations = [f"Update {d['file']}: {d['action']}" for d in required_docs]

        return json.dumps({
            "status": sync_status,
            "code_files_changed": len(code_files),
            "doc_files_changed": len(doc_files),
            "required_docs": required_docs,
            "recommendations": recommendations if recommendations else ["Documentation is in sync"],
            "reference": "agent/how-to/documentation-workflow.md"
        }, indent=2)

    # -------------------------------------------------------------------------
    # Spec Management Tools
    # -------------------------------------------------------------------------

    @mcp.tool()
    async def draft_feature_spec(title: str, description: str, context_files: List[str] = None) -> str:
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
        template = _load_spec_template()
        standards = _scan_standards()  # <--- Load standards

        # Check for InferenceClient availability
        try:
            from mcp_core import InferenceClient
        except ImportError:
            return json.dumps({
                "status": "error",
                "message": "mcp_core.InferenceClient not available"
            }, indent=2)

        try:
            inference = InferenceClient(
                api_key="",
                base_url="https://api.minimax.io/anthropic"
            )
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Failed to initialize InferenceClient: {str(e)}"
            }, indent=2)

        # STRICT ENFORCEMENT PROMPT WITH VETO POWER
        system_prompt = f"""You are a Principal Software Architect with VETO POWER.
Your goal is to write a rigorous implementation spec that complies with PROJECT STANDARDS.

--- PROJECT STANDARDS (THE LAW) ---
{standards}
--- END STANDARDS ---

RULES:
1. Be precise. Use pseudo-code for interfaces.
2. Define data structures explicitly.
3. MANDATORY: The 'Verification Plan' MUST match the testing requirements in 'feature-lifecycle.md'.
   - L2: Unit Tests
   - L3: Unit + Integration
   - L4: Unit + Integration + Manual E2E

!!! CONFLICT RESOLUTION !!!
If the User Request explicitly asks you to violate a Standard (e.g., "skip tests"), you MUST REFUSE.
Do NOT generate the spec.
Instead, return ONLY: "⛔️ REJECTION: Cannot draft spec for '{title}'. Standard 'feature-lifecycle.md' classifies this as L4 (Critical), which mandates Unit + Integration + E2E tests."
4. If no conflict, use the provided Template structure exactly."""

        user_prompt = f"""Task: Create a spec for '{title}'.
Description: {description}
Context Files: {context_files or 'None'}

Template:
{template}

Return ONLY the Markdown content of the new spec (or the Rejection message)."""

        result = await inference.complete(
            system_prompt=system_prompt,
            user_query=user_prompt,
            max_tokens=2000
        )

        if not result.get("success"):
            return json.dumps({
                "status": "error",
                "message": f"Error generating spec: {result.get('error', 'Unknown error')}"
            }, indent=2)

        content = result.get("content", "").strip()

        # HANDLE REJECTION (VETO)
        if content.startswith("⛔️ REJECTION"):
            return json.dumps({
                "status": "rejected",
                "message": f"{content}\n\n💡 **Agentic OS Policy Enforcement**:\nYour request was blocked for violating safety standards.",
                "violated_standard": "feature-lifecycle.md",
                "recommendation": "Add required tests based on complexity level"
            }, indent=2)

        # Clean up any markdown code block markers
        spec_content = content
        if spec_content.startswith("```markdown"):
            spec_content = spec_content[10:]
        if spec_content.startswith("```"):
            spec_content = spec_content[3:]
        if spec_content.endswith("```"):
            spec_content = spec_content[:-3]
        spec_content = spec_content.strip()

        saved_path = _save_spec(title, spec_content)

        return json.dumps({
            "status": "success",
            "spec_path": saved_path,
            "message": f"✅ Spec Drafted (Standards Enforced): {saved_path}",
            "next_step": "Review spec and proceed to implementation"
        }, indent=2)

    @mcp.tool()
    async def verify_spec_completeness(spec_path: str = None) -> str:
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
        # Auto-detect spec_path from start_spec if not provided
        if not spec_path:
            memory = ProjectMemory()
            detected_path = memory.get_spec_path()
            if detected_path:
                spec_path = detected_path
                print(f"[verify_spec_completeness] Auto-detected spec_path: {spec_path}")
            else:
                return json.dumps({
                    "status": "error",
                    "message": "No spec_path provided and no spec detected from start_spec. Call start_spec first or provide spec_path explicitly."
                }, indent=2)

        path = Path(spec_path)
        if not path.exists():
            return json.dumps({
                "status": "error",
                "message": f"File {spec_path} not found"
            }, indent=2)

        content = path.read_text(encoding="utf-8")
        issues = _check_spec_completeness(content)

        if issues:
            return json.dumps({
                "status": "failed",
                "spec_path": spec_path,
                "issues": issues,
                "recommendation": "Fix issues above before proceeding to code"
            }, indent=2)

        return json.dumps({
            "status": "passed",
            "spec_path": spec_path,
            "message": "Spec verification passed - ready for Coder",
            "next_step": "Use @omni-coder tools to implement"
        }, indent=2)

    @mcp.tool()
    async def ingest_legacy_doc(doc_path: str) -> str:
        """
        [Migration Tool] Converts a legacy documentation file into a formal Feature Spec.
        Applies current project standards from agent/standards/.

        It reads the legacy file, extracts:
        - The Goal (Why)
        - The Implementation details (How)
        - The Constraints

        And reformats it into `agent/specs/{filename}.md` following the strict TEMPLATE.
        """
        source_path = Path(doc_path)
        if not source_path.exists():
            return json.dumps({
                "status": "error",
                "message": f"Source file '{doc_path}' not found"
            }, indent=2)

        source_content = source_path.read_text(encoding="utf-8")
        template = _load_spec_template()
        standards = _scan_standards()  # <--- Load standards

        # Check for InferenceClient availability
        try:
            from mcp_core import InferenceClient
        except ImportError:
            return json.dumps({
                "status": "error",
                "message": "mcp_core.InferenceClient not available"
            }, indent=2)

        try:
            inference = InferenceClient(
                api_key="",
                base_url="https://api.minimax.io/anthropic"
            )
        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Failed to initialize InferenceClient: {str(e)}"
            }, indent=2)

        # Enhanced System Prompt with Standards Injection
        system_prompt = f"""You are a Technical Documentation Refactoring Expert.
Your goal is to convert unstructured legacy documentation into a rigorous Feature Spec.

--- PROJECT STANDARDS (ENFORCE THESE) ---
{standards}
--- END STANDARDS ---

RULES:
1. Extract the CORE INTENT (Why are we doing this?).
2. Extract all TECHNICAL DETAILS (File paths, code snippets, logic).
3. Map them into the provided TEMPLATE structure.
4. If the legacy doc violates a Standard (e.g., missing tests), FIX IT in the new Spec.
5. Generate a Verification Plan based on 'feature-lifecycle.md'.
6. Keep the content concise but technically precise."""

        user_prompt = f"""Task: Convert this legacy doc into a Spec.

--- SOURCE DOCUMENT ({doc_path}) ---
{source_content}
--- END SOURCE ---

--- TARGET TEMPLATE ---
{template}
--- END TEMPLATE ---

Return ONLY the Markdown content of the new Spec. Do not include markdown code blocks."""

        try:
            result = await inference.complete(
                system_prompt=system_prompt,
                user_query=user_prompt,
                max_tokens=2000
            )

            # Extract content from result
            spec_content = result.get("content", "") if isinstance(result, dict) else str(result)

            # Clean up any markdown code block markers
            spec_content = spec_content.strip()
            if spec_content.startswith("```markdown"):
                spec_content = spec_content[10:]
            if spec_content.startswith("```"):
                spec_content = spec_content[3:]
            if spec_content.endswith("```"):
                spec_content = spec_content[:-3]
            spec_content = spec_content.strip()

            # Save as new spec
            saved_path = _save_spec(source_path.stem, spec_content)

            return json.dumps({
                "status": "success",
                "legacy_doc": doc_path,
                "new_spec": saved_path,
                "message": "Migration successful! Review the new spec before coding."
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "status": "error",
                "message": f"Failed to migrate doc: {str(e)}"
            }, indent=2)

    # -------------------------------------------------------------------------
    # NEW: Spec Archiving (The Cycle Closer)
    # -------------------------------------------------------------------------

    @mcp.tool()
    async def archive_spec_to_doc(spec_path: str, target_category: str = "explanation") -> str:
        """
        [Lifecycle Tool] Archives a completed Spec and converts it into permanent documentation.

        Use this when a feature is DONE (Code Merged + Tests Passed).

        Actions:
        1. Reads the Spec.
        2. Extracts enduring technical knowledge (Architecture, Decisions, Schema).
        3. Creates a new doc in `docs/{target_category}/`.
        4. Moves the original Spec to `agent/specs/archive/`.

        Args:
            spec_path: Path to the spec (e.g. agent/specs/auth_module.md)
            target_category: "explanation" (concepts), "reference" (APIs), or "how-to" (guides)
        """
        src = Path(spec_path)
        if not src.exists():
            return json.dumps({
                "status": "error",
                "message": f"Spec '{spec_path}' not found."
            }, indent=2)

        content = src.read_text(encoding="utf-8")

        try:
            from mcp_core import InferenceClient
            client = InferenceClient()
        except ImportError:
            return json.dumps({
                "status": "error",
                "message": "mcp_core.InferenceClient not available"
            }, indent=2)

        system_prompt = """You are a Technical Documentation Curator.
Your goal is to convert a "Implementation Spec" into permanent "System Documentation".

INPUT: A Feature Spec (contains Context, Architecture, Plan, Tests).
OUTPUT: A Clean Documentation File.

RULES:
1. KEEP: Context/Goal (Why we built this).
2. KEEP: Architecture & Interface (How it works).
3. DISCARD: Implementation Plan (Step-by-step instructions are now irrelevant).
4. DISCARD: Verification Plan (Tests are now in the codebase).
5. ADD: A "Status" badge indicating this is a live feature."""

        user_prompt = f"""Convert this Spec into {target_category} documentation.

--- SPEC CONTENT ---
{content}
--- END SPEC ---

Return ONLY the Markdown content."""

        result = await client.complete(system_prompt, user_prompt)
        if not result.get("success"):
            return json.dumps({
                "status": "error",
                "message": f"Error converting spec: {result.get('error', 'Unknown error')}"
            }, indent=2)

        # Save new Doc
        doc_content = result.get("content", "").strip()
        doc_content = doc_content.strip()
        if doc_content.startswith("```markdown"):
            doc_content = doc_content[10:]
        if doc_content.startswith("```"):
            doc_content = doc_content[3:]
        if doc_content.endswith("```"):
            doc_content = doc_content[:-3]
        doc_content = doc_content.strip()

        doc_path = Path(f"docs/{target_category}") / src.name
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(doc_content, encoding="utf-8")

        # Archive old Spec
        archive_dir = Path("agent/specs/archive")
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / src.name
        src.rename(archive_path)

        return json.dumps({
            "status": "success",
            "new_doc": str(doc_path),
            "archived_spec": str(archive_path),
            "message": "✅ Spec Archived & Documented!\n\n1. New Doc Created: {doc_path}\n2. Spec Archived: {archive_path}\n\nCycle Complete. 🔄"
        }, indent=2)


def _get_recommendations(results: dict) -> list:
    """Generate recommendations based on alignment results."""
    recs = []

    if not results["philosophy"]["aligned"]:
        recs.append("Review design/writing-style/01_philosophy.md - simplify if possible")

    if results["roadmap"]["in_roadmap"] is False:
        recs.append("Feature not in roadmap - consider adding to design/roadmap.md")

    if not results["architecture"]["aligned"]:
        recs.append("Review design/mcp-architecture-roadmap.md - ensure architecture fit")

    if all(r["aligned"] for r in results.values()):
        recs.append("Feature is well-aligned with design documents")

    return recs


def _get_checklist(level: str) -> list:
    """Get checklist for a complexity level."""
    checklist = ["Code follows writing style (design/writing-style/)"]

    if level in ["L2", "L3", "L4"]:
        checklist.append("Unit tests added/updated")
        checklist.append("Test coverage maintained or improved")

    if level in ["L3", "L4"]:
        checklist.append("Integration tests added")
        checklist.append("Documentation updated in docs/")
        checklist.append("Design reviewed (if L4)")

    if level == "L4":
        checklist.append("E2E tests verified")
        checklist.append("Security review (if applicable)")
        checklist.append("Breaking changes documented")

    return checklist


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "register_product_owner_tools",
    "COMPLEXITY_LEVELS",
    "TEST_REQUIREMENTS",
    "heuristic_complexity"
]
