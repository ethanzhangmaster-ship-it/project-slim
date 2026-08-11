"""Contrastive DNA Extraction — Winner vs Loser Visual Analysis.

Extracts quantitative visual features from all 176 real FB creatives,
then runs contrastive analysis to find what differentiates winners from losers.
"""
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PIL import Image, ImageStat
import numpy as np

ROOT = Path(r"d:\project_slim\project_slim")

# Load all creatives
dna_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "all_creatives_dna.json"
with open(dna_path, "r", encoding="utf-8") as f:
    data = json.load(f)

creatives = data["creatives"]
print(f"Loaded {len(creatives)} creatives")

# Filter to those with valid local images
valid = [c for c in creatives if c.get("local_image_path") and Path(c["local_image_path"]).exists()]
print(f"Valid with local images: {len(valid)}")

# Tier distribution
tiers = Counter(c["tier"] for c in valid)
print(f"Tier distribution: {dict(tiers)}")


# ── Feature Extraction ──

def extract_color_features(img: Image.Image) -> dict:
    """Extract color-related features."""
    # Resize for faster processing
    small = img.resize((120, 120))
    arr = np.array(small)
    
    # Mean and std per channel
    r_mean, g_mean, b_mean = arr[:,:,0].mean(), arr[:,:,1].mean(), arr[:,:,2].mean()
    r_std, g_std, b_std = arr[:,:,0].std(), arr[:,:,1].std(), arr[:,:,2].std()
    
    brightness = (r_mean + g_mean + b_mean) / 3
    saturation = (max(r_mean, g_mean, b_mean) - min(r_mean, g_mean, b_mean)) / max(r_mean, g_mean, b_mean, 1)
    
    # Dominant hue
    if r_mean > g_mean and r_mean > b_mean:
        if g_mean > b_mean * 1.1:
            dominant_hue = "warm_golden"
        else:
            dominant_hue = "warm_red"
    elif g_mean > r_mean and g_mean > b_mean:
        dominant_hue = "green"
    elif b_mean > r_mean and b_mean > g_mean:
        if r_mean > g_mean * 1.2:
            dominant_hue = "purple"
        else:
            dominant_hue = "blue_cool"
    elif r_mean < 50 and g_mean < 50 and b_mean < 50:
        dominant_hue = "dark"
    elif r_mean > 200 and g_mean > 200 and b_mean > 200:
        dominant_hue = "bright_white"
    else:
        dominant_hue = "neutral"
    
    # Color richness (how many distinct colors)
    pixels = list(small.getdata())
    unique_colors = len(set(pixels))
    
    return {
        "r_mean": round(r_mean, 1),
        "g_mean": round(g_mean, 1),
        "b_mean": round(b_mean, 1),
        "brightness": round(brightness, 1),
        "saturation": round(saturation, 3),
        "contrast": round((r_std + g_std + b_std) / 3, 1),
        "dominant_hue": dominant_hue,
        "color_richness": unique_colors,
    }


def extract_composition_features(img: Image.Image) -> dict:
    """Extract composition-related features."""
    w, h = img.size
    arr = np.array(img)
    
    # 3x3 grid brightness analysis
    regions = {}
    for row in range(3):
        for col in range(3):
            left = col * w // 3
            top = row * h // 3
            right = (col + 1) * w // 3
            bottom = (row + 1) * h // 3
            region = arr[top:bottom, left:right]
            bright = region.mean()
            regions[f"r{row}c{col}"] = round(bright, 1)
    
    # Top vs bottom brightness
    top_bright = (regions["r0c0"] + regions["r0c1"] + regions["r0c2"]) / 3
    mid_bright = (regions["r1c0"] + regions["r1c1"] + regions["r1c2"]) / 3
    bot_bright = (regions["r2c0"] + regions["r2c1"] + regions["r2c2"]) / 3
    
    if top_bright > mid_bright * 1.1 and top_bright > bot_bright * 1.1:
        vertical_weight = "top"
    elif bot_bright > mid_bright * 1.1 and bot_bright > top_bright * 1.1:
        vertical_weight = "bottom"
    elif mid_bright > top_bright and mid_bright > bot_bright:
        vertical_weight = "center"
    else:
        vertical_weight = "balanced"
    
    # Aspect ratio
    if w > h:
        aspect = "landscape"
    elif h > w:
        aspect = "portrait"
    else:
        aspect = "square"
    
    return {
        "aspect_ratio": f"{w}:{h}",
        "aspect_type": aspect,
        "width": w,
        "height": h,
        "vertical_weight": vertical_weight,
        "top_brightness": round(top_bright, 1),
        "mid_brightness": round(mid_bright, 1),
        "bot_brightness": round(bot_bright, 1),
        "brightness_gradient": round(bot_bright - top_bright, 1),
    }


