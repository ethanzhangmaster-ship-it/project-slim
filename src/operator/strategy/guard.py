"""P3.3 — Strategy Guard（策略守门员）。

强制执行链路：
    Strategy Mutation → Simulation → Approval → Execution

铁律：
- 任何影响生产的策略变更都**必须**先过 Simulation 闸门；
- **绝不**允许直接改 meta / 生产参数；
- **绝不**在 guard 内调用 Provider 或修改 Decision。

本层只是「闸门」，不是执行器。P3.3.1/3.2 阶段，loop 只把过闸的 proposal
送进 Simulation Queue（仅产出，不执行）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import StrategyProposal


@dataclass
class GuardVerdict:
    allowed: bool
    reason: str
    gated: bool = False   # True = 允许，但必须先过 Simulation 才能执行


class StrategyGuard:
    """校验策略建议是否可进入 Simulation Queue。"""

    def validate(self, proposal: StrategyProposal) -> GuardVerdict:
        # 1) 任何生产变更都必须带 requires_simulation=True
        if proposal.requires_simulation is False:
            return GuardVerdict(
                allowed=False,
                reason="生产变更必须走 Simulation 闸门："
                       "requires_simulation=False 被拦截",
                gated=False,
            )
        # 2) 纯建议（不修改 Decision / 不调 Provider）→ 允许进入 Simulation Queue
        return GuardVerdict(
            allowed=True,
            reason="进入 Simulation Queue（尚未执行，须经 "
                   "Simulation → Approval → Execution）",
            gated=True,
        )


__all__ = ["StrategyGuard", "GuardVerdict"]
