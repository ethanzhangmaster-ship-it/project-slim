"""
E15.2.6 — Auto-Executor (decision layer).

Per the operator's chosen model "决策自动 + 人工落子": the AI decides the
risk tier of every proposed action — low-risk is AUTO-approved, high-risk
needs human APPROVAL — and emits a one-click apply checklist. The PHYSICAL
write to MAX stays a human action in the dashboard (MAX Management API is
write-blocked: PATCH 403/422). So "AUTO" means "AI auto-approves as safe
to apply", never "AI writes MAX".

Deterministic rules, no LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Risk tiers
AUTO = "AUTO"            # AI auto-approves; human applies in MAX dashboard
APPROVAL = "APPROVAL"    # AI flags high-risk; human must approve + apply
OBSERVE = "OBSERVE"      # info only; no apply

# Semantic tier per IntelSignal.action. Unknown actions default to APPROVAL
# (fail safe — never auto-approve something we cannot classify).
_TIER: Dict[str, str] = {
    "disable_network": AUTO,            # zombie: 30d rev<$1 & req>10k
    "increase_bid_opportunity": AUTO,   # raise exposure on high-eCPM network
    "adjust_bid_constraint": AUTO,      # small floor lift (parasite filter)
    "quarantine_network": APPROVAL,     # protected candidate, watch first
    "diversify": APPROVAL,              # changes network portfolio
    "reduce_waterfall_depth": APPROVAL, # restructures ordering
    "review_segment": OBSERVE,
    "monitor": OBSERVE,
    "handoff_ua": OBSERVE,              # UA scope, Growth OS
}

# Human-readable MAX dashboard steps. {t}=target, {low}/{high}=floor range.
_APPLY: Dict[str, str] = {
    "disable_network":
        "MAX 后台 → Mediation → 找到 {t} → 关闭/移除该 network 实例 "
        "（僵尸：30d 收入<$1 且请求>1万，移除零收入损失）",
    "increase_bid_opportunity":
        "MAX 后台 → {t} → 提升 bidding 曝光优先级（提高 bid / 展示权重），"
        "捕获其高 eCPM 潜力",
    "adjust_bid_constraint":
        "MAX 后台 → {t} → 设置统一竞价 price floor 范围 ${low}–${high}"
        "（过滤低价值回填，盯填充率）",
    "quarantine_network":
        "MAX 后台 → {t} → 先降权/隔离观察 7 天，确认僵尸后再禁用",
    "diversify":
        "MAX 后台 → 评估并引入候选网络以分散收入单点风险（需人工评估）",
    "reduce_waterfall_depth":
        "MAX 后台 → 检查 waterfall 实例，移除 0 曝光低 eCPM 的 {t}（重构需谨慎）",
    "monitor": "仅监控，无需操作",
    "review_segment": "仅复核分段数据，无需操作",
    "handoff_ua": "移交 Growth OS（UA 买量范畴），本系统不操作",
}

# Low-confidence AUTO actions get escalated to APPROVAL.
_CONF_FLOOR = 0.5


@dataclass
class RiskDecision:
    action: str
    target: str
    tier: str
    reason: str
    apply_instruction: str
    expected_impact: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action, "target": self.target, "tier": self.tier,
            "reason": self.reason, "apply_instruction": self.apply_instruction,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "requires_human_apply": True,
        }


def _floor_range(title: str) -> tuple:
    m = re.search(r"\$([0-9.]+)\s*-\s*\$([0-9.]+)", title or "")
    if m:
        return m.group(1), m.group(2)
    return "?", "?"


def classify_action(action: str, target: str,
                    expected_impact: str = "", title: str = "",
                    confidence: float = 0.0) -> RiskDecision:
    """Assign a risk tier + human-apply instruction to one action."""
    tier = _TIER.get(action, APPROVAL)   # unknown -> fail safe
    if tier == AUTO and confidence < _CONF_FLOOR:
        tier = APPROVAL  # escalate uncertain low-confidence calls

    if tier == AUTO:
        reason = ("低风险、可逆：AI 自动批准，由人在 MAX 后台一键落子"
                  if action != "adjust_bid_constraint"
                  else "小幅底价调整、可逆：AI 自动批准，由人在 MAX 后台落子")
    elif tier == APPROVAL:
        reason = "高风险/结构性变更：需人工审批后再在 MAX 后台落子"
    else:
        reason = "仅观察，不需执行"

    instr = _APPLY.get(action, "在 MAX 后台对 {t} 执行相应调整".format(t=target))
    if action == "adjust_bid_constraint":
        low, high = _floor_range(title)
        instr = instr.format(t=target, low=low, high=high)
    else:
        instr = instr.format(t=target)

    return RiskDecision(
        action=action, target=target, tier=tier, reason=reason,
        apply_instruction=instr, expected_impact=expected_impact,
        confidence=confidence)


def from_report(report) -> Dict[str, Any]:
    """Classify every action in a MonetizationDailyReport."""
    actions = getattr(report, "actions", None) or []
    return build_apply_checklist(actions)


def build_apply_checklist(actions: List[Any]) -> Dict[str, Any]:
    """Bucket actions into AUTO / APPROVAL / OBSERVE and render a checklist."""
    auto, approval, observe = [], [], []
    for a in actions:
        # accept both ActionItem and plain dict
        action = getattr(a, "action", None) or a.get("action", "")
        target = getattr(a, "target", None) or a.get("target", "")
        impact = getattr(a, "expected_impact", None) or a.get("expected_impact", "") or ""
        title = getattr(a, "title", None) or a.get("title", "") or ""
        conf = getattr(a, "confidence", None)
        if conf is None:
            conf = a.get("confidence", 0.0) or 0.0
        d = classify_action(action, target, impact, title, float(conf))
        bucket = {"AUTO": auto, "APPROVAL": approval, "OBSERVE": observe}[d.tier]
        bucket.append(d)

    result = {
        "auto": [d.to_dict() for d in auto],
        "approval": [d.to_dict() for d in approval],
        "observe": [d.to_dict() for d in observe],
        "counts": {"auto": len(auto), "approval": len(approval),
                   "observe": len(observe)},
        "markdown": render_checklist_markdown(auto, approval, observe),
    }
    return result


def render_checklist_markdown(auto, approval, observe) -> str:
    c = (f"🤖 **Auto-Executor（决策自动 + 人工落子）**\n"
         f"自动批准 {len(auto)} · 需审批 {len(approval)} · 仅观察 {len(observe)}"
         f"　|　所有落子均由人在 MAX 后台执行（API 禁写）")
    lines = [c, ""]
    if auto:
        lines.append("✅ **自动批准（人后台一键落子）**：")
        for d in auto:
            lines.append(f"  • {d.target} — {d.apply_instruction}")
        lines.append("")
    if approval:
        lines.append("⚠️ **需人工审批**：")
        for d in approval:
            lines.append(f"  • {d.target} [{d.action}] — {d.reason}")
        lines.append("")
    if observe:
        lines.append("👁 **仅观察**：")
        for d in observe:
            lines.append(f"  • {d.target} [{d.action}]")
        lines.append("")
    return "\n".join(lines).rstrip()


__all__ = ["AUTO", "APPROVAL", "OBSERVE", "RiskDecision",
           "classify_action", "from_report", "build_apply_checklist",
           "render_checklist_markdown"]
