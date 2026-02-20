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
import time
from unittest.mock import patch, MagicMock


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


class TestEmbeddingServiceInitialization:
    """Tests for EmbeddingService initialization with auto-detection."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._client_mode = False

    def teardown_method(self):
        """Cleanup after each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._client_mode = False

    def test_initialization_with_explicit_client_provider(self):
        """Should use client mode when provider='client' and HTTP server is healthy."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
            with patch.object(
                EmbeddingService, "_verify_embedding_service_works", return_value=True
            ):
                with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                    mock_setting.side_effect = lambda key, default=None: {
                        "embedding.provider": "client",
                        "embedding.client_url": "http://127.0.0.1:18501",
                        "embedding.dimension": 2560,
                        "embedding.http_port": 18501,
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
                "embedding.http_port": 18501,
            }.get(key, default)

            service = EmbeddingService()
            service.initialize()

            assert service._backend == "fallback"
            assert service._client_mode is False

    def test_initialization_ollama_normalizes_localhost_to_ipv4(self):
        """Should normalize localhost API base to IPv4 loopback for Ollama."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: {
                "embedding.provider": "ollama",
                "embedding.litellm_model": "ollama/qwen3-embedding:0.6b",
                "embedding.litellm_api_base": "http://localhost:11434",
                "embedding.dimension": 1024,
                "embedding.http_port": 18501,
            }.get(key, default)

            service = EmbeddingService()
            service.initialize()

            assert service._backend == "litellm"
            assert service._litellm_api_base == "http://127.0.0.1:11434"

    def test_initialization_auto_detects_server(self):
        """Should connect as client when server port is already in use."""
        from omni.foundation.services.embedding import EmbeddingService

        # Mock port_in_use and health/embed check (server already running)
        with patch.object(EmbeddingService, "_is_port_in_use", return_value=True):
            with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
                with patch.object(
                    EmbeddingService, "_verify_embedding_service_works", return_value=True
                ):
                    with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                        mock_setting.side_effect = lambda key, default=None: {
                            "embedding.provider": "",
                            "embedding.http_port": 18501,
                            "embedding.dimension": 2560,
                            "embedding.client_url": "http://127.0.0.1:18501",
                        }.get(key, default)

                        service = EmbeddingService()
                        service.initialize()

                        assert service._client_mode is True
                        assert service._backend == "http"
                        assert service._client_url == "http://127.0.0.1:18501"

    def test_initialization_uses_fallback_when_port_free(self):
        """When port is not in use (auto), should use fallback backend."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch.object(EmbeddingService, "_is_port_in_use", return_value=False):
            with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                mock_setting.side_effect = lambda key, default=None: {
                    "embedding.provider": "",
                    "embedding.http_port": 18501,
                    "embedding.dimension": 2560,
                }.get(key, default)

                service = EmbeddingService()
                service.initialize()

                assert service._backend == "fallback"
                assert service._client_mode is False
                assert service._dimension == 2560

    def test_initialization_idempotent(self):
        """Calling initialize multiple times should not re-initialize."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch.object(EmbeddingService, "_is_port_in_use", return_value=False):
            with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                mock_setting.side_effect = lambda key, default=None: {
                    "embedding.provider": "",
                    "embedding.http_port": 18501,
                    "embedding.dimension": 2560,
                }.get(key, default)

                service = EmbeddingService()
                service.initialize()
                first_backend = service._backend

                service.initialize()
                second_backend = service._backend

                assert first_backend == second_backend == "fallback"


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
    """start_model_loading is a no-op (no in-process model)."""

    def test_start_model_loading_no_op(self):
        """start_model_loading does nothing and does not raise."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        service = EmbeddingService()
        service.start_model_loading()
        assert service.is_loading is False


class TestEmbeddingServiceEmbed:
    """Tests for embedding operations."""

    def setup_method(self):
        """Reset singleton; use fallback backend for embed tests."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = True
        EmbeddingService._backend = "fallback"
        EmbeddingService._dimension = 3
        EmbeddingService._client_mode = False

    def teardown_method(self):
        """Cleanup after each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None

    def test_embed_single_text(self):
        """Should generate embedding for single text (fallback)."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        result = service.embed("test text")

        assert len(result) == 1
        assert len(result[0]) == 3

    def test_embed_batch_texts(self):
        """Should generate embeddings for multiple texts (fallback)."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        result = service.embed_batch(["text1", "text2"])

        assert len(result) == 2
        assert all(len(v) == 3 for v in result)

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
        EmbeddingService._backend = "fallback"
        EmbeddingService._dimension = 2560

    def test_backend_property(self):
        """Should return backend type."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.backend == "fallback"

    def test_dimension_property(self):
        """Should return embedding dimension."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.dimension == 2560

    def test_is_loaded_property(self):
        """is_loaded is True when initialized (no in-process model)."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.is_loaded is True

    def test_is_loading_property(self):
        """is_loading is always False (no in-process model)."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        assert service.is_loading is False


class TestEmbeddingServiceLazyLoad:
    """Tests for lazy loading behavior - embedding should NOT be loaded until embed() is called."""

    def setup_method(self):
        """Reset singleton before each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._client_mode = False

    def teardown_method(self):
        """Cleanup after each test."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = False
        EmbeddingService._client_mode = False

    def test_creating_service_does_not_load_model(self):
        """Creating EmbeddingService should NOT initialize until embed is used."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()

        assert service._initialized is False

    def test_embed_auto_detects_mcp_server(self):
        """embed() should auto-detect MCP server if not initialized."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch.object(EmbeddingService, "_is_port_in_use", return_value=True):
            with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
                with patch.object(
                    EmbeddingService, "_verify_embedding_service_works", return_value=True
                ):
                    with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                        mock_setting.side_effect = lambda key, default=None: {
                            "embedding.provider": "",
                            "embedding.http_port": 18501,
                            "embedding.dimension": 1024,
                            "embedding.client_url": "http://127.0.0.1:18501",
                        }.get(key, default)

                        service = EmbeddingService()

                        # Mock _embed_http to avoid actual HTTP call
                        with patch.object(
                            service, "_embed_http", return_value=[[0.1, 0.2]]
                        ) as mock_http:
                            result = service.embed("test")

                            assert service._initialized is True
                            assert service._client_mode is True
                            assert service._backend == "http"
                            mock_http.assert_called_once()

    def test_embed_client_provider_checks_health_before_client_mode(self):
        """When provider=client, _auto_detect_and_init runs health check; if healthy, uses client mode."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch.object(
            EmbeddingService, "_check_http_server_healthy", return_value=True
        ) as mock_health:
            with patch.object(
                EmbeddingService, "_verify_embedding_service_works", return_value=True
            ):
                with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                    mock_setting.side_effect = lambda key, default=None: {
                        "embedding.provider": "client",
                        "embedding.client_url": "http://127.0.0.1:18501",
                        "embedding.http_port": 18501,
                        "embedding.dimension": 1024,
                    }.get(key, default)

                    service = EmbeddingService()
                    with patch.object(service, "_embed_http", return_value=[[0.1] * 1024]):
                        service.embed("test")

                    mock_health.assert_called()
                    assert service._initialized is True
                    assert service._client_mode is True
                    assert service._client_url == "http://127.0.0.1:18501"

    def test_embed_batch_auto_detects_mcp_server(self):
        """embed_batch() should auto-detect MCP server if not initialized."""
        from omni.foundation.services.embedding import EmbeddingService

        with patch.object(EmbeddingService, "_is_port_in_use", return_value=True):
            with patch.object(EmbeddingService, "_check_http_server_healthy", return_value=True):
                with patch.object(
                    EmbeddingService, "_verify_embedding_service_works", return_value=True
                ):
                    with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
                        mock_setting.side_effect = lambda key, default=None: {
                            "embedding.provider": "",
                            "embedding.http_port": 18501,
                            "embedding.dimension": 1024,
                            "embedding.client_url": "http://127.0.0.1:18501",
                        }.get(key, default)

                        service = EmbeddingService()

                        with patch.object(
                            service, "_embed_http", return_value=[[0.1, 0.2], [0.3, 0.4]]
                        ) as mock_http:
                            result = service.embed_batch(["test1", "test2"])

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

    def test_embed_uses_fallback_when_no_mcp_and_no_model(self):
        """_embed_fallback returns vectors of configured dimension."""
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        service._backend = "fallback"
        service._dimension = 8

        result = service._embed_fallback(["hello world"])

        assert len(result) == 1
        assert len(result[0]) == 8


