"""
Unit tests for skill/scripts/search_tools.py

Tests the keyword-based tool search functionality that uses
LanceDB for tool lookup.

Run from project root:
    cd packages/python/core
    python -m pytest tests/units/skills/test_search_tools.py -v
"""

import subprocess
import sys


def run_test(code: str) -> subprocess.CompletedProcess:
    """Run test code in subprocess with uv environment."""
    return subprocess.run(
        [sys.executable, "-c", code.strip()],
        capture_output=True,
        text=True,
    )


class TestTokenize:
    """Tests for the _tokenize helper function."""

    def test_tokenize_lowercase(self) -> None:
        """Verify tokenize converts to lowercase."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import _tokenize
tokens = _tokenize("Hello World")
assert "hello" in tokens
assert "world" in tokens
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_tokenize_removes_punctuation(self) -> None:
        """Verify tokenize removes punctuation."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import _tokenize
tokens = _tokenize("hello, world!")
assert "," not in tokens
assert "!" not in tokens
assert "hello" in tokens
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_tokenize_handles_empty_string(self) -> None:
        """Verify tokenize handles empty string."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import _tokenize
tokens = _tokenize("")
assert tokens == set()
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"


class TestCalculateScore:
    """Tests for the _calculate_score helper function."""

    def test_name_match_high_score(self) -> None:
        """Verify name matches get highest weight."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import _calculate_score
score = _calculate_score("git commit", "git.commit", "commit message", "git")
assert score >= 5.0
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_skill_match_boost(self) -> None:
        """Verify skill name match gives extra boost."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import _calculate_score
score_with = _calculate_score("git commit", "git.commit", "commit message", "git")
score_without = _calculate_score("git commit", "git.commit", "commit message", "")
assert score_with > score_without
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_exact_prefix_match(self) -> None:
        """Verify exact prefix match gets bonus."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import _calculate_score
score = _calculate_score("git", "git.commit", "commit tool", "git")
assert score > 5.0
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_no_match_zero_score(self) -> None:
        """Verify no match gives zero score."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import _calculate_score
score = _calculate_score("xyz abc", "git.commit", "commit message", "git")
assert score == 0
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"


class TestSearchTools:
    """Tests for the search_tools function."""

    def test_search_returns_json_string(self) -> None:
        """Verify search_tools returns JSON string."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
result = asyncio.run(search_tools("git commit"))
assert isinstance(result, str)
data = json.loads(result)
assert "tools" in data
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_search_finds_git_tools(self) -> None:
        """Verify search finds git-related tools."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
result = asyncio.run(search_tools("git commit"))
data = json.loads(result)
tool_names = [t["name"] for t in data["tools"]]
assert any("git" in name for name in tool_names)
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_search_limits_results(self) -> None:
        """Verify limit parameter works."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
result = asyncio.run(search_tools("file", limit=1))
data = json.loads(result)
assert len(data["tools"]) <= 1
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_search_includes_query_in_response(self) -> None:
        """Verify response includes the query."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
result = asyncio.run(search_tools("my test query"))
data = json.loads(result)
assert data["query"] == "my test query"
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_search_empty_results(self) -> None:
        """Verify search returns when no high-scoring matches."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
# Query that won't match anything
result = asyncio.run(search_tools("xyz123 nonexistent tool"))
data = json.loads(result)
# Should return low-scoring results or empty (depending on scoring)
assert "tools" in data
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_search_score_normalized(self) -> None:
        """Verify scores are normalized to 0-1 range."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
result = asyncio.run(search_tools("git"))
data = json.loads(result)
for tool in data["tools"]:
    assert 0.0 <= tool["score"] <= 1.0
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_search_result_contains_required_fields(self) -> None:
        """Verify tool results contain all required fields."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
result = asyncio.run(search_tools("git"))
data = json.loads(result)
if data["tools"]:
    tool = data["tools"][0]
    for field in ["name", "description", "schema", "score", "skill"]:
        assert field in tool
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_search_schema_contains_properties(self) -> None:
        """Verify schema contains properties and required fields (main fix)."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import search_tools
import asyncio
import json
# Search for git commit to get a tool with full schema
result = asyncio.run(search_tools("git commit"))
data = json.loads(result)
# Find git.commit tool
git_commit_tool = None
for tool in data["tools"]:
    if tool["name"] == "git.commit":
        git_commit_tool = tool
        break
assert git_commit_tool is not None, "git.commit tool not found"
# Verify schema is populated (not empty dict)
schema = git_commit_tool["schema"]
assert "properties" in schema, f"schema missing 'properties': {schema}"
assert "required" in schema, f"schema missing 'required': {schema}"
# Verify properties have actual fields
assert len(schema["properties"]) > 0, f"properties is empty: {schema}"
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"


class TestFormatSearchResult:
    """Tests for the format_search_result function."""

    def test_format_error_message(self) -> None:
        """Verify error messages are formatted correctly."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import format_search_result
import json
error_json = json.dumps({"error": "Test error", "tools": []})
result = format_search_result(error_json)
assert "Search Error" in result
assert "Test error" in result
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_format_empty_results(self) -> None:
        """Verify empty results message."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import format_search_result
import json
empty_json = json.dumps({"tools": [], "total": 0, "query": "test"})
result = format_search_result(empty_json)
assert "No matching tools found" in result
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_format_with_results(self) -> None:
        """Verify formatted results include tool details."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import format_search_result
import json
results_json = json.dumps({
    "tools": [{"name": "git.commit", "description": "Commit", "skill": "git"}],
    "total": 1,
    "query": "git"
})
result = format_search_result(results_json)
assert "Search Results" in result
assert "git.commit" in result
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"

    def test_format_invalid_json(self) -> None:
        """Verify invalid JSON returns as-is."""
        result = run_test("""
import sys
from omni.foundation.config.skills import SKILLS_DIR
sys.path.insert(0, str(SKILLS_DIR("skill", path="scripts")))
from search_tools import format_search_result
result = format_search_result("not json")
assert result == "not json"
print("OK")
""")
        assert result.returncode == 0, f"Failed: {result.stderr}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
