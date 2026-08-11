"""
E15.2.5 — MonetizationReportGenerator.

Turns raw MAX Report API rows into the daily IAA Monetization Report:
totals -> run all intelligence analyzers -> health score -> prioritized
Action list -> markdown + json artifacts.

Phase 1 contract: every action is a recommendation
(requires_manual_apply=True); nothing writes to MAX.
"""
from __future__ import annotations

import json
import os
from datetime import date as _date
from typing import Dict, List, Optional

from operation.optimizer.intel_models import (
    ActionItem, IntelSignal, MonetizationDailyReport, SegmentStat,
)
from operation.optimizer.analyzers.aggregate import aggregate, totals
from operation.optimizer.analyzers.zombie_network import ZombieNetworkDetector
from operation.optimizer.analyzers.hidden_winner import HiddenWinnerDetector
from operation.optimizer.analyzers.waterfall_efficiency import WaterfallEfficiencyAnalyzer
from operation.optimizer.analyzers.bid_floor_advisor import BidFloorAdvisor
from operation.optimizer.analyzers.revenue_concentration import RevenueConcentrationAnalyzer
from operation.optimizer.analyzers.geo_opportunity import GeoOpportunityAnalyzer
from operation.optimizer.scoring import HealthScorer, OpportunityScorer, RiskScorer
from operation.optimizer.validator import ActionValidator, Layer
from operation.optimizer.user_metrics import UserMetrics, UserMetricsService


