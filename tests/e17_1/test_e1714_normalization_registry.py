"""P1.4 — Reality Normalization Layer + Game Registry 测试。

覆盖：
1. GameRegistry 加载 data/game_registry.json（真实映射，零内联密钥）。
2. RealityNormalizer 真实覆盖感知：SIM 演示 → real_confidence=0，confidence 不受虚高影响。
3. 真实 ROAS 归因：收入与花费均真实 → ROAS 计算 + 有机/付费分解。
4. ROAS 门控：收入真实但花费非真实（SIM）→ roas=0，attribution=None（不臆造）。
5. E2E 真实闭环：MAX(revenue,真实) + Meta(acquisition,真实) + Registry(product,真实)
   → 进 GrowthRealityHub → real_confidence=3/5，last_real_api_called=True，ROAS 真算。
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.growth_reality.agent import GrowthRealityHub
from src.growth_reality.collector import RealityCollector
from src.growth_reality.normalizer import RealityNormalizer
from src.growth_reality.production_sources.max_source import MaxRealitySource
from src.growth_reality.production_sources.meta_source import MetaRealitySource
from src.growth_reality.registry import GameRegistry, RegistryRealitySource

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REG_PATH = os.path.join(ROOT, "data", "game_registry.json")


# --------------------------------------------------------------------------- #
# 1. GameRegistry
# --------------------------------------------------------------------------- #
def test_registry_loads_real_mapping_without_inline_secrets():
    reg = GameRegistry(REG_PATH)
    gids = reg.all_game_ids()
    assert len(gids) >= 50  # 从真实 MAX 报表生成

    # ACCT_TEST 的 GameA / GameB 必在
    assert reg.lookup("GameA") is not None
    assert reg.lookup("GameB") is not None

    # 反向映射：MAX application 名 → canonical game_id
    assert reg.max_app_to_game_id("GameA") == "GameA"

    # 零内联密钥：所有 adjust_app_token_ref 均为 secret_ref 字符串，非长 token
    raw = json.dumps(json.load(open(REG_PATH, encoding="utf-8")))
    assert "Bearer" not in raw
    assert "report_key" not in raw  # 密钥不进注册表
    for g in reg.all_game_ids():
        ref = reg.game_id_to_adjust_ref(g)
        assert ref == "" or (":" in ref and "live_accounts" in ref)


# --------------------------------------------------------------------------- #
# 2. Normalizer 真实覆盖感知（SIM 演示不虚高 real_confidence）
# --------------------------------------------------------------------------- #
def _demo_raw():
    return {
        "game_id": "g0",
        "as_of": "2026-07-29",
        "domains": {
            "revenue": {"daily_revenue": 100.0, "payer_count": 5, "arpdau": 1.0, "ltv": 2.0},
            "acquisition": {"spend": 1000.0, "installs": 100, "cpi": 10.0, "roas": 0.0},
            "aso": {"ranking": 10, "store_cvr": 0.02, "rating": 4.0, "review_velocity": 5.0},
            "creative": {"ctr": 0.01, "fatigue_score": 0.2, "creative_score": 80.0},
            "product": {"dau": 5000, "retention": 0.3, "conversion": 0.02},
        },
        "sources": ["demo_sim"],
        "real_domains": [],  # 纯 SIM → 无真实域
    }


def test_normalizer_sim_demo_has_zero_real_confidence():
    snap = RealityNormalizer().normalize_game("g0", "2026-07-29", _demo_raw())
    assert snap.confidence == 1.0          # 全量覆盖（SIM 演示仍为全量，向后兼容）
    assert snap.real_confidence == 0.0     # 真实覆盖为 0
    assert snap.real_domains == []
    assert snap.attribution is None         # SIM 无归因


# --------------------------------------------------------------------------- #
# 3. 真实 ROAS 归因（收入 + 花费均真实）
# --------------------------------------------------------------------------- #
def _real_pair_raw():
    return {
        "game_id": "g1",
        "as_of": "2026-07-29",
        "domains": {
            "revenue": {"daily_revenue": 100.0, "payer_count": 5, "arpdau": 1.0, "ltv": 2.0},
            "acquisition": {"spend": 1000.0, "installs": 100, "cpi": 10.0, "roas": 0.0},
        },
        "sources": ["max_live", "meta_live"],
        "real_domains": ["revenue", "acquisition"],
    }


def test_normalizer_real_pair_computes_roas_and_attribution():
    snap = RealityNormalizer().normalize_game("g1", "2026-07-29", _real_pair_raw())
    assert snap.real_confidence == 2 / 5
    # ROAS = 月化日收入 / 月花费 = 100*30 / 1000 = 3.0
    assert snap.acquisition is not None
    assert round(snap.acquisition.roas, 4) == 3.0
    # 有机/付费分解：paid = 1000/3000 = 0.333；organic = 0.667
    assert snap.attribution is not None
    assert snap.attribution.is_real is True
    assert round(snap.attribution.paid_share_est, 3) == 0.333
    assert round(snap.attribution.organic_share_est, 3) == 0.667


# --------------------------------------------------------------------------- #
# 4. ROAS 门控（收入真实、花费非真实 → 不臆造）
# --------------------------------------------------------------------------- #
def test_normalizer_roas_gated_when_spend_not_real():
    raw = _real_pair_raw()
    raw["real_domains"] = ["revenue"]  # 仅收入真实；花费来自 SIM
    raw["sources"] = ["max_live", "demo_sim"]
    snap = RealityNormalizer().normalize_game("g1", "2026-07-29", raw)
    assert snap.real_confidence == 1 / 5          # 仅收入真实
    assert snap.acquisition.roas == 0.0           # 花费非真实 → 不计算
    assert snap.attribution is None                # 无归因


# --------------------------------------------------------------------------- #
# 5. E2E 真实闭环：MAX + Meta + Registry
# --------------------------------------------------------------------------- #
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


def test_e2e_real_ceo_run_max_meta_registry(mock_meta):
    reg = GameRegistry(REG_PATH)
    fixtures = os.path.join(os.path.dirname(__file__), "fixtures")
    max_src = MaxRealitySource(
        accounts=["ACCT_TEST"], mode="production", registry=reg,
        data_dir=fixtures,  # 只读 fixture，避免 data/ 共享缓存被晨报测试重写
    )
    meta_src = MetaRealitySource(
        access_token="tok", ad_account_id="act_123",
        app_map={"camp_1": "GameA"}, mode="production", registry=reg,
    )
    reg_src = RegistryRealitySource(registry=reg)

    hub = GrowthRealityHub(sources=[max_src, meta_src, reg_src])
    company = hub.refresh(["GameA"], "2026-07-29", persist=False)

    assert hub.last_real_api_called is True
    snap = company.per_game["GameA"]
    # 三真实源覆盖 revenue + acquisition + product → real_confidence=3/5
    assert snap.real_confidence == 3 / 5
    assert snap.revenue is not None and snap.revenue.daily_revenue == 10.0  # MAX 真实
    assert snap.acquisition is not None and snap.acquisition.spend == 500.0  # Meta 真实
    assert snap.product is not None
    # ROAS = 10*30 / 500 = 0.6 → 真实归因
    assert round(snap.acquisition.roas, 4) == 0.6
    assert snap.attribution is not None and snap.attribution.is_real is True
