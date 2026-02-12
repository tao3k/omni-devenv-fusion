"""
Unit tests for EmbeddingService with auto-detection and HTTP server sharing.

Tests cover:
- Port in use detection
- Auto-detection logic (server vs client mode)
- HTTP server startup/shutdown
- Singleton behavior
"""

import pytest
import socket
from unittest.mock import patch, MagicMock, AsyncMock
import threading
import time


class TestEmbeddingServicePortDetection:
    """Tests for port in use detection."""

    def test_is_port_in_use_returns_true_for_open_port(self):
        """Should return True when port is actually in use."""
        # Create a real socket to bind to a random free port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.bind(("127.0.0.1", 0))  # Bind to random free port
            sock.listen(1)
            port = sock.getsockname()[1]

            # Now test our method
            from omni.foundation.services.embedding import EmbeddingService

            service = EmbeddingService()
            result = service._is_port_in_use(port, timeout=0.5)
            assert result is True
        finally:
            sock.close()

    def test_is_port_in_use_returns_false_for_closed_port(self):
        """Should return False when port is not in use."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()

        # Use a port that's definitely not in use (random high port)
        result = service._is_port_in_use(19999, timeout=0.5)
        assert result is False

    def test_is_address_in_use_error_detects_known_oserror(self):
        """Should identify address-in-use OSError variants."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        err = OSError(48, "address already in use")
        assert service._is_address_in_use_error(err) is True

    def test_is_address_in_use_error_detects_message_fallback(self):
        """Should identify address-in-use from exception message fallback."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        err = RuntimeError("error while attempting to bind on address: address already in use")
        assert service._is_address_in_use_error(err) is True


class TestEmbeddingServiceInitialization:
    """Tests for EmbeddingService initialization with auto-detection."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._model_loaded = False
        EmbeddingService._model_loading = False
        EmbeddingService._client_mode = False
        EmbeddingService._http_server_started = False

    def teardown_method(self):
        """Cleanup after each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._model_loaded = False
        EmbeddingService._model_loading = False
        EmbeddingService._client_mode = False
        EmbeddingService._http_server_started = False

    def test_initialization_with_explicit_client_provider(self):
        """Should use client mode when provider='client' in settings."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "embedding.provider": "client",
                "embedding.client_url": "http://127.0.0.1:18501",
                "embedding.dimension": 2560,
            }.get(key, default)

            service = EmbeddingService()
            service.initialize()

            assert service._client_mode is True
            assert service._backend == "http"
            assert service._client_url == "http://127.0.0.1:18501"

    def test_initialization_with_explicit_fallback_provider(self):
        """Should use fallback mode when provider='fallback' in settings."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "embedding.provider": "fallback",
                "embedding.dimension": 2560,
            }.get(key, default)

            service = EmbeddingService()
            service.initialize()

            assert service._backend == "fallback"
            assert service._client_mode is False

    def test_initialization_auto_detects_server(self):
        """Should connect as client when server port is already in use."""
        from omni.foundation.services.embedding import EmbeddingService

        # Mock port_in_use to return True (server already running)
        with patch.object(EmbeddingService, "_is_port_in_use", return_value=True):
            with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
                with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                    mock_setting.side_effect = lambda key, default=None: {
                        "embedding.provider": "",
                        "embedding.http_port": 18501,
                        "embedding.dimension": 2560,
                    }.get(key, default)

                    service = EmbeddingService()
                    service.initialize()

                    assert service._client_mode is True
                    assert service._backend == "http"
                    assert service._client_url == "http://127.0.0.1:18501"

    def test_initialization_starts_server_when_port_free(self):
        """Should start HTTP server when port is not in use."""
        from omni.foundation.services.embedding import EmbeddingService

        # Mock port_in_use to return False (no server running)
        with patch.object(EmbeddingService, "_is_port_in_use", return_value=False):
            with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                mock_setting.side_effect = lambda key, default=None: {
                    "embedding.provider": "",
                    "embedding.http_port": 18501,
                    "embedding.dimension": 2560,
                }.get(key, default)

                # Mock the HTTP server startup by patching time.sleep
                with patch("time.sleep"):  # Skip sleep
                    service = EmbeddingService()
                    service.initialize()

                    # Should have started HTTP server
                    assert service._http_server_started is True

    def test_initialization_idempotent(self):
        """Calling initialize multiple times should not re-initialize."""
        from omni.foundation.services.embedding import EmbeddingService

        call_count = 0

        def mock_is_port_in_use(port, timeout=0.5):
            return False

        def mock_get_setting(key, default=None):
            return {
                "embedding.provider": "",
                "embedding.http_port": 18501,
                "embedding.dimension": 2560,
            }.get(key, default)

        with patch.object(EmbeddingService, "_is_port_in_use", mock_is_port_in_use):
            with patch("omni.foundation.services.embedding.get_setting", mock_get_setting):
                with patch("time.sleep"):  # Skip sleep
                    service = EmbeddingService()
                    service.initialize()
                    first_http_state = service._http_server_started

                    service.initialize()
                    second_http_state = service._http_server_started

                    service.initialize()
                    third_http_state = service._http_server_started

                    # All should have same state (initialized once)
                    assert first_http_state == second_http_state == third_http_state
                    assert first_http_state is True


class TestEmbeddingServiceSingleton:
    """Tests for EmbeddingService singleton behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False

    def test_singleton_returns_same_instance(self):
        """Multiple calls to get_embedding_service should return same instance."""
        from omni.foundation.services.embedding import get_embedding_service

        service1 = get_embedding_service()
        service2 = get_embedding_service()

        assert service1 is service2

    def test_singleton_class_returns_same_instance(self):
        """Multiple instantiations should return same instance."""
        from omni.foundation.services.embedding import EmbeddingService

        service1 = EmbeddingService()
        service2 = EmbeddingService()

        assert service1 is service2


