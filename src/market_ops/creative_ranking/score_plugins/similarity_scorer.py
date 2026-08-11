from .base_scorer import BaseScorer, ScoreResult
from ..config import RankingConfig


class SimilarityScorer(BaseScorer):
    """Winning Similarity - 和Winning Creative的相似度评分

    逻辑：
    - 逐字段对比variant和base_dna
    - 相似度越高 = 保留了Winning的核心成功要素
    - 但100%相同 = 无创新，需要平衡
    - 理想范围：70-90分（足够相似但有变化）

    评分维度：
    - character_type (20%): 角色类型是否一致
    - creature_type (15%): 生物类型是否一致
    - environment_type (15%): 环境类型是否一致
    - color_mood (15%): 色彩情绪是否一致
    - lighting_temperature (10%): 灯光色温是否一致
    - hook_type (15%): Hook类型是否一致
    - composition_layout (10%): 构图布局是否一致
    """

    name = "Winning Similarity"
    weight_key = "winning_similarity"

    def score(
        self,
        variant_dna: dict,
        base_dna: dict,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        config = RankingConfig()
        similarity_weights = config.similarity_weights

        # 定义各维度取值路径
        dimension_paths = {
            "character_type": (["character", "type"], ["character", "type"]),
            "creature_type": (["creatures", 0, "type"], ["creatures", 0, "type"]),
            "environment_type": (["environment", "type"], ["environment", "type"]),
            "color_mood": (["colors", "mood_palette"], ["colors", "mood_palette"]),
            "lighting_temperature": (
                ["lighting", "color_temperature"],
                ["lighting", "color_temperature"],
            ),
            "hook_type": (["hook", "type"], ["hook", "type"]),
            "composition_layout": (["composition", "layout"], ["composition", "layout"]),
        }

        breakdown = {}
        recommendations = []
        risks = []
        total_weight = 0.0
        weighted_sum = 0.0
        match_count = 0

        for dim_key, (v_path, b_path) in dimension_paths.items():
            weight = similarity_weights.get(dim_key, 0.0)
            if weight <= 0:
                continue

            v_val = self._safe_get(variant_dna, v_path, default="")
            b_val = self._safe_get(base_dna, b_path, default="")

            # 处理列表类型（如 mood_palette）
            if isinstance(v_val, list) and isinstance(b_val, list):
                # 取交集判断
                if not v_val and not b_val:
                    dim_score = 100.0
                elif not v_val or not b_val:
                    dim_score = 0.0
                else:
                    # 计算Jaccard相似度
                    set_v = set(str(v).lower() for v in v_val)
                    set_b = set(str(b).lower() for b in b_val)
                    intersection = len(set_v & set_b)
                    union = len(set_v | set_b)
                    dim_score = (intersection / union * 100.0) if union > 0 else 0.0
            else:
                # 字符串精确匹配（忽略大小写）
                v_str = str(v_val).lower().strip() if v_val else ""
                b_str = str(b_val).lower().strip() if b_val else ""
                dim_score = 100.0 if v_str == b_str else 0.0

            if dim_score >= 100.0:
                match_count += 1

            breakdown[dim_key] = {
                "score": round(dim_score, 1),
                "weight": weight,
                "variant_value": v_val,
                "base_value": b_val,
                "contribution": round(dim_score * weight, 1),
            }
            weighted_sum += dim_score * weight
            total_weight += weight

        # 计算原始相似度分数
        raw_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # 调整分数：100%相同需要适当扣分（完全无创新）
        final_score = raw_score
        if raw_score >= 99.0:
            final_score = 85.0  # 完全复制，扣分
            risks.append("与Winning Creative几乎完全相同，缺乏创新，容易导致创意疲劳")
        elif raw_score >= 90.0:
            final_score = raw_score - 5.0
            recommendations.append("高度保留了Winning的核心成功要素")
            risks.append("变化较小，需注意不要与其他变体过于雷同")
        elif raw_score >= 70.0:
            recommendations.append("在保留Winning成功要素的同时有适度变化，处于理想范围")
        elif raw_score >= 50.0:
            recommendations.append("有一定变化，但仍保留了部分Winning要素")
            risks.append("与Winning Creative差异较大，可能丢失已验证的成功因素")
        else:
            risks.append("与Winning Creative差异过大，可能丢失核心成功要素，需谨慎评估")

        final_score = max(0.0, min(100.0, final_score))

        # 明细维度说明
        if match_count >= 6:
            recommendations.append(f"{match_count}/7 个核心维度与Winning Creative保持一致")
        elif match_count <= 2:
            risks.append(f"仅 {match_count}/7 个维度与Winning匹配，偏离度过高")

        return ScoreResult(
            score=round(final_score, 1),
            breakdown=breakdown,
            recommendations=recommendations,
            risks=risks,
            raw_features={"raw_similarity": round(raw_score, 1), "match_count": match_count},
        )
