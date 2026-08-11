from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import random


WINNER_DNA_REAL = {
    "preferred_heroes": [
        {"id": "witch", "name": "Cute Witch", "weight": 0.93, "count": 357},
        {"id": "dragon", "name": "Baby Dragon", "weight": 0.75, "count": 280},
        {"id": "castle", "name": "Dark Castle", "weight": 0.45, "count": 120},
        {"id": "egg", "name": "Magic Egg", "weight": 0.52, "count": 180},
        {"id": "magic_forest", "name": "Magic Forest", "weight": 0.38, "count": 95},
    ],
    "preferred_story": {
        "hook": {"primary": "collection", "weight": 0.621, "count": 239},
        "merge": {"weight": 0.35, "description": "clear merge progression with arrows"},
        "collection": {"weight": 0.62, "description": "200+ creatures to collect"},
        "reward": {"weight": 0.25, "description": "evolution/level-up reveal"},
        "cta": {"style": "banner_bottom", "preferred": ["ornate golden banner", "parchment banner"]},
    },
    "preferred_color": {
        "palette": "warm",
        "warm_count": 1039,
        "cool_count": 790,
        "saturation_min": 0.45,
        "contrast_min": 0.15,
        "dominant_palette": "warm golden yellows, soft purples, pastel blues",
    },
    "preferred_layout": {
        "framing": "center_subject",
        "alternative": "left_right_dynamic",
        "aspect_ratio": "9:16",
        "subject_fill_min": 0.30,
        "center_zone": 0.40,
    },
    "preferred_ui": {
        "text_density_max": 0.015,
        "preferred_elements": ["game logo", "arrow indicators", "merge progress bar", "collection counter"],
        "no_text_first_3s": True,
        "cta_timing": "last_3_seconds",
    },
    "winner_vs_loser": {
        "winner_only": [
            "reward hook",
            "clear merge progression shown with arrows",
            "power fantasy payoff with max level reveal",
            "dramatic before/after character evolution",
            "satisfying merge progression visualization",
            "rich cosmic fantasy aesthetic with glowing effects",
        ],
        "loser_only": [
            "curiosity hook",
            "comparison hook",
            "numbered mystery reveal at step 5",
            "dense array of cute collectible creatures",
        ],
    },
}


@dataclass
class WinnerDNA:
    preferred_heroes: List[Dict[str, Any]] = field(default_factory=list)
    preferred_story: Dict[str, Any] = field(default_factory=dict)
    preferred_color: Dict[str, Any] = field(default_factory=dict)
    preferred_layout: Dict[str, Any] = field(default_factory=dict)
    preferred_ui: Dict[str, Any] = field(default_factory=dict)
    winner_vs_loser: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_real_data(cls) -> "WinnerDNA":
        d = WINNER_DNA_REAL
        return cls(
            preferred_heroes=d["preferred_heroes"],
            preferred_story=d["preferred_story"],
            preferred_color=d["preferred_color"],
            preferred_layout=d["preferred_layout"],
            preferred_ui=d["preferred_ui"],
            winner_vs_loser=d["winner_vs_loser"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preferred_heroes": self.preferred_heroes,
            "preferred_story": self.preferred_story,
            "preferred_color": self.preferred_color,
            "preferred_layout": self.preferred_layout,
            "preferred_ui": self.preferred_ui,
            "winner_vs_loser": self.winner_vs_loser,
        }

    def match_hero(self, hero_name: str) -> float:
        hname = hero_name.lower()
        for h in self.preferred_heroes:
            if h["id"] in hname or h["name"].lower() in hname:
                return h["weight"]
        return 0.0

    def get_top_heroes(self, n: int = 3) -> List[str]:
        sorted_heroes = sorted(self.preferred_heroes, key=lambda h: h["weight"], reverse=True)
        return [h["name"] for h in sorted_heroes[:n]]

    def get_hook_priority(self) -> List[Dict[str, Any]]:
        story = self.preferred_story
        hooks = []
        for key in ["hook", "merge", "collection", "reward"]:
            val = story.get(key)
            if isinstance(val, dict) and "weight" in val:
                hooks.append({"hook_type": val.get("primary", key), "weight": val["weight"]})
        return sorted(hooks, key=lambda h: -h["weight"])

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_heroes": len(self.preferred_heroes),
            "top_hero": self.preferred_heroes[0]["name"] if self.preferred_heroes else None,
            "primary_hook": self.preferred_story.get("hook", {}).get("primary"),
            "winner_only_patterns": len(self.winner_vs_loser.get("winner_only", [])),
            "loser_only_patterns": len(self.winner_vs_loser.get("loser_only", [])),
        }


class DNARules:
    def __init__(self):
        self.dna = WinnerDNA.from_real_data()

    def get_rules(self) -> List[Dict[str, Any]]:
        rules = []
        for hero in self.dna.preferred_heroes:
            rules.append({
                "id": f"hero_{hero['id']}",
                "category": "hero",
                "value": hero["name"],
                "weight": hero["weight"],
                "priority": "high" if hero["weight"] > 0.7 else "medium",
            })
        story = self.dna.preferred_story
        hook_data = story.get("hook", {})
        if hook_data:
            rules.append({
                "id": "hook_primary",
                "category": "hook",
                "value": hook_data.get("primary"),
                "weight": hook_data.get("weight"),
                "priority": "high",
            })
        color = self.dna.preferred_color
        rules.append({
            "id": "color_palette",
            "category": "color",
            "value": color.get("palette"),
            "constraints": {"saturation_min": color.get("saturation_min"), "contrast_min": color.get("contrast_min")},
            "priority": "high",
        })
        layout = self.dna.preferred_layout
        rules.append({
            "id": "layout_framing",
            "category": "layout",
            "value": layout.get("framing"),
            "aspect_ratio": layout.get("aspect_ratio"),
            "priority": "high",
        })
        ui = self.dna.preferred_ui
        rules.append({
            "id": "text_density",
            "category": "ui",
            "value": f"text_density <= {ui.get('text_density_max')}",
            "priority": "high",
        })
        rules.append({
            "id": "no_text_first_3s",
            "category": "ui",
            "value": "No text/UI overlay in first 3 seconds",
            "priority": "high",
        })
        return rules

    def validate_against_dna(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        results = {"matched": True, "score": 1.0, "violations": []}

        hero_input = spec.get("hero", "").lower()
        hero_match = max((h["weight"] for h in self.dna.preferred_heroes if h["id"] in hero_input), default=0)
        if hero_match < 0.3 and hero_input:
            results["violations"].append(f"Hero '{spec['hero']}' has low DNA match ({hero_match:.2f})")
            results["matched"] = False

        hook_input = spec.get("hook_type", "").lower()
        story = self.dna.preferred_story
        hook_primary = story.get("hook", {}).get("primary", "")
        if hook_input and hook_input != hook_primary:
            results["violations"].append(
                f"Hook '{hook_input}' is not primary. Recommended: '{hook_primary}' ({story['hook']['weight']*100:.0f}% of winners)"
            )
            results["score"] *= 0.7

        results["score"] = max(0, min(1, results["score"]))
        if results["violations"]:
            results["matched"] = False
        return results

    def get_stats(self) -> Dict[str, Any]:
        return self.dna.get_stats()
