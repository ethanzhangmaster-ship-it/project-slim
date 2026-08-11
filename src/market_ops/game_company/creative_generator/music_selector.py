from typing import Dict, List, Any, Optional
from .variant_engine import CreativeAsset


class MusicSelector:
    def __init__(self):
        self._sfx_options = {
            "collection": ["coin pickup", "merge success", "collection complete fanfare", "card flip"],
            "reward": ["explosion", "power up", "epic reveal", "magic chime", "ascension"],
            "curiosity": ["mystery tone", "question mark jingle", "unlock sound", "reveal shimmer"],
            "comparison": ["whoosh transition", "time lapse tick", "transformation rumble"],
            "crisis": ["alarm bell", "battle drum", "epic horn", "rescue fanfare", "victory cheer"],
        }
        self._sfx_general = ["button click", "ui swoosh", "magic sparkle", "level up chime", "notification pop"]

    def select(self, asset: CreativeAsset) -> Dict[str, Any]:
        hook_type = asset.hook_type
        music = asset.music if hasattr(asset, 'music') and asset.music else {"mood": "whimsical", "genre": "orchestral fantasy", "bpm": 100}
        sfx = self._sfx_options.get(hook_type, self._sfx_options["collection"]) + self._sfx_general

        return {
            "music": {
                "mood": music.get("mood", "whimsical"),
                "genre": music.get("genre", "orchestral fantasy"),
                "bpm": music.get("bpm", 110),
                "instruments": music.get("instruments", "strings, harp, flute"),
                "duration": "20 seconds",
                "format": "loopable",
                "key": "C major",
            },
            "sound_effects": [
                {"time": "0s", "sound": sfx[0], "type": "UI"},
                {"time": "0.8s", "sound": sfx[1] if len(sfx) > 1 else sfx[0], "type": "transition"},
                {"time": "3s", "sound": sfx[2] if len(sfx) > 2 else sfx[0], "type": "gameplay"},
                {"time": "6s", "sound": sfx[3] if len(sfx) > 3 else sfx[0], "type": "reward"},
                {"time": "12s", "sound": sfx[4] if len(sfx) > 4 else sfx[0], "type": "collection"},
                {"time": "15s", "sound": sfx[0], "type": "social"},
                {"time": "18s", "sound": sfx[1] if len(sfx) > 1 else sfx[0], "type": "CTA"},
            ],
            "silence": "No silence (continuous)",
            "mixing_notes": f"Music at -12dB, SFX at -6dB. Voiceover at -3dB. {music.get('mood', 'whimsical').title()} underscore throughout.",
        }

    def get_stats(self) -> Dict[str, Any]:
        return {"total_hook_sfx_templates": len(self._sfx_options), "total_general_sfx": len(self._sfx_general)}
