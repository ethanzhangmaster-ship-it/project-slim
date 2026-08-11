"""Phase 1: AI Story Planner — 非固定故事结构生成器 V3.4

基于 Winner DNA 和市场数据，自动生成差异化故事板。
支持5种故事原型：rescue / revenge / evolution / challenge / impossible_level
"""
import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ..config import MEMORY_DIR


@dataclass
class StoryBeat:
    """故事节拍 = 一个镜头"""
    beat_id: str
    role: str  # hook / problem / gameplay / reward / cta
    duration: float
    subtitle: str
    subtitle_style: str  # normal / big / urgent / whisper
    visual_direction: str
    transition_in: str  # hard_cut / zoom_in / impact_hit / flash_white / fade
    emotion_target: str
    sound_hint: str = ""


@dataclass
class StoryPlan:
    """完整故事板"""
    plan_id: str
    story_type: str
    title: str
    emotion_arc: List[str]
    beats: List[StoryBeat] = field(default_factory=list)
    total_duration: float = 15.0
    target_ratio: str = "9X16"
    dna_match_score: float = 0


# ===== 故事模板库 =====
STORY_TEMPLATES = {
    "rescue": {
        "title": "Rescue the Witch",
        "emotion_arc": ["curiosity", "tension", "excitement", "satisfaction"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "The Witch is TRAPPED!",
             "style": "big", "visual": "witch trapped in dark cage, close-up",
             "transition": "zoom_in", "emotion": "shock", "sound": "heartbeat"},
            {"role": "problem", "duration": 2.5, "subtitle": "Only YOU can save her",
             "style": "urgent", "visual": "player finger tapping screen",
             "transition": "hard_cut", "emotion": "urgency", "sound": "clock_tick"},
            {"role": "gameplay", "duration": 6.0, "subtitle": "MERGE → EVOLVE → RESCUE",
             "style": "normal", "visual": "fast merge chain, dragon appearing",
             "transition": "impact_hit", "emotion": "excitement", "sound": "combo_sfx"},
            {"role": "reward", "duration": 2.5, "subtitle": "SHE'S FREE! ✨",
             "style": "big", "visual": "witch transforming, bright light",
             "transition": "flash_white", "emotion": "triumph", "sound": "magic_burst"},
            {"role": "cta", "duration": 1.5, "subtitle": "Download & Save Her Now",
             "style": "urgent", "visual": "app store icon + character pose",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ]
    },
    "revenge": {
        "title": "Witch's Revenge",
        "emotion_arc": ["anger", "determination", "power", "victory"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "They took EVERYTHING",
             "style": "big", "visual": "castle burning, witch silhouette",
             "transition": "zoom_in", "emotion": "rage", "sound": "thunder"},
            {"role": "problem", "duration": 2.0, "subtitle": "But she has a SECRET",
             "style": "whisper", "visual": "ancient spell book glowing",
             "transition": "flash_white", "emotion": "mystery", "sound": "whisper"},
            {"role": "gameplay", "duration": 6.5, "subtitle": "Merge to UNLEASH HELL",
             "style": "normal", "visual": "explosive merges, dragon attacks",
             "transition": "impact_hit", "emotion": "power", "sound": "explosion"},
            {"role": "reward", "duration": 2.5, "subtitle": "VICTORY IS YOURS 🔥",
             "style": "big", "visual": "dragon breathing fire on enemies",
             "transition": "zoom_in", "emotion": "triumph", "sound": "victory_horn"},
            {"role": "cta", "duration": 1.5, "subtitle": "Join the Revenge",
             "style": "urgent", "visual": "download button pulsating",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ]
    },
    "evolution": {
        "title": "From Egg to Dragon God",
        "emotion_arc": ["curiosity", "anticipation", "amazement", "satisfaction"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "Level 1 🥚 vs Level 99 🐉",
             "style": "big", "visual": "tiny egg vs massive dragon side by side",
             "transition": "hard_cut", "emotion": "curiosity", "sound": "pop"},
            {"role": "problem", "duration": 2.0, "subtitle": "Can you reach the MAX?",
             "style": "normal", "visual": "level bar filling slowly",
             "transition": "zoom_in", "emotion": "challenge", "sound": "level_up"},
            {"role": "gameplay", "duration": 7.0, "subtitle": "SWIPE → MERGE → EVOLVE",
             "style": "normal", "visual": "continuous merge chain, rapid evolution",
             "transition": "impact_hit", "emotion": "excitement", "sound": "combo_sfx"},
            {"role": "reward", "duration": 2.0, "subtitle": "ULTIMATE FORM UNLOCKED",
             "style": "big", "visual": "legendary dragon with aura, screen shake",
             "transition": "flash_white", "emotion": "amazement", "sound": "epic_fanfare"},
            {"role": "cta", "duration": 1.5, "subtitle": "Evolve Yours Now",
             "style": "urgent", "visual": "character collection showcase",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ]
    },
    "challenge": {
        "title": "Impossible Merge Challenge",
        "emotion_arc": ["confidence", "frustration", "determination", "triumph"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "99% CAN'T Pass Level 47",
             "style": "big", "visual": "failed attempt counter at 99",
             "transition": "zoom_in", "emotion": "challenge", "sound": "buzzer"},
            {"role": "problem", "duration": 2.5, "subtitle": "The board is FULL!",
             "style": "urgent", "visual": "grid packed with items, timer at 3s",
             "transition": "hard_cut", "emotion": "tension", "sound": "heartbeat"},
            {"role": "gameplay", "duration": 6.0, "subtitle": "ONE perfect move...",
             "style": "normal", "visual": "slow motion merge, chain reaction",
             "transition": "impact_hit", "emotion": "hope", "sound": "swoosh"},
            {"role": "reward", "duration": 2.5, "subtitle": "GENIUS! 🧠✨",
             "style": "big", "visual": "victory screen, confetti",
             "transition": "flash_white", "emotion": "triumph", "sound": "cheer"},
            {"role": "cta", "duration": 1.5, "subtitle": "Can YOU beat it?",
             "style": "urgent", "visual": "finger tapping download",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ]
    },
    "impossible_level": {
        "title": "The Final Boss Battle",
        "emotion_arc": ["fear", "desperation", "hope", "glory"],
        "beats": [
            {"role": "hook", "duration": 2.5, "subtitle": "This Boss is UNBEATABLE",
             "style": "big", "visual": "giant boss shadow, HP bar massive",
             "transition": "zoom_in", "emotion": "fear", "sound": "roar"},
            {"role": "problem", "duration": 2.0, "subtitle": "Your team is WEAK",
             "style": "whisper", "visual": "low-level characters trembling",
             "transition": "hard_cut", "emotion": "despair", "sound": "sigh"},
            {"role": "gameplay", "duration": 7.0, "subtitle": "MERGE = POWER UP",
             "style": "normal", "visual": "rapid merges, characters leveling up",
             "transition": "impact_hit", "emotion": "hope", "sound": "power_up"},
            {"role": "reward", "duration": 2.0, "subtitle": "IMPOSSIBLE IS NOTHING",
             "style": "big", "visual": "boss defeated, legendary drop",
             "transition": "flash_white", "emotion": "glory", "sound": "epic_fanfare"},
            {"role": "cta", "duration": 1.5, "subtitle": "Face the Boss Now",
             "style": "urgent", "visual": "boss icon + download CTA",
             "transition": "fade", "emotion": "desire", "sound": "click"},
        ]
    },
}


