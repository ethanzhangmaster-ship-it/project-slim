"""Extract Visual DNA from real FB winner images — Local Analysis + Rule Engine.

Uses PIL for local image analysis (color palette, composition) +
FB metadata (creative name, performance data) to build structured DNA.
"""
import json
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageStat
import numpy as np

ROOT = Path(r"d:\project_slim\project_slim")

# Load real winners DNA
dna_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "real_winners_dna.json"
with open(dna_path, "r", encoding="utf-8") as f:
    winners = json.load(f)

print(f"Loaded {len(winners)} winners")

# Filter valid images
valid = []
for w in winners:
    img_path = w.get("local_image_path", "")
    if img_path and Path(img_path).exists():
        valid.append(w)

print(f"Valid with local images: {len(valid)}")


def analyze_color_palette(img: Image.Image) -> str:
    """Extract dominant color palette description."""
    # Resize for faster processing
    small = img.resize((100, 100))
    pixels = list(small.getdata())
    color_counts = Counter(pixels)
    
    # Get top 5 colors
    top_colors = color_counts.most_common(5)
    
    # Classify colors
    color_names = []
    for rgb, count in top_colors:
        r, g, b = rgb
        # Simple color classification
        if r > 200 and g > 200 and b > 200:
            color_names.append("white/light")
        elif r < 50 and g < 50 and b < 50:
            color_names.append("black/dark")
        elif r > 150 and g < 80 and b < 80:
            color_names.append("red")
        elif r > 150 and g > 100 and b < 60:
            color_names.append("gold/orange")
        elif r < 60 and g > 150 and b < 80:
            color_names.append("green")
        elif r < 60 and g < 100 and b > 150:
            color_names.append("blue")
        elif r > 100 and g < 100 and b > 150:
            color_names.append("purple/violet")
        elif r > 150 and g > 100 and b > 150:
            color_names.append("pink/magenta")
        elif 100 < r < 180 and 80 < g < 160 and 40 < b < 120:
            color_names.append("warm/brown")
        elif r < 80 and g > 100 and b > 120:
            color_names.append("teal/cyan")
        else:
            color_names.append(f"RGB({r},{g},{b})")
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for name in color_names:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    
    return ", ".join(unique[:4])


def analyze_composition(img: Image.Image) -> dict:
    """Analyze image composition by region."""
    w, h = img.size
    
    # Analyze 9 regions (3x3 grid)
    regions = {}
    for row in range(3):
        for col in range(3):
            left = col * w // 3
            top = row * h // 3
            right = (col + 1) * w // 3
            bottom = (row + 1) * h // 3
            region = img.crop((left, top, right, bottom))
            stat = ImageStat.Stat(region)
            brightness = sum(stat.mean) / 3
            regions[f"r{row}c{col}"] = round(brightness, 1)
    
    # Find brightest and darkest regions
    brightest = max(regions, key=regions.get)
    darkest = min(regions, key=regions.get)
    
    # Determine dominant layout
    top_brightness = (regions["r0c0"] + regions["r0c1"] + regions["r0c2"]) / 3
    mid_brightness = (regions["r1c0"] + regions["r1c1"] + regions["r1c2"]) / 3
    bot_brightness = (regions["r2c0"] + regions["r2c1"] + regions["r2c2"]) / 3
    
    if top_brightness > mid_brightness and top_brightness > bot_brightness:
        vertical = "top-weighted"
    elif bot_brightness > mid_brightness and bot_brightness > top_brightness:
        vertical = "bottom-weighted"
    else:
        vertical = "center-weighted"
    
    return {
        "aspect_ratio": f"{w}:{h}",
        "vertical_weight": vertical,
        "brightest_region": brightest,
        "darkest_region": darkest,
    }


