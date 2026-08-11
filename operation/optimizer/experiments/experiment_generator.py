"""
E15.2.6.1 — A/B Experiment Generator.

Upgrades the 6 intel rules' actionable outputs into formal A/B variable
experiments so the operator sees every opportunity in ONE language — the
North Star KPI:

        Maximize  IAA Revenue / DAU

For each A/B-eligible action it produces an ExperimentDefinition with:

    variant_a         — control (current state, measured today)
    variant_b         — treatment (proposed change, measured after apply)
    expected_metric   — always "revenue_per_dau"
    expected_lift_pct — *hypothesized* lift, grounded in the signal metrics
    ab_design         — how the lift is measured (pre/post diff at equal DAU)
    ab_kind           — revenue (real upside) | risk_hedge (no direct lift)

The hypothesized lift is deliberately conservative and is ALWAYS confirmed
by the post-apply diff-in-diff impact measurement (WinnerSelector) — that is
the whole point of the A/B framing: hypothesize, then measure, never assume.

Recovery / reallocation assumptions (documented, conservative):
    HW_RECOVERY   = 0.5  — fraction of a hidden winner's capture-rate gap
                          we expect to recover by raising exposure
    BF_RECOVERY   = 0.5  — fraction of a parasite network's reallocated
                          impression revenue we expect to actually recover
    ZOMBIE_REALLOC= 0.005— fraction of a freed zombie's requests that become
                          blended-eCPM revenue after reallocation

Deterministic — no LLM. Read-only over the report + its signals.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.optimizer.experiments.experiment_models import (
    AB_ELIGIBLE_ACTIONS, PROPOSED,
    _EXPECTED_SIGNAL_RULE, _HYPOTHESIS,
    ExperimentDefinition, exp_id,
)
from operation.optimizer.intel_models import (
    IntelSignal, MonetizationDailyReport,
)

# --- conservative recovery/reallocation assumptions -------------------- #
HW_RECOVERY = 0.5
BF_RECOVERY = 0.5
ZOMBIE_REALLOC = 0.005

# display strings
METRIC = "revenue_per_dau"


class ABExperimentGenerator:
    """Turn validated actions into A/B-framed experiment definitions."""

    # ------------------------------------------------------------------ #
    def generate(self, report: MonetizationDailyReport,
                 dau: Optional[float] = None
                 ) -> List[ExperimentDefinition]:
        """One A/B experiment per A/B-eligible validated action, enriched
        from the matching IntelSignal metrics."""
        sig_by_key: Dict[tuple, IntelSignal] = {}
        for s in report.signals:
            sig_by_key[(s.rule, s.target)] = s
            sig_by_key[(s.action, s.target)] = s

        out: List[ExperimentDefinition] = []
        for v in report.validated_actions:
            if v.get("action") not in AB_ELIGIBLE_ACTIONS:
                continue
            action = v["action"]
            target = v["target"]
            eid = exp_id(report.account, action, target)
            sig = (sig_by_key.get((v.get("source_rule"), target))
                   or sig_by_key.get((action, target)))
            exp = self._build(report, v, sig, dau, eid)
            if exp is not None:
                out.append(exp)
        return out

    # ------------------------------------------------------------------ #
    def _build(self, report: MonetizationDailyReport,
               v: Dict[str, Any], sig: Optional[IntelSignal],
               dau: Optional[float], eid: str
               ) -> Optional[ExperimentDefinition]:
        action = v["action"]
        target = v["target"]
        m = (sig.metrics if sig else {}) or {}
        total_rev = report.revenue
        total_imp = report.impressions
        blended = report.blended_ecpm

        a = b = design = ""
        lift = 0.0
        ab_kind = "revenue"
        verify = "signal"

        if action == "increase_bid_opportunity":
            cr = float(m.get("revenue_capture_rate", 0.0) or 0.0)
            rev_share = float(m.get("revenue_share", 0.0) or 0.0)
            ecpm = float(m.get("ecpm", 0.0) or 0.0)
            imps = int(m.get("impressions", 0) or 0)
            a = (f"现状(A)：{target} 仅捕获其 eCPM 潜力 {cr:.0%} "
                 f"（{imps:,} 曝光 @ eCPM ${ecpm:.2f}，收入占比 {rev_share:.1%}）")
            extra = rev_share * (1.0 - cr) * HW_RECOVERY
            lift = round(extra * 100.0, 2)
            b = (f"变体(B)：提升 bidding 曝光优先级，目标捕获潜力 "
                 f"→ ~{min(cr + (1.0 - cr) * HW_RECOVERY, 1.0):.0%}，"
                 f"预期收入占比 → ~{rev_share * (1.0 + (1.0 - cr) * HW_RECOVERY):.1%}")
            design = ("A/B 测量：apply 前(A) vs apply 后(B) 同 DAU 下 "
                      "Revenue/DAU 差分（diff-in-diff vs 账户漂移）")

        elif action == "adjust_bid_constraint":
            pecpm = float(m.get("ecpm", 0.0) or 0.0)
            share = float(m.get("impression_share", 0.0) or 0.0)
            rng = m.get("recommended_floor_range") or [0.0, 0.0]
            pimp = share * total_imp
            recovered = (pimp * (blended - pecpm) / 1000.0 * BF_RECOVERY
                         if blended > pecpm else 0.0)
            lift = round((recovered / total_rev * 100.0) if total_rev > 0 else 0.0, 2)
            a = (f"现状(A)：{target} 占 {share:.1%} 曝光 @ 寄生 eCPM ${pecpm:.2f} "
                 f"（< 账户 blend ${blended:.2f}），低价值回填")
            b = (f"变体(B)：设 price floor ${float(rng[0]):.2f}–${float(rng[1]):.2f} "
                 f"过滤低价值填充")
            design = ("A/B 测量：过滤前后同 DAU Revenue/DAU 差分"
                      "（同时盯整体填充率不下滑）")

        elif action in ("disable_network", "quarantine_network"):
            attempts = int(m.get("attempts", 0) or 0)
            rev = float(m.get("revenue", 0.0) or 0.0)
            recovered = attempts * blended / 1000.0 * ZOMBIE_REALLOC
            lift = round((recovered / total_rev * 100.0) if total_rev > 0 else 0.0, 2)
            a = (f"现状(A)：{target} 消耗 {attempts:,} 请求仅产生 ${rev:.2f}（僵尸）")
            verb = ("禁用" if action == "disable_network"
                    else "隔离观察 7 天后禁用")
            b = (f"变体(B)：{verb} → 释放瀑布槽位，请求重新分配到高 eCPM 网络"
                 f"（保守估计 {ZOMBIE_REALLOC:.1%} 重分配转化为收入）")
            design = ("A/B 测量：移除前后同 DAU Revenue/DAU 差分"
                      "（移除后僵尸信号消失即验证成功）")

        elif action == "diversify":
            a = f"现状(A)：收入单点集中（{target}），单一网络失效风险"
            b = ("变体(B)：引入候选网络分散收入来源，"
                 "降低单点失效风险（不直接提升收入，属风险对冲）")
            ab_kind = "risk_hedge"
            verify = "guardrail"
            lift = 0.0
            design = ("A/B 测量：仅观察用户侧护栏与集中度变化"
                      "（不追求直接 Revenue/DAU 提升）")
        else:
            return None

        baseline = (total_rev / dau) if dau else None
        rule = _EXPECTED_SIGNAL_RULE.get(action, v.get("source_rule", ""))
        expected_signal = ({"rule": rule, "target": target}
                           if rule else {})
        return ExperimentDefinition(
            exp_id=eid, account=report.account,
            title=v.get("title", f"{action} {target}"),
            hypothesis=_HYPOTHESIS.get(action, v.get("rationale", "")),
            action_type=action, target=target,
            source_rule=v.get("source_rule", rule),
            params={"expected_impact": v.get("expected_impact", "")},
            expected_signal=expected_signal,
            status=PROPOSED, created_at="", launched_at="",
            variant_a=a, variant_b=b,
            expected_metric=METRIC, expected_lift_pct=lift,
            metric_baseline=baseline, ab_design=design,
            ab_kind=ab_kind, verify_mode=verify,
            result_note="proposed A/B from daily report")

    # ------------------------------------------------------------------ #
    def enrich(self, exp: ExperimentDefinition,
               report: MonetizationDailyReport,
               dau: Optional[float] = None) -> bool:
        """Backfill A/B fields on a stored experiment that is missing them
        (migrates experiments proposed *before* the A/B increment existed).
        Returns True if anything was filled in. No-op if already enriched
        or if the action is not A/B-eligible / signal no longer present."""
        if exp.variant_a and exp.variant_b:
            return False
        if exp.action_type not in AB_ELIGIBLE_ACTIONS:
            return False
        sig = None
        for s in report.signals:
            if ((s.rule == exp.source_rule or s.action == exp.action_type)
                    and s.target == exp.target):
                sig = s
                break
        built = self._build(
            report,
            {"action": exp.action_type, "target": exp.target,
             "title": exp.title, "source_rule": exp.source_rule,
             "expected_impact": (exp.params or {}).get("expected_impact", ""),
             "rationale": exp.hypothesis},
            sig, dau, exp.exp_id)
        if built is None:
            return False
        for f in ("variant_a", "variant_b", "expected_metric",
                  "expected_lift_pct", "metric_baseline", "ab_design",
                  "ab_kind", "verify_mode"):
            setattr(exp, f, getattr(built, f))
        return True


__all__ = ["ABExperimentGenerator", "AB_ELIGIBLE_ACTIONS",
           "HW_RECOVERY", "BF_RECOVERY", "ZOMBIE_REALLOC"]