class MonetizationReportGenerator:
    """Deterministic report pipeline — no LLM, no writes."""

    def __init__(self, user_metrics_service: Optional[UserMetricsService] = None) -> None:
        # user-side guardrail source; defaults to a PENDING service (no key)
        self.user_metrics_service = user_metrics_service or UserMetricsService()
        self.zombie = ZombieNetworkDetector()
        self.winner = HiddenWinnerDetector()
        self.waterfall = WaterfallEfficiencyAnalyzer()
        self.floor = BidFloorAdvisor()
        self.concentration = RevenueConcentrationAnalyzer()
        self.geo = GeoOpportunityAnalyzer()
        self.health_scorer = HealthScorer()
        self.opportunity_scorer = OpportunityScorer()
        self.risk_scorer = RiskScorer()
        self.action_validator = ActionValidator()

    # ------------------------------------------------------------------ #
    def generate(self, account: str, rows: List[dict],
                 period_start: str, period_end: str,
                 report_date: Optional[str] = None,
                 history_revenue: Optional[Dict[str, float]] = None,
                 network_unique_geos: Optional[Dict[str, List[str]]] = None,
                 user_metrics: Optional[UserMetrics] = None,
                 ) -> MonetizationDailyReport:
        by_net = aggregate(rows, "network")
        by_app = aggregate(rows, "application")
        by_cc = aggregate(rows, "country")
        by_fmt = aggregate(rows, "ad_format")
        total = totals(by_net)
        blended = total.ecpm
        depth = total.attempts / max(total.impressions, 1)

        signals: List[IntelSignal] = []
        # kill-switch protection: history_revenue / network_unique_geos are
        # supplied by the live agent (30d lookback); None -> no protection.
        signals += self.zombie.analyze(by_net,
                                       history_revenue=history_revenue,
                                       network_unique_geos=network_unique_geos)
        signals += self.winner.analyze(by_net, blended, total.impressions)
        signals += self.waterfall.analyze(total, {"network": by_net,
                                                  "ad_format": by_fmt})
        signals += self.floor.analyze(by_net, blended, total.impressions)
        signals += self.concentration.analyze({"application": by_app,
                                               "network": by_net,
                                               "country": by_cc})
        signals += self.geo.analyze(by_cc, blended)

        # E15.2.5 calibration: three orthogonal scores instead of one
        # misleading "health" number.
        health = self.health_scorer.score(total, by_net, by_app, blended, signals)
        opportunity = self.opportunity_scorer.score(total, by_net, blended, signals)
        risk = self.risk_scorer.score(by_app, by_net, by_cc)

        actions = self._actions(signals)
        # classify each action into Safe / Experiment / Observe with an
        # execution-value score (the "is it worth doing?" layer)
        validated = self.action_validator.classify(actions)
        validated_dicts = [v.to_dict() for v in validated]
        risks = [s.reason for s in signals
                 if s.rule == "revenue_concentration" and s.severity == "critical"]

        # user-side guardrail (ARPDAU / ads-per-user); PENDING if no key
        um = user_metrics or self.user_metrics_service.fetch(
            account, period_start, period_end)

        report = MonetizationDailyReport(
            account=account,
            date=report_date or _date.today().isoformat(),
            period_start=period_start, period_end=period_end,
            revenue=total.revenue, impressions=total.impressions,
            attempts=total.attempts, blended_ecpm=blended,
            waterfall_depth=depth,
            health_score=health.score, health_grade=health.grade,
            opportunity_score=opportunity.score, opportunity_grade=opportunity.grade,
            risk_score=risk.score, risk_grade=risk.grade,
            scores={"health": health.to_dict(),
                    "opportunity": opportunity.to_dict(),
                    "risk": risk.to_dict()},
            signals=signals, actions=actions,
            validated_actions=validated_dicts,
            user_metrics=um.to_dict(), risks=risks,
            sections={"by_network": by_net, "by_app": by_app,
                      "by_country": by_cc, "by_format": by_fmt},
        )
        return report

    # ------------------------------------------------------------------ #
    def _actions(self, signals: List[IntelSignal]) -> List[ActionItem]:
        actions: List[ActionItem] = []
        for s in signals:
            if s.rule == "zombie_network" and s.action == "disable_network":
                actions.append(ActionItem(
                    priority="P0", title=f"Disable {s.target}",
                    action="disable_network", target=s.target,
                    expected_impact=(f"free {s.metrics['attempts']:,} requests "
                                     f"(revenue loss < ${s.metrics['revenue']:.2f})"),
                    source_rule=s.rule, confidence=s.confidence))
            elif s.rule == "zombie_network" and s.action == "quarantine_network":
                # protected candidate — monitor before killing (kill-switch guard)
                actions.append(ActionItem(
                    priority="P2", title=f"Quarantine & watch {s.target} (7d)",
                    action="quarantine_network", target=s.target,
                    expected_impact=(f"looks zombie but protected "
                                     f"({s.metrics.get('protection', 'historical value')}) "
                                     f"— confirm 7d before disabling"),
                    source_rule=s.rule, confidence=s.confidence))
            elif s.rule == "hidden_winner":
                # upgraded to P1 (user): a starved high-eCPM network is
                # real recoverable revenue, second only to killing zombies.
                cr = s.metrics.get("revenue_capture_rate", 0.0)
                actions.append(ActionItem(
                    priority="P1", title=f"Increase bid opportunity for {s.target}",
                    action="increase_bid_opportunity", target=s.target,
                    expected_impact=(f"capturing only {cr:.0%} of its eCPM-implied "
                                     f"potential at eCPM ${s.metrics['ecpm']:.2f} "
                                     f"— raise auction exposure"),
                    source_rule=s.rule, confidence=s.confidence))
            elif s.rule == "bid_floor":
                rng = s.metrics.get("recommended_floor_range",
                                    [s.metrics["recommended_min_floor"]] * 2)
                ctype = s.metrics.get("constraint_type", "floor")
                actions.append(ActionItem(
                    priority="P2",
                    title=(f"Raise {ctype.replace('_', ' ')} on {s.target} "
                           f"to ${rng[0]:.2f}-${rng[1]:.2f}"),
                    action="adjust_bid_constraint", target=s.target,
                    expected_impact="cut lowest-value backfill impressions; watch fill",
                    source_rule=s.rule, confidence=s.confidence))
            elif s.rule == "revenue_concentration" and s.severity == "critical":
                if s.action == "monitor":
                    # country concentration — UA scope, never diversify here
                    actions.append(ActionItem(
                        priority="P3", title=f"Monitor concentration: {s.target}",
                        action="monitor", target=s.target,
                        expected_impact=("geo concentration — audience risk; "
                                         "hand to Growth OS, monitor only"),
                        source_rule=s.rule, confidence=s.confidence))
                else:
                    actions.append(ActionItem(
                        priority="P3", title=f"Diversify: {s.target}",
                        action="diversify", target=s.target,
                        expected_impact="reduce single-point-of-failure revenue risk",
                        source_rule=s.rule, confidence=s.confidence))
            elif s.rule == "geo_opportunity":
                actions.append(ActionItem(
                    priority="P3", title=f"UA opportunity: geo {s.target}",
                    action="handoff_ua", target=s.target,
                    expected_impact=(f"eCPM ${s.metrics['ecpm']:.2f} "
                                     f"— hand to Growth OS (not a monetization action)"),
                    source_rule=s.rule, confidence=s.confidence))
        order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        actions.sort(key=lambda a: (order[a.priority], -a.confidence))
        return actions

    # ------------------------------------------------------------------ #
    def render_markdown(self, r: MonetizationDailyReport) -> str:
        icon = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🔵"}
        lines = [
            f"# IAA Monetization Report — {r.account}",
            "",
            f"**Date:** {r.date}  |  **Period:** {r.period_start} → {r.period_end}",
            "",
            f"**Revenue:** ${r.revenue:.2f}  |  **Impressions:** {r.impressions:,}"
            f"  |  **Blended eCPM:** ${r.blended_ecpm:.2f}"
            f"  |  **Waterfall depth:** {r.waterfall_depth:.1f} att/imp",
            "",
            "## 🎯 Scorecard",
            "",
            "| Score | Value | Grade | Reads as |",
            "|---|---|---|---|",
            f"| 💚 Health | **{r.health_score}/100** | {r.health_grade} "
            f"| current monetization efficiency |",
            f"| 🚀 Opportunity | **{r.opportunity_score}/100** | {r.opportunity_grade} "
            f"| recoverable in-app upside |",
            f"| ⚠️ Risk | **{r.risk_score}/100** | {r.risk_grade} "
            f"| revenue fragility (concentration) |",
            "",
            (f"> Health {r.health_score} is a *state*, not a verdict — "
             f"Opportunity {r.opportunity_score} ({r.opportunity_grade}) is the headroom. "
             f"A low-health / high-opportunity account is under-optimized, not lost."),
            "",
        ]
        # per-score dimension breakdown
        for kind in ("health", "opportunity", "risk"):
            sc = r.scores.get(kind)
            if not sc:
                continue
            lines += [f"<details><summary>{sc['headline']}</summary>", ""]
            for d in sc["dimensions"]:
                lines.append(f"- **{d['name']}**: {d['value']:.0f}/100 "
                             f"(w{d['weight']:.2f}) — {d['detail']}")
            lines += ["", "</details>", ""]

        # ---- user-side guardrail (ARPDAU) -------------------------------
        um = r.user_metrics or {}
        lines += ["## 🛡️ User Guardrail (ARPDAU)", ""]
        if not um.get("available"):
            lines += [
                f"_Pending — {um.get('note', 'no user-side data source configured')}._",
                "",
                "> Success = revenue up **without** raising ad load per user. "
                "Wire Adjust/Firebase to activate this guardrail before any "
                "Experiment-layer rollout.",
                "",
            ]
        else:
            lines += [
                f"- **ARPDAU:** ${um.get('arpdau', 0):.4f}  (DAU {um.get('dau', 0):,})",
                f"- **Ads/user:** {um.get('ads_per_user', 0):.2f}  ·  "
                f"Rewarded/user {um.get('rewarded_per_user', 0):.2f}  ·  "
                f"Interstitial/user {um.get('interstitial_per_user', 0):.2f}",
                f"- Source: `{um.get('source')}`",
                "",
            ]

        # ---- three execution layers (worth-executing decision) ----------
        layer_meta = [
            ("safe", "🔥 Execute Today", "Safe, reversible, high-confidence — auto-execute candidates"),
            ("experiment", "🧪 Experiment First", "Real revenue/fill impact — validate with A/B"),
            ("observe", "👀 Monitor / Hand-off", "Advisory or out-of-scope — watch only"),
        ]
        grouped: Dict[str, list] = {"safe": [], "experiment": [], "observe": []}
        for v in r.validated_actions:
            grouped.get(v.get("layer", "observe"), grouped["observe"]).append(v)

        if not r.validated_actions:
            lines += ["## 🔥 Actions Today", "", "_No actions — account healthy._", ""]
        for key, heading, blurb in layer_meta:
            items = grouped[key]
            if not items:
                continue
            lines += [f"## {heading}", "", f"_{blurb}_", ""]
            for i, v in enumerate(items, 1):
                manual = " *(manual apply in MAX dashboard)*" if v.get("requires_manual_apply") else ""
                lines += [
                    f"**{i}. {icon.get(v['priority'], '')} [{v['priority']}] {v['title']}**{manual}",
                    f"   - Impact: {v['expected_impact']}",
                    f"   - Value score: {v['value_score']:.2f}  ·  "
                    f"conf {v['factors']['confidence']:.0%} · "
                    f"safety {v['factors']['safety']:.0%} · "
                    f"reversible {v['factors']['reversibility']:.0%}",
                    f"   - Why here: {v['rationale']}  ·  rule: `{v['source_rule']}`",
                    "",
                ]
        # ---- experiment & verification layer (full lifecycle) ---------
        if r.experiments:
            lines += ["## 🧪 A/B Experiments (lifecycle: PROPOSED → APPLIED → "
                      "OBSERVED → WINNER/ROLLBACK → MEMORIZED)", ""]
            lines += ["_Every opportunity is a formal A/B test: **A** = current "
                      "state, **B** = proposed change. The expected metric is "
                      "**Revenue/DAU**; the hypothesized lift is confirmed by "
                      "post-apply diff-in-diff, never assumed._", ""]
            _EXP_ICON = {"ACTIVE": "🧪", "SUCCESS": "✅", "FAIL": "❌",
                         "PROPOSED": "🆕", "INCONCLUSIVE": "❓",
                         "ARCHIVED": "🗄️", "APPLIED": "🔧",
                         "WINNER": "🏆", "ROLLBACK": "↩️",
                         "MEMORIZED": "🧠"}
            for e in r.experiments:
                st = e.get("status", "PROPOSED")
                icon = _EXP_ICON.get(st, "•")
                guard = e.get("last_arpdau_guardrail") or "n/a"
                delta = e.get("last_arpdau_delta_pct")
                gtxt = f" · ARPDAU guardrail: {guard}"
                if delta is not None:
                    gtxt += f" ({delta:+.1f}%)"
                lift = e.get("expected_lift_pct")
                lift_txt = (f"{lift:+.1f}%" if isinstance(lift, (int, float))
                            else "—")
                kind = e.get("ab_kind", "revenue")
                kind_tag = "" if kind == "revenue" else " · 🛡️ risk-hedge"
                lines += [
                    f"**{icon} [{st}] {e.get('action_type')} → {e.get('target')}**",
                    f"   - 🎯 Expected: **{e.get('expected_metric', 'revenue_per_dau')} "
                    f"lift {lift_txt}** (hypothesized, A/B-verified){kind_tag}",
                    f"   - A (control): {e.get('variant_a', '')}",
                    f"   - B (variant): {e.get('variant_b', '')}",
                    f"   - Hypothesis: {e.get('hypothesis', '')}",
                ]
                prior = (e.get("params") or {}).get("prior")
                if prior:
                    lines += [f"   - 🧠 {prior}"]
                imp = e.get("impact") or {}
                if e.get("applied_at"):
                    ni = imp.get("net_impact_pct")
                    itxt = (f"applied {e['applied_at']} · "
                            f"${imp.get('before_rev_per_day', 0):.2f}/d → "
                            f"${imp.get('after_rev_per_day', 0):.2f}/d")
                    if isinstance(ni, (int, float)):
                        itxt += (f" · net impact **{ni:+.1f}%/d** "
                                 f"(vs account drift) · verdict "
                                 f"{imp.get('verdict', 'OBSERVING')}")
                    dec = e.get("decision")
                    if dec:
                        itxt += f" · decision **{dec}**"
                    lines += [f"   - 💰 Outcome: {itxt}"]
                lines += [
                    f"   - {e.get('result_note', '')}{gtxt}",
                    "",
                ]
            lines += ["_Apply in MAX dashboard, then anchor with: "
                      "`python operation/optimizer/experiments/cli.py "
                      "apply <ACCT> <exp_id>` — impact is measured "
                      "automatically on the next daily run._", ""]

        # ---- target MAX config (recommendation-only) ------------------
        if r.config_recommendations:
            rec = r.config_recommendations[0]
            summ = rec.get("summary", {})
            lines += ["## 🎛 Target MAX Config (recommendation-only)", "",
                      f"_Segments analyzed: {summ.get('segments')} · "
                      f"demote candidates: {summ.get('demote_candidates')} · "
                      f"floor suggestions: {summ.get('floor_suggestions')}_",
                      "",
                      "> MAX Management API cannot write expanded-targeting "
                      "waterfalls — apply this target config manually in the "
                      "MAX dashboard, then the Experiment Layer verifies impact.",
                      ""]
            demote: Dict[str, int] = {}
            floor: Dict[str, List[float]] = {}
            for seg in rec.get("segments", []):
                for n in seg.get("demote_candidates", []):
                    demote[n] = demote.get(n, 0) + 1
                for n, fl in seg.get("floor_suggestions", {}).items():
                    floor[n] = fl.get("recommended_floor_range", [])
            if demote:
                lines += ["**Demote / raise floor (across segments):**", ""]
                for n in sorted(demote, key=lambda x: -demote[x]):
                    fr = floor.get(n)
                    ftag = (f" → floor ${fr[0]:.2f}-${fr[1]:.2f}"
                            ) if fr else ""
                    lines.append(f"- **{n}** ({demote[n]} segment(s)){ftag}")
                lines.append("")
            lines += ["_Full per-(app,geo,format) ranking in the Target MAX "
                      "Config artifact (config_recommendations/<acct>.md)._", ""]

        # ---- eCPM forecast (predictive, module 6) -------------------
        if r.ecpm_forecasts:
            fc = r.ecpm_forecasts[0]
            summ = fc.get("summary", {})
            # networks that are also demote candidates in the config rec
            demote_nets = set()
            for crec in (r.config_recommendations or []):
                for seg in crec.get("segments", []):
                    demote_nets.update(seg.get("demote_candidates", []))
            _ARROW = {"UP": "↑", "DOWN": "↓", "FLAT": "→"}
            lines += ["## 📈 eCPM Forecast (predictive)", "",
                      f"_Segments forecast: {summ.get('total')} · "
                      f"↑ {summ.get('up')} · ↓ {summ.get('down')} · "
                      f"→ {summ.get('flat')} · "
                      f"⚠️ early-warning {summ.get('early_warning')}_",
                      "",
                      "> Next-period eCPM per (app, geo, format, network) "
                      "from the daily series. Predictive signal to act "
                      "**before** a downtrend hurts — not a MAX write.",
                      "",
                      "**Top segments by volume:**"]
            for f in fc.get("forecasts", [])[:12]:
                arrow = _ARROW.get(f.get("trend"), "→")
                warn = " ⚠️ early-warning" if f.get("early_warning") else ""
                hit = (" (↔ 🎛 降级候选)" if f.get("network") in demote_nets
                       else "")
                lines.append(
                    f"- {arrow} **{f.get('segment')}** — "
                    f"last ${f.get('last_ecpm'):.2f} → "
                    f"pred ${f.get('predicted_ecpm'):.2f} "
                    f"[{f.get('confidence')}] "
                    f"(band ${f.get('lower'):.2f}-${f.get('upper'):.2f})"
                    f"{warn}{hit}")
            ew = [f for f in fc.get("forecasts", []) if f.get("early_warning")]
            if ew:
                lines += ["",
                          "**⚠️ Early warnings (downtrend, predictive):**"]
                for f in ew[:8]:
                    lines.append(
                        f"- **{f.get('segment')}** predicted "
                        f"${f.get('predicted_ecpm'):.2f} "
                        f"({f.get('predicted_ecpm')/max(f.get('last_ecpm'),1e-6):.0%} "
                        f"of last) — monitor / pre-emptive floor")
            lines.append("")

        if r.risks:
            lines += ["## ⚠️ Risk", ""]
            lines += [f"- {x}" for x in r.risks]
            lines.append("")
        # network table
        lines += ["## Networks", "",
                  "| Network | Rev | Rev% | eCPM | Imp | Show% | Attempts |",
                  "|---|---|---|---|---|---|---|"]
        nets = r.sections.get("by_network", {})
        t_rev = max(r.revenue, 1e-9)
        for k, s in sorted(nets.items(), key=lambda kv: -kv[1].revenue):
            lines.append(
                f"| {k} | ${s.revenue:.2f} | {s.revenue / t_rev:.1%} "
                f"| ${s.ecpm:.2f} | {s.impressions:,} | {s.show_rate:.1%} "
                f"| {s.attempts:,} |")
        lines += ["", "## Signals (raw)", ""]
        for s in r.signals:
            lines.append(f"- `[{s.severity}]` **{s.rule}** → {s.action} "
                         f"`{s.target}` ({s.confidence:.0%}): {s.reason}")
        lines += ["", "---",
                  "_Phase 1: all actions are recommendations "
                  "(requires_manual_apply=true). No MAX writes performed._"]
        return "\n".join(lines)

    def save(self, r: MonetizationDailyReport,
             out_dir: str = "outputs/monetization_reports") -> Dict[str, str]:
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.join(out_dir, f"{r.account}_{r.date}")
        md_path, json_path = base + ".md", base + ".json"
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(self.render_markdown(r))
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(r.to_dict(), fh, ensure_ascii=False, indent=2)
        return {"markdown": md_path, "json": json_path}
