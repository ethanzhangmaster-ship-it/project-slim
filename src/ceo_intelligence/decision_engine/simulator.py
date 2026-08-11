"""E17.3 — 模拟层（行动前预测，确定性，无 LLM）。

对每个机会类型给出基线预测（相对收入变化 / ROAS 变化 / 置信 / 风险），
并可选接入 Decision Memory 的历史成功率，对预测置信做加成。

这是「先模拟、后执行」的关键：CEO 不直接拍板，先看模拟结果。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .models import SimulationResult


# 各机会类型的基线模拟（确定性查表，可被记忆微调）
# 风险设定：发布/素材/买量/ASO 偏低（高置信可自动），营收修复/经济偏高（需人工）
_BASE: Dict[str, SimulationResult] = {
    "revenue_recovery": SimulationResult(+0.20, +0.10, 0.70, 0.45),
    "ua_scale": SimulationResult(+0.15, +0.05, 0.75, 0.35),
    "ua_stop_loss": SimulationResult(+0.08, +0.20, 0.85, 0.25),
    "creative_refresh": SimulationResult(+0.12, +0.10, 0.80, 0.30),
    "aso_optimization": SimulationResult(+0.10, +0.05, 0.80, 0.20),
    "monetization": SimulationResult(+0.18, +0.15, 0.70, 0.50),
    "retention": SimulationResult(+0.14, +0.10, 0.75, 0.35),
    "release_health": SimulationResult(+0.05, +0.02, 0.85, 0.15),
}

_DEFAULT = SimulationResult(+0.10, +0.05, 0.75, 0.40)


@dataclass
class MemoryStats:
    """来自 Decision Memory 的历史统计（E16 Experience Store）。"""
    n: int = 0
    success_rate: float = 0.0
    avg_reward: float = 0.0


class OpportunitySimulator:
    """确定性模拟器：机会类型 -> SimulationResult（+ 记忆微调）。"""

    def simulate(
        self, opportunity_type: str, memory: Optional[MemoryStats] = None
    ) -> SimulationResult:
        base = _BASE.get(opportunity_type, _DEFAULT)
        conf = base.confidence
        risk = base.risk
        # 记忆微调：历史样本充足且成功率高 → 提升置信、降低风险
        if memory and memory.n >= 2:
            if memory.success_rate >= 0.8:
                conf = min(0.99, conf + 0.10)
                risk = max(0.10, risk - 0.05)
            elif memory.success_rate <= 0.3:
                conf = max(0.30, conf - 0.10)
                risk = min(0.95, risk + 0.05)
        return SimulationResult(
            expected_revenue_change=base.expected_revenue_change,
            expected_roas_change=base.expected_roas_change,
            confidence=round(conf, 4),
            risk=round(risk, 4),
        )
