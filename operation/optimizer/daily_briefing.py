"""
E15.2.5+ — Daily Briefing runner: all live MAX accounts, one command.

For every account in credentials/live_accounts.json:
  pull -> analyze -> report(+config +forecast) -> reconcile ledger.
Fleet Brain per-app IAA verdicts (SCALE/KEEP/FIX/KILL) and Growth new-game
opportunity discovery are folded into ONE unified morning digest card sent
to Feishu (zero clicks) — the operator receives a single daily report
(revenue diagnosis + fleet verdicts + growth opportunities), not several
separate cards.

Design:
  * One account failing (network, SSL blip, missing key) never blocks the
    others; the failure is recorded in the run summary and pushed as a
    plain-text Feishu alert so a silent skip is impossible.
  * Single card: revenue diagnosis + fleet verdicts + growth opportunities
    are combined into one Feishu interactive card per morning run.
  * Window: LOOKBACK_DAYS ending yesterday (MAX report lags 1-2 days;
    yesterday keeps the freshest usable edge without empty-day noise).
  * Zero MAX writes — this only reads reports and pushes advice.
  * Run summary saved to outputs/daily_briefing/<date>.json for audit /
    scheduler observability.

Usage:
  PYTHONPATH=. python operation/optimizer/daily_briefing.py            # all accounts
  PYTHONPATH=. python operation/optimizer/daily_briefing.py ACCT_2     # one account
  PYTHONPATH=. python operation/optimizer/daily_briefing.py --no-notify
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import date, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")))

from operation.optimizer.intelligence_agent import MonetizationIntelligenceAgent  # noqa: E402
from operation.providers.live.max.accounts import load_accounts  # noqa: E402

LOOKBACK_DAYS = 10
OUT_DIR = os.path.join("outputs", "daily_briefing")


def _window(today: Optional[date] = None) -> tuple:
    """Return (start, end) — LOOKBACK_DAYS ending yesterday."""
    t = today or date.today()
    end = t - timedelta(days=1)
    start = end - timedelta(days=LOOKBACK_DAYS - 1)
    return start.isoformat(), end.isoformat()


def _fetch_user_metrics(account_id: str, start: str, end: str):
    """Best-effort true DAU source (Adjust auto-fetch, manual drop-in cache).
    Returns a UserMetrics with available=True, or None when nothing serves."""
    try:
        from operation.optimizer.user_metrics import UserMetricsService
        um = UserMetricsService().fetch(account_id, start, end)
        if um and um.available and um.dau > 0:
            return um
    except Exception:
        pass
    return None


def run_account(agent: MonetizationIntelligenceAgent, account_id: str,
                start: str, end: str, notify: bool = True) -> Dict:
    """Run one account end-to-end; never raises."""
    t0 = time.time()
    user_metrics = _fetch_user_metrics(account_id, start, end)
    try:
        if notify:
            out = agent.run_and_notify(account_id, start, end,
                                       user_metrics=user_metrics,
                                       cache_rows=True)
        else:
            out = agent.run(account_id, start, end,
                            user_metrics=user_metrics, cache_rows=True)
            # Reconcile the action ledger (read-only loop bookkeeping) so the
            # unified digest can show closed/open action counts. No Feishu push
            # — the single morning card is emitted by run_all().
            from operation.optimizer.loop.action_ledger import ActionLedger
            out["loop"] = ActionLedger("outputs/action_ledger").reconcile(
                out["report"])
        r = out["report"]
        loop = out.get("loop") or {}
        fc = r.ecpm_forecasts[0]["summary"] if r.ecpm_forecasts else {}
        cfg = (r.config_recommendations[0]["summary"]
               if r.config_recommendations
               and isinstance(r.config_recommendations[0], dict)
               and "summary" in r.config_recommendations[0]
               else {})
        return {
            "account": account_id, "status": "OK",
            "seconds": round(time.time() - t0, 1),
            "rows": out.get("rows_analyzed"),
            "health": r.health_score, "opportunity": r.opportunity_score,
            "risk": r.risk_score,
            "revenue": round(r.revenue, 2),
            "blended_ecpm": round(r.blended_ecpm, 2),
            "actions": len(r.actions),
            "loop_resolved": int(loop.get("resolved", 0) or 0),
            "loop_open": int(loop.get("open", 0) or 0),
            "early_warnings": fc.get("early_warning", 0),
            "config_segments": cfg.get("segments",
                                       len(r.config_recommendations[0].get(
                                           "segments", []))
                                       if r.config_recommendations else 0),
            "notified": bool(out.get("notify")),
            "notify_error": out.get("notify_error"),
            "paths": {k: v for k, v in out.get("paths", {}).items()},
        }
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        cached = _replay_cache(agent, account_id, start, end)
        if cached is not None:
            cached["live_error"] = f"{type(exc).__name__}: {exc}"
            cached["seconds"] = round(time.time() - t0, 1)
            return cached
        return {
            "account": account_id, "status": "FAIL",
            "seconds": round(time.time() - t0, 1),
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(limit=3),
        }


def _replay_cache(agent: MonetizationIntelligenceAgent, account_id: str,
                  start: str, end: str) -> Optional[Dict]:
    """Last-resort fallback: if the live pull fails, replay the most recent
    saved raw report (data/<ACCT>_report.json) so the operator still gets a
    card instead of a silent skip. Returns a result dict or None."""
    p = os.path.join("data", f"{account_id}_report.json")
    if not os.path.exists(p):
        return None
    try:
        blob = json.load(open(p, encoding="utf-8"))
        rows = blob.get("rows") if isinstance(blob, dict) else blob
        if not rows:
            return None
        out = agent.run_and_notify(account_id, start, end, rows=rows,
                                   save=False)
        r = out["report"]
        return {
            "account": account_id, "status": "OK_CACHED",
            "seconds": 0.0,
            "rows": out.get("rows_analyzed"),
            "health": r.health_score, "opportunity": r.opportunity_score,
            "risk": r.risk_score, "revenue": round(r.revenue, 2),
            "blended_ecpm": round(r.blended_ecpm, 2),
            "actions": len(r.actions),
            "early_warnings": 0, "config_segments": 0,
            "notified": bool(out.get("notify")),
            "notify_error": out.get("notify_error"),
            "paths": {k: v for k, v in out.get("paths", {}).items()},
            "cached_from": p,
        }
    except Exception:  # noqa: BLE001
        return None


def _run_fleet(account_ids: List[str], notify: bool = True) -> Dict:
    """Build per-app IAA verdicts (SCALE/KEEP/FIX/KILL) from the freshly
    cached MAX reports and push them as one combined Feishu card. Pure
    best-effort: any failure is recorded, never raised, so the Revenue-OS
    morning cards are never blocked by the fleet view."""
    try:
        from operation.factory_brain.fleet_bridge import RealFleetBridge
        bridge = RealFleetBridge()
        reports = bridge.build_all(account_ids)
        if not reports:
            return {"status": "NO_DATA",
                    "note": "no cached MAX reports for " + ",".join(account_ids)}
        md = bridge.render_markdown(reports)
        out_dir = os.path.join("outputs", "fleet_verdicts")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{date.today().isoformat()}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        out = {
            "status": "OK",
            "accounts": [r.account for r in reports],
            "games": sum(len(r.games) for r in reports),
            "verdicts": sum(len(r.verdicts) for r in reports),
            "path": path,
            "markdown": md,
            "notified": False,
        }
        if notify:
            try:
                from operation.optimizer.notify.feishu import send_markdown_card
                res = send_markdown_card(
                    "\U0001F6A2 真实舰队每日判决 · Real Fleet Verdicts",
                    md, color="blue")
                out["notified"] = res is not None
            except Exception as exc:  # noqa: BLE001 — webhook missing/limit
                out["notified"] = False
                out["notify_error"] = f"{type(exc).__name__}: {exc}"
        return out
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_growth(notify: bool = True) -> Dict:
    """Discover new-game market opportunities (Growth OS) and persist the
    briefing, but do NOT push its own card — it is folded into the unified
    morning digest by run_all(). Best-effort: any failure is recorded,
    never raised, so the revenue/fleet cards are never blocked by growth."""
    try:
        from operation.factory_brain.growth_sources.briefing import run as growth_run
        from operation.factory_brain.growth_sources.ingester import build_pipeline_sources
        out = growth_run(notify=False,
                         sources=build_pipeline_sources())  # unified card pushed by run_all
        return {
            "status": "OK",
            "opportunities": int(out["report"].get("count", 0) or 0),
            "markdown": out["markdown"],
            "file": out["file"],
            "notified": False,
        }
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _store_status_live() -> bool:
    """Opt-in gate for REAL store API calls in the morning digest.

    Default = False (dry_run, ZERO network even if credentials exist). Flip
    to True only by setting env LAUNCHFORGE_STORE_LIVE=1 in the automation
    after valid credentials are filled — an auditable approval step, matching
    the system's three-gate execution policy (never auto-touch a store).

    Also reads ``credentials/.env_store_live`` (written by the
    ``import_store_credentials --live-enable`` command) so a persisted
    flag is picked up even without modifying the automation's env vars.
    """
    env = os.environ.get("LAUNCHFORGE_STORE_LIVE")
    if env == "1":
        return True
    # fallback: check credentials/.env_store_live at multiple paths
    candidates = [
        os.path.join(".", "credentials", ".env_store_live"),
        os.path.join("..", "credentials", ".env_store_live"),
    ]
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(here))),
            "credentials", ".env_store_live"))
    except Exception:
        pass
    for path in candidates:
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    if "LAUNCHFORCE_STORE_LIVE=1" in f.read():
                        return True
        except OSError:
            continue
    return False


def _run_store_status(notify: bool = True) -> Dict:
    """Pull live publishing status (App Store Connect / Google Play) for every
    game in the fleet registry and render a table. Folded into the unified
    morning digest (no push of its own). Best-effort + fault-isolated: any
    failure is recorded, never raised, so the other cards are never blocked.

    Safety: by default dry_run=True → ZERO network. Real calls only happen
    when LAUNCHFORGE_STORE_LIVE=1 is set AND the vault holds credentials.
    """
    try:
        from operation.publishing_factory.catalog.game_registry import (
            GameRegistry)
        from operation.publishing.store_status import collect_store_status

        reg = GameRegistry().load()
        products = reg.list_all()
        # One entry per (game, platform) so both stores are tracked.
        games = []
        for g in products:
            for plat in g.platforms:
                store_plat = ("ios" if plat == "app_store"
                              else "android" if plat == "google_play" else None)
                if not store_plat:
                    continue
                entry = {"game_id": g.game_id, "platform": store_plat}
                if store_plat == "ios":
                    entry["bundle_id"] = g.package_name
                else:
                    entry["package_name"] = g.package_name
                games.append(entry)

        if not games:
            return {"status": "NO_DATA",
                    "note": "catalog 为空，填 data/catalog.json 即自动纳入"}

        live = _store_status_live()
        report = collect_store_status(games, dry_run=not live)
        md = _render_store_status_md(report, live)
        out = {
            "status": report.get("status", "disabled"),
            "real_api_called": bool(report.get("real_api_called", False)),
            "games": len(games),
            "markdown": md,
            "notified": False,
        }
        if notify:
            # Store status is folded into the unified card; this branch is
            # reserved but currently a no-op (run_all pushes the single card).
            pass
        return out
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_production_readiness(notify: bool = True) -> Dict:
    """Show per-app closed-testing 14-day clock for every tracked package.

    Google Play requires each NEW app to have 12+ testers opted in for 14
    consecutive days before production access is granted. We track that
    locally in ``data/tester_progress.json`` and surface it as the 5th
    section of the unified morning digest — so the operator can see at
    a glance which apps are ready, which are still counting down, and
    which need more testers.

    Folded into the unified card (no push of its own). Best-effort:
    failures are recorded, never raised. NEW SECTION, ZERO WRITES.
    """
    try:
        from operation.publishing_factory.tester_community import (
            community as tc_community,
            eligibility as tc_eligibility,
        )
        from operation.publishing_factory.play_runtime.tester_pool_agent import (
            summary as pool_summary, promotion_readiness,
            render_promotion_markdown,
        )
        cfg = tc_community.load()
        rows = tc_eligibility.all_apps()
        md = tc_eligibility.render_markdown(rows)
        # E13.5 Tester Pool: supply (>=12?) + which apps are promotion-ready
        # (pool>=12 AND 14-day clock done). Surfaced as a highlight on the
        # same section-5 board so the operator sees the full gate at a glance.
        pool = pool_summary()
        promo = promotion_readiness([r["package_name"] for r in rows])
        extra = render_promotion_markdown(promo)
        return {
            "status": "OK",
            "community_configured": bool(cfg.get("configured")),
            "tester_count": len(cfg.get("emails", []) or []),
            "group_count": len(cfg.get("groups", []) or []),
            "tracked_packages": len(rows),
            "ready_packages": sum(1 for r in rows
                                  if r.get("production_ready")),
            "pool_size": pool["pool_size"],
            "pool_meets_min": pool["meets_minimum"],
            "promote_ready": promo["promote_ready"],
            "promote_count": promo["promote_count"],
            "markdown": md + extra,
            "notified": False,
        }
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _render_release_state_md() -> str:
    """Render the staged-rollout progress table from the local
    ``release_state.json`` (written by the Release Agent). Zero network —
    this is just the persisted decision state, not a live console read."""
    try:
        from pathlib import Path
        import json
        p = Path("data/play_runtime/release_state.json")
        if not p.exists():
            return ""
        state = json.loads(p.read_text(encoding="utf-8"))
        if not state:
            return ""
        lines = ["", "**灰度进度 (Release Agent)**", "",
                 "| 包 | 当前阶段 | 状态 | 上次推进 |",
                 "|---|---|---|---|"]
        frac = {0: "5%", 1: "20%", 2: "50%", 3: "100%"}
        for pkg, st in state.items():
            idx = st.get("stage_index", -1)
            pct = frac.get(idx, f"阶段{idx}")
            status = st.get("status", "?")
            last = (st.get("last_advance_at") or "")[:10]
            lines.append(f"| {pkg} | {pct} | {status} | {last} |")
        return "\n".join(lines)
    except Exception:
        return ""


def _run_health(notify: bool = True) -> Dict:
    """E13.5 — surface the latest Vitals health board as the 7th unified-card
    section. Shows each tracked package's most recent health recommendation
    (healthy / watch / halt / no_data) so the operator sees at a glance which
    live rollouts are safe and which need a halt. Reads ONLY the local
    ``health.jsonl`` audit log (written by the Health Agent's ``run_daily`` /
    ``evaluate``) — ZERO network, ZERO writes in the briefing itself."""
    try:
        from operation.publishing_factory.play_runtime.health_audit import (
            latest_board)
        board = latest_board()
        if not board:
            md = "_暂无 Vitals 健康记录（Health Agent 已就绪，跑 " \
                 "`health_cli run` 即出真实健康看板）_"
            return {"status": "EMPTY", "count": 0, "markdown": md}
        label = {"healthy": "✅ 健康", "watch": "⚠️ 关注",
                 "halt": "🛑 须halt", "no_data": "⚪ 无数据"}
        lines = ["| 包 | 判定 | crash% | anr% | 原因 |",
                 "|---|---|---|---|---|"]
        crit = 0
        for pkg, rec in sorted(board.items()):
            rec_name = rec.get("recommendation", "no_data")
            if rec_name == "halt":
                crit += 1
            cr = rec.get("crash_rate")
            ar = rec.get("anr_rate")
            cr_s = f"{cr:.2f}" if isinstance(cr, (int, float)) else "—"
            ar_s = f"{ar:.2f}" if isinstance(ar, (int, float)) else "—"
            reason = "; ".join(rec.get("reasons", []) or []) or "—"
            lines.append(
                f"| {pkg} | {label.get(rec_name, rec_name)} | {cr_s} | "
                f"{ar_s} | {reason} |")
        note = (f"\n\n_🛑 {crit} 个包触发 halt 判定，需运营确认是否停版_"
                if crit else "")
        return {"status": "OK", "count": len(board), "critical": crit,
                "markdown": "\n".join(lines) + note}
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_review(notify: bool = True) -> Dict:
    """E13.5 — surface the latest review-intelligence board as the 8th
    unified-card section. Shows each tracked package's review mix (crash /
    bug / complaint / question / praise), how many need a reply, and how many
    have already been replied to. Reads ONLY the local ``reviews.jsonl`` audit
    log (written by the Review Agent's ``run_daily``) — ZERO network, ZERO
    writes in the briefing itself."""
    try:
        from operation.publishing_factory.play_runtime.review_audit import (
            summary_by_package)
        board = summary_by_package()
        if not board:
            md = "_暂无评论情报（Review Agent 已就绪，跑 " \
                 "`review_cli run` 即出真实评论看板）_"
            return {"status": "EMPTY", "count": 0, "markdown": md}
        cat_label = {"crash": "💥崩溃", "bug": "🐞异常",
                     "complaint": "😠吐槽", "question": "❓提问",
                     "praise": "👍好评", "ignore": "🤔中性"}
        lines = ["| 包 | 总量 | 崩溃 | 异常 | 吐槽 | 提问 | 好评 | 待回 | 已回 |",
                 "|---|---|---|---|---|---|---|---|---|"]
        tot = {"total": 0, "crash": 0, "bug": 0, "complaint": 0,
               "question": 0, "praise": 0, "needs_reply": 0, "replied": 0}
        # Sort by volume desc so the noisiest packages surface first.
        for pkg, agg in sorted(board.items(),
                               key=lambda kv: kv[1].get("total", 0),
                               reverse=True):
            for k in tot:
                tot[k] += agg.get(k, 0)
            lines.append(
                f"| {pkg} | {agg.get('total', 0)} | {agg.get('crash', 0)} | "
                f"{agg.get('bug', 0)} | {agg.get('complaint', 0)} | "
                f"{agg.get('question', 0)} | {agg.get('praise', 0)} | "
                f"{agg.get('needs_reply', 0)} | {agg.get('replied', 0)} |")
        # footer total row
        lines.append(
            f"| **合计** | **{tot['total']}** | {tot['crash']} | {tot['bug']} | "
            f"{tot['complaint']} | {tot['question']} | {tot['praise']} | "
            f"**{tot['needs_reply']}** | **{tot['replied']}** |")
        note = (f"\n\n_💡 评论分类：{cat_label['crash']}{cat_label['bug']}"
                f"{cat_label['complaint']}{cat_label['question']}"
                f"{cat_label['praise']}；`review_cli run --apply` 自动回复待回评论_")
        return {"status": "OK", "count": len(board),
                "needs_reply": tot["needs_reply"],
                "replied": tot["replied"],
                "markdown": "\n".join(lines) + note}
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_experiment(notify: bool = True) -> Dict:
    """E13.5 — surface the ASO (store-listing experiment) board as the 9th
    unified-card section. Shows each tracked package's experiment mix
    (proposed / created / running / ended) and any winner recommendations.
    Reads ONLY the local ``experiments.jsonl`` audit log (written by the
    Listing Experiment Agent's ``run_daily``) — ZERO network, ZERO writes in
    the briefing itself."""
    try:
        from operation.publishing_factory.play_runtime.experiment_audit import (
            summary_by_package)
        board = summary_by_package()
        if not board:
            md = "_暂无 ASO 实验（Listing Experiment Agent 已就绪，跑 " \
                 "`experiment_cli evaluate` 即出真实实验看板）_"
            return {"status": "EMPTY", "count": 0, "markdown": md}
        lines = ["| 包 | 提案 | 已建 | 进行中 | 已结束 | 胜出建议 |",
                 "|---|---|---|---|---|---|"]
        tot = {"proposed": 0, "created": 0, "running": 0,
               "ended": 0, "winner": 0}
        for pkg, agg in sorted(board.items(),
                               key=lambda kv: kv[1].get("running", 0),
                               reverse=True):
            for k in tot:
                tot[k] += agg.get(k, 0)
            lines.append(
                f"| {pkg} | {agg.get('proposed', 0)} | {agg.get('created', 0)} "
                f"| {agg.get('running', 0)} | {agg.get('ended', 0)} | "
                f"{agg.get('winner', 0)} |")
        lines.append(
            f"| **合计** | **{tot['proposed']}** | **{tot['created']}** | "
            f"**{tot['running']}** | **{tot['ended']}** | **{tot['winner']}** |")
        note = ("\n\n_💡 ASO = 商店列表 A/B 实验（`edits.experiments`）："
                "只测不改，胜出再推广；`experiment_cli title-test --apply` "
                "可发起标题实验（如 fil/ar 合规短标题）_")
        return {"status": "OK", "count": len(board),
                "running": tot["running"], "ended": tot["ended"],
                "winner": tot["winner"],
                "markdown": "\n".join(lines) + note}
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_tester_pool(notify: bool = True) -> Dict:
    """E13.5 — surface the persistent closed-testing tester pool status as
    the 10th unified-card section. Shows pool size vs the 12-tester minimum
    and the last invite outcome per app. Reads ONLY the local pool file +
    audit JSONL — ZERO network, ZERO writes.

    Note: Google Play needs >= 12 OPTED-IN testers before promotion; this
    agent automates the *invite* send (a persistent pool, invited once to
    every app) but cannot make people join — that still needs the testers'
    opt-in via the shared link.
    """
    try:
        from operation.publishing_factory.play_runtime.tester_pool_agent \
            import summary as pool_summary, MIN_POOL
        s = pool_summary()
        if s["pool_size"] == 0:
            md = ("_暂无测试员池（Tester Pool Agent 已就绪，跑 "
                  "`tester_pool_cli add you@x.com` 录入 12 个邮箱即可解锁"
                  "自动邀请）_")
            return {"status": "EMPTY", "count": 0, "markdown": md}
        pool_status = "✅ 达标" if s['meets_minimum'] else f"⚠️ 还差 {s['short_by']} 个"
        lines = [
            f"池规模 **{s['pool_size']}** / 晋升最低 **{s['min_required']}** "
            f"→ {pool_status}",
            "",
            "| 包 | 最后邀请 | 模式 | 缺口 |",
            "|---|---|---|---|",
        ]
        for pkg, st in sorted(s["per_package"].items()):
            ok = st.get("last_ok")
            mode = "真邀" if st.get("last_apply") else "模拟"
            miss = len(st.get("last_missing", []))
            lines.append(
                f"| {pkg} | {'✅' if ok else '❌'} | {mode} | {miss} |")
        note = ("\n\n_💡 测试员池只自动化「发邀请」这一步——你录入 12 个真实邮箱"
                "一次，之后每个新 App 自动邀请同一池；但 Google 要求测试员"
                "主动点链接加入才算数，这一步仍需人确认。_")
        if not s["per_package"]:
            note = ("\n\n_💡 池已建好，但尚未对任何 App 跑过 `tester_pool_cli "
                    "run <pkg> --apply`。每个新 App 跑一次即自动填满 12 人邀请。_")
        return {"status": "OK", "count": s["pool_size"],
                "meets_minimum": s["meets_minimum"],
                "markdown": "\n".join(lines) + note}
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_play_runtime(notify: bool = True) -> Dict:
    """E13.5 — surface the last-24h Google Play Runtime audit trail as the
    6th unified-card section. Shows what the system proposed / simulated /
    executed against the real console so the operator gets one glance at
    release + store-optimization activity. Reads ONLY the local JSONL audit
    log — ZERO network, ZERO writes."""
    try:
        from operation.publishing_factory.play_runtime.audit import last_24h
        recs = last_24h()
        if not recs:
            md = "_暂无 Play Runtime 操作记录（底座已就绪，待 " \
                 "Release / Health / ASO Agent 调用）_"
            rel = _render_release_state_md()
            if rel:
                md = md + "\n" + rel
            return {"status": "EMPTY", "count": 0, "markdown": md}
        lines = ["| 时间 | 操作 | 包 | 半径 | 阶段 | 真调API | 结果 |",
                 "|---|---|---|---|---|---|---|"]
        for r in recs[-15:]:
            at = (r.get("at") or "")[:19].replace("T", " ")
            op = r.get("op", "?")
            pkg = r.get("package_name", "?")
            radius = r.get("radius", "?")
            stage = r.get("stage", "?")
            api = "✅" if r.get("real_api_called") else "—"
            ok = "✅" if r.get("ok") else "❌"
            lines.append(
                f"| {at} | {op} | {pkg} | {radius} | {stage} | {api} | {ok} |")
        rel = _render_release_state_md()
        if rel:
            lines.append(rel)
        return {"status": "OK", "count": len(recs),
                "markdown": "\n".join(lines)}
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_play_ops(notify: bool = True) -> Dict:
    """E13.5 — run the unified Play Runtime daily sweep (Health -> Release ->
    Review -> Experiment -> Tester Pool) in ONE call so the morning briefing's
    Play sections (6-10) are auto-populated from a single command.

    SIMULATION by default (zero network) — under the morning automation this is
    always a dry sweep; the audits it writes are then read back by the section
    renderers below. Fault-isolated: any agent failure is recorded, never
    raised, so the rest of the digest is never blocked.
    """
    try:
        from operation.publishing_factory.play_runtime.runner import (
            run_play_ops, render_status_line)
        s = run_play_ops(packages=None, apply=False)
        lines = [render_status_line(s), "",
                 "| Agent | 状态 | 项数 | 耗时 |", "|---|---|---|---|"]
        for name, v in s["agents"].items():
            tag = "✅" if v["status"] == "OK" else "❌"
            lines.append(
                f"| {name} | {tag} {v['status']} | {v.get('items', 0)} | "
                f"{v.get('seconds', 0)}s |")
        if s["failures"]:
            lines.append("")
            lines.append("⚠️ " + " · ".join(s["failures"]))
        return {"status": s["status"], "agents_ok": s["agents_ok"],
                "agents_total": s["agents_total"], "mode": s["mode"],
                "real_api_called": s["real_api_called"],
                "packages": s["packages_count"],
                "markdown": "\n".join(lines), "notified": False}
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _run_cfo_report() -> Dict:
    """E16.1.x — run the CFO brain (Forecast + Portfolio) on the REAL MAX
    report dumps and embed the business report into the morning digest.

    Reads only local files (data/<ACCT>_report.json + user_metrics); writes
    outputs/cfo_report/<date>.md. Fault-isolated: never blocks the digest.
    """
    try:
        from operation.factory_brain.cfo_report import main as cfo_main
        path = cfo_main()
        md = path.read_text(encoding="utf-8")
        return {"status": "OK", "path": str(path), "markdown": md}
    except Exception as exc:  # noqa: BLE001 — isolation is the point
        return {"status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}"}


def _render_store_status_md(report: Dict, live: bool) -> str:
    """Render the store-status section body (no H1 — embedded under the
    digest's own '## 4️⃣' header)."""
    status = report.get("status", "disabled")
    per = report.get("per_game", [])
    lines = []
    if status == "disabled":
        reason = report.get("reason", "dry_run")
        if reason == "no_store_credentials":
            lines.append("_未激活：密钥库无商店凭证（填 credentials/store_keys.json "
                         "并设 LAUNCHFORGE_STORE_LIVE=1 即出真实状态）_")
        else:
            lines.append("_未激活：dry_run 安全模式（设 LAUNCHFORGE_STORE_LIVE=1 "
                         "即出真实上架状态）_")
    lines.append("| 游戏 | 平台 | 状态 | 版本 | 备注 |")
    lines.append("|---|---|---|---|---|")
    label = {
        "unknown": "未知", "prepare_for_submission": "待提交",
        "waiting_for_review": "等待审核", "in_review": "审核中",
        "rejected": "被拒", "ready_for_sale": "已上架",
        "approved": "已过审待发", "draft": "草稿", "published": "已发布",
    }
    for g in per:
        plat = "iOS" if g.get("platform") == "ios" else "Android"
        st = g.get("status") or "unknown"
        st_txt = label.get(st, st)
        ver = g.get("version") or "—"
        note = g.get("error") or g.get("note") or ""
        if st == "rejected" and not note:
            note = "查看商店后台驳回原因"
        lines.append(
            f"| {g.get('game_id')} | {plat} | {st_txt} | {ver} | {note} |")
    return "\n".join(lines)


def _strip_h1(md: str) -> str:
    """Drop the leading H1 title + blank lines so a section can be embedded
    under the digest's own headers without a duplicate title."""
    lines = md.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].startswith("#"):
        i += 1
        while i < len(lines) and lines[i].strip() == "":
            i += 1
    return "\n".join(lines[i:])


def _build_morning_digest(results: List[Dict], fleet_out: Dict,
                          growth_out: Dict, store_out: Dict,
                          production_out: Dict, health_out: Dict,
                          play_runtime_out: Dict, review_out: Dict,
                          experiment_out: Dict, tester_pool_out: Dict,
                          play_ops_out: Dict,
                          summary: Dict,
                          start: str, end: str) -> str:
    """Combine revenue diagnosis + fleet verdicts + growth opportunities +
    store publishing status into ONE markdown card the operator reads each
    morning."""
    date_str = summary["date"]
    ok = [r for r in results if r["status"].startswith("OK")]
    fail = [r for r in results if not r["status"].startswith("OK")]
    ready_n = int(production_out.get("ready_packages", 0) or 0)
    lines = [
        "# 🌅 LaunchForge 每日全量晨报",
        "",
        f"_生成 {date_str} · 数据窗口 {start} ~ {end}_",
        f"_亮灯：{len(ok)} 账户正常 / {len(fail)} 异常 · "
        f"舰队 {fleet_out.get('games', 0)} 款 · "
        f"新游机会 {growth_out.get('opportunities', 0)} 条 · "
        f"上架 {store_out.get('games', 0)} 款 · "
        f"待产 {ready_n} 款 · "
        f"健康 {health_out.get('count', 0)} 款"
        f"（🛑{health_out.get('critical', 0)}） · "
        f"Play巡检 {play_ops_out.get('agents_ok', 0)}/"
        f"{play_ops_out.get('agents_total', 0)}_",
        "",
        "## 1️⃣ 营收诊断 · Revenue OS",
        "",
    ]
    if ok:
        lines += [
            "| 账户 | 健康 | 机会 | 风险 | 营收$ | 混合eCPM | 动作 |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in ok:
            lines.append(
                f"| {r['account']} | {r['health']} | {r['opportunity']} | "
                f"{r['risk']} | {r['revenue']} | {r['blended_ecpm']} | "
                f"{r['actions']} |")
        loop_bits = []
        for r in ok:
            lr, lo = r.get("loop_resolved", 0), r.get("loop_open", 0)
            if lr or lo:
                loop_bits.append(f"{r['account']} 已闭环{lr}/待办{lo}")
        if loop_bits:
            lines += ["", "动作闭环：" + " · ".join(loop_bits)]
    if fail:
        lines += ["", "⚠️ 异常账户：" + ", ".join(r["account"] for r in fail)]
    lines += ["", "---", ""]
    # E16.1.x CFO business report (real dollars, forecast, verdicts)
    cfo_out = summary.get("cfo") or {}
    lines += ["## 💰 CFO 经营报告 · Forecast + Portfolio", ""]
    cfo_md = cfo_out.get("markdown")
    if cfo_md:
        lines.append(_strip_h1(cfo_md))
    else:
        lines.append(f"_{cfo_out.get('error', '暂无 CFO 报告')}_")
    lines += ["", "---", ""]
    # Fleet Brain verdicts
    lines += ["## 2️⃣ 真实舰队判决 · Fleet Verdicts", ""]
    fleet_md = fleet_out.get("markdown")
    if fleet_md:
        lines.append(_strip_h1(fleet_md))
    else:
        lines.append(f"_{fleet_out.get('note', fleet_out.get('error', '暂无舰队判决'))}_")
    lines += ["", "---", ""]
    # Growth opportunities
    lines += ["## 3️⃣ 新游机会 · Growth", ""]
    growth_md = growth_out.get("markdown")
    if growth_md:
        lines.append(_strip_h1(growth_md))
    else:
        lines.append(f"_{growth_out.get('error', '暂无新游机会')}_")
    lines += ["", "---", ""]
    # Store publishing status (App Store Connect / Google Play)
    lines += ["## 4️⃣ 上架状态 · Store Status", ""]
    store_md = store_out.get("markdown")
    if store_md:
        lines.append(store_md)
    else:
        lines.append(f"_{store_out.get('note', store_out.get('error', '暂无上架状态'))}_")
    lines += ["", "---", ""]
    # Production readiness (per-app closed-testing 14-day clock)
    lines += ["## 5️⃣ Production Readiness · 待产状态", ""]
    prod_md = production_out.get("markdown")
    if prod_md:
        lines.append(_strip_h1(prod_md))
    else:
        lines.append(f"_{production_out.get('note', production_out.get('error', '暂无待产 App'))}_")
    lines += ["", "---", ""]
    # E13.5 Play Runtime audit trail (last 24h console operations)
    lines += ["## 6️⃣ Play Runtime · 发布运行时", ""]
    pr_md = play_runtime_out.get("markdown")
    if pr_md:
        lines.append(pr_md)
    else:
        lines.append(f"_{play_runtime_out.get('note', play_runtime_out.get('error', '暂无 Play 操作记录'))}_")
    lines += ["", "---", ""]
    # E13.5 Health: latest Vitals health board (healthy / watch / halt)
    lines += ["## 7️⃣ Vitals 健康看板 · Health Agent", ""]
    health_md = health_out.get("markdown")
    if health_md:
        lines.append(health_md)
    else:
        lines.append(f"_{health_out.get('note', health_out.get('error', '暂无健康看板'))}_")
    lines += ["", "---", ""]
    # E13.5 Review: latest review-intelligence board (crash/bug/complaint/
    # question/praise + reply status). Folded into the card (no push). Reads
    # only the local reviews.jsonl audit (written by the Review Agent).
    lines += ["## 8️⃣ 评论情报 · Review Agent", ""]
    review_md = review_out.get("markdown")
    if review_md:
        lines.append(review_md)
    else:
        lines.append(f"_{review_out.get('note', review_out.get('error', '暂无评论情报'))}_")
    lines += ["", "---", ""]

    # E13.5 Listing Experiment: latest ASO board (proposed / running / ended
    # + winner recommendations). Folded into the card (no push). Reads only
    # the local experiments.jsonl audit (written by the Experiment Agent).
    lines += ["## 9️⃣ ASO 实验 · Listing Experiment Agent", ""]
    experiment_md = experiment_out.get("markdown")
    if experiment_md:
        lines.append(experiment_md)
    else:
        lines.append(f"_{experiment_out.get('note', experiment_out.get('error', '暂无 ASO 实验'))}_")
    lines += ["", "---", ""]
    # E13.5 Tester Pool: persistent closed-testing pool + last invite status.
    # Folded into the card (no push). Reads only the local pool file + audit.
    lines += ["## 🔟 测试员池 · Tester Pool Agent", ""]
    tp_md = tester_pool_out.get("markdown")
    if tp_md:
        lines.append(tp_md)
    else:
        lines.append(f"_{tester_pool_out.get('note', tester_pool_out.get('error', '暂无测试员池'))}_")
    lines += ["", "---", ""]
    # E13.5 Play Ops: the unified daily fleet sweep (Health -> Release ->
    # Review -> Experiment -> Tester Pool) that auto-populates the Play
    # sections above. Folded into the card (no push of its own). SIMULATION by
    # default (zero network); shows which agents ran and whether any failed.
    lines += ["## 🌐 Play Ops 每日巡检 · Daily Sweep", ""]
    po_md = play_ops_out.get("markdown")
    if po_md:
        lines.append(po_md)
    else:
        lines.append(f"_{play_ops_out.get('error', 'Play Ops 巡检未运行')}_")
    lines += ["", "---", ""]
    lines += ["📎 完整明细见 outputs/daily_briefing/ 与 outputs/monetization_reports/"]
    return "\n".join(lines)


def run_all(account_ids: Optional[List[str]] = None,
            notify: bool = True,
            today: Optional[date] = None) -> Dict:
    start, end = _window(today)
    accounts = load_accounts()
    ids = account_ids or sorted(accounts.keys())

    agent = MonetizationIntelligenceAgent()
    # Analysis only — no per-account Feishu push. The unified morning digest
    # built below is the single card the operator receives each morning.
    results = [run_account(agent, a, start, end, notify=False) for a in ids]

    ok = [r for r in results if r["status"].startswith("OK")]
    fail = [r for r in results if not r["status"].startswith("OK")]
    summary = {
        "date": (today or date.today()).isoformat(),
        "window": {"start": start, "end": end},
        "accounts_total": len(ids), "ok": len(ok), "fail": len(fail),
        "results": results,
    }

    # Fleet Brain: per-app IAA verdicts (SCALE/KEEP/FIX/KILL) — the
    # fund-manager view of every live game. Folded into the digest (no push).
    # Reads the same fresh cached reports the live pull just wrote.
    summary["fleet"] = _run_fleet(ids, notify=False)
    # Growth: new-game market opportunities (mock + real-if-configured).
    # Folded into the digest (no push) so the operator gets one morning card.
    summary["growth"] = _run_growth(notify=False)
    # Store publishing status (App Store Connect / Google Play). Folded into
    # the digest. Dry-run safe by default; real calls only when the operator
    # opts in via LAUNCHFORGE_STORE_LIVE=1 after filling store credentials.
    summary["store"] = _run_store_status(notify=False)
    # Production readiness: per-app closed-testing 14-day clock. Folded into
    # the unified card (no push) so a fresh "ready to apply" badge lights up
    # in the morning digest when an app's 14-day clock hits zero.
    summary["production"] = _run_production_readiness(notify=False)
    # E13.5 Play Runtime: last-24h audit of all console operations. Folded
    # into the unified card (no push). Reads only the local JSONL audit log.
    summary["play_runtime"] = _run_play_runtime(notify=False)
    # E13.5 Health: latest Vitals health board (folded into the card, no push).
    # Reads only the local health.jsonl audit (written by the Health Agent).
    summary["health"] = _run_health(notify=False)
    # E13.5 Review: latest review-intelligence board (folded into the card,
    # no push). Reads only the local reviews.jsonl audit (written by the
    # Review Agent's run_daily).
    summary["review"] = _run_review(notify=False)
    # E13.5 Listing Experiment: latest ASO board (folded into the card, no
    # push). Reads only the local experiments.jsonl audit (written by the
    # Experiment Agent's run_daily).
    summary["experiment"] = _run_experiment(notify=False)
    # E13.5 Tester Pool: persistent closed-testing pool + last invite status
    # (folded into the card, no push). Reads only the local pool file + audit.
    summary["tester_pool"] = _run_tester_pool(notify=False)
    # E13.5 Play Ops: run the unified fleet sweep FIRST so the audit JSONLs it
    # writes are then read back by the section renderers (6-10) above. SIM by
    # default (zero network) — the morning automation never fires real writes.
    summary["play_ops"] = _run_play_ops(notify=False)
    # E16.1.x CFO business report on real MAX dumps (local files only).
    summary["cfo"] = _run_cfo_report()

    # ONE unified morning digest: revenue + fleet + growth + store + production
    # + health + play runtime + review + ASO experiment + tester pool + sweep.
    digest_md = _build_morning_digest(
        results, summary["fleet"], summary["growth"], summary["store"],
        summary["production"], summary["health"], summary["play_runtime"],
        summary["review"], summary["experiment"], summary["tester_pool"],
        summary["play_ops"],
        summary, start, end)
    summary["digest"] = {"notified": False, "notify_error": None,
                         "markdown": digest_md}

    if notify:
        try:
            from operation.optimizer.notify.feishu import send_markdown_card
            res = send_markdown_card(
                f"🌅 LaunchForge 每日全量晨报 {summary['date']}",
                digest_md, color="blue")
            summary["digest"]["notified"] = res is not None
        except Exception as exc:  # noqa: BLE001 — webhook missing / rate-limit
            summary["digest"]["notify_error"] = f"{type(exc).__name__}: {exc}"

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{summary['date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    summary["summary_path"] = path

    # Failures must be loud: push a plain-text alert (best-effort) when an
    # account analysis failed OR the unified card itself failed to push, so a
    # missing card is never silent.
    if (fail or summary["digest"]["notify_error"]) and notify:
        try:
            from operation.optimizer.notify.feishu import FeishuNotifier
            lines = [f"⚠️ IAA 每日全量晨报异常 {summary['date']}"]
            lines += [f"- {r['account']}: {r['error']}" for r in fail]
            if summary["digest"]["notify_error"]:
                lines.append(
                    f"- 合并晨报卡片推送失败：{summary['digest']['notify_error']}")
            FeishuNotifier(None).send_text("\n".join(lines))
        except Exception:  # noqa: BLE001
            pass
    return summary


def main() -> int:
    args = [a for a in sys.argv[1:]]
    notify = "--no-notify" not in args
    ids = [a for a in args if not a.startswith("--")] or None
    s = run_all(ids, notify=notify)
    print(f"window {s['window']['start']} ~ {s['window']['end']}")
    for r in s["results"]:
        if r["status"].startswith("OK"):
            tag = "OK " if r["status"] == "OK" else "CACHE"
            print(f"  {r['account']}  {tag}  {r['seconds']}s  "
                  f"H{r['health']} O{r['opportunity']} R{r['risk']}  "
                  f"rev ${r['revenue']}  actions {r['actions']}  "
                  f"EW {r['early_warnings']}  notified={r['notified']}")
        else:
            print(f"  {r['account']}  FAIL {r['seconds']}s  {r['error']}")
    fl = s.get("fleet", {})
    if fl.get("status") == "OK":
        print(f"  🚢 fleet: {fl['games']} games / {fl['verdicts']} verdicts "
              f"-> {fl['path']}")
    elif fl:
        print(f"  🚢 fleet: {fl.get('status')} "
              f"{fl.get('error', fl.get('note', ''))}")
    gr = s.get("growth", {})
    print(f"  🎮 growth: {gr.get('status')} "
          f"opportunities={gr.get('opportunities')}")
    st = s.get("store", {})
    print(f"  🛒 store: {st.get('status')} "
          f"games={st.get('games')} "
          f"real_api_called={st.get('real_api_called', False)}")
    pd = s.get("production", {})
    print(f"  🚦 production-readiness: {pd.get('status')} "
          f"tracked={pd.get('tracked_packages', 0)} "
          f"ready={pd.get('ready_packages', 0)} "
          f"testers={pd.get('tester_count', 0)} "
          f"pool={pd.get('pool_size', 0)}/"
          f"{pd.get('promote_count', 0)}🚀")
    hl = s.get("health", {})
    print(f"  🩺 health: {hl.get('status')} "
          f"packages={hl.get('count', 0)} "
          f"critical(halt)={hl.get('critical', 0)}")
    rv = s.get("review", {})
    print(f"  💬 review: {rv.get('status')} "
          f"packages={rv.get('count', 0)} "
          f"needs_reply={rv.get('needs_reply', 0)} "
          f"replied={rv.get('replied', 0)}")
    ex = s.get("experiment", {})
    print(f"  🧪 aso: {ex.get('status')} "
          f"packages={ex.get('count', 0)} "
          f"running={ex.get('running', 0)} "
          f"ended={ex.get('ended', 0)} "
          f"winner_rec={ex.get('winner', 0)}")
    tp = s.get("tester_pool", {})
    print(f"  🧪 tester-pool: {tp.get('status')} "
          f"pool={tp.get('count', 0)} "
          f"meets_min={tp.get('meets_minimum', False)}")
    po = s.get("play_ops", {})
    print(f"  🌐 play-ops: {po.get('status')} "
          f"{po.get('agents_ok', 0)}/{po.get('agents_total', 0)} "
          f"agents · mode={po.get('mode')} "
          f"real_api={po.get('real_api_called', False)}")
    dg = s.get("digest", {})
    if dg.get("notified"):
        print("  🌅 全量晨报：已推送 1 张合并卡（营收+舰队+新游）")
    elif dg.get("notify_error"):
        print(f"  🌅 全量晨报：推送失败 {dg.get('notify_error')}")
    else:
        print("  🌅 全量晨报：未推送（--no-notify）")
    print(f"summary -> {s['summary_path']}")
    return 0 if s["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
