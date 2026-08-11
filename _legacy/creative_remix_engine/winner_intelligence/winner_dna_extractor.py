"""Winner DNA Extractor — 从视频提取买量DNA

提取维度：
1. Hook DNA — 开场类型、第一帧强度、运动速度、新颖度
2. Subject DNA — 主体识别、大小占比、中心位置
3. Gameplay DNA — 动作识别、清晰度、前后对比
4. Reward DNA — 奖励类型、闪光、进化、新角色
5. Structure DNA — 视频节奏结构
"""
import json
from pathlib import Path
from typing import Dict, List, Optional


class WinnerDNAExtractor:
    """Winner DNA 提取器"""

    def __init__(self, ranking_db_path: Optional[Path] = None):
        if ranking_db_path is None:
            ranking_db_path = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
        self.ranking_data = {}
        self._load(ranking_db_path)

    def _load(self, path: Path):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("shots", []):
                    self.ranking_data[item.get("video_name", "")] = item
            except Exception:
                pass

    def extract(self, video_name: str) -> Dict:
        """提取完整 Winner DNA"""
        rank = self.ranking_data.get(video_name, {})
        name = video_name.lower()

        return {
            "video_name": video_name,
            "hook_dna": self._extract_hook_dna(name, rank),
            "subject_dna": self._extract_subject_dna(name, rank),
            "gameplay_dna": self._extract_gameplay_dna(name, rank),
            "reward_dna": self._extract_reward_dna(name, rank),
            "structure_dna": self._extract_structure_dna(name, rank),
        }

    def _extract_hook_dna(self, name: str, rank: dict) -> dict:
        hook_v2 = rank.get("hook_score_v2", 0)
        hook_break = rank.get("hook_breakdown", {})

        # 判断 hook 类型
        hook_type = "general"
        if any(k in name for k in ["trap", "cage", "danger", "shock", "surprise"]):
            hook_type = "shock"
        elif any(k in name for k in ["level", "vs", "challenge", "impossible", "99%"]):
            hook_type = "challenge"
        elif any(k in name for k in ["egg", "evol", "transform", "become"]):
            hook_type = "transformation"
        elif any(k in name for k in ["secret", "mystery", "curious", "what", "how"]):
            hook_type = "curiosity"
        elif any(k in name for k in ["rescue", "save", "help", "trap"]):
            hook_type = "urgency"

        return {
            "hook_type": hook_type,
            "first_frame_strength": round(hook_break.get("visual_impact", rank.get("impact_score", 0)), 1),
            "motion_speed": round(hook_break.get("motion", rank.get("motion_score", 0)), 1),
            "novelty": round(hook_break.get("novelty", 20), 1),
            "emotion": round(hook_break.get("emotion", 30), 1),
            "subject_size": round(hook_break.get("subject_size", 30), 1),
            "overall_hook": round(hook_v2, 1),
        }

    def _extract_subject_dna(self, name: str, rank: dict) -> dict:
        subjects = []
        if "dragon" in name or "龙" in name:
            subjects.append("dragon")
        if "witch" in name or "女巫" in name or "wizard" in name:
            subjects.append("witch")
        if "castle" in name or "城堡" in name:
            subjects.append("castle")
        if "hero" in name or "warrior" in name or "knight" in name:
            subjects.append("hero")
        if "monster" in name or "beast" in name or "creature" in name:
            subjects.append("monster")
        if "treasure" in name or "chest" in name or "gold" in name:
            subjects.append("treasure")
        if not subjects:
            subjects.append("character")

        # 主体大小占比估算（从 impact 的 subject_size 推断）
        subject_size = rank.get("hook_breakdown", {}).get("subject_size", 30)
        size_ratio = min(0.6, subject_size / 100 * 0.5)

        return {
            "subjects": subjects,
            "primary_subject": subjects[0] if subjects else "character",
            "size_ratio": round(size_ratio, 3),
            "center_position": "center" if subject_size > 40 else "varied",
        }

    def _extract_gameplay_dna(self, name: str, rank: dict) -> dict:
        clarity = rank.get("gameplay_clarity", 0)
        clarity_break = rank.get("gameplay_clarity_breakdown", {})

        action = "showcase"
        if any(k in name for k in ["merge", "hecheng", "wanfa", "play"]):
            action = "merge"
        elif any(k in name for k in ["drag", "swipe", "move"]):
            action = "drag"
        elif any(k in name for k in ["evol", "upgrade", "level", "promote"]):
            action = "upgrade"
        elif any(k in name for k in ["unlock", "open", "reveal"]):
            action = "unlock"
        elif any(k in name for k in ["battle", "fight", "boss", "attack"]):
            action = "battle"

        return {
            "action": action,
            "clarity": round(clarity, 1),
            "merge_score": round(clarity_break.get("merge_score", 30), 1),
            "drag_score": round(clarity_break.get("drag_score", 30), 1),
            "upgrade_score": round(clarity_break.get("upgrade_score", 30), 1),
            "before_after": round(clarity_break.get("before_after_score", 30), 1),
            "motion_continuous": round(rank.get("motion_score", 0), 1),
        }

    def _extract_reward_dna(self, name: str, rank: dict) -> dict:
        reward_score = rank.get("reward_score", 0)
        reward_types = rank.get("reward_types", [])

        reward_type = "general"
        if "dragon" in reward_types or "evolution" in reward_types:
            reward_type = "dragon_evolution"
        elif "treasure" in reward_types:
            reward_type = "treasure"
        elif "magic" in reward_types:
            reward_type = "magic_effect"
        elif "unlock" in reward_types:
            reward_type = "new_character"

        return {
            "reward_type": reward_type,
            "reward_score": round(reward_score, 1),
            "reward_types": reward_types,
            "flash_strength": round(rank.get("impact_score", 0) * 0.7, 1),
            "evolution_visible": "evolution" in name or "evol" in name or "upgrade" in name,
        }

    def _extract_structure_dna(self, name: str, rank: dict) -> dict:
        """分析视频节奏结构（基于 Ranking 分数推断）"""
        duration = 15  # 默认15s
        # 从文件名推断时长
        import re
        m = re.search(r'(\d+)s', name)
        if m:
            duration = int(m.group(1))

        hook_strength = rank.get("hook_score_v2", 0)
        gameplay = rank.get("gameplay_clarity", 0)
        reward = rank.get("reward_score", 0)
        impact = rank.get("impact_score", 0)

        # 推断结构比例
        hook_dur = min(3.0, max(1.0, hook_strength / 40))
        gameplay_dur = min(8.0, max(2.0, gameplay / 10))
        reward_dur = min(5.0, max(1.5, reward / 20))
        cta_dur = max(0.5, duration - hook_dur - gameplay_dur - reward_dur)

        return {
            "total_duration": duration,
            "hook_duration": round(hook_dur, 1),
            "gameplay_duration": round(gameplay_dur, 1),
            "reward_duration": round(reward_dur, 1),
            "cta_duration": round(cta_dur, 1),
            "pacing": "fast" if rank.get("motion_score", 0) > 60 else "medium" if rank.get("motion_score", 0) > 30 else "slow",
        }

    def extract_all(self, video_names: List[str]) -> Dict[str, dict]:
        """批量提取"""
        return {name: self.extract(name) for name in video_names}
