from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


HEROES = [
    {"id": "white_witch", "name": "White Witch", "pet": "Baby Dragon", "style": "whimsical", "palette": "golden purple"},
    {"id": "dark_witch", "name": "Dark Witch", "pet": "Phoenix", "style": "mysterious", "palette": "deep purple magenta"},
    {"id": "little_witch", "name": "Little Witch", "pet": "Magic Wolf", "style": "cute", "palette": "pastel rainbow"},
    {"id": "red_witch", "name": "Red Witch", "pet": "Fire Fox", "style": "passionate", "palette": "red gold"},
    {"id": "ice_witch", "name": "Ice Witch", "pet": "Frost Dragon", "style": "elegant", "palette": "ice blue silver"},
    {"id": "forest_witch", "name": "Forest Witch", "pet": "Owl", "style": "nature", "palette": "green brown"},
]

ENVIRONMENTS = [
    {"id": "magic_forest", "name": "Magic Forest", "lighting": "sunbeams through trees", "mood": "enchanting"},
    {"id": "floating_castle", "name": "Floating Castle", "lighting": "magical glow", "mood": "mysterious"},
    {"id": "moon_forest", "name": "Moon Forest", "lighting": "moonlight", "mood": "dreamy"},
    {"id": "dark_tower", "name": "Dark Tower", "lighting": "candle light", "mood": "dramatic"},
    {"id": "enchanted_garden", "name": "Enchanted Garden", "lighting": "golden hour", "mood": "warm"},
    {"id": "crystal_cave", "name": "Crystal Cave", "lighting": "crystal reflections", "mood": "magical"},
    {"id": "volcano_lair", "name": "Volcano Lair", "lighting": "lava glow", "mood": "epic"},
    {"id": "sky_temple", "name": "Sky Temple", "lighting": "cloud light", "mood": "serene"},
]

MERGE_OBJECTS = [
    {"id": "dragon_egg", "name": "Dragon Egg", "chain": "egg→baby→adult→legendary"},
    {"id": "magic_plant", "name": "Magic Plant", "chain": "seed→sprout→bloom→ancient"},
    {"id": "treasure_chest", "name": "Treasure Chest", "chain": "bronze→silver→gold→mythic"},
    {"id": "crystal_gem", "name": "Crystal Gem", "chain": "shard→crystal→star→cosmic"},
    {"id": "magic_book", "name": "Magic Book", "chain": "page→chapter→tome→ancient"},
    {"id": "castle_piece", "name": "Castle Piece", "chain": "ruin→tower→castle→citadel"},
    {"id": "potion", "name": "Potion", "chain": "weak→strong→elite→legendary"},
    {"id": "star_dust", "name": "Star Dust", "chain": "dust→star→galaxy→universe"},
]

REWARDS = [
    {"id": "legendary_evolution", "name": "Legendary Evolution", "effect": "character transforms, bright flash, particles"},
    {"id": "rare_treasure", "name": "Rare Treasure", "effect": "chest opens, gold explosion, rainbow light"},
    {"id": "epic_merge", "name": "Epic Merge", "effect": "merge flash, power wave, level up"},
    {"id": "collection_complete", "name": "Collection Complete", "effect": "all creatures appear, collection fills, celebration"},
    {"id": "dragon_hatch", "name": "Dragon Hatch", "effect": "egg cracks, baby emerges, magical aura"},
    {"id": "castle_complete", "name": "Castle Complete", "effect": "castle assembles, light beams, flag raises"},
    {"id": "max_level", "name": "Max Level", "effect": "character evolves to max, golden aura, sparkles"},
]

CAMERAS = [
    {"id": "center_hero", "name": "Center Hero", "angle": "eye level", "movement": "slow zoom in"},
    {"id": "dynamic_wide", "name": "Dynamic Wide", "angle": "slight high angle", "movement": "swipe across scene"},
    {"id": "close_up", "name": "Close Up", "angle": "close up on character", "movement": "gentle push in"},
    {"id": "over_shoulder", "name": "Over Shoulder", "angle": "over shoulder view", "movement": "follow action"},
    {"id": "birds_eye", "name": "Bird's Eye", "angle": "top down", "movement": "zoom out reveal"},
    {"id": "dutch", "name": "Dutch Angle", "angle": "slight tilt", "movement": "dynamic rotation"},
]

