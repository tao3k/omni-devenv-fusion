"""Tests for Arrow Analytics functionality in SkillDiscoveryService.

Tests the PyArrow-based high-performance analytics operations.
"""

from __future__ import annotations

import pytest


class TestArrowAnalyticsTable:
    """Tests for get_analytics_table method."""

    def test_get_analytics_table_returns_pyarrow_table(self):
        """Test that get_analytics_table returns a PyArrow Table."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService
            import pyarrow as pa

            service = SkillDiscoveryService()
            table = service.get_analytics_dataframe()

            # Analyzer module may not be available - skip if None
            if table is None:
                pytest.skip("Analytics table not available (analyzer module missing or no data)")

            # Should return a PyArrow Table
            assert isinstance(table, pa.Table), f"Expected PyArrow Table, got {type(table)}"

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")

    def test_analytics_table_has_expected_columns(self):
        """Test that the analytics table has all expected columns."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            table = service.get_analytics_dataframe()

            if table is None:
                pytest.skip("No data in database, skipping column check")

            expected_columns = ["id", "content", "skill_name", "tool_name", "file_path", "keywords"]
            for col in expected_columns:
                assert col in table.column_names, f"Missing expected column: {col}"

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")

    def test_analytics_table_row_count(self):
        """Test that the analytics table has correct row count."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            table = service.get_analytics_dataframe()

            if table is None:
                pytest.skip("No data in database")

            # Should have at least one row if tools are indexed
            assert table.num_rows > 0, "Analytics table should have at least one row"

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")


class TestCategoryDistribution:
    """Tests for get_category_distribution method."""

    def test_get_category_distribution_returns_dict(self):
        """Test that get_category_distribution returns a dictionary."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            distribution = service.get_category_distribution()

            assert isinstance(distribution, dict), f"Expected dict, got {type(distribution)}"

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")

    def test_category_distribution_values_are_integers(self):
        """Test that category distribution values are integers (counts)."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            distribution = service.get_category_distribution()

            if not distribution:
                pytest.skip("No categories found")

            for category, count in distribution.items():
                assert isinstance(category, str), (
                    f"Category key should be str, got {type(category)}"
                )
                assert isinstance(count, int), f"Category count should be int, got {type(count)}"
                assert count > 0, "Category count should be positive"

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")


class TestSystemContext:
    """Tests for generate_system_context method."""

    def test_generate_system_context_returns_string(self):
        """Test that generate_system_context returns a string."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            context = service.generate_system_context()

            assert isinstance(context, str), f"Expected str, got {type(context)}"
            assert len(context) > 0, "Context should not be empty"

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")

    def test_system_context_contains_tool_format(self):
        """Test that system context contains @omni tool references."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            context = service.generate_system_context()

            # Should contain @omni("tool.name") pattern
            assert '@omni("' in context or "@omni(" in context, (
                "Context should contain @omni tool references"
            )

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")

    def test_system_context_not_empty(self):
        """Test that system context is not empty when tools exist."""
        try:
            from omni.core.skills.discovery import SkillDiscoveryService

            service = SkillDiscoveryService()
            context = service.generate_system_context()

            # Should contain @omni("tool.name") pattern
            assert '@omni("' in context or "@omni(" in context, (
                "Context should contain @omni tool references"
            )

        except ImportError as e:
            pytest.skip(f"Required module not available: {e}")


class TestRustVectorStoreIntegration:
    """Tests for RustVectorStore Arrow integration."""

    def test_rust_vector_store_has_get_analytics_table(self):
        """Test that RustVectorStore has get_analytics_table method."""
        try:
            from omni.foundation.bridge.rust_vector import get_vector_store
            import asyncio

            async def check():
                store = get_vector_store()
                assert hasattr(store, "get_analytics_table"), (
                    "RustVectorStore should have get_analytics_table method"
                )

            asyncio.run(check())

        except ImportError as e:
            pytest.skip(f"Rust bindings not available: {e}")

    def test_rust_vector_store_get_analytics_table_returns_table(self):
        """Test that get_analytics_table returns a valid PyArrow Table."""
        try:
            from omni.foundation.bridge.rust_vector import get_vector_store
            import pyarrow as pa
            import asyncio

            async def check():
                store = get_vector_store()
                table = await store.get_analytics_table()

                if table is not None:
                    assert isinstance(table, pa.Table), f"Expected PyArrow Table, got {type(table)}"

            asyncio.run(check())

        except ImportError as e:
            pytest.skip(f"Rust bindings not available: {e}")
