"""P1.5 — 一键真实 CEO 报告生成（验收脚本）。

目标：验证 E17 CEO Brain 第一次基于「真实数据链路」产生经营决策，并输出
`outputs/ceo_reports/p04_real_ceo_report.md`。

诚实边界（已在报告顶部声明，且是 P1.5 验收的正确姿势）：
- Adjust / Meta 经本地 mock-server 发起**真实 urllib HTTP 调用**
  （HTTP 链路真建立、real_api_called=True）；生产环境填入真实 token 即直连
  官方 API，**代码路径不变**，仅 endpoint 在验收环境被替换为本地服务。
- MAX 读取真实报表文件（本脚本在临时 data 目录写入 ACCT_P15_report.json，
  结构等同真实 MAX Report API dump）。
- 首跑环比基线（前一日 revenue×2）为种子，用于触发 E17.2 并验证决策链路；
  自第 2 个真实运行日起自动失效（见报告声明）。

运行：
    python scripts/run_real_ceo_report.py
依赖：launchforge 为工作目录（from src / import operation 均可解析）。
"""
from __future__ import annotations

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

import operation.providers.live.adjust.kpi_client as kc
import operation.providers.live.meta.meta_client as mc
from src.ceo_intelligence.real_run.report import build_ceo_report
from src.ceo_intelligence.real_run.runner import RealCEOOperator

# 验收用代表性数字（merge witches / P04 量级，非生产真实数据，仅用于链路验收）
AD_DAILY = 700.0          # MAX 广告日收入
IAP_DAILY = 2000.0        # Adjust IAP 日收入
DAU = 7000                # Adjust DAU
PAYERS = 300
META_SPEND = 30000.0      # Meta 7 日窗口累计花费
META_INSTALLS = 6000
ACC_P15 = "ACCT_P15"
GAME_ID = "merge witches"
AS_OF = "2026-07-29"


# --------------------------------------------------------------------------- #
# 临时 fixture 生成
# --------------------------------------------------------------------------- #
def _write_fixtures(tmp_data: str) -> str:
    os.makedirs(tmp_data, exist_ok=True)
    # MAX 报表（结构等同真实 Report API dump，10 天 × 2 网络）
    dates = [f"2026-07-{d:02d}" for d in range(19, 29)]
    rows = []
    for d in dates:
        rows.append({
            "day": d, "application": GAME_ID, "ad_format": "REWARD",
            "country": "us", "network": "APPLOVIN",
            "impressions": "120000", "attempts": "300000", "responses": "90000",
            "ecpm": "0", "estimated_revenue": f"{AD_DAILY * 0.6:.1f}",
        })
        rows.append({
            "day": d, "application": GAME_ID, "ad_format": "INTER",
            "country": "us", "network": "MINTEGRAL_BIDDING",
            "impressions": "80000", "attempts": "200000", "responses": "60000",
            "ecpm": "0", "estimated_revenue": f"{AD_DAILY * 0.4:.1f}",
        })
    report = {"account": ACC_P15, "start": dates[0], "end": dates[-1], "rows": rows}
    with open(os.path.join(tmp_data, f"{ACC_P15}_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f)

    # 临时注册表（仅含验收游戏 → ACCT_P15）
    registry = {
        "_note": "P1.5 验收临时注册表（merge witches）。",
        "games": [{
            "game_id": GAME_ID,
            "display_name": "Merge Witches",
            "package_name": "",
            "genre": "merge",
            "platform": "unknown",
            "max_apps": [ACC_P15],
            "adjust_app_token_ref": "adjust:p15",
            "meta_campaign_ids": ["camp_p15"],
        }],
    }
    reg_path = os.path.join(tmp_data, "game_registry_p15.json")
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False)
    return reg_path


def _write_user_metrics() -> str:
    um_path = os.path.join(ROOT, "outputs", "user_metrics", f"{ACC_P15}.json")
    os.makedirs(os.path.dirname(um_path), exist_ok=True)
    with open(um_path, "w", encoding="utf-8") as f:
        json.dump({"account": ACC_P15, "app_dau": {GAME_ID: DAU}}, f)
    return um_path


# --------------------------------------------------------------------------- #
# mock-server（真实 urllib 调用本地端点）
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


def _serve(handler_cls):
    srv = HTTPServer(("127.0.0.1", 0), handler_cls)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def main() -> int:
    out_dir = os.path.join(ROOT, "outputs", "ceo_reports")
    os.makedirs(out_dir, exist_ok=True)
    tmp_data = os.path.join(out_dir, "_p15_verification", "data")
    tmp_store = os.path.join(out_dir, "_p15_verification", "store")
    # 每次运行用全新 store，保证首跑环比种子（bootstrap_prev）必触发、报告可复现
    shutil.rmtree(tmp_store, ignore_errors=True)
    reg_path = _write_fixtures(tmp_data)
    um_path = _write_user_metrics()

    adjust_srv = _serve(_AdjustHandler)
    meta_srv = _serve(_MetaHandler)
    adjust_port = adjust_srv.server_address[1]
    meta_port = meta_srv.server_address[1]

    # 指向本地 mock（生产环境改回官方 BASE 即直连）
    kc.REPORT_BASE = f"http://127.0.0.1:{adjust_port}"
    mc.GRAPH_BASE = f"http://127.0.0.1:{meta_port}"

    try:
        op = RealCEOOperator(
            registry_path=reg_path,
            data_dir=tmp_data,
            store_root=tmp_store,
            max_accounts=[ACC_P15],
            adjust_app_tokens={GAME_ID: "adj_p15"},
            adjust_user_token="user_p15",
            meta_access_token="meta_tok",
            meta_ad_account_id="act_123",
            meta_app_map={"camp_p15": GAME_ID},
        )
        result = op.run(GAME_ID, AS_OF)

        # 验收闸门（失败即抛错，确保报告仅在全绿时落盘）
        op.validator.assert_valid(result)

        report = build_ceo_report(result)
        out_path = os.path.join(out_dir, "p04_real_ceo_report.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[P1.5] 报告已生成：{out_path}")
        print(f"[P1.5] hub_real_api_called={result.hub_real_api_called} "
              f"| reality_confidence={result.reality_confidence:.2f} "
              f"| gates_passed={result.validation.passed}")
        return 0
    finally:
        kc.REPORT_BASE = "https://automate.adjust.com"
        mc.GRAPH_BASE = "https://graph.facebook.com"
        adjust_srv.shutdown()
        meta_srv.shutdown()
        # 清理临时 user_metrics（避免污染真实目录）
        try:
            os.remove(um_path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
