"""Feature Store — 特征存储与缓存"""
import json
from pathlib import Path
from typing import List, Dict, Optional

from ..predictor.feature_schema import CreativeFeatureVector
from ..config import MEMORY_DIR


class FeatureStore:
    """存储和检索创意特征"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.store_dir = MEMORY_DIR / "features"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, Dict] = {}

    def save(self, features: List[CreativeFeatureVector]):
        """保存特征到文件"""
        data = [self._vector_to_dict(f) for f in features]
        path = self.store_dir / f"{self.game_code}_features.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.cache = {d["creative_id"]: d for d in data}

    def load(self) -> List[CreativeFeatureVector]:
        """加载特征"""
        path = self.store_dir / f"{self.game_code}_features.json"
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.cache = {d["creative_id"]: d for d in data}
        return [self._dict_to_vector(d) for d in data]

    def get(self, creative_id: str) -> Optional[CreativeFeatureVector]:
        """获取单个特征"""
        if creative_id in self.cache:
            return self._dict_to_vector(self.cache[creative_id])
        return None

    @staticmethod
    def _vector_to_dict(v: CreativeFeatureVector) -> Dict:
        return {
            "creative_id": v.creative_id,
            "video_id": v.video_id,
            "duration": v.duration,
            "hook_score": v.hook_score,
            "emotion_score": v.emotion_score,
            "motion_score": v.motion_score,
            "gameplay_score": v.gameplay_score,
            "reward_score": v.reward_score,
            "scene_count": v.scene_count,
            "scene_change_rate": v.scene_change_rate,
            "text_density": v.text_density,
            "contrast": v.contrast,
            "saturation": v.saturation,
            "color_score": v.color_score,
            "character_count": v.character_count,
            "dna_match": v.dna_match,
            "theme_match": v.theme_match,
            "visual_match": v.visual_match,
            "ctr": v.ctr,
            "cvr": v.cvr,
            "purchase_rate": v.purchase_rate,
            "roas": v.roas,
        }

    @staticmethod
    def _dict_to_vector(d: Dict) -> CreativeFeatureVector:
        return CreativeFeatureVector(
            creative_id=d.get("creative_id", ""),
            video_id=d.get("video_id", ""),
            duration=d.get("duration", 0),
            hook_score=d.get("hook_score", 0),
            emotion_score=d.get("emotion_score", 0),
            motion_score=d.get("motion_score", 0),
            gameplay_score=d.get("gameplay_score", 0),
            reward_score=d.get("reward_score", 0),
            scene_count=d.get("scene_count", 0),
            scene_change_rate=d.get("scene_change_rate", 0),
            text_density=d.get("text_density", 0),
            contrast=d.get("contrast", 0),
            saturation=d.get("saturation", 0),
            color_score=d.get("color_score", 0),
            character_count=d.get("character_count", 0),
            dna_match=d.get("dna_match", 0),
            theme_match=d.get("theme_match", 0),
            visual_match=d.get("visual_match", 0),
            ctr=d.get("ctr", 0),
            cvr=d.get("cvr", 0),
            purchase_rate=d.get("purchase_rate", 0),
            roas=d.get("roas", 0),
        )
