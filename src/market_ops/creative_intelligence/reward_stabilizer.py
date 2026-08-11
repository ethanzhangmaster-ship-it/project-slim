"""Reward Stabilizer — 收敛约束 1/3

Reward Stationarity: EMA 平滑 + cohort 归一化，消除 ROAS 延迟噪声。

核心约束:
- 原始 reward 经过 EMA 平滑后再进入 FinalBandit.update()
- 按 cohort (channel/project) 做 z-score 归一化，消除跨市场偏差
- 支持 delayed reward 回填时的增量修正

数据流:
    raw_quality_score → EMA Smooth → Cohort Normalize → stabilized_reward → FinalBandit
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CohortStats:
    """单个 cohort 的 reward 统计"""
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0  # Welford 在线方差累加器

    def update(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def std(self) -> float:
        return (self.m2 / max(self.count, 1)) ** 0.5 if self.count > 1 else 0.5

    def to_dict(self) -> dict[str, Any]:
        return {"count": self.count, "mean": round(self.mean, 4), "std": round(self.std, 4)}


# ============================================================================
# 统一 Reward 公式
# ============================================================================

def unified_reward(
    roas: float = 0.0,
    purchase_rate: float = 0.0,
    ctr: float = 0.0,
    *,
    w_roas: float = 0.5,
    w_purchase: float = 0.3,
    w_ctr: float = 0.2,
) -> float:
    """统一 Reward 公式 (Annealed RL Policy System)

    Reward = w_roas * ROAS_norm + w_purchase * P(Purchase|creative) + w_ctr * CTR_quality

    ROAS_norm: min(roas / 0.4, 1.0)  — 归一化, 0.4 为 ROAS 饱和上限
    purchase_rate: 直接使用 (0~1)
    CTR_quality: ctr / 10.0  — 归一化, 10% CTR 为满分

    Returns:
        float ∈ [0, 1]
    """
    roas_norm = min(roas / 0.4, 1.0) if roas > 0 else 0.0
    ctr_norm = min(ctr / 10.0, 1.0) if ctr > 0 else 0.0
    return w_roas * roas_norm + w_purchase * purchase_rate + w_ctr * ctr_norm


class RewardStabilizer:
    """Reward 稳定器: EMA 平滑 + cohort 归一化

    用法:
        stabilizer = RewardStabilizer(ema_alpha=0.3)
        raw = quality_score  # 0~1
        smoothed = stabilizer.smooth(arm_key, raw)
        normalized = stabilizer.normalize(arm_key, smoothed, cohort="Facebook")
    """

    def __init__(self, ema_alpha: float = 0.3, memory_path: str | Path | None = None):
        """
        Args:
            ema_alpha: EMA 平滑因子 (0.1~0.5). 越小越平滑但越滞后.
            memory_path: 持久化路径 (JSON)
        """
        if not 0.0 < ema_alpha <= 1.0:
            raise ValueError(f"ema_alpha must be in (0,1], got {ema_alpha}")
        self.ema_alpha = ema_alpha

        # EMA 缓存: arm_key → smoothed_reward
        self._ema: dict[str, float] = {}
        # 原始值缓存: 用于 delayed reward 增量修正
        self._raw_cache: dict[str, list[float]] = {}
        # Cohort 统计: cohort_key → CohortStats
        self._cohorts: dict[str, CohortStats] = {}

        self._memory_path = Path(memory_path) if memory_path else None
        if self._memory_path and self._memory_path.exists():
            self._load()

    # ========================================================================
    # EMA 平滑
    # ========================================================================

    def smooth(self, key: str, raw_reward: float) -> float:
        """EMA 平滑 reward。

        ema[t] = alpha * raw[t] + (1-alpha) * ema[t-1]

        首次出现 raw_reward 时直接采用 (无历史).
        """
        if key not in self._ema:
            self._ema[key] = raw_reward
        else:
            self._ema[key] = self.ema_alpha * raw_reward + (1 - self.ema_alpha) * self._ema[key]

        # 缓存原始值用于 delayed reward 修正
        if key not in self._raw_cache:
            self._raw_cache[key] = []
        self._raw_cache[key].append(raw_reward)
        # 只保留最近 10 个原始值
        if len(self._raw_cache[key]) > 10:
            self._raw_cache[key] = self._raw_cache[key][-10:]

        self._save()
        return self._ema[key]

    def get_smoothed(self, key: str) -> float | None:
        """获取当前平滑值 (不更新)"""
        return self._ema.get(key)

    # ========================================================================
    # Cohort 归一化
    # ========================================================================

    def update_cohort(self, cohort_key: str, reward: float) -> None:
        """更新 cohort 统计 (Welford 在线算法)"""
        if cohort_key not in self._cohorts:
            self._cohorts[cohort_key] = CohortStats()
        self._cohorts[cohort_key].update(reward)

    def normalize(self, arm_key: str, smoothed_reward: float, cohort_key: str) -> float:
        """Cohort 归一化: z-score → [0,1] sigmoid。

        如果 cohort 样本不足 (count < 5), 不做归一化, 直接返回原始值.
        """
        stats = self._cohorts.get(cohort_key)
        if stats is None or stats.count < 5:
            return smoothed_reward

        if stats.std < 1e-6:
            return 0.5  # 全同值 → 中性

        # z-score
        z = (smoothed_reward - stats.mean) / stats.std
        # sigmoid 映射到 [0,1]
        normalized = 1.0 / (1.0 + 2.71828 ** (-z))
        return max(0.0, min(1.0, normalized))

    # ========================================================================
    # Delayed Reward 修正
    # ========================================================================

    def correct(self, key: str, new_raw_reward: float) -> float | None:
        """Delayed reward 回填: 用新数据修正 EMA。

        当 D7 ROAS 回流后, 用新值重新计算 EMA.
        返回修正后的 smoothed reward, 或 None (如果 key 不存在).
        """
        if key not in self._ema:
            return None

        # 用新值做一次新的 EMA 更新
        self._ema[key] = self.ema_alpha * new_raw_reward + (1 - self.ema_alpha) * self._ema[key]
        self._save()
        return self._ema[key]

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save(self) -> None:
        if not self._memory_path:
            return
        data = {
            "ema_alpha": self.ema_alpha,
            "ema": self._ema,
            "cohorts": {k: v.to_dict() for k, v in self._cohorts.items()},
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
            self.ema_alpha = data.get("ema_alpha", self.ema_alpha)
            self._ema = data.get("ema", {})
            for k, v in data.get("cohorts", {}).items():
                cs = CohortStats()
                cs.count = v.get("count", 0)
                cs.mean = v.get("mean", 0.0)
                # 从 std 反推 m2
                std = v.get("std", 0.5)
                cs.m2 = (std ** 2) * max(cs.count, 1)
                self._cohorts[k] = cs

    def stats(self) -> dict[str, Any]:
        """诊断输出"""
        return {
            "ema_alpha": self.ema_alpha,
            "tracked_arms": len(self._ema),
            "cohorts": {k: v.to_dict() for k, v in self._cohorts.items()},
        }