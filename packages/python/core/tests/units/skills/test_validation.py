from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from omni.core.skills import validation


def test_load_skills_from_scanner_uses_configured_skills_dir(tmp_path: Path) -> None:
    skills_dir = tmp_path / "assets" / "skills"
    skills_dir.mkdir(parents=True)

    mock_store = MagicMock()
    mock_store.get_skill_index_sync.return_value = [
        {
            "name": "knowledge",
            "tools": [
                {"name": "knowledge.search", "input_schema": {"type": "object"}},
                {"name": "ingest", "input_schema": {"type": "object"}},
            ],
        }
    ]

    with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
        with patch("omni.foundation.bridge.RustVectorStore", return_value=mock_store):
            loaded = validation._load_skills_from_scanner()

    mock_store.get_skill_index_sync.assert_called_once_with(str(skills_dir))
    assert "knowledge.search" in loaded
    assert "knowledge.ingest" in loaded


def test_validate_tool_args_reports_missing_required() -> None:
    validation._skill_tools_cache = {
        "knowledge.ingest_document": {
            "input_schema": {
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Path to file"}},
                "required": ["file_path"],
            }
        }
    }

    errors = validation.validate_tool_args("knowledge.ingest_document", args={})

    assert len(errors) == 1
    assert errors[0].field == "file_path"
    assert errors[0].error_type == validation.ErrorType.MISSING_REQUIRED
