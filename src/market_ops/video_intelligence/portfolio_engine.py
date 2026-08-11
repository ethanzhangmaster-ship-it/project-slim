"""Portfolio Engine - 创意组合管理

不是简单的聚类，而是 Facebook Portfolio 思维：
- Safe: 已验证的安全创意，保证基本盘
- Growth: 表现良好的成长创意，扩大测试
- Explore: 全新方向的探索创意，发现新机会

可配置比例：
{
  "safe": 0.5,
  "growth": 0.3,
  "explore": 0.2
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_ALLOCATION = {
    "safe": 0.5,
    "growth": 0.3,
    "explore": 0.2,
}

DEFAULT_BUDGET_ALLOCATION = {
    "safe": 0.6,
    "growth": 0.3,
    "explore": 0.1,
}


@dataclass(slots=True)
class PortfolioBucket:
    name: str
    variants: list[dict] = field(default_factory=list)
    target_count: int = 0
    actual_count: int = 0


class PortfolioEngine:
    """创意组合管理引擎 - 基于 Facebook Portfolio 思维"""

    def __init__(self, allocation_config: dict[str, float] | None = None):
        self.allocation_config = allocation_config or DEFAULT_ALLOCATION.copy()
        self.budget_config = DEFAULT_BUDGET_ALLOCATION.copy()
        self._validate_allocation()

    def _validate_allocation(self) -> None:
        total = sum(self.allocation_config.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Allocation ratios must sum to 1.0, got {total}")

    def allocate(
        self,
        ranked_variants: list[dict],
        total_count: int = 20,
    ) -> dict[str, list[dict]]:
        """分配创意到三个桶

        Safe: Winning Similarity > 80 且 Decision Score > 70
        Growth: Winning Similarity 60-80 且 Decision Score > 65
        Explore: Winning Similarity < 60 或 Novelty > 70

        如果某桶不足，从相邻桶补充
        """
        target_counts = {
            "safe": int(total_count * self.allocation_config["safe"]),
            "growth": int(total_count * self.allocation_config["growth"]),
            "explore": int(total_count * self.allocation_config["explore"]),
        }

        assigned = total_count - sum(target_counts.values())
        if assigned > 0:
            target_counts["safe"] += assigned

        buckets: dict[str, list[dict]] = {
            "safe": [],
            "growth": [],
            "explore": [],
        }

        remaining: list[dict] = []
        for variant in ranked_variants:
            bucket = self.classify_variant(variant)
            if len(buckets[bucket]) < target_counts[bucket]:
                buckets[bucket].append(variant)
            else:
                remaining.append(variant)

        bucket_order = ["safe", "growth", "explore"]
        for i, bucket_name in enumerate(bucket_order):
            while len(buckets[bucket_name]) < target_counts[bucket_name] and remaining:
                best_idx = -1
                best_score = -1
                for idx, v in enumerate(remaining):
                    score = self._bucket_suitability_score(v, bucket_name)
                    if score > best_score:
                        best_score = score
                        best_idx = idx
                if best_idx >= 0:
                    buckets[bucket_name].append(remaining.pop(best_idx))
                else:
                    break

        for bucket_name in bucket_order:
            while len(buckets[bucket_name]) < target_counts[bucket_name] and remaining:
                buckets[bucket_name].append(remaining.pop(0))

        return buckets

    def classify_variant(self, variant: dict) -> str:
        """判断单个variant属于哪个桶"""
        winning_similarity = variant.get("winning_similarity", 0)
        decision_score = variant.get("decision_score", 0)
        novelty = variant.get("novelty", 0)

        if winning_similarity > 80 and decision_score > 70:
            return "safe"
        elif 60 <= winning_similarity <= 80 and decision_score > 65:
            return "growth"
        elif winning_similarity < 60 or novelty > 70:
            return "explore"
        else:
            if decision_score > 65:
                return "growth"
            elif decision_score > 50:
                return "explore"
            else:
                return "explore"

    def _bucket_suitability_score(self, variant: dict, bucket_name: str) -> float:
        """计算variant对某个桶的适合度分数"""
        winning_similarity = variant.get("winning_similarity", 0)
        decision_score = variant.get("decision_score", 0)
        novelty = variant.get("novelty", 0)

        if bucket_name == "safe":
            sim_score = max(0, min(100, winning_similarity - 80)) * 5
            dec_score = max(0, min(100, decision_score - 70)) * 3.33
            return sim_score * 0.6 + dec_score * 0.4
        elif bucket_name == "growth":
            sim_center = 70
            sim_score = 100 - abs(winning_similarity - sim_center) * 2
            dec_score = max(0, min(100, decision_score - 65)) * 2.86
            return max(0, sim_score) * 0.5 + dec_score * 0.5
        else:
            low_sim_score = max(0, 60 - winning_similarity) * 1.67
            high_novelty_score = max(0, novelty - 70) * 3.33
            return low_sim_score * 0.4 + high_novelty_score * 0.6

    def rebalance(
        self,
        portfolio_dict: dict[str, list[dict]],
        target_counts: dict[str, int],
    ) -> dict[str, list[dict]]:
        """再平衡组合"""
        result = {k: list(v) for k, v in portfolio_dict.items()}

        overflow = []
        for bucket_name, target in target_counts.items():
            while len(result[bucket_name]) > target:
                overflow.append(result[bucket_name].pop())

        bucket_order = ["safe", "growth", "explore"]
        for bucket_name in bucket_order:
            target = target_counts.get(bucket_name, 0)
            while len(result[bucket_name]) < target and overflow:
                best_idx = -1
                best_score = -1
                for idx, v in enumerate(overflow):
                    score = self._bucket_suitability_score(v, bucket_name)
                    if score > best_score:
                        best_score = score
                        best_idx = idx
                if best_idx >= 0:
                    result[bucket_name].append(overflow.pop(best_idx))
                else:
                    break

        for bucket_name in bucket_order:
            target = target_counts.get(bucket_name, 0)
            while len(result[bucket_name]) < target and overflow:
                result[bucket_name].append(overflow.pop(0))

        return result

    def get_budget_allocation(
        self,
        portfolio: dict[str, list[dict]],
        total_budget: float = 1000,
    ) -> dict[str, dict[str, Any]]:
        """按比例分配预算

        Safe: 60% 预算（稳定回报）
        Growth: 30% 预算（增长机会）
        Explore: 10% 预算（探索新方向）
        """
        result: dict[str, dict[str, Any]] = {}

        for bucket_name in ["safe", "growth", "explore"]:
            variants = portfolio.get(bucket_name, [])
            count = len(variants)
            bucket_budget = total_budget * self.budget_config[bucket_name]
            per_variant_budget = bucket_budget / count if count > 0 else 0

            result[bucket_name] = {
                "budget": bucket_budget,
                "variant_count": count,
                "per_variant_budget": per_variant_budget,
                "budget_ratio": self.budget_config[bucket_name],
                "variants": [],
            }

            for variant in variants:
                result[bucket_name]["variants"].append({
                    "variant_id": variant.get("variant_id", variant.get("id", "")),
                    "budget": per_variant_budget,
                    "decision_score": variant.get("decision_score", 0),
                })

        return result

    def generate_portfolio_report(
        self,
        portfolio: dict[str, list[dict]],
    ) -> dict[str, Any]:
        """生成组合报告"""
        total = sum(len(v) for v in portfolio.values())

        report: dict[str, Any] = {
            "total_variants": total,
            "buckets": {},
            "summary": {},
        }

        for bucket_name in ["safe", "growth", "explore"]:
            variants = portfolio.get(bucket_name, [])
            count = len(variants)
            ratio = count / total if total > 0 else 0

            avg_decision_score = 0.0
            avg_winning_similarity = 0.0
            avg_novelty = 0.0

            if variants:
                avg_decision_score = sum(v.get("decision_score", 0) for v in variants) / count
                avg_winning_similarity = sum(v.get("winning_similarity", 0) for v in variants) / count
                avg_novelty = sum(v.get("novelty", 0) for v in variants) / count

            report["buckets"][bucket_name] = {
                "count": count,
                "ratio": ratio,
                "target_ratio": self.allocation_config.get(bucket_name, 0),
                "avg_decision_score": round(avg_decision_score, 2),
                "avg_winning_similarity": round(avg_winning_similarity, 2),
                "avg_novelty": round(avg_novelty, 2),
                "top_variants": [
                    {
                        "variant_id": v.get("variant_id", v.get("id", "")),
                        "decision_score": v.get("decision_score", 0),
                        "winning_similarity": v.get("winning_similarity", 0),
                        "novelty": v.get("novelty", 0),
                    }
                    for v in sorted(variants, key=lambda x: x.get("decision_score", 0), reverse=True)[:5]
                ],
            }

        report["summary"] = {
            "safety_score": report["buckets"]["safe"]["ratio"] / self.allocation_config["safe"] if self.allocation_config["safe"] > 0 else 0,
            "growth_score": report["buckets"]["growth"]["ratio"] / self.allocation_config["growth"] if self.allocation_config["growth"] > 0 else 0,
            "exploration_score": report["buckets"]["explore"]["ratio"] / self.allocation_config["explore"] if self.allocation_config["explore"] > 0 else 0,
            "portfolio_health": 0.0,
        }

        health = 0.0
        weights = {"safe": 0.4, "growth": 0.35, "explore": 0.25}
        for bucket_name, weight in weights.items():
            actual = report["buckets"][bucket_name]["ratio"]
            target = self.allocation_config[bucket_name]
            if target > 0:
                ratio = actual / target
                health += weight * min(ratio, 1.0)

        report["summary"]["portfolio_health"] = round(health, 2)

        return report
