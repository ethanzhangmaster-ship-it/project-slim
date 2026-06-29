"""Creative Score Engine - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from market_ops.clients.lovart import LovartClient


@dataclass
class CreativeScore:
    image_path: Path
    hook_score: float = 0.0
    reward_score: float = 0.0
    emotion_score: float = 0.0
    clarity_score: float = 0.0
    scroll_stop_score: float = 0.0
    novelty_score: float = 0.0
    final_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": str(self.image_path),
            "hook_score": self.hook_score,
            "reward_score": self.reward_score,
            "emotion_score": self.emotion_score,
            "clarity_score": self.clarity_score,
            "scroll_stop_score": self.scroll_stop_score,
            "novelty_score": self.novelty_score,
            "final_score": self.final_score,
        }


class CreativeScoreEngine:
    WEIGHTS = {
        "hook": 0.25,
        "reward": 0.20,
        "emotion": 0.15,
        "clarity": 0.20,
        "scroll_stop": 0.15,
        "novelty": 0.10,
    }
    
    SCORE_THRESHOLD = 8.0
    
    # Diversity penalty (from old creative_loop scoring_engine)
    DIVERSITY_THRESHOLD = 0.90
    DIVERSITY_PENALTY = 2.0
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/scores"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lovart_client = LovartClient()
    
    def score_images(self, images: List[Dict[str, Any]]) -> List[CreativeScore]:
        """评分图片"""
        scores = []
        
        for img_data in images:
            image_path = Path(img_data.get("file_path", img_data.get("image_path", "")))
            
            score = self._score_single(image_path, img_data)
            scores.append(score)
        
        self._save_scores(scores)
        return scores
    
    def _score_single(self, image_path: Path, img_data: Dict[str, Any]) -> CreativeScore:
        """评分单个图片"""
        if not image_path.exists():
            return CreativeScore(image_path=image_path)
        
        try:
            lovart_score = self.lovart_client.score_image(str(image_path))
            return self._parse_lovart_score(lovart_score, image_path)
        except Exception:
            return self._fallback_score(image_path, img_data)
    
    def _parse_lovart_score(self, lovart_score: Dict[str, Any], image_path: Path) -> CreativeScore:
        """解析Lovart评分"""
        scores = lovart_score.get("scores", lovart_score)
        
        hook_score = scores.get("hook_clarity", scores.get("hook_score", 0.0))
        clarity_score = scores.get("visual_quality", scores.get("clarity_score", 0.0))
        novelty_score = scores.get("originality", scores.get("novelty_score", 0.0))
        emotion_score = scores.get("brand_alignment", scores.get("emotion_score", 0.0))
        scroll_stop_score = scores.get("ad_suitability", scores.get("scroll_stop_score", 0.0))
        reward_score = 7.0
        
        final_score = self._calculate_final(
            hook_score, reward_score, emotion_score,
            clarity_score, scroll_stop_score, novelty_score
        )
        
        return CreativeScore(
            image_path=image_path,
            hook_score=hook_score,
            reward_score=reward_score,
            emotion_score=emotion_score,
            clarity_score=clarity_score,
            scroll_stop_score=scroll_stop_score,
            novelty_score=novelty_score,
            final_score=final_score,
        )
    
    def _fallback_score(self, image_path: Path, img_data: Dict[str, Any]) -> CreativeScore:
        """备用评分"""
        from PIL import Image
        
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            clarity_score = 7.0 if (width >= 1024 and height >= 1792) else 5.0
            hook_score = 6.0
            reward_score = 6.0
            emotion_score = 6.0
            scroll_stop_score = 6.0
            novelty_score = 6.0
            
            final_score = self._calculate_final(
                hook_score, reward_score, emotion_score,
                clarity_score, scroll_stop_score, novelty_score
            )
            
            return CreativeScore(
                image_path=image_path,
                hook_score=hook_score,
                reward_score=reward_score,
                emotion_score=emotion_score,
                clarity_score=clarity_score,
                scroll_stop_score=scroll_stop_score,
                novelty_score=novelty_score,
                final_score=final_score,
            )
        except Exception:
            return CreativeScore(image_path=image_path)
    
    def _calculate_final(self, hook: float, reward: float, emotion: float,
                         clarity: float, scroll_stop: float, novelty: float,
                         penalty: float = 0.0) -> float:
        """计算最终分数"""
        weighted_sum = (
            hook * self.WEIGHTS["hook"] +
            reward * self.WEIGHTS["reward"] +
            emotion * self.WEIGHTS["emotion"] +
            clarity * self.WEIGHTS["clarity"] +
            scroll_stop * self.WEIGHTS["scroll_stop"] +
            novelty * self.WEIGHTS["novelty"]
        )
        return max(0.0, min(10.0, weighted_sum - penalty))
    
    def get_top_winners(self, scores: List[CreativeScore], 
                        threshold: float = None, top_n: int = 2) -> List[CreativeScore]:
        """获取Top赢家"""
        threshold = threshold or self.SCORE_THRESHOLD
        
        sorted_scores = sorted(scores, key=lambda x: x.final_score, reverse=True)
        return [s for s in sorted_scores if s.final_score >= threshold][:top_n]
    
    def apply_diversity_penalty(self, scores: List[CreativeScore],
                                previous_winners: List[str],
                                phash_similarity_fn = None) -> List[CreativeScore]:
        """应用多样性惩罚 (Port from old creative_loop scoring_engine)
        
        与历史赢家过于相似的素材会被扣分，避免重复产出。
        """
        for score in scores:
            for winner_path in previous_winners:
                similarity = self._compute_hash_similarity(
                    str(score.image_path), winner_path
                )
                if similarity > self.DIVERSITY_THRESHOLD:
                    score.final_score = self._calculate_final(
                        score.hook_score,
                        score.reward_score,
                        score.emotion_score,
                        score.clarity_score,
                        score.scroll_stop_score,
                        score.novelty_score,
                        self.DIVERSITY_PENALTY,
                    )
                    break
        return scores
    
    def _compute_hash_similarity(self, path1: str, path2: str) -> float:
        """计算两张图片的pHash相似度"""
        try:
            from PIL import Image
            import imagehash
            img1 = Image.open(path1)
            img2 = Image.open(path2)
            hash1 = imagehash.phash(img1)
            hash2 = imagehash.phash(img2)
            max_bits = len(str(hash1)) * 4
            distance = hash1 - hash2
            return 1.0 - (distance / max_bits)
        except Exception:
            return 0.0
    
    def _save_scores(self, scores: List[CreativeScore]) -> Path:
        """保存评分"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scores_{timestamp}.json"
        output_path = self.output_dir / filename
        
        data = [s.to_dict() for s in scores]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path