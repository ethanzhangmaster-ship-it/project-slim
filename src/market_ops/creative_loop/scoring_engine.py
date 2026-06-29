"""Scoring Engine - Lovart评分+diversity penalty (DEPRECATED)
Use market_ops.creative_growth_loop.08_scoring.creative_score_engine instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.08_scoring.creative_score_engine")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from market_ops.clients.lovart import LovartClient


@dataclass
class ImageScore:
    image_path: Path
    novelty_score: float = 0.0
    visual_score: float = 0.0
    hook_score: float = 0.0
    ctr_score: float = 0.0
    emotion_score: float = 0.0
    diversity_penalty: float = 0.0
    final_score: float = 0.0
    model: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": str(self.image_path),
            "novelty_score": self.novelty_score,
            "visual_score": self.visual_score,
            "hook_score": self.hook_score,
            "ctr_score": self.ctr_score,
            "emotion_score": self.emotion_score,
            "diversity_penalty": self.diversity_penalty,
            "final_score": self.final_score,
            "model": self.model,
        }


class ScoringEngine:
    DIVERSITY_THRESHOLD = 0.9
    DIVERSITY_PENALTY = 2.0
    
    WEIGHTS = {
        "novelty": 0.2,
        "visual": 0.25,
        "hook": 0.25,
        "ctr": 0.15,
        "emotion": 0.15,
    }

    def __init__(self, output_dir: str = "output/creative_loop_v2/scores"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lovart_client = LovartClient()

    def score_images(self, images: List[Dict[str, Any]], 
                    previous_winners: List[str] = None) -> List[ImageScore]:
        scores: List[ImageScore] = []
        
        for img_data in images:
            image_path = Path(img_data["file_path"])
            model = img_data.get("model", "")
            
            score = self._score_single(image_path, model)
            scores.append(score)
        
        if previous_winners:
            scores = self._apply_diversity_penalty(scores, previous_winners)
        
        self._save_scores(scores)
        return scores

    def _score_single(self, image_path: Path, model: str) -> ImageScore:
        if not image_path.exists():
            return ImageScore(image_path=image_path, model=model)
        
        try:
            lovart_score = self.lovart_client.score_image(str(image_path))
            return self._parse_lovart_score(lovart_score, image_path, model)
        except Exception:
            return self._fallback_score(image_path, model)

    def _parse_lovart_score(self, lovart_score: Dict[str, Any], image_path: Path, model: str) -> ImageScore:
        return ImageScore(
            image_path=image_path,
            visual_score=lovart_score.get("visual_quality", 0.0),
            hook_score=lovart_score.get("hook_clarity", 0.0),
            emotion_score=lovart_score.get("brand_alignment", 0.0),
            novelty_score=lovart_score.get("originality", 0.0),
            ctr_score=lovart_score.get("ad_suitability", 0.0),
            final_score=lovart_score.get("overall", 0.0),
            model=model,
        )

    def _fallback_score(self, image_path: Path, model: str) -> ImageScore:
        from PIL import Image
        
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            visual_score = 7.0 if (width >= 1024 and height >= 1792) else 5.0
            novelty_score = 6.0
            hook_score = 6.0
            ctr_score = 6.0
            emotion_score = 6.0
            
            final_score = self._calculate_final_score(
                novelty_score, visual_score, hook_score, ctr_score, emotion_score, 0.0
            )
            
            return ImageScore(
                image_path=image_path,
                novelty_score=novelty_score,
                visual_score=visual_score,
                hook_score=hook_score,
                ctr_score=ctr_score,
                emotion_score=emotion_score,
                final_score=final_score,
                model=model,
            )
        except Exception:
            return ImageScore(image_path=image_path, model=model)

    def _calculate_final_score(self, novelty: float, visual: float, hook: float, 
                              ctr: float, emotion: float, penalty: float) -> float:
        weighted_sum = (
            novelty * self.WEIGHTS["novelty"] +
            visual * self.WEIGHTS["visual"] +
            hook * self.WEIGHTS["hook"] +
            ctr * self.WEIGHTS["ctr"] +
            emotion * self.WEIGHTS["emotion"]
        )
        return max(0.0, min(10.0, weighted_sum - penalty))

    def _apply_diversity_penalty(self, scores: List[ImageScore], 
                                 previous_winners: List[str]) -> List[ImageScore]:
        for score in scores:
            for winner_path in previous_winners:
                similarity = self._compute_similarity(str(score.image_path), winner_path)
                if similarity > self.DIVERSITY_THRESHOLD:
                    score.diversity_penalty = self.DIVERSITY_PENALTY
                    score.final_score = self._calculate_final_score(
                        score.novelty_score,
                        score.visual_score,
                        score.hook_score,
                        score.ctr_score,
                        score.emotion_score,
                        self.DIVERSITY_PENALTY
                    )
                    break
        return scores

    def _compute_similarity(self, path1: str, path2: str) -> float:
        try:
            from transformers import CLIPProcessor, CLIPModel
            import torch
            from PIL import Image
            
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            
            img1 = Image.open(path1).convert("RGB")
            img2 = Image.open(path2).convert("RGB")
            
            inputs = processor(images=[img1, img2], return_tensors="pt")
            outputs = model.get_image_features(**inputs)
            
            return torch.nn.functional.cosine_similarity(outputs[0], outputs[1], dim=0).item()
        except Exception:
            return 0.0

    def _save_scores(self, scores: List[ImageScore]) -> Path:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scores_{timestamp}.json"
        output_path = self.output_dir / filename
        
        data = [s.to_dict() for s in scores]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path

    def get_top_winners(self, scores: List[ImageScore], threshold: float = 8.0, top_n: int = 2) -> List[ImageScore]:
        sorted_scores = sorted(scores, key=lambda x: x.final_score, reverse=True)
        return [s for s in sorted_scores if s.final_score >= threshold][:top_n]