"""Annealing Controller — 统一退火机制

系统唯一的温度参数 T(t), 驱动全部三层:
  - Exploration:  P(explore) = T(t)
  - Mutation:     mutation_strength = T(t)
  - Budget:       budget_i ∝ softmax(theta_i / T(t))
  - Learning:     effective_reward = theta + T(t) * (raw_reward - theta)

退火函数:
  T(t) = max(T_min, T_0 * exp(-k * t))

本质:
  Early:  T 高 → 广泛试错 (找结构)
  Mid:    T 中 → 聚焦赢家 (找模式)
  Late:   T 低 → 收敛 ROI (稳定印钞)
"""

from __future__ import annotations

import json
from math import exp
from pathlib import Path
from typing import Any


class AnnealingController:
    """统一退火控制器 — 系统唯一温度来源

    参数推荐:
      T_0 = 1.0    (初始高温, 广泛探索)
      T_min = 0.1  (最低温度, 几乎纯利用)
      k = 0.02     (衰减系数, 越大越快收敛)

    用法:
      ac = AnnealingController(T_0=1.0, T_min=0.1, k=0.02)
      T = ac.temperature  # 当前温度
      ac.step()           # 推进一个时间步
    """

    def __init__(
        self,
        T_0: float = 1.0,
        T_min: float = 0.10,
        k: float = 0.02,
        memory_path: str | Path | None = None,
    ):
        if not 0 < T_min < T_0:
            raise ValueError(f"T_min ({T_min}) must be in (0, T_0 ({T_0}))")
        if k <= 0:
            raise ValueError(f"k ({k}) must be > 0")

        self.T_0 = T_0
        self.T_min = T_min
        self.k = k
        self._step: int = 0

        self._memory_path = Path(memory_path) if memory_path else None
        if self._memory_path and self._memory_path.exists():
            self._load()

    # ========================================================================
    # 核心: T(t)
    # ========================================================================

    @property
    def temperature(self) -> float:
        """当前温度 T(t) = max(T_min, T_0 * exp(-k * t))"""
        return max(self.T_min, self.T_0 * exp(-self.k * self._step))

    @property
    def step(self) -> int:
        return self._step

    def step(self) -> float:
        """推进一个时间步, 返回新温度"""
        self._step += 1
        self._save()
        return self.temperature

    # ========================================================================
    # 阶段判断
    # ========================================================================

    @property
    def phase(self) -> str:
        """当前退火阶段"""
        T = self.temperature
        if T > 0.6:
            return "early"   # 广泛探索
        elif T > 0.25:
            return "mid"     # 聚焦赢家
        else:
            return "late"    # 收敛 ROI

    @property
    def exploration_probability(self) -> float:
        """P(explore) = T(t)"""
        return self.temperature

    @property
    def exploitation_probability(self) -> float:
        """P(exploit) = 1 - T(t)"""
        return 1.0 - self.temperature

    # ========================================================================
    # 驱动层: 将 T 应用于各子系统
    # ========================================================================

    def mutation_rate(self, base_rate: float = 0.5) -> float:
        """mutation_strength = base_rate * T(t)

        高温 → 全结构变异, 低温 → 微调文案
        """
        return max(0.05, base_rate * self.temperature)

    def effective_reward(self, theta_current: float, raw_reward: float) -> float:
        """学习退火: effective_reward = theta + T(t) * (raw_reward - theta)

        等价于: theta_new = theta + alpha * T(t) * (raw_reward - theta)
        但不修改 FinalBandit 内部公式.

        T=1.0 → effective_reward = raw_reward (全量学习)
        T=0.1 → effective_reward ≈ theta_current (几乎不学)
        """
        return theta_current + self.temperature * (raw_reward - theta_current)

    def softmax_budget_weights(self, thetas: list[float]) -> list[float]:
        """softmax(theta_i / T(t)) 预算分配权重

        高温 (T 大) → theta_i/T 小 → softmax 接近均匀 → 平均分配
        低温 (T 小) → theta_i/T 大 → softmax 尖锐 → 极度集中赢家
        """
        T = self.temperature
        if T < 1e-6:
            T = 1e-6
        scaled = [t / T for t in thetas]
        # 数值稳定: 减去 max
        max_val = max(scaled)
        exps = [exp(s - max_val) for s in scaled]
        total = sum(exps)
        return [e / total for e in exps] if total > 0 else [1.0 / len(thetas)] * len(thetas)

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save(self) -> None:
        if not self._memory_path:
            return
        data = {
            "T_0": self.T_0,
            "T_min": self.T_min,
            "k": self.k,
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
            self._step = data.get("step", 0)

    def stats(self) -> dict[str, Any]:
        return {
            "T_0": self.T_0,
            "T_min": self.T_min,
            "k": self.k,
            "step": self._step,
            "temperature": round(self.temperature, 4),
            "phase": self.phase,
            "P(explore)": round(self.exploration_probability, 4),
            "P(exploit)": round(self.exploitation_probability, 4),
        }

    def simulate(self, n_steps: int = 50) -> list[dict[str, Any]]:
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