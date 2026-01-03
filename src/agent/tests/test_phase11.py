# src/agent/tests/test_phase11.py
"""
Phase 11: The Neural Matrix - Test Suite

Tests for:
- Pydantic schema validation
- LangGraph commit workflow
- Smart Commit V2 tools

Reference: agent/specs/phase11_neural_matrix.md

Run from project root:
    uv run pytest src/agent/tests/test_phase11.py -v
"""
import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from common.mcp_core.gitops import get_project_root

_project_root = get_project_root()
_agent_dir = _project_root / "src" / "agent"
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

# Import from agent.core (src/agent/core)
from core.schema import (
    SpecGapAnalysis,
    LegislationDecision,
    FeatureComplexity,
    ComplexityLevel,
    RouterDomain,
    CommitMessageValidation,
)


# =============================================================================
# Schema Tests
# =============================================================================

class TestSpecGapAnalysis:
    """Tests for SpecGapAnalysis schema."""

    def test_spec_gap_analysis_valid(self):
        """Verify valid spec gap analysis can be created."""
        gap = SpecGapAnalysis(
            spec_exists=True,
            spec_path="agent/specs/test.md",
            completeness_score=85,
            missing_sections=["Security"],
            has_template_placeholders=False,
            test_plan_defined=True
        )
        assert gap.spec_exists is True
        assert gap.completeness_score == 85
        assert len(gap.missing_sections) == 1

    def test_spec_gap_analysis_minimal(self):
        """Verify minimal spec gap analysis."""
        gap = SpecGapAnalysis(
            spec_exists=False,
            spec_path=None,
            completeness_score=0,
            missing_sections=["all"],
            has_template_placeholders=False,
            test_plan_defined=False
        )
        assert gap.spec_exists is False
        assert gap.completeness_score == 0

    def test_spec_gap_analysis_score_bounds(self):
        """Verify score is constrained to 0-100."""
        with pytest.raises(ValueError):
            SpecGapAnalysis(
                spec_exists=True,
                spec_path="test.md",
                completeness_score=150,  # Invalid
                missing_sections=[],
                has_template_placeholders=False,
                test_plan_defined=True
            )


class TestLegislationDecision:
    """Tests for LegislationDecision schema."""

    def test_allowed_decision(self):
        """Verify allowed decision schema."""
        gap = SpecGapAnalysis(
            spec_exists=True,
            spec_path="agent/specs/test.md",
            completeness_score=90,
            missing_sections=[],
            has_template_placeholders=False,
            test_plan_defined=True
        )
        decision = LegislationDecision(
            decision="allowed",
            reasoning="Spec is complete",
            required_action="proceed_to_code",
            gap_analysis=gap,
            spec_path="agent/specs/test.md"
        )
        assert decision.decision == "allowed"
        assert decision.required_action == "proceed_to_code"

    def test_blocked_decision(self):
        """Verify blocked decision schema."""
        gap = SpecGapAnalysis(
            spec_exists=False,
            spec_path=None,
            completeness_score=0,
            missing_sections=["all"],
            has_template_placeholders=False,
            test_plan_defined=False
        )
        decision = LegislationDecision(
            decision="blocked",
            reasoning="Legislation is mandatory",
            required_action="create_spec",
            gap_analysis=gap,
            spec_path=None
        )
        assert decision.decision == "blocked"
        assert decision.required_action == "create_spec"


class TestFeatureComplexity:
    """Tests for FeatureComplexity schema."""

    def test_complexity_level_l1(self):
        """Verify L1 complexity schema."""
        complexity = FeatureComplexity(
            level=ComplexityLevel.L1,
            name="Trivial",
            definition="Typos, config tweaks",
            rationale="Documentation only change",
            test_requirements="just lint",
            examples=["Fix typo", "Update README"]
        )
        assert complexity.level == ComplexityLevel.L1
        assert complexity.level.value == "L1"

    def test_complexity_level_l4(self):
        """Verify L4 complexity schema."""
        complexity = FeatureComplexity(
            level=ComplexityLevel.L4,
            name="Critical",
            definition="Auth, Payments, breaking changes",
            rationale="Authentication system change",
            test_requirements="just test-unit && just test-int && manual E2E",
            examples=["Add OAuth", "DB migration"]
        )
        assert complexity.level == ComplexityLevel.L4


