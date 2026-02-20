#!/usr/bin/env python3
"""
Minimal Telegram Bot API mock server for local/CI webhook black-box tests.

Supported endpoints:
  - GET  /health
  - POST /bot<TOKEN>/sendMessage
  - POST /bot<TOKEN>/sendChatAction
  - POST /bot<TOKEN>/sendPhoto
  - POST /bot<TOKEN>/sendDocument
  - POST /bot<TOKEN>/sendVideo
  - POST /bot<TOKEN>/sendAudio
  - POST /bot<TOKEN>/sendVoice
  - POST /bot<TOKEN>/sendMediaGroup
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import count
from typing import Any


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


MESSAGE_ID_COUNTER = count(1)
SUPPORTED_METHODS = {
    "sendMessage",
    "sendChatAction",
    "sendPhoto",
    "sendDocument",
    "sendVideo",
    "sendAudio",
    "sendVoice",
    "sendMediaGroup",
}


def parse_args() -> ServerConfig:
    parser = argparse.ArgumentParser(description="Run a minimal Telegram Bot API mock server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=18080, help="Bind port (default: 18080).")
    args = parser.parse_args()
    if args.port <= 0 or args.port > 65535:
        raise ValueError("--port must be in range 1..65535")
    return ServerConfig(host=args.host, port=args.port)


class TelegramMockHandler(BaseHTTPRequestHandler):
    server_version = "TelegramMock/0.1"

    def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        raw_len = self.headers.get("Content-Length", "0").strip() or "0"
        try:
            body_len = int(raw_len)
        except ValueError:
            body_len = 0
        if body_len <= 0:
            return {}
        body = self.rfile.read(body_len)
        try:
            parsed = json.loads(body.decode("utf-8"))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
        return {}

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write_json({"ok": True, "status": "healthy"})
            return
        self._write_json({"ok": False, "description": "not found"}, status=404)

    def do_POST(self) -> None:
        segments = [segment for segment in self.path.split("/") if segment]
        if len(segments) != 2 or not segments[0].startswith("bot"):
            self._write_json({"ok": False, "description": "invalid endpoint"}, status=404)
            return
        method = segments[1]
        if method not in SUPPORTED_METHODS:
            self._write_json(
                {"ok": False, "description": f"unsupported method: {method}"}, status=404
            )
            return

        body = self._read_json_body()
        if method == "sendChatAction":
            self._write_json({"ok": True, "result": True})
            return

        if method == "sendMediaGroup":
            result = [
                {"message_id": next(MESSAGE_ID_COUNTER), "chat": {"id": body.get("chat_id", 0)}}
            ]
            self._write_json({"ok": True, "result": result})
            return

        self._write_json(
            {
                "ok": True,
                "result": {
                    "message_id": next(MESSAGE_ID_COUNTER),
                    "chat": {"id": body.get("chat_id", 0)},
                    "text": body.get("text", ""),
                },
            }
        )

    def log_message(self, format: str, *args: object) -> None:
        # Keep CI logs concise and deterministic.
        return


def main() -> int:
    try:
        config = parse_args()
    except ValueError as error:
        print(f"Error: {error}")
        return 2

    server = ThreadingHTTPServer((config.host, config.port), TelegramMockHandler)
    print(f"Telegram mock API listening on http://{config.host}:{config.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
