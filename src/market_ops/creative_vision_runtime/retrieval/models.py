"""E11.3.4 — Vision Retrieval Models。

VisionVector:         视觉特征向量 + 元数据
SearchResult:         检索结果（相似度 + 记录）
WinnerPattern:        Winner 模式分析结果
SimilarAssetSummary:  相似素材摘要
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VisionVector:
    """视觉特征向量。

    Attributes:
        feature_id:          特征记录 ID
        creative_asset_id:   CreativeEntity 内部 ID
        vector:              8 维特征向量
        hook_score:          开头冲击力 (0-1)
        reward_score:        结尾视觉回报 (0-1)
        is_winner:           是否为 WINNER
        metadata:            扩展元数据
    """

    feature_id: str
    creative_asset_id: str
    vector: list[float]

    hook_score: float = 0.0
    reward_score: float = 0.0
    is_winner: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def dimension(self) -> int:
        return len(self.vector)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "creative_asset_id": self.creative_asset_id,
            "vector": self.vector,
            "hook_score": self.hook_score,
            "reward_score": self.reward_score,
            "is_winner": self.is_winner,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisionVector:
        return cls(
            feature_id=data["feature_id"],
            creative_asset_id=data["creative_asset_id"],
            vector=data["vector"],
            hook_score=float(data.get("hook_score", 0.0)),
            reward_score=float(data.get("reward_score", 0.0)),
            is_winner=bool(data.get("is_winner", False)),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"VisionVector(asset={self.creative_asset_id}, "
            f"dim={self.dimension}, "
            f"winner={self.is_winner})"
        )


@dataclass
class SearchResult:
    """单条检索结果。

    Attributes:
        creative_asset_id:  素材 ID
        feature_id:         特征记录 ID
        similarity:         余弦相似度 (0-1)
        hook_score:         开头冲击力
        reward_score:       结尾视觉回报
        is_winner:          是否为 WINNER
        eagle_filename:     Eagle 文件名
        metadata:           扩展元数据
    """

    creative_asset_id: str
    feature_id: str
    similarity: float

    hook_score: float = 0.0
    reward_score: float = 0.0
    is_winner: bool = False
    eagle_filename: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_asset_id": self.creative_asset_id,
            "feature_id": self.feature_id,
            "similarity": self.similarity,
            "hook_score": self.hook_score,
            "reward_score": self.reward_score,
            "is_winner": self.is_winner,
            "eagle_filename": self.eagle_filename,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"SearchResult(asset={self.creative_asset_id}, "
            f"sim={self.similarity:.3f}, "
            f"winner={self.is_winner})"
        )


@dataclass
class WinnerPattern:
    """Winner 模式分析结果。

    Attributes:
        query_asset_id:      查询素材 ID
        total_similar:       相似素材总数
        winner_count:        WINNER 数量
        winner_ratio:        WINNER 占比
        avg_hook_score:      WINNER 平均 hook_score
        avg_reward_score:    WINNER 平均 reward_score
        avg_brightness:      WINNER 平均亮度
        avg_contrast:        WINNER 平均对比度
        avg_edge_density:    WINNER 平均边缘密度
        avg_saturation:      WINNER 平均饱和度
        avg_color_entropy:   WINNER 平均色彩熵
        recommendations:    推荐模式描述
        top_similar:        最相似的素材列表
    """

    query_asset_id: str = ""
    total_similar: int = 0
    winner_count: int = 0
    winner_ratio: float = 0.0

    avg_hook_score: float = 0.0
    avg_reward_score: float = 0.0
    avg_brightness: float = 0.0
    avg_contrast: float = 0.0
    avg_edge_density: float = 0.0
    avg_saturation: float = 0.0
    avg_color_entropy: float = 0.0

    recommendations: list[str] = field(default_factory=list)
    top_similar: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_asset_id": self.query_asset_id,
            "total_similar": self.total_similar,
            "winner_count": self.winner_count,
            "winner_ratio": self.winner_ratio,
            "avg_hook_score": self.avg_hook_score,
            "avg_reward_score": self.avg_reward_score,
            "avg_brightness": self.avg_brightness,
            "avg_contrast": self.avg_contrast,
            "avg_edge_density": self.avg_edge_density,
            "avg_saturation": self.avg_saturation,
            "avg_color_entropy": self.avg_color_entropy,
            "recommendations": self.recommendations,
            "top_similar": self.top_similar,
        }

    def __repr__(self) -> str:
        return (
            f"WinnerPattern(query={self.query_asset_id}, "
            f"winner_ratio={self.winner_ratio:.1%}, "
            f"n={self.total_similar})"
        )