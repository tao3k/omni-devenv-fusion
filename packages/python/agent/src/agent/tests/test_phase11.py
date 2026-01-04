# packages/python/agent/src/agent/tests/test_phase11.py
"""
Phase 11: The Neural Matrix - Test Suite (Simplified)

Tests for:
- Pydantic schema validation
- Context injection

Reference: agent/specs/phase11_neural_matrix.md

In uv workspace, packages are installed and can be imported directly.
"""
import pytest
from pathlib import Path

# Direct imports from installed workspace packages
from agent.core.schema import (
    SpecGapAnalysis,
    LegislationDecision,
    FeatureComplexity,
    ComplexityLevel,
    RouterDomain,
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

        loader = ContextLoader()
        # Use a path that definitely doesn't exist
        content = loader._read_file_safe("/tmp/this-file-definitely-does-not-exist-12345.md")

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
# Phase 13.9: Git Status Injection Tests
# =============================================================================

class TestGitStatusInjection:
    """Tests for Phase 13.9 Context Injection."""

    def test_context_loader_has_git_status_method(self):
        """Verify ContextLoader has _get_git_status_summary method."""
        from agent.core.context_loader import ContextLoader

        loader = ContextLoader()
        assert hasattr(loader, "_get_git_status_summary")
        assert callable(loader._get_git_status_summary)

    def test_git_status_returns_string(self):
        """Verify git status returns a string."""
        from agent.core.context_loader import ContextLoader

        loader = ContextLoader()
        status = loader._get_git_status_summary()

        assert isinstance(status, str)
        assert len(status) > 0

    def test_system_prompt_includes_git_status_placeholder(self):
        """Verify system_core.md has git_status placeholder."""
        core_path = Path.cwd() / "agent" / "prompts" / "system_core.md"
        if core_path.exists():
            content = core_path.read_text()
            assert "{{git_status}}" in content


# =============================================================================
# Phase 13.10: Git Skill Tests (Simplified)
# =============================================================================

_SKILLS_ROOT = Path.cwd() / "agent" / "skills"


class TestGitSkill:
    """Tests for Git Skill (Phase 13.10 - Critical Operations Only)."""

    def test_git_skill_module_exists(self):
        """Verify git skill module exists."""
        git_tools_py = _SKILLS_ROOT / "git" / "tools.py"
        assert git_tools_py.exists(), f"Git skill not found at {git_tools_py}"

    def test_git_skill_tools_defined(self):
        """Verify critical git tools (commit, push) are defined."""
        import ast

        git_tools_py = _SKILLS_ROOT / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        tool_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                tool_names.append(node.name)

        assert "git_commit" in tool_names, "git_commit should be defined"
        assert "git_push" in tool_names, "git_push should be defined"

    def test_no_deprecated_tools(self):
        """Verify only critical git tools exist (commit, push)."""
        import ast

        git_tools_py = _SKILLS_ROOT / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        tool_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                tool_names.append(node.name)

        # Should only have git_commit and git_push
        assert tool_names == ["git_commit", "git_push"], f"Expected only git_commit and git_push, found: {tool_names}"

    def test_git_commit_has_message_param(self):
        """Verify git_commit has message parameter."""
        import ast

        git_tools_py = _SKILLS_ROOT / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find git_commit function
        git_commit_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "git_commit":
                git_commit_func = node
                break

        assert git_commit_func is not None, "git_commit not found"

        # Verify function signature
        args = [arg.arg for arg in git_commit_func.args.args]
        assert "message" in args, "git_commit should have 'message' parameter"

    def test_git_push_has_no_params(self):
        """Verify git_push has no parameters (no-arg tool)."""
        import ast

        git_tools_py = _SKILLS_ROOT / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find git_push function
        git_push_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "git_push":
                git_push_func = node
                break

        assert git_push_func is not None, "git_push not found"

        # Verify function has no required parameters
        args = [arg.arg for arg in git_push_func.args.args]
        assert len(args) == 0, f"git_push should have no parameters, found: {args}"

    def test_git_skill_uses_gitops(self):
        """Verify git skill uses run_git_cmd from gitops."""
        import ast

        git_tools_py = _SKILLS_ROOT / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Check imports from gitops
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "gitops" in node.module:
                    for alias in node.names:
                        imports.append(alias.asname or alias.name)

        # Should import run_git_cmd
        assert "run_git_cmd" in imports, "git skill should import 'run_git_cmd' from gitops"

    def test_git_skill_supports_hot_reload(self):
        """Verify git skill structure supports hot reload."""
        import ast

        git_tools_py = _SKILLS_ROOT / "git" / "tools.py"
        content = git_tools_py.read_text()
        tree = ast.parse(content)

        # Find register function
        register_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "register":
                register_func = node
                break

        assert register_func is not None, "register function not found"

        # Verify register function has mcp parameter (FastMCP pattern)
        args = [arg.arg for arg in register_func.args.args]
        assert "mcp" in args, "register should have 'mcp' parameter for FastMCP"


# =============================================================================
# Phase 13.10: Config-Driven Skill Loading Tests
# =============================================================================

class TestSkillRegistry:
    """Tests for Config-Driven Skill Loading (Phase 13.10)."""

    def test_skill_registry_exists(self):
        """Verify skill registry module exists."""
        from agent.core.skill_registry import get_skill_registry, SkillRegistry
        assert get_skill_registry is not None
        assert SkillRegistry is not None

    def test_get_preload_skills_from_config(self):
        """Verify preload skills are read from settings.yaml."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        preload = registry.get_preload_skills()

        assert isinstance(preload, list)
        assert len(preload) > 0
        # Should contain expected skills
        assert "git" in preload
        assert "filesystem" in preload
        assert "terminal" in preload

    def test_list_available_skills(self):
        """Verify available skills are discovered from agent/skills/."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        available = registry.list_available_skills()

        assert isinstance(available, list)
        assert len(available) > 0
        # Should find git skill
        assert "git" in available
        # Should be sorted
        assert available == sorted(available)

    def test_list_loaded_skills_initially_empty(self):
        """Verify no skills are loaded initially (before boot)."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        loaded = registry.list_loaded_skills()

        assert isinstance(loaded, list)
        # At test time, no skills should be loaded yet

    def test_get_skill_manifest(self):
        """Verify skill manifests can be read."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        manifest = registry.get_skill_manifest("git")

        assert manifest is not None
        assert manifest.name == "git"
        assert manifest.tools_module == "agent.skills.git.tools"

    def test_get_nonexistent_skill_manifest(self):
        """Verify graceful handling of nonexistent skill."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        manifest = registry.get_skill_manifest("nonexistent_skill_xyz")

        assert manifest is None

    def test_settings_yaml_has_skills_config(self):
        """Verify settings.yaml has skills configuration."""
        from common.mcp_core.settings import get_setting

        preload = get_setting("skills.preload")
        reload_enabled = get_setting("skills.reload.enabled")

        assert preload is not None
        assert isinstance(preload, list)
        assert reload_enabled is True

    def test_knowledge_skill_in_preload(self):
        """Verify knowledge skill is in preload list."""
        from common.mcp_core.settings import get_setting

        preload = get_setting("skills.preload", [])

        assert "knowledge" in preload, "knowledge skill should be preloaded"
        assert preload[0] == "knowledge", "knowledge skill should be first in preload"

    def test_knowledge_skill_manifest_valid(self):
        """Verify knowledge skill has valid manifest."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        manifest = registry.get_skill_manifest("knowledge")

        assert manifest is not None
        assert manifest.name == "knowledge"
        assert "knowledge" in manifest.tools_module
        assert "Project Cortex" in manifest.description


# =============================================================================
# Phase 13.10: Knowledge Skill Tests
# =============================================================================

class TestKnowledgeSkill:
    """Tests for Knowledge Skill (Project Cortex)."""

    def test_knowledge_skill_module_exists(self):
        """Verify knowledge skill module exists."""
        knowledge_tools = _SKILLS_ROOT / "knowledge" / "tools.py"
        assert knowledge_tools.exists(), f"Knowledge skill not found at {knowledge_tools}"

    def test_knowledge_tools_defined(self):
        """Verify knowledge tools are defined (no execution)."""
        import ast

        knowledge_tools_py = _SKILLS_ROOT / "knowledge" / "tools.py"
        content = knowledge_tools_py.read_text()
        tree = ast.parse(content)

        tool_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                tool_names.append(node.name)

        # Note: get_writing_memory moved to writer skill
        expected_tools = [
            "get_development_context",
            "consult_architecture_doc",
            "consult_language_expert",
            "get_language_standards",
            "list_supported_languages"
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Expected tool '{tool}' not found. Found: {tool_names}"

    def test_knowledge_skill_has_register(self):
        """Verify knowledge skill has register function."""
        import ast

        knowledge_tools_py = _SKILLS_ROOT / "knowledge" / "tools.py"
        content = knowledge_tools_py.read_text()
        tree = ast.parse(content)

        has_register = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "register":
                has_register = True
                break

        assert has_register, "Knowledge skill should have 'register' function"

    def test_knowledge_tools_never_execute(self):
        """Verify knowledge tools only read, never execute commands."""
        import ast

        knowledge_tools_py = _SKILLS_ROOT / "knowledge" / "tools.py"
        content = knowledge_tools_py.read_text()

        # Knowledge tools should NOT call subprocess
        assert "subprocess" not in content, "Knowledge tools should not execute commands"
        assert "os.system" not in content, "Knowledge tools should not execute commands"


# =============================================================================
# Phase 13.10: Writer Skill Tests
# =============================================================================

class TestWriterSkill:
    """Tests for Writer Skill (Writing Quality)."""

    def test_writer_skill_module_exists(self):
        """Verify writer skill module exists."""
        writer_tools = _SKILLS_ROOT / "writer" / "tools.py"
        assert writer_tools.exists(), f"Writer skill not found at {writer_tools}"

    def test_writer_tools_defined(self):
        """Verify writer tools are defined."""
        import ast

        writer_tools_py = _SKILLS_ROOT / "writer" / "tools.py"
        content = writer_tools_py.read_text()
        tree = ast.parse(content)

        tool_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                tool_names.append(node.name)

        expected_tools = [
            "lint_writing_style",
            "check_markdown_structure",
            "polish_text",
            "load_writing_memory",
            "run_vale_check"
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Expected tool '{tool}' not found. Found: {tool_names}"

    def test_writer_skill_has_register(self):
        """Verify writer skill has register function."""
        import ast

        writer_tools_py = _SKILLS_ROOT / "writer" / "tools.py"
        content = writer_tools_py.read_text()
        tree = ast.parse(content)

        has_register = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "register":
                has_register = True
                break

        assert has_register, "Writer skill should have 'register' function"


# =============================================================================
# Phase 13.10: Memory Skill Tests (Hippocampus Interface)
# =============================================================================

class TestMemorySkill:
    """Tests for Memory Skill (Vector-based Memory)."""

    def test_memory_skill_module_exists(self):
        """Verify memory skill module exists."""
        memory_tools_py = _SKILLS_ROOT / "memory" / "tools.py"
        assert memory_tools_py.exists(), f"Memory skill not found at {memory_tools_py}"

    def test_memory_tools_defined(self):
        """Verify memory tools are defined."""
        import ast

        memory_tools_py = _SKILLS_ROOT / "memory" / "tools.py"
        content = memory_tools_py.read_text()
        tree = ast.parse(content)

        tool_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                tool_names.append(node.name)

        expected_tools = [
            "remember_insight",
            "log_episode",
            "recall",
            "list_harvested_knowledge",
            "harvest_session_insight",
            "get_memory_stats"
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Expected tool '{tool}' not found. Found: {tool_names}"

    def test_memory_skill_has_register(self):
        """Verify memory skill has register function."""
        import ast

        memory_tools_py = _SKILLS_ROOT / "memory" / "tools.py"
        content = memory_tools_py.read_text()
        tree = ast.parse(content)

        has_register = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "register":
                has_register = True
                break

        assert has_register, "Memory skill should have 'register' function"

    def test_memory_skill_uses_chromadb(self):
        """Verify memory skill uses ChromaDB for vector storage."""
        import ast

        memory_tools_py = _SKILLS_ROOT / "memory" / "tools.py"
        content = memory_tools_py.read_text()

        # Should import chromadb
        assert "chromadb" in content, "Memory skill should use ChromaDB"

    def test_memory_skill_manifest_valid(self):
        """Verify memory skill has valid manifest."""
        from agent.core.skill_registry import get_skill_registry

        registry = get_skill_registry()
        manifest = registry.get_skill_manifest("memory")

        assert manifest is not None
        assert manifest.name == "memory"
        assert "Hippocampus" in manifest.description

    def test_memory_skill_in_preload(self):
        """Verify memory skill is in preload list."""
        from common.mcp_core.settings import get_setting

        preload = get_setting("skills.preload", [])
        assert "memory" in preload, "memory skill should be preloaded"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
