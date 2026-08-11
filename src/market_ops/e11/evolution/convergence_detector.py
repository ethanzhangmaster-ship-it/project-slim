"""E11.4.2 Convergence Detector — 收敛检测器。

判断进化是否已达到收敛状态（无显著改进）。

配置：
  ConvergenceConfig(
      patience=5,      # 无改进容忍代数
      min_delta=0.01,  # 最小改进阈值
  )

检测逻辑：
  - 从历史记录中取最近 patience 代
  - 如果 best_score 的最大变化 < min_delta → 收敛

数据流：
  EvolutionHistory → ConvergenceDetector.detect() → {"converged": bool, "reason": str}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .generation_schema import EvolutionHistory


# ═══════════════════════════════════════════════════════════
# ConvergenceConfig — 收敛配置
# ═══════════════════════════════════════════════════════════

@dataclass
class ConvergenceConfig:
    """收敛检测配置。

    patience: 连续无改进代数上限，超过则判定收敛
    min_delta: 最小改进阈值，小于此值视为无改进
    """
    patience: int = 5
    min_delta: float = 0.01

    def to_dict(self) -> dict[str, Any]:
        return {
            "patience": self.patience,
            "min_delta": self.min_delta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConvergenceConfig:
        return cls(
            patience=data.get("patience", 5),
            min_delta=data.get("min_delta", 0.01),
        )

    def __repr__(self) -> str:
        return (
            f"ConvergenceConfig(patience={self.patience}, "
            f"min_delta={self.min_delta})"
        )


# ═══════════════════════════════════════════════════════════
# ConvergenceDetector — 收敛检测器
# ═══════════════════════════════════════════════════════════

class ConvergenceDetector:
    """收敛检测器。

    判断多代进化是否已收敛（无显著改进）。

    Usage:
        detector = ConvergenceDetector(config)
        result = detector.detect(history)
        # → {"converged": True, "reason": "No improvement in last 5 generations (delta=0.005 < 0.01)"}
    """

    def __init__(self, config: ConvergenceConfig | None = None) -> None:
        """初始化。

        Args:
            config: 收敛配置（默认使用 ConvergenceConfig()）
        """
        self._config = config or ConvergenceConfig()

    @property
    def config(self) -> ConvergenceConfig:
        return self._config

    # ── 检测 ──────────────────────────────────────────

    def detect(self, history: EvolutionHistory) -> dict[str, Any]:
        """检测进化是否收敛。

        Args:
            history: 进化历史

        Returns:
            {
                "converged": bool,
                "reason": str,
                "patience": int,
                "min_delta": float,
                "actual_delta": float | None,
            }
        """
        generations = history.generations
        if len(generations) < 2:
            return {
                "converged": False,
                "reason": "Insufficient generations (need at least 2)",
                "patience": self._config.patience,
                "min_delta": self._config.min_delta,
                "actual_delta": None,
            }

        # 取最近 patience 代
        window = generations[-self._config.patience:]
        if len(window) < 2:
            return {
                "converged": False,
                "reason": "Insufficient generation window for convergence check",
                "patience": self._config.patience,
                "min_delta": self._config.min_delta,
                "actual_delta": None,
            }

        # 计算窗口内最高分和最低分的差值
        scores = [g.best_score for g in window]
        max_score = max(scores)
        min_score = min(scores)
        actual_delta = round(max_score - min_score, 6)

        if actual_delta < self._config.min_delta:
            return {
                "converged": True,
                "reason": (
                    f"No improvement in last {len(window)} generations "
                    f"(delta={actual_delta} < {self._config.min_delta})"
                ),
                "patience": self._config.patience,
                "min_delta": self._config.min_delta,
                "actual_delta": actual_delta,
            }
        else:
            return {
                "converged": False,
                "reason": (
                    f"Still improving (delta={actual_delta} >= "
                    f"{self._config.min_delta})"
                ),
                "patience": self._config.patience,
                "min_delta": self._config.min_delta,
                "actual_delta": actual_delta,
            }

    def is_converged(self, history: EvolutionHistory) -> bool:
        """便捷方法：返回是否收敛。"""
        return self.detect(history)["converged"]

    def __repr__(self) -> str:
        return repr(self._config)