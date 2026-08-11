"""Evolution Quality Gate — 演化质量关卡

对每个 DNA Variant 执行 4 项检查:
1. Winner Similarity (DNA 维度重叠度) — 确保变异不偏离 Winner 太远
2. Diversity (差异度) — 确保变异有足够新意
3. Gameplay Preservation (玩法保留度) — 确保核心玩法不变
4. Reward Visibility (奖励可见度) — 确保奖励区域足够突出

然后计算加权 Evolution Score，过滤不通过的变体。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import (
    OUTPUT_DIR, DNA_EVOLUTION_DIR,
    EVO_SIMILARITY_MIN, EVO_DIVERSITY_MIN,
    EVO_GAMEPLAY_MIN, EVO_REWARD_MIN,
    EVOLUTION_SCORE_WEIGHTS, ensure_dirs,
)


class EvolutionChecker:
    """演化质量关卡"""

    def __init__(self):
        self.results: List[dict] = []

    def check_similarity(self, variant: dict, winner_dna: dict) -> float:
        """计算 Winner Similarity — DNA 维度重叠度

        基于原始 DNA 与变异 DNA 在各维度上的重叠程度计算。
        每个维度按子字段逐一比较，值相同计分，值不同不计分。
        保留维度自动满分，变异维度按实际匹配程度计分。

        Returns:
            similarity score (0.0 ~ 1.0), 要求 > 0.75
        """
        source_dna = variant.get("original_dna", winner_dna)
        mutated_dna = variant.get("mutated_dna", {})

        dimensions = [
            # (dim_key, sub_fields, weight)
            ("composition", ["gameplay_area.ratio", "reward_area.ratio",
                            "character_area.ratio", "background_area.ratio",
                            "gameplay_area.position", "reward_area.position",
                            "character_area.position", "background_area.position"], 0.20),
            ("gameplay", ["type", "elements_count"], 0.25),
            ("reward", ["type", "elements_count"], 0.20),
            ("style", ["color_palette", "lighting", "camera", "render_style"], 0.15),
            ("hook", ["value"], 0.10),
            ("layout", ["value"], 0.10),
        ]

        total_score = 0.0
        total_weight = 0.0

        for dim_key, sub_fields, weight in dimensions:
            total_weight += weight
            matches = 0
            valid_count = 0

            for field in sub_fields:
                orig_val = self._get_field(source_dna, dim_key, field)
                mut_val = self._get_field(mutated_dna, dim_key, field)

                if orig_val is not None and mut_val is not None:
                    valid_count += 1
                    if self._values_equal(orig_val, mut_val):
                        matches += 1

            if valid_count > 0:
                dim_score = matches / valid_count
            else:
                dim_score = 1.0  # 无可比较字段, 默认满分

            total_score += dim_score * weight

        # Normalize to 0-1 range
        if total_weight > 0:
            return round(total_score / total_weight, 4)

        return 1.0

    def check_diversity(self, variant: dict, winner_dna: dict) -> float:
        """计算 Diversity — 变异差异度

        基于策略定义的变异维度占总可变异维度的比例。
        保留维度不计入 diversity 计算 (因为预期不变)。

        Returns:
            diversity score (0.0 ~ 1.0), 要求 > 0.25
        """
        source_dna = variant.get("original_dna", winner_dna)
        mutated_dna = variant.get("mutated_dna", {})

        # 获取策略的 mutate 列表, 只在这些维度上计算 diversity
        strategy_key = variant.get("strategy", "")
        from .mutation_rules import VARIANT_STRATEGIES
        strategy = VARIANT_STRATEGIES.get(strategy_key, {})
        mutate_dims = strategy.get("mutate", ["style", "composition", "reward", "layout", "gameplay"])

        # 动态构建字段列表: 只包含策略指定的变异维度
        dim_fields_map = {
            "composition": [
                "gameplay_area.ratio", "reward_area.ratio",
                "character_area.ratio", "background_area.ratio",
                "gameplay_area.position", "reward_area.position",
                "character_area.position", "background_area.position",
            ],
            "gameplay": ["type", "elements_count"],
            "reward": ["type", "elements_count"],
            "style": ["color_palette", "lighting", "camera", "render_style"],
            "layout": ["value"],
            "hook": ["value"],
        }

        all_fields = []
        for dim_key in mutate_dims:
            fields = dim_fields_map.get(dim_key, [])
            for field in fields:
                all_fields.append((dim_key, field))

        if not all_fields:
            return 0.0

        changes = 0
        for dim_key, field in all_fields:
            orig_val = self._get_field(source_dna, dim_key, field)
            mut_val = self._get_field(mutated_dna, dim_key, field)

            if orig_val is not None and mut_val is not None:
                if not self._values_equal(orig_val, mut_val):
                    changes += 1

        diversity = changes / len(all_fields)
        return round(diversity, 4)

    def check_gameplay_preservation(self, variant: dict, winner_dna: dict) -> float:
        """计算 Gameplay Preservation — 玩法保留度

        检查 gameplay type 是否保留、elements 是否重叠。

        Returns:
            gameplay preservation score (0.0 ~ 1.0), 要求 > 0.85
        """
        source_dna = variant.get("original_dna", winner_dna)
        mutated_dna = variant.get("mutated_dna", {})

        # Gameplay type 匹配 (权重 0.7)
        source_type = source_dna.get("gameplay", {}).get("type", "")
        mut_type = mutated_dna.get("gameplay", {}).get("type", "")
        type_score = 1.0 if source_type == mut_type and source_type else 0.0

        # Gameplay elements 重叠 (权重 0.3)
        source_elems = set(source_dna.get("gameplay", {}).get("elements", []))
        mut_elems = set(mutated_dna.get("gameplay", {}).get("elements", []))

        if source_elems:
            overlap = len(source_elems & mut_elems)
            jaccard = overlap / len(source_elems | mut_elems) if (source_elems | mut_elems) else 1.0
        else:
            jaccard = 1.0

        gp_score = 0.7 * type_score + 0.3 * jaccard
        return round(gp_score, 4)

    def check_reward_visibility(self, variant: dict) -> float:
        """计算 Reward Visibility — 奖励可见度

        基于 mutated_dna 中 reward area 的比例。
        20% 是合格线, 30% 以上满分。

        Returns:
            reward visibility score (0.0 ~ 1.0)
        """
        mutated_dna = variant.get("mutated_dna", {})

        reward_ratio = mutated_dna.get("composition", {}).get("reward_area", {}).get("ratio", 0.0)

        # Ratio 映射: 0% → 0.0, 20% → 0.5, 30%+ → 1.0
        if reward_ratio >= 0.30:
            return 1.0
        elif reward_ratio <= 0.10:
            return 0.0
        else:
            # 线性映射: 0.10 → 0.0, 0.30 → 1.0
            return round((reward_ratio - 0.10) / 0.20, 4)

    def calculate_evolution_score(self, variant: dict,
                                  similarity: float,
                                  gameplay_preserve: float,
                                  reward_visibility: float) -> float:
        """计算加权 Evolution Score

        EvolutionScore = 0.35 × WinnerSimilarity + 0.25 × GameplayPreserve
                       + 0.20 × RewardVisibility + 0.20 × Novelty

        其中 Novelty = Diversity (差异度), 越高越好。
        """
        diversity = variant.get("_diversity", 0.0)

        weights = EVOLUTION_SCORE_WEIGHTS
        score = (
            weights["winner_similarity"] * similarity +
            weights["gameplay_preserve"] * gameplay_preserve +
            weights["reward_visibility"] * reward_visibility +
            weights["novelty"] * diversity
        )
        return round(score, 4)

    def evaluate_variant(self, variant: dict, winner_dna: dict) -> dict:
        """对单个 variant 执行完整评估

        Returns:
            评估结果 dict
        """
        similarity = self.check_similarity(variant, winner_dna)
        diversity = self.check_diversity(variant, winner_dna)
        gameplay_preserve = self.check_gameplay_preservation(variant, winner_dna)
        reward_visibility = self.check_reward_visibility(variant)

        evolution_score = self.calculate_evolution_score(
            variant, similarity, gameplay_preserve, reward_visibility
        )

        # 存储中间结果供后续使用
        variant["_similarity"] = similarity
        variant["_diversity"] = diversity
        variant["_gameplay_preserve"] = gameplay_preserve
        variant["_reward_visibility"] = reward_visibility
        variant["_evolution_score"] = evolution_score

        # 四项检查
        passes = (
            similarity >= EVO_SIMILARITY_MIN and
            diversity >= EVO_DIVERSITY_MIN and
            gameplay_preserve >= EVO_GAMEPLAY_MIN and
            reward_visibility >= EVO_REWARD_MIN
        )

        failures = []
        if similarity < EVO_SIMILARITY_MIN:
            failures.append(f"Similarity({similarity:.4f}) < {EVO_SIMILARITY_MIN}")
        if diversity < EVO_DIVERSITY_MIN:
            failures.append(f"Diversity({diversity:.4f}) < {EVO_DIVERSITY_MIN}")
        if gameplay_preserve < EVO_GAMEPLAY_MIN:
            failures.append(f"GameplayPreserve({gameplay_preserve:.4f}) < {EVO_GAMEPLAY_MIN}")
        if reward_visibility < EVO_REWARD_MIN:
            failures.append(f"RewardVisibility({reward_visibility:.4f}) < {EVO_REWARD_MIN}")

        return {
            "creative_id": variant.get("creative_id", "unknown"),
            "winner_similarity": similarity,
            "diversity": diversity,
            "gameplay_preserve": gameplay_preserve,
            "reward_visibility": reward_visibility,
            "evolution_score": evolution_score,
            "pass": passes,
            "failures": failures,
        }

    def filter_variants(self, variants: List[dict],
                        winner_dnas: Optional[Dict[str, dict]] = None) -> Tuple[List[dict], List[dict]]:
        """过滤不通过的变体

        Args:
            variants: variant 列表 (含 original_dna 和 mutated_dna)
            winner_dnas: {winner_asset_id: winner_data} 索引, 可选

        Returns:
            (passed_variants, failed_variants)
        """
        # 构建 winner DNA 索引（用于给 variant 提供 original_dna 引用）
        if winner_dnas is None:
            winner_dnas = {}

        self.results = []
        passed = []
        failed = []

        for v in variants:
            winner_id = v.get("winner_source", {}).get("asset_id", "")
            winner_dna = winner_dnas.get(winner_id, v.get("original_dna", {}))

            result = self.evaluate_variant(v, winner_dna)
            self.results.append(result)

            if result["pass"]:
                passed.append(v)
            else:
                failed.append(v)

        num_total = len(variants)
        num_passed = len(passed)
        pass_rate = (num_passed / num_total * 100) if num_total > 0 else 0

        print(f"\n[EvolutionChecker] Quality Gate 结果:")
        print(f"  Total variants: {num_total}")
        print(f"  Passed: {num_passed} ({pass_rate:.1f}%)")
        print(f"  Failed: {len(failed)} ({100 - pass_rate:.1f}%)")

        # 打印失败原因摘要
        if failed:
            fail_reasons = {}
            for r in self.results:
                if not r["pass"]:
                    for f in r["failures"]:
                        reason_type = f.split("(")[0]
                        fail_reasons[reason_type] = fail_reasons.get(reason_type, 0) + 1
            print(f"  Failure breakdown: {fail_reasons}")

        return passed, failed

    def save_results(self, output_path: Optional[Path] = None):
        """保存评估结果到 JSON"""
        ensure_dirs()
        output_path = output_path or (DNA_EVOLUTION_DIR / "evolution_check_results.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8-evo",
                "total_evaluated": len(self.results),
                "passed": sum(1 for r in self.results if r["pass"]),
                "failed": sum(1 for r in self.results if not r["pass"]),
                "results": self.results,
            }, f, ensure_ascii=False, indent=2)

        print(f"[EvolutionChecker] 评估结果已保存: {output_path}")

    # --- 内部辅助方法 ---

    @staticmethod
    def _get_field(dna: dict, dim_key: str, field: str) -> any:
        """从 DNA dict 中提取字段值

        Args:
            dna: DNA dict
            dim_key: 维度名 (composition/gameplay/reward/style/hook/layout)
            field: 字段路径, 如 "gameplay_area.ratio" 或 "value"

        Returns:
            字段值, 不存在则返回 None
        """
        if dim_key == "hook":
            # hook 是直接值
            if field == "value":
                return dna.get("hook", None)
            return None

        if dim_key == "layout":
            if field == "value":
                return dna.get("layout", None)
            return None

        dim_data = dna.get(dim_key, {})
        if not dim_data:
            return None

        if "." in field:
            parts = field.split(".")
            val = dim_data
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p)
                else:
                    return None
            return val
        elif field == "elements_count":
            elems = dim_data.get("elements", [])
            return len(elems)
        else:
            return dim_data.get(field)

    @staticmethod
    def _values_equal(a: any, b: any) -> bool:
        """比较两个值是否相等 (处理 list/dict 等)"""
        if isinstance(a, list) and isinstance(b, list):
            return sorted(str(x) for x in a) == sorted(str(x) for x in b)
        if isinstance(a, dict) and isinstance(b, dict):
            return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        return a == b
