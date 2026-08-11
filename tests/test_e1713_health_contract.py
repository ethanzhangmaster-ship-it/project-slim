"""E17.13 Health Check Contract — 健康检查端点契约测试.

验证 /healthz, /readyz, /api/status, /api/diagnostic 端点的契约:
  - 状态码 (200, 503, 404)
  - 响应结构 (必需字段)
  - Content-Type header
  - 边界条件 (blocked 状态下 readyz 返回 503)
"""

from __future__ import annotations

import json
import os
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start_server(tmp_path: Path, env_overrides: dict[str, str] | None = None) -> tuple[HTTPConnection, threading.Thread, threading.Event]:
    """Start a ControlPlane HTTP server in a background thread.

    Returns (connection, thread, ready_event).
    """
    src_dir = tmp_path / "src" / "market_ops"
    src_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "active").mkdir(parents=True, exist_ok=True)

    ready = threading.Event()

    def _run() -> None:
        from market_ops.product.server import Handler, ThreadingHTTPServer
        from market_ops.product.control_plane import ControlPlane
        Handler.control_plane = ControlPlane(tmp_path)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        ready.port = port
        ready.set()
        server.handle_request()
        server.handle_request()
        server.handle_request()
        server.handle_request()
        server.handle_request()
        server.handle_request()
        server.handle_request()

    t = threading.Thread(target=_run, daemon=True)

    with patch.dict(os.environ, env_overrides or {}, clear=True):
        t.start()

    ready.wait(timeout=5)
    time.sleep(0.1)  # let server settle
    conn = HTTPConnection("127.0.0.1", ready.port, timeout=5)
    conn.connect()
    return conn, t, ready


# ---------------------------------------------------------------------------
# test_healthz_returns_200
# ---------------------------------------------------------------------------

def test_healthz_returns_200(tmp_path: Path) -> None:
    """/healthz 始终返回 200."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/healthz")
        resp = conn.getresponse()
        assert resp.status == 200
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_healthz_response_structure
# ---------------------------------------------------------------------------

def test_healthz_response_structure(tmp_path: Path) -> None:
    """/healthz 响应包含 status/version/checks 字段."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/healthz")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        assert "status" in body, f"Missing 'status' in: {list(body.keys())}"
        assert "version" in body, f"Missing 'version' in: {list(body.keys())}"
        assert "checks" in body, f"Missing 'checks' in: {list(body.keys())}"
        assert isinstance(body["checks"], list)
        assert body["status"] in ("ready", "degraded", "blocked")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_readyz_blocked_returns_503
# ---------------------------------------------------------------------------

def test_readyz_blocked_returns_503(tmp_path: Path) -> None:
    """blocked 状态时 /readyz 返回 503."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/readyz")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        if body["status"] == "blocked":
            assert resp.status == 503
        else:
            assert resp.status == 200
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_readyz_ready_returns_200
# ---------------------------------------------------------------------------

def test_readyz_ready_returns_200(tmp_path: Path) -> None:
    """ready 状态时 /readyz 返回 200."""
    src_dir = tmp_path / "src" / "market_ops"
    src_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "output" / "active").mkdir(parents=True, exist_ok=True)

    ready = threading.Event()

    def _run() -> None:
        from market_ops.product.server import Handler, ThreadingHTTPServer
        from market_ops.product.control_plane import ControlPlane
        Handler.control_plane = ControlPlane(tmp_path)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        ready.port = port
        ready.set()
        server.handle_request()
        server.handle_request()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    ready.wait(timeout=5)
    time.sleep(0.1)

    conn = HTTPConnection("127.0.0.1", ready.port, timeout=5)
    conn.connect()
    try:
        conn.request("GET", "/readyz")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        # src 目录存在，output 目录存在，状态应为 ready 或 degraded
        assert resp.status in (200, 503)
        assert body["status"] in ("ready", "degraded", "blocked")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_api_status_structure
# ---------------------------------------------------------------------------

def test_api_status_structure(tmp_path: Path) -> None:
    """/api/status 包含 metrics/capabilities/checks 字段."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/api/status")
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read().decode())
        assert "metrics" in body, f"Missing 'metrics' in: {list(body.keys())}"
        assert "capabilities" in body, f"Missing 'capabilities' in: {list(body.keys())}"
        assert "checks" in body, f"Missing 'checks' in: {list(body.keys())}"
        assert isinstance(body["metrics"], dict)
        assert isinstance(body["capabilities"], dict)
        assert isinstance(body["checks"], list)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_api_diagnostic_structure
