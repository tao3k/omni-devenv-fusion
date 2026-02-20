"""
Tests for SkillManager - ensuring embedding is NOT loaded during initialization.

This test prevents regression of the issue where SkillManager.__init__
would call embedding_service._load_local embedding_model(), causing unnecessary
model loading even when MCP server is available.
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path


class TestSkillManagerEmbeddingLazyLoad:
    """Tests for SkillManager lazy embedding behavior."""

    def setup_method(self):
        """Reset singleton states before each test."""
        # Reset embedding service singleton
        try:
            from omni.foundation.services.embedding import EmbeddingService

            EmbeddingService._instance = None
            EmbeddingService._initialized = False
            EmbeddingService._model_loaded = False
            EmbeddingService._model_loading = False
            EmbeddingService._client_mode = False
        except ImportError:
            pass

    def test_skill_manager_does_not_trigger_embedding_load(self):
        """SkillManager initialization should NOT call start_model_loading.

        Regression test: SkillManager must not eagerly trigger embedding
        model loading; it only uses the embedding service for dimension/backend.
        """
        from omni.core.services.skill_manager import SkillManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("omni.core.services.skill_manager.get_embedding_service") as mock_get_embed:
                mock_embed = MagicMock()
                mock_embed.dimension = 1024
                mock_embed.backend = "fallback"
                mock_get_embed.return_value = mock_embed

                manager = SkillManager(
                    project_root=tmpdir,
                    enable_watcher=False,
                )

                # get_embedding_service is used; start_model_loading must not be called
                mock_get_embed.assert_called()
                mock_embed.start_model_loading.assert_not_called()

    def test_skill_manager_uses_settings_for_dimension(self):
        """SkillManager should get dimension from get_effective_embedding_dimension (config), not from embedding service."""
        from omni.core.services.skill_manager import SkillManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("omni.core.services.skill_manager.get_embedding_service") as mock_get_embed:
                mock_embed = MagicMock()
                mock_embed.dimension = 9999  # Should NOT be used for store dimension
                mock_get_embed.return_value = mock_embed

                with patch(
                    "omni.foundation.services.index_dimension.get_effective_embedding_dimension",
                    return_value=1024,
                ):
                    with patch("omni.core.services.skill_manager.PyVectorStore") as mock_store:
                        with patch("omni.core.services.skill_manager.SkillIndexer"):
                            with patch("omni.core.services.skill_manager.HolographicRegistry"):
                                manager = SkillManager(
                                    project_root=tmpdir,
                                    enable_watcher=False,
                                )

                                mock_store.assert_called_once()
                                call_args = mock_store.call_args
                                assert call_args[0][1] == 1024

    def test_skill_manager_embedding_singleton_not_modified(self):
        """SkillManager should not modify embedding service state."""
        from omni.foundation.services.embedding import EmbeddingService

        with tempfile.TemporaryDirectory() as tmpdir:
            original_initialized = EmbeddingService._initialized

            try:
                from omni.core.services.skill_manager import SkillManager

                with patch(
                    "omni.core.services.skill_manager.get_embedding_service"
                ) as mock_get_embed:
                    mock_embed = MagicMock()
                    mock_embed.dimension = 1024
                    mock_get_embed.return_value = mock_embed

                    with patch("omni.core.services.skill_manager.PyVectorStore"):
                        with patch("omni.core.services.skill_manager.SkillIndexer"):
                            with patch("omni.core.services.skill_manager.HolographicRegistry"):
                                manager = SkillManager(
                                    project_root=tmpdir,
                                    enable_watcher=False,
                                )

                assert EmbeddingService._initialized == original_initialized

            finally:
                EmbeddingService._instance = None
                EmbeddingService._initialized = original_initialized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
