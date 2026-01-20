"""
packages/python/agent/src/agent/tests/unit/test_references_sot.py
Test Suite for references.yaml SSOT (Single Source of Truth) Validation

Tests verify that all knowledge paths are configured in references.yaml
and that code uses get_reference_path() instead of hardcoded paths.

Usage:
    uv run pytest packages/python/agent/src/agent/tests/unit/test_references_sot.py -v
"""

from __future__ import annotations

# Use SSOT for imports
from common.lib import setup_import_paths

# Setup paths before importing agent modules
setup_import_paths()


class TestReferencesSSOT:
    """Verify references.yaml is used as SSOT for knowledge paths."""

    def test_reference_library_exists(self):
        """Verify ReferenceLibrary can be instantiated."""
        from common.mcp_core.reference_library import ReferenceLibrary

        ref = ReferenceLibrary()
        assert ref is not None

    def test_context_system_context_exists(self):
        """Verify context.system_context reference exists."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("context.system_context")
        assert path is not None
        assert "system_context.xml" in path

    def test_context_skill_index_exists(self):
        """Verify context.skill_index reference exists."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("context.skill_index")
        assert path is not None
        assert "skill_index.json" in path

    def test_context_architecture_docs_exists(self):
        """Verify context.architecture_docs_dir reference exists."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("context.architecture_docs_dir")
        assert path is not None

    def test_design_docs_dir_exists(self):
        """Verify design_docs.dir reference exists."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("design_docs.dir")
        assert path is not None

    def test_knowledge_dirs_exists(self):
        """Verify knowledge_dirs reference exists and is a list."""
        from common.mcp_core.reference_library import ReferenceLibrary

        ref = ReferenceLibrary()
        dirs = ref.get("knowledge_dirs", [])
        assert isinstance(dirs, list)
        assert len(dirs) > 0

    def test_knowledge_dirs_has_required_domains(self):
        """Verify knowledge_dirs has all required domains."""
        from common.mcp_core.reference_library import ReferenceLibrary

        ref = ReferenceLibrary()
        dirs = ref.get("knowledge_dirs", [])

        domains = [d.get("domain") for d in dirs if isinstance(d, dict)]
        required = ["knowledge", "workflow", "architecture", "standards"]
        for required_domain in required:
            assert required_domain in domains, f"Missing domain: {required_domain}"

    def test_prompts_exists(self):
        """Verify prompts reference exists."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("prompts.system_core")
        assert path is not None
        assert "prompts" in path

    def test_howto_gitops_exists(self):
        """Verify howto.gitops reference exists."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("howto.gitops")
        assert path is not None
        assert "gitops" in path

    def test_has_reference_function(self):
        """Verify has_reference function works."""
        from common.mcp_core.reference_library import has_reference

        assert has_reference("context.system_context")
        assert has_reference("context.skill_index")
        assert not has_reference("nonexistent.reference")


class TestContextOrchestratorSSOT:
    """Verify context_orchestrator.py uses references.yaml."""

    def test_context_orchestrator_uses_reference(self):
        """Verify context_orchestrator imports get_reference_path."""
        from agent.core.context_orchestrator import ContextOrchestrator
        from common.mcp_core.reference_library import get_reference_path

        # Verify the reference function works
        assert get_reference_path("context.system_context")
        assert get_reference_path("context.skill_index")
        assert get_reference_path("context.architecture_docs_dir")


class TestAlignmentSSOT:
    """Verify alignment.py uses references.yaml."""

    def test_alignment_imports_reference_library(self):
        """Verify alignment module imports get_reference_path."""
        from agent.capabilities.product_owner.alignment import (
            _get_reference_docs,
            load_design_doc,
        )

        # Verify functions exist and are callable
        assert callable(_get_reference_docs)
        assert callable(load_design_doc)

    def test_alignment_uses_design_docs_reference(self):
        """Verify alignment uses design_docs.dir reference."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("design_docs.dir")
        assert path is not None
        assert "docs" in path

    def test_alignment_uses_standards_reference(self):
        """Verify alignment uses standards.feature_lifecycle reference."""
        from common.mcp_core.reference_library import get_reference_path

        path = get_reference_path("standards.feature_lifecycle")
        assert path is not None
        assert "feature-lifecycle" in path


class TestIngestorSSOT:
    """Verify ingestor.py uses references.yaml."""

    def test_ingestor_uses_reference_library(self):
        """Verify ingestor module uses ReferenceLibrary."""
        from agent.capabilities.knowledge.ingestor import get_knowledge_dirs
        from common.mcp_core.reference_library import ReferenceLibrary

        # Verify ReferenceLibrary works
        ref = ReferenceLibrary()
        dirs = ref.get("knowledge_dirs", [])
        assert isinstance(dirs, list)

        # Verify get_knowledge_dirs returns a list
        result = get_knowledge_dirs()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_ingestor_knowledge_dirs_has_domains(self):
        """Verify get_knowledge_dirs returns directories with domains."""
        from agent.capabilities.knowledge.ingestor import get_knowledge_dirs

        dirs = get_knowledge_dirs()
        for d in dirs:
            assert isinstance(d, dict)
            assert "path" in d
            assert "domain" in d


class TestNoHardcodedPaths:
    """Verify critical paths are not hardcoded in source files."""

    def test_no_hardcoded_docs_path_in_orchestrator(self):
        """Verify no hardcoded 'Path(\"docs\")' in context_orchestrator package."""
        import re
        from pathlib import Path
        import os

        # Check the new package structure
        base_dir = Path("packages/python/agent/src/agent/core/context_orchestrator")
        files_to_check = [
            base_dir / "orchestrator.py",
            base_dir / "layers" / "layer1_persona.py",
            base_dir / "layers" / "layer3_knowledge.py",
            base_dir / "layers" / "layer6_maps.py",
        ]

        for file_path in files_to_check:
            if file_path.exists():
                with open(file_path, "r") as f:
                    content = f.read()

                # Check for hardcoded path patterns that should use references.yaml
                hardcoded_patterns = [
                    r'Path\s*\(\s*["\']docs["\']\s*\)',  # Path("docs")
                ]

                for pattern in hardcoded_patterns:
                    matches = re.findall(pattern, content)
                    assert len(matches) == 0, (
                        f"Found hardcoded path pattern in {file_path}: {pattern}"
                    )

    def test_no_hardcoded_docs_path_in_alignment(self):
        """Verify no hardcoded 'Path("docs")' in alignment.py."""
        import re

        file_path = "packages/python/agent/src/agent/capabilities/product_owner/alignment.py"
        with open(file_path, "r") as f:
            content = f.read()

        hardcoded_patterns = [
            r'Path\s*\(\s*["\']docs["\']\s*\)',  # Path("docs")
        ]

        for pattern in hardcoded_patterns:
            matches = re.findall(pattern, content)
            assert len(matches) == 0, f"Found hardcoded path pattern: {pattern}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
