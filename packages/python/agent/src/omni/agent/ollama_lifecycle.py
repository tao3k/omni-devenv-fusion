"""
Ollama lifecycle for MCP: detect binary, start serve subprocess, pull model, stop on exit.

When embedding is Ollama-backed, the MCP command can:
- Detect if the ollama binary is installed (PATH).
- If the configured API host:port is not listening, start `ollama serve` in a subprocess.
- Wait for the server to be ready, then run `ollama pull <model>` so the embedding model exists.
- On MCP shutdown, terminate the subprocess we started (only if we started it).

Ollama is not started if:
- embedding is not Ollama-backed
- ollama binary is not found
- The configured host:port is already in use (assume user runs Ollama themselves)
"""

from __future__ import annotations

import atexit
import contextlib
import json
import shutil
import socket
import subprocess
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting

# Process we started so it can be stopped on shutdown (set by ensure_ollama_for_embedding)
_managed_ollama_process: subprocess.Popen[bytes] | None = None
_atexit_registered = False

log = get_logger("omni.agent.ollama")


def _ollama_models_dir() -> str:
    """Return project models directory for Ollama (.data/models). Ensures it exists."""
    try:
        from omni.foundation.config.prj import PRJ_DATA

        path = PRJ_DATA.ensure_dir("models")
        return str(path)
    except Exception:
        return ""


# Default Ollama API port
DEFAULT_OLLAMA_PORT = 11434


def get_embedding_ollama_config() -> dict[str, Any]:
    """Read embedding config relevant to Ollama (provider, api_base, litellm_model)."""
    provider = (get_setting("embedding.provider") or "").strip().lower()
    api_base = (get_setting("embedding.litellm_api_base") or "").strip() or "http://localhost:11434"
    litellm_model = (
        get_setting("embedding.litellm_model") or ""
    ).strip() or "ollama/qwen3-embedding:0.6b"
    return {"provider": provider, "api_base": api_base, "litellm_model": litellm_model}


def is_ollama_backed_embedding(provider: str, litellm_model: str) -> bool:
    """Return True when embedding config resolves to an Ollama-backed flow."""
    normalized_provider = (provider or "").strip().lower()
    normalized_model = (litellm_model or "").strip().lower()
    return normalized_provider == "ollama" or (
        normalized_provider == "litellm" and normalized_model.startswith("ollama/")
    )


def find_ollama_binary() -> str | None:
    """Return path to ollama binary if found in PATH, else None."""
    return shutil.which("ollama")


def parse_ollama_api_base(api_base: str) -> tuple[str, int]:
    """Parse embedding.litellm_api_base (e.g. http://localhost:11434) into (host, port)."""
    try:
        parsed = urlparse(api_base)
        host = (parsed.hostname or "127.0.0.1").strip() or "127.0.0.1"
        port = parsed.port if parsed.port is not None else DEFAULT_OLLAMA_PORT
        return host, port
    except Exception:
        return "127.0.0.1", DEFAULT_OLLAMA_PORT


