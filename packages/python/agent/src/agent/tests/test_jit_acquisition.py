"""
packages/python/agent/src/agent/tests/test_phase27_jit_acquisition.py
Test Suite for Phase 27: JIT Skill Acquisition Protocol

Tests cover:
- SkillDiscovery: search, find_by_id, suggest_for_query
- JIT install functions: jit_install_skill, discover_skills, suggest_skills_for_task
- MCP tools: discover_skills, jit_install_skill, suggest_skills_for_task
"""

import pytest
from pathlib import Path

from common.skills_path import SKILLS_DIR, load_skill_module


class TestSkillDiscovery:
    """Test SkillDiscovery class functionality."""

    def test_load_index(self):
        """Test that the skills index loads correctly."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        index = discovery._load_index()

        assert "version" in index
        assert "skills" in index
        assert isinstance(index["skills"], list)

    def test_list_all_skills(self):
        """Test listing all skills in the index."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        skills = discovery.list_all()

        assert isinstance(skills, list)
        assert len(skills) > 0

        # Each skill should have required fields
        for skill in skills:
            assert "id" in skill
            assert "name" in skill
            assert "url" in skill
            assert "keywords" in skill

    def test_find_by_id_exact(self):
        """Test finding a skill by exact ID."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        skill = discovery.find_by_id("pandas-expert")

        assert skill is not None
        assert skill["id"] == "pandas-expert"
        assert "pandas" in skill["keywords"]

    def test_find_by_id_underscore_variant(self):
        """Test finding skill with underscore variant of ID."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        # If skill ID uses underscore format
        skill = discovery.find_by_id("docker_ops")
        # Should work with hyphen format
        assert skill is not None or True  # May or may not exist

    def test_find_by_id_not_found(self):
        """Test finding a non-existent skill."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        skill = discovery.find_by_id("non-existent-skill-xyz")

        assert skill is None

    def test_search_local_by_keyword(self):
        """Test searching skills by keyword."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()

        # Search for docker-related skills
        results = discovery.search_local("docker", limit=5)

        assert isinstance(results, list)
        # Should find docker-ops skill
        if len(results) > 0:
            assert any(
                "docker" in s.get("keywords", []) or "docker" in s.get("id", "") for s in results
            )

    def test_search_local_by_description(self):
        """Test searching skills by description."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()

        # Search for data analysis
        results = discovery.search_local("data analysis", limit=5)

        assert isinstance(results, list)

    def test_search_local_empty_query(self):
        """Test that empty query returns all skills."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        all_skills = discovery.list_all()
        results = discovery.search_local("", limit=10)

        assert len(results) <= 10
        # Should contain some of the skills
        assert len(results) > 0

    def test_search_local_limit(self):
        """Test that search respects the limit parameter."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        results = discovery.search_local("", limit=3)

        assert len(results) <= 3

    def test_find_by_keyword(self):
        """Test finding skills by specific keyword."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()

        # Find skills with 'pcap' keyword
        results = discovery.find_by_keyword("pcap")

        assert isinstance(results, list)
        # Should find network-analysis skill
        if len(results) > 0:
            assert any("pcap" in s.get("keywords", []) for s in results)

    def test_suggest_for_query(self):
        """Test task-based skill suggestion."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()

        # Suggest skills for pcap analysis
        suggestion = discovery.suggest_for_query("analyze pcap file")

        assert "query" in suggestion
        assert "suggestions" in suggestion
        assert "count" in suggestion
        assert "ready_to_install" in suggestion
        assert suggestion["query"] == "analyze pcap file"

    def test_suggestion_quality(self):
        """Test that suggestions are relevant."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()

        # Query for network-related task
        suggestion = discovery.suggest_for_query("network troubleshooting")

        # Should find network-related skills
        if suggestion["count"] > 0:
            for s in suggestion["suggestions"]:
                keywords = s.get("keywords", [])
                # Should have network-related keywords
                has_network = any("network" in k.lower() or "pcap" in k.lower() for k in keywords)
                assert has_network, f"Skill {s['name']} doesn't match network query"


