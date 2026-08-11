"""P1.5 — First Real Game CEO Run 测试。

验收：把真实源（MAX 报表 + Meta 买量 + Registry 产品元数据）接入 GrowthRealityHub，
跑首个真·CEO 经营闭环，生成 data/reality/<as_of>_snapshot.jsonl（每行一个真实快照）。

覆盖：
1. 快照 JSONL 生成：行数 == 游戏数；每行可反序列化为 GrowthRealitySnapshot。
2. 真实标记：MAX 真读报表 → hub.last_real_api_called == True。
3. 真实 ROAS：GameA 有真实收入(MAX)+真实花费(Meta mock) → roas>0、attribution.is_real。
4. 优雅降级：Adjust/Meta 缺凭证时返回 {}，不阻断整体运行（real_api_called 仍 True 因 MAX）。
5. CEO 问题可答：快照含 revenue/spend/roas，区分「产品增长 vs 买量砸出」。
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.models import GrowthRealitySnapshot
from src.growth_reality.production_sources.max_source import MaxRealitySource
from src.growth_reality.production_sources.meta_source import MetaRealitySource
from src.growth_reality.registry import GameRegistry, RegistryRealitySource

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REG_PATH = os.path.join(ROOT, "data", "game_registry.json")
OUT_DIR = os.path.join(ROOT, "data", "reality")

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

    def log_message(self, *args):
        pass


class _MockMeta:
    def __init__(self) -> None:
        self._server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> int:
        self._thread.start()
        return self.port

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def mock_meta(monkeypatch):
    import operation.providers.live.meta.meta_client as mc
    with _MockMeta() as port:
        monkeypatch.setattr(mc, "GRAPH_BASE", f"http://127.0.0.1:{port}")
        yield


def _run(as_of, out_dir):
    reg = GameRegistry(REG_PATH)
    sources = [
        MaxRealitySource(
            accounts=["ACCT_TEST"], mode="production", registry=reg, as_of=as_of,
            # 只读 fixture，避免 data/ 共享缓存被晨报测试重写
            data_dir=os.path.join(os.path.dirname(__file__), "fixtures"),
        ),
        RegistryRealitySource(registry=reg),
        MetaRealitySource(
            access_token="tok", ad_account_id="act_123",
            app_map={"camp_1": "GameA"}, mode="production", registry=reg, as_of=as_of,
        ),
    ]
    hub = GrowthRealityHub(sources=sources)
    company = hub.refresh(["GameA", "GameB"], as_of, persist=False)
    # 写快照 JSONL
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{as_of}_snapshot.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for gid, snap in company.per_game.items():
            f.write(json.dumps(snap.to_dict(), ensure_ascii=False) + "\n")
    return hub, company, path


def test_real_ceo_run_produces_snapshot_jsonl(mock_meta, tmp_path):
    out = str(tmp_path / "reality")
    hub, company, path = _run("2026-07-29", out)

    # 1) JSONL 生成：行数 == 游戏数
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    assert len(lines) == 2
    for ln in lines:
        d = json.loads(ln)
        GrowthRealitySnapshot.from_dict(d)  # 可反序列化

    # 2) 真实标记：MAX 真读报表
    assert hub.last_real_api_called is True

    # 3) 真实 ROAS：GameA 有收入(MAX)+花费(Meta)
    snap_a = company.per_game["GameA"]
    assert snap_a.revenue is not None and snap_a.revenue.daily_revenue == 10.0
    assert snap_a.acquisition is not None and snap_a.acquisition.spend == 500.0
    assert snap_a.acquisition.roas == 0.6
    assert snap_a.attribution is not None and snap_a.attribution.is_real is True

    # 4) GameB 无 Meta 花费 → roas=0（不臆造），但 MAX 收入仍在（ACCT_TEST GameB 日均 1.0）
    snap_b = company.per_game["GameB"]
    assert snap_b.revenue is not None and snap_b.revenue.daily_revenue == 1.0
    assert snap_b.acquisition is None or snap_b.acquisition.roas == 0.0

    # 5) CEO 问题可答：快照含 revenue/spend/roas 字段
    d = json.loads(lines[0])
    assert "revenue" in d and "acquisition" in d
