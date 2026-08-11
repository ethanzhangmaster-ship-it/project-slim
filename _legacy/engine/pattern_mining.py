"""Pattern Mining — extract creative archetypes from clusters + performance.

Identifies structural patterns:
  Character Reveal, Gameplay Loop, Narrative, Text Scroll, Scene Display,
  Crafting System, Pet Showcase, Transformation, Plot Twist, Game Showcase
"""
import re
import numpy as np
from collections import Counter, defaultdict


# Keyword mapping: Eagle P4 name keywords → Creative Pattern name
PATTERN_KEYWORDS = {
    "Character Reveal": ["juesezhanshi", "character", "hero", "figure", "person"],
    "Gameplay Loop": ["wanfashipin", "wanfa", "gameplay", "play", "loop"],
    "Narrative": ["juqing", "story", "narrative", "drama", "plot"],
    "Hook Opener": ["kaitou", "hook", "opener", "intro", "片头"],
    "Text Scroll": ["wenzigundong", "text", "scroll", "caption", "文字滚动"],
    "Scene Display": ["changjingzhanshi", "scene", "environment", "背景"],
    "Crafting System": ["hechengwanfa", "craft", "merge", "cook", "合成"],
    "Pet Showcase": ["chongwuzhanshi", "pet", "animal", "宠物"],
    "Transformation": ["bianshen", "transform", "evolve", "变身"],
    "Plot Twist": ["fudan", "twist", "surprise", "反转"],
    "Game Showcase": ["wanfazhanshi", "showcase", "demo", "preview"],
}


def mine_patterns(eagle_items: list, cluster_info: dict, cluster_perf: dict) -> dict:
    """Mine creative patterns from clusters + performance data.

    Returns:
        dict[cid] → {
            pattern, eagle_asset_count, fb_video_count,
            total_spend, total_revenue, roas, mean_duration,
            duration_range, examples
        }
    """
    patterns = {}

    for cid, p in sorted(cluster_perf.items(), key=lambda x: x[1]["total_spend"], reverse=True):
        c = cluster_info.get(cid, {})
        members = c.get("members", [])
        if not members:
            continue

        member_text = " ".join(members).lower()
        matched = {}
        for pname, keywords in PATTERN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in member_text)
            if score > 0:
                matched[pname] = score

        main_pattern = max(matched, key=matched.get) if matched else "Unknown"
        fb_count = p.get("fb_count", 0)
        spend = p.get("total_spend", 0)
        rev = p.get("total_revenue", 0)
        roas = rev / max(spend, 1)
        durs = c.get("durations", [])

        patterns[cid] = {
            "pattern": main_pattern,
            "pattern_score": max(matched.values()) if matched else 0,
            "patterns_matched": dict(sorted(matched.items(), key=lambda x: -x[1])),
            "eagle_asset_count": len(members),
            "fb_video_count": fb_count,
            "total_spend": round(spend, 2),
            "total_revenue": round(rev, 2),
            "roas": round(roas, 4),
            "mean_duration": round(float(np.mean(durs)), 1) if durs else 0,
            "duration_range": f"{min(durs):.0f}s-{max(durs):.0f}s" if durs else "N/A",
            "examples": members[:5],
        }

    return patterns
