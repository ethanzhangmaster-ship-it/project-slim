"""Pattern Mining Engine — bridges Lovart DNA → Prompt Compiler.

Reads all per-image DNA JSONs from _dna/, aggregates into:
  - Dominant hooks, moods, color palettes
  - Character patterns (visual identity across creatives)
  - UI/composition recipes
  - Prompt generation rules (features → instructions)
Writes result to _pattern_recipe.json.
"""

import json, re
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any

ROOT = Path("/Users/sixin/Desktop/project_slim")
DNA_DIR = ROOT / "output/creatives_cache/_dna"


# ── Colour word → hex mapping for dominant detection ──
WARM_KEYWORDS = {"gold", "amber", "orange", "yellow", "warm", "peach", "coral", "rose", "pink", "magenta"}
COOL_KEYWORDS = {"blue", "purple", "violet", "cyan", "teal", "mint", "cool", "indigo"}
DARK_KEYWORDS = {"black", "dark", "midnight", "shadow", "gothic", "ebony"}
LIGHT_KEYWORDS = {"white", "light", "cream", "pastel", "soft", "bright", "glow"}


def load_all_dna() -> dict[str, list[dict]]:
    """Load all DNA files grouped by project."""
    dna: dict[str, list[dict]] = defaultdict(list)
    for f in sorted(DNA_DIR.glob("*.json")):
        proj = f.stem.split("_", 1)[0]  # "P04_xxx.json" → "P04"
        try:
            dna[proj].append(json.loads(f.read_text(encoding="utf-8")))
        except:
            pass
    return dict(dna)


def classify_palette_tone(palette_str: str) -> Counter:
    """Count warm/cool/dark/light keyword hits in a palette description."""
    c = Counter()
    text = palette_str.lower()
    for kw in WARM_KEYWORDS:
        if kw in text:
            c["warm"] += 1
    for kw in COOL_KEYWORDS:
        if kw in text:
            c["cool"] += 1
    for kw in DARK_KEYWORDS:
        if kw in text:
            c["dark"] += 1
    for kw in LIGHT_KEYWORDS:
        if kw in text:
            c["light"] += 1
    return c


def extract_patterns(dna_items: list[dict]) -> dict[str, Any]:
    """Aggregate DNA items into structured patterns."""
    hooks = Counter()
    moods = Counter()
    palette_tones = Counter()
    subjects_raw: list[str] = []
    compositions: list[str] = []
    ui_all = Counter()
    overlay_texts: list[str] = []
    cta_styles: list[str] = []
    standout_all = Counter()
    char_keywords = Counter()

    for d in dna_items:
        hooks[d.get("hook_type", "unknown")] += 1
        moods[d.get("mood", "unknown")] += 1
        palette_tones += classify_palette_tone(d.get("palette", ""))
        subjects_raw.append(d.get("subject", ""))
        compositions.append(d.get("composition", ""))
        for ui in d.get("ui_elements", []):
            ui_all[ui.strip().lower()] += 1
        text = d.get("overlay_text", "")
        if text:
            overlay_texts.append(text)
        cta = d.get("cta_style", "")
        if cta:
            cta_styles.append(cta)
        for sf in d.get("standout_features", []):
            standout_all[sf.strip().lower()] += 1
        # Character keyword extraction
        subject = d.get("subject", "").lower()
        for kw in ["witch", "cute witch", "red-haired", "young witch", "hooded", "gothic", 
                    "chibi", "cartoon", "stylized", "female", "wizard", "sorceress"]:
            if kw in subject:
                char_keywords[kw] += 1

    # Composition pattern
    comp_patterns = Counter()
    for c in compositions:
        if "split" in c.lower() and "panel" in c.lower():
            comp_patterns["4-panel_progress"] += 1
        elif "split" in c.lower() or "left" in c.lower() or "right" in c.lower():
            comp_patterns["split_screen"] += 1
        elif "close-up" in c.lower() or "close up" in c.lower():
            comp_patterns["close_up"] += 1
        elif "full body" in c.lower() or "full-body" in c.lower():
            comp_patterns["full_body"] += 1
        elif "center" in c.lower():
            comp_patterns["center_hero"] += 1
        else:
            comp_patterns["other"] += 1

    # Dominant tone
    dominant_tone = palette_tones.most_common(1)[0][0] if palette_tones else "neutral"

    # Extract common hook words from subjects
    hook_contexts: list[str] = []
    for s in subjects_raw:
        if any(kw in s.lower() for kw in ["merge", "board", "game board"]):
            hook_contexts.append("merge_gameplay")
        elif any(kw in s.lower() for kw in ["progression", "evolution", "transform", "before-after", "panel"]):
            hook_contexts.append("progress_story")
        elif any(kw in s.lower() for kw in ["close-up", "close up", "portrait"]):
            hook_contexts.append("character_closeup")
        elif any(kw in s.lower() for kw in ["collect", "collection", "book", "creatures"]):
            hook_contexts.append("collection")
        elif any(kw in s.lower() for kw in ["reward", "spin", "wheel", "chest", "treasure"]):
            hook_contexts.append("reward_reveal")
        else:
            hook_contexts.append("other")

    context_counter = Counter(hook_contexts)

    return {
        "total_analyzed": len(dna_items),
        "dominant_hook": hooks.most_common(5),
        "dominant_mood": moods.most_common(5),
        "palette_tones": dict(palette_tones.most_common()),
        "dominant_tone": dominant_tone,
        "char_keywords": char_keywords.most_common(8),
        "composition_patterns": comp_patterns.most_common(5),
        "ui_elements_top": ui_all.most_common(12),
        "standout_features_top": standout_all.most_common(10),
        "scene_contexts": context_counter.most_common(5),
        "sample_CTA_styles": list(set(cta_styles))[:8],
        "sample_overlay_texts": [t for t in set(overlay_texts) if t][:15],
        "subjects_sample": subjects_raw[:15] if subjects_raw else [],
    }