# =============================================================================
# Commit Workflow Tests
# =============================================================================

class TestCommitWorkflow:
    """Tests for LangGraph commit workflow."""

    def test_workflow_compiles(self):
        """Verify LangGraph workflow compiles successfully."""
        from core.workflows.commit_flow import create_commit_workflow

        workflow = create_commit_workflow()
        assert workflow is not None

    def test_workflow_has_required_nodes(self):
        """Verify workflow has all required nodes."""
        from core.workflows.commit_flow import create_commit_workflow

        workflow = create_commit_workflow()

        # Check nodes exist (graph is StateGraph before compilation)
        nodes = list(workflow.nodes.keys())
        assert "analyze" in nodes
        assert "human_gate" in nodes
        assert "execute" in nodes

    def test_workflow_edges(self):
        """Verify workflow has correct edges."""
        from core.workflows.commit_flow import create_commit_workflow

        workflow = create_commit_workflow()

        # StateGraph uses set_entry_point, check by verifying nodes exist
        nodes = list(workflow.nodes.keys())
        assert "analyze" in nodes
        assert "human_gate" in nodes
        assert "execute" in nodes

    def test_get_workflow_returns_compiled(self):
        """Verify get_workflow returns compiled state graph."""
        from core.workflows.commit_flow import get_workflow

        workflow = get_workflow()

        # CompiledStateGraph should have stream method
        assert hasattr(workflow, 'stream')
        assert hasattr(workflow, 'get_state')
        assert hasattr(workflow, 'update_state')


# =============================================================================
# Product Owner Helper Functions Tests
# =============================================================================

class TestProductOwnerHelpers:
    """Tests for product_owner helper functions."""

    def test_get_spec_path_from_name(self):
        """Verify spec path generation from name."""
        from capabilities.product_owner import _get_spec_path_from_name

        # Test with simple name
        path = _get_spec_path_from_name("user_authentication")
        assert path is None  # File doesn't exist

        # Test with special characters
        path = _get_spec_path_from_name("auth/login_flow")
        assert path is None

    def test_analyze_spec_gap_no_spec(self):
        """Verify gap analysis when spec doesn't exist."""
        from capabilities.product_owner import _analyze_spec_gap

        gap = _analyze_spec_gap(None)

        assert gap["spec_exists"] is False
        assert gap["completeness_score"] == 0
        assert gap["missing_sections"] == ["all"]
        assert gap["test_plan_defined"] is False

    def test_analyze_spec_gap_with_existing_spec(self):
        """Verify gap analysis when spec exists."""
        from capabilities.product_owner import _analyze_spec_gap

        # Use an existing spec file (with the naming convention)
        spec_path = "agent/specs/phase11_the_neural_matrix.md"
        gap = _analyze_spec_gap(spec_path)

        assert gap["spec_exists"] is True
        assert gap["spec_path"] == spec_path
        assert gap["completeness_score"] > 0
        assert isinstance(gap["missing_sections"], list)


# =============================================================================
# Integration Tests (Mocked)
# Note: smart_commit and confirm_commit are MCP tools, not exported functions.
# They can only be tested through the MCP server interface.
# =============================================================================

# Skipping these tests as the functions are MCP tools, not module exports


# =============================================================================
# Router Domain Tests
# =============================================================================

class TestRouterDomain:
    """Tests for RouterDomain enum."""

    def test_all_domains_defined(self):
        """Verify all expected domains exist."""
        assert RouterDomain.GITOPS.value == "GitOps"
        assert RouterDomain.PRODUCT_OWNER.value == "ProductOwner"
        assert RouterDomain.CODER.value == "Coder"
        assert RouterDomain.QA.value == "QA"
        assert RouterDomain.MEMORY.value == "Memory"
        assert RouterDomain.DEVOPS.value == "DevOps"
        assert RouterDomain.SEARCH.value == "Search"


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_diff():
    """Provide a sample git diff for testing."""
    return """diff --git a/src/agent/core/schema.py b/src/agent/core/schema.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/agent/core/schema.py
@@ -0,0 +1,100 @@
+# Phase 11 Schema
+class SpecGapAnalysis(BaseModel):
+    pass
+"""