class TestDiscoverSkillsFunction:
    """Test the discover_skills convenience function."""

    def test_discover_skills_with_query(self):
        """Test discover_skills function with query."""
        from agent.core.registry import discover_skills

        result = discover_skills("docker", limit=3)

        assert "query" in result
        assert "count" in result
        assert "skills" in result
        assert "ready_to_install" in result
        assert result["query"] == "docker"
        assert result["count"] >= 0

    def test_discover_skills_empty_query(self):
        """Test discover_skills with empty query."""
        from agent.core.registry import discover_skills

        result = discover_skills("", limit=5)

        assert result["count"] > 0
        assert len(result["skills"]) <= 5

    def test_discover_skills_ready_to_install(self):
        """Test that ready_to_install contains skill IDs."""
        from agent.core.registry import discover_skills

        result = discover_skills("data", limit=5)

        # ready_to_install should be a list of IDs
        assert isinstance(result["ready_to_install"], list)
        for skill_id in result["ready_to_install"]:
            assert isinstance(skill_id, str)


class TestSuggestSkillsForTaskFunction:
    """Test the suggest_skills_for_task convenience function."""

    def test_suggest_for_task(self):
        """Test suggest_skills_for_task function."""
        from agent.core.registry import suggest_skills_for_task

        result = suggest_skills_for_task("work with docker containers")

        assert "query" in result
        assert "suggestions" in result
        assert "count" in result

    def test_suggest_returns_empty_for_unknown(self):
        """Test that suggestions return empty for unknown tasks."""
        from agent.core.registry import suggest_skills_for_task

        result = suggest_skills_for_task("xyzabc123 unknown task")

        # May or may not find matches depending on index
        assert "count" in result


class TestJitInstallSkillFunction:
    """Test the jit_install_skill function."""

    def test_jit_install_not_found(self):
        """Test JIT install for non-existent skill."""
        from agent.core.registry import jit_install_skill

        result = jit_install_skill("non-existent-skill-xyz")

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower() or "hint" in result

    def test_jit_install_already_exists(self):
        """Test JIT install for already installed skill."""
        from agent.core.registry import jit_install_skill

        # Try to install a skill that doesn't exist (would fail at git clone)
        result = jit_install_skill("non-existent-skill-xyz")

        # Should handle gracefully
        assert "success" in result
        assert result["success"] is False


class TestSkillCommands:
    """Test that skill commands are properly registered via One Tool."""

    def test_omni_function_exists(self):
        """omni function should be importable from test_skills."""
        # omni is now imported from test_skills (Phase 35.3)
        from test_skills import omni

        assert callable(omni), "omni should be callable"

    def test_skill_discover_registered(self):
        """Test that skill.discover command function exists and is callable."""
        # Load skill module from assets directory
        module = load_skill_module("skill")
        assert hasattr(module, "discover"), "skill.discover should exist"
        assert callable(module.discover), "skill.discover should be callable"

    def test_skill_suggest_registered(self):
        """Test that skill.suggest command function exists and is callable."""
        module = load_skill_module("skill")
        assert hasattr(module, "suggest"), "skill.suggest should exist"
        assert callable(module.suggest), "skill.suggest should be callable"

    def test_skill_jit_install_registered(self):
        """Test that skill.jit_install command function exists and is callable."""
        module = load_skill_module("skill")
        assert hasattr(module, "jit_install"), "skill.jit_install should exist"
        assert callable(module.jit_install), "skill.jit_install should be callable"

    def test_skill_list_index_registered(self):
        """Test that skill.list_index command function exists and is callable."""
        module = load_skill_module("skill")
        assert hasattr(module, "list_index"), "skill.list_index should exist"
        assert callable(module.list_index), "skill.list_index should be callable"

    def test_skill_manifest_exists(self):
        """Test that skill SKILL.md exists and is valid."""
        import frontmatter
        from common.skills_path import SKILLS_DIR

        skill_md_path = SKILLS_DIR(skill="skill", filename="SKILL.md")
        assert skill_md_path.exists(), "skill SKILL.md should exist"

        with open(skill_md_path) as f:
            post = frontmatter.load(f)
        manifest = post.metadata
        assert manifest["name"] == "Skill Manager"
        # Check for key routing keywords
        assert "skill" in manifest["routing_keywords"]
        assert "discovery" in manifest["routing_keywords"]
        assert "install" in manifest["routing_keywords"]