def infer_hook_type(creative_name: str) -> str:
    """Infer hook type from creative name."""
    nl = creative_name.lower()
    if any(kw in nl for kw in ["merge", "combine", "match"]):
        return "merge_upgrade"
    if any(kw in nl for kw in ["hatch", "egg", "dragon", "hatching"]):
        return "hatching_egg"
    if any(kw in nl for kw in ["before", "after", "vs", "day 1", "transform"]):
        return "before_after"
    if any(kw in nl for kw in ["collect", "collection", "all"]):
        return "collection"
    if any(kw in nl for kw in ["asmr", "cleaning", "clean", "fix"]):
        return "asmr_cleaning"
    if any(kw in nl for kw in ["reward", "claim", "treasure", "loot", "gift", "gem"]):
        return "reward_reveal"
    if any(kw in nl for kw in ["story", "mystery", "secret", "discover"]):
        return "story_hook"
    if any(kw in nl for kw in ["magic", "adventure", "magical", "witch"]):
        return "character_showcase"
    if any(kw in nl for kw in ["build", "castle", "empire", "garden"]):
        return "build_upgrade"
    if any(kw in nl for kw in ["evolve", "evolution", "level up", "upgrade"]):
        return "evolution"
    if any(kw in nl for kw in ["try it", "try now", "play now"]):
        return "general_showcase"
    return "general_showcase"


# ── Extract all features ──

print(f"\n{'='*60}")
print("Extracting visual features for all 176 creatives...")
print("=" * 60)

features = []
errors = 0

for i, c in enumerate(valid):
    if (i + 1) % 50 == 0:
        print(f"  [{i+1}/{len(valid)}]")
    
    try:
        img = Image.open(c["local_image_path"])
        color = extract_color_features(img)
        comp = extract_composition_features(img)
        hook = infer_hook_type(c.get("creative_name", ""))
        
        features.append({
            "creative_id": c["creative_id"],
            "tier": c["tier"],
            "spend": c["spend"],
            "revenue": c["revenue"],
            "roas": c["roas"],
            "installs": c["installs"],
            "creative_name": c.get("creative_name", ""),
            "platform": c.get("platform", "unknown"),
            "hook_type": hook,
            "color": color,
            "composition": comp,
            "local_image_path": c["local_image_path"],
        })
    except Exception as e:
        errors += 1

print(f"Extracted: {len(features)} features, {errors} errors")


# ── Contrastive Analysis ──

print(f"\n{'='*60}")
print("CONTRASTIVE ANALYSIS: Winner vs Loser")
print("=" * 60)

# Group by tier
winners = [f for f in features if f["tier"] == "winner"]
neutrals = [f for f in features if f["tier"] == "neutral"]
losers = [f for f in features if f["tier"] == "loser"]

def avg(seq):
    return sum(seq) / len(seq) if seq else 0

def analyze_tier(tier_features, tier_name):
    """Analyze a tier's visual characteristics."""
    if not tier_features:
        return {}
    
    return {
        "count": len(tier_features),
        "avg_spend": avg([f["spend"] for f in tier_features]),
        "avg_revenue": avg([f["revenue"] for f in tier_features]),
        "avg_roas": avg([f["roas"] for f in tier_features]),
        # Color
        "avg_brightness": avg([f["color"]["brightness"] for f in tier_features]),
        "avg_contrast": avg([f["color"]["contrast"] for f in tier_features]),
        "avg_saturation": avg([f["color"]["saturation"] for f in tier_features]),
        "avg_color_richness": avg([f["color"]["color_richness"] for f in tier_features]),
        "dominant_hue_dist": dict(Counter(f["color"]["dominant_hue"] for f in tier_features)),
        # Composition
        "aspect_dist": dict(Counter(f["composition"]["aspect_type"] for f in tier_features)),
        "vertical_weight_dist": dict(Counter(f["composition"]["vertical_weight"] for f in tier_features)),
        "avg_brightness_gradient": avg([f["composition"]["brightness_gradient"] for f in tier_features]),
        # Hook
        "hook_type_dist": dict(Counter(f["hook_type"] for f in tier_features)),
        # Platform
        "platform_dist": dict(Counter(f["platform"] for f in tier_features)),
    }