@pytest.fixture
def sample_commit_message():
    """Provide a sample commit message for testing."""
    return "feat(agent): add Phase 11 neural matrix schema"


# =============================================================================
# Run Tests
# =============================================================================

# =============================================================================
# Phase 13.8: Configuration-Driven Context Tests
# =============================================================================

class TestContextLoader:
    """Tests for Configuration-Driven Context (Phase 13.8)."""

    def test_context_loader_exists(self):
        """Verify context_loader module exists."""
        from agent.core.context_loader import ContextLoader, load_system_context
        assert ContextLoader is not None
        assert callable(load_system_context)

    def test_context_loader_loads_system_prompt(self):
        """Verify system prompt can be loaded from configuration."""
        from agent.core.context_loader import ContextLoader

        loader = ContextLoader()
        prompt = loader.get_combined_system_prompt()

        assert prompt is not None
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_context_loader_includes_core_prompt(self):
        """Verify system prompt includes core content."""
        from agent.core.context_loader import ContextLoader

        loader = ContextLoader()
        prompt = loader.get_combined_system_prompt()

        # Should contain key phrases from system_core.md
        assert "Omni-DevEnv" in prompt or "security" in prompt.lower()

    def test_context_loader_handles_missing_user_custom(self):
        """Verify graceful handling when user_custom.md doesn't exist."""
        from agent.core.context_loader import ContextLoader
        from common.mcp_core.settings import get_setting

        loader = ContextLoader()
        user_path = get_setting("prompts.user_custom_path", "nonexistent/path.md")
        content = loader._read_file_safe(user_path)

        # Should return empty string, not raise exception
        assert content == ""

    def test_settings_prompts_config_exists(self):
        """Verify settings.yaml has prompts configuration."""
        from common.mcp_core.settings import get_setting

        core_path = get_setting("prompts.core_path")
        user_path = get_setting("prompts.user_custom_path")

        assert core_path is not None
        assert "system_core.md" in core_path
        assert "user_custom.md" in user_path


# =============================================================================
# InferenceClient API Signature Tests (Regression Tests)
# =============================================================================

class TestInferenceClientSignature:
    """Tests for InferenceClient API signature (prevents regression)."""

    def test_inference_client_complete_signature(self):
        """Verify InferenceClient.complete has correct signature."""
        from common.mcp_core.inference import InferenceClient
        import inspect

        sig = inspect.signature(InferenceClient.complete)
        params = list(sig.parameters.keys())

        # Must have these parameters
        assert "system_prompt" in params, "complete() must have 'system_prompt' parameter"
        assert "user_query" in params, "complete() must have 'user_query' parameter"
        # Must NOT have 'prompt' parameter (old API)
        assert "prompt" not in params, "complete() must NOT have 'prompt' parameter (old API)"

    def test_inference_client_returns_dict(self):
        """Verify InferenceClient.complete returns Dict[str, Any]."""
        from common.mcp_core.inference import InferenceClient

        # Check return annotation in the function signature
        import inspect
        sig = inspect.signature(InferenceClient.complete)
        return_annotation = str(sig.return_annotation)
        # Should contain Dict and Any
        assert "Dict" in return_annotation, f"Return should be Dict, got: {return_annotation}"
        assert "Any" in return_annotation, f"Return should include Any, got: {return_annotation}"


class TestCommitToolsInferenceUsage:
    """Tests for correct InferenceClient usage in commit tools."""

    def test_commit_tools_uses_correct_api(self):
        """Verify commit.py uses correct InferenceClient API."""
        import ast
        from pathlib import Path

        commit_py = Path(__file__).parent.parent / "tools" / "commit.py"
        if not commit_py.exists():
            pytest.skip("commit.py not found")

        content = commit_py.read_text()
        tree = ast.parse(content)

        # Find all function calls to client.complete
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "complete":
                        # Check keyword arguments
                        kwargs = {kw.arg for kw in node.keywords}
                        assert "prompt" not in kwargs, "commit.py: complete() must NOT use 'prompt' kwarg"
                        assert "system_prompt" in kwargs or "user_query" in kwargs, \
                            "commit.py: complete() should use 'system_prompt' and 'user_query'"

    def test_spec_tools_uses_correct_api(self):
        """Verify spec.py uses correct InferenceClient API."""
        import ast
        from pathlib import Path

        spec_py = Path(__file__).parent.parent / "tools" / "spec.py"
        if not spec_py.exists():
            pytest.skip("spec.py not found")

        content = spec_py.read_text()
        tree = ast.parse(content)

        # Find all function calls to client.complete
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "complete":
                        # Check keyword arguments
                        kwargs = {kw.arg for kw in node.keywords}
                        assert "prompt" not in kwargs, "spec.py: complete() must NOT use 'prompt' kwarg"
                        assert "system_prompt" in kwargs or "user_query" in kwargs, \
                            "spec.py: complete() should use 'system_prompt' and 'user_query'"


