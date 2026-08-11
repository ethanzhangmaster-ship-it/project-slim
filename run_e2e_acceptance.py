"""E2E 无人值守验收脚本 — AI Game Studio OS.

跑通完整闭环链路并输出结构化证据:
  CEO 例会 → GrowthLoop → 决策审批 → LiveOps 流失分析 → 回流活动设计
  → 活动执行 + 审批 → ChurnAlert 回流 → 监控总览聚合

Usage:
    # 方式 1: 启动后端后运行 (推荐, 走真实 HTTP)
    python -m uvicorn src.market_ops.workspace.app:app --port 8000 --host 127.0.0.1
    python run_e2e_acceptance.py

    # 方式 2: 直接运行 (脚本内部启动 TestClient, 无需独立后端)
    python run_e2e_acceptance.py

Output:
    - 控制台: 逐步骤 PASS/FAIL/SKIP 摘要
    - e2e_evidence.json: 完整证据文件
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# 默认配置
BASE_URL = "http://127.0.0.1:8000"
GAME_ID = "p04"
EVIDENCE_FILE = PROJECT_ROOT / "e2e_evidence.json"
TIMEOUT_S = 30


# ═══════════════════════════════════════════════════════════════
# 客户端: 优先 HTTP, 回退 TestClient
# ═══════════════════════════════════════════════════════════════


class E2EClient:
    """统一客户端: 优先用 requests 走真实 HTTP, 不可用时回退 TestClient."""

    def __init__(self) -> None:
        self._http: Any = None
        self._test_client: Any = None
        try:
            import requests  # noqa: F401
            # 探测后端是否在跑
            try:
                import requests as _r
                _r.get(f"{BASE_URL}/healthz", timeout=2)
                self._http = _r
            except Exception:
                self._http = None
        except ImportError:
            self._http = None

        if self._http is None:
            from fastapi.testclient import TestClient
            from src.market_ops.workspace.app import app
            self._test_client = TestClient(app)

    def get(self, path: str) -> tuple[int, Any]:
        if self._http is not None:
            r = self._http.get(f"{BASE_URL}{path}", timeout=TIMEOUT_S)
            return r.status_code, _safe_json(r)
        r = self._test_client.get(path)
        return r.status_code, _safe_json(r)

    def post(self, path: str, body: dict | None = None) -> tuple[int, Any]:
        if self._http is not None:
            r = self._http.post(f"{BASE_URL}{path}", json=body or {}, timeout=TIMEOUT_S)
            return r.status_code, _safe_json(r)
        r = self._test_client.post(path, json=body or {})
        return r.status_code, _safe_json(r)


def _safe_json(r: Any) -> Any:
    try:
        return r.json()
    except Exception:
        return {"_text": getattr(r, "text", "")}


# ═══════════════════════════════════════════════════════════════
# 12 步链路
# ═══════════════════════════════════════════════════════════════


def run_e2e() -> dict[str, Any]:
    client = E2EClient()
    steps: list[dict[str, Any]] = []
    started_at = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()

    def step(idx: int, name: str, status: str, detail: dict[str, Any]) -> None:
        steps.append({
            "step": idx,
            "name": name,
            "status": status,
            "detail": detail,
        })
        marker = {"pass": "✓", "fail": "✗", "skip": "○"}.get(status, "?")
        print(f"  [{marker}] Step {idx:>2} {name} — {status.upper()}")

    print("=" * 72)
    print("E2E 无人值守验收 — AI Game Studio OS")
    print(f"开始时间: {started_at}")
    print("=" * 72)

    # ── Step 1: CEO 每日例会 ─────────────────────────────────
    print("\n[1/12] CEO 每日例会")
    code, data = client.post("/api/ceo/daily-run", {"use_real_data": False})
    if code == 200:
        stages = data.get("stages", [])
        step(1, "CEO 每日例会", "pass", {
            "endpoint": "POST /api/ceo/daily-run",
            "mode": "demo",
            "stages": len(stages),
            "status": data.get("status", ""),
            "duration_seconds": data.get("duration_seconds", 0),
            "real_api_called": data.get("real_api_called", False),
        })
    else:
        step(1, "CEO 每日例会", "fail", {"http_code": code, "response": data})
        return _build_evidence(steps, started_at, t0)

    # ── Step 2: GrowthLoop 触发 ──────────────────────────────
    print("[2/12] GrowthLoop 触发")
    code, data = client.post("/api/loop/trigger", {
        "dry_run": True,
        "days": 7,
        "fetch_meta_ads": False,
    })
    if code == 200:
        step(2, "GrowthLoop 触发", "pass", {
            "endpoint": "POST /api/loop/trigger",
            "mode": "dry_run",
            "cycle": data.get("cycle_number"),
            "phase": data.get("phase", ""),
            "actions_planned": data.get("actions_planned", 0),
        })
    else:
        step(2, "GrowthLoop 触发", "fail", {"http_code": code, "response": data})

    # ── Step 3: 决策列表 + 审批 ──────────────────────────────
    print("[3/12] 决策列表 + 审批")
    code, data = client.get("/api/decisions")
    if code == 200:
        decisions = data if isinstance(data, list) else data.get("decisions", [])
        pending = [d for d in decisions if d.get("status") == "pending"]
        approved_one = False
        for d in pending[:1]:
            cid = d.get("decision_id") or d.get("id")
            if cid:
                c2, _ = client.post(f"/api/decisions/{cid}/approve", {"approver": "e2e"})
                if c2 == 200:
                    approved_one = True
        step(3, "决策列表 + 审批", "pass" if not pending else ("pass" if approved_one else "fail"), {
            "endpoint": "GET /api/decisions",
            "total": len(decisions),
            "pending": len(pending),
            "approved_in_this_run": approved_one,
        })
    else:
        step(3, "决策列表 + 审批", "fail", {"http_code": code, "response": data})

    # ── Step 4: LiveOps 流失分析 ─────────────────────────────
    print("[4/12] LiveOps 流失分析")
    code, data = client.get(f"/api/liveops/churn-analysis/{GAME_ID}")
    if code == 200:
        step(4, "LiveOps 流失分析", "pass", {
            "endpoint": f"GET /api/liveops/churn-analysis/{GAME_ID}",
            "game_id": data.get("game_id", GAME_ID),
            "total_players": data.get("total_players", 0),
            "at_risk_count": data.get("at_risk_count", 0),
            "avg_churn_risk": data.get("avg_churn_risk", 0.0),
        })
    else:
        step(4, "LiveOps 流失分析", "fail", {"http_code": code, "response": data})

    # ── Step 5: LiveOps 回流活动设计 ─────────────────────────
    print("[5/12] LiveOps 回流活动设计")
    code, data = client.post("/api/liveops/winback-campaign", {"game_id": GAME_ID})
    if code == 200:
        campaign_id = data.get("campaign_id", "")
        step(5, "LiveOps 回流活动设计", "pass", {
            "endpoint": "POST /api/liveops/winback-campaign",
            "campaign_id": campaign_id,
            "campaign_type": data.get("campaign_type", ""),
            "target_count": data.get("target_count", 0),
        })
    else:
        campaign_id = ""
        step(5, "LiveOps 回流活动设计", "fail", {"http_code": code, "response": data})

    # ── Step 6: LiveOps 活动执行 ─────────────────────────────
    print("[6/12] LiveOps 活动执行")
    if campaign_id:
        code, data = client.post(
            f"/api/liveops/campaigns/{campaign_id}/execute",
            {"dry_run": False},
        )
        if code == 200:
            step(6, "LiveOps 活动执行", "pass", {
                "endpoint": f"POST /api/liveops/campaigns/{campaign_id}/execute",
                "execution_id": data.get("execution_id", ""),
                "approval_level": data.get("approval_level", -1),
                "status": data.get("status", ""),
                "actions": len(data.get("actions", [])),
            })
        else:
            step(6, "LiveOps 活动执行", "fail", {"http_code": code, "response": data})
    else:
        step(6, "LiveOps 活动执行", "skip", {"reason": "无 campaign_id (Step 5 失败)"})

    # ── Step 7: LiveOps 执行审批 ─────────────────────────────
    print("[7/12] LiveOps 执行审批")
    code, data = client.get("/api/liveops/pending-approvals")
    if code == 200:
        pending_exec = data if isinstance(data, list) else data.get("pending", [])
        step(7, "LiveOps 执行审批", "pass" if not pending_exec else "skip", {
            "endpoint": "GET /api/liveops/pending-approvals",
            "pending_count": len(pending_exec),
            "note": "Level 0 自动通过, 无 pending" if not pending_exec else "存在待审批",
        })
    else:
        step(7, "LiveOps 执行审批", "fail", {"http_code": code, "response": data})

    # ── Step 8: ChurnAlert 回流响应 ──────────────────────────
    print("[8/12] ChurnAlert 回流响应")
    code, data = client.get("/api/growth/churn-responses")
    if code == 200:
        responses = data if isinstance(data, list) else data.get("responses", [])
        step(8, "ChurnAlert 回流响应", "pass", {
            "endpoint": "GET /api/growth/churn-responses",
            "responses": len(responses),
        })
    else:
        step(8, "ChurnAlert 回流响应", "fail", {"http_code": code, "response": data})

    # ── Step 9: ChurnAlert 统计 ──────────────────────────────
    print("[9/12] ChurnAlert 统计")
    code, data = client.get("/api/growth/churn-responses/stats")
    if code == 200:
        step(9, "ChurnAlert 统计", "pass", {
            "endpoint": "GET /api/growth/churn-responses/stats",
            "stats": data if isinstance(data, dict) else {"raw": data},
        })
    else:
        step(9, "ChurnAlert 统计", "fail", {"http_code": code, "response": data})

    # ── Step 10: 监控总览 ────────────────────────────────────
    print("[10/12] 监控总览")
    code, data = client.get("/api/monitor/overview")
    if code == 200:
        health = data.get("health", {}) if isinstance(data.get("health"), dict) else {}
        step(10, "监控总览", "pass", {
            "endpoint": "GET /api/monitor/overview",
            "health_status": health.get("status", data.get("health_status", "")),
            "alerts_count": data.get("alerts_count", 0),
            "critical_alerts": data.get("critical_alerts", 0),
            "warning_alerts": data.get("warning_alerts", 0),
            "growth_loop": data.get("growth_loop", {}),
            "liveops": data.get("liveops", {}),
            "approval_queue": health.get("subsystems", {}).get("approval_queue", {}),
        })
    else:
        step(10, "监控总览", "fail", {"http_code": code, "response": data})

    # ── Step 11: 监控告警列表 ────────────────────────────────
    print("[11/12] 监控告警列表")
    code, data = client.get("/api/monitor/alerts")
    if code == 200:
        alerts = data if isinstance(data, list) else data.get("alerts", [])
        step(11, "监控告警列表", "pass", {
            "endpoint": "GET /api/monitor/alerts",
            "alerts": len(alerts),
            "alert_ids": [a.get("alert_id", "") for a in alerts[:5]],
        })
    else:
        step(11, "监控告警列表", "fail", {"http_code": code, "response": data})

    # ── Step 12: 跨 Agent 协同拓扑 ───────────────────────────
    print("[12/12] 跨 Agent 协同拓扑")
    code, data = client.get("/api/liveops/cross-agent")
    if code == 200:
        step(12, "跨 Agent 协同拓扑", "pass", {
            "endpoint": "GET /api/liveops/cross-agent",
            "topology_nodes": data.get("topology", {}).get("nodes", 0),
            "topology_edges": data.get("topology", {}).get("edges", 0),
            "ceo_liveops_triggered": data.get("ceo_liveops_triggered", False),
            "total_liveops_events": data.get("total_liveops_events", 0),
        })
    else:
        step(12, "跨 Agent 协同拓扑", "fail", {"http_code": code, "response": data})

    return _build_evidence(steps, started_at, t0)


def _build_evidence(steps: list[dict[str, Any]], started_at: str, t0: float) -> dict[str, Any]:
    total = len(steps)
    passed = sum(1 for s in steps if s["status"] == "pass")
    failed = sum(1 for s in steps if s["status"] == "fail")
    skipped = sum(1 for s in steps if s["status"] == "skip")
    overall = "PASS" if failed == 0 else "FAIL"

    evidence = {
        "acceptance_date": started_at,
        "duration_seconds": round(time.time() - t0, 2),
        "summary": {
            "total_steps": total,
            "pass": passed,
            "fail": failed,
            "skip": skipped,
            "overall": overall,
        },
        "steps": steps,
    }

    EVIDENCE_FILE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 72)
    print(f"E2E 验收结论: {overall}")
    print(f"  Total: {total}  Pass: {passed}  Fail: {failed}  Skip: {skipped}")
    print(f"  耗时: {evidence['duration_seconds']}s")
    print(f"  证据文件: {EVIDENCE_FILE}")
    print("=" * 72)
    return evidence


if __name__ == "__main__":
    result = run_e2e()
    sys.exit(0 if result["summary"]["overall"] == "PASS" else 1)
