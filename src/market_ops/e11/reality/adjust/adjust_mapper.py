"""E11.6.2 Adjust Creative Mapper — Adjust creative_id → E11 genome_id 映射。

连接 Adjust 素材归因与 E11 Genome 体系：

  Adjust creative_id → CreativeEntity → Creative DNA → Genome ID

当前阶段使用注册表模式（registry），后续可升级为数据库查询。

映射逻辑：
  1. 精确匹配: creative_id → genome_id
  2. 前缀匹配: creative_id 前缀 → 批量匹配
  3. 未匹配: 返回空字符串（需人工审核）
"""

from __future__ import annotations

from typing import Any


# ═══════════════════════════════════════════════════════════
# AdjustCreativeMapper
# ═══════════════════════════════════════════════════════════

class AdjustCreativeMapper:
    """Adjust creative_id → E11 genome_id 映射器。

    维护 creative_id 到 genome_id 的映射关系，支持：
      - 精确映射注册
      - 批量映射
      - 前缀匹配
      - 反向查询

    Usage:
        mapper = AdjustCreativeMapper()
        mapper.register("creative_905", "genome_001")
        genome_id = mapper.map_creative("creative_905")
        # → "genome_001"
    """

    def __init__(self) -> None:
        self._creative_map: dict[str, str] = {}
        self._genome_map: dict[str, set[str]] = {}  # genome_id → {creative_id, ...}
        self._unmapped: set[str] = set()

    # ── 注册 ──────────────────────────────────────────

    def register(
        self,
        creative_id: str,
        genome_id: str,
    ) -> None:
        """注册 creative_id → genome_id 映射。

        Args:
            creative_id: Adjust 素材 ID
            genome_id: E11 Genome ID
        """
        self._creative_map[creative_id] = genome_id
        if genome_id not in self._genome_map:
            self._genome_map[genome_id] = set()
        self._genome_map[genome_id].add(creative_id)

        # 从未匹配集合中移除
        self._unmapped.discard(creative_id)

    def register_batch(
        self,
        mappings: dict[str, str],
    ) -> None:
        """批量注册 creative_id → genome_id 映射。

        Args:
            mappings: {creative_id: genome_id, ...}
        """
        for creative_id, genome_id in mappings.items():
            self.register(creative_id, genome_id)

    # ── 查询 ──────────────────────────────────────────

    def map_creative(self, creative_id: str) -> str:
        """将 Adjust creative_id 映射到 E11 genome_id。

        查找顺序：
          1. 精确匹配
          2. 前缀匹配（逐步缩短）
          3. 返回空字符串

        Args:
            creative_id: Adjust 素材 ID

        Returns:
            genome_id，未匹配时返回 ""
        """
        if not creative_id:
            return ""

        # 1. 精确匹配
        if creative_id in self._creative_map:
            return self._creative_map[creative_id]

        # 2. 前缀匹配（从最长开始）
        parts = creative_id.rsplit("_", 1)
        if len(parts) == 2 and parts[0] in self._creative_map:
            return self._creative_map[parts[0]]

        # 3. 未匹配
        self._unmapped.add(creative_id)
        return ""

    def map_batch(self, creative_ids: list[str]) -> dict[str, str]:
        """批量映射 creative_id → genome_id。

        Args:
            creative_ids: Adjust 素材 ID 列表

        Returns:
            {creative_id: genome_id}
        """
        return {cid: self.map_creative(cid) for cid in creative_ids}

    # ── 反向查询 ──────────────────────────────────────

    def get_creatives_for_genome(self, genome_id: str) -> list[str]:
        """获取某个 Genome 对应的所有 creative_id。

        Args:
            genome_id: E11 Genome ID

        Returns:
            creative_id 列表
        """
        if genome_id in self._genome_map:
            return sorted(self._genome_map[genome_id])
        return []

    def get_genome_for_creative(self, creative_id: str) -> str:
        """与 map_creative 相同，语义更清晰的别名。"""
        return self.map_creative(creative_id)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_map": self._creative_map,
            "unmapped": sorted(self._unmapped),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdjustCreativeMapper:
        mapper = cls()
        creative_map = data.get("creative_map", {})
        if creative_map:
            mapper.register_batch(creative_map)
        mapper._unmapped = set(data.get("unmapped", []))
        return mapper

    # ── 查询属性 ──────────────────────────────────────

    @property
    def mapped_count(self) -> int:
        """已映射的 creative 数量。"""
        return len(self._creative_map)

    @property
    def unmapped_count(self) -> int:
        """未匹配的 creative 数量。"""
        return len(self._unmapped)

    @property
    def genome_count(self) -> int:
        """已关联的 genome 数量。"""
        return len(self._genome_map)

    def get_unmapped(self) -> list[str]:
        """获取所有未匹配的 creative_id，用于人工审核。"""
        return sorted(self._unmapped)

    def __repr__(self) -> str:
        return (
            f"AdjustCreativeMapper(mapped={self.mapped_count}, "
            f"unmapped={self.unmapped_count}, "
            f"genomes={self.genome_count})"
        )