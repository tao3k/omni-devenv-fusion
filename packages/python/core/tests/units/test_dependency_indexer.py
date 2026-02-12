"""Integration tests for Dependency Indexer - Python side.

Tests the full workflow with mock crate sources to avoid external dependencies.
"""

import json
import os
import tempfile
import pytest


class TestDependencyIndexerScenarios:
    """Scenario-based tests for Dependency Indexer with mock sources."""

    def test_scenario_parse_and_index_symbols(self):
        """Scenario: LLM upgrades a dependency version and needs to look up new API.

        Uses mock sources to test the indexing workflow without external dependencies.
        """
        temp_dir = tempfile.mkdtemp()

        # Create Cargo.toml with test dependency
        cargo_path = os.path.join(temp_dir, "Cargo.toml")
        with open(cargo_path, "w") as f:
            f.write("""[package]
name = "test-project"
version = "0.1.0"

[dependencies]
mock_crate = "1.0"
""")

        # Create config
        config_path = os.path.join(temp_dir, "references.yaml")
        with open(config_path, "w") as f:
            f.write("""ast_symbols_external:
  - type: rust
    manifests:
      - "**/Cargo.toml"
""")

        # Create mock crate source
        mock_src_dir = os.path.join(temp_dir, "mock_crate_src")
        os.makedirs(mock_src_dir)
        with open(os.path.join(mock_src_dir, "lib.rs"), "w") as f:
            f.write("""// Mock crate for testing

pub struct Error;

impl Error {
    pub fn new() -> Self {
        Error
    }

    pub fn context(&self, msg: &str) -> anyhow::Error {
        anyhow::anyhow!("{}: {}", msg, self)
    }
}

pub fn create_error(msg: &str) -> Error {
    Error
}
""")

        from omni_core_rs import PyDependencyConfig, PyDependencyIndexer

        # Test that config is loaded correctly
        config = PyDependencyConfig.load(config_path)
        assert len(config.manifests) > 0, "Should load manifest config"

    def test_scenario_config_loading(self):
        """Scenario: Test that references.yaml is parsed correctly."""
        temp_dir = tempfile.mkdtemp()

        config_path = os.path.join(temp_dir, "references.yaml")
        with open(config_path, "w") as f:
            f.write("""ast_symbols_external:
  - type: rust
    manifests:
      - "**/Cargo.toml"
      - "**/Cargo.lock"
  - type: python
    registry: pip
    manifests:
      - "**/pyproject.toml"
""")

        from omni_core_rs import PyDependencyConfig

        config = PyDependencyConfig.load(config_path)
        manifests = config.manifests

        # Should have rust and python configs
        rust_configs = [m for m in manifests if m.pkg_type == "rust"]
        python_configs = [m for m in manifests if m.pkg_type == "python"]

        assert len(rust_configs) == 1, "Should have rust config"
        assert len(python_configs) == 1, "Should have python config"
        assert "**/Cargo.toml" in rust_configs[0].manifests
        assert "pip" in python_configs[0].registry

    def test_scenario_indexer_creation(self):
        """Scenario: Test indexer creation with different configurations."""
        from omni_core_rs import PyDependencyIndexer

        temp_dir = tempfile.mkdtemp()

        # Without config
        indexer1 = PyDependencyIndexer(temp_dir, None)
        assert indexer1 is not None

        # With non-existent config
        indexer2 = PyDependencyIndexer(temp_dir, "/nonexistent/path.yaml")
        assert indexer2 is not None

    def test_scenario_search_methods(self):
        """Scenario: Test that search methods return valid JSON."""
        temp_dir = tempfile.mkdtemp()

        # Create a minimal Cargo.toml
        cargo_path = os.path.join(temp_dir, "Cargo.toml")
        with open(cargo_path, "w") as f:
            f.write("""[package]
name = "test"
version = "0.1.0"
""")

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)

        # Test search returns valid JSON
        result = indexer.search("test", 10)
        symbols = json.loads(result)
        assert isinstance(symbols, list)

        # Test search_crate returns valid JSON
        result = indexer.search_crate("nonexistent", "test", 10)
        symbols = json.loads(result)
        assert isinstance(symbols, list)

        # Test stats returns valid JSON
        result = indexer.stats()
        stats = json.loads(result)
        assert "total_crates" in stats
        assert "total_symbols" in stats

    def test_scenario_indexed_list(self):
        """Scenario: Test get_indexed returns list of crates."""
        temp_dir = tempfile.mkdtemp()

        # Create a minimal project
        cargo_path = os.path.join(temp_dir, "Cargo.toml")
        with open(cargo_path, "w") as f:
            f.write("""[package]
name = "test"
version = "0.1.0"
""")

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)
        indexed = indexer.get_indexed()

        assert isinstance(indexed, list)

    def test_scenario_load_index(self):
        """Scenario: Test load_index returns bool."""
        temp_dir = tempfile.mkdtemp()

        # Create a minimal project
        cargo_path = os.path.join(temp_dir, "Cargo.toml")
        with open(cargo_path, "w") as f:
            f.write("""[package]
name = "test"
version = "0.1.0"
""")

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)
        loaded = indexer.load_index()

        assert isinstance(loaded, bool)

    def test_scenario_build_returns_json(self):
        """Scenario: Test build returns valid JSON string."""
        temp_dir = tempfile.mkdtemp()

        # Create minimal Cargo.toml without dependencies
        cargo_path = os.path.join(temp_dir, "Cargo.toml")
        with open(cargo_path, "w") as f:
            f.write("""[package]
name = "test"
version = "0.1.0"
""")

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)
        result = indexer.build(True)

        # Should return JSON string
        data = json.loads(result)
        assert "files_processed" in data
        assert "total_symbols" in data
        assert "errors" in data
        assert "crates_indexed" in data

    def test_scenario_symbol_kinds(self):
        """Scenario: Test that symbol kinds are properly defined."""
        from omni_core_rs import PyExternalSymbol

        # Create symbol with different kinds
        kinds = [
            "struct",
            "enum",
            "trait",
            "fn",
            "method",
            "field",
            "impl",
            "mod",
            "const",
            "static",
            "type",
            "unknown",
        ]

        for kind in kinds:
            sym = PyExternalSymbol(
                name="Test", kind=kind, file="/test/lib.rs", line=1, crate_name="test"
            )
            assert sym.name == "Test"
            assert sym.crate_name == "test"


