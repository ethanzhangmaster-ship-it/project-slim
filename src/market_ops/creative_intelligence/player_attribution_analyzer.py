"""Phase 4.1.1 — Player Attribution Analyzer (Creative → Player Cohort).

Creative → Player Cohort 归因分析。
回答："这个创意吸引来的是什么玩家？"

接入 E9.4: CreativePlayerAttribution + IAPGenomeFitnessCalculator
从 player_intelligence 模块读取归因数据，构建 PlayerAttributionProfile。

Phase 4.1.1 升级：
  - 直接集成 player_intelligence.CreativePlayerAttribution
  - 支持 Adjust 数据作为 IAP 数据源
  - 新增 avg_revenue 字段
  - 支持从 PlayerDNAEngine 的实时数据构建归因
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import PlayerAttributionProfile


class PlayerAttributionAnalyzer:
    """Creative → Player Cohort 归因分析器。

    Phase 4.1.1 升级：直接连接 player_intelligence 模块，
    支持从 PlayerDNAEngine 和 CreativePlayerAttribution 获取归因数据。

    数据源优先级：
      1. player_intelligence.CreativePlayerAttribution (E9.4)
      2. JSON 文件降级（player_genomes.json）
    """

    def __init__(self) -> None:
        self._attribution_map: dict[str, PlayerAttributionProfile] = {}
        self._loaded = False

    # ── Loading: Primary — player_intelligence module ───────

    def load_from_e94(
        self,
        player_dna_map: dict[str, Any] | None = None,
        creative_dna_map: dict[str, dict[str, Any]] | None = None,
    ) -> int:
        """从 E9.4 player_intelligence 模块加载归因。

        使用 CreativePlayerAttribution 进行 Creative → Player Cohort 归因。
        这是 Adjust 数据的主要入口。

        Args:
            player_dna_map: {player_id: PlayerDNA} 从 PlayerDNAEngine
            creative_dna_map: {creative_id: dna_dict} 从 creative_dna_master.json
        Returns:
            加载的 creative 数量
        """
        try:
            from market_ops.player_intelligence.models import PlayerDNA
            from market_ops.player_intelligence.creative_player_attribution import (
                CreativePlayerAttribution,
            )
        except ImportError:
            return 0

        attribution = CreativePlayerAttribution()

        # Load creative DNA
        if creative_dna_map:
            attribution._creative_dna = creative_dna_map
        else:
            attribution.load_creative_dna()

        # Build PlayerDNA map if provided as dict
        if player_dna_map:
            # Convert dict values to PlayerDNA if needed
            dna_map: dict[str, Any] = {}
            for pid, val in player_dna_map.items():
                if isinstance(val, PlayerDNA):
                    dna_map[pid] = val
                elif isinstance(val, dict):
                    dna_map[pid] = self._dict_to_player_dna(pid, val)
            attribution.attribute_player_dna(dna_map)
            attribution.compute_genome_fitness()

        # Extract cohorts
        cohorts = attribution.get_creative_cohorts()
        for cid, cohort_dict in cohorts.items():
            self._attribution_map[cid] = self._cohort_to_profile(cid, cohort_dict)

        self._loaded = True
        return len(self._attribution_map)

    @staticmethod
    def _dict_to_player_dna(player_id: str, data: dict[str, Any]) -> Any:
        """Convert dict to PlayerDNA (lazy import)."""
        from market_ops.player_intelligence.models import (
            PlayerDNA, ProgressionDNA, CollectionDNA,
            PaymentDNA, RetentionDNA,
        )

        pd_data = data.get("payment", data.get("payment_dna", {}))
        ret_data = data.get("retention", data.get("retention_dna", {}))
        prog_data = data.get("progression", data.get("progression_dna", {}))
        coll_data = data.get("collection", data.get("collection_dna", {}))

        dna = PlayerDNA(
            player_id=player_id,
            creative_id=data.get("creative_id", ""),
            progression=ProgressionDNA(
                merge_count=int(prog_data.get("merge_count", 0)),
                merge_speed=float(prog_data.get("merge_speed", 0)),
                max_level=int(prog_data.get("max_level", 0)),
                areas_unlocked=int(prog_data.get("areas_unlocked", 0)),
                buildings_restored=int(prog_data.get("buildings_restored", 0)),
                progression_velocity=float(prog_data.get("progression_velocity", 0)),
            ),
            collection=CollectionDNA(
                items_collected=int(coll_data.get("items_collected", 0)),
                rare_items=int(coll_data.get("rare_items", 0)),
                collections_completed=int(coll_data.get("collections_completed", 0)),
                collection_rate=float(coll_data.get("collection_rate", 0)),
                rare_item_interest=float(coll_data.get("rare_item_interest", 0)),
                completion_bias=float(coll_data.get("completion_bias", 0)),
            ),
            payment=PaymentDNA(
                is_payer=pd_data.get("is_payer", False),
                first_purchase_day=int(pd_data.get("first_purchase_day", -1)),
                total_purchases=int(pd_data.get("total_purchases", 0)),
                total_spend=float(pd_data.get("total_spend", 0)),
                purchase_frequency=float(pd_data.get("purchase_frequency", 0)),
                avg_order_value=float(pd_data.get("avg_order_value", 0)),
                purchase_triggers=pd_data.get("purchase_triggers", []),
            ),
            retention=RetentionDNA(
                days_active=int(ret_data.get("days_active", 0)),
                total_sessions=int(ret_data.get("total_sessions", 0)),
                session_frequency=float(ret_data.get("session_frequency", 0)),
                d1_retained=ret_data.get("d1_retained", False),
                d7_retained=ret_data.get("d7_retained", False),
                d30_retained=ret_data.get("d30_retained", False),
                return_behavior=ret_data.get("return_behavior", "unknown"),
                event_participation=int(ret_data.get("event_participation", 0)),
            ),
            lifetime_days=int(data.get("lifetime_days", 0)),
            d30_ltv=float(data.get("d30_ltv", pd_data.get("total_spend", 0))),
            d90_ltv=float(data.get("d90_ltv", 0)),
        )
        dna.compute_derived()
        return dna

    @staticmethod
    def _cohort_to_profile(
        creative_id: str, cohort_dict: dict[str, Any]
    ) -> PlayerAttributionProfile:
        """Convert PlayerCohort dict to PlayerAttributionProfile."""
        avg_revenue = (
            cohort_dict.get("avg_d30_ltv", 0) * cohort_dict.get("player_count", 0)
        )
        return PlayerAttributionProfile(
            creative_id=creative_id,
            player_count=int(cohort_dict.get("player_count", 0)),
            payer_count=int(cohort_dict.get("payer_count", 0)),
            payer_rate=float(cohort_dict.get("payer_rate", 0)),
            d1_retention=float(cohort_dict.get("d1_retention", 0)),
            d7_retention=float(cohort_dict.get("d7_retention", 0)),
            d30_retention=float(cohort_dict.get("d30_retention", 0)),
            avg_merge_count=float(cohort_dict.get("avg_merge_count", 0)),
            avg_merge_speed=float(cohort_dict.get("avg_merge_speed", 0)),
            avg_areas_unlocked=float(cohort_dict.get("avg_areas_unlocked", 0)),
            avg_collection_rate=float(cohort_dict.get("avg_collection_rate", 0)),
            avg_progression_velocity=float(cohort_dict.get("avg_progression_velocity", 0)),
            top_payment_triggers=[
                (t.get("trigger", ""), t.get("count", 0))
                for t in cohort_dict.get("top_payment_triggers", [])
            ],
        )

    # ── Loading: Fallback — JSON files ─────────────────────

    def load_from_player_data(
        self,
        player_genomes_path: Path | None = None,
        creative_dna_path: Path | None = None,
    ) -> int:
        """从玩家基因组数据加载归因（JSON 降级路径）。

        Args:
            player_genomes_path: E9.5 输出的 player_genomes.json
            creative_dna_path: E9.6 输出的 creative_prediction.json
        Returns:
            加载的 creative 数量
        """
        root = Path(__file__).parent.parent.parent.parent

        # Load player genomes (E9.5)
        pg_path = player_genomes_path or (
            root / "output" / "player_intelligence" / "player_genomes.json"
        )
        player_genomes = {}
        if pg_path.exists():
            with open(pg_path, "r", encoding="utf-8") as f:
                player_genomes = json.load(f)

        # Load creative DNA (E9.6)
        cd_path = creative_dna_path or (
            root / "output" / "creative_analysis" / "creative_prediction.json"
        )
        creative_dna = {}
        if cd_path.exists():
            with open(cd_path, "r", encoding="utf-8") as f:
                creative_dna = json.load(f)

        # Build attribution
        self._attribution_map = self._build_attribution(
            player_genomes, creative_dna
        )
        self._loaded = True
        return len(self._attribution_map)

    def load_from_adjust_data(
        self,
        adjust_csv_path: Path | None = None,
    ) -> int:
        """从 Adjust 数据直接构建归因（Phase 4.1.1 新增）。

        Adjust 数据包含 creative_id → player_id → revenue 映射。
        这是 IAP 产品的核心数据源。

        Args:
            adjust_csv_path: Adjust 导出 CSV 路径
        Returns:
            加载的 creative 数量
        """
        root = Path(__file__).parent.parent.parent.parent
        csv_path = adjust_csv_path or (
            root / "output" / "p04_platform_analysis" / "p04_merged_fb_adjust.csv"
        )
        if not csv_path.exists():
            return 0

        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Group by creative_id
        cohorts: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"player_count": 0, "payer_count": 0, "total_revenue": 0.0,
                     "total_installs": 0, "total_spend": 0.0}
        )

        for row in rows:
            cid = row.get("ad_id", "")
            if not cid:
                continue
            adj_rev = float(row.get("adj_revenue") or 0)
            adj_inst = int(float(row.get("adj_installs") or 0))
            fb_spend = float(row.get("fb_spend") or 0)

            c = cohorts[cid]
            c["player_count"] += adj_inst
            c["total_revenue"] += adj_rev
            c["total_installs"] += adj_inst
            c["total_spend"] += fb_spend

        # Build profiles
        for cid, c in cohorts.items():
            n = c["player_count"]
            if n == 0:
                continue
            total_rev = c["total_revenue"]
            payer_rate_est = min(c["total_installs"] / max(n, 1) * 0.08, 1.0)  # estimate

            self._attribution_map[cid] = PlayerAttributionProfile(
                creative_id=cid,
                player_count=n,
                payer_count=int(n * payer_rate_est),
                payer_rate=round(payer_rate_est, 3),
                d1_retention=0.0,  # Adjust doesn't have retention
                d7_retention=0.0,
                d30_retention=0.0,
            )

        self._loaded = True
        return len(self._attribution_map)

    def _build_attribution(
        self,
        player_genomes: dict[str, Any],
        creative_dna_list: list[dict[str, Any]],
    ) -> dict[str, PlayerAttributionProfile]:
        """从玩家基因组数据构建归因映射."""
        # Group players by creative_id
        cohorts: dict[str, list[dict[str, Any]]] = defaultdict(list)

        # Handle player_genomes as dict or list
        if isinstance(player_genomes, dict):
            if "players" in player_genomes:
                players = player_genomes["players"]
            else:
                players = list(player_genomes.values())
        else:
            players = player_genomes

        for player in players:
            if isinstance(player, dict):
                creative_id = player.get("creative_id", "")
                if creative_id:
                    cohorts[creative_id].append(player)

        # Build profiles
        profiles: dict[str, PlayerAttributionProfile] = {}
        for creative_id, players_list in cohorts.items():
            profile = self._compute_cohort(creative_id, players_list)
            profiles[creative_id] = profile

        return profiles

    def _compute_cohort(
        self, creative_id: str, players: list[dict[str, Any]]
    ) -> PlayerAttributionProfile:
        """计算一个 creative 的玩家群体指标."""
        n = len(players)
        if n == 0:
            return PlayerAttributionProfile(creative_id=creative_id)

        # Payers
        payers = [
            p for p in players
            if p.get("is_payer", False) or p.get("payment_dna", {}).get("is_payer", False)
        ]
        payer_count = len(payers)

        # Revenue
        total_revenue = sum(
            float(p.get("payment_dna", {}).get("total_spend", 0))
            for p in payers
        )
        avg_revenue = total_revenue / payer_count if payer_count > 0 else 0.0

        # Retention
        d1_retained = sum(
            1 for p in players
            if p.get("retention_dna", {}).get("d1_retained", False)
            or p.get("d1_retained", False)
        )
        d7_retained = sum(
            1 for p in players
            if p.get("retention_dna", {}).get("d7_retained", False)
            or p.get("d7_retained", False)
        )
        d30_retained = sum(
            1 for p in players
            if p.get("retention_dna", {}).get("d30_retained", False)
            or p.get("d30_retained", False)
        )

        # Behavior averages
        def _avg_behavior(key: str, default: float = 0.0) -> float:
            vals = []
            for p in players:
                v = p.get(key, default)
                if isinstance(v, (int, float)):
                    vals.append(float(v))
            return sum(vals) / len(vals) if vals else 0.0

        # Payment triggers
        trigger_counts: dict[str, int] = defaultdict(int)
        for p in payers:
            pd = p.get("payment_dna", {})
            triggers = pd.get("purchase_triggers", [])
            if isinstance(triggers, list):
                for t in triggers:
                    trigger_counts[str(t)] += 1
        top_triggers = sorted(trigger_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return PlayerAttributionProfile(
            creative_id=creative_id,
            player_count=n,
            payer_count=payer_count,
            payer_rate=round(payer_count / n, 3) if n > 0 else 0.0,
            d1_retention=round(d1_retained / n, 3) if n > 0 else 0.0,
            d7_retention=round(d7_retained / n, 3) if n > 0 else 0.0,
            d30_retention=round(d30_retained / n, 3) if n > 0 else 0.0,
            avg_merge_count=_avg_behavior("merge_count"),
            avg_merge_speed=_avg_behavior("merge_speed"),
            avg_areas_unlocked=_avg_behavior("areas_unlocked"),
            avg_collection_rate=_avg_behavior("collection_rate"),
            avg_progression_velocity=_avg_behavior("progression_velocity"),
            top_payment_triggers=top_triggers,
        )

    # ── Query ──────────────────────────────────────────────

    def get(self, creative_id: str) -> PlayerAttributionProfile | None:
        return self._attribution_map.get(creative_id)

    def get_all(self) -> list[PlayerAttributionProfile]:
        return list(self._attribution_map.values())

    def get_high_value_cohorts(self) -> list[PlayerAttributionProfile]:
        """筛选高价值玩家群体."""
        return [p for p in self._attribution_map.values() if p.is_high_value_cohort]

    def rank_by_cohort_quality(self, n: int = 10) -> list[PlayerAttributionProfile]:
        """按玩家群体质量排序."""
        return sorted(
            self._attribution_map.values(),
            key=lambda p: p.cohort_quality_score,
            reverse=True,
        )[:n]

    # ── Statistics ─────────────────────────────────────────

    def cohort_stats(self) -> dict[str, Any]:
        """全局群体统计."""
        all_profiles = list(self._attribution_map.values())
        if not all_profiles:
            return {"total_creatives": 0}

        total_players = sum(p.player_count for p in all_profiles)
        total_payers = sum(p.payer_count for p in all_profiles)

        return {
            "total_creatives": len(all_profiles),
            "total_players": total_players,
            "total_payers": total_payers,
            "overall_payer_rate": round(total_payers / total_players, 3) if total_players > 0 else 0,
            "avg_d30_retention": round(
                sum(p.d30_retention for p in all_profiles) / len(all_profiles), 3
            ),
            "high_value_cohorts": len(self.get_high_value_cohorts()),
            "avg_cohort_quality": round(
                sum(p.cohort_quality_score for p in all_profiles) / len(all_profiles), 3
            ),
        }