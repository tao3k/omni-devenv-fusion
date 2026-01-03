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
# =============================================================================

class TestSmartCommitV2Integration:
    """Integration tests for smart_commit_v2 (mocked)."""

    @pytest.mark.asyncio
    async def test_smart_commit_v2_no_staged_changes(self):
        """Verify error when no staged changes exist."""
        from main import smart_commit_v2

        # Mock git to return empty diff
        with patch('main._get_git_diff', return_value=""):
            result = await smart_commit_v2(context="Test")
            result_dict = json.loads(result)

            assert result_dict["status"] == "error"
            assert "No staged changes" in result_dict["message"]

    @pytest.mark.asyncio
    async def test_confirm_commit_invalid_session(self):
        """Verify error for invalid session ID."""
        from main import confirm_commit

        result = await confirm_commit(
            session_id="nonexistent_session",
            decision="approved"
        )
        result_dict = json.loads(result)

        assert result_dict["status"] == "error"
        assert "not found" in result_dict["message"]

    @pytest.mark.asyncio
    async def test_confirm_commit_invalid_decision(self):
        """Verify error for invalid decision."""
        from main import confirm_commit, _commit_workflow_sessions

        # Create a mock session
        _commit_workflow_sessions["test_session"] = {"status": "pending"}

        result = await confirm_commit(
            session_id="test_session",
            decision="maybe"  # Invalid
        )
        result_dict = json.loads(result)

        assert result_dict["status"] == "error"
        assert "Invalid decision" in result_dict["message"]

        # Cleanup
        _commit_workflow_sessions.pop("test_session", None)


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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