class TestEmbeddingServiceModelLoading:
    """Tests for background model loading."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = True
        EmbeddingService._model_loaded = False
        EmbeddingService._model_loading = False
        EmbeddingService._client_mode = False
        EmbeddingService._http_server_started = True

    def teardown_method(self):
        """Cleanup after each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._model_loaded = False
        EmbeddingService._model_loading = False
        EmbeddingService._client_mode = False

    def test_start_model_loading_skips_in_client_mode(self):
        """Should not load model in client mode."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        # Must set BEFORE calling start_model_loading
        service._client_mode = True

        # Mock _load_local_model to verify it's not called
        with patch.object(service, "_load_local_model") as mock_load:
            service.start_model_loading()
            # _load_local_model should NOT be called when in client mode
            mock_load.assert_not_called()

    def test_start_model_loading_skips_if_already_loaded(self):
        """Should not load model if already loaded."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._model_loaded = True

        service = EmbeddingService()
        service.start_model_loading()

        assert service._model_loading is False

    def test_start_model_loading_triggers_background_load(self):
        """Should start background thread for model loading."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch.object(EmbeddingService, "_load_local_model"):
            service = EmbeddingService()
            service.start_model_loading()

            # Should have started loading
            assert service._model_loading is True


class TestEmbeddingServiceEmbed:
    """Tests for embedding operations."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService
        import numpy as np

        EmbeddingService._instance = None
        EmbeddingService._initialized = True
        EmbeddingService._model_loaded = True
        EmbeddingService._backend = "local"
        EmbeddingService._client_mode = False
        EmbeddingService._model = MagicMock()
        # Use numpy array like real sentence-transformers
        EmbeddingService._model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        EmbeddingService._model.get_sentence_embedding_dimension.return_value = 3

    def teardown_method(self):
        """Cleanup after each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None

    def test_embed_single_text(self):
        """Should generate embedding for single text."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        result = service.embed("test text")

        assert len(result) == 1
        assert len(result[0]) == 3

    def test_embed_batch_texts(self):
        """Should generate embeddings for multiple texts."""
        from omni.foundation.services.embedding import EmbeddingService
        import numpy as np

        # Reset model mock for this specific test
        EmbeddingService._model = MagicMock()
        EmbeddingService._model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        EmbeddingService._model.get_sentence_embedding_dimension.return_value = 3

        service = EmbeddingService()
        result = service.embed_batch(["text1", "text2"])

        assert len(result) == 2

    def test_embed_uses_client_in_client_mode(self):
        """Should use HTTP client in client mode."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._client_mode = True
        EmbeddingService._client_url = "http://127.0.0.1:18501"

        mock_response = [[0.1, 0.2, 0.3]]
        with patch(
            "omni.foundation.services.embedding.EmbeddingService._embed_http",
            return_value=mock_response,
        ) as mock_client:
            service = EmbeddingService()
            result = service.embed("test")

            assert result == mock_response
            mock_client.assert_called_once()


class TestEmbeddingServiceProperties:
    """Tests for EmbeddingService properties."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = True
        EmbeddingService._backend = "local"
        EmbeddingService._dimension = 2560
        EmbeddingService._model_loaded = True
        EmbeddingService._model_loading = False

    def test_backend_property(self):
        """Should return backend type."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.backend == "local"

    def test_dimension_property(self):
        """Should return embedding dimension."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.dimension == 2560

    def test_is_loaded_property(self):
        """Should indicate if model is loaded."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.is_loaded is True

    def test_is_loading_property(self):
        """Should indicate if model is loading."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._model_loading = True
        service = EmbeddingService()
        assert service.is_loading is True


