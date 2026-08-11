from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class CreativeConcept:
    concept_id: str
    theme: str
    format: str
    headline: str
    description: str
    cta_text: str
    target_audience: str
    predicted_ctr: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class CreativeEvaluation:
    creative_id: str
    overall_score: float
    ctr_score: float
    cvr_score: float
    engagement_score: float
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class CreativeBrain:
    """创意大脑，负责生成和评估广告创意。"""

    def __init__(self):
        self.concepts: List[CreativeConcept] = []
        self.winning_patterns: List[Dict[str, Any]] = []

    def generate_creative_concepts(self, brief: Dict[str, Any], count: int = 3) -> List[CreativeConcept]:
        """基于 brief 生成创意概念。"""
        themes = ["fantasy", "action", "puzzle", "social", "competitive"]
        formats = ["video", "playable", "carousel", "image"]
        audiences = brief.get("target_audiences", ["casual", "midcore", "hardcore"])

        concepts = []
        for i in range(count):
            theme = themes[i % len(themes)]
            fmt = formats[i % len(formats)]
            concept = CreativeConcept(
                concept_id=f"cc_{datetime.now().strftime('%Y%m%d')}_{i}",
                theme=theme,
                format=fmt,
                headline=f"Experience the ultimate {theme} adventure!",
                description=f"Join millions of players in this exciting {theme} game.",
                cta_text="Play Now" if i % 2 == 0 else "Download Free",
                target_audience=audiences[i % len(audiences)],
                predicted_ctr=round(0.02 + (i * 0.005), 3),
                tags=[theme, fmt, "auto_generated"],
            )
            concepts.append(concept)
        self.concepts.extend(concepts)
        return concepts

    def evaluate_creative(self, creative: Dict[str, Any]) -> CreativeEvaluation:
        """评估单个创意的预期表现。"""
        ctr = creative.get("ctr", 0.0)
        cvr = creative.get("cvr", 0.0)
        engagement = creative.get("engagement_rate", 0.0)

        ctr_score = min(ctr * 1000, 10.0)
        cvr_score = min(cvr * 500, 10.0)
        engagement_score = min(engagement * 200, 10.0)
        overall = round((ctr_score + cvr_score + engagement_score) / 3, 2)

        strengths = []
        weaknesses = []
        suggestions = []

        if ctr > 0.03:
            strengths.append("高点击率")
        else:
            weaknesses.append("点击率偏低")
            suggestions.append("尝试更吸引人的标题")

        if cvr > 0.05:
            strengths.append("转化率高")
        else:
            weaknesses.append("转化率一般")
            suggestions.append("优化落地页或 CTA")

        return CreativeEvaluation(
            creative_id=creative.get("id", "unknown"),
            overall_score=overall,
            ctr_score=round(ctr_score, 2),
            cvr_score=round(cvr_score, 2),
            engagement_score=round(engagement_score, 2),
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
        )

    def predict_ctr(self, creative: Dict[str, Any]) -> float:
        """预测创意的点击率。"""
        base = 0.015
        if creative.get("has_video", False):
            base += 0.01
        if "free" in creative.get("headline", "").lower():
            base += 0.005
        if creative.get("format") == "playable":
            base += 0.008
        base += creative.get("historical_ctr", 0.0) * 0.3
        return round(min(base, 0.15), 4)

    def get_winning_patterns(self) -> List[Dict[str, Any]]:
        """返回历史上表现优异的创意模式。"""
        return [
            {"pattern": "gameplay_highlight + urgency_cta", "avg_ctr": 0.045, "confidence": 0.92},
            {"pattern": "user_testimonial + social_proof", "avg_ctr": 0.038, "confidence": 0.88},
            {"pattern": "before_after_transform + challenge", "avg_ctr": 0.042, "confidence": 0.90},
            {"pattern": "limited_time_offer + countdown", "avg_ctr": 0.050, "confidence": 0.85},
        ]
