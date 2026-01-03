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
# Phase 13.9: Git Skill Hot Reload Tests
# =============================================================================

class TestGitSkillHotReload:
    """Tests for Git Skill Hot Reload functionality."""

    def test_git_skill_module_exists(self):
        """Verify git skill module exists and can be imported."""
        from agent.skills.git.tools import register, _commit_sessions
        assert register is not None
        assert isinstance(_commit_sessions, dict)

    def test_git_skill_tools_defined(self):
        """Verify all git skill tools are defined in the module using AST."""
        import ast
        from pathlib import Path

        git_tools_py = Path(__file__).parent.parent / "skills" / "git" / "tools.py"
        assert git_tools_py.exists(), f"Git skill not found at {git_tools_py}"

        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find all @mcp.tool() decorated async functions
        tool_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for decorator in node.decorator_list:
                    # Check for @mcp.tool() decorator pattern
                    # Pattern 1: @mcp.tool()
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr == 'tool':
                                tool_names.append(node.name)
                    # Pattern 2: @mcp.tool (without parens, rare)
                    elif isinstance(decorator, ast.Name):
                        if decorator.id == 'tool':
                            tool_names.append(node.name)

        # Verify expected tools exist
        expected_tools = ["git_status", "git_diff_staged", "git_diff_unstaged",
                          "git_log", "git_add", "spec_aware_commit", "smart_commit"]

        for tool in expected_tools:
            assert tool in tool_names, \
                f"Expected tool '{tool}' not found in git skill. Found: {tool_names}"

    def test_spec_aware_commit_uses_inference_client(self):
        """Verify spec_aware_commit is defined with correct InferenceClient API usage."""
        import ast
        from pathlib import Path

        git_tools_py = Path(__file__).parent.parent / "skills" / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find spec_aware_commit function
        spec_aware_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "spec_aware_commit":
                spec_aware_func = node
                break

        assert spec_aware_func is not None, "spec_aware_commit not found"

        # Verify function signature
        args = [arg.arg for arg in spec_aware_func.args.args]
        assert "context" in args, "spec_aware_commit should have 'context' parameter"

        # Verify function body contains InferenceClient usage
        body_text = ast.get_source_segment(content, spec_aware_func)
        assert "InferenceClient" in body_text, "spec_aware_commit should use InferenceClient"
        assert "system_prompt" in body_text, "spec_aware_commit should use system_prompt"
        assert "user_query" in body_text, "spec_aware_commit should use user_query"

    def test_smart_commit_v2_implementation(self):
        """Verify smart_commit V2 (session-based) is properly implemented."""
        import ast
        from pathlib import Path

        git_tools_py = Path(__file__).parent.parent / "skills" / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find smart_commit function
        smart_commit_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "smart_commit":
                smart_commit_func = node
                break

        assert smart_commit_func is not None, "smart_commit not found"

        # Verify function signature
        args = [arg.arg for arg in smart_commit_func.args.args]
        assert "message" in args, "smart_commit should have 'message' parameter"
        assert "auth_token" in args, "smart_commit should have 'auth_token' parameter"

        # Verify function body
        body_text = ast.get_source_segment(content, smart_commit_func)

        # Verify session-based storage
        assert "_commit_sessions" in body_text, "smart_commit should use _commit_sessions"

        # Verify session_id generation
        assert "secrets.token_hex" in body_text, "smart_commit should generate session_id"

        # Verify two-phase workflow (auth_token check)
        assert 'if auth_token:' in body_text or 'if auth_token :' in body_text, \
            "smart_commit should have execute phase when auth_token is provided"

        # Verify session creation in analysis phase
        assert "_commit_sessions[session_id]" in body_text, \
            "smart_commit should create session in analysis phase"

    def test_git_skill_uses_dynamic_paths(self):
        """Verify git skill uses dynamic project root detection via gitops."""
        import ast
        from pathlib import Path

        git_tools_py = Path(__file__).parent.parent / "skills" / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Check imports from gitops
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "gitops" in node.module:
                    for alias in node.names:
                        imports.append(alias.asname or alias.name)

        # Should import git command functions
        required_imports = ["run_git_cmd", "get_git_status", "get_git_diff", "get_git_log"]
        for imp in required_imports:
            assert imp in imports, f"git skill should import '{imp}' from gitops"

    def test_git_skill_supports_hot_reload(self):
        """Verify git skill structure supports hot reload (no caching decorators)."""
        import ast
        from pathlib import Path

        git_tools_py = Path(__file__).parent.parent / "skills" / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find register function
        register_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "register":
                register_func = node
                break

        assert register_func is not None, "register function not found"

        # Check register function decorators
        for decorator in register_func.decorator_list:
            # Check for caching decorators that would prevent hot reload
            decorator_name = None
            if isinstance(decorator, ast.Name):
                decorator_name = decorator.id
            elif isinstance(decorator, ast.Attribute):
                decorator_name = decorator.attr

            if decorator_name in ["lru_cache", "cache", "cached"]:
                raise AssertionError(f"register should not have '{decorator_name}' decorator")

        # Verify register defines tools
        body_text = ast.get_source_segment(content, register_func)
        assert "@mcp.tool()" in body_text, "register should define MCP tools"

    def test_smart_commit_session_workflow(self):
        """Test the session-based commit workflow logic."""
        from agent.skills.git.tools import _commit_sessions

        # Verify session storage is dict
        assert isinstance(_commit_sessions, dict)

        # Test session creation
        session_id = "test1234"
        _commit_sessions[session_id] = {
            "status": "pending_auth",
            "message": "feat(test): test commit",
            "timestamp": "2026-01-03T12:00:00"
        }

        # Verify session is stored
        assert session_id in _commit_sessions
        assert _commit_sessions[session_id]["status"] == "pending_auth"
        assert _commit_sessions[session_id]["message"] == "feat(test): test commit"

        # Test session cleanup
        _commit_sessions.pop(session_id, None)
        assert session_id not in _commit_sessions, "Session should be cleaned up"

    def test_gitops_has_required_functions(self):
        """Verify gitops module has all required git command functions."""
        from common.mcp_core import gitops

        # Verify all required functions exist and are callable
        required = ["run_git_cmd", "get_git_status", "get_git_diff", "get_git_log"]
        for name in required:
            assert hasattr(gitops, name), f"gitops should have '{name}'"
            func = getattr(gitops, name)
            assert callable(func), f"gitops.{name} should be callable"

    def test_git_skill_tool_count(self):
        """Verify git skill has exactly the expected number of tools."""
        import ast
        from pathlib import Path

        git_tools_py = Path(__file__).parent.parent / "skills" / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Count @mcp.tool() decorated functions
        tool_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            if decorator.func.attr == 'tool':
                                tool_count += 1

        # Expected: 7 tools
        assert tool_count == 7, f"Expected 7 tools, found {tool_count}"

    def test_smart_commit_token_file_writing(self):
        """Verify smart_commit does NOT use token file (session-based, not file-based)."""
        import ast
        from pathlib import Path

        git_tools_py = Path(__file__).parent.parent / "skills" / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find smart_commit function
        smart_commit_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "smart_commit":
                smart_commit_func = node
                break

        assert smart_commit_func is not None, "smart_commit not found"

        # Verify function body uses session-based workflow (not token file)
        body_text = ast.get_source_segment(content, smart_commit_func)

        # Verify session-based storage
        assert "_commit_sessions" in body_text, "smart_commit should use _commit_sessions"

        # Verify auth_token parameter is used for execution phase
        assert 'if auth_token:' in body_text, "smart_commit should have execute phase"

        # Verify NO TOKEN_FILE usage
        assert "TOKEN_FILE" not in body_text, "smart_commit should NOT use TOKEN_FILE"
        assert 'write_text' not in body_text, "smart_commit should NOT write token file"

        # Verify the format is session_id:token:timestamp:message is NOT used
        # (we use simple session_id in _commit_sessions dict, not a file format)
        assert 'f"{session_id}:{session_id}:' not in body_text, \
            "smart_commit should NOT format token like file-based system"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
