import pytest
from omni.test_kit.decorators import omni_skill


@pytest.mark.asyncio
@omni_skill(name="note_taker")
class TestNoteTakerModular:
    """Modular tests for note_taker skill."""

    async def test_summarize_session(self, skill_tester):
        """Test summarize_session execution."""
        trajectory = [
            {"type": "goal", "content": "Test task"},
            {
                "type": "decision",
                "title": "Decision 1",
                "context": "ctx",
                "choice": "A",
                "rationale": "rat",
            },
            {"type": "insight", "content": "Important insight"},
        ]

        result = await skill_tester.run(
            "note_taker", "summarize_session", session_id="test_session_123", trajectory=trajectory
        )

        assert result.success
        assert result.output["success"] is True
        assert result.output["session_id"] == "test_session_123"
        assert result.output["decisions_count"] == 1

    async def test_update_knowledge_base(self, skill_tester):
        """Test update_knowledge_base execution."""
        result = await skill_tester.run(
            "note_taker",
            "update_knowledge_base",
            category="patterns",
            title="Test Modular Pattern",
            content="Some modular content",
            tags=["test"],
        )

        assert result.success
        assert result.output["success"] is True
        assert result.output["category"] == "patterns"

    async def test_search_notes(self, skill_tester):
        """Test search_notes execution."""
        # Add a note first
        await skill_tester.run(
            "note_taker",
            "update_knowledge_base",
            category="notes",
            title="Searchable Note",
            content="findme",
            tags=["search"],
        )

        result = await skill_tester.run("note_taker", "search_notes", query="findme")

        assert result.success
        assert result.output["count"] >= 1
        assert any("Searchable Note" in r["title"] for r in result.output["results"])
