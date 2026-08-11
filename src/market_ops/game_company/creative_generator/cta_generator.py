from typing import Dict, List, Any, Optional


CTA_TEMPLATES = {
    "collection": [
        "Collect 200+ Magical Creatures!",
        "Every creature has a unique power!",
        "Your collection awaits...",
        "Complete the collection today!",
        "How many can you collect?",
    ],
    "reward": [
        "Your epic reward awaits!",
        "The legend begins NOW!",
        "What will you unlock next?",
        "Power up your collection!",
        "Mythic rewards inside!",
    ],
    "challenge": [
        "Can you reach Level 100?",
        "Only the strongest survive...",
        "Challenge accepted?",
        "Prove your magic power!",
        "Rise to the top!",
    ],
    "free": [
        "Download Free!",
        "Start your adventure FREE!",
        "No payment needed!",
        "Join 1M+ players FREE!",
        "Free magical journey!",
    ],
    "curiosity": [
        "What's waiting for YOU inside?",
        "Only 1% can find this...",
        "The secret is hidden here!",
        "Dare to discover?",
        "The mystery unfolds...",
    ],
}


class CTAGenerator:
    def __init__(self):
        self._templates = CTA_TEMPLATES

    def generate(self, asset_hook_type: str = "collection", asset_title: str = "", style: str = "golden banner",
                 urgency: str = "medium") -> Dict[str, str]:
        hook = asset_hook_type if asset_hook_type in self._templates else "collection"
        variants = self._templates.get(hook, self._templates["collection"])

        text = max(variants, key=len)
        short = min(variants, key=len)

        return {
            "primary_text": text,
            "short_text": short,
            "all_variants": variants,
            "style": style,
            "urgency": urgency,
            "recommended_animation": "pulse" if urgency == "high" else "gentle fade",
        }

    def get_variants(self, asset_hook_type: str = "collection") -> List[str]:
        return list(self._templates.get(asset_hook_type, self._templates["collection"]))

    def get_stats(self) -> Dict[str, Any]:
        total = sum(len(v) for v in self._templates.values())
        return {"total_templates": total, "total_categories": len(self._templates)}
