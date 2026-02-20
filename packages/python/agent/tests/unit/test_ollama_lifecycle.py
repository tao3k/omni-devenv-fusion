"""Unit tests for Ollama lifecycle (detect, start, pull, stop) used by MCP command."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from omni.agent.ollama_lifecycle import (
    ensure_ollama_for_embedding,
    find_ollama_binary,
    model_name_from_litellm,
    parse_ollama_api_base,
    stop_ollama_subprocess,
)


class TestModelNameFromLitellm:
    """Tests for model_name_from_litellm."""

    def test_ollama_slash_prefix_stripped(self) -> None:
        assert model_name_from_litellm("ollama/qwen3-embedding:0.6b") == "qwen3-embedding:0.6b"

    def test_empty_returns_default(self) -> None:
        assert model_name_from_litellm("") == "qwen3-embedding:0.6b"

    def test_no_slash_returns_stripped(self) -> None:
        assert model_name_from_litellm("nomic-embed-text") == "nomic-embed-text"


class TestParseOllamaApiBase:
    """Tests for parse_ollama_api_base."""

    def test_localhost_11434(self) -> None:
        assert parse_ollama_api_base("http://localhost:11434") == ("localhost", 11434)

    def test_127_with_port(self) -> None:
        assert parse_ollama_api_base("http://127.0.0.1:11434") == ("127.0.0.1", 11434)

    def test_no_port_defaults_11434(self) -> None:
        # urlparse keeps hostname as "localhost" when no port; we default port to 11434
        assert parse_ollama_api_base("http://localhost") == ("localhost", 11434)

    def test_invalid_returns_defaults(self) -> None:
        host, port = parse_ollama_api_base("not-a-url")
        assert host == "127.0.0.1"
        assert port == 11434


class TestFindOllamaBinary:
    """Tests for find_ollama_binary."""

    def test_returns_path_when_found(self) -> None:
        with patch(
            "omni.agent.ollama_lifecycle.shutil.which", return_value="/usr/local/bin/ollama"
        ):
            assert find_ollama_binary() == "/usr/local/bin/ollama"

    def test_returns_none_when_not_found(self) -> None:
        with patch("omni.agent.ollama_lifecycle.shutil.which", return_value=None):
            assert find_ollama_binary() is None


class TestEnsureOllamaForEmbedding:
    """Tests for ensure_ollama_for_embedding (mocked; no real subprocess)."""

    @pytest.mark.parametrize("provider", ["client", "xinference", ""])
    def test_returns_none_when_provider_not_ollama(self, provider: str) -> None:
        with patch("omni.agent.ollama_lifecycle.get_setting") as m_get:
            m_get.side_effect = lambda k: (
                provider
                if k == "embedding.provider"
                else "http://localhost:11434"
                if k == "embedding.litellm_api_base"
                else "ollama/qwen3-embedding:0.6b"
                if k == "embedding.litellm_model"
                else None
            )
            assert ensure_ollama_for_embedding() is None

    def test_returns_none_when_litellm_provider_is_not_ollama_model(self) -> None:
        with patch("omni.agent.ollama_lifecycle.get_setting") as m_get:
            m_get.side_effect = lambda k: (
                "litellm"
                if k == "embedding.provider"
                else "http://localhost:11434"
                if k == "embedding.litellm_api_base"
                else "openai/text-embedding-3-small"
                if k == "embedding.litellm_model"
                else None
            )
            with patch("omni.agent.ollama_lifecycle.find_ollama_binary") as m_find:
                assert ensure_ollama_for_embedding() is None
                m_find.assert_not_called()

    def test_litellm_with_ollama_model_uses_ollama_management_path(self) -> None:
        with patch("omni.agent.ollama_lifecycle.get_setting") as m_get:
            m_get.side_effect = lambda k: (
                "litellm"
                if k == "embedding.provider"
                else "http://localhost:11434"
                if k == "embedding.litellm_api_base"
                else "ollama/qwen3-embedding:0.6b"
                if k == "embedding.litellm_model"
                else None
            )
            with patch(
                "omni.agent.ollama_lifecycle.find_ollama_binary", return_value=None
            ) as m_find:
                assert ensure_ollama_for_embedding() is None
                m_find.assert_called_once()

    def test_returns_none_when_ollama_not_in_path(self) -> None:
        with patch("omni.agent.ollama_lifecycle.get_setting") as m_get:
            m_get.side_effect = lambda k: (
                "ollama"
                if k == "embedding.provider"
                else "http://localhost:11434"
                if k == "embedding.litellm_api_base"
                else "ollama/qwen3-embedding:0.6b"
                if k == "embedding.litellm_model"
                else None
            )
            with patch("omni.agent.ollama_lifecycle.find_ollama_binary", return_value=None):
                assert ensure_ollama_for_embedding() is None

    def test_returns_none_when_already_listening(self) -> None:
        with patch("omni.agent.ollama_lifecycle.get_setting") as m_get:
            m_get.side_effect = lambda k: (
                "ollama"
                if k == "embedding.provider"
                else "http://localhost:11434"
                if k == "embedding.litellm_api_base"
                else "ollama/qwen3-embedding:0.6b"
                if k == "embedding.litellm_model"
                else None
            )
            with (
                patch(
                    "omni.agent.ollama_lifecycle.find_ollama_binary", return_value="/usr/bin/ollama"
                ),
                patch("omni.agent.ollama_lifecycle.is_ollama_listening", return_value=True),
                patch("omni.agent.ollama_lifecycle.pull_ollama_model", return_value=True),
            ):
                assert ensure_ollama_for_embedding() is None


class TestStopOllamaSubprocess:
    """Tests for stop_ollama_subprocess."""

    def test_none_is_noop(self) -> None:
        stop_ollama_subprocess(None)

    def test_terminates_and_waits(self) -> None:
        proc = subprocess.Popen(
            ["true"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        stop_ollama_subprocess(proc, timeout_sec=2.0)
        assert proc.poll() is not None
