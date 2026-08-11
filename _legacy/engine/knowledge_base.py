"""Knowledge Base Builder — structured creative pattern knowledge store.

Output: creative_patterns.json consumable by:
  - AI image generation (prompt engineering)
  - AI script writing (structure template)
  - AI ad auto-generation
"""
from datetime import datetime


def build_knowledge_base(patterns: dict, explanations: dict) -> dict:
    """Build structured creative knowledge base from patterns + explanations.

    Returns:
        {
            version, generated_at, total_patterns,
            patterns, best_practices, recommendations
        }
    """
    kb = {
        "version": "3.5.0",
        "generated_at": datetime.now().isoformat(),
        "total_patterns": len(patterns),
        "patterns": {},
        "best_practices": {},
        "recommendations": [],
    }

    for cid, p in sorted(patterns.items(), key=lambda x: x[1]["total_spend"], reverse=True):
        ex = explanations.get(cid, {})
        arch = p["pattern"]

        kb["patterns"][cid] = {
            "pattern_name": arch,
            "best_duration": f"{p['mean_duration']:.0f}s" if p['mean_duration'] else "N/A",
            "best_ratio": "9:16",
            "eagle_examples": p["examples"][:3],
            "avg_spend": round(p["total_spend"] / max(p["fb_video_count"], 1), 2),
            "avg_revenue": round(p["total_revenue"] / max(p["fb_video_count"], 1), 2) if p["fb_video_count"] else 0,
            "roas": p["roas"],
            "total_spend": p["total_spend"],
            "verdict": ex.get("verdict", ""),
            "action": ex.get("action", ""),
            "insight": ex.get("archetype_analysis", ""),
            "optimization_tip": ex.get("optimization_tip", ""),
        }

    top = sorted(patterns.values(), key=lambda x: x["total_spend"] * x["roas"], reverse=True)[:5]
    for i, p in enumerate(top):
        kb["best_practices"][f"rank_{i+1}"] = {
            "pattern": p["pattern"],
            "total_spend": p["total_spend"],
            "roas": p["roas"],
            "takeaway": f"Scale {p['pattern']} pattern: ${p['total_spend']:,.0f} at ROAS {p['roas']:.2f}",
        }

    for p in sorted(patterns.values(), key=lambda x: x["total_spend"] * x["roas"], reverse=True)[:3]:
        if p["roas"] >= 0.5:
            kb["recommendations"].append({
                "type": "scale",
                "pattern": p["pattern"],
                "reason": f"ROAS {p['roas']:.2f} on ${p['total_spend']:,.0f} spend",
                "action": "Increase production of this creative type by 2x",
            })

    for p in sorted(patterns.values(), key=lambda x: x["total_spend"]):
        if p["roas"] < 0.3 and p["total_spend"] > 200:
            kb["recommendations"].append({
                "type": "reduce",
                "pattern": p["pattern"],
                "reason": f"ROAS {p['roas']:.2f} on ${p['total_spend']:,.0f} spend",
                "action": "Reduce or pause this creative type",
            })

    return kb
