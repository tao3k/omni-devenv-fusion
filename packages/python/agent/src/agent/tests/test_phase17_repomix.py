"""
src/agent/tests/test_phase17_repomix.py
Phase 17: Repomix-Powered Knowledge Ingestion Tests

Tests the Phase 17 enhancement where KnowledgeIngestor parses
repomix-generated XML for standardized knowledge ingestion.

Usage:
    python -m pytest packages/python/agent/src/agent/tests/test_phase17_repomix.py -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from agent.capabilities.knowledge_ingestor import (
    ingest_from_repomix_xml,
    REPOMIX_XML_PATH,
)


# Sample XML content matching repomix format
SAMPLE_REPOMIX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<files>
  <file path="agent/knowledge/test-doc.md">
# Test Document

This is a test document for Phase 17.
  </file>
  <file path="agent/knowledge/standards/test-standards.md">
# Test Standards

Keywords: python, testing, standards

## Section

Some content here.
  </file>
</files>
"""


class TestRepomixIngestor:
    """Test Phase 17 Repomix XML ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_from_repomix_xml_missing_file(self):
        """Verify error when XML file doesn't exist."""
        with patch('agent.capabilities.knowledge_ingestor.get_vector_memory') as mock_vm:
            mock_vm.return_value.client = MagicMock()

            result = await ingest_from_repomix_xml("/nonexistent/path.xml")

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_ingest_parses_xml_correctly(self):
        """Verify XML is parsed and files are extracted."""
        # Create a temporary XML file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(SAMPLE_REPOMIX_XML)
            temp_path = f.name

        try:
            with patch('agent.capabilities.knowledge_ingestor.get_vector_memory') as mock_vm:
                mock_vm.return_value.add = AsyncMock(return_value=True)

                result = await ingest_from_repomix_xml(temp_path)

                assert result["success"] is True
                assert result["total"] == 2  # Two files in sample XML
                assert result["ingested"] == 2
                assert result["failed"] == 0
                # Verify VectorStore.add was called twice
                assert mock_vm.return_value.add.call_count == 2

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_domain_extraction_from_path(self):
        """Verify domain is correctly extracted from file path."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<files>
  <file path="agent/skills/knowledge/standards/python.md">
# Python Standards
Content
  </file>
  <file path="agent/how-to/gitops.md">
# GitOps Guide
Content
  </file>
  <file path="docs/explanation/architecture.md">
# Architecture
Content
  </file>
</files>
"""

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_path = f.name

        try:
            with patch('agent.capabilities.knowledge_ingestor.get_vector_memory') as mock_vm:
                mock_vm.return_value.add = AsyncMock(return_value=True)

                result = await ingest_from_repomix_xml(temp_path)

                assert result["success"] is True
                # Check that add was called with correct domains
                calls = mock_vm.return_value.add.call_args_list
                domains = [call[1]["metadatas"][0]["domain"] for call in calls]
                assert "standards" in domains
                assert "workflow" in domains
                assert "architecture" in domains

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_title_extraction_from_content(self):
        """Verify title is extracted from first H1."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<files>
  <file path="test.md">
# My Custom Title

Some content here.
  </file>
</files>
"""

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_path = f.name

        try:
            with patch('agent.capabilities.knowledge_ingestor.get_vector_memory') as mock_vm:
                mock_vm.return_value.add = AsyncMock(return_value=True)

                result = await ingest_from_repomix_xml(temp_path)

                # Check title was extracted
                call = mock_vm.return_value.add.call_args
                title = call[1]["metadatas"][0]["title"]
                assert title == "My Custom Title"

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_keywords_extraction(self):
        """Verify keywords are extracted from content."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<files>
  <file path="test.md">
# Test Doc

Keywords: python, testing, standards, ruff

Content here.
  </file>
</files>
"""

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_path = f.name

        try:
            with patch('agent.capabilities.knowledge_ingestor.get_vector_memory') as mock_vm:
                mock_vm.return_value.add = AsyncMock(return_value=True)

                result = await ingest_from_repomix_xml(temp_path)

                # Check keywords were extracted
                call = mock_vm.return_value.add.call_args
                keywords = call[1]["metadatas"][0]["keywords"]
                assert "python" in keywords
                assert "testing" in keywords
                assert "standards" in keywords
                assert "ruff" in keywords

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_empty_files_skipped(self):
        """Verify empty file nodes are skipped."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<files>
  <file path="empty.md"></file>
  <file path="valid.md">
# Valid Doc
Content here.
  </file>
</files>
"""

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_path = f.name

        try:
            with patch('agent.capabilities.knowledge_ingestor.get_vector_memory') as mock_vm:
                mock_vm.return_value.add = AsyncMock(return_value=True)

                result = await ingest_from_repomix_xml(temp_path)

                assert result["success"] is True
                assert result["total"] == 1  # Only valid file
                assert mock_vm.return_value.add.call_count == 1

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_id_generation(self):
        """Verify unique ID is generated from filename."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<files>
  <file path="agent/knowledge/my-test-document.md">
# My Test
Content
  </file>
</files>
"""

        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(xml_content)
            temp_path = f.name

        try:
            with patch('agent.capabilities.knowledge_ingestor.get_vector_memory') as mock_vm:
                mock_vm.return_value.add = AsyncMock(return_value=True)

                result = await ingest_from_repomix_xml(temp_path)

                # Check ID generation (spaces/hyphens to underscores)
                call = mock_vm.return_value.add.call_args
                file_id = call[1]["ids"][0]
                assert "knowledge-my_test_document" == file_id

        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_default_xml_path(self):
        """Verify default REPOMIX_XML_PATH is used when none specified."""
        # Mock the project root to return a temp directory
        with patch('agent.capabilities.knowledge_ingestor.get_project_root') as mock_root:
            mock_root.return_value = Path("/nonexistent")

            result = await ingest_from_repomix_xml()

            # Should try to use REPOMIX_XML_PATH
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_xml_parse_error_handling(self):
        """Verify XML parse errors are handled gracefully."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write("This is not valid XML <")
            temp_path = f.name

        try:
            result = await ingest_from_repomix_xml(temp_path)

            assert result["success"] is False
            assert "parse error" in result["error"].lower()

        finally:
            Path(temp_path).unlink()


class TestRepomixConstants:
    """Test Phase 17 constants."""

    def test_repomix_xml_path(self):
        """Verify REPOMIX_XML_PATH is set correctly."""
        assert REPOMIX_XML_PATH == ".data/project_knowledge.xml"
