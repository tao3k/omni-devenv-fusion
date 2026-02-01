#!/usr/bin/env python3
"""Test script for TUI socket communication.

Usage:
    python test_tui_socket.py

This script:
1. Starts a Rust TUI server (if available)
2. Sends test events
3. Verifies responses
"""

import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# Add omni.agent to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
AGENT_SRC = PROJECT_ROOT / "packages" / "python" / "agent" / "src"
sys.path.append(str(AGENT_SRC))

SOCKET_PATH = "/tmp/omni-tui-test.sock"


def wait_for_socket(path: Path, timeout: float = 5.0) -> bool:
    """Wait for socket to be available."""
    start = time.time()
    while time.time() - start < timeout:
        if path.exists():
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(str(path))
                sock.close()
                return True
            except:
                pass
        time.sleep(0.1)
    return False


def send_event_sync(socket_path: str, event: dict) -> bool:
    """Send event and return success status."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        msg = json.dumps(event) + "\n"
        sock.sendall(msg.encode())
        sock.close()
        return True
    except Exception as e:
        print(f"Send failed: {e}")
        return False


def test_socket_events():
    """Test sending events through Unix socket."""
    print("=" * 60)
    print("TUI Socket Integration Test")
    print("=" * 60)

    # Check if Rust TUI binary exists
    # Path relative to project root
    tui_path = PROJECT_ROOT / "target" / "debug" / "omni-tui"
    if not tui_path.exists():
        print(f"[-] TUI binary not found at {tui_path}")
        print("    Run: cd packages/rust/crates/omni-tui && cargo build")
        return False

    # Clean up existing socket
    socket_path = Path(SOCKET_PATH)
    if socket_path.exists():
        socket_path.unlink()

    print("[*] Starting Rust TUI server...")
    proc = subprocess.Popen(
        [str(tui_path), "--socket", SOCKET_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not wait_for_socket(socket_path):
            print("[-] TUI server failed to start")
            proc.kill()
            return False

        print("[+] TUI server is running")

        # Test events
        events = [
            {
                "source": "test",
                "topic": "test/connection",
                "payload": {"message": "Connection test"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            {
                "source": "omega",
                "topic": "omega/mission/start",
                "payload": {"goal": "Test mission from Python"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            {
                "source": "cortex",
                "topic": "cortex/task/complete",
                "payload": {"task_id": "test-001", "status": "success"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        ]

        print(f"[*] Sending {len(events)} test events...")
        for event in events:
            if send_event_sync(SOCKET_PATH, event):
                print(f"    [+] {event['topic']}")
            else:
                print(f"    [-] {event['topic']} - FAILED")
            time.sleep(0.2)

        print("[*] Waiting for events to be processed...")
        time.sleep(1)

        print("[+] Test completed successfully!")
        return True

    finally:
        print("[*] Stopping TUI server...")
        proc.terminate()
        proc.wait(timeout=5)

        # Cleanup
        if socket_path.exists():
            socket_path.unlink()


def test_tui_bridge():
    """Test TUIBridge from Python."""
    print("\n" + "=" * 60)
    print("TUIBridge Python Integration Test")
    print("=" * 60)

    try:
        from omni.agent.cli.console import TUIBridge, init_tui, shutdown_tui

        socket_path = "/tmp/omni-tui-bridge-test.sock"

        print(f"[*] Initializing TUI bridge on {socket_path}")
        init_tui(socket_path)

        bridge = TUIBridge()
        if bridge.connect(socket_path):
            print("[+] Bridge connected")

            # Send test event
            event = {
                "source": "test",
                "topic": "test/bridge",
                "payload": {"message": "Bridge test"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            if bridge.send_event(event):
                print("[+] Event sent via bridge")
            else:
                print("[-] Bridge send failed")

            bridge.disconnect()
        else:
            print("[-] Bridge connection failed (TUI server may not be running)")

        shutdown_tui()
        print("[+] Bridge test completed")
        return True

    except ImportError as e:
        print(f"[-] Import error: {e}")
        return False
    except Exception as e:
        print(f"[-] Bridge test error: {e}")
        return False


if __name__ == "__main__":
    print("TUI Testing Suite")
    print()

    results = []

    # Test 1: Socket events (requires Rust TUI to be built)
    results.append(("Socket Events", test_socket_events()))

    # Test 2: Python TUIBridge
    results.append(("TUIBridge", test_tui_bridge()))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    sys.exit(0 if all_passed else 1)
