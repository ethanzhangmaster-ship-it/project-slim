"""Policy Stabilizer — 收敛约束 2/3

Policy Regularization: 变异率衰减 + 信号引导变异方向。

核心约束:
- MutationRate = f(performance): 好素材少动, 坏素材多试, 不是平均探索
- 全局探索衰减: lim(t→∞) exploration_rate → 0
- 变异方向由 Bandit 信号 (theta/sigma) 引导, 不是随机

数据流:
    FinalBandit state (theta, sigma, trials) → MutationDecayScheduler → signal-guided mutation
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import exp
from pathlib import Path
from typing import Any


@dataclass
class ArmPerformance:
    """单个 arm 的性能快照, 用于计算 mutation_rate"""
    theta: float
    sigma: float
    trials: int

    @property
    def is_stable_winner(self) -> bool:
        """高 theta + 低 sigma → 稳定赢家"""
        return self.theta > 0.15 and self.sigma < 0.20

    @property
    def is_uncertain_winner(self) -> bool:
        """高 theta + 高 sigma → 不确定赢家"""
        return self.theta > 0.10 and self.sigma > 0.25

    @property
    def is_stable_loser(self) -> bool:
        """低 theta + 低 sigma → 稳定输家"""
        return self.theta < -0.05 and self.sigma < 0.15

    @property
    def is_exploration_candidate(self) -> bool:
        """低 theta + 高 sigma → 需要探索"""
        return self.theta < 0.05 and self.sigma > 0.20


class MutationDecayScheduler:
    """全局探索衰减调度器

    模拟退火: exploration_rate = exp(-lambda * t)
    lim(t→∞) exploration_rate → 0

    用法:
        scheduler = MutationDecayScheduler(decay_lambda=0.01)
        rate = scheduler.mutation_rate(arm_perf)  # 0~1
    """

    # 突变率边界
    RATE_MIN = 0.05   # 最低突变率 (稳定赢家)
    RATE_MAX = 0.80   # 最高突变率 (需要探索)
    RATE_DEFAULT = 0.40  # 默认突变率 (未知)

    def __init__(self, decay_lambda: float = 0.01, memory_path: str | Path | None = None):
        """
        Args:
            decay_lambda: 全局衰减系数 (0.005~0.05). 越大衰减越快.
            memory_path: 持久化路径
        """
        self.decay_lambda = decay_lambda
        self._step = 0

        # 每个 arm 的局部突变率
        self._arm_rates: dict[str, float] = {}

        self._memory_path = Path(memory_path) if memory_path else None
        if self._memory_path and self._memory_path.exists():
            self._load()

    # ========================================================================
    # 核心: mutation_rate = f(performance)
    # ========================================================================

    def mutation_rate(self, arm_key: str, perf: ArmPerformance) -> float:
        """计算单个 arm 的突变率。

        规则:
        - 稳定赢家 (theta>0.15, sigma<0.20) → rate → RATE_MIN (几乎不动)
        - 不确定赢家 (theta>0.10, sigma>0.25) → rate 中等 (谨慎试)
        - 稳定输家 (theta<-0.05, sigma<0.15) → rate → RATE_MIN (放弃)
        - 需要探索 (theta<0.05, sigma>0.20) → rate → RATE_MAX (多试)
        - 其他 → RATE_DEFAULT

        全局衰减因子叠加: rate *= exp(-lambda * step)
        """
        # 1. 局部: 基于性能的突变率
        if perf.is_stable_winner:
            local_rate = 0.10
        elif perf.is_uncertain_winner:
            local_rate = 0.35
        elif perf.is_stable_loser:
            local_rate = 0.05
        elif perf.is_exploration_candidate:
            local_rate = 0.70
        elif perf.trials < 3:
            local_rate = 0.60  # 样本不足, 多探索
        else:
            local_rate = self.RATE_DEFAULT

        # 2. 全局: 指数衰减 lim(t→∞) → 0
        global_decay = exp(-self.decay_lambda * self._step)
        rate = local_rate * global_decay

        # 3. clamp
        rate = max(self.RATE_MIN, min(self.RATE_MAX, rate))

        self._arm_rates[arm_key] = rate
        self._save()
        return rate

    def step(self) -> None:
        """推进全局步数 (每次 pipeline 运行后调用)"""
        self._step += 1
        self._save()

    def get_arm_rate(self, arm_key: str) -> float:
        return self._arm_rates.get(arm_key, self.RATE_DEFAULT)

    @property
    def global_exploration_rate(self) -> float:
        """当前全局探索率"""
        return exp(-self.decay_lambda * self._step)

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save(self) -> None:
        if not self._memory_path:
            return
        data = {
            "decay_lambda": self.decay_lambda,
            "step": self._step,
            "global_exploration_rate": round(self.global_exploration_rate, 4),
            "arm_rates": self._arm_rates,
        }
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._memory_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(self._memory_path)

    def _load(self) -> None:
        if not self._memory_path or not self._memory_path.exists():
            return
        with open(self._memory_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.decay_lambda = data.get("decay_lambda", self.decay_lambda)
            self._step = data.get("step", 0)
            self._arm_rates = data.get("arm_rates", {})

    def stats(self) -> dict[str, Any]:
        return {
            "decay_lambda": self.decay_lambda,
            "step": self._step,
            "global_exploration_rate": round(self.global_exploration_rate, 4),
            "tracked_arms": len(self._arm_rates),
            "arm_rates": self._arm_rates,
        }


# ============================================================================
# Signal-Guided Mutation Director
# ============================================================================

@dataclass
class MutationDirective:
    """变异指令: 告诉变异器该往哪个方向变"""
    gene_type: str
    target_value: str | None = None      # 定向目标值 (强信号)
    avoid_values: list[str] = field(default_factory=list)  # 避免的值 (弱信号)
    mutation_rate: float = 0.5           # 该维度的变异概率
    reason: str = ""                     # 可解释原因


class SignalGuidedDirector:
    """基于 Bandit 信号生成变异指令。

    输入: FinalBandit 的 theta/sigma 排序
    输出: 每个 gene_type 的 MutationDirective

    逻辑:
    - 识别 theta 最高/最低的 arm → 定向变异方向
    - sigma 高的 arm → 需要更多探索 (增加变异率)
    - sigma 低的 arm → 已经确定 (减少变异率)

    支持两种调度器:
    - MutationDecayScheduler (旧)
    - AnnealingController (推荐, 统一 T 驱动)
    """

    def __init__(self) -> None:
        pass

    def generate_directives(
        self,
        bandit_state: dict[str, dict[str, Any]],
        scheduler: Any,  # MutationDecayScheduler | AnnealingController
    ) -> list[MutationDirective]:
        """从 Bandit 状态生成变异指令。

        Args:
            bandit_state: FinalBandit.get_state() 的输出
            scheduler: MutationDecayScheduler 或 AnnealingController

        Returns:
            每个 gene_type 一条 MutationDirective
        """
        # 检测调度器类型
        from market_ops.creative_intelligence.annealing_controller import AnnealingController
        is_annealing = isinstance(scheduler, AnnealingController)

        directives: list[MutationDirective] = []

        for gene_type, state in bandit_state.items():
            arms = state.get("arms", {})
            if not arms or len(arms) < 2:
                continue

            # 排序: theta DESC
            sorted_arms = sorted(arms.items(), key=lambda x: x[1]["theta"], reverse=True)
            best_gv, best = sorted_arms[0]
            worst_gv, worst = sorted_arms[-1]

            perf = ArmPerformance(
                theta=best["theta"], sigma=best["sigma"], trials=best["trials"],
            )
            arm_key = f"{gene_type}_{best_gv}"

            # 统一的变异率: AnnealingController 用 mutation_rate(), MutationDecayScheduler 用 mutation_rate()
            if is_annealing:
                rate = scheduler.mutation_rate(base_rate=0.5)
            else:
                rate = scheduler.mutation_rate(arm_key, perf)

            # 构建指令
            avoid = []
            reason_parts = []

            if worst["theta"] < 0 and worst["sigma"] < 0.20:
                # 稳定输家: 明确避免
                avoid.append(worst_gv)
                reason_parts.append(f"avoid {worst_gv} (theta={worst['theta']:.3f}, stable loser)")

            if best["sigma"] > 0.25:
                reason_parts.append(f"winner {best_gv} has high uncertainty (sigma={best['sigma']:.3f})")
            else:
                reason_parts.append(f"winner {best_gv} is stable (sigma={best['sigma']:.3f}), low mutation")

            # 如果还有第二高 theta 且 sigma 高 → 可能是有潜力的候选
            if len(sorted_arms) > 2:
                second_gv, second = sorted_arms[1]
                if second["sigma"] > 0.25 and second["theta"] > 0:
                    reason_parts.append(f"candidate {second_gv} needs more exploration (theta={second['theta']:.3f}, sigma={second['sigma']:.3f})")

            directive = MutationDirective(
                gene_type=gene_type,
                target_value=best_gv if best["theta"] > 0.05 else None,
                avoid_values=avoid,
                mutation_rate=rate,
                reason="; ".join(reason_parts) if reason_parts else "default",
            )
            directives.append(directive)

        return directives

    def to_guide_dict(self, directives: list[MutationDirective]) -> dict[str, dict[str, Any]]:
        """转为字典格式, 方便传给变异器"""
        return {
            d.gene_type: {
                "target": d.target_value,
                "avoid": d.avoid_values,
                "rate": d.mutation_rate,
                "reason": d.reason,
            }
            for d in directives
        }