"""Phase 2.1.6.2 — Composition Validator（自动版式校验）。

对每张已生成的创意做 4 项构图检查（PRD §8）：
  1. 主体比例     gameplay_area_ratio   >= 0.45
  2. Reward 可见  reward_visibility      >= 0.60
  3. 角色主导     character_attention    <= 0.35（越低越好）
  4. Before/After state_transition_score >= 0.70

并融合出 composition_match（0-1），供 Production Score V2 使用。

关于度量可靠性的重要说明（踩坑）：
  CLIP ViT-B-32 对本数据集的某些细粒度广告构图概念方向不稳定 / 区分度极低：
   - 「gameplay 占满画面 vs 大量背景」：pos/neg cosine 几乎相等，无法区分。
   - 「before/after 转变 vs 静态单图」：单张 merge 图被 CLIP 判为「静态单图」，
     该探针方向反转、不可用。
  因此本实现改用「可靠信号」重构这两项：
   - gameplay_area_ratio = 0.5*玩法模式置信度 + 0.5*(1 - 角色抢主体度)
     （玩法被识别 + 角色不抢主体 ⇒ 玩法占据画面主体）
   - state_transition_score = 玩法模式置信度（被识别的 merge/evolution/collection
     本身就是 before→after 转变的识别）
  reward_visibility 与 character_attention 仍用 CLIP（这两个方向稳定、区分度好）。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

from market_ops.creative_intelligence.factory.ranking.clip_ranker import (  # noqa: E402
    OpenCLIPEncoder,
)

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

# 校验阈值
GAMEPLAY_AREA_MIN = 0.45
REWARD_VIS_MIN = 0.60
CHARACTER_ATTENTION_MAX = 0.35
STATE_TRANSITION_MIN = 0.70


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _prob(pos: float, neg: float, temperature: float = 100.0) -> float:
    """temperature-scaled softmax（放大 CLIP 微小 cosine 差值）。"""
    m = max(pos, neg)
    ex = np.exp([(pos - m) * temperature, (neg - m) * temperature])
    return float(ex[0] / ex.sum())


# 角色是否「抢主体 / 海报立绘式肖像」—— pos 越高代表越像 portrait 主宰画面。
# 方向稳定：poster 图 pos>>neg，in-scene host 图 neg>>pos（已验证）。
_CHAR_PROMPTS = (
    "a close-up character portrait that dominates the frame as the main subject",
    "a character that is small and set in the background as a supporting element",
)


def character_attention(image_emb: np.ndarray, encoder: OpenCLIPEncoder) -> float:
    """角色抢主体程度（0-1，越低越好）。"""
    char_pos = _cosine(image_emb, encoder.encode_text(_CHAR_PROMPTS[0]))
    char_neg = _cosine(image_emb, encoder.encode_text(_CHAR_PROMPTS[1]))
    return round(_prob(char_pos, char_neg), 4)


def gameplay_area_ratio(pattern_confidence: float, char_attention: float) -> float:
    """玩法主体占画面比例（PRD §8 主体比例）。

    用可靠信号重构：玩法被识别（pattern_conf 高）+ 角色不抢主体（char_attn 低）
    ⇒ 玩法占据画面主体。范围 0-1。
    """
    v = 0.5 * float(pattern_confidence) + 0.5 * (1.0 - float(char_attention))
    return round(float(min(1.0, max(0.0, v))), 4)


def composition_match(
    gameplay_area_ratio_v: float,
    reward_visibility: float,
    character_attention: float,
    state_transition_score: float,
) -> float:
    """融合 4 项子分 -> composition_match（0-1）。

    每项归一化到 0-1：达到/超过阈值即 ≈1；未达则按比例缩放。
    character_attention 越低越好（1 - attn/阈值）。
    """
    c1 = min(1.0, gameplay_area_ratio_v / GAMEPLAY_AREA_MIN)
    c2 = min(1.0, float(reward_visibility) / REWARD_VIS_MIN)
    c3 = max(0.0, 1.0 - (float(character_attention) / CHARACTER_ATTENTION_MAX))
    c4 = min(1.0, float(state_transition_score) / STATE_TRANSITION_MIN)
    return round(float(np.mean([c1, c2, c3, c4])), 4)


def evaluate(
    image_emb: np.ndarray,
    reward_visibility: float,
    pattern_confidence: float,
    encoder: OpenCLIPEncoder,
) -> Dict[str, Any]:
    """完整构图校验入口。

    image_emb          : 已编码的图像 embedding（避免重复编码）
    reward_visibility  : 来自 CriticAgent 的 cs.reward_visibility（CLIP，可靠）
    pattern_confidence : 来自 CriticAgent 的 cs.gameplay_clarity（4 模式 argmax 分）
    encoder            : OpenCLIPEncoder（仅用于 character_attention 探针）
    """
    char_attn = character_attention(image_emb, encoder)
    gar = gameplay_area_ratio(pattern_confidence, char_attn)
    # before/after 转变 = 被识别的玩法模式本身
    state = round(float(pattern_confidence), 4)
    match = composition_match(gar, reward_visibility, char_attn, state)

    checks = {
        "gameplay_area_ratio_ok": gar >= GAMEPLAY_AREA_MIN,
        "reward_visible": reward_visibility >= REWARD_VIS_MIN,
        "character_secondary": char_attn <= CHARACTER_ATTENTION_MAX,
        "state_transition_ok": state >= STATE_TRANSITION_MIN,
    }
    return {
        "gameplay_area_ratio": gar,
        "reward_visibility": round(float(reward_visibility), 4),
        "character_attention": char_attn,
        "state_transition_score": state,
        "composition_match": match,
        "checks": checks,
    }
