"""E13.7.12 Pattern Ranking Models — 模式排名数据模型.

Day 7.12 Step 1:
  多维度 Pattern 排名所需的纯数据模型。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RankedPattern:
    """排名后的 Pattern — 携带排名分数和因子分解.

    Attributes:
        pattern_id: 原始 Pattern ID
        rank_score: 综合排名分数 [0, 1]
        original_score: 原始 Pattern.score
        confidence: 置信度
        sample_factor: 样本因子 [0, 1]
        recency_factor: 时效因子 [0, 1]
        reward_stability: 奖励稳定性 [0, 1]
        rank: 排名位置 (1-based)
        created_at: 排名时间
    """
    pattern_id: str = ""
    rank_score: float = 0.0
    original_score: float = 0.0
    confidence: float = 0.0
    sample_factor: float = 0.0
    recency_factor: float = 0.0
    reward_stability: float = 0.0
    rank: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "rank_score": self.rank_score,
            "original_score": self.original_score,
            "confidence": self.confidence,
            "sample_factor": self.sample_factor,
            "recency_factor": self.recency_factor,
            "reward_stability": self.reward_stability,
            "rank": self.rank,
            "created_at": self.created_at,
        }


@dataclass
class RankingResult:
    """排名结果 — 一次完整排名操作的输出.

    Attributes:
        result_id: 结果唯一标识
        total_ranked: 排名总数
        ranked_patterns: 排名后的 Pattern 列表 (按 rank_score 降序)
        top_pattern_id: 排名第一的 Pattern ID
        top_rank_score: 最高排名分数
        avg_rank_score: 平均排名分数
        created_at: 排名时间
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_ranked: int = 0
    ranked_patterns: list[RankedPattern] = field(default_factory=list)
    top_pattern_id: str = ""
    top_rank_score: float = 0.0
    avg_rank_score: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "total_ranked": self.total_ranked,
            "ranked_patterns": [rp.to_dict() for rp in self.ranked_patterns],
            "top_pattern_id": self.top_pattern_id,
            "top_rank_score": self.top_rank_score,
            "avg_rank_score": self.avg_rank_score,
            "created_at": self.created_at,
        }

    @classmethod
    def from_ranked(cls, ranked: list[RankedPattern]) -> "RankingResult":
        n = len(ranked)
        avg = round(sum(rp.rank_score for rp in ranked) / n, 4) if n > 0 else 0.0
        return cls(
            total_ranked=n,
            ranked_patterns=ranked,
            top_pattern_id=ranked[0].pattern_id if n > 0 else "",
            top_rank_score=ranked[0].rank_score if n > 0 else 0.0,
            avg_rank_score=avg,
        )


__all__ = [
    "RankedPattern",
    "RankingResult",
]