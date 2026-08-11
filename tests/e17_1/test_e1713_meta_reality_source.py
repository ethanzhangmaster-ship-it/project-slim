"""P1.3 — MetaRealitySource 测试。

覆盖：
1. SIM 回退：确定性样本，real_api_called 恒 False。
2. 生产模式 + 本地 mock Meta Graph API：真打 HTTP（urllib）并 real_api_called=True，
   collector 层 flag 透出；缺失凭证时返回 {}（flag False）。
3. E2E：MetaRealitySource 进 GrowthRealityHub → 公司快照含真实 acquisition，
   hub.last_real_api_called == True。

注意：mock server 仅替换 meta_client.GRAPH_BASE 指向 127.0.0.1，
仍真实跑 urllib 传输层（非 monkeypatch 返回值），所以能验证"真实调用发生过"。
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.collector import RealityCollector
from src.growth_reality.production_sources.meta_source import MetaRealitySource

MOCK_BODY = {
    "data": [
        {
            "id": "camp_1",
            "name": "GameA",
            "insights": {
                "data": [
                    {
                        "spend": "500.0",
                        "impressions": "100000",
                        "actions": [{"action_type": "app_installs", "value": "1000"}],
                        "cpm": "5.0",
                        "cpp": "0.5",
                        "country": "US",
                    }
                ]
            },
        }
    ]
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps(MOCK_BODY).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # 静默
        pass


class _MockMeta:
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
def mock_meta(monkeypatch) -> None:
    import operation.providers.live.meta.meta_client as mc
    with _MockMeta() as port:
        monkeypatch.setattr(mc, "GRAPH_BASE", f"http://127.0.0.1:{port}")
        yield


# --------------------------------------------------------------------------- #
# 1. SIM 回退
# --------------------------------------------------------------------------- #
def test_sim_returns_bundle_and_never_calls_real_api():
    src = MetaRealitySource(mode="sim")
    out = src.collect("merge_monster", "2026-07-29")
    assert set(out.keys()) == {"acquisition"}
    assert out["acquisition"]["spend"] > 0
    assert out["acquisition"]["installs"] > 0
    assert src.real_api_called is False

    again = MetaRealitySource(mode="sim").collect("merge_monster", "2026-07-29")
    assert again == out


# --------------------------------------------------------------------------- #
# 2. 生产模式 + 真实 HTTP 调用
# --------------------------------------------------------------------------- #
def test_production_calls_real_api_and_flags(mock_meta):
    src = MetaRealitySource(
        access_token="tok", ad_account_id="act_123",
        app_map={"camp_1": "GameA"}, mode="production", window_days=7,
    )
    out = src.collect("GameA", "2026-07-29")
    assert src.real_api_called is True
    acq = out["acquisition"]
    # spend=500, installs=1000 → cpi = 0.5
    assert acq["spend"] == 500.0
    assert acq["installs"] == 1000
    assert acq["cpi"] == 0.5

    collector = RealityCollector(sources=[src])
    collector.collect_game("GameA", "2026-07-29")
    assert collector.real_api_called is True


def test_production_missing_credentials_returns_empty_and_no_flag():
    src = MetaRealitySource(mode="production")  # 无 token / ad_account
    assert src.collect("GameA", "2026-07-29") == {}
    assert src.real_api_called is False


# --------------------------------------------------------------------------- #
# 3. E2E：进 GrowthRealityHub
# --------------------------------------------------------------------------- #
def test_e2e_hub_consumes_real_meta(mock_meta):
    src = MetaRealitySource(
        access_token="tok", ad_account_id="act_123",
        app_map={"camp_1": "GameA"}, mode="production", window_days=7,
    )
    hub = GrowthRealityHub(sources=[src])
    company = hub.refresh(["GameA"], "2026-07-29", persist=False)

    assert hub.last_real_api_called is True
    snap = company.per_game["GameA"]
    assert snap.acquisition is not None
    assert snap.acquisition.spend == 500.0
    assert snap.acquisition.installs == 1000
    assert snap.acquisition.cpi == 0.5
    # 仅覆盖 acquisition 单域 → confidence = 1/5
    assert snap.confidence == 1 / 5