CTAS = [
    {"id": "collection_cta", "text": "Collect 200+ Magical Creatures!", "style": "golden banner", "urgency": "medium"},
    {"id": "merge_cta", "text": "Merge Your Dragons Now!", "style": "parchment", "urgency": "medium"},
    {"id": "challenge_cta", "text": "Can You Reach Level 100?", "style": "mystery box", "urgency": "high"},
    {"id": "free_cta", "text": "Download Free - Start Your Journey!", "style": "gradient button", "urgency": "high"},
    {"id": "discover_cta", "text": "Discover Your Magic Powers!", "style": "crystal", "urgency": "medium"},
    {"id": "build_cta", "text": "Build Your Dark Empire!", "style": "gothic banner", "urgency": "low"},
    {"id": "hatch_cta", "text": "Hatch Your Baby Dragon FREE!", "style": "egg shape", "urgency": "high"},
]

HOOK_SCRIPTS = {
    "collection": {
        "hook_line": "Watch as your collection grows from nothing to LEGENDARY!",
        "beat1": "Show empty collection → first creature appears → more join → collection fills",
        "beat2": "Each merge adds a new creature with unique powers",
        "beat3": "Final reveal: all 200+ creatures in one glorious display",
    },
    "reward": {
        "hook_line": "The moment of truth... will it be LEGENDARY or just COMMON?",
        "beat1": "Build tension: merge animations building up",
        "beat2": "Critical merge: screen flashes, suspense builds",
        "beat3": "Reward explosion: legendary creature emerges with epic effects",
    },
    "curiosity": {
        "hook_line": "What's inside the MYSTERY CHEST? Only the bravest will find out...",
        "beat1": "Mystery element appears (question marks, shadows, locked chest)",
        "beat2": "Player interacts: tapping, merging, unlocking",
        "beat3": "Reveal: unexpected reward that exceeds expectations",
    },
    "comparison": {
        "hook_line": "Day 1 vs Day 30: The TRANSFORMATION will shock you!",
        "beat1": "Before state: small, weak, empty (player can relate)",
        "beat2": "Transition: rapid time-lapse of merges and upgrades",
        "beat3": "After state: magnificent, powerful, complete - the dream result",
    },
    "crisis": {
        "hook_line": "The DARKNESS is coming... Only YOU can save the Magic World!",
        "beat1": "Crisis established: dark clouds, broken castle, creatures in danger",
        "beat2": "Hero rises: witch prepares to fight, merges for power",
        "beat3": "Victory: crisis resolved, world saved, rewards earned",
    },
}

MUSIC_STYLES = [
    {"mood": "whimsical", "genre": "orchestral fantasy", "bpm": 100, "instruments": "strings, harp, flute"},
    {"mood": "epic", "genre": "epic orchestral", "bpm": 130, "instruments": "full orchestra, choir"},
    {"mood": "mysterious", "genre": "dark ambient", "bpm": 80, "instruments": "synth, bass, bells"},
    {"mood": "happy", "genre": "upbeat pop", "bpm": 120, "instruments": "piano, guitar, drums"},
    {"mood": "magical", "genre": "cinematic fantasy", "bpm": 110, "instruments": "celesta, strings, choir"},
]

SUBSCENE_TEMPLATES = {
    0: {"time": "0-0.8s", "category": "hook", "action": "Hero appears center frame with dramatic reveal", "duration": 0.8},
    1: {"time": "0.8-3s", "category": "introduction", "action": "Pet/companion joins hero, chemistry shown", "duration": 2.2},
    2: {"time": "3-6s", "category": "gameplay", "action": "Merge mechanic demonstrated with arrows and UI", "duration": 3.0},
    3: {"time": "6-9s", "category": "reward", "action": "Epic reward moment with bright flash and particles", "duration": 3.0},
    4: {"time": "9-12s", "category": "variety", "action": "More gameplay variety: different merges and outcomes", "duration": 3.0},
    5: {"time": "12-15s", "category": "collection", "action": "Collection showcase: all creatures/items displayed", "duration": 3.0},
    6: {"time": "15-18s", "category": "social", "action": "Social proof: ratings, reviews, active players shown", "duration": 3.0},
    7: {"time": "18-20s", "category": "cta", "action": "CTA button with pulse animation, app store badges", "duration": 2.0},
}