def is_ollama_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return True if Ollama API responds on host:port (e.g. GET /api/version)."""
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/api/version",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        pass
    # Fallback: TCP connect only (in case path differs)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except Exception:
        return False


def wait_for_ollama(host: str, port: int, timeout_sec: float = 30.0, interval: float = 0.5) -> bool:
    """Poll until Ollama API is reachable or timeout. Returns True if ready."""
    import time

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if is_ollama_listening(host, port, timeout=interval):
            return True
        time.sleep(interval)
    return False


def ollama_has_model(host: str, port: int, model_name: str, timeout: float = 2.0) -> bool:
    """Return True if the model is already present (GET /api/tags)."""
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/api/tags",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") or []
        for m in models:
            name = (m.get("name") or "").strip()
            if name == model_name or name.startswith(model_name + ":"):
                return True
        return False
    except Exception:
        return False


def start_ollama_serve(host: str, port: int) -> subprocess.Popen[bytes] | None:
    """Start `ollama serve` in a subprocess. OLLAMA_HOST is set so server binds to host:port.
    OLLAMA_MODELS is set to project .data/models so models are stored in one place.

    Returns the Popen instance if started, None on failure. Caller must stop it on shutdown.
    """
    ollama = find_ollama_binary()
    if not ollama:
        return None
    env = dict(__import__("os").environ)
    env["OLLAMA_HOST"] = f"{host}:{port}"
    models_dir = _ollama_models_dir()
    if models_dir:
        env["OLLAMA_MODELS"] = models_dir
        log.info("Ollama models directory: %s", models_dir)
    try:
        proc = subprocess.Popen(
            [ollama, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        log.info("Started Ollama serve subprocess", host=host, port=port, pid=proc.pid)
        return proc
    except Exception as e:
        log.warning("Failed to start ollama serve: %s", e)
        return None


def pull_ollama_model(host: str, port: int, model_name: str, timeout_sec: float = 300.0) -> bool:
    """Run `ollama pull <model_name>`. Logs so user sees we are downloading, not stuck."""
    ollama = find_ollama_binary()
    if not ollama:
        return False
    env = dict(__import__("os").environ)
    env["OLLAMA_HOST"] = f"{host}:{port}"
    models_dir = _ollama_models_dir()
    if models_dir:
        env["OLLAMA_MODELS"] = models_dir

    log.info(
        "Downloading embedding model '%s' (this may take a few minutes on first run)...",
        model_name,
    )
    try:
        result = subprocess.run(
            [ollama, "pull", model_name],
            stdin=subprocess.DEVNULL,
            stdout=None,
            stderr=None,
            timeout=timeout_sec,
            env=env,
            check=False,
        )
        if result.returncode == 0:
            log.info("Embedding model '%s' ready.", model_name)
            return True
        log.warning("Ollama pull exited with code %s", result.returncode)
        return False
    except subprocess.TimeoutExpired:
        log.warning("Ollama pull timed out", model=model_name)
        return False
    except Exception as e:
        log.warning("Ollama pull failed: %s", e)
        return False


def stop_ollama_subprocess(proc: subprocess.Popen[bytes] | None, timeout_sec: float = 5.0) -> None:
    """Gracefully terminate the Ollama subprocess we started. No-op if proc is None."""
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        log.warning("Ollama subprocess did not exit in time, killing")
        proc.kill()
        proc.wait(timeout=2.0)
    except Exception as e:
        log.debug("Error stopping Ollama subprocess: %s", e)
    finally:
        with contextlib.suppress(Exception):
            proc.poll()


def model_name_from_litellm(litellm_model: str) -> str:
    """Extract Ollama model name from embedding.litellm_model (e.g. ollama/qwen3-embedding:0.6b -> qwen3-embedding:0.6b)."""
    if not litellm_model:
        return "qwen3-embedding:0.6b"
    if "/" in litellm_model:
        return litellm_model.split("/", 1)[1].strip()
    return litellm_model.strip()


def _stop_managed_ollama() -> None:
    """Stop the Ollama subprocess we started (if any). Safe to call multiple times."""
    global _managed_ollama_process
    if _managed_ollama_process is None:
        return
    stop_ollama_subprocess(_managed_ollama_process)
    _managed_ollama_process = None


def ensure_ollama_for_embedding() -> subprocess.Popen[bytes] | None:
    """If embedding is Ollama-backed, ensure Ollama is running and model is pulled.

    - If ollama is not in PATH, log and return None.
    - If the configured API host:port is already listening, only pull the model (if needed) and return None.
    - Otherwise start `ollama serve` in a subprocess, wait for ready, pull the model, store in
      _managed_ollama_process (stopped at process exit via atexit), and return the Popen.
    Callers can call stop_managed_ollama() for early shutdown (e.g. MCP graceful exit).
    """
    global _managed_ollama_process, _atexit_registered

    cfg = get_embedding_ollama_config()
    if not is_ollama_backed_embedding(cfg["provider"], cfg["litellm_model"]):
        return None

    if not find_ollama_binary():
        log.warning(
            "Embedding provider is ollama but 'ollama' binary not found in PATH. "
            "Install Ollama or set embedding.provider to another value."
        )
        return None

    host, port = parse_ollama_api_base(cfg["api_base"])
    model_name = model_name_from_litellm(cfg["litellm_model"])

    if is_ollama_listening(host, port):
        if ollama_has_model(host, port, model_name):
            log.info(
                "Ollama already running at %s:%s; embedding model '%s' present",
                host,
                port,
                model_name,
            )
        else:
            log.info("Ollama already running at %s:%s; pulling embedding model", host, port)
            pull_ollama_model(host, port, model_name)
        return None

    proc = start_ollama_serve(host, port)
    if proc is None:
        return None

    if not wait_for_ollama(host, port, timeout_sec=30.0):
        log.warning("Ollama serve did not become ready in time; stopping subprocess")
        stop_ollama_subprocess(proc)
        return None

    if ollama_has_model(host, port, model_name):
        log.info("Embedding model '%s' already present (skipping pull)", model_name)
    else:
        pull_ollama_model(host, port, model_name)
    _managed_ollama_process = proc
    if not _atexit_registered:
        atexit.register(_stop_managed_ollama)
        _atexit_registered = True
    return proc