class StoryPlanner:
    """AI Story Planner — 基于 Winner DNA 生成差异化故事板"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.dna = self._load_dna()
        self.templates = STORY_TEMPLATES

    def _load_dna(self) -> Dict:
        """加载 Winner DNA V2"""
        dna_file = MEMORY_DIR / "winner_dna_v2.json"
        if dna_file.exists():
            try:
                with open(dna_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "theme": ["witch", "dragon", "castle"],
            "emotion_arc": ["surprise", "tension", "excitement", "satisfaction"],
            "avg_roas": 1.8,
        }

    def select_story_type(self, dna_override: Optional[str] = None) -> str:
        """
        基于 DNA 选择最佳故事类型。
        也可以外部强制指定。
        """
        if dna_override and dna_override in self.templates:
            return dna_override

        theme = self.dna.get("theme", [])
        emotion = self.dna.get("emotion_arc", [])

        # 主题 → 故事映射
        scores = {k: 50 for k in self.templates}
        if "witch" in theme:
            scores["rescue"] += 25
            scores["revenge"] += 20
        if "dragon" in theme:
            scores["evolution"] += 25
            scores["impossible_level"] += 15
        if "castle" in theme:
            scores["challenge"] += 15

        # 情绪弧线 → 故事映射
        if "surprise" in emotion or "shock" in emotion:
            scores["rescue"] += 10
            scores["impossible_level"] += 10
        if "anger" in emotion or "power" in emotion:
            scores["revenge"] += 15
        if "curiosity" in emotion or "amazement" in emotion:
            scores["evolution"] += 10
        if "frustration" in emotion or "determination" in emotion:
            scores["challenge"] += 10

        # 加入随机性避免重复
        for k in scores:
            scores[k] += random.randint(-10, 10)

        return max(scores, key=scores.get)

    def generate_plan(self, story_type: Optional[str] = None,
                      plan_id: str = "plan_001") -> StoryPlan:
        """生成完整故事板"""
        stype = story_type or self.select_story_type()
        template = self.templates.get(stype, self.templates["evolution"])

        beats = []
        t = 0.0
        for i, b in enumerate(template["beats"]):
            beat = StoryBeat(
                beat_id=f"{plan_id}_b{i:02d}",
                role=b["role"],
                duration=b["duration"],
                subtitle=b["subtitle"],
                subtitle_style=b["style"],
                visual_direction=b["visual"],
                transition_in=b["transition"],
                emotion_target=b["emotion"],
                sound_hint=b.get("sound", ""),
            )
            beats.append(beat)
            t += b["duration"]

        # 微调总时长到目标 15s
        target = 15.0
        if t != target and beats:
            scale = target / t
            for b in beats:
                b.duration = round(b.duration * scale, 2)
            t = round(sum(b.duration for b in beats), 2)

        # DNA 匹配分
        dna_match = self._calc_dna_match(stype)

        return StoryPlan(
            plan_id=plan_id,
            story_type=stype,
            title=template["title"],
            emotion_arc=template["emotion_arc"],
            beats=beats,
            total_duration=t,
            target_ratio="9X16",
            dna_match_score=dna_match,
        )

    def _calc_dna_match(self, story_type: str) -> float:
        """计算故事类型与 DNA 的匹配分"""
        theme = self.dna.get("theme", [])
        score = 60
        if story_type == "rescue" and "witch" in theme:
            score += 20
        if story_type == "evolution" and "dragon" in theme:
            score += 20
        if story_type == "revenge" and "castle" in theme:
            score += 15
        return min(score, 100)

    def generate_batch(self, count: int = 3) -> List[StoryPlan]:
        """生成一批差异化故事板"""
        plans = []
        types_used = []
        for i in range(count):
            # 尽量保证多样性
            stype = self.select_story_type()
            attempts = 0
            while stype in types_used and attempts < 5:
                stype = self.select_story_type()
                attempts += 1
            types_used.append(stype)

            plan = self.generate_plan(stype, plan_id=f"plan_{i+1:03d}")
            plans.append(plan)
        return plans