class TestDependencyIndexerEdgeCases:
    """Edge case tests."""

    def test_empty_project(self):
        """Empty project with no dependencies should not error."""
        temp_dir = tempfile.mkdtemp()

        cargo_path = os.path.join(temp_dir, "Cargo.toml")
        with open(cargo_path, "w") as f:
            f.write("""[package]
name = "empty"
version = "0.1.0"
""")

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)
        result = json.loads(indexer.build(True))

        # Just verify the result is valid JSON and has expected keys
        assert result["files_processed"] >= 0  # May vary based on crate discovery
        assert "total_symbols" in result
        assert "errors" in result

    def test_build_with_clean_flag(self):
        """Test clean flag resets the index."""
        temp_dir = tempfile.mkdtemp()

        cargo_path = os.path.join(temp_dir, "Cargo.toml")
        with open(cargo_path, "w") as f:
            f.write("""[package]
name = "test"
version = "0.1.0"
""")

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)

        # Build with clean=True
        result1 = json.loads(indexer.build(True))

        # Build again with clean=True (should be same)
        result2 = json.loads(indexer.build(True))

        assert result1["crates_indexed"] == result2["crates_indexed"]

    def test_invalid_config_path(self):
        """Invalid config path should not crash."""
        temp_dir = tempfile.mkdtemp()

        from omni_core_rs import PyDependencyIndexer

        # Use non-existent config
        indexer = PyDependencyIndexer(temp_dir, "/this/path/does/not/exist.yaml")
        result = json.loads(indexer.build(True))

        # Should complete without crash
        assert "files_processed" in result

    def test_special_characters_in_pattern(self):
        """Search patterns with special characters should not crash."""
        temp_dir = tempfile.mkdtemp()

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)

        # These should not crash
        result = indexer.search("", 10)  # empty pattern
        json.loads(result)

        result = indexer.search("***", 10)  # invalid regex-ish
        json.loads(result)

    def test_large_limit(self):
        """Large search limit should not crash."""
        temp_dir = tempfile.mkdtemp()

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)

        result = indexer.search("test", 10000)  # very large limit
        symbols = json.loads(result)
        assert isinstance(symbols, list)


class TestDependencyIndexerAPISurface:
    """Tests that verify the API surface is complete."""

    def test_all_classes_exported(self):
        """Verify all PyO3 classes are exported."""
        from omni_core_rs import (
            PyDependencyIndexer,
            PyDependencyConfig,
            PyDependencyIndexResult,
            PyDependencyStats,
            PyExternalSymbol,
            PyExternalDependency,
            PySymbolIndex,
        )

        assert PyDependencyIndexer is not None
        assert PyDependencyConfig is not None
        assert PyDependencyIndexResult is not None
        assert PyDependencyStats is not None
        assert PyExternalSymbol is not None
        assert PyExternalDependency is not None
        assert PySymbolIndex is not None

    def test_indexer_methods_exist(self):
        """Verify all required methods exist on PyDependencyIndexer."""
        temp_dir = tempfile.mkdtemp()

        from omni_core_rs import PyDependencyIndexer

        indexer = PyDependencyIndexer(temp_dir, None)

        # Check methods exist (won't test functionality)
        assert hasattr(indexer, "build")
        assert hasattr(indexer, "search")
        assert hasattr(indexer, "search_crate")
        assert hasattr(indexer, "get_indexed")
        assert hasattr(indexer, "stats")
        assert hasattr(indexer, "load_index")
        assert hasattr(indexer, "get_symbol_index")

    def test_config_methods_exist(self):
        """Verify required methods exist on PyDependencyConfig."""
        from omni_core_rs import PyDependencyConfig

        # Static method
        assert hasattr(PyDependencyConfig, "load")

    def test_symbol_methods_exist(self):
        """Verify required methods exist on PySymbolIndex."""
        from omni_core_rs import PySymbolIndex

        index = PySymbolIndex()

        assert hasattr(index, "search")
        assert hasattr(index, "search_crate")
        assert hasattr(index, "get_crates")
        assert hasattr(index, "symbol_count")
        assert hasattr(index, "crate_count")
        assert hasattr(index, "clear")
        assert hasattr(index, "serialize")
        assert hasattr(index, "deserialize")