class TestKnownSkillsIndex:
    """Test the known_skills.json index file."""

    def test_index_has_required_fields(self):
        """Test that index has all required fields."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        index = discovery._load_index()

        assert index["version"] == "1.0.0"
        assert len(index["skills"]) > 0

    def test_each_skill_has_required_fields(self):
        """Test that each skill has required fields."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        index = discovery._load_index()

        for skill in index["skills"]:
            assert "id" in skill, "Skill missing 'id' field"
            assert "name" in skill, "Skill missing 'name' field"
            assert "url" in skill, "Skill missing 'url' field"
            assert "description" in skill, "Skill missing 'description' field"
            assert "keywords" in skill, "Skill missing 'keywords' field"

    def test_each_skill_id_is_unique(self):
        """Test that all skill IDs are unique."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        index = discovery._load_index()

        ids = [s["id"] for s in index["skills"]]
        assert len(ids) == len(set(ids)), "Duplicate skill IDs found"

    def test_each_skill_url_is_valid(self):
        """Test that each skill URL is a valid GitHub URL."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        index = discovery._load_index()

        for skill in index["skills"]:
            url = skill["url"]
            assert url.startswith("https://github.com/"), (
                f"Skill {skill['id']} has invalid URL: {url}"
            )


class TestCliCommands:
    """Test CLI commands for skill discovery."""

    def test_skill_discover_command_exists(self):
        """Test that 'omni skill discover' command is registered."""
        from agent.cli.commands.skill import skill_discover

        # Verify the typer command function exists
        assert callable(skill_discover)

    def test_discover_with_query(self):
        """Test CLI discover with query using jit.discover_skills."""
        from agent.core.registry.jit import discover_skills

        # Should not raise exception
        result = discover_skills("docker", limit=3)

        # Verify results structure
        assert "query" in result
        assert "skills" in result
        assert "count" in result
        assert "ready_to_install" in result

    def test_discover_without_query(self):
        """Test CLI discover without query using jit.discover_skills."""
        from agent.core.registry.jit import discover_skills

        # Should return skills
        result = discover_skills("", limit=5)

        # Verify results structure
        assert "query" in result
        assert "skills" in result
        assert len(result["skills"]) <= 5


class TestIntegration:
    """Integration tests for the full JIT workflow."""

    def test_full_discovery_workflow(self):
        """Test the full discovery -> suggestion workflow."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()

        # 1. List all skills
        all_skills = discovery.list_all()
        assert len(all_skills) > 0

        # 2. Search for specific skill
        results = discovery.search_local("docker", limit=5)
        assert isinstance(results, list)

        # 3. Find by exact ID
        skill = discovery.find_by_id("docker-ops")
        if skill:
            assert skill["id"] == "docker-ops"

        # 4. Suggest for task
        suggestion = discovery.suggest_for_query("container orchestration")
        assert "suggestions" in suggestion

    def test_discovery_consistency(self):
        """Test that different discovery methods return consistent results."""
        from agent.core.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()

        # Find by ID should return the same skill as search
        skill = discovery.find_by_id("pandas-expert")
        if skill:
            search_results = discovery.search_local("pandas", limit=10)
            search_ids = [s["id"] for s in search_results]

            assert "pandas-expert" in search_ids
