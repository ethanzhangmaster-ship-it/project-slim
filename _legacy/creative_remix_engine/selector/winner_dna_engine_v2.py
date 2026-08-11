"""Winner DNA Engine V2 — 接入Creative Intelligence V4.6"""
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, field

from ..config import MEMORY_DIR


@dataclass
class WinnerDNAV2:
    """V2 Winner DNA"""
    theme: List[str] = field(default_factory=list)
    visual_style: List[str] = field(default_factory=list)
    structure: List[str] = field(default_factory=list)
    emotion_arc: List[str] = field(default_factory=list)
    hook: Dict[str, Any] = field(default_factory=dict)
    gameplay: Dict[str, Any] = field(default_factory=dict)
    ending: Dict[str, Any] = field(default_factory=dict)
    avg_ctr: float = 0
    avg_cvr: float = 0
    avg_roas: float = 0


class WinnerDNAEngineV2:
    """V2: 从Creative Intelligence V4.6读取Winner DNA"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.dna_file = MEMORY_DIR / "winner_dna_v2.json"
        self.dna = self._load_or_create()

    def _load_or_create(self) -> WinnerDNAV2:
        """加载或创建默认DNA"""
        if self.dna_file.exists():
            try:
                with open(self.dna_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return WinnerDNAV2(**data)
            except:
                pass

        # 默认DNA
        return WinnerDNAV2(
            theme=["witch", "dragon", "castle"],
            visual_style=["high_contrast", "bright_color", "dynamic"],
            structure=["hook", "problem", "gameplay", "reward", "cta"],
            emotion_arc=["surprise", "tension", "excitement", "satisfaction"],
            hook={"type": "visual_shock", "duration": "0-3", "objects": ["witch", "dragon"]},
            gameplay={"merge": True, "combo": True, "speed": "fast"},
            ending={"reward": True, "upgrade": True, "cta": True},
            avg_ctr=0.035,
            avg_cvr=0.012,
            avg_roas=1.8,
        )

    def save(self):
        """保存DNA"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.dna_file, "w", encoding="utf-8") as f:
            json.dump(self.dna.__dict__, f, ensure_ascii=False, indent=2, default=str)

    def match_score(self, creative_features: Dict) -> float:
        """
        计算创意与Winner DNA的匹配分 (0-100)
        """
        score = 0
        max_score = 0

        # Theme匹配 (30分)
        if "theme" in creative_features:
            theme_overlap = len(set(creative_features["theme"]) & set(self.dna.theme))
            score += min(theme_overlap * 15, 30)
        max_score += 30

        # Hook类型匹配 (25分)
        if "hook_type" in creative_features:
            if creative_features["hook_type"] == self.dna.hook.get("type"):
                score += 25
            else:
                score += 10
        max_score += 25

        # Gameplay匹配 (20分)
        if "gameplay_features" in creative_features:
            gp = creative_features["gameplay_features"]
            if self.dna.gameplay.get("merge") and gp.get("merge"):
                score += 10
            if self.dna.gameplay.get("combo") and gp.get("combo"):
                score += 10
        max_score += 20

        # Ending匹配 (15分)
        if "ending_features" in creative_features:
            end = creative_features["ending_features"]
            if self.dna.ending.get("reward") and end.get("reward"):
                score += 8
            if self.dna.ending.get("upgrade") and end.get("upgrade"):
                score += 7
        max_score += 15

        # Visual Style匹配 (10分)
        if "visual_style" in creative_features:
            style_overlap = len(set(creative_features["visual_style"]) & set(self.dna.visual_style))
            score += min(style_overlap * 5, 10)
        max_score += 10

        return min(100, score / max_score * 100) if max_score > 0 else 50

    def evolve(self, winner_features: List[Dict], loser_features: List[Dict]):
        """根据赢家和输家进化DNA"""
        # 统计赢家主题
        from collections import Counter
        themes = Counter()
        for wf in winner_features:
            for t in wf.get("theme", []):
                themes[t] += 1

        if themes:
            self.dna.theme = [t for t, c in themes.most_common(5)]

        # 统计赢家hook类型
        hook_types = Counter(wf.get("hook_type", "") for wf in winner_features if wf.get("hook_type"))
        if hook_types:
            self.dna.hook["type"] = hook_types.most_common(1)[0][0]

        # 保存
        self.save()
