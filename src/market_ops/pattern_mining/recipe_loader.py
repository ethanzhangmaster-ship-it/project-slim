"""Recipe Loader — loads pattern-mined recipes and converts to prompt compiler instructions.

Reads output/creatives_cache/_recipe_{project}.json → compiler-ready directives.
"""
import json
from pathlib import Path
from typing import Any

ROOT = Path("/Users/sixin/Desktop/project_slim")
RECIPE_DIR = ROOT / "output/creatives_cache"
DEFAULT_PROJECT = "P04"


def load_recipe(project: str | None = None) -> dict[str, Any]:
    """Load recipe JSON. Falls back to hard-coded defaults if recipe not found."""
    proj = project or DEFAULT_PROJECT
    recipe_path = RECIPE_DIR / f"_recipe_{proj}.json"
    if recipe_path.exists():
        return json.loads(recipe_path.read_text(encoding="utf-8"))
    return _default_recipe(proj)


def recipe_to_prompt_section(recipe: dict) -> str:
    """Convert recipe to a prompt section that guides generation."""
    rules = recipe.get("PROMPT_COMPILER_RULES", {})
    identity = recipe.get("CREATIVE_IDENTITY", {})

    lines = [
        "PATTERN-MINED CREATIVE RECIPE (from historical Facebook winners):",
        "",
        f"CHARACTER: {identity.get('character', 'cute stylized witch')}",
        f"MOOD: {identity.get('mood', 'whimsical, enchanting')}",
        f"TONE GUIDANCE: {rules.get('tone_guidance', '')}",
        f"CHARACTER GUIDANCE: {rules.get('character_guidance', '')}",
        f"HOOK GUIDANCE: {rules.get('hook_guidance', '')}",
        f"COMPOSITION: {rules.get('composition_guidance', '')}",
        "",
        "FORBIDDEN:",
    ]
    for fd in rules.get("forbidden_directions", []):
        lines.append(f"- {fd}")
    
    # Inject winner/loser diff if available
    wl = recipe.get("WINNER_VS_LOSER", {})
    if wl:
        lines.append("")
        lines.append("WINNER-SPECIFIC PATTERNS (from spend-stratified A/B diff):")
        for d in wl.get("winner_only_patterns", []):
            lines.append(f"- {d}")
        lines.append("")
        lines.append("AVOID (loser patterns):")
        for d in wl.get("loser_only_patterns", []):
            lines.append(f"- {d}")

    return "\n".join(lines)


def _default_recipe(project: str = "P04") -> dict:
    """Fallback recipe when a mined one isn't available."""
    if "P02" in project or "Mermaid" in project:
        return {
            "CREATIVE_IDENTITY": {"character": "colorful mermaid characters", "mood": "cheerful collecting magical"},
            "VISUAL_STYLE": {"tone": "vibrant ocean", "lighting": "shimmering water sparkles"},
            "HOOK_PRIORITY": [{"hook": "collection", "weight": 0.7}, {"hook": "reward", "weight": 0.3}],
            "PROMPT_COMPILER_RULES": {
                "tone_guidance": "Vibrant turquoise and coral ocean palette. Cheerful underwater atmosphere.",
                "character_guidance": "Colorful mermaid characters with distinct designs. Happy expressions.",
                "hook_guidance": "Primary hook: collection. Show merge board + collection book.",
                "composition_guidance": "Split screen showing merge board and character.",
                "forbidden_directions": ["Dark/horror tone", "Cold/icy palette", "Abstract without merge mechanic"],
            },
        }
    if "P07" in project or "Vampire" in project:
        return {
            "CREATIVE_IDENTITY": {"character": "dramatic vampire characters", "mood": "dramatic romantic tension"},
            "VISUAL_STYLE": {"tone": "dark purple romantic", "lighting": "dramatic spotlight shadow"},
            "HOOK_PRIORITY": [{"hook": "twist", "weight": 1.0}],
            "PROMPT_COMPILER_RULES": {
                "tone_guidance": "Deep purple and dark blue backgrounds with golden accent. Dramatic Victorian aesthetic.",
                "character_guidance": "Dramatic vampire characters in romantic conflict. 4-panel comic format.",
                "hook_guidance": "Primary hook: twist. Shocking reveals, betrayals, secret identities.",
                "composition_guidance": "4-panel comic progression. Dramatic before/after reveals.",
                "forbidden_directions": ["Cute/whimsical tone", "Bright daylight scenes", "Static single-image ads"],
            },
        }
    return {
        "CREATIVE_IDENTITY": {"character": "cute witch", "mood": "whimsical cozy magical"},
        "VISUAL_STYLE": {"tone": "warm", "lighting": "soft glowy"},
        "HOOK_PRIORITY": [{"hook": "collection", "weight": 0.6}, {"hook": "curiosity", "weight": 0.2}],
        "PROMPT_COMPILER_RULES": {
            "tone_guidance": "Use warm amber/gold palette with soft purple accents.",
            "character_guidance": "Character should be cute/whimsical witch. Consistency across all creatives.",
            "hook_guidance": "Primary hook: collection. Secondary: curiosity.",
            "composition_guidance": "Center hero composition preferred.",
            "forbidden_directions": ["Hyper-realistic dark sorceress", "Cold/icy palette dominant"],
        },
    }
