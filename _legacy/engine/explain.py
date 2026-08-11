"""Explainability Engine — rule-based → LLM-ready explanations.

Generates human-readable analysis for each cluster:
  - Why it performs well/poorly
  - What to do next
  - Archetype-specific insights
  - Duration recommendations

Designed to be swapped with GPT/local LLM later.
"""

def generate_explanation(cluster_id: str, pattern_info: dict) -> dict:
    """Generate structured explanation for a creative cluster.

    Output keys:
      verdict, action, archetype_analysis, duration_insight, metrics
    """
    arch = pattern_info.get("pattern", "Unknown")
    roas = pattern_info.get("roas", 0)
    spend = pattern_info.get("total_spend", 0)
    dur = pattern_info.get("mean_duration", 0)
    dur_range = pattern_info.get("duration_range", "N/A")
    eagles = pattern_info.get("eagle_asset_count", 0)
    fbs = pattern_info.get("fb_video_count", 0)

    # ── Verdict ──
    if roas >= 0.8:
        verdict = "🔥 HIGH PERFORMANCE — Scale this creative pattern"
        action = "Increase budget allocation. Produce more variants in this style."
    elif roas >= 0.5:
        verdict = "✅ MODERATE PERFORMANCE — Keep testing"
        action = "Maintain current spend. Iterate on top-performing variants."
    elif roas > 0:
        verdict = "⚠️ LOW PERFORMANCE — Needs optimization"
        action = "Reduce spend. Test different hook or CTA variations."
    else:
        verdict = "❌ ZERO ROAS — Stop or fundamental redesign"
        action = "Pause immediately. This pattern does not convert."

    # ── Archetype-specific insights ──
    ARCH_INSIGHTS = {
        "Character Reveal": {
            "why": "Character reveal hooks generate curiosity-driven clicks. Players form emotional connections in <3s.",
            "tip": "Ensure character occupies 60%+ of frame. Use bright colors. Add subtle entrance animation."
        },
        "Gameplay Loop": {
            "why": "Gameplay loops demonstrate value proposition directly. Seeing the core mechanic builds purchase intent.",
            "tip": "Show the most satisfying 3 seconds. Add on-screen text overlay explaining the mechanic."
        },
        "Narrative": {
            "why": "Narrative hooks create cliffhanger effect. Users click to see 'what happens next'.",
            "tip": "Start with a conflict or mystery. End before resolution to drive CTA."
        },
        "Hook Opener": {
            "why": "Quick hooks capture attention before users scroll past. Critical for low-attention audiences.",
            "tip": "First frame must be visually striking. Keep hook ≤5s before showing game."
        },
        "Text Scroll": {
            "why": "Text scroll appeals to information-seeking users. Effective for utility/gameplay education.",
            "tip": "Keep text large and readable on mobile. Use 3-5 bullet points max."
        },
    }

    arch_info = ARCH_INSIGHTS.get(arch, {
        "why": f"This pattern ({arch}, {dur:.0f}s avg) attracted {fbs} FB creatives with ${spend:,.0f} total spend.",
        "tip": "Analyze top-performing videos in this cluster to identify visual patterns."
    })

    # ── Duration insight ──
    dur_insight = (
        f"Average duration: {dur:.0f}s (range: {dur_range}). "
        + ("Optimal for mobile feed consumption."
           if 15 <= dur <= 45
           else "Consider adjusting to 15-45s range for better retention.")
    )

    return {
        "cluster_id": cluster_id,
        "verdict": verdict,
        "action": action,
        "archetype_analysis": arch_info["why"],
        "optimization_tip": arch_info["tip"],
        "duration_insight": dur_insight,
        "metrics": {
            "roas": round(roas, 4),
            "total_spend": round(spend, 2),
            "eagle_assets": eagles,
            "fb_videos": fbs,
            "mean_duration": round(dur, 1),
        },
    }
