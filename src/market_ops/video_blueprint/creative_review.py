"""Creative Review - 创意评审引擎

多维度评分:
Facebook Score / Hook Score / Story Score / Emotion Score
Retention Score / Novelty Score / CTR Score / ROAS Confidence

最终 Overall: 0~100
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreativeReview:
    """创意评审结果"""
    variant_id: str
    overall_score: int
    facebook_score: int
    hook_score: int
    story_score: int
    emotion_score: int
    camera_score: int
    editing_score: int
    visual_score: int
    retention_score: int
    novelty_score: int
    ctr_score: int
    roas_confidence: int
    predicted_ctr: float
    predicted_ipm: float
    predicted_roas: float
    breakdown: dict[str, Any] = field(default_factory=dict)
    verdict: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "overall_score": self.overall_score,
            "facebook_score": self.facebook_score,
            "hook_score": self.hook_score,
            "story_score": self.story_score,
            "emotion_score": self.emotion_score,
            "camera_score": self.camera_score,
            "editing_score": self.editing_score,
            "visual_score": self.visual_score,
            "retention_score": self.retention_score,
            "novelty_score": self.novelty_score,
            "ctr_score": self.ctr_score,
            "roas_confidence": self.roas_confidence,
            "predicted_ctr": self.predicted_ctr,
            "predicted_ipm": self.predicted_ipm,
            "predicted_roas": self.predicted_roas,
            "breakdown": self.breakdown,
            "verdict": self.verdict,
        }


class CreativeReviewEngine:
    """创意评审引擎"""

    def review(
        self,
        dna: VideoDNA,
        blueprint: VideoBlueprint,
        storyboard: Storyboard,
        shotlist: Shotlist,
    ) -> CreativeReview:
        """多维度评审"""
        # Facebook Score (平台适配)
        fb_score = self._score_facebook(dna, blueprint)

        # Hook Score (前三秒吸引力)
        hook_score = self._score_hook(dna, storyboard)

        # Story Score (故事完整性)
        story_score = self._score_story(blueprint, storyboard)

        # Emotion Score (情绪传达)
        emotion_score = self._score_emotion(dna, storyboard)

        # Camera Score (运镜质量)
        camera_score = self._score_camera(dna, storyboard)

        # Retention Score (留存预期)
        retention_score = self._score_retention(shotlist, blueprint)

        # Novelty Score (新颖性)
        novelty_score = self._score_novelty(dna)

        # CTR Score (点击率预期)
        ctr_score = self._score_ctr(dna, blueprint)

        # Editing Score (剪辑规范)
        editing_score = self._score_editing(dna)

        # Visual Score (视觉表现)
        visual_score = self._score_visual(dna, storyboard)

        # ROAS Confidence (ROAS 信心)
        roas_confidence = self._score_roas(dna)

        # Predicted metrics from Decision Variant metadata
        metadata = dna.metadata or {}
        predicted_ctr = metadata.get("predicted_ctr") or 0.0
        predicted_ipm = self._estimate_ipm(predicted_ctr)
        predicted_roas = metadata.get("predicted_roas") or 0.0

        # Overall (9个评分维度)
        overall = int(
            (fb_score + hook_score + story_score + emotion_score + camera_score +
             editing_score + visual_score + ctr_score + roas_confidence) / 9
        )

        verdict = self._get_verdict(overall)

        return CreativeReview(
            variant_id=dna.variant_id,
            overall_score=overall,
            facebook_score=fb_score,
            hook_score=hook_score,
            story_score=story_score,
            emotion_score=emotion_score,
            camera_score=camera_score,
            editing_score=editing_score,
            visual_score=visual_score,
            retention_score=retention_score,
            novelty_score=novelty_score,
            ctr_score=ctr_score,
            roas_confidence=roas_confidence,
            predicted_ctr=predicted_ctr,
            predicted_ipm=predicted_ipm,
            predicted_roas=predicted_roas,
            breakdown={
                "hook_in_3s": self._check_hook_in_3s(storyboard),
                "has_cta": self._check_has_cta(storyboard),
                "shot_count": shotlist.total_shots,
                "avg_shot_duration": shotlist.total_duration / max(1, shotlist.total_shots),
                "story_segments": len(blueprint.segments),
            },
            verdict=verdict,
        )

    def _score_facebook(self, dna: VideoDNA, blueprint: VideoBlueprint) -> int:
        score = 70
        if dna.platform == "facebook":
            score += 10
        if dna.rhythm in ("Fast", "Explosive"):
            score += 5
        if blueprint.video_length <= 15:
            score += 10
        elif blueprint.video_length <= 20:
            score += 5
        return min(100, score)

    def _score_hook(self, dna: VideoDNA, storyboard: Storyboard) -> int:
        score = 60
        if storyboard.scenes:
            first_scene = storyboard.scenes[0]
            if first_scene.end_time <= 3.0:
                score += 20
            if first_scene.fx:
                score += 10
            if "Zoom" in first_scene.camera or "Push" in first_scene.camera:
                score += 10
        return min(100, score)

    def _score_story(self, blueprint: VideoBlueprint, storyboard: Storyboard) -> int:
        score = 60
        score += min(20, len(blueprint.segments) * 4)
        has_hook = any(s.name == "Hook" or s.name == "Opening" for s in storyboard.scenes)
        has_cta = any(s.name == "CTA" for s in storyboard.scenes)
        if has_hook:
            score += 10
        if has_cta:
            score += 10
        return min(100, score)

    def _score_emotion(self, dna: VideoDNA, storyboard: Storyboard) -> int:
        score = 65
        if dna.emotion in ("Urgency", "Excitement", "Wonder"):
            score += 15
        if any(s.lighting for s in storyboard.scenes):
            score += 10
        if any(s.fx for s in storyboard.scenes):
            score += 10
        return min(100, score)

    def _score_retention(self, shotlist: Shotlist, blueprint: VideoBlueprint) -> int:
        score = 60
        avg_dur = blueprint.video_length / max(1, shotlist.total_shots)
        if avg_dur <= 1.0:
            score += 20
        elif avg_dur <= 1.5:
            score += 10
        if blueprint.video_length <= 15:
            score += 10
        return min(100, score)

    def _score_novelty(self, dna: VideoDNA) -> int:
        score = 50
        if dna.story_pattern in ("Surprise", "Challenge"):
            score += 20
        if dna.hook in ("Boss", "Transformation", "Surprise"):
            score += 15
        return min(100, score)

    def _score_ctr(self, dna: VideoDNA, blueprint: VideoBlueprint) -> int:
        score = 55
        if dna.hook in ("Collection", "Surprise", "Boss"):
            score += 15
        if blueprint.video_length <= 15:
            score += 10
        if dna.cta_style == "Character Point":
            score += 10
        if dna.emotion == "Urgency":
            score += 10
        return min(100, score)

    def _score_roas(self, dna: VideoDNA) -> int:
        score = 50
        metadata = dna.metadata or {}
        decision_score = metadata.get("decision_score")
        if decision_score and isinstance(decision_score, (int, float)):
            score += min(30, int(decision_score / 3))
        predicted_roas = metadata.get("predicted_roas")
        if predicted_roas and isinstance(predicted_roas, (int, float)):
            score += min(20, int(predicted_roas * 10))
        return min(100, score)

    def _score_editing(self, dna: VideoDNA) -> int:
        score = 60
        if dna.editing_style in ("Fast Cut", "Cinematic"):
            score += 15
        if dna.color_style in ("Vibrant", "Warm"):
            score += 10
        if dna.transition_style in ("Cut", "Flash"):
            score += 10
        return min(100, score)

    def _score_visual(self, dna: VideoDNA, storyboard: Storyboard) -> int:
        score = 60
        if dna.lighting_style in ("Golden", "Dramatic"):
            score += 15
        if any(s.lighting for s in storyboard.scenes):
            score += 10
        if any(s.fx for s in storyboard.scenes):
            score += 10
        return min(100, score)

    def _score_camera(self, dna: VideoDNA, storyboard: Storyboard) -> int:
        score = 60
        if dna.camera_style in ("Tracking", "Orbit", "Zoom"):
            score += 15
        if all(s.camera and s.camera != "None" for s in storyboard.scenes):
            score += 15
        if any(s.motion for s in storyboard.scenes):
            score += 10
        return min(100, score)

    def _estimate_ipm(self, predicted_ctr: float) -> float:
        if not predicted_ctr:
            return 0.0
        return round(predicted_ctr * 1.5, 2)

    def _check_hook_in_3s(self, storyboard: Storyboard) -> bool:
        if not storyboard.scenes:
            return False
        return storyboard.scenes[0].end_time <= 3.0

    def _check_has_cta(self, storyboard: Storyboard) -> bool:
        return any(s.name == "CTA" for s in storyboard.scenes)

    def _get_verdict(self, overall: int) -> str:
        if overall >= 85:
            return "优秀 - 建议立即投产"
        if overall >= 70:
            return "良好 - 建议投产"
        if overall >= 55:
            return "一般 - 建议优化后投产"
        return "需改进 - 建议重新设计"
