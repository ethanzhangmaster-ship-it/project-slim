"""Phase 2.1.6.1 — 总分模型 + Hard Reject 规则（升级版）。

Production Score =
    0.25 Gameplay Understanding
  + 0.20 Reward Visibility
  + 0.15 Hook Strength
  + 0.15 Ad Structure
  + 0.15 Visual Quality
  + 0.10 CLIP Winner Similarity

Gameplay Understanding（玩法理解度）= 融合 3 个子分量：
    0.50 Pattern Match   （= max(merge/evolution/collection/reward) 4 模式分）
  + 0.30 Action Visibility（玩法动作是否清晰可见）
  + 0.20 Reward Visibility（奖励是否突出）

Hard Reject（任一触发 → 直接 FAIL）：
  - Wrong Format        : 长宽比不符 winner ±5%
  - AI Text Dominates   : 大面积乱码文字 / 假 Logo / 假按钮伪影
  - No Gameplay Understood: 4 模式分全低（<0.40），即没有可识别玩法 →
                           海报/立绘/风景类被此处拦截（替代旧 No Merge / Character Portrait）
"""
from __future__ import annotations

from dataclasses import dataclass

# 维度 PASS 阈值（用于非 Hard Reject 的维度判定）
DIM_PASS = 0.75
# Hard Reject 触发阈值（更严格）
REJECT_GAMEPLAY = 0.40   # 4 模式分全都 < 0.40 → 无玩法
REJECT_ADSTRUCT = 0.40
REJECT_ARTIFACT = 0.70    # ai_artifact_score（连通域文字密度）超过即判定大面积乱码

# Gameplay Understanding 子分量权重
GU_PATTERN_W = 0.50
GU_ACTION_W = 0.30
GU_REWARD_W = 0.20

# 生产总分权重（合计 1.0）
PRODUCTION_WEIGHTS = {
    "gameplay_understanding": 0.25,
    "reward_visibility": 0.20,
    "hook_strength": 0.15,
    "ad_structure": 0.15,
    "visual_quality": 0.15,
    "clip_similarity": 0.10,
}

# 生产总分权重 V2（Phase 2.1.6.2 升级，合计 1.0）
# 引入 Composition Match + Diversity，强化「广告结构」与「批次多样性」
PRODUCTION_WEIGHTS_V2 = {
    "gameplay_understanding": 0.30,
    "reward_visibility": 0.20,
    "composition_match": 0.15,
    "visual_quality": 0.15,
    "clip_similarity": 0.10,
    "diversity": 0.10,
}


def gameplay_understanding(pattern_match: float, action_visibility: float, reward_visibility: float) -> float:
    """Gameplay Understanding = 0.5*Pattern Match + 0.3*Action + 0.2*Reward。"""
    gu = (
        GU_PATTERN_W * float(pattern_match)
        + GU_ACTION_W * float(action_visibility)
        + GU_REWARD_W * float(reward_visibility)
    )
    return round(gu, 4)


def production_score(s: dict) -> float:
    """s 需含 6 个维度键（gameplay_understanding / reward_visibility / hook_strength
    / ad_structure / visual_quality / clip_similarity）。返回加权总分 0-1。"""
    total = 0.0
    for k, w in PRODUCTION_WEIGHTS.items():
        total += w * float(s.get(k, 0.0))
    return round(total, 4)


def production_score_v2(s: dict) -> float:
    """Production Score V2（Phase 2.1.6.2）。

    需含键：gameplay_understanding / reward_visibility / composition_match /
    visual_quality / clip_similarity / diversity。返回加权总分 0-1。
    """
    total = 0.0
    for k, w in PRODUCTION_WEIGHTS_V2.items():
        total += w * float(s.get(k, 0.0))
    return round(total, 4)


def apply_hard_reject(
    cs,
    aspect_ok: bool,
    ai_artifact_score: float,
    ad_structure_score: float,
) -> tuple[str, str]:
    """返回 (decision, hard_reject_reason)。

    cs: CreativeScore 实例（含 gameplay_clarity / reward_visibility / hook_strength /
    visual_quality 等）。先查 Hard Reject；无触发再按维度阈值判 PASS/FAIL。
    """
    # 1. Wrong Format
    if not aspect_ok:
        return "FAIL", "Wrong Format — aspect ratio does not match winner (±5%)"

    # 2. AI Text Dominates（大面积乱码文字 / 假 Logo / 假按钮）
    if ai_artifact_score >= REJECT_ARTIFACT:
        return "FAIL", (
            f"AI Text Dominates — artifact score {ai_artifact_score:.2f} "
            "(garbled text / fake button / fake logo)"
        )

    # 3. No Gameplay Understood（4 模式分全低 → 海报/立绘/风景类）
    if cs.gameplay_clarity < REJECT_GAMEPLAY:
        return "FAIL", "No Gameplay Understood — no recognizable merge/evolution/collection/reward pattern"

    # 无 Hard Reject → 按维度阈值判 PASS
    failed = [
        name
        for name, val in (
            ("gameplay_understanding", cs.gameplay_understanding),
            ("reward_visibility", cs.reward_visibility),
            ("hook_strength", cs.hook_strength),
            ("visual_quality", cs.visual_quality),
        )
        if val < DIM_PASS
    ]
    if failed:
        return "FAIL", "Below threshold: " + ", ".join(failed)
    return "PASS", ""