w_analysis = analyze_tier(winners, "Winners")
n_analysis = analyze_tier(neutrals, "Neutrals")
l_analysis = analyze_tier(losers, "Losers")

# Print contrastive insights
print(f"\n{'─'*40}")
print("1. COLOR ANALYSIS")
print(f"{'─'*40}")
print(f"  {'Metric':<25} {'Winners':>10} {'Neutrals':>10} {'Losers':>10}")
print(f"  {'─'*55}")
for metric, label in [
    ("avg_brightness", "Brightness"),
    ("avg_contrast", "Contrast"),
    ("avg_saturation", "Saturation"),
    ("avg_color_richness", "Color Richness"),
]:
    print(f"  {label:<25} {w_analysis[metric]:>10.1f} {n_analysis[metric]:>10.1f} {l_analysis[metric]:>10.1f}")

print(f"\n  Dominant Hue:")
for hue in ["dark", "blue_cool", "purple", "warm_golden", "warm_red", "green", "neutral", "bright_white"]:
    wc = w_analysis["dominant_hue_dist"].get(hue, 0)
    nc = n_analysis["dominant_hue_dist"].get(hue, 0)
    lc = l_analysis["dominant_hue_dist"].get(hue, 0)
    if wc or nc or lc:
        print(f"    {hue:<15} W:{wc:>2} N:{nc:>2} L:{lc:>2}")

print(f"\n{'─'*40}")
print("2. COMPOSITION ANALYSIS")
print(f"{'─'*40}")
print(f"  {'Metric':<25} {'Winners':>10} {'Neutrals':>10} {'Losers':>10}")
print(f"  {'─'*55}")
for metric, label in [
    ("avg_brightness_gradient", "Brightness Gradient"),
]:
    print(f"  {label:<25} {w_analysis[metric]:>10.1f} {n_analysis[metric]:>10.1f} {l_analysis[metric]:>10.1f}")

print(f"\n  Vertical Weight:")
for vw in ["top", "center", "bottom", "balanced"]:
    wc = w_analysis["vertical_weight_dist"].get(vw, 0)
    nc = n_analysis["vertical_weight_dist"].get(vw, 0)
    lc = l_analysis["vertical_weight_dist"].get(vw, 0)
    if wc or nc or lc:
        print(f"    {vw:<10} W:{wc:>2} N:{nc:>2} L:{lc:>2}")

print(f"\n  Aspect Ratio:")
for asp in ["portrait", "landscape", "square"]:
    wc = w_analysis["aspect_dist"].get(asp, 0)
    nc = n_analysis["aspect_dist"].get(asp, 0)
    lc = l_analysis["aspect_dist"].get(asp, 0)
    if wc or nc or lc:
        print(f"    {asp:<10} W:{wc:>2} N:{nc:>2} L:{lc:>2}")

print(f"\n{'─'*40}")
print("3. HOOK TYPE ANALYSIS")
print(f"{'─'*40}")
all_hooks = set()
for d in [w_analysis, n_analysis, l_analysis]:
    all_hooks.update(d["hook_type_dist"].keys())
for hook in sorted(all_hooks):
    wc = w_analysis["hook_type_dist"].get(hook, 0)
    nc = n_analysis["hook_type_dist"].get(hook, 0)
    lc = l_analysis["hook_type_dist"].get(hook, 0)
    print(f"  {hook:<20} W:{wc:>2} N:{nc:>2} L:{lc:>2}")

