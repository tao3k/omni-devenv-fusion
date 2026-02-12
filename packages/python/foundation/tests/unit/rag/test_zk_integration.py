"""
Tests for zk_integration module.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path


class TestZkClient:
    """Test ZkClient class."""

    def test_client_initialization(self):
        """Test client can be initialized."""
        from omni.rag.zk_integration import ZkClient

        client = ZkClient(notebook_dir="/tmp/test")
        assert client.notebook_dir == "/tmp/test"

    def test_client_default_directory(self):
        """Test client uses current directory by default."""
        from omni.rag.zk_integration import ZkClient

        import os

        original_cwd = os.getcwd()
        try:
            client = ZkClient()
            assert client.notebook_dir is None
        finally:
            os.chdir(original_cwd)

    def test_zk_note_from_dict(self):
        """Test ZkNote creation from dict."""
        from omni.rag.zk_client import ZkNote

        data = {
            "filenameStem": "test-note",
            "path": "test-note.md",
            "absPath": "/path/to/test-note.md",
            "title": "Test Note",
            "link": "[Test Note](test-note)",
            "lead": "A test note",
            "body": "Full content",
            "tags": ["tag1", "tag2"],
            "created": "2026-02-05T10:00:00Z",
            "modified": "2026-02-05T12:00:00Z",
        }

        note = ZkNote.from_dict(data)

        assert note.filename_stem == "test-note"
        assert note.title == "Test Note"
        assert len(note.tags) == 2
        assert note.tags[0] == "tag1"

    def test_zk_note_to_dict(self):
        """Test ZkNote conversion to dict."""
        from omni.rag.zk_client import ZkNote

        note = ZkNote(
            path="test.md",
            abs_path="/path/to/test.md",
            title="Test",
            link="[Test](test)",
        )

        data = note.to_dict()

        assert data["path"] == "test.md"
        assert data["title"] == "Test"

    def test_zk_link_from_dict(self):
        """Test ZkLink creation from dict."""
        from omni.rag.zk_integration import ZkLink

        data = {
            "source": "note-a",
            "sourceTitle": "Note A",
            "target": "note-b",
            "targetTitle": "Note B",
            "type": "wiki",
        }

        link = ZkLink.from_dict(data)

        assert link.source == "note-a"
        assert link.target == "note-b"
        assert link.link_type == "wiki"


class TestZkIntegrationAsync:
    """Test async methods of ZkClient."""

    @pytest.mark.asyncio
    async def test_list_notes_with_results(self):
        """Test listing notes with mock results."""
        from omni.rag.zk_integration import ZkClient, ZkNote

        client = ZkClient(notebook_dir="/tmp/test")

        mock_data = [
            {
                "filename": "note1.md",
                "filenameStem": "note1",
                "path": "note1.md",
                "absPath": "/tmp/test/note1.md",
                "title": "Note 1",
                "link": "[Note 1](note1)",
                "tags": ["tag1"],
            },
            {
                "filename": "note2.md",
                "filenameStem": "note2",
                "path": "note2.md",
                "absPath": "/tmp/test/note2.md",
                "title": "Note 2",
                "link": "[Note 2](note2)",
                "tags": ["tag2"],
            },
        ]

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_data

            notes = await client.list_notes(match="test", limit=10)

            assert len(notes) == 2
            assert notes[0].title == "Note 1"
            assert notes[1].title == "Note 2"

    @pytest.mark.asyncio
    async def test_list_notes_empty(self):
        """Test listing notes with empty results."""
        from omni.rag.zk_integration import ZkClient

        client = ZkClient(notebook_dir="/tmp/test")

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = []

            notes = await client.list_notes(match="nonexistent")

            assert len(notes) == 0

    @pytest.mark.asyncio
    async def test_list_notes_handles_error(self):
        """Test listing notes handles errors gracefully."""
        from omni.rag.zk_integration import ZkClient

        client = ZkClient(notebook_dir="/tmp/test")

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("zk failed")

            notes = await client.list_notes(match="test")

            assert len(notes) == 0

    @pytest.mark.asyncio
    async def test_search_notes(self):
        """Test search_notes method."""
        from omni.rag.zk_integration import ZkClient

        client = ZkClient(notebook_dir="/tmp/test")

        mock_data = [
            {
                "filename": "python.md",
                "filenameStem": "python",
                "path": "python.md",
                "absPath": "/tmp/test/python.md",
                "title": "Python Guide",
                "link": "[Python Guide](python)",
                "tags": ["programming"],
            },
        ]

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_data

            notes = await client.search("python async", limit=5)

            assert len(notes) == 1
            assert "python" in notes[0].title.lower()

    @pytest.mark.asyncio
    async def test_find_related(self):
        """Test find_related method."""
        from omni.rag.zk_integration import ZkClient

        client = ZkClient(notebook_dir="/tmp/test")

        mock_data = [
            {
                "filename": "related1.md",
                "filenameStem": "related1",
                "path": "related1.md",
                "absPath": "/tmp/test/related1.md",
                "title": "Related Note 1",
                "link": "[Related Note 1](related1)",
                "tags": [],
            },
        ]

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_data

            notes = await client.find_related("note-id", max_distance=2, limit=10)

            assert len(notes) == 1

    @pytest.mark.asyncio
    async def test_find_by_tags(self):
        """Test find_by_tags method."""
        from omni.rag.zk_integration import ZkClient

        client = ZkClient(notebook_dir="/tmp/test")

        mock_data = [
            {
                "filename": "tagged.md",
                "filenameStem": "tagged",
                "path": "tagged.md",
                "absPath": "/tmp/test/tagged.md",
                "title": "Tagged Note",
                "link": "[Tagged Note](tagged)",
                "tags": ["python", "async"],
            },
        ]

        with patch.object(client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_data

            notes = await client.find_by_tags(["python"], limit=10)

            assert len(notes) == 1
            assert "python" in notes[0].tags


class TestGetZkClient:
    """Test get_zk_client function."""

    def test_get_zk_client_with_path(self):
        """Test get_zk_client creates client with path."""
        from omni.rag.zk_integration import get_zk_client

        client = get_zk_client("/custom/path")

        assert client is not None
        assert client.notebook_dir == "/custom/path"
