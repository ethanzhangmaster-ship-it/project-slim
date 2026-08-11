"""Performance Quality Gate V3.8 — 基于买量价值的质量分级

从 V3.x 的视觉质量 S/A/B/C 升级为 Performance Grade：
- S+: 顶级买量素材（Buying Score >= 85, Predicted CTR >= 3.5%）
- S: 优秀买量素材（Buying Score >= 75, Predicted CTR >= 2.8%）
- A: 良好买量素材（Buying Score >= 60, Predicted CTR >= 2.0%）
- B: 可用素材（Buying Score >= 45, Predicted CTR >= 1.2%）
- Reject: 不建议投放（Buying Score < 45 或 Predicted CTR < 1.0%）
"""
from typing import Dict, List, Optional
from dataclasses import dataclass

from .creative_value_predictor import CreativeValuePredictor
from .archetype_ranker import ArchetypeDiscoveryEngine


@dataclass
class PerformanceGrade:
    """Performance Grade 结果"""
    grade: str
    buying_score: float
    predicted_ctr: float
    predicted_cpi: float
    predicted_d7_roi: float
    archetype: str
    archetype_similarity: float
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    is_approved: bool


class PerformanceQualityGate:
    """Performance Quality Gate V3.8"""

    GRADES = ["S+", "S", "A", "B", "Reject"]

    GRADE_THRESHOLDS = {
        "S+": {"buying_score": 85, "ctr": 3.5, "roi": 0.30},
        "S":  {"buying_score": 75, "ctr": 2.8, "roi": 0.25},
        "A":  {"buying_score": 60, "ctr": 2.0, "roi": 0.18},
        "B":  {"buying_score": 45, "ctr": 1.2, "roi": 0.10},
    }

    def __init__(self, ranking_db_path=None, winner_db_path=None):
        self.value_predictor = CreativeValuePredictor(ranking_db_path, winner_db_path)
        self.archetype_engine = ArchetypeDiscoveryEngine(winner_db_path)
        self.archetype_engine.discover_archetypes()

    def evaluate(self, video_name: str, dna: Optional[dict] = None) -> PerformanceGrade:
        """评估单个创意的 Performance Grade"""
        # 1. 预测买量价值
        prediction = self.value_predictor.predict(video_name)
        buying_score = prediction["buying_score"]
        pred_ctr = prediction["predicted_ctr"]
        pred_cpi = prediction["predicted_cpi"]
        pred_roi = prediction["predicted_d7_roi"]

        # 2. Archetype 分类
        if dna is None:
            from .winner_dna_extractor import WinnerDNAExtractor
            extractor = WinnerDNAExtractor()
            dna = extractor.extract(video_name)

        archetype_result = self.archetype_engine.classify_creative(dna)
        archetype = archetype_result["archetype"]
        archetype_sim = archetype_result["similarity"]

        # 3. 计算 Grade
        grade = self._compute_grade(buying_score, pred_ctr, pred_roi, archetype_sim)

        # 4. 分析优势劣势
        strengths, weaknesses = self._analyze_strengths_weaknesses(
            prediction["breakdown"], pred_ctr, pred_cpi, archetype_sim
        )

        # 5. 生成建议
        recommendations = self._generate_recommendations(
            grade, strengths, weaknesses, archetype_result
        )

        is_approved = grade not in ["Reject"]

        return PerformanceGrade(
            grade=grade,
            buying_score=buying_score,
            predicted_ctr=pred_ctr,
            predicted_cpi=pred_cpi,
            predicted_d7_roi=pred_roi,
            archetype=archetype,
            archetype_similarity=archetype_sim,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            is_approved=is_approved,
        )

    def _compute_grade(self, buying_score: float, ctr: float, roi: float,
                       archetype_sim: float) -> str:
        """计算 Performance Grade"""
        # S+ 要求
        if (buying_score >= self.GRADE_THRESHOLDS["S+"]["buying_score"] and
                ctr >= self.GRADE_THRESHOLDS["S+"]["ctr"] and
                roi >= self.GRADE_THRESHOLDS["S+"]["roi"] and
                archetype_sim >= 60):
            return "S+"

        # S 要求
        if (buying_score >= self.GRADE_THRESHOLDS["S"]["buying_score"] and
                ctr >= self.GRADE_THRESHOLDS["S"]["ctr"] and
                roi >= self.GRADE_THRESHOLDS["S"]["roi"]):
            return "S"

        # A 要求
        if (buying_score >= self.GRADE_THRESHOLDS["A"]["buying_score"] and
                ctr >= self.GRADE_THRESHOLDS["A"]["ctr"] and
                roi >= self.GRADE_THRESHOLDS["A"]["roi"]):
            return "A"

        # B 要求
        if (buying_score >= self.GRADE_THRESHOLDS["B"]["buying_score"] and
                ctr >= self.GRADE_THRESHOLDS["B"]["ctr"]):
            return "B"

        return "Reject"

    def _analyze_strengths_weaknesses(self, breakdown: dict, ctr: float, cpi: float,
                                      archetype_sim: float):
        """分析优势和劣势"""
        strengths = []
        weaknesses = []

        # Hook 分析
        hook_score = breakdown.get("hook", 0) / self.value_predictor.WEIGHTS["hook"] * 100 / 100 \
            if self.value_predictor.WEIGHTS["hook"] > 0 else 0
        hook_raw = breakdown.get("hook", 0) / self.value_predictor.WEIGHTS["hook"]
        if hook_raw >= 70:
            strengths.append(f"Hook能力强 ({hook_raw:.0f}/100)，能有效吸引注意力")
        elif hook_raw < 40:
            weaknesses.append(f"Hook能力弱 ({hook_raw:.0f}/100)，开场吸引力不足")

        # Gameplay 分析
        gp_raw = breakdown.get("gameplay", 0) / self.value_predictor.WEIGHTS["gameplay"]
        if gp_raw >= 70:
            strengths.append(f"玩法清晰度高 ({gp_raw:.0f}/100)，用户易理解")
        elif gp_raw < 40:
            weaknesses.append(f"玩法清晰度低 ({gp_raw:.0f}/100)，游戏机制表达不足")

        # Reward 分析
        reward_raw = breakdown.get("reward", 0) / self.value_predictor.WEIGHTS["reward"]
        if reward_raw >= 70:
            strengths.append(f"奖励吸引力强 ({reward_raw:.0f}/100)，转化动力足")
        elif reward_raw < 40:
            weaknesses.append(f"奖励吸引力弱 ({reward_raw:.0f}/100)，缺乏下载动力")

        # Novelty 分析
        novelty_raw = breakdown.get("novelty", 0) / self.value_predictor.WEIGHTS["novelty"]
        if novelty_raw >= 70:
            strengths.append(f"创意新颖度高 ({novelty_raw:.0f}/100)，有差异化优势")
        elif novelty_raw < 35:
            weaknesses.append(f"创意新颖度低 ({novelty_raw:.0f}/100)，同质化严重")

        # CTR 预测
        if ctr >= 3.0:
            strengths.append(f"预测CTR优秀 ({ctr:.1f}%)，获客成本可控")
        elif ctr < 1.5:
            weaknesses.append(f"预测CTR偏低 ({ctr:.1f}%)，可能导致CPI偏高")

        # CPI 预测
        if cpi <= 0.4:
            strengths.append(f"预测CPI低 (${cpi:.2f})，买量效率高")
        elif cpi > 0.8:
            weaknesses.append(f"预测CPI偏高 (${cpi:.2f})，需关注ROI")

        # Winner Bonus
        winner_bonus = breakdown.get("winner_bonus", 0)
        if winner_bonus >= 10:
            strengths.append(f"Winner DNA匹配度高 (+{winner_bonus:.0f}加分)，接近高绩效模式")
        elif winner_bonus == 0:
            weaknesses.append("未匹配到已知Winner模式，表现不确定性较高")

        # Archetype 相似度
        if archetype_sim >= 70:
            strengths.append(f"与{('Top ' if archetype_sim > 80 else '')}Archetype高度相似 ({archetype_sim:.0f}%)")
        elif archetype_sim < 40:
            weaknesses.append(f"与Archetype相似度低 ({archetype_sim:.0f}%)，偏离已知成功模式")

        return strengths, weaknesses

    def _generate_recommendations(self, grade: str, strengths: List[str],
                                   weaknesses: List[str],
                                   archetype_result: dict) -> List[str]:
        """生成优化建议"""
        recommendations = []

        if grade == "S+":
            recommendations.append("顶级素材，建议立即投放并分配主要预算")
            recommendations.append("可作为A/B测试的基准对照组")
            recommendations.append("提取DNA模式用于指导更多素材生成")
        elif grade == "S":
            recommendations.append("优秀素材，建议投放并持续观察表现")
            recommendations.append("可尝试小幅变体优化冲击S+")
        elif grade == "A":
            recommendations.append("良好素材，建议在测试组投放")
            if weaknesses:
                recommendations.append(f"优化方向: {weaknesses[0]}")
        elif grade == "B":
            recommendations.append("可用素材，建议小预算测试验证")
            recommendations.append("建议针对性优化弱项指标后再扩大投放")
            if weaknesses:
                recommendations.append(f"优先改进: {weaknesses[0]}")
        else:
            recommendations.append("不建议投放，需大幅优化或重新制作")
            if weaknesses:
                recommendations.append(f"核心问题: {weaknesses[0]}")

        # 基于 Archetype 的建议
        archetype_name = archetype_result.get("archetype", "")
        if archetype_name and archetype_result.get("similarity", 0) < 60:
            arch_info = archetype_result.get("archetype_info", {})
            if arch_info.get("avg_ctr", 0) >= 3.0:
                recommendations.append(
                    f"建议向 {archetype_name} 模式靠拢 (平均CTR {arch_info['avg_ctr']:.1f}%)"
                )

        return recommendations

    def batch_evaluate(self, video_names: List[str]) -> List[PerformanceGrade]:
        """批量评估"""
        return [self.evaluate(name) for name in video_names]

    def filter_approved(self, video_names: List[str],
                         min_grade: str = "B") -> List[PerformanceGrade]:
        """筛选达到指定等级以上的素材"""
        results = self.batch_evaluate(video_names)

        grade_order = {"S+": 0, "S": 1, "A": 2, "B": 3, "Reject": 4}
        min_rank = grade_order.get(min_grade, 3)

        approved = [r for r in results if grade_order.get(r.grade, 99) <= min_rank]
        approved.sort(key=lambda x: grade_order.get(x.grade, 99))
        return approved

    def get_grade_distribution(self, video_names: List[str]) -> Dict[str, int]:
        """获取等级分布统计"""
        results = self.batch_evaluate(video_names)
        distribution = {g: 0 for g in self.GRADES}
        for r in results:
            distribution[r.grade] = distribution.get(r.grade, 0) + 1
        return distribution

    def get_top_performers(self, video_names: List[str],
                           top_n: int = 10) -> List[PerformanceGrade]:
        """获取Top表现的素材"""
        results = self.batch_evaluate(video_names)
        grade_order = {"S+": 0, "S": 1, "A": 2, "B": 3, "Reject": 4}
        results.sort(key=lambda x: (grade_order.get(x.grade, 99), -x.buying_score))
        return results[:top_n]