def generate_prompt_recipe(patterns: dict) -> dict:
    """Convert patterns into structured prompt-generation rules."""
    hooks = patterns.get("dominant_hook", [])
    tones = patterns.get("palette_tones", {})
    comps = patterns.get("composition_patterns", {})
    moods_list = [m[0] for m in patterns.get("dominant_mood", [])[:3]]
    char_list = [c[0] for c in patterns.get("char_keywords", [])[:4]]
    ui = patterns.get("ui_elements_top", [])
    contexts = patterns.get("scene_contexts", [])

    # Primary hook (top 3)
    primary_hooks = [h[0] for h in hooks[:3]]

    # Tone directive
    warm = tones.get("warm", 0)
    cool = tones.get("cool", 0)
    dark = tones.get("dark", 0)
    light = tones.get("light", 0)

    if warm > cool:
        tone_directive = "warm, inviting palette with golden/amber accents"
    elif cool > warm:
        tone_directive = "cool, magical palette with deep purples and blues"
    else:
        tone_directive = "balanced warm-cool magical palette"

    if light > dark:
        light_directive = "bright and airy with soft pastels"
    else:
        light_directive = "dark atmospheric background with glowing focal elements"

    # Character directive
    character_directive = ", ".join(char_list) if char_list else "cute stylized witch"

    # Composition directive
    comp_list = [c[0] for c in comps] if isinstance(comps, list) else list(comps)
    top_comp = comp_list[0] if comp_list else "close_up"
    comp_directive = top_comp.replace("_", " ")

    # Mood directive
    mood_directive = ", ".join(moods_list[:3]) if moods_list else "whimsical, enchanting"

    # UI elements
    ui_directive = ", ".join([u[0] for u in ui[:5]]) if ui else "CTA button, game logo"

    recipe = {
        "CREATIVE_IDENTITY": {
            "character": character_directive,
            "mood": mood_directive,
        },
        "VISUAL_STYLE": {
            "tone": tone_directive,
            "lighting": light_directive,
            "composition_primary": comp_directive,
        },
        "HOOK_PRIORITY": [
            {"hook": h, "weight": round(patterns["dominant_hook"][i][1] / patterns["total_analyzed"], 3)}
            for i, h in enumerate(primary_hooks)
        ],
        "UI_REQUIREMENTS": ui_directive,
        "PROMPT_COMPILER_RULES": {
            "tone_guidance": "Use warm amber/gold palette with soft purple accents. Avoid hyper-realistic dark fantasy direction.",
            "character_guidance": "Character should be cute/whimsical witch, not menacing or hyper-realistic. Consistency across all creatives.",
            "hook_guidance": f"Primary hooks (in order): {', '.join(primary_hooks)}. Default to collection hook for new creatives.",
            "composition_guidance": f"Preferred composition: {comp_directive}. Common variant: 4-panel progress story.",
            "forbidden_directions": [
                "Hyper-realistic dark sorceress",
                "Cold/icy palette dominant",
                "Abstract or excessively minimal UI",
                "Character redesign between creatives"
            ],
        },
    }
    return recipe


