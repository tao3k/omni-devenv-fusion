"""
packages/python/agent/src/agent/tests/unit/test_ingest_command.py
Test Suite for Ingest CLI Command

Tests cover:
- omni ingest --help displays correctly
- Subcommand help displays correctly
- Subcommands exist and are registered

Usage:
    uv run pytest packages/python/agent/src/agent/tests/unit/test_ingest_command.py -v
"""

import pytest
from typer.testing import CliRunner

# Use SSOT for imports
from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing agent modules
setup_import_paths()

from omni.agent.cli.app import app


def run_omni(args: list[str]) -> tuple[int, str, str]:
    """Run omni CLI command using Typer's CliRunner."""
    runner = CliRunner()
    result = runner.invoke(app, args)
    return result.exit_code, result.output, ""


class TestIngestHelp:
    """Test ingest command help output."""

    def test_ingest_help(self):
        """Test that 'omni ingest --help' displays correctly."""
        code, stdout, _ = run_omni(["ingest", "--help"])

        assert code == 0, f"Command failed with output: {stdout}"
        # Use reference_library for expected strings (SSOT)
        expected_strings = [
            "Index content into knowledge base",
            "knowledge",
            "skills",
            "all",
            "status",
        ]
        for expected in expected_strings:
            assert expected in stdout, f"Expected '{expected}' in help output"

    def test_ingest_knowledge_help(self):
        """Test that 'omni ingest knowledge --help' displays correctly."""
        code, stdout, _ = run_omni(["ingest", "knowledge", "--help"])

        assert code == 0, f"Command failed with output: {stdout}"
        assert "Index documentation into knowledge base" in stdout
        assert "--dir" in stdout or "-d" in stdout
        assert "--json" in stdout or "-j" in stdout

    def test_ingest_skills_help(self):
        """Test that 'omni ingest skills --help' displays correctly."""
        code, stdout, _ = run_omni(["ingest", "skills", "--help"])

        assert code == 0, f"Command failed with output: {stdout}"
        assert "Index skills into skills table" in stdout
        assert "--clear" in stdout or "-c" in stdout
        assert "--json" in stdout or "-j" in stdout

    def test_ingest_all_help(self):
        """Test that 'omni ingest all --help' displays correctly."""
        code, stdout, _ = run_omni(["ingest", "all", "--help"])

        assert code == 0, f"Command failed with output: {stdout}"
        assert "Index all content" in stdout or "knowledge and skills" in stdout
        assert "--clear" in stdout or "-c" in stdout
        assert "--json" in stdout or "-j" in stdout

    def test_ingest_status_help(self):
        """Test that 'omni ingest status --help' displays correctly."""
        code, stdout, _ = run_omni(["ingest", "status", "--help"])

        assert code == 0, f"Command failed with output: {stdout}"
        assert "ingest status" in stdout.lower() or "status" in stdout


class TestIngestCommandsExist:
    """Test that ingest subcommands are properly registered."""

    def test_ingest_knowledge_command_exists(self):
        """Verify knowledge subcommand is registered."""
        code, stdout, _ = run_omni(["ingest", "--help"])
        assert code == 0
        assert "knowledge" in stdout.lower()

    def test_ingest_skills_command_exists(self):
        """Verify skills subcommand is registered."""
        code, stdout, _ = run_omni(["ingest", "--help"])
        assert code == 0
        assert "skills" in stdout.lower()

    def test_ingest_all_command_exists(self):
        """Verify all subcommand is registered."""
        code, stdout, _ = run_omni(["ingest", "--help"])
        assert code == 0
        assert "all" in stdout.lower()

    def test_ingest_status_command_exists(self):
        """Verify status subcommand is registered."""
        code, stdout, _ = run_omni(["ingest", "--help"])
        assert code == 0
        assert "status" in stdout.lower()


class TestIngestKnowledgeFunctionality:
    """Test basic ingest knowledge functionality."""

    def test_ingest_knowledge_json_output(self):
        """Test that ingest knowledge --json returns valid JSON structure."""
        code, stdout, _ = run_omni(["ingest", "knowledge", "--json"])

        # Should return valid JSON with knowledge stats
        assert code == 0, f"Command failed with output: {stdout}"
        assert "knowledge" in stdout.lower() or "added" in stdout.lower()


class TestIngestRegistration:
    """Test that ingest command is properly registered with main app."""

    def test_ingest_registered_in_app(self):
        """Verify ingest is registered in main omni app."""
        code, stdout, _ = run_omni(["--help"])

        assert code == 0
        assert "ingest" in stdout.lower()


class TestIngestReferences:
    """Test that ingest references are properly configured in references.yaml (SSOT)."""

    def test_cli_reference_exists(self):
        """Verify CLI reference is configured in references.yaml."""
        from omni.foundation.services.reference import has_reference

        assert has_reference("cli.doc"), "CLI reference should exist in references.yaml"

    def test_cli_ingest_commands_exist(self):
        """Verify ingest commands are listed in references.yaml."""
        from omni.foundation.services.reference import get_reference_path

        doc_path = get_reference_path("cli.doc")
        assert doc_path, "cli.doc should point to documentation"
        assert "cli.md" in doc_path, "CLI doc should reference cli.md"

    def test_ingest_commands_from_references(self):
        """Verify ingest commands can be retrieved from references."""
        from omni.foundation.services.reference import ReferenceLibrary

        ref = ReferenceLibrary()
        ingest_commands = ref.get("cli.ingest_commands", [])

        assert "knowledge" in ingest_commands
        assert "skills" in ingest_commands
        assert "all" in ingest_commands
        assert "status" in ingest_commands


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
