"""P3.4.3 — Allocation 约束定义与校验器。

约束只描述「资源怎么挪才合法」，不做任何分配计算（分配在 :mod:`.simulator`）。
约束校验输出 ``ConstraintCheck`` 列表，供 :class:`AllocationSimulationResult`
收敛出 ``verdict``。

纪律（继承 P3.4）：
- 不预测收入、不重算 ROAS / spend / revenue；不触碰 E17.3 / Provider / 执行层。
- 本模块零业务依赖，只依赖 :mod:`.allocation_models` 的枚举与 ``ConstraintCheck``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .allocation_models import AllocationDelta, ConstraintCheck, ConstraintStatus

# 浮点容差（预算守恒 / 比例比较用）
_EPS = 1e-6

# 软告警阈值：总挪动比例超过此值仅 WARN（不阻断），供人工留意。
# 这是内部常量，不暴露为配置字段（max_shift_ratio / min_reserve_ratio 才是可配约束）。
_TOTAL_SHIFT_WARN_RATIO = 0.35


@dataclass
class AllocationConstraints:
    """一次 what-if 资源迁移模拟的硬约束。

    - ``total_budget``:     预算池总额（与 baseline / proposed amount 同币种单位）
    - ``max_shift_ratio``:  单游戏最大挪动比例（``|delta| / total_budget`` 的上限）
    - ``min_reserve_ratio``:战略储备下限（``reserve = total_budget - Σproposed``
                             必须 ≥ 此比例；等价于任一游戏占比 ≤ ``1 - min_reserve_ratio``）
    """

    total_budget: float = 0.0
    max_shift_ratio: float = 0.2
    min_reserve_ratio: float = 0.1

    def to_dict(self) -> Dict[str, float]:
        return {
            "total_budget": self.total_budget,
            "max_shift_ratio": self.max_shift_ratio,
            "min_reserve_ratio": self.min_reserve_ratio,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "AllocationConstraints":
        return cls(
            total_budget=float(d.get("total_budget", 0.0)),
            max_shift_ratio=float(d.get("max_shift_ratio", 0.2)),
            min_reserve_ratio=float(d.get("min_reserve_ratio", 0.1)),
        )

    # ------------------------------------------------------------------ #
    # 校验
    # ------------------------------------------------------------------ #
    def validate(
        self,
        baseline: Dict[str, float],
        proposed: Dict[str, float],
        deltas: List[AllocationDelta],
        gross_shift: float,
    ) -> List[ConstraintCheck]:
        """对一次模拟的结果逐条校验，返回有序 ``ConstraintCheck`` 列表。

        顺序固定：non_empty → budget_conservation → per_game_shift_cap →
        reserve_floor → non_negative → total_shift_warn。
        任何一条 ``BLOCKED`` 都会使模拟整体 verdict 为 BLOCKED。
        """
        checks: List[ConstraintCheck] = []

        # 1) 非空组合
        if not baseline:
            checks.append(
                ConstraintCheck(
                    "non_empty",
                    ConstraintStatus.BLOCKED,
                    detail="baseline allocation is empty (no games)",
                )
            )
            return checks

        base_sum = sum(baseline.values())
        prop_sum = sum(proposed.values())

        # 2) 预算守恒：挪动不改变总预算
        if abs(prop_sum - base_sum) > _EPS:
            checks.append(
                ConstraintCheck(
                    "budget_conservation",
                    ConstraintStatus.BLOCKED,
                    detail=f"sum(proposed)={prop_sum:.4f} != sum(baseline)={base_sum:.4f}",
                    observed=prop_sum,
                    limit=base_sum,
                )
            )
        else:
            checks.append(
                ConstraintCheck(
                    "budget_conservation",
                    ConstraintStatus.PASS,
                    detail="sum(proposed) == sum(baseline) (budget conserved)",
                    observed=prop_sum,
                    limit=base_sum,
                )
            )

        # 有效预算池：未显式给定时用 baseline 总和兜底（避免除零）
        tb = self.total_budget if self.total_budget > 0 else (base_sum or 0.0)

        # 3) 单游戏挪动上限（max_shift_ratio）
        max_ratio = 0.0
        worst = None
        for d in deltas:
            if tb > 0:
                r = abs(d.delta) / tb
                if r > max_ratio:
                    max_ratio = r
                    worst = d.game_id
        if max_ratio > self.max_shift_ratio + _EPS:
            checks.append(
                ConstraintCheck(
                    "per_game_shift_cap",
                    ConstraintStatus.BLOCKED,
                    detail=(
                        f"game '{worst}' shift ratio {max_ratio:.4f} exceeds "
                        f"max_shift_ratio {self.max_shift_ratio}"
                    ),
                    observed=max_ratio,
                    limit=self.max_shift_ratio,
                )
            )
        else:
            checks.append(
                ConstraintCheck(
                    "per_game_shift_cap",
                    ConstraintStatus.PASS,
                    detail=f"max per-game shift ratio {max_ratio:.4f} <= {self.max_shift_ratio}",
                    observed=max_ratio,
                    limit=self.max_shift_ratio,
                )
            )

        # 4) 战略储备下限（min_reserve_ratio）
        reserve = tb - prop_sum
        floor = self.min_reserve_ratio * tb
        if reserve < floor - _EPS:
            checks.append(
                ConstraintCheck(
                    "reserve_floor",
                    ConstraintStatus.BLOCKED,
                    detail=(
                        f"reserve {reserve:.4f} < min_reserve_ratio*tb {floor:.4f} "
                        f"(at least {self.min_reserve_ratio:.2f} of budget must stay reserved)"
                    ),
                    observed=reserve,
                    limit=floor,
                )
            )
        else:
            checks.append(
                ConstraintCheck(
                    "reserve_floor",
                    ConstraintStatus.PASS,
                    detail=f"reserve {reserve:.4f} >= floor {floor:.4f}",
                    observed=reserve,
                    limit=floor,
                )
            )

        # 5) 非负分配（任何游戏不得出现负预算）
        neg_games = [gid for gid, v in proposed.items() if v < -_EPS]
        if neg_games:
            checks.append(
                ConstraintCheck(
                    "non_negative",
                    ConstraintStatus.BLOCKED,
                    detail=f"negative proposed allocation for: {neg_games}",
                    observed=min(proposed.values()),
                )
            )
        else:
            checks.append(
                ConstraintCheck(
                    "non_negative",
                    ConstraintStatus.PASS,
                    detail="all proposed allocations >= 0",
                )
            )

        # 6) 总挪动软告警（不阻断，仅提示）
        gross_ratio = (gross_shift / tb) if tb > 0 else 0.0
        if gross_ratio > _TOTAL_SHIFT_WARN_RATIO:
            checks.append(
                ConstraintCheck(
                    "total_shift_warn",
                    ConstraintStatus.WARN,
                    detail=(
                        f"gross shift ratio {gross_ratio:.4f} exceeds soft warn "
                        f"ratio {_TOTAL_SHIFT_WARN_RATIO} (review before any real action)"
                    ),
                    observed=gross_ratio,
                    limit=_TOTAL_SHIFT_WARN_RATIO,
                )
            )
        else:
            checks.append(
                ConstraintCheck(
                    "total_shift_warn",
                    ConstraintStatus.PASS,
                    detail=f"gross shift ratio {gross_ratio:.4f} within soft warn ratio",
                    observed=gross_ratio,
                    limit=_TOTAL_SHIFT_WARN_RATIO,
                )
            )

        return checks
