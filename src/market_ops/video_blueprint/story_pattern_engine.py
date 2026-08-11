"""Story Pattern Engine - 动态故事模式引擎

不要固定 Hook → Gameplay → Reward → CTA，
而是根据玩法自动生成。

支持:
- Collection
- Merge
- Boss
- Puzzle
- Decoration
- Idle
- Battle
- Simulation
- RPG
- Match3

例如:
Collection: Hook → Search → Collect → Reward → CTA
Boss:       Hook → Boss → Fail → Retry → Victory → CTA
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StorySegment:
    """故事段落"""
    name: str
    duration_ratio: float   # 占时长的比例
    description: str
    required_elements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ratio": self.duration_ratio,
            "description": self.description,
            "required_elements": self.required_elements,
        }


@dataclass
class StoryPattern:
    """故事模式"""
    pattern_id: str
    variant_id: str
    gameplay_type: str
    segments: list[StorySegment] = field(default_factory=list)
    total_segments: int = 0
    recommended_duration: int = 15

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "variant_id": self.variant_id,
            "gameplay_type": self.gameplay_type,
            "segments": [s.to_dict() for s in self.segments],
            "total_segments": self.total_segments,
            "recommended_duration": self.recommended_duration,
        }


class StoryPatternEngine:
    """动态故事模式引擎"""

    # 玩法类型 → 故事段落模板
    GAMEPLAY_PATTERNS: dict[str, list[dict[str, Any]]] = {
        "Collection": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Curious moment", "elements": ["collectible_item", "glow"]},
            {"name": "Search",   "ratio": 0.25, "desc": "Finding items", "elements": ["exploration", "hint"]},
            {"name": "Collect",  "ratio": 0.30, "desc": "Collecting action", "elements": ["tap", "merge", "combo"]},
            {"name": "Reward",   "ratio": 0.20, "desc": "Reward reveal", "elements": ["chest", "coins", "celebration"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Call to action", "elements": ["button", "download"]},
        ],
        "Merge": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Mergeable items appear", "elements": ["items", "glow"]},
            {"name": "Merge",    "ratio": 0.30, "desc": "Swiping to merge", "elements": ["swipe", "merge_effect"]},
            {"name": "Upgrade",  "ratio": 0.25, "desc": "New item revealed", "elements": ["evolution", "sparkle"]},
            {"name": "Reward",   "ratio": 0.20, "desc": "Rare item reward", "elements": ["rare_item", "fx"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Play now", "elements": ["button"]},
        ],
        "Boss": [
            {"name": "Hook",     "ratio": 0.12, "desc": "Boss entrance", "elements": ["boss", "dramatic"]},
            {"name": "Boss",     "ratio": 0.25, "desc": "Boss battle", "elements": ["attack", "dodge"]},
            {"name": "Fail",     "ratio": 0.15, "desc": "Player fails", "elements": ["fail", "retry_button"]},
            {"name": "Retry",    "ratio": 0.15, "desc": "Retry with new strategy", "elements": ["upgrade", "power_up"]},
            {"name": "Victory",  "ratio": 0.18, "desc": "Boss defeated", "elements": ["victory", "rewards"]},
            {"name": "CTA",      "ratio": 0.15, "desc": "Download and fight", "elements": ["button"]},
        ],
        "Puzzle": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Puzzle appears", "elements": ["puzzle_board"]},
            {"name": "Think",    "ratio": 0.20, "desc": "Player thinking", "elements": ["contemplation"]},
            {"name": "Solve",    "ratio": 0.30, "desc": "Solving puzzle", "elements": ["match", "clear"]},
            {"name": "Reward",   "ratio": 0.25, "desc": "Level complete", "elements": ["stars", "coins"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Next puzzle", "elements": ["button"]},
        ],
        "Match3": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Colorful board", "elements": ["gems", "board"]},
            {"name": "Match",    "ratio": 0.30, "desc": "Matching gems", "elements": ["swap", "combo"]},
            {"name": "Combo",    "ratio": 0.25, "desc": "Chain reaction", "elements": ["cascade", "explosion"]},
            {"name": "Reward",   "ratio": 0.20, "desc": "Score explosion", "elements": ["score", "celebration"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Play now", "elements": ["button"]},
        ],
        "Battle": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Enemy appears", "elements": ["enemy", "threat"]},
            {"name": "Attack",   "ratio": 0.30, "desc": "Combat sequence", "elements": ["attack", "skill"]},
            {"name": "Special",  "ratio": 0.20, "desc": "Ultimate move", "elements": ["ultimate", "fx"]},
            {"name": "Victory",  "ratio": 0.25, "desc": "Winning scene", "elements": ["victory", "loot"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Join battle", "elements": ["button"]},
        ],
        "Idle": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Idle rewards building", "elements": ["idle_ui", "timer"]},
            {"name": "Build",    "ratio": 0.30, "desc": "Upgrading structures", "elements": ["build", "progress"]},
            {"name": "Collect",  "ratio": 0.25, "desc": "Collecting idle income", "elements": ["coins", "multiplier"]},
            {"name": "Expand",   "ratio": 0.20, "desc": "New area unlocked", "elements": ["unlock", "map"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Start idling", "elements": ["button"]},
        ],
        "Simulation": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Life simulation begins", "elements": ["character", "room"]},
            {"name": "Interact", "ratio": 0.30, "desc": "Player interactions", "elements": ["tap", "decorate"]},
            {"name": "Upgrade",  "ratio": 0.25, "desc": "Room/item upgrade", "elements": ["upgrade", "new_item"]},
            {"name": "Reveal",   "ratio": 0.20, "desc": "New room revealed", "elements": ["room", "surprise"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Play your story", "elements": ["button"]},
        ],
        "RPG": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Hero appears", "elements": ["hero", "weapon"]},
            {"name": "Quest",    "ratio": 0.25, "desc": "Quest accepted", "elements": ["quest", "map"]},
            {"name": "Battle",   "ratio": 0.25, "desc": "Monster battle", "elements": ["combat", "skill"]},
            {"name": "LevelUp",  "ratio": 0.20, "desc": "Level up celebration", "elements": ["level_up", "stats"]},
            {"name": "CTA",      "ratio": 0.15, "desc": "Start adventure", "elements": ["button"]},
        ],
        "Decoration": [
            {"name": "Hook",     "ratio": 0.15, "desc": "Empty space", "elements": ["empty_room"]},
            {"name": "Decorate", "ratio": 0.30, "desc": "Placing furniture", "elements": ["drag", "place"]},
            {"name": "Style",    "ratio": 0.25, "desc": "Theme applied", "elements": ["theme", "color"]},
            {"name": "Reveal",   "ratio": 0.20, "desc": "Room complete", "elements": ["finished_room"]},
            {"name": "CTA",      "ratio": 0.10, "desc": "Design your own", "elements": ["button"]},
        ],
    }

    def generate(self, dna: VideoDNA, variant: dict[str, Any]) -> StoryPattern:
        """根据 Video DNA 和 Decision Variant 生成故事模式"""
        # 推断玩法类型
        gameplay_type = self._infer_gameplay(dna, variant)
        segments_template = self.GAMEPLAY_PATTERNS.get(gameplay_type, self.GAMEPLAY_PATTERNS["Collection"])

        segments = []
        for seg_tpl in segments_template:
            segments.append(StorySegment(
                name=seg_tpl["name"],
                duration_ratio=seg_tpl["ratio"],
                description=seg_tpl["desc"],
                required_elements=list(seg_tpl["elements"]),
            ))

        return StoryPattern(
            pattern_id=f"pattern_{dna.variant_id}",
            variant_id=dna.variant_id,
            gameplay_type=gameplay_type,
            segments=segments,
            total_segments=len(segments),
            recommended_duration=self._recommend_duration(dna),
        )

    def _infer_gameplay(self, dna: VideoDNA, variant: dict[str, Any]) -> str:
        """推断玩法类型"""
        hook = dna.hook
        dim = variant.get("changed_dimension", "")
        dna_data = variant.get("dna", {})

        # 从 Hook 推断
        hook_to_gameplay = {
            "Collection": "Collection",
            "Merge": "Merge",
            "Boss": "Boss",
            "Puzzle": "Puzzle",
            "Battle": "Battle",
            "Story": "RPG",
        }
        if hook in hook_to_gameplay:
            return hook_to_gameplay[hook]

        # 从 DNA gameplay 推断
        gp = dna_data.get("gameplay", {})
        gp_type = gp.get("type", "")
        if gp_type in self.GAMEPLAY_PATTERNS:
            return gp_type

        # 默认
        return "Collection"

    def _recommend_duration(self, dna: VideoDNA) -> int:
        """推荐时长"""
        rhythm = dna.rhythm
        if rhythm == "Fast":
            return 15
        if rhythm == "Medium":
            return 20
        return 30