def infer_hook_type(creative_name: str, platform: str) -> str:
    """Infer hook type from creative name."""
    name_lower = creative_name.lower()
    
    if any(kw in name_lower for kw in ["merge", "combine", "match"]):
        return "merge_upgrade"
    if any(kw in name_lower for kw in ["hatch", "egg", "dragon", "hatching"]):
        return "hatching_egg"
    if any(kw in name_lower for kw in ["before", "after", "vs", "day 1", "day 30", "transform"]):
        return "before_after"
    if any(kw in name_lower for kw in ["collect", "collection", "200+", "all"]):
        return "collection"
    if any(kw in name_lower for kw in ["asmr", "cleaning", "clean", "fix"]):
        return "asmr_cleaning"
    if any(kw in name_lower for kw in ["reward", "claim", "treasure", "loot", "gift", "gem"]):
        return "reward_reveal"
    if any(kw in name_lower for kw in ["story", "mystery", "secret", "discover"]):
        return "story_hook"
    if any(kw in name_lower for kw in ["magic", "adventure", "magical", "witch"]):
        return "character_showcase"
    if any(kw in name_lower for kw in ["build", "castle", "empire", "garden"]):
        return "build_upgrade"
    if any(kw in name_lower for kw in ["evolve", "evolution", "level up", "upgrade"]):
        return "evolution"
    
    return "general_showcase"


def infer_style(creative_name: str, palette: str) -> str:
    """Infer visual style from name and palette."""
    name_lower = creative_name.lower()
    
    if "dark" in palette.lower() or "purple" in palette.lower() or "black" in palette.lower():
        if "castle" in name_lower or "empire" in name_lower or "dark" in name_lower:
            return "dark_fantasy"
        return "magical_twilight"
    if "gold" in palette.lower() or "warm" in palette.lower():
        return "warm_magical"
    if "green" in palette.lower() or "blue" in palette.lower():
        return "nature_magic"
    if "pink" in palette.lower() or "magenta" in palette.lower():
        return "dreamy_fantasy"
    
    return "casual_fantasy"


def extract_dna(w: dict) -> dict:
    """Extract visual DNA from a single winner image + metadata."""
    img_path = Path(w["local_image_path"])
    creative_name = w.get("creative_name", "")
    platform = w.get("platform", "unknown")
    
    try:
        img = Image.open(img_path)
        
        # Local analysis
        palette = analyze_color_palette(img)
        composition = analyze_composition(img)
        stat = ImageStat.Stat(img)
        mean_brightness = sum(stat.mean) / 3
        contrast = sum(stat.stddev) / 3
        
        # Rule-based inference
        hook_type = infer_hook_type(creative_name, platform)
        style = infer_style(creative_name, palette)
        
        # Build gameplay elements from name
        name_lower = creative_name.lower()
        gameplay_elements = []
        if any(kw in name_lower for kw in ["merge", "board", "combine"]):
            gameplay_elements.append("merge_board")
        if any(kw in name_lower for kw in ["dragon", "egg", "hatch"]):
            gameplay_elements.append("dragon_eggs")
        if any(kw in name_lower for kw in ["castle", "build", "empire"]):
            gameplay_elements.append("castle_building")
        if any(kw in name_lower for kw in ["garden", "flower", "plant"]):
            gameplay_elements.append("magical_garden")
        if any(kw in name_lower for kw in ["witch", "wizard", "magic"]):
            gameplay_elements.append("witch_character")
        if any(kw in name_lower for kw in ["collect", "collection"]):
            gameplay_elements.append("collection_system")
        if any(kw in name_lower for kw in ["treasure", "gem", "reward", "loot"]):
            gameplay_elements.append("reward_system")
        if any(kw in name_lower for kw in ["evolve", "evolution", "upgrade"]):
            gameplay_elements.append("evolution_chain")
        if not gameplay_elements:
            gameplay_elements.append("merge_gameplay")
        
        # Build standout features
        standout = []
        if hook_type == "hatching_egg":
            standout.append("dramatic_egg_hatching_reveal")
        if hook_type == "before_after":
            standout.append("transformation_comparison")
        if hook_type == "collection":
            standout.append("collection_completion_urge")
        if "magical" in name_lower:
            standout.append("magical_visual_effects")
        if contrast > 50:
            standout.append("high_contrast_pop")
        standout.append(f"proven_performance_roas_{w.get('roas', 0):.1f}")
        
        return {
            "subject": creative_name[:80] if creative_name else "Evolution Merge creative",
            "composition": f"{composition['vertical_weight']} layout, {composition['aspect_ratio']} aspect ratio",
            "palette": palette,
            "lighting": "bright" if mean_brightness > 128 else "dark" if mean_brightness < 64 else "medium",
            "ui_elements": gameplay_elements,
            "overlay_text": creative_name[:100] if creative_name else "",
            "cta_style": "bottom_banner" if composition["vertical_weight"] == "bottom-weighted" else "overlay",
            "character_pose": "game_character" if "witch" in name_lower or "dragon" in name_lower else "gameplay_focus",
            "mood": style.replace("_", " "),
            "hook_type": hook_type,
            "gameplay_elements": gameplay_elements,
            "standout_features": standout,
            "overall_summary": f"Real FB winner creative (spend=${w.get('spend', 0):.0f}, ROAS={w.get('roas', 0):.2f}) using {hook_type} hook with {style} style",
            # Metadata
            "image_stats": {
                "size": f"{img.size[0]}x{img.size[1]}",
                "mean_brightness": round(mean_brightness, 1),
                "contrast": round(contrast, 1),
                "unique_colors_approx": len(Counter(list(img.resize((50, 50)).getdata()))),
            },
            "source": "local_analysis_rule_engine",
            "status": "pending_ai_vision_verification",
        }
        
    except Exception as e:
        return {
            "subject": creative_name[:80] if creative_name else "unknown",
            "hook_type": infer_hook_type(creative_name, platform),
            "status": "error",
            "error": str(e),
            "source": "rule_engine_fallback",
        }