class TestEmbeddingServiceHttpRaisesOnFailure:
    """_embed_http: on HTTP failure, raise EmbeddingUnavailableError (no fallback)."""

    def setup_method(self):
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = True
        EmbeddingService._backend = "http"
        EmbeddingService._client_mode = True
        EmbeddingService._client_url = "http://127.0.0.1:18501"
        EmbeddingService._dimension = 256

    def teardown_method(self):
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._backend = "fallback"

    def test_embed_http_raises_on_http_error(self):
        """When HTTP client raises, embed() propagates EmbeddingUnavailableError."""
        from omni.foundation.services.embedding import EmbeddingService, EmbeddingUnavailableError

        service = EmbeddingService()
        with patch("omni.foundation.embedding_client.get_embedding_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.sync_embed_batch.side_effect = RuntimeError("connection refused")
            mock_get_client.return_value = mock_client
            with pytest.raises(EmbeddingUnavailableError) as exc_info:
                service.embed("hello")
        assert "connection refused" in str(exc_info.value)
        assert service._client_mode is True  # No switch to fallback

    def test_embed_batch_raises_on_http_error(self):
        """When HTTP client fails, embed_batch raises EmbeddingUnavailableError."""
        from omni.foundation.services.embedding import EmbeddingService, EmbeddingUnavailableError

        service = EmbeddingService()
        with patch("omni.foundation.embedding_client.get_embedding_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.sync_embed_batch.side_effect = RuntimeError("HTTP 500")
            mock_get_client.return_value = mock_client
            with pytest.raises(EmbeddingUnavailableError) as exc_info:
                service.embed_batch(["text"])
        assert "HTTP 500" in str(exc_info.value)


class TestEmbeddingServiceLiteLLMResilience:
    """LiteLLM transient failure handling (retry + circuit breaker)."""

    def setup_method(self):
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._initialized = True
        EmbeddingService._backend = "litellm"
        EmbeddingService._litellm_model = "ollama/qwen3-embedding:0.6b"
        EmbeddingService._litellm_api_base = "http://localhost:11434"
        EmbeddingService._litellm_circuit_open_until = 0.0
        EmbeddingService._litellm_last_error = None

    def teardown_method(self):
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        EmbeddingService._litellm_circuit_open_until = 0.0
        EmbeddingService._litellm_last_error = None
        EmbeddingService._backend = "fallback"

    def test_embed_litellm_transient_failure_opens_circuit(self):
        from omni.foundation.services.embedding import EmbeddingService, EmbeddingUnavailableError

        service = EmbeddingService()
        settings = {
            "embedding.timeout": 1,
            "embedding.litellm_connect_retries": 3,
            "embedding.litellm_retry_backoff_ms": 0,
            "embedding.litellm_circuit_open_secs": 7,
        }
        with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: settings.get(key, default)
            with patch("litellm.embedding", side_effect=RuntimeError("Connection refused")):
                with pytest.raises(EmbeddingUnavailableError) as exc_info:
                    service._embed_litellm(["hello"])

        message = str(exc_info.value).lower()
        assert "endpoint unavailable" in message
        assert "retries=3" in message
        assert service._litellm_circuit_open_until > time.monotonic()
        assert service._litellm_last_error is not None

    def test_embed_litellm_circuit_open_fails_fast(self):
        from omni.foundation.services.embedding import EmbeddingService, EmbeddingUnavailableError

        service = EmbeddingService()
        service._litellm_circuit_open_until = time.monotonic() + 20.0
        service._litellm_last_error = "connection refused"
        settings = {
            "embedding.timeout": 1,
            "embedding.litellm_connect_retries": 3,
            "embedding.litellm_retry_backoff_ms": 0,
            "embedding.litellm_circuit_open_secs": 5,
        }
        with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: settings.get(key, default)
            with patch("litellm.embedding") as mock_embedding:
                with pytest.raises(EmbeddingUnavailableError) as exc_info:
                    service._embed_litellm(["hello"])
        assert "circuit_open_remaining_secs" in str(exc_info.value)
        mock_embedding.assert_not_called()

    def test_embed_litellm_recovers_and_clears_circuit(self):
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        settings = {
            "embedding.timeout": 1,
            "embedding.litellm_connect_retries": 2,
            "embedding.litellm_retry_backoff_ms": 0,
            "embedding.litellm_circuit_open_secs": 5,
        }

        class _Resp:
            data = [{"embedding": [0.1, 0.2, 0.3]}]

        with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: settings.get(key, default)
            with patch(
                "litellm.embedding",
                side_effect=[RuntimeError("Connection refused"), _Resp()],
            ):
                vectors = service._embed_litellm(["hello"])

        assert len(vectors) == 1
        assert vectors[0][:3] == [0.1, 0.2, 0.3]
        assert service._litellm_circuit_open_until == 0.0
        assert service._litellm_last_error is None

    def test_embed_litellm_retries_loopback_alias_and_recovers(self):
        from omni.foundation.services.embedding import EmbeddingService

        service = EmbeddingService()
        service._litellm_api_base = "http://localhost:11434"
        settings = {
            "embedding.provider": "ollama",
            "embedding.timeout": 1,
            "embedding.litellm_connect_retries": 2,
            "embedding.litellm_retry_backoff_ms": 0,
            "embedding.litellm_circuit_open_secs": 5,
        }

        class _Resp:
            data = [{"embedding": [0.1, 0.2, 0.3]}]

        def _embedding_side_effect(*_args, **kwargs):
            api_base = kwargs.get("api_base")
            if api_base == "http://localhost:11434":
                raise RuntimeError("Connection refused")
            if api_base == "http://127.0.0.1:11434":
                return _Resp()
            raise AssertionError(f"unexpected api_base: {api_base}")

        with patch("omni.foundation.services.embedding.get_setting") as mock_setting:
            mock_setting.side_effect = lambda key, default=None: settings.get(key, default)
            with patch("litellm.embedding", side_effect=_embedding_side_effect) as mock_embedding:
                vectors = service._embed_litellm(["hello"])

        assert len(vectors) == 1
        assert vectors[0][:3] == [0.1, 0.2, 0.3]
        assert mock_embedding.call_count == 2
        assert service._litellm_api_base == "http://127.0.0.1:11434"


class TestEmbeddingServiceFallbackDimension:
    """_embed_fallback returns vectors of configured dimension."""

    def test_embed_fallback_output_shape(self):
        """_embed_fallback returns list of vectors, each of length _dimension."""
        from omni.foundation.services.embedding import EmbeddingService

        EmbeddingService._instance = None
        service = EmbeddingService()
        service._dimension = 64
        result = service._embed_fallback(["a", "b"])
        assert len(result) == 2
        assert all(len(v) == 64 for v in result)
        assert all(isinstance(x, float) for v in result for x in v)


class TestEmbeddingOverride:
    """When an override is set (e.g. by skill hooks), embed/embed_batch delegate to it."""

    def test_embed_batch_uses_override_when_set(self):
        from omni.foundation.services.embedding import (
            get_embedding_override,
            get_embedding_service,
            set_embedding_override,
        )

        class MockOverride:
            def embed(self, text: str):
                return [[0.1] * 8]

            def embed_batch(self, texts: list[str]):
                return [[0.2] * 8 for _ in texts]

        try:
            set_embedding_override(MockOverride())
            svc = get_embedding_service()
            out = svc.embed_batch(["a", "b"])
            assert out == [[0.2] * 8, [0.2] * 8]
        finally:
            set_embedding_override(None)
        assert get_embedding_override() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
