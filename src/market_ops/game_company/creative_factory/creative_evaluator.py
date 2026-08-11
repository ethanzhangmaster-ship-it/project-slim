from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CreativeScore:
    score_id: str
    creative_id: str
    ctr_score: float = 0.0
    conversion_score: float = 0.0
    quality_score: float = 0.0
    overall_score: float = 0.0
    score: float = 0.0


class CreativeEvaluator:
    def __init__(self):
        self.scores: Dict[str, CreativeScore] = {}

    def evaluate(self, creative, performance_data: Dict[str, Any]) -> CreativeScore:
        ctr_score = self._calculate_ctr_score(performance_data)
        conversion_score = self._calculate_conversion_score(performance_data)
        quality_score = getattr(creative, "quality_score", 0.85)
        
        overall_score = (ctr_score * 0.3 + conversion_score * 0.4 + quality_score * 0.3)

        score = CreativeScore(
            score_id=f"score_{hash(str(creative)) % 10000:04d}",
            creative_id=getattr(creative, "video_id", getattr(creative, "screenshot_id", "unknown")),
            ctr_score=round(ctr_score, 2),
            conversion_score=round(conversion_score, 2),
            quality_score=round(quality_score, 2),
            overall_score=round(overall_score, 2),
            score=round(overall_score * 100, 1),
        )

        self.scores[score.score_id] = score
        return score

    def rank(self, creatives: List[Any], performance_data: List[Dict[str, Any]]) -> List[CreativeScore]:
        scores = []
        for i, creative in enumerate(creatives):
            data = performance_data[i] if i < len(performance_data) else {}
            score = self.evaluate(creative, data)
            scores.append(score)
        return sorted(scores, key=lambda x: x.overall_score, reverse=True)

    def _calculate_ctr_score(self, data: Dict[str, Any]) -> float:
        ctr = data.get("ctr", 0.02)
        if ctr > 0.05:
            return 0.95
        elif ctr > 0.03:
            return 0.8
        elif ctr > 0.015:
            return 0.6
        else:
            return 0.4

    def _calculate_conversion_score(self, data: Dict[str, Any]) -> float:
        cvr = data.get("cvr", 0.02)
        if cvr > 0.05:
            return 0.95
        elif cvr > 0.03:
            return 0.8
        elif cvr > 0.015:
            return 0.6
        else:
            return 0.4

    def evaluate_demo(self) -> CreativeScore:
        creative = {"video_id": "test_video", "quality_score": 0.9}
        performance = {"ctr": 0.04, "cvr": 0.035}
        return self.evaluate(creative, performance)
