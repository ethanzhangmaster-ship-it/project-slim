"""Asset DNA Extractor — 从视频提取Creative DNA多维度标签

Schema:
{
  "creative_dna": {
    "role": ["hook", "reward", ...],
    "subject": ["dragon", "witch", ...],
    "action": ["merge", "upgrade", ...],
    "emotion": ["surprise", "curiosity", ...],
    "scene": ["battle", "magic", ...],
    "camera": {"movement": "zoom", "speed": "fast"},
    "quality_grade": "S/A/B/C"
  }
}
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class CreativeDNA:
    role: List[str] = field(default_factory=list)
    subject: List[str] = field(default_factory=list)
    action: List[str] = field(default_factory=list)
    emotion: List[str] = field(default_factory=list)
    scene: List[str] = field(default_factory=list)
    camera_movement: str = ""
    camera_speed: str = ""
    quality_grade: str = "C"

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "subject": self.subject,
            "action": self.action,
            "emotion": self.emotion,
            "scene": self.scene,
            "camera": {"movement": self.camera_movement, "speed": self.camera_speed},
            "quality_grade": self.quality_grade,
        }


class AssetDNAExtractor:
    """Creative DNA 提取器"""

    # 关键词映射表
    SUBJECT_KEYWORDS = {
        "dragon": ["dragon", "龙", "egg", "dinosaur", "wyvern"],
        "witch": ["witch", "女巫", "wizard", "mage", "magic", "spell", "sorcerer"],
        "castle": ["castle", "城堡", "fortress", "kingdom", "throne", "tower"],
        "hero": ["hero", "warrior", "knight", "fighter", "champion"],
        "npc": ["npc", "villager", "merchant", "guide"],
        "creature": ["monster", "beast", "creature", "animal", "pet"],
    }

    ACTION_KEYWORDS = {
        "merge": ["merge", "he", "合", "combine", "fusion", "synthesize", "hecheng"],
        "upgrade": ["upgrade", "level", "evolve", "evolution", "promote", "ascend"],
        "drag": ["drag", "swipe", "move", "pull", "slide", "dragdrop"],
        "unlock": ["unlock", "open", "reveal", "discover", "unlocking"],
        "battle": ["attack", "fight", "battle", "combat", "shoot", "hit", "defeat"],
        "collect": ["collect", "gather", "pickup", "loot", "reward"],
    }

    EMOTION_KEYWORDS = {
        "surprise": ["surprise", "shock", "omg", "unexpected", "sudden", "trap"],
        "curiosity": ["curiosity", "mystery", "secret", "what", "wonder", "how"],
        "excitement": ["excitement", "thrill", "action", "fast", "intense", "climax"],
        "achievement": ["achievement", "victory", "win", "success", "complete", "clear"],
        "urgency": ["urgency", "danger", "hurry", "save", "rescue", "help"],
        "satisfaction": ["satisfaction", "relax", "reward", "comfortable", "peaceful"],
    }

    SCENE_KEYWORDS = {
        "battle": ["battle", "war", "fight", "arena", "combat", "boss"],
        "magic": ["magic", "spell", "enchant", "mystic", "arcane", "portal"],
        "treasure": ["treasure", "chest", "gold", "gem", "loot", "rich"],
        "forest": ["forest", "jungle", "wood", "tree", "nature"],
        "dungeon": ["dungeon", "cave", "underground", "prison", "trap"],
        "sky": ["sky", "cloud", "fly", "aerial", "space"],
    }

    def __init__(self, ranking_db_path: Optional[Path] = None):
        if ranking_db_path is None:
            ranking_db_path = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
        self.ranking_data = {}
        self._load_ranking(ranking_db_path)

    def _load_ranking(self, path: Path):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("shots", []):
                    self.ranking_data[item.get("video_name", "")] = item
            except Exception:
                pass

    def extract(self, video_name: str) -> CreativeDNA:
        """从视频名称+Ranking数据提取完整DNA"""
        name = video_name.lower()
        rank = self.ranking_data.get(video_name, {})

        dna = CreativeDNA()

        # 1. Role — 从 Ranking 的 role_scores + 文件名推断
        role_scores = rank.get("role_scores", {})
        if role_scores:
            dna.role = [r for r, s in sorted(role_scores.items(), key=lambda x: -x[1]) if s >= 40]
        else:
            dna.role = self._infer_role_from_name(name)

        # 2. Subject — 主体识别
        dna.subject = self._match_keywords(name, self.SUBJECT_KEYWORDS)
        # 从Ranking的视觉特征补充
        if rank.get("impact_score", 0) > 60 and not dna.subject:
            dna.subject = ["character"]  # 高冲击力的通常有角色

        # 3. Action — 动作识别
        dna.action = self._match_keywords(name, self.ACTION_KEYWORDS)
        if rank.get("gameplay_clarity", 0) > 50:
            if "merge" not in dna.action:
                dna.action.append("merge")
        if rank.get("motion_score", 0) > 60:
            if "action" not in dna.action:
                dna.action.append("action")

        # 4. Emotion — 情绪弧线
        dna.emotion = self._match_keywords(name, self.EMOTION_KEYWORDS)
        # 从视觉分数补充
        if rank.get("hook_score_v2", 0) > 60:
            dna.emotion.append("surprise")
        if rank.get("reward_score", 0) > 60:
            dna.emotion.append("achievement")
        dna.emotion = list(set(dna.emotion))

        # 5. Scene — 场景识别
        dna.scene = self._match_keywords(name, self.SCENE_KEYWORDS)

        # 6. Camera — 运动分析
        motion = rank.get("motion_score", 0)
        if motion > 60:
            dna.camera_speed = "fast"
        elif motion > 30:
            dna.camera_speed = "medium"
        else:
            dna.camera_speed = "slow"

        # 运动模式：高motion + 高impact = zoom_in; 高motion + 低impact = pan
        if motion > 60 and rank.get("impact_score", 0) > 50:
            dna.camera_movement = "zoom_in"
        elif motion > 60:
            dna.camera_movement = "pan"
        else:
            dna.camera_movement = "static"

        # 7. Quality Grade
        dna.quality_grade = self._grade_quality(rank)

        return dna

    def _infer_role_from_name(self, name: str) -> List[str]:
        """从文件名推断角色"""
        s = name.lower()
        roles = []
        if any(k in s for k in ["kaitou", "开场", "hook", "start", "intro"]):
            roles.append("hook")
        if any(k in s for k in ["wanfa", "玩法", "gameplay", "merge", "play", "hecheng"]):
            roles.append("gameplay")
        if any(k in s for k in ["juese", "角色", "reward", "character", "evol", "zhanshi"]):
            roles.append("reward")
        if any(k in s for k in ["wenti", "问题", "problem", "challenge", "level", "boss"]):
            roles.append("problem")
        if any(k in s for k in ["cta", "download", "结尾", "end"]):
            roles.append("cta")
        if not roles:
            roles.append("mixed")
        return roles

    def _match_keywords(self, text: str, keyword_map: dict) -> List[str]:
        """匹配关键词"""
        matched = []
        for category, keywords in keyword_map.items():
            if any(kw in text for kw in keywords):
                matched.append(category)
        return matched

    def _grade_quality(self, rank: dict) -> str:
        """质量分级 S/A/B/C"""
        impact = rank.get("impact_score", 0)
        motion = rank.get("motion_score", 0)
        hook = rank.get("hook_score_v2", 0)
        clarity = rank.get("gameplay_clarity", 0)
        ad_value = rank.get("ad_value_score", 0)

        # S: 至少3个维度 > 60
        high_dims = sum(1 for s in [impact, motion, hook, clarity, ad_value] if s > 60)
        if high_dims >= 3:
            return "S"
        if high_dims >= 2 or ad_value > 50:
            return "A"
        if high_dims >= 1 or ad_value > 35:
            return "B"
        return "C"

    def extract_all(self, video_dir: Path) -> Dict[str, dict]:
        """批量提取全部视频的DNA"""
        results = {}
        for vp in video_dir.glob("*.mp4"):
            dna = self.extract(vp.stem)
            results[vp.stem] = {
                "video_name": vp.stem,
                "video_path": str(vp),
                "creative_dna": dna.to_dict(),
            }
        return results
