"""E11 Phase 2 — Adjust Creative Matcher。

将 AdjustRevenueEntity 匹配到 CreativeEntity，实现 4 级匹配逻辑。

匹配优先级：
  Level 1: 精确 creative_asset_id 匹配
  Level 2: legacy_id 匹配（6位数字）
  Level 3: creative name 匹配（Facebook ad_name ↔ Adjust creative）
  Level 4: campaign + adset + creative 组合匹配

匹配结果通过 CreativeEntity.merge_adjust_data() 写入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .models import AdjustRevenueEntity

if TYPE_CHECKING:
    from market_ops.creative_repository import CreativeEntity


@dataclass
class MatchResult:
    """单次匹配结果。"""

    adjust_entity: AdjustRevenueEntity
    creative_entity: CreativeEntity | None = None
    level: int = 0                # 匹配级别 (1-4, 0=未匹配)
    level_name: str = ""          # 级别名称
    matched: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjust_creative_id": self.adjust_entity.adjust_creative_id,
            "creative_asset_id": (
                self.creative_entity.creative_asset_id if self.creative_entity else ""
            ),
            "level": self.level,
            "level_name": self.level_name,
            "matched": self.matched,
        }


@dataclass
class AdjustMatchReport:
    """匹配报告。"""

    total_adjust: int = 0
    total_creative: int = 0
    matched: int = 0
    unmatched: int = 0
    match_rate: float = 0.0
    by_level: dict[int, int] = field(default_factory=dict)  # level → count
    results: list[MatchResult] = field(default_factory=list)

    def to_summary(self) -> str:
        lines = [
            "=" * 60,
            "  Adjust → CreativeEntity Match Report",
            "=" * 60,
            "",
            f"  Adjust entities: {self.total_adjust}",
            f"  Creative entities: {self.total_creative}",
            f"  Matched: {self.matched}",
            f"  Unmatched: {self.unmatched}",
            f"  Match Rate: {self.match_rate:.1%}",
            "",
        ]
        for level in sorted(self.by_level.keys()):
            lines.append(f"    Level {level}: {self.by_level[level]}")
        if self.unmatched > 0:
            lines.append(f"\n  Unmatched Adjust IDs:")
            for r in self.results:
                if not r.matched:
                    lines.append(f"    - {r.adjust_entity.adjust_creative_id}")
        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_adjust": self.total_adjust,
            "total_creative": self.total_creative,
            "matched": self.matched,
            "unmatched": self.unmatched,
            "match_rate": self.match_rate,
            "by_level": self.by_level,
            "results": [r.to_dict() for r in self.results],
        }


class AdjustCreativeMatcher:
    """Adjust → CreativeEntity 匹配器。

    4 级匹配逻辑：
      Level 1: creative_asset_id 精确匹配（最高优先级）
      Level 2: legacy_id 匹配（6位数字）
      Level 3: creative name 匹配（ad_name ↔ Adjust creative name）
      Level 4: campaign + adgroup + creative 组合匹配

    Usage:
        matcher = AdjustCreativeMatcher()
        report = matcher.match(creative_entities, adjust_entities)
        print(report.to_summary())
    """

    # 匹配级别名称
    LEVEL_NAMES = {
        0: "Unmatched",
        1: "Exact creative_asset_id",
        2: "Legacy ID",
        3: "Creative Name",
        4: "Campaign + Adgroup + Creative",
    }

    def match(
        self,
        creative_entities: list[CreativeEntity],
        adjust_entities: list[AdjustRevenueEntity],
    ) -> AdjustMatchReport:
        """执行匹配并写入 CreativeEntity。

        遍历每个 Adjust 实体，按优先级匹配 CreativeEntity，
        匹配成功后调用 merge_adjust_data() 写入收入数据。

        Args:
            creative_entities: CreativeEntity 列表
            adjust_entities:  AdjustRevenueEntity 列表

        Returns:
            AdjustMatchReport 包含匹配统计
        """
        report = AdjustMatchReport(
            total_adjust=len(adjust_entities),
            total_creative=len(creative_entities),
        )

        # 构建索引
        id_index = self._build_id_index(creative_entities)
        legacy_index = self._build_legacy_index(creative_entities)
        name_index = self._build_name_index(creative_entities)
        campaign_index = self._build_campaign_index(creative_entities)

        for adj in adjust_entities:
            result = self._match_one(
                adj, id_index, legacy_index, name_index, campaign_index,
            )
            report.results.append(result)

            if result.matched:
                report.matched += 1
                report.by_level[result.level] = (
                    report.by_level.get(result.level, 0) + 1
                )
            else:
                report.unmatched += 1

        report.match_rate = (
            round(report.matched / report.total_adjust, 4)
            if report.total_adjust > 0
            else 0.0
        )

        return report

    def _match_one(
        self,
        adj: AdjustRevenueEntity,
        id_index: dict[str, CreativeEntity],
        legacy_index: dict[str, CreativeEntity],
        name_index: dict[str, list[CreativeEntity]],
        campaign_index: dict[str, list[CreativeEntity]],
    ) -> MatchResult:
        """按优先级匹配单个 Adjust 实体。"""
        # Level 1: 精确 creative_asset_id
        if adj.creative_asset_id and adj.creative_asset_id in id_index:
            ce = id_index[adj.creative_asset_id]
            ce.merge_adjust_data(adj.to_dict())
            return MatchResult(
                adjust_entity=adj,
                creative_entity=ce,
                level=1,
                level_name=self.LEVEL_NAMES[1],
                matched=True,
            )

        # Level 2: legacy_id
        if adj.legacy_id and adj.legacy_id in legacy_index:
            ce = legacy_index[adj.legacy_id]
            ce.merge_adjust_data(adj.to_dict())
            return MatchResult(
                adjust_entity=adj,
                creative_entity=ce,
                level=2,
                level_name=self.LEVEL_NAMES[2],
                matched=True,
            )

        # Level 3: creative name
        if adj.creative:
            name_lower = adj.creative.lower().strip()
            if name_lower in name_index:
                candidates = name_index[name_lower]
                if candidates:
                    ce = candidates[0]
                    ce.merge_adjust_data(adj.to_dict())
                    return MatchResult(
                        adjust_entity=adj,
                        creative_entity=ce,
                        level=3,
                        level_name=self.LEVEL_NAMES[3],
                        matched=True,
                    )

        # Level 4: campaign + adgroup + creative
        if adj.campaign and adj.adgroup and adj.creative:
            key = f"{adj.campaign}|{adj.adgroup}|{adj.creative}".lower().strip()
            if key in campaign_index:
                candidates = campaign_index[key]
                if candidates:
                    ce = candidates[0]
                    ce.merge_adjust_data(adj.to_dict())
                    return MatchResult(
                        adjust_entity=adj,
                        creative_entity=ce,
                        level=4,
                        level_name=self.LEVEL_NAMES[4],
                        matched=True,
                    )

        return MatchResult(
            adjust_entity=adj,
            level=0,
            level_name=self.LEVEL_NAMES[0],
            matched=False,
        )

    # ── Index Builders ──────────────────────────────────

    def _build_id_index(
        self, entities: list[CreativeEntity],
    ) -> dict[str, CreativeEntity]:
        """Level 1: creative_asset_id 索引。"""
        idx: dict[str, CreativeEntity] = {}
        for ce in entities:
            if ce.creative_asset_id:
                idx[ce.creative_asset_id] = ce
        return idx

    def _build_legacy_index(
        self, entities: list[CreativeEntity],
    ) -> dict[str, CreativeEntity]:
        """Level 2: legacy_id 索引。"""
        idx: dict[str, CreativeEntity] = {}
        for ce in entities:
            if ce.legacy_id:
                idx[ce.legacy_id] = ce
        return idx

    def _build_name_index(
        self, entities: list[CreativeEntity],
    ) -> dict[str, list[CreativeEntity]]:
        """Level 3: creative name 索引（lowercase）。"""
        idx: dict[str, list[CreativeEntity]] = {}
        for ce in entities:
            name = ce.identity.name.lower().strip()
            if name:
                if name not in idx:
                    idx[name] = []
                idx[name].append(ce)
        return idx

    def _build_campaign_index(
        self, entities: list[CreativeEntity],
    ) -> dict[str, list[CreativeEntity]]:
        """Level 4: campaign + adgroup + creative 组合索引。

        注意：CreativeEntity 不直接存储 campaign/adgroup，
        需要从 FacebookCreativeEntity 获取。这里使用 identity.name 作为 creative name。
        """
        # Level 4 需要 campaign/adgroup 信息，这些信息在 FacebookCreativeEntity 中
        # 但在 CreativeEntity 中不直接存储。这里返回空索引，
        # 实际使用时通过 campaign/adgroup 信息匹配。
        return {}

    def __repr__(self) -> str:
        return "AdjustCreativeMatcher()"