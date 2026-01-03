"""
Test Suite for Writer Compliance - WritingStyleCache Singleton Pattern

Tests:
1. WritingStyleCache singleton behavior
2. Guidelines loading from agent/writing-style/*.md
3. polish_text tool integration

Run: uv run python mcp-server/tests/test_writer_compliance.py
"""
import json
import unittest
from pathlib import Path

from mcp_server.executor.writer import WritingStyleCache, _polish_text_impl, _load_writing_memory_impl


class TestWritingStyleCache(unittest.TestCase):
    """Test WritingStyleCache singleton pattern"""

    def setUp(self):
        """Reset cache before each test"""
        WritingStyleCache._loaded = False
        WritingStyleCache._instance = None
        WritingStyleCache._guidelines = ""
        WritingStyleCache._guidelines_dict = {}

    def tearDown(self):
        """Clean up after each test"""
        WritingStyleCache._loaded = False
        WritingStyleCache._instance = None
        WritingStyleCache._guidelines = ""
        WritingStyleCache._guidelines_dict = {}

    def test_singleton_pattern(self):
        """Test that WritingStyleCache follows singleton pattern"""
        cache1 = WritingStyleCache()
        cache2 = WritingStyleCache()
        self.assertIs(cache1, cache2)

    def test_guidelines_loaded_from_files(self):
        """Test that guidelines are loaded from agent/writing-style/*.md"""
        cache = WritingStyleCache()
        guidelines = WritingStyleCache.get_guidelines()

        # Should have loaded the style files
        self.assertTrue(len(guidelines) > 0, "Guidelines should not be empty")

    def test_guidelines_dict_populated(self):
        """Test that guidelines dict contains expected files"""
        _ = WritingStyleCache()
        guidelines_dict = WritingStyleCache.get_guidelines_dict()

        # Should have loaded at least 3 style guides
        self.assertGreaterEqual(len(guidelines_dict), 3, "Should have 3+ style guides")

        # Check expected files exist
        self.assertIn("01-concise.md", guidelines_dict)
        self.assertIn("02-formatting.md", guidelines_dict)
        self.assertIn("03-technical.md", guidelines_dict)

    def test_get_guidelines_for_prompt(self):
        """Test that get_guidelines_for_prompt returns formatted rules"""
        _ = WritingStyleCache()
        prompt_guidelines = WritingStyleCache.get_guidelines_for_prompt()

        # Should contain file references and rules
        self.assertIn("01-concise.md", prompt_guidelines)
        self.assertIn("02-formatting.md", prompt_guidelines)

    def test_reload_functionality(self):
        """Test that reload forces cache refresh"""
        _ = WritingStyleCache()
        guidelines1 = WritingStyleCache.get_guidelines()

        WritingStyleCache.reload()
        guidelines2 = WritingStyleCache.get_guidelines()

        # Should be the same after reload
        self.assertEqual(guidelines1, guidelines2)


class TestPolishTextImpl(unittest.TestCase):
    """Test polish_text implementation"""

    def setUp(self):
        WritingStyleCache._loaded = False
        WritingStyleCache._instance = None
        WritingStyleCache._guidelines = ""
        WritingStyleCache._guidelines_dict = {}

    def tearDown(self):
        WritingStyleCache._loaded = False
        WritingStyleCache._instance = None

    def test_polish_text_detects_clutter(self):
        """Test that polish_text detects clutter words"""
        import asyncio

        # Text with clutter words
        test_text = "We basically utilize this in order to facilitate the process."

        result = asyncio.run(_polish_text_impl(test_text))
        data = json.loads(result)

        self.assertEqual(data["status"], "needs_polish")
        self.assertGreater(len(data["violations"]), 0)

    def test_polish_text_returns_clean_for_good_text(self):
        """Test that polish_text returns clean for well-written text"""
        import asyncio

        # Text following guidelines
        test_text = "We deploy the feature. It works as expected."

        result = asyncio.run(_polish_text_impl(test_text))
        data = json.loads(result)

        # Should have no clutter violations
        clutter_violations = [v for v in data["violations"] if v.get("type") == "clutter_word"]
        self.assertEqual(len(clutter_violations), 0)


class TestLoadWritingMemoryImpl(unittest.TestCase):
    """Test load_writing_memory implementation"""

    def setUp(self):
        WritingStyleCache._loaded = False
        WritingStyleCache._instance = None
        WritingStyleCache._guidelines = ""
        WritingStyleCache._guidelines_dict = {}

    def tearDown(self):
        WritingStyleCache._loaded = False
        WritingStyleCache._instance = None

    def test_load_writing_memory_returns_status(self):
        """Test that load_writing_memory returns loaded status"""
        import asyncio

        result = asyncio.run(_load_writing_memory_impl())
        data = json.loads(result)

        self.assertEqual(data["status"], "loaded")
        self.assertIn("files_loaded", data)
        self.assertGreater(data["total_files"], 0)


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Writer Compliance Test Suite")
    print("=" * 60)
    print("\nTesting Writing Style Cache...")
    print("1. WritingStyleCache singleton pattern")
    print("2. Guidelines loading from agent/writing-style/*.md")
    print("3. polish_text tool integration")
    print("=" * 60)

    unittest.main(verbosity=2)
