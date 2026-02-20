"""Tests for gateway HTTP webhook (Phase 4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from omni.agent.gateway import create_webhook_app


@pytest.fixture
def mock_kernel():
    """Minimal kernel mock for webhook app."""
    return object()


def test_health_returns_ok(mock_kernel):
    """GET /health returns status ok."""
    app = create_webhook_app(kernel=mock_kernel, enable_cors=False)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert "omni-gateway-webhook" in data.get("service", "")


def test_message_empty_body_returns_400(mock_kernel):
    """POST /message with empty body returns 400."""
    app = create_webhook_app(kernel=mock_kernel, enable_cors=False)
    client = TestClient(app)
    resp = client.post("/message", content="")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_message_missing_message_returns_400(mock_kernel):
    """POST /message without message returns 400."""
    app = create_webhook_app(kernel=mock_kernel, enable_cors=False)
    client = TestClient(app)
    resp = client.post("/message", json={"session_id": "s1"})
    assert resp.status_code == 400


def test_message_success_returns_output(mock_kernel):
    """POST /message with valid body returns output from execute_task_with_session."""
    with patch(
        "omni.agent.gateway.webhook.execute_task_with_session", new_callable=AsyncMock
    ) as m_exec:
        m_exec.return_value = {"output": "Hello back", "session_id": "web:s1"}
        app = create_webhook_app(kernel=mock_kernel, enable_cors=False)
        client = TestClient(app)
        resp = client.post("/message", json={"message": "hello", "session_id": "web:s1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("output") == "Hello back"
    assert data.get("session_id") == "web:s1"
    m_exec.assert_called_once()
    call_kw = m_exec.call_args[1]
    assert call_kw.get("kernel") is mock_kernel
    assert m_exec.call_args[0][0] == "web:s1"
    assert m_exec.call_args[0][1] == "hello"