print(f"\n{'─'*40}")
print("4. PLATFORM ANALYSIS")
print(f"{'─'*40}")
for plat in ["iOS", "Android"]:
    wc = w_analysis["platform_dist"].get(plat, 0)
    nc = n_analysis["platform_dist"].get(plat, 0)
    lc = l_analysis["platform_dist"].get(plat, 0)
    print(f"  {plat:<10} W:{wc:>2} N:{nc:>2} L:{lc:>2}")


# ── Key Insights ──

print(f"\n{'='*60}")
print("KEY CONTRASTIVE INSIGHTS")
print("=" * 60)

insights = []

# Color insights
w_bright = w_analysis["avg_brightness"]
l_bright = l_analysis["avg_brightness"]
if w_bright > l_bright * 1.05:
    insights.append(f"Winners are {w_bright/l_bright:.1%} brighter than losers (avg brightness {w_bright:.0f} vs {l_bright:.0f})")
elif l_bright > w_bright * 1.05:
    insights.append(f"Losers are {l_bright/w_bright:.1%} brighter than winners — dark/moody palette may perform better")

w_contrast = w_analysis["avg_contrast"]
l_contrast = l_analysis["avg_contrast"]
if w_contrast > l_contrast * 1.05:
    insights.append(f"Winners have {w_contrast/l_contrast:.1%} higher contrast ({w_contrast:.0f} vs {l_contrast:.0f}) — more visual pop")
elif l_contrast > w_contrast * 1.05:
    insights.append(f"Losers have {l_contrast/w_contrast:.1%} higher contrast — too much contrast may hurt")

# Hook insights
w_hooks = w_analysis["hook_type_dist"]
l_hooks = l_analysis["hook_type_dist"]
for hook in set(list(w_hooks.keys()) + list(l_hooks.keys())):
    w_pct = w_hooks.get(hook, 0) / max(w_analysis["count"], 1) * 100
    l_pct = l_hooks.get(hook, 0) / max(l_analysis["count"], 1) * 100
    if w_pct > l_pct * 2 and w_pct > 10:
        insights.append(f"'{hook}' hook: {w_pct:.0f}% of winners vs {l_pct:.0f}% of losers — WINNER PATTERN")
    elif l_pct > w_pct * 2 and l_pct > 10:
        insights.append(f"'{hook}' hook: {l_pct:.0f}% of losers vs {w_pct:.0f}% of winners — LOSER PATTERN")

# Composition insights
w_vw = w_analysis["vertical_weight_dist"]
l_vw = l_analysis["vertical_weight_dist"]
for vw in ["top", "center", "bottom", "balanced"]:
    w_pct = w_vw.get(vw, 0) / max(w_analysis["count"], 1) * 100
    l_pct = l_vw.get(vw, 0) / max(l_analysis["count"], 1) * 100
    diff = abs(w_pct - l_pct)
    if diff > 20:
        if w_pct > l_pct:
            insights.append(f"'{vw}-weighted' composition: {w_pct:.0f}% of winners vs {l_pct:.0f}% of losers — WINNER PATTERN")
        else:
            insights.append(f"'{vw}-weighted' composition: {l_pct:.0f}% of losers vs {w_pct:.0f}% of winners — LOSER PATTERN")

for i, insight in enumerate(insights):
    print(f"  [{i+1}] {insight}")

if not insights:
    print("  (Sample size too small for statistically significant insights)")


# ── Save enriched DNA ──

output_path = ROOT / "output" / "creative_analysis" / "dna_cache" / "contrastive_dna.json"
output = {
    "version": "1.0.0",
    "source": "facebook_graph_api",
    "analysis_method": "local_contrastive_analysis",
    "extracted_at": datetime.now().isoformat(),
    "summary": {
        "total_images": len(features),
        "winners": w_analysis["count"],
        "neutrals": n_analysis["count"],
        "losers": l_analysis["count"],
    },
    "tier_analysis": {
        "winners": w_analysis,
        "neutrals": n_analysis,
        "losers": l_analysis,
    },
    "contrastive_insights": insights,
    "creatives": features,
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nSaved contrastive DNA to: {output_path}")
print(f"  {len(features)} features, {len(insights)} contrastive insights")