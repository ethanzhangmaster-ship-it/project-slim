"""Experiment Builder — Facebook 测试批次构建

取 Top N ranked variants, 输出 facebook_test_batch.json,
格式兼容 Facebook Ads API 的 creative 测试批次创建。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..config import DNA_EVOLUTION_DIR, FB_TEST_BATCH_SIZE, ensure_dirs


class ExperimentBuilder:
    """Facebook 测试批次构建器"""

    def __init__(self):
        self.test_batch: dict = {}

    def build_test_batch(self, ranked_variants: List[dict],
                         prompts: Optional[List[dict]] = None,
                         top_n: Optional[int] = None) -> dict:
        """从排名结果构建 Facebook 测试批次

        Args:
            ranked_variants: 已排名的 variant 列表
            prompts: 对应的 prompt 列表 (可选, 用于注入生成提示)
            top_n: 取前 N 个, 默认 FB_TEST_BATCH_SIZE

        Returns:
            测试批次 dict
        """
        top_n = top_n or FB_TEST_BATCH_SIZE
        top_variants = ranked_variants[:min(top_n, len(ranked_variants))]

        # 构建 prompt 索引 (按 creative_id)
        prompt_index = {}
        if prompts:
            for p in prompts:
                cid = p.get("creative_id", "")
                if cid:
                    prompt_index[cid] = p

        creatives = []
        for v in top_variants:
            creative_id = v.get("creative_id", "unknown")
            creative_entry = {
                "creative_id": creative_id,
                "winner_source": v.get("winner_source", {}),
                "strategy": v.get("strategy", ""),
                "strategy_label": v.get("strategy_label", ""),
                "mutation_reason": v.get("mutation_reason", ""),
                "expected_advantage": v.get("expected_advantage", ""),
                "evolution_score": v.get("_evolution_score", 0),
                "scores": {
                    "winner_similarity": v.get("_similarity", 0),
                    "diversity": v.get("_diversity", 0),
                    "gameplay_preserve": v.get("_gameplay_preserve", 0),
                    "reward_visibility": v.get("_reward_visibility", 0),
                },
            }

            # 注入 prompt (如有)
            matched_prompt = prompt_index.get(creative_id)
            if matched_prompt:
                creative_entry["generation_prompt"] = matched_prompt.get("prompt", "")
                creative_entry["negative_prompt"] = matched_prompt.get("negative_prompt", "")

            # 注入 changed fields 摘要
            changes = v.get("change", [])
            if changes:
                creative_entry["mutated_fields"] = changes

            creatives.append(creative_entry)

        self.test_batch = {
            "version": "2.1.8-evo",
            "campaign": {
                "name": "DNA Evolution Test Batch",
                "objective": "Test creative variants evolved from top-performing winners",
                "description": (
                    f"Automated creative evolution batch: {len(creatives)} variants "
                    f"from {len(set(c.get('winner_source', {}).get('asset_id', '') for c in creatives))} winners"
                ),
            },
            "total_creatives": len(creatives),
            "strategies_used": list(set(c.get("strategy", "") for c in creatives)),
            "creatives": creatives,
        }

        print(f"\n[ExperimentBuilder] 测试批次构建完成:")
        print(f"  Creatives: {len(creatives)}")
        print(f"  Strategies: {self.test_batch['strategies_used']}")
        print(f"  Avg Score: {sum(c['evolution_score'] for c in creatives) / len(creatives):.4f}"
              if creatives else "  No creatives")

        return self.test_batch

    def save(self, output_path: Optional[Path] = None):
        """保存 Facebook 测试批次 JSON"""
        ensure_dirs()
        output_path = output_path or (DNA_EVOLUTION_DIR / "facebook_test_batch.json")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.test_batch, f, ensure_ascii=False, indent=2)

        print(f"[ExperimentBuilder] 测试批次已保存: {output_path}")
        return output_path
