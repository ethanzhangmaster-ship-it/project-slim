"""P1.6 — 真实数据覆盖日报一键生成。

两种运行模式：
1. 生产模式（默认，无需 token）：
   用真实 GameRegistry + 本地 MAX 报表缓存 + （可选）Adjust/Meta token，
   跑 E17.1 GrowthRealityHub 全量 58 游戏 → RealityHealthMonitor →
   DailyRealityStore 落盘 → 输出 outputs/reality_coverage_report.md。
   诚实声明当前真实覆盖缺口（防 CEO 被骗）。

2. 验收模式（--demo）：
   复用 P1.5 已验证的 mock-server 链路，对 `merge witches` 注入 Adjust+Meta+MAX
   真实 urllib 调用（real_api_called=True），证明覆盖层在真实数据到位时变绿
   （fully_covered=True、0 DATA_GAP）。生产环境填入真实 token 即直连官方 API，
   代码路径不变。

运行：
    python scripts/run_reality_coverage.py            # 生产模式
    python scripts/run_reality_coverage.py --demo      # 验收绿路
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import operation.providers.live.adjust.kpi_client as kc  # noqa: E402
import operation.providers.live.meta.meta_client as mc  # noqa: E402
from src.growth_reality.agent import GrowthRealityHub  # noqa: E402
from src.growth_reality.coverage import (  # noqa: E402
    DailyRealityStore,
    RealityHealthMonitor,
)
from src.growth_reality.production_sources.adjust_source import AdjustRealitySource  # noqa: E402
from src.growth_reality.production_sources.max_source import MaxRealitySource  # noqa: E402
from src.growth_reality.production_sources.meta_source import MetaRealitySource  # noqa: E402
from src.growth_reality.registry import DEFAULT_PATH, GameRegistry, RegistryRealitySource  # noqa: E402

AS_OF = "2026-07-29"
STORE_ROOT = os.path.join(ROOT, "data", "reality")
OUT_PATH = os.path.join(ROOT, "outputs", "reality_coverage_report.md")

# -- demo 验收常量（merge witches / P04 量级，仅用于链路验收，非生产真实值）--
AD_DAILY = 700.0
IAP_DAILY = 2000.0
DAU = 7000
PAYERS = 300
META_SPEND = 30000.0
META_INSTALLS = 6000
ACC_P15 = "ACCT_P15"
GAME_ID = "merge witches"


# --------------------------------------------------------------------------- #
# demo mock-server（与 P1.5 一致：真实 urllib 调用本地端点）
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
                "id": "camp_p15", "name": "Merge Witches UA",
                "insights": {"data": [{
                    "spend": f"{META_SPEND:.1f}", "impressions": "500000",
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


def _serve(handler_cls):
    srv = HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# --------------------------------------------------------------------------- #
# 生产模式
# --------------------------------------------------------------------------- #
def run_production(as_of: str) -> int:
    reg = GameRegistry(DEFAULT_PATH)
    sources = [
        RegistryRealitySource(reg),
        MaxRealitySource(mode="production", registry=reg),
        AdjustRealitySource(mode="production", registry=reg),
        MetaRealitySource(mode="production", registry=reg),
    ]
    hub = GrowthRealityHub(sources)
    game_ids = reg.all_game_ids()
    company = hub.refresh(game_ids, as_of, persist=False)

    monitor = RealityHealthMonitor(reg)
    report = monitor.check(company)

    store = DailyRealityStore(STORE_ROOT)
    store.save_company(company, as_of)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    print(f"[P1.6] 生产模式：{len(game_ids)} 游戏 | "
          f"覆盖 {report.covered_games} | 缺口游戏 {report.games_with_gaps} | "
          f"DATA_GAP {len(report.gaps)}")
    print(f"[P1.6] 报告：{OUT_PATH}")
    print(f"[P1.6] 经营库：{STORE_ROOT}（按游戏/日期落盘）")
    return 0


# --------------------------------------------------------------------------- #
# demo 验收模式（证明真实数据到位时覆盖层变绿）
# --------------------------------------------------------------------------- #
def run_demo(as_of: str) -> int:
    out_dir = os.path.join(ROOT, "outputs", "_p16_demo")
    tmp_data = os.path.join(out_dir, "data")
    tmp_store = os.path.join(out_dir, "store")
    shutil.rmtree(tmp_store, ignore_errors=True)
    os.makedirs(tmp_data, exist_ok=True)

    # 临时 MAX 报表（application == game_id，可被 app_map 直接命中）
    dates = [f"2026-07-{d:02d}" for d in range(19, 29)]
    rows = []
    for d in dates:
        rows.append({"day": d, "application": GAME_ID, "ad_format": "REWARD",
                     "country": "us", "network": "APPLOVIN",
                     "impressions": "120000", "attempts": "300000", "responses": "90000",
                     "ecpm": "0", "estimated_revenue": f"{AD_DAILY * 0.6:.1f}"})
        rows.append({"day": d, "application": GAME_ID, "ad_format": "INTER",
                     "country": "us", "network": "MINTEGRAL_BIDDING",
                     "impressions": "80000", "attempts": "200000", "responses": "60000",
                     "ecpm": "0", "estimated_revenue": f"{AD_DAILY * 0.4:.1f}"})
    with open(os.path.join(tmp_data, f"{ACC_P15}_report.json"), "w", encoding="utf-8") as f:
        json.dump({"account": ACC_P15, "start": dates[0], "end": dates[-1], "rows": rows}, f)

    # 临时注册表：merge witches 完全绑定（含真实源标识）
    reg_doc = {"_note": "P1.6 demo 临时注册表", "games": [{
        "game_id": GAME_ID, "display_name": "Merge Witches",
        "package_name": "com.born2play.mergewitches", "genre": "merge",
        "platform": "android", "max_apps": [ACC_P15],
        "adjust_app_token": "live_accounts:apps:merge_witches:token",
        "meta_app_id": "meta_app_mergewitches", "max_account": ACC_P15,
        "country": "US", "meta_campaign_ids": ["camp_p15"],
    }]}
    reg_path = os.path.join(tmp_data, "game_registry_demo.json")
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(reg_doc, f, ensure_ascii=False)

    adjust_srv = _serve(_AdjustHandler)
    meta_srv = _serve(_MetaHandler)
    orig_adj, orig_meta = kc.REPORT_BASE, mc.GRAPH_BASE
    kc.REPORT_BASE = f"http://127.0.0.1:{adjust_srv.server_address[1]}"
    mc.GRAPH_BASE = f"http://127.0.0.1:{meta_srv.server_address[1]}"

    try:
        reg = GameRegistry(reg_path)
        sources = [
            RegistryRealitySource(reg),
            MaxRealitySource(mode="production", data_dir=tmp_data,
                             accounts=[ACC_P15], registry=reg),
            AdjustRealitySource(mode="production",
                                app_tokens={GAME_ID: "adj_p15"}, user_token="user_p15",
                                registry=reg),
            MetaRealitySource(mode="production", access_token="meta_tok",
                              ad_account_id="act_123",
                              app_map={"camp_p15": GAME_ID}, registry=reg),
        ]
        hub = GrowthRealityHub(sources)
        company = hub.refresh([GAME_ID], as_of, persist=False)
        assert hub.last_real_api_called, "demo 应触发真实 API"
        monitor = RealityHealthMonitor(reg)
        report = monitor.check(company)
        assert report.covered_games == 1, f"demo 应完全覆盖，实际 {report.covered_games}"
        assert report.gaps == [], f"demo 不应有 DATA_GAP，实际 {report.gaps}"

        store = DailyRealityStore(tmp_store)
        store.save_company(company, as_of)

        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            f.write("# P1.6 验收模式（demo）\n\n> 真实数据到位时覆盖层变绿。\n\n"
                    + report.to_markdown())

        print(f"[P1.6 demo] hub_real_api_called={hub.last_real_api_called} "
              f"| fully_covered={report.covered_games}/1 | DATA_GAP={len(report.gaps)}")
        print(f"[P1.6 demo] 经营库示例：{store.dates(GAME_ID)}")
        return 0
    finally:
        kc.REPORT_BASE, mc.GRAPH_BASE = orig_adj, orig_meta
        adjust_srv.shutdown()
        meta_srv.shutdown()


def main() -> int:
    ap = argparse.ArgumentParser(description="P1.6 Reality Coverage Report")
    ap.add_argument("--demo", action="store_true", help="验收模式：证明真实数据到位时覆盖层变绿")
    ap.add_argument("--as-of", default=AS_OF)
    args = ap.parse_args()
    if args.demo:
        return run_demo(args.as_of)
    return run_production(args.as_of)


if __name__ == "__main__":
    raise SystemExit(main())
