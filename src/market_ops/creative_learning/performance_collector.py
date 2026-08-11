"""E9.7: Performance Collector — Unified interface for real ad performance data.

Supports: Facebook Ads, Adjust, AppsFlyer, Firebase, MAX (via CSV fallback)
+ MockPerformanceGenerator for testing the learning loop.

The mock generator creates "real" campaign results with systematic biases
embedded in specific DNA features, so the learning engine can discover them.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.creative_learning.schemas import CreativeActualPerformance


# ═══════════════════════════════════════════════════════════
# Performance Collector
# ═══════════════════════════════════════════════════════════

class PerformanceCollector:
    """Unified interface for collecting real campaign performance data.

    Usage:
        collector = PerformanceCollector()
        collector.load_from_csv("ads_performance.csv")
        # or
        collector.load_from_mock(predictions, seed=42)
    """

    def __init__(self) -> None:
        self._performances: dict[str, CreativeActualPerformance] = {}

    def load_from_csv(self, path: str | Path) -> int:
        """Load performance data from CSV file."""
        import csv
        p = Path(path)
        if not p.exists():
            return 0

        count = 0
        with open(p, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                perf = CreativeActualPerformance(
                    creative_id=row.get("creative_id", row.get("ad_id", "")),
                    data_source="csv",
                    installs=int(row.get("installs", 0)),
                    spend=float(row.get("spend", 0)),
                    revenue=float(row.get("revenue", 0)),
                    total_players=int(row.get("total_players", row.get("installs", 0))),
                    d30_retention=float(row.get("d30_retention", 0)),
                    payer_rate=float(row.get("payer_rate", 0)),
                    ltv_d30=float(row.get("ltv_d30", row.get("ltv", 0))),
                )
                self._performances[perf.creative_id] = perf
                count += 1

        return count

    def load_from_json(self, path: str | Path) -> int:
        """Load performance data from JSON file."""
        p = Path(path)
        if not p.exists():
            return 0

        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)

        count = 0
        for item in data:
            perf = CreativeActualPerformance(
                creative_id=item.get("creative_id", ""),
                data_source=item.get("data_source", "json"),
                installs=item.get("installs", 0),
                spend=item.get("spend", 0),
                revenue=item.get("revenue", 0),
                total_players=item.get("total_players", 0),
                d30_retention=item.get("d30_retention", 0),
                payer_rate=item.get("payer_rate", 0),
                ltv_d30=item.get("ltv_d30", 0),
                archetype_distribution=item.get("archetype_distribution", {}),
            )
            self._performances[perf.creative_id] = perf
            count += 1

        return count

    def add_performance(self, perf: CreativeActualPerformance) -> None:
        self._performances[perf.creative_id] = perf

    def get_performance(self, creative_id: str) -> CreativeActualPerformance | None:
        return self._performances.get(creative_id)

    @property
    def performances(self) -> dict[str, CreativeActualPerformance]:
        return self._performances

    def get_summary(self) -> dict[str, Any]:
        if not self._performances:
            return {"status": "empty", "total_creatives": 0}

        perfs = list(self._performances.values())
        n = len(perfs)
        avg_ltv = sum(p.ltv_d30 for p in perfs) / n
        avg_payer = sum(p.payer_rate for p in perfs) / n
        avg_retention = sum(p.d30_retention for p in perfs) / n

        return {
            "total_creatives": n,
            "total_installs": sum(p.installs for p in perfs),
            "total_spend": round(sum(p.spend for p in perfs), 2),
            "total_revenue": round(sum(p.revenue for p in perfs), 2),
            "avg_ltv_d30": round(avg_ltv, 2),
            "avg_payer_rate": round(avg_payer, 3),
            "avg_d30_retention": round(avg_retention, 3),
        }


# ═══════════════════════════════════════════════════════════
# Mock Performance Generator
# ═══════════════════════════════════════════════════════════

class MockPerformanceGenerator:
    """Generates synthetic "real" campaign performance for testing.

    Creates performance data with systematic biases embedded in
    specific DNA features, allowing the learning engine to discover
    which features are over/under-valued.

    The biases are:
      - "challenge" hook: +25% more Power players than predicted
      - "emotional" hook: +15% more Collector players
      - "curiosity" hook: +20% more Explorer players
      - "merge" mechanism: +10% more Progression players
      - "power" reward: +30% higher LTV than predicted
      - "collection" reward: +15% higher LTV
    """

    # DNA feature biases: (feature_name, archetype, bias_factor)
    _BIASES = {
        # Hook type → archetype biases
        "challenge": [("power", 0.25, "challenge_hook_drives_power")],
        "emotional": [("collector", 0.15, "emotional_attachment_drives_collection")],
        "curiosity": [("explorer", 0.20, "curiosity_drives_exploration")],
        "surprise": [("explorer", 0.12, "surprise_drives_exploration")],
        "rescue": [("power", 0.10, "rescue_hook_drives_power")],
        "transformation": [("power", 0.15, "transformation_drives_power")],
        "secret": [("explorer", 0.12, "secret_hook_drives_exploration")],
        "collection": [("collector", 0.18, "collection_hook_drives_collector")],
        "progression": [("progression", 0.15, "progression_hook_drives_progression")],

        # Mechanism → archetype biases
        "merge": [("progression", 0.10, "merge_mechanic_drives_progression")],
        "merge2": [("progression", 0.10, "merge_mechanic_drives_progression")],
        "progression_chain": [("progression", 0.12, "progression_chain_drives_progression")],

        # Reward → LTV biases
        "power": [("ltv", 0.30, "power_reward_increases_ltv")],
        "evolution": [("ltv", 0.20, "evolution_reward_increases_ltv")],
        "collection": [("ltv", 0.15, "collection_reward_increases_ltv")],
        "rare_item": [("ltv", 0.25, "rare_item_increases_ltv")],
        "baby_dragon": [("ltv", 0.22, "baby_dragon_increases_ltv")],
        "discovery": [("ltv", 0.18, "discovery_reward_increases_ltv")],
        "unlock": [("ltv", 0.12, "unlock_reward_increases_ltv")],
    }

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def generate(
        self,
        predictions: list[dict[str, Any]],
        noise_scale: float = 0.08,
    ) -> list[CreativeActualPerformance]:
        """Generate mock "actual" performance with systematic biases.

        Args:
            predictions: list of E9.6 CreativePrediction.to_dict() results
            noise_scale: random noise magnitude (0-1)

        Returns:
            list of CreativeActualPerformance with embedded biases
        """
        performances = []

        for pred in predictions:
            creative_id = pred.get("creative_id", "")
            genome_name = pred.get("creative_genome_name", "")
            expected = pred.get("expected", {})
            dna_features = pred.get("dna_features", {}).get("features", {})
            source_dna = pred.get("dna_features", {}).get("source_dna", {})

            # Base values from prediction
            base_ltv = expected.get("ltv", 10.0)
            base_payer_rate = expected.get("payer_rate", 0.15)
            base_retention = expected.get("d30_retention", 0.3)

            # Start with predicted archetype distribution
            pred_arch = pred.get("prediction", {})
            arch_dist = {}
            for arch, detail in pred_arch.items():
                arch_dist[arch] = detail.get("adjusted_probability", 0.2)

            # Apply systematic biases from DNA features
            ltv_bias = 0.0
            applied_biases = []

            hook_type = source_dna.get("hook", "")
            reward_type = source_dna.get("reward", "")
            mechanism_type = source_dna.get("mechanism", "")

            for feature_value, bias_list in self._BIASES.items():
                # Check if this creative has this DNA feature
                has_feature = (
                    feature_value == hook_type
                    or feature_value == reward_type
                    or feature_value == mechanism_type
                )
                if not has_feature:
                    continue

                for target, bias_amount, reason in bias_list:
                    if target in ("power", "collector", "explorer", "progression", "casual"):
                        # Archetype bias: shift distribution
                        if target in arch_dist:
                            # Take from casual first, then proportionally from others
                            if "casual" in arch_dist and arch_dist.get("casual", 0) > bias_amount:
                                arch_dist["casual"] = max(0, arch_dist["casual"] - bias_amount)
                            else:
                                # Reduce others proportionally
                                others = {k: v for k, v in arch_dist.items() if k != target}
                                total_others = sum(others.values())
                                if total_others > 0:
                                    scale = (total_others - bias_amount) / total_others
                                    for k in others:
                                        arch_dist[k] = max(0.01, arch_dist[k] * scale)

                            arch_dist[target] = min(0.95, arch_dist.get(target, 0) + bias_amount)
                            applied_biases.append(f"{feature_value}→{target}+{bias_amount:.0%}")

                    elif target == "ltv":
                        ltv_bias += bias_amount * base_ltv
                        applied_biases.append(f"{feature_value}→LTV+{bias_amount:.0%}")

            # Add random noise
            for arch in arch_dist:
                noise = self._rng.uniform(-noise_scale, noise_scale)
                arch_dist[arch] = max(0.01, min(0.95, arch_dist[arch] + noise))

            # Renormalize archetype distribution
            total = sum(arch_dist.values())
            if total > 0:
                arch_dist = {k: v / total for k, v in arch_dist.items()}

            # Apply noise to metrics
            actual_ltv = base_ltv + ltv_bias + self._rng.uniform(-noise_scale * base_ltv, noise_scale * base_ltv)
            actual_ltv = max(0.1, actual_ltv)
            actual_payer = base_payer_rate + self._rng.uniform(-noise_scale, noise_scale)
            actual_payer = max(0.001, min(0.95, actual_payer))
            actual_retention = base_retention + self._rng.uniform(-noise_scale, noise_scale)
            actual_retention = max(0.01, min(0.95, actual_retention))

            # Generate campaign metrics
            installs = self._rng.randint(500, 10000)
            spend = installs * self._rng.uniform(0.5, 3.0)
            revenue = actual_ltv * installs * actual_payer

            perf = CreativeActualPerformance(
                creative_id=creative_id,
                data_source="mock",
                installs=installs,
                spend=round(spend, 2),
                revenue=round(revenue, 2),
                total_players=installs,
                d30_retention=round(actual_retention, 3),
                payer_rate=round(actual_payer, 3),
                ltv_d30=round(actual_ltv, 2),
                archetype_distribution=arch_dist,
                raw_player_count=installs,
            )
            performances.append(perf)

        return performances

    def generate_for_collector(
        self,
        creative_ids: list[str],
        predictions: dict[str, dict[str, Any]],
    ) -> dict[str, CreativeActualPerformance]:
        """Generate mock performances and return as dict."""
        pred_list = [
            predictions.get(cid, {"creative_id": cid})
            for cid in creative_ids
        ]
        perfs = self.generate(pred_list)
        return {p.creative_id: p for p in perfs}