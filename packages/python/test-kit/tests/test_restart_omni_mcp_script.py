"""Integration tests for scripts/channel/restart-omni-mcp.sh."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import textwrap
import time
import urllib.request
from pathlib import Path

from omni.foundation.runtime.gitops import get_project_root


def _reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_mock_uv(tmp_path: Path) -> Path:
    mock_server = tmp_path / "mock_mcp_server.py"
    mock_server.write_text(
        textwrap.dedent(
            """
            import os
            import signal
            import threading
            import time
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


            def _parse_host_port(argv):
                host = "127.0.0.1"
                port = None
                index = 0
                while index < len(argv):
                    token = argv[index]
                    if token == "--host" and index + 1 < len(argv):
                        host = argv[index + 1]
                        index += 2
                        continue
                    if token == "--port" and index + 1 < len(argv):
                        port = int(argv[index + 1])
                        index += 2
                        continue
                    index += 1
                if port is None:
                    raise SystemExit("missing --port")
                return host, port


            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == "/health":
                        payload = b'{"status":"healthy","ready":true,"initializing":false}'
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    self.send_response(404)
                    self.end_headers()

                def log_message(self, *_args, **_kwargs):
                    return


            host, port = _parse_host_port(os.sys.argv[1:])
            server = ThreadingHTTPServer((host, port), Handler)


            def _stop(*_args):
                server.shutdown()


            signal.signal(signal.SIGTERM, _stop)
            signal.signal(signal.SIGINT, _stop)

            mode = os.environ.get("MOCK_MCP_MODE", "stable")
            if mode == "flaky":
                delay = float(os.environ.get("MOCK_MCP_FLAKY_EXIT_DELAY", "0.3"))

                def _shutdown_later():
                    time.sleep(delay)
                    server.shutdown()

                threading.Thread(target=_shutdown_later, daemon=True).start()

            server.serve_forever()
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    uv_script = tmp_path / "uv"
    uv_script.write_text(
        textwrap.dedent(
            """
            #!/usr/bin/env bash
            set -euo pipefail
            SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
            exec python3 "${SCRIPT_DIR}/mock_mcp_server.py" "$@"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    uv_script.chmod(0o755)
    return uv_script


def _health_ok(port: int, timeout_secs: float = 1.0) -> bool:
    request = urllib.request.Request(f"http://127.0.0.1:{port}/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_secs) as response:
            return response.status == 200
    except Exception:
        return False


def _terminate_pid_from_file(path: Path) -> None:
    if not path.exists():
        return
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return
    pid = int(raw)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(40):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _run_restart_script(
    *,
    port: int,
    runtime_dir: Path,
    env: dict[str, str],
    stabilize_secs: int,
) -> subprocess.CompletedProcess[str]:
    root = get_project_root()
    script = root / "scripts" / "channel" / "restart-omni-mcp.sh"
    pid_file = runtime_dir / f"mcp-{port}.pid"
    log_file = runtime_dir / f"mcp-{port}.log"
    return subprocess.run(
        [
            "bash",
            str(script),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--pid-file",
            str(pid_file),
            "--log-file",
            str(log_file),
            "--health-timeout-secs",
            "10",
            "--stabilize-secs",
            str(stabilize_secs),
        ],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_restart_script_passes_with_stable_mock_server(tmp_path: Path) -> None:
    _write_mock_uv(tmp_path)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    port = _reserve_local_port()
    pid_file = runtime_dir / f"mcp-{port}.pid"
    listener_pid_file = Path(f"{pid_file}.listener")

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["PRJ_RUNTIME_DIR"] = str(runtime_dir)
    env["MOCK_MCP_MODE"] = "stable"

    try:
        result = _run_restart_script(port=port, runtime_dir=runtime_dir, env=env, stabilize_secs=1)
        assert result.returncode == 0, result.stdout + "\n" + result.stderr
        assert pid_file.exists()
        assert listener_pid_file.exists()

        assert _health_ok(port), "mock MCP should be healthy after restart"
    finally:
        _terminate_pid_from_file(listener_pid_file)
        _terminate_pid_from_file(pid_file)


def test_restart_script_fails_for_flaky_server_during_stabilization(tmp_path: Path) -> None:
    _write_mock_uv(tmp_path)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    port = _reserve_local_port()
    pid_file = runtime_dir / f"mcp-{port}.pid"
    listener_pid_file = Path(f"{pid_file}.listener")

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["PRJ_RUNTIME_DIR"] = str(runtime_dir)
    env["MOCK_MCP_MODE"] = "flaky"
    env["MOCK_MCP_FLAKY_EXIT_DELAY"] = "0.2"

    try:
        result = _run_restart_script(port=port, runtime_dir=runtime_dir, env=env, stabilize_secs=2)
        assert result.returncode != 0
        assert "stabilization window" in result.stderr
        assert not pid_file.exists()
        assert not listener_pid_file.exists()
    finally:
        _terminate_pid_from_file(listener_pid_file)
        _terminate_pid_from_file(pid_file)
