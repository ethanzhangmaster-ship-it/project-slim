"""P1.1 — AdjustRealitySource 测试。

覆盖：
1. SIM 回退：确定性样本，real_api_called 恒 False。
2. 生产模式 + 本地 mock Adjust API：真打 HTTP（urllib）并 real_api_called=True，
   collector 层 flag 透出；缺失 token 时返回 {}（domain 保持 None）。
3. E2E：AdjustRealitySource 进 GrowthRealityHub → 公司快照含真实 revenue，
   hub.last_real_api_called == True。

注意：mock server 仅替换 kpi_client.REPORT_BASE 指向 127.0.0.1，
仍真实跑 urllib 传输层（非 monkeypatch 返回值），所以能验证"真实调用发生过"。
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Iterator

import pytest

from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.collector import RealityCollector
from src.growth_reality.production_sources.adjust_source import AdjustRealitySource


# --------------------------------------------------------------------------- #
# 本地 mock Adjust Report Service
# --------------------------------------------------------------------------- #
CSV_BODY = (
    "date,app_token,daus\n"
    "2026-07-28,abc,1000\n"
    "2026-07-29,abc,1200\n"
)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = CSV_BODY.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 静默
        pass


class _MockAdjust:
    def __init__(self) -> None:
        self._server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "int":
        self._thread.start()
        return self.port

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def mock_adjust(monkeypatch) -> Iterator[None]:
    import operation.providers.live.adjust.kpi_client as kc
    with _MockAdjust() as port:
        monkeypatch.setattr(kc, "REPORT_BASE", f"http://127.0.0.1:{port}")
        yield


# --------------------------------------------------------------------------- #
# 1. SIM 回退
# --------------------------------------------------------------------------- #
def test_sim_returns_bundle_and_never_calls_real_api():
    src = AdjustRealitySource(mode="sim")
    out = src.collect("merge_witch", "2026-07-29")
    assert set(out.keys()) == {"revenue", "product"}
    assert out["revenue"]["daily_revenue"] > 0
    assert out["product"]["dau"] > 0
    assert src.real_api_called is False

    # 确定性：两次相同
    again = AdjustRealitySource(mode="sim").collect("merge_witch", "2026-07-29")
    assert again == out


# --------------------------------------------------------------------------- #
# 2. 生产模式 + 真实 HTTP 调用
# --------------------------------------------------------------------------- #
def test_production_calls_real_api_and_flags(mock_adjust):
    src = AdjustRealitySource(
        app_tokens={"merge_witch": "abc"},
        user_token="tok",
        mode="production",
        window_days=2,
    )
    out = src.collect("merge_witch", "2026-07-29")
    # 真打了 mock server（urllib）→ flag 必须 True
    assert src.real_api_called is True
    # dau 窗口均值 = (1000+1200)/2 = 1100
    assert out["product"]["dau"] == 1100
    # 日均收入 = (1000+1200)/2 = 1100（mock 同值）
    assert out["revenue"]["daily_revenue"] == 1100.0

    # collector 层汇聚 flag
    collector = RealityCollector(sources=[src])
    collector.collect_game("merge_witch", "2026-07-29")
    assert collector.real_api_called is True


def test_production_missing_token_returns_empty_and_no_flag():
    src = AdjustRealitySource(mode="production")  # 无 token
    assert src.collect("merge_witch", "2026-07-29") == {}
    assert src.real_api_called is False


# --------------------------------------------------------------------------- #
# 3. E2E：进 GrowthRealityHub
# --------------------------------------------------------------------------- #
def test_e2e_hub_consumes_real_adjust(mock_adjust):
    src = AdjustRealitySource(
        app_tokens={"merge_witch": "abc"},
        user_token="tok",
        mode="production",
        window_days=2,
    )
    hub = GrowthRealityHub(sources=[src])
    company = hub.refresh(["merge_witch"], "2026-07-29", persist=False)

    assert hub.last_real_api_called is True
    snap = company.per_game["merge_witch"]
    assert snap.revenue is not None
    assert snap.revenue.daily_revenue == 1100.0
    assert snap.product is not None
    assert snap.product.dau == 1100
    # confidence 因覆盖了 revenue+product 两域 = 2/5
    assert snap.confidence == pytest.approx(2 / 5, abs=1e-6)
