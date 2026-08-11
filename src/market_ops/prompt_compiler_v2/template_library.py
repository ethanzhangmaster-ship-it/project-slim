"""P04 Witch 默认模板库。

Identity Lock: 所有模板的 identity 固定为 witch_v1。
不允许 per-template 角色描述，不允许多角色体系。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Every preset shares this locked identity.
IDENTITY_LOCKED = "witch_v1"


@dataclass(frozen=True, slots=True)
class TemplatePreset:
    template: str
    hook: str
    reward: str
    mechanic: str
    identity: str
    scene: str
    camera: str
    composition: str
    lighting: str
    emotion: str
    cta: str
    style: str


def _witch_defaults() -> list[TemplatePreset]:
    return [
        TemplatePreset(
            template="secret_chest_reveal",
            hook="Secret Chest",
            reward="Epic Chest爆开，Diamond Rain + 10000 Coins",
            mechanic="Merge",
            identity=IDENTITY_LOCKED,
            scene="Magic Forest",
            camera="Close Up",
            composition="Top Bottom",
            lighting="Golden epic glow, high contrast, cinematic rim light",
            emotion="Surprise",
            cta="Install Now",
            style="Hyper Realistic Mobile Game Ad",
        ),
        TemplatePreset(
            template="impossible_merge_fail",
            hook="Impossible Merge",
            reward="Huge Explosion + Legendary Reward Chest",
            mechanic="Wrong merge choice → failure → hint to correct merge",
            identity=IDENTITY_LOCKED,
            scene="Magic Forest",
            camera="Close Up",
            composition="Top Bottom",
            lighting="High contrast, epic particles, dramatic shadows",
            emotion="Surprise",
            cta="Install Now",
            style="Hyper Realistic Mobile Game Ad",
        ),
        TemplatePreset(
            template="level_100_progress",
            hook="Level 100",
            reward="Level 100 unlock + Epic Chest + Diamond Glow",
            mechanic="Merge",
            identity=IDENTITY_LOCKED,
            scene="Magic Forest",
            camera="Close Up",
            composition="Top Bottom",
            lighting="Cool base + golden highlight, cinematic glow",
            emotion="Surprise",
            cta="Install Now",
            style="Hyper Realistic Mobile Game Ad",
        ),
        TemplatePreset(
            template="huge_treasure",
            hook="Huge Treasure",
            reward="Giant Treasure Pile + Diamond Rain + Coins",
            mechanic="Merge to open treasure room",
            identity=IDENTITY_LOCKED,
            scene="Magic Forest",
            camera="Close Up",
            composition="Top Bottom",
            lighting="Epic glow, soft volumetric light, high contrast",
            emotion="Surprise",
            cta="Install Now",
            style="Hyper Realistic Mobile Game Ad",
        ),
        TemplatePreset(
            template="lucky_reward_spin",
            hook="Lucky Reward",
            reward="Lucky wheel jackpot + Epic Chest",
            mechanic="Merge completes task → spin → jackpot",
            identity=IDENTITY_LOCKED,
            scene="Magic Forest",
            camera="Close Up",
            composition="Top Bottom",
            lighting="Bright reward glow, cinematic sparkle",
            emotion="Surprise",
            cta="Install Now",
            style="Hyper Realistic Mobile Game Ad",
        ),
        # ════════════════════════════════════════
        # Collection-hook templates (62% of historical winners)
        # ════════════════════════════════════════
        TemplatePreset(
            template="creature_collection_book",
            hook="Collect 200+",
            reward="Complete your creature collection + unlock Legendary Dragon",
            mechanic="Merge to discover new creatures → fill collection book",
            identity=IDENTITY_LOCKED,
            scene="Magical Sanctuary",
            camera="Close Up",
            composition="Top Bottom",
            lighting="Warm amber glow, cozy magical atmosphere with soft sparkles",
            emotion="Satisfaction",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="magical_garden_collection",
            hook="Grow Your Collection",
            reward="Rare golden flower blooms + magical creature appears",
            mechanic="Merge plants → unlock new species → fill garden",
            identity=IDENTITY_LOCKED,
            scene="Enchanted Garden",
            camera="Close Up",
            composition="Split Screen",
            lighting="Soft pastel glow, morning light, magical pollen sparkles",
            emotion="Delight",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="witch_evolution_collection",
            hook="From Apprentice to Sorceress",
            reward="Collect all 5 evolution stages → Ultimate Witch form unlocked",
            mechanic="Merge items → evolve character → fill collection",
            identity=IDENTITY_LOCKED,
            scene="Mystic Castle",
            camera="Wide Shot",
            composition="Before After Split",
            lighting="Cool purple base with warm gold progression glow, cosmic particles",
            emotion="Excitement",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="rare_collection_grid",
            hook="Rare Collection Found!",
            reward="Complete the merge grid → Bonus Legendary Chest + 5000 Coins",
            mechanic="Merge board with glowing rare items → fill all slots",
            identity=IDENTITY_LOCKED,
            scene="Magic Forest",
            camera="Close Up",
            composition="Top Bottom",
            lighting="Dark atmospheric background, glowing rare items as focal points, high contrast",
            emotion="Excitement",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="hidden_creature_discovery",
            hook="Hidden Creature Found!",
            reward="Rare golden egg hatches → Mythical Phoenix unlocked",
            mechanic="Merge mystery eggs → discover hidden creatures → collect all",
            identity=IDENTITY_LOCKED,
            scene="Enchanted Forest",
            camera="Close Up",
            composition="Center Hero",
            lighting="Dramatic reveal lighting, dark background, bright magical creature glow",
            emotion="Surprise",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="collection_progress_tracker",
            hook="Only 3 Left!",
            reward="Complete the collection → Grand Prize Crystal Dragon + 10000 Gems",
            mechanic="Track merge progress → fill collection slots → grand reward",
            identity=IDENTITY_LOCKED,
            scene="Treasure Vault",
            camera="Close Up",
            composition="Top Bottom",
            lighting="Dark vault with golden spotlight on missing collection slots, high contrast",
            emotion="Anticipation",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        # ════════════════════════════════════════
        # Curiosity-hook templates (16% of historical winners)
        # ════════════════════════════════════════
        TemplatePreset(
            template="mystery_egg_hatch",
            hook="What's Inside?",
            reward="Mysterious egg cracks open → Mythical creature revealed + Collection progress",
            mechanic="Merge mysterious eggs → discover what hatches → fill collection page",
            identity=IDENTITY_LOCKED,
            scene="Enchanted Cave",
            camera="Close Up",
            composition="Center Hero",
            lighting="Dark atmospheric cave, bright crack of light from hatching egg, high contrast",
            emotion="Curiosity",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="hidden_door_reveal",
            hook="Secret Door Unlocked!",
            reward="Hidden chamber revealed → Rare legendary item + 3000 Gems",
            mechanic="Merge clues → unlock secret door → discover hidden content",
            identity=IDENTITY_LOCKED,
            scene="Mystic Castle Interior",
            camera="Wide Shot",
            composition="Before After Split",
            lighting="Dim torch-lit corridor, bright magical glow from opening door, dramatic reveal",
            emotion="Curiosity",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="what_just_happened",
            hook="Wait... What?!",
            reward="Unexpected transformation → Surprise epic form + Boost",
            mechanic="Merge unexpected combo → surprising reaction → rare unlock",
            identity=IDENTITY_LOCKED,
            scene="Magic Laboratory",
            camera="Close Up",
            composition="Center Hero",
            lighting="Chaotic magical explosion of light, sparks and particle effects, surprised character framed by glow",
            emotion="Surprise",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
    ]


def _p02_mermaid_defaults() -> list[TemplatePreset]:
    """P02 Mermaid templates — ocean theme, collection + reward hooks."""
    return [
        TemplatePreset(
            template="mermaid_collection_book",
            hook="Collect All Mermaids!",
            reward="Complete your mermaid collection + unlock Royal Coral Palace",
            mechanic="Merge ocean items → discover new mermaids → fill collection",
            identity="mermaid_v1",
            scene="Underwater Coral Reef",
            camera="Close Up",
            composition="Split Screen",
            lighting="Vibrant turquoise glow with golden sunbeams through water, magical bubbles",
            emotion="Delight",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="ocean_treasure_spin",
            hook="Spin for Ocean Treasures!",
            reward="Lucky spin jackpot → Rare Golden Shell + 5000 Pearls",
            mechanic="Merge to collect spins → spin wheel → jackpot reward",
            identity="mermaid_v1",
            scene="Sunken Treasure Ship",
            camera="Close Up",
            composition="Center Hero",
            lighting="Golden treasure glow from chest, shimmering aqua water, sparkles",
            emotion="Excitement",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
        TemplatePreset(
            template="mermaid_evolution",
            hook="Baby Fish → Ocean Queen",
            reward="Evolve through 5 stages → Legendary Mermaid Queen + Crown",
            mechanic="Merge fish → evolve → unlock ultimate mermaid form",
            identity="mermaid_v1",
            scene="Coral Palace",
            camera="Wide Shot",
            composition="Before After Split",
            lighting="Vibrant coral pinks and turquoise, sparkling evolution particles",
            emotion="Excitement",
            cta="Install Now",
            style="Whimsical Mobile Game Ad",
        ),
    ]


def _p07_vampire_defaults() -> list[TemplatePreset]:
    """P07 Vampire templates — 4-panel comic twist hooks, dramatic romance."""
    return [
        TemplatePreset(
            template="vampire_love_twist",
            hook="She Didn't See This Coming...",
            reward="Unexpected romantic twist → Unlock secret love story chapter",
            mechanic="4-panel comic narrative → shocking twist → audience must see what happens next",
            identity="vampire_v1",
            scene="Victorian Ballroom",
            camera="Wide Shot",
            composition="4-Panel Comic Progress",
            lighting="Dramatic chandelier lighting, deep purple shadows, golden candle glow",
            emotion="Tension",
            cta="Install Now",
            style="Dramatic Comic Mobile Game Ad",
        ),
        TemplatePreset(
            template="vampire_betrayal_reveal",
            hook="The Betrayal That Changed Everything",
            reward="Vampire power awakened → Revenge arc unlocked + Ultimate Form",
            mechanic="4-panel comic → shocking betrayal → character transformation → cliffhanger",
            identity="vampire_v1",
            scene="Dark Castle Throne Room",
            camera="Close Up",
            composition="4-Panel Comic Progress",
            lighting="Dark shadowed corners, dramatic spotlight on character face, blood-red glow",
            emotion="Tension",
            cta="Install Now",
            style="Dramatic Comic Mobile Game Ad",
        ),
        TemplatePreset(
            template="vampire_secret_identity",
            hook="He's NOT Who You Think...",
            reward="Vampire identity revealed → Secret power unlocked + Story twist",
            mechanic="4-panel reveal → clue → discovery → shocking identity twist",
            identity="vampire_v1",
            scene="Moonlit Rooftop",
            camera="Close Up",
            composition="4-Panel Comic Progress",
            lighting="Moonlit silver glow, dark silhouette contrast, dramatic reveal lighting",
            emotion="Curiosity",
            cta="Install Now",
            style="Dramatic Comic Mobile Game Ad",
        ),
    ]


def presets_for_project(project: str) -> list[TemplatePreset]:
    key = (project or "").strip().lower()
    if "witch" in key or "p04" in key:
        return _witch_defaults()
    if "mermaid" in key or "p02" in key:
        return _p02_mermaid_defaults()
    if "vampire" in key or "p07" in key:
        return _p07_vampire_defaults()
    return _witch_defaults()


def pick_presets(project: str, count: int) -> list[TemplatePreset]:
    presets = presets_for_project(project)
    if count <= 0:
        return []
    
    # Categorize templates by hook type for weighted sampling
    collection_presets = [
        p for p in presets 
        if any(kw in p.hook.lower() for kw in ["collect", "collection", "rare", "grow", "hidden", "from", "only"])
    ]
    reward_presets = [
        p for p in presets 
        if any(kw in p.hook.lower() for kw in ["secret", "impossible", "level", "huge", "lucky"]) and p not in collection_presets
    ]
    curiosity_presets = [
        p for p in presets
        if any(kw in p.hook.lower() for kw in ["what", "wait", "secret door"]) and p not in collection_presets
    ]
    
    # Try to load recipe weights for hook priority
    weights = {"collection": 0.62, "curiosity": 0.16, "reward": 0.10, "other": 0.12}  # from historical (62/16/10/12)
    try:
        import json
        recipe_path = __import__("pathlib").Path(__file__).parent.parent.parent.parent / "output/creatives_cache/_recipe_P04.json"
        if recipe_path.exists():
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            for hp in recipe.get("HOOK_PRIORITY", []):
                h = hp["hook"]
                w = hp["weight"]
                if h == "collection":
                    weights["collection"] = w
                elif h == "reward":
                    weights["reward"] = max(w, 0.1)
    except Exception:
        pass
    
    import random
    random.seed(42)
    result: list[TemplatePreset] = []
    
    for _ in range(count):
        r = random.random()
        if r < weights["collection"] and collection_presets:
            result.append(random.choice(collection_presets))
        elif r < weights["collection"] + weights["curiosity"] and curiosity_presets:
            result.append(random.choice(curiosity_presets))
        elif r < weights["collection"] + weights["curiosity"] + weights["reward"] and reward_presets:
            result.append(random.choice(reward_presets))
        else:
            result.append(random.choice(presets))  # fallback: any template
    return result
