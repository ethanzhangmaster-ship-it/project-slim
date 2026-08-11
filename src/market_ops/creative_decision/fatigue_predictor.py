"""Module 4: Creative Fatigue Predictor

检测与历史素材是否重复，预测疲劳风险。

例如：
- Similarity > 95% → Fatigue High
- 同一 Winning 已有 5+ 颜色变体 → 视觉疲劳
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FatiguePrediction:
    variant_id: str
    fatigue_risk: float = 0.0         # 0-100, 越高越疲劳
    similarity_to_historical: float = 0.0
    color_fatigue: float = 0.0
    creature_fatigue: float = 0.0
    recommendation: str = ""          # "continue" / "pause" / "remake"


class CreativeFatiguePredictor:
    """创意疲劳预测器
    
    逻辑：
    1. 与历史 Winning 素材的相似度 >95% → 极高疲劳 (80-100)
    2. 与历史 Winning 素材的相似度 85-95% → 高疲劳 (60-80)
    3. 同一 Winning 已有 5+ 颜色变体 → 颜色疲劳 (+20)
    4. 同一 Winning 已有 3+ 生物变体 → 生物疲劳 (+15)
    5. 历史投放天数 >14天 → 时间疲劳 (+10)
    6. Frequency >3 → 频率疲劳 (+15)
    
    建议：
    - <40: 继续投放
    - 40-60: 谨慎，监控频率
    - 60-80: 建议暂停或大幅降低预算
    - >80: 必须重新制作
    """

    # 疲劳阈值
    SIMILARITY_EXTREME = 0.95
    SIMILARITY_HIGH = 0.85
    MAX_SAFE_COLOR_VARIANTS = 5
    MAX_SAFE_CREATURE_VARIANTS = 3
    MAX_SAFE_DAYS = 14
    MAX_SAFE_FREQUENCY = 3.0

    def predict(self, variant: dict, history: list[dict] | None = None) -> FatiguePrediction:
        """预测单个 variant 的疲劳风险
        
        Args:
            variant: ranking.json 中的单个 variant
            history: 历史投放素材列表 [{creative_id, dna, spend, days, frequency}]
        """
        variant_id = variant.get("variant_id", "unknown")
        dimensions = variant.get("dimensions", {})
        changed_dimension = variant.get("changed_dimension", "")
        modified_dna = variant.get("modified_dna", {})

        # 从 ranking dimensions 获取已有疲劳分数
        fatigue_dim = dimensions.get("creative_fatigue", {})
        base_fatigue_score = fatigue_dim.get("score", 50.0)

        # 从 similarity 维度获取与 Winning 的相似度
        similarity_dim = dimensions.get("winning_similarity", {})
        winning_similarity = similarity_dim.get("score", 50.0) / 100.0  # 归一化到 0-1

        # 初始化各疲劳分量
        similarity_fatigue = 0.0
        color_fatigue = 0.0
        creature_fatigue = 0.0
        time_fatigue = 0.0
        frequency_fatigue = 0.0

        # 1. 基于与 Winning 相似度的疲劳推断
        if winning_similarity > self.SIMILARITY_EXTREME:
            similarity_fatigue = 80.0 + (winning_similarity - self.SIMILARITY_EXTREME) / (1.0 - self.SIMILARITY_EXTREME) * 20.0
        elif winning_similarity > self.SIMILARITY_HIGH:
            similarity_fatigue = 60.0 + (winning_similarity - self.SIMILARITY_HIGH) / (self.SIMILARITY_EXTREME - self.SIMILARITY_HIGH) * 20.0
        else:
            similarity_fatigue = max(0.0, (winning_similarity - 0.5) / 0.35 * 60.0)

        # 2. 基于 changed_dimension 的变体类型疲劳（无历史时也能推断）
        if "color" in changed_dimension.lower() or "colors_mood" in changed_dimension.lower():
            # 颜色变体本身疲劳风险较低，但如果 ranking 里的 fatigue 分数已经高，则叠加
            color_fatigue = max(0.0, base_fatigue_score - 40.0) * 0.3
        if "creature" in changed_dimension.lower() and "color" not in changed_dimension.lower():
            creature_fatigue = max(0.0, base_fatigue_score - 45.0) * 0.25

        # 3. 如果有历史数据，进行更精确的疲劳计算
        if history:
            similarity_to_historical, color_count, creature_count, max_days, max_frequency = self._analyze_history(
                variant, history
            )

            # 历史相似度疲劳（与具体历史素材的相似度，而非 Winning）
            if similarity_to_historical > self.SIMILARITY_EXTREME:
                similarity_fatigue = max(similarity_fatigue, 85.0)
            elif similarity_to_historical > self.SIMILARITY_HIGH:
                similarity_fatigue = max(similarity_fatigue, 70.0)

            # 颜色变体数量疲劳
            if color_count >= self.MAX_SAFE_COLOR_VARIANTS:
                color_fatigue = max(color_fatigue, 20.0 + (color_count - self.MAX_SAFE_COLOR_VARIANTS) * 3.0)
            elif color_count >= 3:
                color_fatigue = max(color_fatigue, 10.0)

            # 生物变体数量疲劳
            if creature_count >= self.MAX_SAFE_CREATURE_VARIANTS:
                creature_fatigue = max(creature_fatigue, 15.0 + (creature_count - self.MAX_SAFE_CREATURE_VARIANTS) * 3.0)
            elif creature_count >= 2:
                creature_fatigue = max(creature_fatigue, 8.0)

            # 时间疲劳
            if max_days > self.MAX_SAFE_DAYS:
                time_fatigue = 10.0 + min(10.0, (max_days - self.MAX_SAFE_DAYS) * 0.5)

            # 频率疲劳
            if max_frequency > self.MAX_SAFE_FREQUENCY:
                frequency_fatigue = 15.0 + min(10.0, (max_frequency - self.MAX_SAFE_FREQUENCY) * 5.0)
        else:
            # 无历史时，用 winning_similarity 近似替代 historical similarity
            similarity_to_historical = winning_similarity

        # 综合疲劳分数（取各分量加权和上限）
        total_fatigue = (
            similarity_fatigue * 0.35
            + color_fatigue * 0.20
            + creature_fatigue * 0.15
            + time_fatigue * 0.15
            + frequency_fatigue * 0.15
        )

        # 融合 ranking 中的 fatigue 维度分数（作为先验）
        # 如果 ranking 引擎已经给了高疲劳分，则取两者较高值
        blended_fatigue = max(total_fatigue, base_fatigue_score * 0.6)

        final_fatigue = max(0.0, min(100.0, blended_fatigue))

        # 生成建议
        recommendation = self._recommendation_for_score(final_fatigue)

        return FatiguePrediction(
            variant_id=variant_id,
            fatigue_risk=round(final_fatigue, 1),
            similarity_to_historical=round(similarity_to_historical * 100, 1),
            color_fatigue=round(color_fatigue, 1),
            creature_fatigue=round(creature_fatigue, 1),
            recommendation=recommendation,
        )

    def predict_batch(self, variants: list[dict], history: list[dict] | None = None) -> list[FatiguePrediction]:
        """批量预测"""
        return [self.predict(v, history) for v in variants]

    def _analyze_history(self, variant: dict, history: list[dict]) -> tuple[float, int, int, float, float]:
        """分析历史数据，返回 (最大相似度, 颜色变体数, 生物变体数, 最大投放天数, 最大频率)"""
        variant_dna = variant.get("modified_dna", {})

        max_similarity = 0.0
        color_variants = set()
        creature_variants = set()
        max_days = 0.0
        max_frequency = 0.0

        # 提取当前 variant 的关键特征
        curr_color = self._safe_get(variant_dna, ["creatures", 0, "color"], "")
        curr_creature = self._safe_get(variant_dna, ["creatures", 0, "type"], "")
        curr_env = self._safe_get(variant_dna, ["environment", "type"], "")
        curr_mood = self._safe_get(variant_dna, ["colors", "mood_palette", 0], "")

        for hist_item in history:
            hist_dna = hist_item.get("dna", {})
            if not hist_dna:
                continue

            # 计算 DNA 相似度（简化版）
            similarity = self._compute_dna_similarity(variant_dna, hist_dna)
            max_similarity = max(max_similarity, similarity)

            # 统计颜色变体
            hist_color = self._safe_get(hist_dna, ["creatures", 0, "color"], "")
            hist_mood = self._safe_get(hist_dna, ["colors", "mood_palette", 0], "")
            if hist_color or hist_mood:
                color_key = f"{hist_color}_{hist_mood}"
                color_variants.add(color_key)
            if curr_color == hist_color or curr_mood == hist_mood:
                color_variants.add(f"{curr_color}_{curr_mood}")

            # 统计生物变体
            hist_creature = self._safe_get(hist_dna, ["creatures", 0, "type"], "")
            if hist_creature:
                creature_variants.add(hist_creature)
            if curr_creature:
                creature_variants.add(curr_creature)

            # 投放天数和频率
            days = hist_item.get("days", 0)
            freq = hist_item.get("frequency", 0)
            if isinstance(days, (int, float)):
                max_days = max(max_days, float(days))
            if isinstance(freq, (int, float)):
                max_frequency = max(max_frequency, float(freq))

        return max_similarity, len(color_variants), len(creature_variants), max_days, max_frequency

    def _compute_dna_similarity(self, dna_a: dict, dna_b: dict) -> float:
        """计算两个 DNA 之间的简化相似度（0-1）"""
        if not dna_a or not dna_b:
            return 0.0

        keys_to_compare = [
            (["character", "type"], 0.20),
            (["creatures", 0, "type"], 0.20),
            (["creatures", 0, "color"], 0.15),
            (["environment", "type"], 0.15),
            (["colors", "mood_palette", 0], 0.15),
            (["hook", "type"], 0.15),
        ]

        total_weight = 0.0
        match_weight = 0.0

        for path, weight in keys_to_compare:
            val_a = str(self._safe_get(dna_a, path, "")).lower().strip()
            val_b = str(self._safe_get(dna_b, path, "")).lower().strip()
            total_weight += weight
            if val_a and val_b and val_a == val_b:
                match_weight += weight
            elif val_a and val_b:
                # 部分匹配（如同属一个类别）给予一半权重
                match_weight += weight * 0.3

        return match_weight / total_weight if total_weight > 0 else 0.0

    def _recommendation_for_score(self, score: float) -> str:
        """根据疲劳分数给出建议"""
        if score < 40:
            return "continue"
        elif score < 60:
            return "caution"
        elif score < 80:
            return "pause"
        else:
            return "remake"

    def _safe_get(self, d: dict, path: list, default: Any = None) -> Any:
        """安全地沿路径取值"""
        current = d
        for key in path:
            if not isinstance(current, dict):
                if isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
                    current = current[key]
                else:
                    return default
            else:
                current = current.get(key, default)
            if current is None:
                return default
        return current
