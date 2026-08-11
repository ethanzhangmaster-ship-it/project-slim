"""Asset Mapping Engine - 素材映射引擎

每个镜头映射具体素材。

例如:
Background: forest_day
Character: witch_v03
Creature: dragon_red
FX: fire_v02
UI: merge_ui
Music: epic01

后续支持 Eagle / NAS / ComfyUI 统一使用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssetMapping:
    """素材映射"""
    shot_id: str
    asset_reference: str = ""
    background: str = "default_bg"
    character: str = "default_char"
    creature: str = "default_creature"
    fx: str = "default_fx"
    particles: str = "default_particles"
    music: str = "default_music"
    ui: str = "default_ui"
    lut: str = "default_lut"
    environment: str = "default_env"
    source: str = "library"
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "asset_reference": self.asset_reference,
            "background": self.background,
            "character": self.character,
            "creature": self.creature,
            "fx": self.fx,
            "particles": self.particles,
            "music": self.music,
            "ui": self.ui,
            "lut": self.lut,
            "environment": self.environment,
            "source": self.source,
            "path": self.path,
        }


@dataclass
class AssetMap:
    """素材映射表"""
    map_id: str
    variant_id: str
    mappings: list[AssetMapping] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "map_id": self.map_id,
            "variant_id": self.variant_id,
            "mappings": [m.to_dict() for m in self.mappings],
        }


class AssetMappingEngine:
    """素材映射引擎"""

    # 环境 → 背景素材
    ENV_TO_BG: dict[str, str] = {
        "magic_forest": "forest_day",
        "dark_forest": "forest_night",
        "enchanted_castle": "castle_interior",
        "candy_kingdom": "candy_land",
        "floating_island": "sky_island",
    }

    # 角色 → 角色素材
    CHAR_TO_ASSET: dict[str, str] = {
        "witch": "witch_v03",
        "warrior": "warrior_v02",
        "princess": "princess_v01",
    }

    # 生物 → 生物素材
    CREATURE_TO_ASSET: dict[str, str] = {
        "dragon": "dragon_red",
        "wolf": "wolf_grey",
        "phoenix": "phoenix_gold",
        "unicorn": "unicorn_white",
    }

    # 段落 → FX
    SEGMENT_TO_FX: dict[str, str] = {
        "Hook": "glow_v01",
        "Boss": "fire_v02",
        "Victory": "confetti_v01",
        "Reward": "coin_burst_v02",
        "CTA": "button_glow_v01",
    }

    # 段落 → 粒子
    SEGMENT_TO_PARTICLE: dict[str, str] = {
        "Hook": "sparkle_gold",
        "Boss": "ember_dark",
        "Victory": "confetti_multi",
        "Reward": "coin_gold",
        "CTA": "shimmer_white",
    }

    # 情绪 → LUT
    EMOTION_TO_LUT: dict[str, str] = {
        "Urgent": "lut_warm_01",
        "Excited": "lut_vibrant_02",
        "Epic": "lut_cinematic_01",
        "Warm": "lut_soft_01",
        "Curiosity": "lut_cool_01",
        "Wonder": "lut_dreamy_01",
    }

    # 音乐风格 → 音乐
    MUSIC_TO_TRACK: dict[str, str] = {
        "Epic": "epic01",
        "Upbeat": "upbeat02",
        "Ambient": "ambient03",
        "Dramatic": "dramatic01",
    }

    def generate(self, dna: VideoDNA, shotlist: Shotlist) -> AssetMap:
        """根据 Video DNA 和 Shotlist 生成素材映射"""
        dna_data = dna.metadata.get("dna_data", {})
        env = dna_data.get("environment", {}).get("type", "magic_forest")
        char = dna_data.get("character", {}).get("type", "witch")
        creatures = dna_data.get("creatures", [{}])
        creature = creatures[0].get("type", "dragon") if creatures else "dragon"

        bg = self.ENV_TO_BG.get(env, "forest_day")
        char_asset = self.CHAR_TO_ASSET.get(char, "witch_v03")
        creature_asset = self.CREATURE_TO_ASSET.get(creature, "dragon_red")
        lut = self.EMOTION_TO_LUT.get(dna.emotion, "lut_vibrant_02")
        music = self.MUSIC_TO_TRACK.get(dna.music_style, "upbeat02")

        mappings = []
        for shot in shotlist.shots:
            seg_name = shot.scene_name
            fx = self.SEGMENT_TO_FX.get(seg_name, "glow_v01")
            particle = self.SEGMENT_TO_PARTICLE.get(seg_name, "sparkle_gold")
            ui = "merge_ui" if "Merge" in seg_name or "Gameplay" in seg_name else "default_ui"

            mappings.append(AssetMapping(
                shot_id=shot.shot_id,
                asset_reference=f"ASSET_{shot.shot_id}",
                background=bg,
                character=char_asset,
                creature=creature_asset,
                fx=fx,
                particles=particle,
                music=music,
                ui=ui,
                lut=lut,
                environment=env,
                source="library",
                path=f"library://{bg}/{char_asset}/{creature_asset}",
            ))

        return AssetMap(
            map_id=f"assetmap_{dna.variant_id}",
            variant_id=dna.variant_id,
            mappings=mappings,
        )
