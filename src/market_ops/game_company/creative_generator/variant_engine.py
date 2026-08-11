from typing import Dict, List, Any, Optional
from datetime import datetime
import random

from .creative_factory import (
    HEROES, ENVIRONMENTS, MERGE_OBJECTS, REWARDS, CAMERAS,
    CTAS, HOOK_SCRIPTS, MUSIC_STYLES, SUBSCENE_TEMPLATES,
)


def _combine(available: List[Dict], existing: List[str]) -> Optional[Dict]:
    candidates = [c for c in available if c["id"] not in existing]
    return random.choice(candidates) if candidates else random.choice(available)


class CreativeConfig:
    def __init__(self, project: str = "P04 Witch", hook_type: str = "collection", direction: str = None):
        self.project = project
        self.hook_type = hook_type if hook_type in HOOK_SCRIPTS else "collection"
        self.direction = direction or hook_type or "collection"

    def to_dict(self) -> Dict[str, str]:
        return {"project": self.project, "hook_type": self.hook_type, "direction": self.direction}


class CreativeAsset:
    def __init__(self, creative_id: str, project: str = "P04 Witch", hook_type: str = "collection", **kwargs):
        self.creative_id = creative_id
        self.project = project
        self.hook_type = hook_type
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._validate_defaults()

    def _validate_defaults(self):
        if not hasattr(self, "hero") or not self.hero:
            self.hero = {}
        if not hasattr(self, "environment") or not self.environment:
            self.environment = {}
        if not hasattr(self, "merge_object") or not self.merge_object:
            self.merge_object = {}
        if not hasattr(self, "reward") or not self.reward:
            self.reward = {}
        if not hasattr(self, "camera") or not self.camera:
            self.camera = {}
        if not hasattr(self, "cta") or not self.cta:
            self.cta = {}
        if not hasattr(self, "music") or not self.music:
            self.music = {}
        if not hasattr(self, "title") or not self.title:
            self.title = f"Creative {self.creative_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "title": self.title,
            "hook_type": self.hook_type,
            "hero": self.hero,
            "environment": self.environment,
            "merge_object": self.merge_object,
            "reward": self.reward,
            "camera": self.camera,
            "cta": self.cta,
            "music": self.music,
        }


class VariantEngine:
    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)
        self._used_combinations: List[str] = []

    def _combo_key(self, asset: CreativeAsset) -> str:
        return f"{asset.hero.get('id')}_{asset.environment.get('id')}_{asset.merge_object.get('id')}_{asset.reward.get('id')}"

    def _is_duplicate(self, asset: CreativeAsset) -> bool:
        key = self._combo_key(asset)
        if key in self._used_combinations:
            return True
        self._used_combinations.append(key)
        return False

    def generate_variant(self, config: CreativeConfig, creative_id: str) -> CreativeAsset:
        all_ids = {"heroes": [], "envs": [], "objects": [], "rewards": [], "cameras": [], "ctas": []}

        used_heroes = list(all_ids["heroes"])
        used_envs = list(all_ids["envs"])
        used_objects = list(all_ids["objects"])
        used_rewards = list(all_ids["rewards"])
        used_cameras = list(all_ids["cameras"])
        used_ctas = list(all_ids["ctas"])

        for key in self._used_combinations:
            parts = key.split("_")
            if len(parts) >= 1:
                all_ids["heroes"].append(parts[0])
            if len(parts) >= 2:
                all_ids["envs"].append(parts[1])
            if len(parts) >= 3:
                all_ids["objects"].append(parts[2])
            if len(parts) >= 4:
                all_ids["rewards"].append(parts[3])

        max_attempts = 50
        for _ in range(max_attempts):
            hero = _combine(HEROES, all_ids["heroes"])
            env = _combine(ENVIRONMENTS, all_ids["envs"])
            obj = _combine(MERGE_OBJECTS, all_ids["objects"])
            reward = _combine(REWARDS, all_ids["rewards"])
            camera = _combine(CAMERAS, all_ids["cameras"])
            cta_obj = _combine(CTAS, all_ids["ctas"])

            music = random.choice(MUSIC_STYLES)
            hook_script = HOOK_SCRIPTS.get(config.hook_type, HOOK_SCRIPTS["collection"])

            title_parts = [
                hero.get("name", "Witch"),
                "+",
                obj.get("name", "Merge"),
                "-",
                hook_script.get("hook_line", "").split("!")[0][:40],
            ]
            title = " ".join(title_parts)

            asset = CreativeAsset(
                creative_id=creative_id,
                project=config.project,
                hero=hero,
                environment=env,
                merge_object=obj,
                reward=reward,
                camera=camera,
                cta=cta_obj,
                hook_script={"hook_type": config.hook_type, **hook_script},
                music=music,
                title=title,
                hook_type=config.hook_type,
            )

            if not self._is_duplicate(asset):
                return asset

        return asset

    def generate_variants(self, config: CreativeConfig, count: int) -> List[CreativeAsset]:
        self._used_combinations = []
        assets = []
        for i in range(count):
            cid = f"creative_{i+1:03d}"
            asset = self.generate_variant(config, cid)
            assets.append(asset)
        return assets

    def get_stats(self) -> Dict[str, Any]:
        return {"used_combinations": len(self._used_combinations)}
