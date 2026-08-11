"""DNA Match Checker — 检查生成图是否符合 Winner DNA

比较 4 个维度:
- layout_match: 构图布局
- gameplay_ratio_match: 玩法区域占比
- reward_match: 奖励类型
- color_match: 主色调

Production Score V3:
  0.25 Gameplay + 0.20 Reward + 0.20 Winner Similarity
  + 0.15 Composition + 0.10 Visual Quality + 0.10 Diversity
"""
from typing import Dict, List, Optional

from ..config import PRODUCTION_SCORE_WEIGHTS_V3


def check_dna_match(generated_dna: dict, winner_dna: dict) -> Dict[str, bool]:
    """检查生成图 DNA 与 Winner DNA 的匹配度

    Args:
        generated_dna: 生成图的 DNA (同 structure as winner DNA)
        winner_dna: Winner 的 DNA

    Returns:
        各维度匹配结果
    """
    gen_comp = generated_dna.get("composition", {})
    win_comp = winner_dna.get("composition", {})

    # Layout match
    layout_match = generated_dna.get("layout", "") == winner_dna.get("layout", "")

    # Gameplay ratio match (±15% tolerance)
    gen_ratio = gen_comp.get("gameplay_area", {}).get("ratio", 0)
    win_ratio = win_comp.get("gameplay_area", {}).get("ratio", 0)
    gameplay_ratio_match = abs(gen_ratio - win_ratio) < 0.15

    # Reward type match
    gen_reward = generated_dna.get("reward", {}).get("type", "")
    win_reward = winner_dna.get("reward", {}).get("type", "")
    reward_match = gen_reward == win_reward or win_reward == "mixed"

    # Color match
    gen_color = generated_dna.get("style", {}).get("color_palette", "")
    win_color = winner_dna.get("style", {}).get("color_palette", "")
    color_match = gen_color == win_color

    return {
        "layout_match": layout_match,
        "gameplay_ratio_match": gameplay_ratio_match,
        "reward_match": reward_match,
        "color_match": color_match,
        "match_score": sum([layout_match, gameplay_ratio_match,
                           reward_match, color_match]) / 4.0,
    }


def calculate_production_score_v3(
    gameplay_score: float = 0,
    reward_score: float = 0,
    winner_similarity: float = 0,
    composition_score: float = 0,
    visual_quality: float = 0,
    diversity_score: float = 0,
) -> Dict[str, float]:
    """计算 Production Score V3

    所有输入分数范围: 0.0 ~ 1.0

    Returns:
        {"total": float, "breakdown": {...}, "passed": bool}
    """
    w = PRODUCTION_SCORE_WEIGHTS_V3

    total = (
        w["gameplay"] * gameplay_score +
        w["reward"] * reward_score +
        w["winner_similarity"] * winner_similarity +
        w["composition"] * composition_score +
        w["visual_quality"] * visual_quality +
        w["diversity"] * diversity_score
    )

    return {
        "total": round(total, 4),
        "passed": total >= 0.85,
        "breakdown": {
            "gameplay": round(gameplay_score, 3),
            "reward": round(reward_score, 3),
            "winner_similarity": round(winner_similarity, 3),
            "composition": round(composition_score, 3),
            "visual_quality": round(visual_quality, 3),
            "diversity": round(diversity_score, 3),
        },
        "weights": w,
    }