# ── Main ──
print("Pattern Mining Engine — v1\n" + "="*50)

all_dna = load_all_dna()
print(f"Projects loaded: {list(all_dna.keys())}")
for p, items in all_dna.items():
    print(f"  {p}: {len(items)} DNA records")

for project, dna_items in all_dna.items():
    if not dna_items:
        continue
    print(f"\n{'='*50}")
    print(f"[{project}] Pattern Mining ({len(dna_items)} records)")

    patterns = extract_patterns(dna_items)
    recipe = generate_prompt_recipe(patterns)
    
    # Inject winner/loser diff if available
    wl_path = ROOT / "output/winner_vs_loser_diff.json"
    if wl_path.exists():
        try:
            wl_data = json.loads(wl_path.read_text(encoding="utf-8"))
            diffs = wl_data.get("key_differences", [])
            winner_only = []
            loser_only = []
            for d in diffs:
                for w in d.get("winner_only", []):
                    winner_only.append(f"[{d['dimension']}] {w}")
                for l in d.get("loser_only", []):
                    loser_only.append(f"[{d['dimension']}] {l}")
            recipe["WINNER_VS_LOSER"] = {
                "source": wl_data.get("source", "unknown"),
                "sample_size": wl_data.get("sample_size", 0),
                "winner_only_patterns": winner_only,
                "loser_only_patterns": loser_only,
            }
        except:
            pass

    # Save patterns
    pattern_path = ROOT / "output/creatives_cache" / f"_patterns_{project}.json"
    pattern_path.write_text(json.dumps(patterns, ensure_ascii=False, indent=2))
    print(f"  Patterns → {pattern_path}")

    # Save recipe
    recipe_path = ROOT / "output/creatives_cache" / f"_recipe_{project}.json"
    recipe_path.write_text(json.dumps(recipe, ensure_ascii=False, indent=2))
    print(f"  Recipe → {recipe_path}")

    # Print summary
    print(f"\n  🎯 Hook: {patterns['dominant_hook'][:3]}")
    print(f"  🎨 Tone: {patterns['dominant_tone']} ({patterns['palette_tones']})")
    print(f"  🧙 Character: {patterns['char_keywords'][:4]}")
    comp_summary = list(patterns['composition_patterns'].items())[:3] if hasattr(patterns['composition_patterns'], 'items') else patterns['composition_patterns'][:3]
    print(f"  📐 Composition: {comp_summary}")
    print(f"  😊 Mood: {patterns['dominant_mood'][:3]}")

# ── Cross-project summary ──
summary = {
    "generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ"),
    "projects": {
        p: {
            "total_analyzed": len(items),
            "top_hook": [h[0] for h in (items and extract_patterns(items)["dominant_hook"][:2] or [])],
            "dominant_tone": (items and extract_patterns(items)["dominant_tone"] or "?") if items else "?",
            "character": [c[0] for c in (items and extract_patterns(items)["char_keywords"][:3] or [])] if items else [],
        }
        for p, items in all_dna.items()
    }
}
summary_path = ROOT / "output/creatives_cache" / "_pattern_summary.json"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print(f"\n{'='*50}")
print(f"Cross-project summary → {summary_path}")
print(json.dumps(summary, ensure_ascii=False, indent=2))
