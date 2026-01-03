"""
src/agent/tests/test_mcp_dependencies.py
Tests to verify MCP server dependencies are properly configured.

These tests catch issues like:
- Missing workspace dependencies in MCP server pyproject.toml
- Import failures when running as MCP server
"""
import pytest
import subprocess
import sys
from pathlib import Path


class TestMcpServerDependencies:
    """Test that MCP servers can import their required dependencies."""

    def test_orchestrator_can_import_common_mcp_core(self):
        """Orchestrator should be able to import common.mcp_core modules."""
        # This simulates what happens when orchestrator MCP server starts
        result = subprocess.run(
            ["uv", "run", "python", "-c",
             "from common.mcp_core.gitops import get_project_root; print('OK')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"Orchestrator failed to import common.mcp_core:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_executor_can_import_common_mcp_core(self):
        """Executor MCP server should be able to import common.mcp_core."""
        result = subprocess.run(
            ["uv", "run", "python", "-c",
             "from common.mcp_core.gitops import get_project_root; print('OK')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"Executor failed to import common.mcp_core:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_coder_can_import_common_mcp_core(self):
        """Coder MCP server should be able to import common.mcp_core."""
        result = subprocess.run(
            ["uv", "run", "python", "-c",
             "from common.mcp_core.gitops import get_project_root; print('OK')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"Coder failed to import common.mcp_core:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_agent_skill_registry_imports(self):
        """agent.core.skill_registry should import successfully."""
        result = subprocess.run(
            ["uv", "run", "python", "-c",
             "from agent.core.skill_registry import SkillRegistry; print('OK')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"agent.core.skill_registry import failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout

    def test_executor_git_ops_module_imports(self):
        """executor's git_ops module should import successfully (without MCP decorator issues)."""
        result = subprocess.run(
            ["uv", "run", "python", "-c",
             "import mcp_server.executor.git_ops as g; print('OK')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent
        )
        assert result.returncode == 0, (
            f"mcp_server.executor.git_ops module import failed:\n{result.stderr}"
        )
        assert "OK" in result.stdout


class TestPyprojectDependencies:
    """Test that pyproject.toml files have correct dependency declarations."""

    def test_executor_has_common_dependency(self):
        """executor pyproject.toml should include omni-dev-fusion-common."""
        pyproject_path = (
            Path(__file__).parent.parent.parent.parent /
            "src/mcp_server/executor/pyproject.toml"
        )
        content = pyproject_path.read_text()
        assert "omni-dev-fusion-common" in content, (
            "executor/pyproject.toml should include omni-dev-fusion-common in dependencies"
        )

    def test_coder_has_common_dependency(self):
        """coder pyproject.toml should include omni-dev-fusion-common."""
        pyproject_path = (
            Path(__file__).parent.parent.parent.parent /
            "src/mcp_server/coder/pyproject.toml"
        )
        content = pyproject_path.read_text()
        assert "omni-dev-fusion-common" in content, (
            "coder/pyproject.toml should include omni-dev-fusion-common in dependencies"
        )

    def test_executor_sources_matches_dependencies(self):
        """executor [tool.uv.sources] should have corresponding entries in [dependencies]."""
        pyproject_path = (
            Path(__file__).parent.parent.parent.parent /
            "src/mcp_server/executor/pyproject.toml"
        )
        content = pyproject_path.read_text()

        # Check if sources declares workspace deps
        if "[tool.uv.sources]" in content:
            # Extract source dependencies
            sources_section = content.split("[tool.uv.sources]")[1]
            # Find the next section
            for marker in ["[project]", "[build-system]", "[tool.", "["]:
                if marker in sources_section:
                    sources_section = sources_section.split(marker)[0]
                    break

            source_deps = []
            for line in sources_section.split("\n"):
                if "= { workspace = true }" in line:
                    # Extract package name from line
                    pkg = line.strip().split("=")[0].strip()
                    source_deps.append(pkg)

            # Check each source dep is also in dependencies
            if "[dependencies]" in content:
                deps_section = content.split("[dependencies]")[1]
                for marker in ["[project]", "[build-system]", "[tool.", "["]:
                    if marker in deps_section:
                        deps_section = deps_section.split(marker)[0]
                        break

                for dep in source_deps:
                    assert dep in deps_section, (
                        f"executor: '{dep}' is in [tool.uv.sources] but not in [dependencies]"
                    )

    def test_coder_sources_matches_dependencies(self):
        """coder [tool.uv.sources] should have corresponding entries in [dependencies]."""
        pyproject_path = (
            Path(__file__).parent.parent.parent.parent /
            "src/mcp_server/coder/pyproject.toml"
        )
        content = pyproject_path.read_text()

        if "[tool.uv.sources]" in content:
            sources_section = content.split("[tool.uv.sources]")[1]
            for marker in ["[project]", "[build-system]", "[tool.", "["]:
                if marker in sources_section:
                    sources_section = sources_section.split(marker)[0]
                    break

            source_deps = []
            for line in sources_section.split("\n"):
                if "= { workspace = true }" in line:
                    pkg = line.strip().split("=")[0].strip()
                    source_deps.append(pkg)

            if "[dependencies]" in content:
                deps_section = content.split("[dependencies]")[1]
                for marker in ["[project]", "[build-system]", "[tool.", "["]:
                    if marker in deps_section:
                        deps_section = deps_section.split(marker)[0]
                        break

                for dep in source_deps:
                    assert dep in deps_section, (
                        f"coder: '{dep}' is in [tool.uv.sources] but not in [dependencies]"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