# ── Extract DNA for all valid winners ──

print(f"\n{'='*60}")
print(f"Extracting Visual DNA for {len(valid)} real winners...")
print(f"{'='*60}")

results = []
for i, w in enumerate(valid):
    cid = w["creative_id"]
    print(f"[{i+1}/{len(valid)}] {cid} — {w.get('creative_name', 'N/A')[:50]}")
    
    dna = extract_dna(w)
    print(f"  Hook: {dna.get('hook_type', '?')} | Palette: {dna.get('palette', '?')[:50]}")
    
    results.append({
        "creative_id": cid,
        "creative_name": w.get("creative_name", ""),
        "platform": w.get("platform", "unknown"),
        "spend": w.get("spend", 0),
        "revenue": w.get("revenue", 0),
        "roas": w.get("roas", 0),
        "installs": w.get("installs", 0),
        "local_image_path": w.get("local_image_path", ""),
        "eagle_filename": w.get("eagle_filename", ""),
        "visual_dna": dna,
        "extracted_at": datetime.now().isoformat(),
    })

# Save
output_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "real_winners_dna_vision.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({
        "version": "1.0.0",
        "source": "facebook_graph_api",
        "analysis_method": "local_analysis_rule_engine",
        "total": len(results),
        "winners": results,
    }, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"DNA Extraction Complete!")
print(f"  Records: {len(results)}")
print(f"  Saved to: {output_path}")
print(f"{'='*60}")

# Stats
hook_types = Counter(r["visual_dna"].get("hook_type", "unknown") for r in results)
print(f"\nHook Type Distribution:")
for ht, count in hook_types.most_common():
    print(f"  {ht}: {count}")

# Performance summary
total_spend = sum(r["spend"] for r in results)
total_revenue = sum(r["revenue"] for r in results)
print(f"\nPerformance Summary:")
print(f"  Total Spend: ${total_spend:,.0f}")
print(f"  Total Revenue: ${total_revenue:,.0f}")
print(f"  Overall ROAS: {total_revenue/total_spend:.2f}" if total_spend > 0 else "  Overall ROAS: N/A")
print(f"  Avg ROAS: {sum(r['roas'] for r in results)/len(results):.2f}")