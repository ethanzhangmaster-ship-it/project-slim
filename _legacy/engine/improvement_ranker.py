"""Improvement Ranker — 对优化建议排序，输出最值得改的前 N 个点。

输入：
  counterfactual simulation results (mutations × ΔROAS/ΔCTR/ΔCVR)

输出：
  ranked improvements:
    1. Hook contrast +20% → +0.08 ROAS uplift
    2. Mid entropy -15%  → +0.05 ROAS uplift
    3. Late brightness +25% → +0.03 ROAS uplift
"""
from __future__ import annotations
from typing import Dict, List, Tuple


def rank_improvements(results: List[Dict],
                      target: str = "roas",
                      max_results: int = 5) -> List[Dict]:
    """Rank mutations by expected performance uplift.

    Args:
        results: list from counterfactual_simulator.simulate_all()
        target: "roas", "ctr", or "cvr"
        max_results: top N to return

    Returns:
        list of ranked improvements:
        [{
            "rank": 1,
            "mutation": "increase_hook_contrast",
            "description": "...",
            "ae_instruction": "...",
            "current_prediction": 0.42,
            "new_prediction": 0.50,
            "delta": 0.08,
            "delta_pct": 19.0,
            "dimension": "hook",
            "time_window": "0-1s",
            "feature": "hook_contrast",
            "current_value": 0.15,
            "new_value": 0.18,
        }, ...]
    """
    # Filter to relevant target
    filtered = [r for r in results if r.get("target") == target]

    # Sort by delta descending
    sorted_results = sorted(filtered, key=lambda x: x.get("delta", 0), reverse=True)

    # Add rank
    ranked = []
    for i, r in enumerate(sorted_results[:max_results]):
        ranked.append({
            "rank": i + 1,
            "mutation": r["mutation"],
            "description": r.get("description", ""),
            "ae_instruction": r.get("ae_instruction", ""),
            "current_prediction": r["current_prediction"],
            "new_prediction": r["new_prediction"],
            "delta": r["delta"],
            "delta_pct": r["delta_pct"],
            "dimension": r.get("dimension", "unknown"),
            "time_window": r.get("time_window", "unknown"),
            "feature": r["feature"],
            "current_value": r["current_value"],
            "new_value": r["new_value"],
        })

    return ranked


def summarize_improvements(ranked: List[Dict], current_roas: float) -> Dict:
    """Generate summary of all improvements.

    Returns:
        {
            "current_roas": 0.42,
            "predicted_optimized_roas": 0.58,
            "total_roas_uplift": 0.16,
            "n_improvements": 3,
            "top_focus": "hook",
            "improvements": [ranked list],
        }
    """
    total_uplift = sum(r.get("delta", 0) for r in ranked if r["delta"] > 0)

    # Determine main focus dimension
    dimensions = {}
    for r in ranked:
        dim = r.get("dimension", "unknown")
        dimensions[dim] = dimensions.get(dim, 0) + abs(r.get("delta", 0))
    top_dim = max(dimensions, key=dimensions.get) if dimensions else "unknown"

    return {
        "current_roas": round(current_roas, 4),
        "predicted_optimized_roas": round(current_roas + total_uplift, 4),
        "total_roas_uplift": round(total_uplift, 4),
        "n_improvements": len(ranked),
        "top_focus": top_dim,
        "improvements": ranked,
    }
