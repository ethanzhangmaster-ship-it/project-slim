"""
E15.2.5 — MonetizationIntelligenceAgent.

Daily entrypoint: pull MAX Report API rows for an account (or accept
cached rows), run MonetizationReportGenerator, persist md + json.

Three-phase rollout contract:
  Phase 1 (now): auto-diagnose -> MONETIZATION ACTION REPORT (this module)
  Phase 2: apply-checklist + human Approve
  Phase 3: platform API write when MAX opens expanded-targeting writes
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from operation.optimizer.intel_models import (
    MonetizationDailyReport, fnum,
)
from operation.optimizer.reports.report_generator import MonetizationReportGenerator

REPORT_URL = "https://r.applovin.com/maxReport"
COLUMNS = ("day,application,ad_format,country,network,impressions,"
           "attempts,responses,ecpm,estimated_revenue")


def _urlopen_json(url: str, timeout: int = 30, retries: int = 3) -> dict:
    """urlopen with retry/backoff. MAX Report API occasionally drops the
    TLS connection mid-stream (SSL: UNEXPECTED_EOF_WHILE_READING), a transient
    blip that must not fail the whole daily run. Retry a few times."""
    import time as _time
    last: Exception = RuntimeError("no attempts made")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url), timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # noqa: BLE001 — transient network only
            last = exc
            if attempt < retries:
                _time.sleep(1.5 * attempt)
    raise last


class MonetizationIntelligenceAgent:
    def __init__(self, account_loader=None) -> None:
        """account_loader: callable(account_id) -> {"report_key": ...}.
        Defaults to the persistent multi-account store."""
        if account_loader is None:
            from operation.providers.live.max.accounts import get_account
            account_loader = get_account
        self._get_account = account_loader
        self.generator = MonetizationReportGenerator()

    # ------------------------------------------------------------------ #
    def pull_rows(self, account_id: str, start: str, end: str,
                  timeout: int = 30) -> List[dict]:
        """Pull day-by-day to avoid the 5000-row single-call truncation."""
        acct = self._get_account(account_id)
        if not acct or not acct.get("report_key"):
            raise ValueError(f"{account_id}: missing report_key in account store")
        from datetime import date, timedelta
        d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
        rows: List[dict] = []
        d = d0
        while d <= d1:
            day = d.isoformat()
            offset = 0
            while True:                 # offset pagination within one day
                params = {"api_key": acct["report_key"], "start": day,
                          "end": day, "format": "json", "limit": 5000,
                          "offset": offset, "columns": COLUMNS}
                url = f"{REPORT_URL}?{urllib.parse.urlencode(params)}"
                data = _urlopen_json(url, timeout=timeout)
                page = data.get("results", [])
                rows.extend(page)
                if len(page) < 5000:
                    break
                offset += 5000
                if offset > 200000:     # hard safety stop
                    raise RuntimeError(f"{account_id} {day}: runaway pagination")
            d += timedelta(days=1)
        return rows

    # ------------------------------------------------------------------ #
    def run(self, account_id: str, start: str, end: str,
            rows: Optional[List[dict]] = None,
            report_date: Optional[str] = None,
            out_dir: str = "outputs/monetization_reports",
            save: bool = True,
            cache_rows: bool = False,
            history_revenue: Optional[Dict[str, float]] = None,
            network_unique_geos: Optional[Dict[str, List[str]]] = None,
            user_metrics: Optional[object] = None,
            auto_history: bool = True,
            history_lookback_days: int = 30,
            experiments_dir: str = "outputs/experiments",
            enable_experiments: bool = True,
            config_dir: str = "outputs/config_recommendations",
            enable_config_recommender: bool = True,
            enable_ecpm_prediction: bool = True) -> Dict:
        """Full daily cycle. Pass `rows` to skip the live pull (offline/replay).

        On a live pull (rows is None) and when kill-switch protection data is
        not supplied, a single wider 30d pull is made to build:
          history_revenue       – per-network revenue over the lookback
          network_unique_geos   – countries each network is the primary filler in
        These feed ZombieNetworkDetector so a once-valuable network is
        downgraded to quarantine (watch-only) instead of a blind disable.
        """
        if rows is None:
            if (auto_history and history_revenue is None
                    and network_unique_geos is None):
                hstart = (date.fromisoformat(end)
                          - timedelta(days=max(history_lookback_days, 1) - 1)
                          ).isoformat()
                wide = self.pull_rows(account_id, hstart, end)
                hist = self._aggregate_history(wide)
                history_revenue = hist["history_revenue"]
                network_unique_geos = hist["network_unique_geos"]
                rows = [r for r in wide if start <= str(r.get("day", "")) <= end]
            else:
                rows = self.pull_rows(account_id, start, end)
        report: MonetizationDailyReport = self.generator.generate(
            account=account_id, rows=rows,
            period_start=start, period_end=end, report_date=report_date,
            history_revenue=history_revenue,
            network_unique_geos=network_unique_geos,
            user_metrics=user_metrics)
        # E15.2.6.2 — DAU truth + ARPDAU guardrail activation.
        # When a DAU source is available (operator drop-in today; Adjust/Firebase
        # later), derive ARPDAU = MAX revenue / DAU and persist it to the
        # drop-in history so tomorrow's run has a real guardrail baseline.
        self._finalize_user_metrics(report, account_id)
        # E15.2.5+: Experiment & Verification Layer — verify open experiments
        # against this report and propose new ones from Experiment-layer
        # actions. Zero MAX writes; the operator applies changes manually.
        if enable_experiments:
            report.experiments = self._run_experiments(
                report, experiments_dir, rows=rows)
        # E15.2.6 — IAA Growth Report (result-driven daily view).
        # Builds the single-KPI (Revenue/DAU) summary the operator reads,
        # and persists a prior-revenue snapshot for day-over-day growth.
        # DAU stays "pending" until Adjust key is wired (user_metrics.dau).
        from operation.optimizer.reports.growth_report import (
            build_growth_report, render_growth_markdown,
            load_prior_revenue, save_prior_revenue,
        )
        from operation.optimizer.experiments.experiment_store import (
            ExperimentStore,
        )
        _dau = getattr(user_metrics, "dau", None) if user_metrics else None
        if _dau is None:
            _dau = (report.user_metrics or {}).get("dau")
        _prior = load_prior_revenue(account_id)
        _gr = build_growth_report(
            account_id, report, ExperimentStore(experiments_dir),
            dau=_dau, prior_revenue=_prior)
        report.growth_report = _gr
        report.sections["growth"] = render_growth_markdown(_gr)
        if save:
            save_prior_revenue(account_id, report.revenue, report.date)
            # E15.2.7+ — persist the raw windowed rows so downstream readers
            # (fleet_bridge per-app verdicts, _replay_cache fallback) consume
            # the SAME fresh window this morning's card was built from.
            # Best-effort: a cache write must never fail the analysis.
            if cache_rows:
                try:
                    os.makedirs("data", exist_ok=True)
                    with open(os.path.join(
                            "data", f"{account_id}_report.json"),
                            "w", encoding="utf-8") as _fh:
                        json.dump({"account": account_id, "start": start,
                                   "end": end, "rows": rows},
                                  _fh, ensure_ascii=False)
                except (OSError, ValueError):
                    pass
        # E15.2.6 — Auto-Executor decision layer: tier every proposed action
        # AUTO / APPROVAL / OBSERVE and emit a one-click apply checklist.
        # AI decides the risk; the human still applies in MAX (write-blocked).
        from operation.optimizer.auto_executor import from_report as _ae_from
        report.auto_executor = _ae_from(report)
        # E15.2.5 Autonomous IAA — Target MAX Config recommender (P0):
        # per-(app, geo, format) network ranking + floor ranges. The operator
        # applies the target config manually; MAX API cannot write waterfalls.
        if enable_config_recommender:
            from operation.optimizer.config_recommender import ConfigRecommender
            cr = ConfigRecommender()
            rec = cr.recommend(rows, account_id, start, end,
                               overall_blend_ecpm=report.blended_ecpm,
                               today=report.date)
            report.config_recommendations = [rec.to_dict()]
            if save:
                cp = cr.save(rec, config_dir)
                cpaths = {"config_markdown": cp.get("markdown"),
                          "config_json": cp.get("json")}
            else:
                cpaths = {}
        else:
            cpaths = {}
        # E15.2.5 Autonomous IAA (increment 2) — eCPM Prediction (module 6):
        # forecast next-period eCPM per (app, geo, format, network) from the
        # daily series already present in the report rows. The agent becomes
        # predictive (early warnings on downtrends) without any MAX writes.
        if enable_ecpm_prediction:
            from operation.optimizer.prediction import EcmpPredictor
            rec = EcmpPredictor().predict_account(
                rows, account_id, start, end, today=report.date)
            report.ecpm_forecasts = [rec.to_dict()]
        paths = self.generator.save(report, out_dir) if save else {}
        paths.update(cpaths)
        return {"report": report, "paths": paths,
                "rows_analyzed": len(rows),
                "phase": 1, "max_writes": 0}

    # ------------------------------------------------------------------ #
    def _finalize_user_metrics(self, report: MonetizationDailyReport,
                               account_id: str) -> None:
        """E15.2.6.2: with a DAU source present, derive ARPDAU from MAX
        revenue and persist it for tomorrow's guardrail baseline. Mutates
        report.user_metrics in place (it is already a dict from generate())."""
        um = getattr(report, "user_metrics", None)
        if not isinstance(um, dict):
            return
        dau = um.get("dau")
        if not dau or dau <= 0:
            return
        rev = float(report.revenue or 0.0)
        if rev > 0 and not (um.get("arpdau") or 0.0):
            um["arpdau"] = round(rev / dau, 5)
        um["available"] = True
        um.setdefault("source", "manual_dropin")
        if rev > 0:
            from operation.optimizer.user_metrics import persist_arpdau
            persist_arpdau(account_id, report.date, int(dau),
                           float(um.get("arpdau") or 0.0), rev)

    # ------------------------------------------------------------------ #
    def _run_experiments(self, report: MonetizationDailyReport,
                         experiments_dir: str,
                         rows: Optional[List[dict]] = None
                         ) -> List[Dict[str, Any]]:
        """Verify active experiments, propose new ones, and — for applied
        experiments — measure real revenue impact, select winners and write
        OptimizationMemory (Outcome Learning). Returns the full experiment
        list (dicts) for the account, for report + card rendering."""
        from operation.optimizer.experiments.experiment_store import ExperimentStore
        from operation.optimizer.experiments.verification_engine import VerificationEngine
        store = ExperimentStore(experiments_dir)
        engine = VerificationEngine()
        today = report.date
        active = store.active(report.account)
        verifications = [engine.verify(report, exp, today=today) for exp in active]
        if verifications:
            store.apply_verifications(report.account, verifications)
        created = store.propose_from_validated(report, today=today)
        # Outcome Learning: attach precedent priors to new hypotheses
        from operation.optimizer.experiments.optimization_memory import (
            OptimizationMemory)
        memory = OptimizationMemory(
            path=os.path.join(experiments_dir, "optimization_memory.jsonl"))
        if created:
            defs = store.load(report.account)
            touched = False
            for exp in created:
                note = memory.prior_note(exp.action_type, exp.target)
                if note and exp.exp_id in defs:
                    defs[exp.exp_id].params["prior"] = note
                    touched = True
            if touched:
                store.save(report.account, defs)
        # Outcome Learning: measure applied experiments → winner → memory
        if rows:
            self._learn_outcomes(store, memory, report.account, rows, today)
        return [d.to_dict() for d in store.load(report.account).values()]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _learn_outcomes(store, memory, account: str,
                        rows: List[dict], today: str) -> None:
        """For every APPLIED-but-undecided experiment: before/after impact
        (diff-in-diff vs account drift) → KEEP/ROLLBACK verdict → persist
        the measured outcome to OptimizationMemory. Read-only on MAX."""
        from operation.optimizer.experiments.impact import ImpactMeasurer
        from operation.optimizer.experiments.winner_selector import WinnerSelector
        from operation.optimizer.experiments.experiment_models import (
            MEMORIZED, ROLLBACK, WINNER)
        measurer, selector = ImpactMeasurer(), WinnerSelector()
        defs = store.load(account)
        touched = False
        for exp in defs.values():
            if not exp.applied_at or exp.decision:
                continue
            m = measurer.measure(rows, exp.exp_id, exp.target, exp.applied_at)
            d = selector.decide(m, guardrail=exp.last_arpdau_guardrail
                                or "pending")
            exp.impact = {**m.to_dict(), "verdict": d.verdict,
                          "confidence": round(d.confidence, 2)}
            touched = True
            if not d.decision:          # OBSERVING — no verdict yet
                exp.result_note = d.note
                continue
            exp.decision = d.decision
            exp.result_note = d.note
            exp.resolved_at = today
            memory.record(
                account=account, action=exp.action_type, target=exp.target,
                net_impact_pct=d.net_impact_pct,
                guardrail=exp.last_arpdau_guardrail or "pending",
                decision=d.decision, confidence=d.confidence,
                applied_at=exp.applied_at, decided_at=today)
            exp.memorized_at = today
            if d.verdict == ROLLBACK:
                exp.status = ROLLBACK
            elif d.verdict == WINNER:
                exp.status = WINNER      # winner, outcome memorized
            else:
                exp.status = MEMORIZED   # inconclusive-keep, memorized
        if touched:
            store.save(account, defs)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _aggregate_history(wide_rows: List[dict]) -> Dict[str, object]:
        """Roll a wide (>=30d) MAX Report pull into kill-switch context."""
        rev: Dict[str, float] = {}
        geos: Dict[str, set] = {}
        for r in wide_rows:
            net = r.get("network")
            if not net:
                continue
            rev[net] = rev.get(net, 0.0) + fnum(r.get("estimated_revenue"), 0.0)
            geo = (r.get("country") or "").lower()
            if geo:
                geos.setdefault(net, set()).add(geo)
        return {"history_revenue": rev,
                "network_unique_geos": {k: sorted(v) for k, v in geos.items()}}

    # ------------------------------------------------------------------ #
    def run_and_notify(self, account_id: str, start: str, end: str,
                       rows: Optional[List[dict]] = None,
                       report_date: Optional[str] = None,
                       out_dir: str = "outputs/monetization_reports",
                       webhook: Optional[str] = None,
                       ledger_dir: str = "outputs/action_ledger",
                       history_revenue: Optional[Dict[str, float]] = None,
                       network_unique_geos: Optional[Dict[str, List[str]]] = None,
                       user_metrics: Optional[object] = None,
                       auto_history: bool = True,
                       history_lookback_days: int = 30,
                       save: bool = True,
                       cache_rows: bool = False) -> Dict:
        """Full closed loop:
        pull -> analyze -> report -> reconcile action ledger -> push Feishu.

        The ledger turns recommendations into a loop: actions that stop
        firing on the next run are auto-marked RESOLVED (applied/healed)
        and announced in the group; stale open actions get reminders.
        """
        out = self.run(account_id, start, end, rows=rows,
                       report_date=report_date, out_dir=out_dir,
                       history_revenue=history_revenue,
                       network_unique_geos=network_unique_geos,
                       user_metrics=user_metrics,
                       auto_history=auto_history,
                       history_lookback_days=history_lookback_days,
                       save=save, cache_rows=cache_rows)
        report = out["report"]

        from operation.optimizer.loop.action_ledger import ActionLedger
        loop_summary = ActionLedger(ledger_dir).reconcile(report)
        out["loop"] = loop_summary

        from operation.optimizer.notify.feishu import FeishuNotifier
        notifier = FeishuNotifier(webhook)          # falls back to notify.json
        # Push failure (rate limit, network blip) must NOT invalidate the
        # analysis: artifacts are already on disk. Record and continue.
        try:
            out["notify"] = notifier.send_report(report, loop_summary)
        except Exception as exc:  # noqa: BLE001 — notify is best-effort
            out["notify"] = None
            out["notify_error"] = f"{type(exc).__name__}: {exc}"
        return out
