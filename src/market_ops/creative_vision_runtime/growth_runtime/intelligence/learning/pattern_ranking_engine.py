"""E13.7.12 Pattern Ranking Engine — 模式排名引擎.

Day 7.12 Step 2:
  多维度 Pattern 排名引擎，对 PatternMemory 列表进行综合评分排名。

核心职责:
  1. 计算复合 rank_score (5 因子加权)
  2. 按 rank_score 降序排序并分配排名位置
  3. 输出 RankingResult

排名公式:
  rank_score = score × 0.30 + confidence × 0.25 + sample_factor × 0.20
             + recency_factor × 0.15 + reward_stability × 0.10

因子计算:
  - sample_factor = min(log(samples+1) / log(100), 1.0)
  - recency_factor = max(0, 1.0 - days_since_last_seen / 90)
  - reward_stability = 1.0 - std_reward / max(avg_reward, 0.01)

边缘情况:
  - 空列表 → 返回空 RankingResult
  - last_seen 为 None/空 → recency_factor = 0.0
  - avg_reward 为 0 → reward_stability = 0.5
  - std_reward 为 0 → reward_stability = 1.0
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternMemory
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.pattern_ranking_models import (
    RankedPattern,
    RankingResult,
)


class PatternRankingEngine:
    """模式排名引擎 — 多维度因子加权排名.

    用法:
        engine = PatternRankingEngine()
        result = engine.rank(patterns)
        # result.top_pattern_id, result.ranked_patterns, ...
    """

    def rank(self, patterns: list[PatternMemory]) -> RankingResult:
        """对 Pattern 列表进行排名，返回 RankingResult.

        Args:
            patterns: PatternMemory 列表

        Returns:
            RankingResult: 包含排名结果
        """
        if not patterns:
            return RankingResult()

        ranked: list[RankedPattern] = []
        for p in patterns:
            ranked.append(self._compute_ranked_pattern(p))

        # 按 rank_score 降序排序
        ranked.sort(key=lambda rp: rp.rank_score, reverse=True)

        # 分配 rank (1-based)
        for i, rp in enumerate(ranked):
            rp.rank = i + 1

        return RankingResult.from_ranked(ranked)

    # ── 因子计算 ──────────────────────────────────────────────────

    def _compute_ranked_pattern(self, pattern: PatternMemory) -> RankedPattern:
        """计算单个 Pattern 的排名因子并构建 RankedPattern."""
        perf = pattern.performance
        sample_factor = self._calc_sample_factor(perf.samples)
        recency_factor = self._calc_recency_factor(perf.last_seen)
        reward_stability = self._calc_reward_stability(perf.avg_reward, perf.std_reward)
        rank_score = self._compute_rank_score(
            score=pattern.score,
            confidence=pattern.confidence,
            sample_factor=sample_factor,
            recency_factor=recency_factor,
            reward_stability=reward_stability,
        )
        return RankedPattern(
            pattern_id=pattern.pattern_id,
            rank_score=round(rank_score, 4),
            original_score=pattern.score,
            confidence=pattern.confidence,
            sample_factor=round(sample_factor, 4),
            recency_factor=round(recency_factor, 4),
            reward_stability=round(reward_stability, 4),
        )

    @staticmethod
    def _compute_rank_score(
        score: float,
        confidence: float,
        sample_factor: float,
        recency_factor: float,
        reward_stability: float,
    ) -> float:
        """复合排名分数计算.

        公式:
          rank_score = score × 0.30 + confidence × 0.25 + sample_factor × 0.20
                     + recency_factor × 0.15 + reward_stability × 0.10
        """
        return (
            score * 0.30
            + confidence * 0.25
            + sample_factor * 0.20
            + recency_factor * 0.15
            + reward_stability * 0.10
        )

    @staticmethod
    def _calc_sample_factor(samples: int) -> float:
        """样本因子 — 对数平滑，避免大样本过度主导.

        公式: min(log(samples+1) / log(100), 1.0)
        """
        if samples <= 0:
            return 0.0
        return round(min(math.log(samples + 1) / math.log(100), 1.0), 4)

    @staticmethod
    def _calc_recency_factor(last_seen: str | None) -> float:
        """时效因子 — 最近出现的时间衰减.

        公式: max(0, 1.0 - days_since_last_seen / 90)

        边缘情况:
          - last_seen 为 None 或空字符串 → 0.0
          - 解析失败 → 0.0
        """
        if not last_seen:
            return 0.0

        try:
            # 处理 ISO 格式: "2024-01-15T10:30:00+00:00" 或 "2024-01-15T10:30:00Z"
            last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - last_seen_dt
            days = delta.total_seconds() / 86400.0
            return round(max(0.0, 1.0 - days / 90.0), 4)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _calc_reward_stability(avg_reward: float, std_reward: float) -> float:
        """奖励稳定性 — 标准差越小越稳定.

        公式: 1.0 - std_reward / max(avg_reward, 0.01)

        边缘情况:
          - avg_reward 为 0 → 0.5 (默认)
          - std_reward 为 0 → 1.0 (完全稳定)
        """
        if std_reward == 0.0:
            return 1.0
        if avg_reward == 0.0:
            return 0.5
        stability = 1.0 - std_reward / max(avg_reward, 0.01)
        return round(max(0.0, min(1.0, stability)), 4)


__all__ = [
    "PatternRankingEngine",
]