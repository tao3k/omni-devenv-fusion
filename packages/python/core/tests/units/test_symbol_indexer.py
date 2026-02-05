"""Tests for Zero-Token Symbol Indexer."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from omni.core.knowledge.symbol_indexer import (
    Symbol,
    SymbolIndex,
    SymbolIndexer,
    build_symbol_index,
)


class TestSymbol:
    """Tests for Symbol class."""

    def test_symbol_creation(self):
        """Test basic symbol creation."""
        sym = Symbol(
            name="TestClass",
            kind="class",
            line=10,
            signature="class TestClass",
            file_path="test.py",
        )
        assert sym.name == "TestClass"
        assert sym.kind == "class"
        assert sym.line == 10
        assert sym.file_path == "test.py"

    def test_symbol_to_dict(self):
        """Test symbol serialization."""
        sym = Symbol(
            name="test_func",
            kind="function",
            line=5,
            signature="def test_func()",
            file_path="test.py",
        )
        data = sym.to_dict()
        assert data["name"] == "test_func"
        assert data["kind"] == "function"
        assert data["line"] == 5


class TestSymbolIndex:
    """Tests for SymbolIndex class."""

    def test_add_and_lookup_symbol(self):
        """Test adding and looking up symbols."""
        index = SymbolIndex()

        sym = Symbol(
            name="MyClass",
            kind="class",
            line=10,
            signature="class MyClass",
            file_path="test.py",
        )
        index.add_symbol(sym)

        results = index.lookup("MyClass")
        assert len(results) == 1
        assert results[0]["file"] == "test.py"
        assert results[0]["line"] == 10

    def test_lookup_nonexistent(self):
        """Test lookup of nonexistent symbol."""
        index = SymbolIndex()
        results = index.lookup("NonExistent")
        assert results == []

    def test_stats(self):
        """Test index statistics."""
        index = SymbolIndex()
        index.add_symbol(Symbol("A", "class", 1, "class A", "a.py"))
        index.add_symbol(Symbol("B", "class", 2, "class B", "b.py"))
        stats = index.stats()
        assert stats["unique_symbols"] == 2
        assert stats["indexed_files"] == 2


class TestSymbolIndexer:
    """Tests for SymbolIndexer class."""

    def test_indexer_initialization(self):
        """Test indexer creation with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = SymbolIndexer(tmpdir)
            assert indexer.root.name  # Root is set
            assert ".py" in indexer.extensions

    def test_find_code_files(self):
        """Test file discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create test files
            (tmppath / "test.py").write_text("def foo(): pass")
            (tmppath / "test.rs").write_text("fn foo() {}")
            (tmppath / "readme.txt").write_text("not code")

            indexer = SymbolIndexer(tmpdir, extensions=[".py", ".rs"])
            files = indexer._find_code_files()

            assert len(files) == 2
            suffixes = {f.suffix for f in files}
            assert suffixes == {".py", ".rs"}

    def test_extract_symbols_from_file(self):
        """Test symbol extraction from a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            test_file = tmppath / "test.py"
            test_file.write_text("""
class MyClass:
    def method(self):
        pass

def standalone_func():
    pass
""")

            indexer = SymbolIndexer(tmpdir)
            symbols = indexer._extract_symbols_from_file(test_file)

            # Should find class and functions
            kinds = {s.kind for s in symbols}
            assert "class" in kinds
            assert "function" in kinds

    def test_build_index(self):
        """Test building the symbol index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create test files
            (tmppath / "module1.py").write_text("""
class Foo:
    pass

def bar():
    pass
""")
            (tmppath / "module2.py").write_text("""
class Baz:
    pass
""")

            indexer = SymbolIndexer(tmpdir)
            stats = indexer.build(clean=True)

            assert stats["indexed_files"] == 2
            assert stats["unique_symbols"] >= 3  # Foo, bar, Baz

    def test_search_symbol(self):
        """Test symbol search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "test.py").write_text("""
class MyClass:
    pass
""")

            indexer = SymbolIndexer(tmpdir)
            indexer.build(clean=True)

            results = indexer.search_symbol("MyClass")
            assert len(results) >= 1
            assert any(r["file"] == "test.py" for r in results)

    def test_search_pattern(self):
        """Test pattern-based search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "test.py").write_text("""
class FooClass:
    pass

class BarClass:
    pass
""")

            indexer = SymbolIndexer(tmpdir)
            indexer.build(clean=True)

            results = indexer.search_pattern("*Class")
            names = {r["name"] for r in results}
            assert "FooClass" in names
            assert "BarClass" in names

    def test_incremental_build(self):
        """Test incremental updates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            test_file = tmppath / "test.py"
            test_file.write_text("def func1(): pass")

            indexer = SymbolIndexer(tmpdir)
            stats1 = indexer.build(clean=True)
            assert stats1["indexed_files"] == 1  # First build should index

            # Update file content (changes hash)
            test_file.write_text("def func2(): pass")
            stats2 = indexer.build(clean=False)

            # Should re-index because content changed
            assert stats2["indexed_files"] == 1

            # Build again with no changes
            stats3 = indexer.build(clean=False)
            # Should skip re-indexing unchanged file
            assert stats3["indexed_files"] == 0

    def test_clear(self):
        """Test clearing the index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            (tmppath / "test.py").write_text("class Foo: pass")

            indexer = SymbolIndexer(tmpdir)
            indexer.build(clean=True)

            assert indexer.index.stats()["unique_symbols"] > 0

            indexer.clear()

            assert indexer.index.stats()["unique_symbols"] == 0


class TestBuildFunction:
    """Tests for convenience function."""

    def test_build_symbol_index(self):
        """Test the convenience build function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / "test.py").write_text("class Test: pass")

            indexer = build_symbol_index(tmppath)

            assert indexer.index.stats()["indexed_files"] == 1
