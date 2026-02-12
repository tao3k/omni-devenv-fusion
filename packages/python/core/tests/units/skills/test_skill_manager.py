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
        """SkillManager initialization should NOT call _load_local_model().

        This is a regression test for the issue where SkillManager.__init__
        would eagerly load the embedding model, causing unnecessary loading
        even when MCP server is available.
        """
        from omni.core.services.skill_manager import SkillManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("omni.core.services.skill_manager.get_embedding_service") as mock_get_embed:
                mock_embed = MagicMock()
                mock_embed.dimension = 1024
                mock_get_embed.return_value = mock_embed

                # Create SkillManager
                manager = SkillManager(
                    project_root=tmpdir,
                    enable_watcher=False,
                )

                # Verify _load_local_model was NOT called
                mock_embed._load_local_model.assert_not_called()

    def test_skill_manager_uses_settings_for_dimension(self):
        """SkillManager should get dimension from settings, not from loading embedding."""
        import importlib
        import omni.foundation.config.settings as settings_module
        from omni.core.services.skill_manager import SkillManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("omni.core.services.skill_manager.get_embedding_service") as mock_get_embed:
                mock_embed = MagicMock()
                mock_embed.dimension = 9999  # This should NOT be used
                mock_get_embed.return_value = mock_embed

                # Patch get_setting at the settings module level (imported inside __init__)
                original_get_setting = settings_module.get_setting
                settings_module.get_setting = (
                    lambda key, default=None: 1024 if key == "embedding.dimension" else default
                )

                try:
                    with patch("omni.core.services.skill_manager.PyVectorStore") as mock_store:
                        with patch("omni.core.services.skill_manager.SkillIndexer"):
                            with patch("omni.core.services.skill_manager.HolographicRegistry"):
                                manager = SkillManager(
                                    project_root=tmpdir,
                                    enable_watcher=False,
                                )

                                # Verify PyVectorStore was called with settings dimension
                                mock_store.assert_called_once()
                                call_args = mock_store.call_args
                                # Second argument should be dimension from settings (1024)
                                assert call_args[0][1] == 1024
                finally:
                    # Restore original function
                    settings_module.get_setting = original_get_setting

    def test_skill_manager_embedding_singleton_not_modified(self):
        """SkillManager should not modify embedding service state."""
        from omni.foundation.services.embedding import EmbeddingService

        with tempfile.TemporaryDirectory() as tmpdir:
            # Store original states
            original_initialized = EmbeddingService._initialized
            original_model_loaded = EmbeddingService._model_loaded

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

                # Verify embedding service state was NOT changed
                assert EmbeddingService._initialized == original_initialized
                assert EmbeddingService._model_loaded == original_model_loaded

            finally:
                # Cleanup
                EmbeddingService._instance = None
                EmbeddingService._initialized = original_initialized
                EmbeddingService._model_loaded = original_model_loaded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
