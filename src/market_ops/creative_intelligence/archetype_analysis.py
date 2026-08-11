"""Phase 4.1.2 — Archetype Analysis (Creative → Player Archetype 预测+校正).

核心能力：
  1. 预测：基于 Creative DNA 预测会吸引什么玩家类型
  2. 校正：使用真实玩家数据校正预测偏差
  3. 学习：预测 → 实际 → 误差 → 权重修正

Phase 4.1.2 升级：
  - 直接集成 player_intelligence.ArchetypeClassifier
  - 新增 collector_ratio / progression_ratio / power_ratio 快捷属性
  - 支持从 PlayerDNA 实时构建 Archetype 分布
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import ArchetypeProfile


class ArchetypeAnalyzer:
    """Creative → Player Archetype 分析器。

    Phase 4.1.2 升级：直接连接 player_intelligence.ArchetypeClassifier，
    支持从 PlayerDNA + BehaviorFeatures 实时分类。

    预测 + 校正双路径：
      - 预测：规则引擎 + 贝叶斯（E9.6）
      - 实际：真实玩家分类数据（E9.5）
      - 校正：计算误差，学习权重
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ArchetypeProfile] = {}

    # ── Loading: Primary — player_intelligence module ───────

    def load_from_e95(
        self,
        dna_map: dict[str, Any] | None = None,
        features_map: dict[str, Any] | None = None,
        creative_dna_map: dict[str, dict[str, Any]] | None = None,
    ) -> int:
        """从 E9.5 player_intelligence 模块加载 Archetype 分类。

        使用 ArchetypeClassifier 进行玩家分类，
        然后按 Creative ID 聚合 Archetype 分布。

        Args:
            dna_map: {player_id: PlayerDNA}
            features_map: {player_id: BehaviorFeatures}
            creative_dna_map: {creative_id: dna_dict}
        Returns:
            加载的 creative 数量
        """
        try:
            from market_ops.player_intelligence.models import PlayerDNA
            from market_ops.player_intelligence.archetype_classifier import (
                ArchetypeClassifier,
            )
            from market_ops.player_intelligence.behavior_feature_engine import (
                BehaviorFeatureEngine,
            )
        except ImportError:
            return 0

        classifier = ArchetypeClassifier()

        # Build features if not provided
        if features_map is None and dna_map:
            engine = BehaviorFeatureEngine()
            # Convert to proper PlayerDNA dict
            dna_typed: dict[str, Any] = {}
            for pid, val in dna_map.items():
                if isinstance(val, PlayerDNA):
                    dna_typed[pid] = val
                elif isinstance(val, dict):
                    # Try to build minimal PlayerDNA
                    from market_ops.player_intelligence.models import (
                        PlayerDNA, ProgressionDNA, CollectionDNA,
                        PaymentDNA, RetentionDNA,
                    )
                    dna_typed[pid] = PlayerDNA(
                        player_id=pid,
                        creative_id=val.get("creative_id", ""),
                        progression=ProgressionDNA(),
                        collection=CollectionDNA(),
                        payment=PaymentDNA(
                            is_payer=val.get("is_payer", False),
                            total_spend=float(val.get("total_spend", 0)),
                        ),
                        retention=RetentionDNA(
                            d7_retained=val.get("d7_retained", False),
                            d30_retained=val.get("d30_retained", False),
                        ),
                    )
            features_map = engine.extract_all(dna_typed)

        # Classify
        if dna_typed if 'dna_typed' in dir() else dna_map:
            source = dna_typed if 'dna_typed' in dir() else dna_map
            dna_final: dict[str, Any] = {}
            for pid, val in source.items():
                if isinstance(val, PlayerDNA):
                    dna_final[pid] = val
            if dna_final and features_map:
                genomes = classifier.classify_all(dna_final, features_map)
                classifier.build_creative_archetype_matrix(genomes, creative_dna_map)

                # Aggregate by creative_id
                self._profiles = self._aggregate_from_genomes(genomes)

        return len(self._profiles)

    def _aggregate_from_genomes(
        self, genomes: list[Any]
    ) -> dict[str, ArchetypeProfile]:
        """从 PlayerGenome 列表聚合为 ArchetypeProfile."""
        # Group by creative_id
        by_creative: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int))

        for g in genomes:
            cid = getattr(g, "creative_id", "")
            if not cid:
                continue
            arch = getattr(g, "archetype", None)
            if arch and hasattr(arch, "value"):
                by_creative[cid][arch.value] += 1
            elif isinstance(arch, str):
                by_creative[cid][arch] += 1

        profiles: dict[str, ArchetypeProfile] = {}
        for cid, counts in by_creative.items():
            total = sum(counts.values())
            if total == 0:
                continue
            profile = ArchetypeProfile(creative_id=cid)
            profile.actual_collector = round(counts.get("collector", 0) / total, 3)
            profile.actual_power = round(counts.get("power", 0) / total, 3)
            profile.actual_progression = round(counts.get("progression", 0) / total, 3)
            profile.actual_explorer = round(counts.get("explorer", 0) / total, 3)
            profile.actual_casual = round(counts.get("casual", 0) / total, 3)
            profiles[cid] = profile

        return profiles

    # ── Loading: JSON files ─────────────────────────────────

    def load_predictions(
        self, prediction_path: Path | None = None
    ) -> int:
        """加载 E9.6 预测结果."""
        root = Path(__file__).parent.parent.parent.parent
        pp = prediction_path or (
            root / "output" / "creative_matching" / "creative_prediction.json"
        )
        if not pp.exists():
            return 0

        with open(pp, "r", encoding="utf-8") as f:
            predictions = json.load(f)

        if isinstance(predictions, dict):
            predictions = predictions.get("predictions", [])

        loaded = 0
        for pred in predictions:
            if not isinstance(pred, dict):
                continue
            cid = pred.get("creative_id", "")
            if not cid:
                continue

            if cid not in self._profiles:
                self._profiles[cid] = ArchetypeProfile(creative_id=cid)

            arch_pred = pred.get("archetype_prediction", {})
            if isinstance(arch_pred, dict):
                probs = arch_pred.get("probabilities", arch_pred)
                self._profiles[cid].predicted_collector = float(
                    probs.get("collector", probs.get("Collector", 0)))
                self._profiles[cid].predicted_power = float(
                    probs.get("power", probs.get("Power", 0)))
                self._profiles[cid].predicted_progression = float(
                    probs.get("progression", probs.get("Progression", 0)))
                self._profiles[cid].predicted_explorer = float(
                    probs.get("explorer", probs.get("Explorer", 0)))
                self._profiles[cid].predicted_casual = float(
                    probs.get("casual", probs.get("Casual", 0)))
            loaded += 1

        return loaded

    def load_actuals(
        self, player_genomes_path: Path | None = None
    ) -> int:
        """加载 E9.5 真实玩家分类数据."""
        root = Path(__file__).parent.parent.parent.parent
        pgp = player_genomes_path or (
            root / "output" / "player_intelligence" / "player_genomes.json"
        )
        if not pgp.exists():
            return 0

        with open(pgp, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            players = data.get("players", list(data.values()))
        else:
            players = data

        # Group by creative_id and count archetypes
        cohort_archetypes: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int))

        for player in players:
            if not isinstance(player, dict):
                continue
            cid = player.get("creative_id", "")
            if not cid:
                continue

            arch = player.get("archetype", "")
            if not arch:
                pg = player.get("player_genome", {})
                arch = pg.get("archetype", "")
            if not arch:
                continue

            arch = arch.lower()
            cohort_archetypes[cid][arch] += 1

        # Compute actual distribution
        loaded = 0
        for cid, counts in cohort_archetypes.items():
            total = sum(counts.values())
            if total == 0:
                continue

            if cid not in self._profiles:
                self._profiles[cid] = ArchetypeProfile(creative_id=cid)

            profile = self._profiles[cid]
            profile.actual_collector = round(
                counts.get("collector", 0) / total, 3)
            profile.actual_power = round(
                counts.get("power", 0) / total, 3)
            profile.actual_progression = round(
                counts.get("progression", 0) / total, 3)
            profile.actual_explorer = round(
                counts.get("explorer", 0) / total, 3)
            profile.actual_casual = round(
                counts.get("casual", 0) / total, 3)
            loaded += 1

        return loaded

    def calibrate(self) -> int:
        """预测 vs 实际校正 — 计算误差."""
        count = 0
        for profile in self._profiles.values():
            profile.compute_prediction_error()
            count += 1
        return count

    # ── Phase 4.1.2: Archetype convenience properties ──────

    def get_collector_ratio(self, creative_id: str) -> float:
        """获取 Collector 型玩家占比."""
        p = self._profiles.get(creative_id)
        return p.actual_collector if p else 0.0

    def get_progression_ratio(self, creative_id: str) -> float:
        """获取 Progression 型玩家占比."""
        p = self._profiles.get(creative_id)
        return p.actual_progression if p else 0.0

    def get_power_ratio(self, creative_id: str) -> float:
        """获取 Power 型玩家占比."""
        p = self._profiles.get(creative_id)
        return p.actual_power if p else 0.0

    # ── Query ──────────────────────────────────────────────

    def get(self, creative_id: str) -> ArchetypeProfile | None:
        return self._profiles.get(creative_id)

    def get_all(self) -> list[ArchetypeProfile]:
        return list(self._profiles.values())

    def get_by_dominant_archetype(
        self, archetype: str
    ) -> list[ArchetypeProfile]:
        return [
            p for p in self._profiles.values()
            if p.dominant_archetype == archetype
        ]

    def get_high_value_attractors(self) -> list[ArchetypeProfile]:
        """吸引高价值玩家（Collector+Power+Progression > 60%）的创意."""
        return [
            p for p in self._profiles.values()
            if p.high_value_ratio >= 0.60
        ]

    def get_prediction_errors(self) -> list[ArchetypeProfile]:
        """预测偏差最大的创意（学习信号）."""
        return sorted(
            [p for p in self._profiles.values() if p.prediction_accuracy > 0],
            key=lambda p: p.prediction_accuracy,
        )[:20]

    # ── Statistics ─────────────────────────────────────────

    def archetype_stats(self) -> dict[str, Any]:
        """全局 Archetype 统计."""
        all_profiles = list(self._profiles.values())
        if not all_profiles:
            return {"total": 0}

        total_actual = defaultdict(float)
        total_predicted = defaultdict(float)
        n = len(all_profiles)

        for p in all_profiles:
            total_actual["collector"] += p.actual_collector
            total_actual["power"] += p.actual_power
            total_actual["progression"] += p.actual_progression
            total_actual["explorer"] += p.actual_explorer
            total_actual["casual"] += p.actual_casual
            total_predicted["collector"] += p.predicted_collector
            total_predicted["power"] += p.predicted_power
            total_predicted["progression"] += p.predicted_progression
            total_predicted["explorer"] += p.predicted_explorer
            total_predicted["casual"] += p.predicted_casual

        calibrated = [p for p in all_profiles if p.prediction_accuracy > 0]

        return {
            "total": n,
            "calibrated": len(calibrated),
            "avg_prediction_accuracy": round(
                sum(p.prediction_accuracy for p in calibrated) / max(1, len(calibrated)), 3
            ),
            "actual_distribution": {
                k: round(v / n, 3) for k, v in total_actual.items()
            },
            "predicted_distribution": {
                k: round(v / n, 3) for k, v in total_predicted.items()
            },
            "high_value_attractors": len(self.get_high_value_attractors()),
            "dominant_map": {
                arch: len(self.get_by_dominant_archetype(arch))
                for arch in ["collector", "power", "progression", "explorer", "casual"]
            },
        }