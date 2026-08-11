"""Policy Stabilizer Core (Spec §14) — 统一策略控制器

将退火 (Annealing) + FinalBandit 合成为一个统一控制器。

一句话定义:
    用温度 T(t) 控制 Bandit 的学习速度、探索强度、以及预算分配，
    从而实现"自动收敛的广告策略系统"。

核心融合思想:
    T(t) 不是参数，而是整个系统的"时间方向控制器"，
    它决定系统什么时候探索、什么时候收敛、什么时候进入稳定赚钱状态。

关键绑定关系:
    | 组件                | 被 T(t) 控制的行为    |
    | theta 更新          | 学习速度              |
    | sigma（不确定性）    | 探索强度              |
    | action selection   | exploit/explore      |
    | mutation strength  | 创意变异幅度           |
    | budget allocation  | 资金集中程度           |

系统行为变化:
    初期 (T高): 大量探索, mutation 疯狂, 找结构空间
    中期 (T中): 收敛到几个结构, winner 开始出现, budget 开始偏斜
    后期 (T低): 90% 预算集中在 Top creatives, mutation 几乎停止, ROAS 稳定

数据流:
    T(t) → Bandit update (theta/sigma) → Policy selection (softmax(theta+T*sigma))
         → Budget allocation (exp(theta/T)) → Variation Engine (mutation=T)
         → Facebook Ads → Reward (ROAS/CTR/Purchase) → 回流
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from market_ops.creative_intelligence.final_bandit import FinalBandit, FinalArm


# ============================================================================
# Temperature 函数
# ============================================================================

def temperature_at(t: int, T0: float = 1.0, T_min: float = 0.1, k: float = 0.03) -> float:
    """退火温度函数: T(t) = max(T_min, T0 * exp(-k * t))

    Args:
        t: 时间步 (通常为 pipeline 运行次数)
        T0: 初始温度 (默认 1.0)
        T_min: 最低温度 (默认 0.1)
        k: 衰减系数 (默认 0.03, 越大越快收敛)

    Returns:
        当前温度 ∈ [T_min, T0]
    """
    return max(T_min, T0 * math.exp(-k * t))


# ============================================================================
# Policy Stabilizer Core
# ============================================================================

@dataclass
class StabilizerConfig:
    """Policy Stabilizer 配置"""
    T0: float = 1.0       # 初始温度
    T_min: float = 0.1    # 最低温度
    k: float = 0.03       # 衰减系数


class PolicyStabilizerCore:
    """统一策略控制器 (Spec §14)

    T(t) 是 Bandit 的"控制旋钮"——所有子系统的行为都由 T(t) 统一驱动。

    用法:
        core = PolicyStabilizerCore(T0=1.0, T_min=0.1, k=0.03)
        bandit = FinalBandit()

        # 每轮 pipeline:
        T = core.temperature
        core.update_bandit(bandit, gene_type, gene_value, reward)
        probs = core.select(bandit, gene_type)
        budget = core.allocate_budget(bandit, gene_type)
        mutation = core.mutation_strength
        core.step()  # 推进时间步
    """

    def __init__(
        self,
        T0: float = 1.0,
        T_min: float = 0.1,
        k: float = 0.03,
        memory_path: str | Path | None = None,
    ):
        """
        Args:
            T0: 初始温度 (默认 1.0, 广泛探索)
            T_min: 最低温度 (默认 0.1, 几乎纯利用)
            k: 衰减系数 (默认 0.03, 越大越快收敛)
            memory_path: 持久化路径
        """
        if not 0 < T_min < T0:
            raise ValueError(f"T_min ({T_min}) must be in (0, T0 ({T0}))")
        if k <= 0:
            raise ValueError(f"k ({k}) must be > 0")

        self.config = StabilizerConfig(T0=T0, T_min=T_min, k=k)
        self._step: int = 0

        self._memory_path = Path(memory_path) if memory_path else None
        if self._memory_path and self._memory_path.exists():
            self._load()

    # ========================================================================
    # 核心: T(t)
    # ========================================================================

    @property
    def temperature(self) -> float:
        """当前温度 T(t) = max(T_min, T0 * exp(-k * t))"""
        return temperature_at(self._step, self.config.T0, self.config.T_min, self.config.k)

    @property
    def step(self) -> int:
        return self._step

    def advance(self) -> float:
        """推进一个时间步, 返回新温度"""
        self._step += 1
        self._save()
        return self.temperature

    step_forward = advance  # alias

    # ========================================================================
    # 阶段判断
    # ========================================================================

    @property
    def phase(self) -> str:
        """当前退火阶段"""
        T = self.temperature
        if T > 0.6:
            return "early"   # 广泛探索: 找结构空间
        elif T > 0.25:
            return "mid"     # 聚焦赢家: winner 开始出现
        else:
            return "late"    # 收敛 ROI: 90% 预算集中在 Top

    # ========================================================================
    # 1. Bandit 更新 (受 T 控制)
    # ========================================================================

    def update_bandit(
        self,
        bandit: FinalBandit,
        gene_type: str,
        gene_value: str,
        reward: float,
    ) -> None:
        """T(t)-modulated Bandit 更新

        delta = reward - theta
        theta += alpha * delta * T
        sigma = (1 - beta * T) * sigma + beta * abs(delta)
        trials += 1

        T 高 → 学得快 (探索), T 低 → 学得慢 (收敛)
        """
        bandit.update_with_temperature(gene_type, gene_value, reward, self.temperature)

    # ========================================================================
    # 2. 动作选择 (Exploit vs Explore)
    # ========================================================================

    def select(
        self,
        bandit: FinalBandit,
        gene_type: str,
    ) -> dict[str, float]:
        """T(t)-modulated action selection → 概率分布

        score_i = theta_i + T * sigma_i
        P(select i) = softmax(score_i)

        T 高 → sigma (探索) 重要 → 广泛探索
        T 低 → theta (收益) 重要 → 集中 exploit

        Returns:
            {gene_value: probability} 概率分布
        """
        T = self.temperature
        type_arms = [a for a in bandit.arms.values() if a.gene_type == gene_type]
        if not type_arms:
            return {}

        if all(a.trials == 0 for a in type_arms):
            n = len(type_arms)
            return {a.gene_value: 1.0 / n for a in type_arms}

        scores = [a.theta + T * a.sigma for a in type_arms]
        max_score = max(scores)
        effective_tau = max(T, 0.05)
        exp_scores = [math.exp((s - max_score) / effective_tau) for s in scores]
        total = sum(exp_scores)

        return {a.gene_value: e / total for a, e in zip(type_arms, exp_scores)}

    def sample(
        self,
        bandit: FinalBandit,
        gene_type: str,
    ) -> str:
        """从 T(t)-modulated 分布中采样一个 arm"""
        return bandit.sample_with_temperature(gene_type, self.temperature)

    # ========================================================================
    # 3. 预算分配 (核心收敛机制)
    # ========================================================================

    def allocate_budget(
        self,
        bandit: FinalBandit,
        gene_type: str,
    ) -> dict[str, float]:
        """T(t)-modulated 预算分配

        budget_i ∝ exp(theta_i / T(t))

        行为:
          T 高 → 平均分配 (探索)
          T 中 → 偏向赢家
          T 低 → 极度集中 (收敛)
        """
        T = max(self.temperature, 1e-6)
        type_arms = [a for a in bandit.arms.values() if a.gene_type == gene_type]
        if not type_arms:
            return {}

        thetas = np.array([a.theta for a in type_arms])
        scaled = thetas / T
        # 数值稳定
        scaled -= scaled.max()
        exps = np.exp(scaled)
        total = exps.sum()

        if total == 0:
            n = len(type_arms)
            return {a.gene_value: 1.0 / n for a in type_arms}

        return {a.gene_value: float(e / total) for a, e in zip(type_arms, exps)}

    # ========================================================================
    # 4. Mutation 控制
    # ========================================================================

    @property
    def mutation_strength(self) -> float:
        """mutation_strength = T(t)

        映射:
          T > 0.6  → 完全结构变异
          0.25 < T ≤ 0.6 → semantic 变异
          T ≤ 0.25 → copy tweak
        """
        return self.temperature

    def mutation_type(self) -> str:
        """当前阶段推荐的变异类型"""
        T = self.temperature
        if T > 0.6:
            return "structural"   # 完全结构变异
        elif T > 0.25:
            return "semantic"     # semantic 变异
        else:
            return "tweak"        # copy tweak

    # ========================================================================
    # 综合诊断
    # ========================================================================

    def stats(self) -> dict[str, Any]:
        """当前系统状态"""
        return {
            "step": self._step,
            "temperature": round(self.temperature, 4),
            "phase": self.phase,
            "mutation_strength": round(self.mutation_strength, 4),
            "mutation_type": self.mutation_type(),
            "config": {
                "T0": self.config.T0,
                "T_min": self.config.T_min,
                "k": self.config.k,
            },
        }

    def simulate_curve(self, n_steps: int = 50) -> list[dict[str, Any]]:
        """模拟退火曲线 (诊断用)"""
        saved_step = self._step
        curve = []
        for i in range(n_steps):
            self._step = saved_step + i
            curve.append({
                "step": self._step,
                "T": round(self.temperature, 4),
                "phase": self.phase,
            })
        self._step = saved_step
        return curve

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save(self) -> None:
        if not self._memory_path:
            return
        data = {
            "config": {
                "T0": self.config.T0,
                "T_min": self.config.T_min,
                "k": self.config.k,
            },
            "step": self._step,
            "temperature": round(self.temperature, 4),
            "phase": self.phase,
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
            cfg = data.get("config", {})
            if cfg:
                self.config = StabilizerConfig(
                    T0=cfg.get("T0", self.config.T0),
                    T_min=cfg.get("T_min", self.config.T_min),
                    k=cfg.get("k", self.config.k),
                )
            self._step = data.get("step", 0)