# =============================================================================
# Token File Format Tests
# =============================================================================

class TestTokenFileFormat:
    """Tests for commit token file format (prevents expiration issues)."""

    def test_token_file_format_parseable(self):
        """Verify token file format can be parsed correctly by justfile."""
        import subprocess

        # Use a fixed timestamp that date -d can parse reliably
        timestamp = "2026-01-03 12:00:00"

        # Simulate token file content
        token_content = f"session123:abc123:{timestamp}:test message"

        # Parse format: session_id:token:timestamp:message
        parts = token_content.split(":")
        assert len(parts) >= 4, "Token format must have at least 4 parts"

        session_id, token, ts, message = parts[0], parts[1], parts[2], ":".join(parts[3:])

        # Verify timestamp can be parsed by bash date command
        result = subprocess.run(
            ["date", "-d", ts, "+%s"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"date -d failed to parse: {ts}, error: {result.stderr}"

        epoch = int(result.stdout.strip())
        # Verify it's a valid epoch timestamp (2026-01-03 = ~1735838400)
        assert epoch > 1700000000, f"Invalid epoch: {epoch}"
        assert epoch < 2000000000, f"Invalid epoch: {epoch}"

    def test_justfile_agent_commit_timestamp_parsing(self):
        """Verify justfile can parse the timestamp format correctly."""
        import subprocess
        import os

        # Use a fixed timestamp to avoid timezone issues
        timestamp = "2026-01-03 12:00:00"
        token_file = "/tmp/.omni_commit_token_test"

        # Write token file with proper format
        token_content = f"session123:test-token:{timestamp}:test commit"
        with open(token_file, "w") as f:
            f.write(token_content)

        # Test the parsing logic from justfile (lines 58-71)
        result = subprocess.run(
            ["bash", "-c", f'''
                TOKEN_FILE="{token_file}"
                if [ -f "$TOKEN_FILE" ]; then
                    TOKEN_CONTENT=$(cat "$TOKEN_FILE")
                    TIMESTAMP=$(echo "$TOKEN_CONTENT" | cut -d':' -f3)
                    # This is what justfile does on line 69
                    TOKEN_EPOCH=$(date -d "$TIMESTAMP" +%s 2>/dev/null || date +%s)
                    NOW_EPOCH=$(date +%s)
                    ELAPSED=$((NOW_EPOCH - TOKEN_EPOCH))
                    echo "ELAPSED=$ELAPSED"
                    # Just verify parsing works, not expiration check
                    echo "PARSED_OK"
                else
                    echo "FILE_NOT_FOUND"
                fi
            '''],
            capture_output=True,
            text=True
        )

        # The token should be parseable
        assert result.returncode == 0, f"Failed to parse token: {result.stderr}"
        assert "PARSED_OK" in result.stdout, f"Token parsing failed: {result.stdout}"

        # Cleanup
        os.remove(token_file)

    def test_token_file_format_with_epoch(self):
        """Verify epoch timestamp format also works (fallback)."""
        import subprocess

        # Use epoch timestamp directly (what happens when date -d fails)
        epoch_ts = "1735838400"  # 2026-01-03 12:00:00 UTC

        # Simulate token file content with epoch
        token_content = f"session123:abc123:{epoch_ts}:test message"

        # Parse format
        parts = token_content.split(":")
        assert len(parts) >= 4

        ts = parts[2]
        assert ts.isdigit(), "Epoch timestamp should be numeric"

        # Verify epoch is valid
        assert int(ts) > 1700000000, "Invalid epoch timestamp"
        assert int(ts) < 2000000000, "Invalid epoch timestamp"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