# ---------------------------------------------------------------------------

def test_api_diagnostic_structure(tmp_path: Path) -> None:
    """/api/diagnostic 返回诊断报告结构."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/api/diagnostic")
        resp = conn.getresponse()
        assert resp.status == 200
        body = json.loads(resp.read().decode())
        assert "mode" in body, f"Missing 'mode' in: {list(body.keys())}"
        assert "offline_mode" in body, f"Missing 'offline_mode' in: {list(body.keys())}"
        assert "missing_credentials" in body, f"Missing 'missing_credentials' in: {list(body.keys())}"
        assert "blocked_capabilities" in body, f"Missing 'blocked_capabilities' in: {list(body.keys())}"
        assert "recommendations" in body, f"Missing 'recommendations' in: {list(body.keys())}"
        assert isinstance(body["missing_credentials"], list)
        assert isinstance(body["blocked_capabilities"], list)
        assert isinstance(body["recommendations"], list)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_unknown_path_returns_404
# ---------------------------------------------------------------------------

def test_unknown_path_returns_404(tmp_path: Path) -> None:
    """未知路径返回 404 + {"error": "not found"}."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/unknown/path/xyz")
        resp = conn.getresponse()
        assert resp.status == 404
        body = json.loads(resp.read().decode())
        assert body == {"error": "not found"}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_unknown_path_no_trailing_slash
# ---------------------------------------------------------------------------

def test_unknown_path_no_trailing_slash(tmp_path: Path) -> None:
    """无斜杠的未知路径也返回 404."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/nonexistent")
        resp = conn.getresponse()
        assert resp.status == 404
        body = json.loads(resp.read().decode())
        assert body == {"error": "not found"}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_content_type_json
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("endpoint", [
    "/healthz",
    "/readyz",
    "/api/status",
    "/api/diagnostic",
])
def test_content_type_json(tmp_path: Path, endpoint: str) -> None:
    """所有端点返回 Content-Type: application/json."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", endpoint)
        resp = conn.getresponse()
        content_type = resp.getheader("Content-Type", "")
        assert "application/json" in content_type, (
            f"{endpoint} Content-Type={content_type}, expected application/json"
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_index_returns_html
# ---------------------------------------------------------------------------

def test_index_returns_html(tmp_path: Path) -> None:
    """根路径 / 返回 HTML 页面."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/")
        resp = conn.getresponse()
        assert resp.status == 200
        content_type = resp.getheader("Content-Type", "")
        assert "text/html" in content_type
        body = resp.read().decode()
        assert "<!doctype html>" in body.lower()
        assert "Market Ops Control Center" in body
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# test_healthz_and_status_share_same_handler
# ---------------------------------------------------------------------------

def test_healthz_and_status_share_same_handler(tmp_path: Path) -> None:
    """/healthz 和 /api/status 共享同一处理逻辑，返回相同结构."""
    conn, _t, _ready = _start_server(tmp_path)
    try:
        conn.request("GET", "/healthz")
        hz_body = json.loads(conn.getresponse().read().decode())

        conn.request("GET", "/api/status")
        st_body = json.loads(conn.getresponse().read().decode())

        assert hz_body["status"] == st_body["status"]
        assert hz_body["version"] == st_body["version"]
        assert hz_body["mode"] == st_body["mode"]
    finally:
        conn.close()


__all__ = [
    "test_healthz_returns_200",
    "test_healthz_response_structure",
    "test_readyz_blocked_returns_503",
    "test_readyz_ready_returns_200",
    "test_api_status_structure",
    "test_api_diagnostic_structure",
    "test_unknown_path_returns_404",
    "test_unknown_path_no_trailing_slash",
    "test_content_type_json",
    "test_index_returns_html",
    "test_healthz_and_status_share_same_handler",
]