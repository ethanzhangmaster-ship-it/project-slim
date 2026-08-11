"""Phase 4.1.3 — Payment Behavior Analyzer (Creative → Payment Pattern).

IAP 核心分析：
  回答："这个创意吸引的用户为什么付费？什么时候付？"

Phase 4.1.3 升级：
  - 新增 D0/D1/D7 付费率时间窗分析
  - 新增 whale_ratio 大R占比
  - 新增 preferred_offers 商品偏好
  - 新增 avg_purchase_count 人均购买次数
  - 接入 Adjust 数据作为付费数据源
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .models import PaymentProfile


class PaymentBehaviorAnalyzer:
    """Creative → Payment Pattern 付费行为分析器。

    Phase 4.1.3 升级：深度付费分析，从玩家付费数据中提取每个 Creative 的：
      - 付费时间窗（D0/D1/D7）
      - 大R占比
      - 商品偏好
      - 付费深度
    """

    def __init__(self) -> None:
        self._profiles: dict[str, PaymentProfile] = {}

    # ── Loading: Primary — Adjust data + player_intelligence ──

    def load_from_adjust_data(
        self,
        adjust_csv_path: Path | None = None,
    ) -> int:
        """从 Adjust 数据直接提取付费模式（Phase 4.1.3 新增）。

        Adjust 数据包含 creative_id → revenue，可以估算付费率。
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

        cohorts: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "revenue": 0.0, "installs": 0, "spend": 0.0,
                "row_count": 0,
            }
        )

        for row in rows:
            cid = row.get("ad_id", "")
            if not cid:
                continue
            c = cohorts[cid]
            c["revenue"] += float(row.get("adj_revenue") or 0)
            c["installs"] += int(float(row.get("adj_installs") or 0))
            c["spend"] += float(row.get("fb_spend") or 0)
            c["row_count"] += 1

        for cid, c in cohorts.items():
            n = c["installs"]
            if n == 0:
                continue
            total_rev = c["revenue"]
            # Estimate payer metrics from revenue
            estimated_payers = max(1, int(n * 0.08))  # 8% payer rate estimate
            arppu = total_rev / estimated_payers if estimated_payers > 0 else 0
            arpu = total_rev / n

            self._profiles[cid] = PaymentProfile(
                creative_id=cid,
                payer_count=estimated_payers,
                payer_rate=round(estimated_payers / n, 3),
                total_revenue=round(total_rev, 2),
                arppu=round(arppu, 2),
                arpu=round(arpu, 2),
                avg_purchase_count=round(estimated_payers / max(n, 1) * 3, 1),  # estimate
                d0_payer_rate=0.0,
                d1_payer_rate=0.0,
                d7_payer_rate=0.0,
                whale_ratio=0.0,
            )

        return len(self._profiles)

    def load_from_player_data(
        self,
        player_genomes_path: Path | None = None,
        adjust_csv_path: Path | None = None,
    ) -> int:
        """从玩家基因组数据 + Adjust 数据提取付费模式。

        Phase 4.1.3 升级：同时加载 Adjust 数据补充付费信息。
        """
        root = Path(__file__).parent.parent.parent.parent
        pgp = player_genomes_path or (
            root / "output" / "player_intelligence" / "player_genomes.json"
        )

        players: list[dict[str, Any]] = []
        if pgp.exists():
            with open(pgp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                players = data.get("players", list(data.values()))
            else:
                players = data

        # Group by creative_id
        cohorts: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for player in players:
            if not isinstance(player, dict):
                continue
            cid = player.get("creative_id", "")
            if cid:
                cohorts[cid].append(player)

        # Build profiles
        for cid, cohort_players in cohorts.items():
            self._profiles[cid] = self._compute_payment_profile(
                cid, cohort_players)

        # Also try loading Adjust data for revenue validation
        if adjust_csv_path or (root / "output" / "p04_platform_analysis" / "p04_merged_fb_adjust.csv").exists():
            self._enrich_with_adjust(root)

        return len(self._profiles)

    def _enrich_with_adjust(self, root: Path) -> None:
        """用 Adjust 数据补充付费信息."""
        csv_path = root / "output" / "p04_platform_analysis" / "p04_merged_fb_adjust.csv"
        if not csv_path.exists():
            return

        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        adjust_revenue: dict[str, float] = defaultdict(float)
        for row in rows:
            cid = row.get("ad_id", "")
            if cid:
                adjust_revenue[cid] += float(row.get("adj_revenue") or 0)

        for cid, profile in self._profiles.items():
            if cid in adjust_revenue and adjust_revenue[cid] > profile.total_revenue:
                profile.total_revenue = round(adjust_revenue[cid], 2)
                if profile.payer_count > 0:
                    profile.arppu = round(adjust_revenue[cid] / profile.payer_count, 2)
                if profile.payer_rate > 0 and profile.player_count > 0:
                    profile.arpu = round(adjust_revenue[cid] / profile.player_count, 2)

    @property
    def player_count(self) -> int:
        """Helper for _enrich_with_adjust."""
        return 0

    def _compute_payment_profile(
        self, creative_id: str, players: list[dict[str, Any]]
    ) -> PaymentProfile:
        """计算付费画像（Phase 4.1.3 升级）."""
        n = len(players)
        if n == 0:
            return PaymentProfile(creative_id=creative_id)

        # Extract payment data
        payers = []
        total_revenue = 0.0
        total_purchases = 0
        first_purchase_days = []
        purchase_frequencies = []
        order_values = []
        purchase_counts = []
        trigger_dist: dict[str, float] = defaultdict(float)
        offer_dist: dict[str, int] = defaultdict(int)

        # D0/D1/D7 payer tracking
        d0_payers = 0
        d1_payers = 0
        d7_payers = 0

        # Whale tracking
        whale_count = 0
        WHALE_THRESHOLD = 50.0

        for p in players:
            pd = p.get("payment_dna", {})
            if not isinstance(pd, dict):
                continue

            is_payer = pd.get("is_payer", False)
            total_spend = float(pd.get("total_spend", 0))

            if is_payer and total_spend > 0:
                payers.append(p)
                total_revenue += total_spend

                fp_day = pd.get("first_purchase_day", -1)
                if isinstance(fp_day, (int, float)) and fp_day >= 0:
                    first_purchase_days.append(float(fp_day))
                    if fp_day == 0:
                        d0_payers += 1
                    if fp_day <= 1:
                        d1_payers += 1
                    if fp_day <= 7:
                        d7_payers += 1

                freq = pd.get("purchase_frequency", 0)
                if isinstance(freq, (int, float)):
                    purchase_frequencies.append(float(freq))

                aov = pd.get("avg_order_value", 0)
                if isinstance(aov, (int, float)) and aov > 0:
                    order_values.append(float(aov))

                total_p = pd.get("total_purchases", 0)
                if isinstance(total_p, (int, float)):
                    purchase_counts.append(float(total_p))

                # Whale detection
                if total_spend >= WHALE_THRESHOLD:
                    whale_count += 1

                triggers = pd.get("purchase_triggers", [])
                if isinstance(triggers, list):
                    for t in triggers:
                        trigger_dist[str(t)] += 1
                        offer_dist[str(t)] += 1

            # Also check player_genome payment_profile
            pg = p.get("payment_profile", {})
            if isinstance(pg, dict):
                pp = pg
                if pp.get("is_payer") and not is_payer:
                    payers.append(p)
                    total_revenue += float(pp.get("predicted_ltv_d30", 0))

        payer_count = len(payers)
        payer_rate = round(payer_count / n, 3) if n > 0 else 0.0
        arppu = round(total_revenue / payer_count, 2) if payer_count > 0 else 0.0
        arpu = round(total_revenue / n, 2) if n > 0 else 0.0

        avg_first_day = round(
            sum(first_purchase_days) / len(first_purchase_days), 1
        ) if first_purchase_days else 0.0

        avg_freq = round(
            sum(purchase_frequencies) / len(purchase_frequencies), 2
        ) if purchase_frequencies else 0.0

        avg_aov = round(
            sum(order_values) / len(order_values), 2
        ) if order_values else 0.0

        avg_purchase_count = round(
            sum(purchase_counts) / len(purchase_counts), 2
        ) if purchase_counts else 0.0

        # D0/D1/D7 payer rates
        d0_payer_rate = round(d0_payers / n, 4) if n > 0 else 0.0
        d1_payer_rate = round(d1_payers / n, 4) if n > 0 else 0.0
        d7_payer_rate = round(d7_payers / n, 4) if n > 0 else 0.0

        # Whale ratio
        whale_ratio = round(whale_count / n, 4) if n > 0 else 0.0

        # Normalize trigger distribution
        total_triggers = sum(trigger_dist.values())
        if total_triggers > 0:
            trigger_dist_norm = {
                k: round(v / total_triggers, 3)
                for k, v in trigger_dist.items()
            }
        else:
            trigger_dist_norm = {}

        # Preferred offers (top by count)
        preferred_offers = [
            offer for offer, _ in sorted(offer_dist.items(), key=lambda x: -x[1])[:5]
        ]

        return PaymentProfile(
            creative_id=creative_id,
            payer_count=payer_count,
            payer_rate=payer_rate,
            total_revenue=round(total_revenue, 2),
            arppu=arppu,
            arpu=arpu,
            avg_first_purchase_day=avg_first_day,
            avg_purchase_frequency=avg_freq,
            avg_order_value=avg_aov,
            avg_purchase_count=avg_purchase_count,
            d0_payer_rate=d0_payer_rate,
            d1_payer_rate=d1_payer_rate,
            d7_payer_rate=d7_payer_rate,
            whale_ratio=whale_ratio,
            trigger_distribution=trigger_dist_norm,
            preferred_offers=preferred_offers,
        )

    # ── Query ──────────────────────────────────────────────

    def get(self, creative_id: str) -> PaymentProfile | None:
        return self._profiles.get(creative_id)

    def get_all(self) -> list[PaymentProfile]:
        return list(self._profiles.values())

    def get_healthy_monetizers(self) -> list[PaymentProfile]:
        """付费健康度高的创意."""
        return [
            p for p in self._profiles.values()
            if p.is_healthy_monetization
        ]

    def get_by_dominant_trigger(self, trigger: str) -> list[PaymentProfile]:
        """按主导付费触发筛选."""
        return [
            p for p in self._profiles.values()
            if p.dominant_trigger == trigger
        ]

    def get_whales(self, min_whale_ratio: float = 0.05) -> list[PaymentProfile]:
        """大R占比高的创意（Phase 4.1.3 新增）."""
        return [
            p for p in self._profiles.values()
            if p.whale_ratio >= min_whale_ratio
        ]

    def get_early_converters(self, min_d0_rate: float = 0.01) -> list[PaymentProfile]:
        """D0 付费率高的创意（Phase 4.1.3 新增）."""
        return [
            p for p in self._profiles.values()
            if p.d0_payer_rate >= min_d0_rate
        ]

    def rank_by_health(self, n: int = 10) -> list[PaymentProfile]:
        """按付费健康度排序."""
        return sorted(
            self._profiles.values(),
            key=lambda p: p.payment_health_score,
            reverse=True,
        )[:n]

    def rank_by_arppu(self, n: int = 10) -> list[PaymentProfile]:
        """按 ARPPU 排序."""
        return sorted(
            self._profiles.values(),
            key=lambda p: p.arppu,
            reverse=True,
        )[:n]

    def rank_by_whale_ratio(self, n: int = 10) -> list[PaymentProfile]:
        """按大R占比排序（Phase 4.1.3 新增）."""
        return sorted(
            self._profiles.values(),
            key=lambda p: p.whale_ratio,
            reverse=True,
        )[:n]

    # ── Statistics ─────────────────────────────────────────

    def payment_stats(self) -> dict[str, Any]:
        """全局付费统计（Phase 4.1.3 升级）."""
        all_profiles = list(self._profiles.values())
        if not all_profiles:
            return {"total_creatives": 0}

        total_payers = sum(p.payer_count for p in all_profiles)
        total_revenue = sum(p.total_revenue for p in all_profiles)

        # Aggregate trigger distribution
        trigger_agg: dict[str, float] = defaultdict(float)
        for p in all_profiles:
            for trigger, ratio in p.trigger_distribution.items():
                trigger_agg[trigger] += ratio

        return {
            "total_creatives": len(all_profiles),
            "total_payers": total_payers,
            "total_revenue": round(total_revenue, 2),
            "avg_payer_rate": round(
                sum(p.payer_rate for p in all_profiles) / len(all_profiles), 3
            ),
            "avg_arppu": round(
                sum(p.arppu for p in all_profiles if p.arppu > 0)
                / max(1, len([p for p in all_profiles if p.arppu > 0])), 2
            ),
            "avg_arpu": round(
                sum(p.arpu for p in all_profiles) / len(all_profiles), 2
            ),
            "avg_d0_payer_rate": round(
                sum(p.d0_payer_rate for p in all_profiles) / len(all_profiles), 4
            ),
            "avg_d1_payer_rate": round(
                sum(p.d1_payer_rate for p in all_profiles) / len(all_profiles), 4
            ),
            "avg_d7_payer_rate": round(
                sum(p.d7_payer_rate for p in all_profiles) / len(all_profiles), 4
            ),
            "avg_whale_ratio": round(
                sum(p.whale_ratio for p in all_profiles) / len(all_profiles), 4
            ),
            "healthy_monetizers": len(self.get_healthy_monetizers()),
            "whale_creatives": len(self.get_whales()),
            "early_converters": len(self.get_early_converters()),
            "dominant_triggers": dict(
                sorted(trigger_agg.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "avg_payment_health": round(
                sum(p.payment_health_score for p in all_profiles) / len(all_profiles), 3
            ),
        }