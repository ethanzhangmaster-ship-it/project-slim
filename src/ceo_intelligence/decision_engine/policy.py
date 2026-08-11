"""E17.3 — 公司级决策策略（三道门，复用 E16.1.1 三门体系思想，阈值按 CEO 层重定）。

Gate 1 — 数据可信度：confidence < 0.8 → OBSERVE（仅观察，不执行）
Gate 2 — 风险控制：   risk >= 0.6  → APPROVE（需人工审批）
Gate 3 — 执行权限：   按 ActionDomain 区分
                        · RELEASE（发布类）且高置信低风险的 → EXECUTE
                        · PAYMENT（付费/经济类）→ APPROVE（必须人工）
                        · 其余（UA/ASO/CREATIVE/PRODUCT）高置信低风险的 → EXECUTE
                                                     否则 → APPROVE

附加：
- 无正向收益预期（expected_value <= 0）→ REJECT
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .models import ActionDomain, DecisionType, action_domain


# 风险阈值
HIGH_RISK = 0.6
LOW_RISK = 0.4
CONF_THRESHOLD = 0.8  # Gate 1 阈值（复用 E16.1.1 思想，公司级定为 0.8）


@dataclass
class PolicyConfig:
    conf_threshold: float = CONF_THRESHOLD
    high_risk: float = HIGH_RISK
    low_risk: float = LOW_RISK


class CompanyDecisionPolicy:
    """公司级三道门：把（机会/模拟/记忆）映射到 DecisionType。"""

    def __init__(self, config: PolicyConfig | None = None):
        self.cfg = config or PolicyConfig()

    def decide(
        self,
        *,
        game_id: str,
        opportunity_type: str,
        expected_value: float,
        confidence: float,
        risk: float,
    ) -> Tuple[DecisionType, str]:
        domain = action_domain(opportunity_type)

        # 无正向收益预期 → 拒绝
        if expected_value <= 0:
            return DecisionType.REJECT, "无正向收益预期，拒绝执行"

        # Gate 1：数据可信度不足 → 仅观察
        if confidence < self.cfg.conf_threshold:
            return (
                DecisionType.OBSERVE,
                f"置信度 {confidence:.0%} < {self.cfg.conf_threshold:.0%}，仅观察不执行",
            )

        # Gate 2：高风险 → 人工审批
        if risk >= self.cfg.high_risk:
            return DecisionType.APPROVE, f"风险 {risk:.0%} 偏高，需人工审批"

        # Gate 3：执行权限按域区分
        if domain == ActionDomain.PAYMENT:
            return DecisionType.APPROVE, "付费/经济类动作必须人工审批"

        if domain == ActionDomain.RELEASE:
            if risk < self.cfg.low_risk:
                return DecisionType.EXECUTE, "发布类动作，高置信低风险，可自动执行"
            return DecisionType.APPROVE, "发布类动作风险中等，需人工确认"

        # UA / ASO / CREATIVE / PRODUCT：高置信且低风险 → 自动执行
        if risk < self.cfg.low_risk:
            return DecisionType.EXECUTE, "高置信低风险，可自动执行"
        return DecisionType.APPROVE, "置信足够但风险中等，需人工审批"