class TestEmbeddingServiceLazyLoad:
    """Tests for lazy loading behavior - embedding should NOT be loaded until embed() is called."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._model_loaded = False
        EmbeddingService._model_loading = False
        EmbeddingService._client_mode = False
        EmbeddingService._http_server_started = False

    def teardown_method(self):
        """Cleanup after each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._model_loaded = False
        EmbeddingService._model_loading = False
        EmbeddingService._client_mode = False

    def test_creating_service_does_not_load_model(self):
        """Creating EmbeddingService should NOT load the model."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()

        assert service._initialized is False
        assert service._model_loaded is False
        assert service._model_loading is False

    def test_embed_auto_detects_mcp_server(self):
        """embed() should auto-detect MCP server if not initialized."""
        from omni.foundation.services.embedding import EmbeddingService

        # Mock port_in_use to return True (MCP server running)
        with patch.object(EmbeddingService, "_is_port_in_use", return_value=True):
            with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
                with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                    mock_setting.side_effect = lambda key, default=None: {
                        "embedding.http_port": 18501,
                        "embedding.dimension": 1024,
                    }.get(key, default)

                    service = EmbeddingService()

                    # Mock _embed_http to avoid actual HTTP call
                    with patch.object(
                        service, "_embed_http", return_value=[[0.1, 0.2]]
                    ) as mock_http:
                        result = service.embed("test")

                        # Should have auto-detected and used client mode
                        assert service._initialized is True
                        assert service._client_mode is True
                        assert service._backend == "http"
                        mock_http.assert_called_once()

    def test_embed_batch_auto_detects_mcp_server(self):
        """embed_batch() should auto-detect MCP server if not initialized."""
        from omni.foundation.services.embedding import EmbeddingService

        # Mock port_in_use to return True (MCP server running)
        with patch.object(EmbeddingService, "_is_port_in_use", return_value=True):
            with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
                with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                    mock_setting.side_effect = lambda key, default=None: {
                        "embedding.http_port": 18501,
                        "embedding.dimension": 1024,
                    }.get(key, default)

                    service = EmbeddingService()

                    # Mock _embed_http to avoid actual HTTP call
                    with patch.object(
                        service, "_embed_http", return_value=[[0.1, 0.2], [0.3, 0.4]]
                    ) as mock_http:
                        result = service.embed_batch(["test1", "test2"])

                        # Should have auto-detected and used client mode
                        assert service._initialized is True
                        assert service._client_mode is True
                        assert service._backend == "http"
                        mock_http.assert_called_once()

    def test_embed_does_not_auto_detect_if_already_initialized(self):
        """embed() should not re-run auto-detect if already initialized."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        service._initialized = True
        service._client_mode = True
        service._backend = "http"

        # Track if auto_detect is called
        with patch.object(service, "_auto_detect_and_init") as mock_auto:
            with patch.object(service, "_embed_http", return_value=[[0.1, 0.2]]) as mock_http:
                service.embed("test")

                # Should NOT have called auto_detect
                mock_auto.assert_not_called()
                mock_http.assert_called_once()

    def test_embed_does_not_load_local_model_in_client_mode(self):
        """embed() should NOT call _load_local_model when in client mode."""
        from omni.foundation.services.embedding import EmbeddingService

        # Simulate MCP server is running
        with patch.object(EmbeddingService, "_is_port_in_use", return_value=True):
            with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
                with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                    mock_setting.side_effect = lambda key, default=None: {
                        "embedding.http_port": 18501,
                        "embedding.dimension": 1024,
                    }.get(key, default)

                    service = EmbeddingService()

                    # Ensure auto-detect runs
                    with patch.object(
                        service, "_embed_http", return_value=[[0.1, 0.2]]
                    ) as mock_http:
                        with patch.object(service, "_load_local_model") as mock_load:
                            service.embed("test")

                            # Should NOT have called _load_local_model
                            mock_load.assert_not_called()

    def test_embed_uses_fallback_when_no_mcp_and_no_model(self):
        """embed() should use fallback when no MCP server and model not loaded."""
        from omni.foundation.services.embedding import EmbeddingService

        # Create service and set to fallback mode (simulating no local model)
        service = EmbeddingService()
        service._backend = "fallback"
        service._dimension = 8
        service._model = None  # No local model loaded

        # Should use fallback (hash-based embeddings)
        result = service._embed_fallback(["hello world"])

        # Should return a vector of the configured dimension
        assert len(result) == 1
        assert len(result[0]) == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
