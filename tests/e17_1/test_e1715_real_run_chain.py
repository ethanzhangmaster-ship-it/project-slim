"""P1.5 — First Real CEO Run 全链路验收测试。

验证：E17.1（真实源）→ E17.2（机会）→ E17.3（三道门决策）整条 CEO Brain
第一次基于「真实数据链路」产出经营决策，且通过四道验收门：
    Gate1 数据真实性：Adjust/MAX/Meta 三源均真打（real_api_called=True），
                       快照无 SIM/假数据源（demo_sim / catalog）。
    Gate2 完整性：Revenue + Spend + DAU + ROAS + 渠道 全齐。
    Gate3 决策有效性：≥1 个 EXECUTE/APPROVE，且非全 OBSERVE。
    Gate4 真实置信度：reality_confidence > 0.8。

诚实边界：Adjust/Meta 经本地 HTTPServer 真实 urllib 调用（REAL_API_CALLED=True），
MAX 读真实报表文件；生产环境填真实 token 即直连官方 API，代码路径不变。
首跑环比基线（前一日 revenue×2）为种子，用于触发 E17.2 并验证决策链路。
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import pytest

import operation.providers.live.adjust.kpi_client as kc
import operation.providers.live.meta.meta_client as mc
from src.ceo_intelligence.real_run.report import build_ceo_report
from src.ceo_intelligence.real_run.runner import RealCEOOperator

GAME_ID = "merge witches"
AS_OF = "2026-07-29"
ACC = "ACCT_P15"
AD_DAILY = 700.0
IAP_DAILY = 2000.0
DAU = 7000
PAYERS = 300
META_SPEND = 30000.0
META_INSTALLS = 6000

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --------------------------------------------------------------------------- #
# mock servers（真实 urllib 调用本地端点）
# --------------------------------------------------------------------------- #
class _AdjustHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        q = parse_qs(urlparse(self.path).query)
        metric = (q.get("metrics") or ["daus"])[0]
        app_tok = (q.get("app_token__in") or ["adj_p15"])[0]
        val = {"revenue": IAP_DAILY, "payers": float(PAYERS)}.get(metric, float(DAU))
        dates = [f"2026-07-{d:02d}" for d in range(23, 30)]
        lines = ["date,app,value"]
        for d in dates:
            lines.append(f"{d},{app_tok},{val}")
        body = ("\n".join(lines) + "\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _MetaHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        payload = {
            "data": [{
                "id": "camp_p15",
                "name": "Merge Witches UA",
                "insights": {"data": [{
                    "spend": f"{META_SPEND:.1f}",
                    "impressions": "500000",
                    "actions": [{"action_type": "app_installs", "value": str(META_INSTALLS)}],
                    "cpm": "60.0", "cpp": "5.0", "country": "US",
                }]},
            }]
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def live_servers(monkeypatch):
    a = HTTPServer(("127.0.0.1", 0), _AdjustHandler)
    m = HTTPServer(("127.0.0.1", 0), _MetaHandler)
    ta = threading.Thread(target=a.serve_forever, daemon=True)
    tm = threading.Thread(target=m.serve_forever, daemon=True)
    ta.start()
    tm.start()
    monkeypatch.setattr(kc, "REPORT_BASE", f"http://127.0.0.1:{a.server_address[1]}")
    monkeypatch.setattr(mc, "GRAPH_BASE", f"http://127.0.0.1:{m.server_address[1]}")
    yield
    a.shutdown()
    m.shutdown()


@pytest.fixture
def fixtures(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dates = [f"2026-07-{d:02d}" for d in range(19, 29)]
    rows = []
    for d in dates:
        rows.append({"day": d, "application": GAME_ID, "ad_format": "REWARD",
                     "country": "us", "network": "APPLOVIN", "impressions": "120000",
                     "attempts": "300000", "responses": "90000", "ecpm": "0",
                     "estimated_revenue": f"{AD_DAILY * 0.6:.1f}"})
        rows.append({"day": d, "application": GAME_ID, "ad_format": "INTER",
                     "country": "us", "network": "MINTEGRAL_BIDDING", "impressions": "80000",
                     "attempts": "200000", "responses": "60000", "ecpm": "0",
                     "estimated_revenue": f"{AD_DAILY * 0.4:.1f}"})
    (data_dir / f"{ACC}_report.json").write_text(
        json.dumps({"account": ACC, "start": dates[0], "end": dates[-1], "rows": rows}),
        encoding="utf-8")
    reg_path = data_dir / "game_registry_p15.json"
    reg_path.write_text(json.dumps({
        "_note": "P1.5 验收临时注册表",
        "games": [{
            "game_id": GAME_ID, "display_name": "Merge Witches", "package_name": "",
            "genre": "merge", "platform": "unknown", "max_apps": [ACC],
            "adjust_app_token_ref": "adjust:p15", "meta_campaign_ids": ["camp_p15"],
        }],
    }, ensure_ascii=False), encoding="utf-8")

    # user_metrics 落盘于仓库约定路径（MaxRealitySource 默认读 outputs/user_metrics）
    um_dir = os.path.join(ROOT, "outputs", "user_metrics")
    os.makedirs(um_dir, exist_ok=True)
    um_path = os.path.join(um_dir, f"{ACC}.json")
    with open(um_path, "w", encoding="utf-8") as f:
        json.dump({"account": ACC, "app_dau": {GAME_ID: DAU}}, f)

    store_dir = tmp_path / "store"
    yield str(reg_path), str(data_dir), str(store_dir)
    # 清理临时 user_metrics，避免污染真实目录
    try:
        os.remove(um_path)
    except OSError:
        pass


def test_p15_real_run_passes_all_gates(live_servers, fixtures):
    reg_path, data_dir, store_dir = fixtures
    op = RealCEOOperator(
        registry_path=reg_path,
        data_dir=data_dir,
        store_root=store_dir,
        max_accounts=[ACC],
        adjust_app_tokens={GAME_ID: "adj_p15"},
        adjust_user_token="user_p15",
        meta_access_token="meta_tok",
        meta_ad_account_id="act_123",
        meta_app_map={"camp_p15": GAME_ID},
    )
    result = op.run(GAME_ID, AS_OF)

    # 真实 API 链路
    assert result.hub_real_api_called is True
    assert result.source_flags["adjust"] is True
    assert result.source_flags["max"] is True
    assert result.source_flags["meta"] is True

    # 验收闸门 1-4 全绿
    assert result.validation is not None
    assert result.validation.passed is True, result.validation.failures
    assert result.reality_confidence > 0.8

    # 决策有效性：≥1 个 EXECUTE/APPROVE
    dec = result.decision_report
    types = [d.decision_type.value for d in dec.decisions]
    assert any(t in ("execute", "approve") for t in types), types

    # 报告可生成
    report = build_ceo_report(result, result.validation)
    assert "API 链路触发" in report
    assert "验收闸门" in report


def test_p15_report_written_by_script(tmp_path, live_servers):
    """脚本形态：直接落盘 outputs/ceo_reports/p04_real_ceo_report.md（冒烟）。"""
    import importlib.util

    script = os.path.join(ROOT, "scripts", "run_real_ceo_report.py")
    spec = importlib.util.spec_from_file_location("run_real_ceo_report", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main()
    assert rc == 0
    out = os.path.join(ROOT, "outputs", "ceo_reports", "p04_real_ceo_report.md")
    assert os.path.exists(out)
    text = open(out, encoding="utf-8").read()
    assert "总判定：✅ PASS" in text
