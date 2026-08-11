"""Phase 2.1.6.1 — 多模式 Gameplay Understanding（基于 OpenCLIP 文图相似度）。

升级点（对比 2.1.6 单维 gameplay_clarity）：
  - 4 种玩法模式各自独立 CLIP 评分：merge / evolution / collection / reward_reveal
  - gameplay_clarity（即 Gameplay Understanding 的 pattern-match 分量）
    = max(4 模式分)，不再只认 Merge Board → Level/Collection/Reward 类型不再误判
  - 额外输出 gameplay_type（argmax 模式）+ confidence（该模式分）
  - 新增 action_visibility（玩法动作是否可见），供 Gameplay Understanding 融合

每个维度用 positive/negative prompt 对，对图像/文本 embedding 余弦相似度做
temperature-scaled softmax（temperature≈100，对应 OpenCLIP logit_scale），
得到 0-1 的「该维度满足度」。

注：这是 CLIP 文图相似度的近似审核，不是 VLM 真理解。生产环境建议接真
VLM（如 GPT-4o）做终检。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from market_ops.creative_intelligence.factory.ranking.clip_ranker import (  # noqa: E402
    OpenCLIPEncoder,
)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _prob(pos: float, neg: float, temperature: float = 100.0) -> float:
    """用 OpenCLIP logit_scale 量级的 temperature 放大 cosine 差值。

    CLIP 的 image-text 余弦相似度原始尺度很小（正负 prompt 差常 <0.1），
    直接 softmax 会全挤在 0.5。乘 temperature（≈100）后，pos/neg 的微小
    差异被拉开为接近 0/1 的概率。
    """
    m = max(pos, neg)
    ex = np.exp([(pos - m) * temperature, (neg - m) * temperature])
    return float(ex[0] / ex.sum())


# 4 种玩法模式的 (positive, negative) prompt 对。
# pos 描述该模式的核心视觉；neg 描述「无该模式 / 静态 / 无动作」。
_PATTERN_PROMPTS: dict[str, tuple[str, str]] = {
    "merge": (
        "two identical items with a plus sign and an arrow combining into one "
        "higher-level reward, merge puzzle gameplay loop",
        "no items combining, no plus sign, no upgrade arrow, a single static object",
    ),
    "evolution": (
        "a low-level character transforming and leveling up into a powerful "
        "higher-level character, character upgrade evolution with before and after",
        "a static character with no transformation or level up, no before and after",
    ),
    "collection": (
        "multiple collectible items gathered together forming a collection or "
        "treasure hoard of many items",
        "only one or two isolated items, no collection of multiple things",
    ),
    "reward_reveal": (
        "a hidden reward being revealed with an excited reaction, a big reveal "
        "moment of a legendary prize",
        "plain gameplay with no reward being revealed, no surprise moment",
    ),
}

# 辅助维度（动作可见度 / 奖励可见度 / 视觉质感 / 钩子强度）
_AUX_PROMPTS: dict[str, tuple[str, str]] = {
    "action_visibility": (
        "clear visible gameplay action such as items merging or a character "
        "transforming, motion and change happening on screen",
        "a static frozen scene with no visible action or transformation",
    ),
    "reward_visibility": (
        "a prominent large reward such as a baby dragon or legendary glowing item, "
        "central and clear",
        "reward is tiny, hidden behind scenery, or absent from the image",
    ),
    "visual_quality": (
        "high-end 3D mobile game advertisement, premium App Store quality, "
        "polished lighting",
        "low-quality, amateur, blurry, or broken AI image",
    ),
    "hook_strength": (
        "strong visual hook showing the merging gameplay or the main reward "
        "grabbing attention",
        "image whose main focus is not gameplay or reward but only ambient scenery",
    ),
    # 已弃用：CLIP 在「渲染畸形 / 文字」方向反转，不可靠。保留仅为兼容旧调用。
    "ai_artifact": (
        "clean properly rendered 3D mobile game artwork",
        "AI generated image with melted objects and broken distorted anatomy",
    ),
}


class GameplayChecker:
    def __init__(self, encoder: OpenCLIPEncoder) -> None:
        self.enc = encoder
        # 预编码所有 prompt 文本
        self._pat_txt: dict[str, np.ndarray] = {}
        for k, (pos, neg) in _PATTERN_PROMPTS.items():
            self._pat_txt[k] = np.stack(
                [self.enc.encode_text(pos), self.enc.encode_text(neg)], axis=0
            )
        self._aux_txt: dict[str, np.ndarray] = {}
        for k, (pos, neg) in _AUX_PROMPTS.items():
            self._aux_txt[k] = np.stack(
                [self.enc.encode_text(pos), self.enc.encode_text(neg)], axis=0
            )

    def score(self, image_emb: np.ndarray) -> dict[str, float]:
        """返回多模式 Gameplay Understanding 结果。

        关键键：
          gameplay_clarity  : = max(4 模式分)，Gameplay Understanding 的 pattern 分量
          gameplay_type     : argmax 模式名（merge/evolution/collection/reward_reveal）
          confidence        : 该模式分（= gameplay_clarity）
          merge_score / evolution_score / collection_score / reward_score : 4 模式分
          action_visibility / reward_visibility / visual_quality / hook_strength
        """
        out: dict[str, float] = {}

        # 4 模式
        pat_scores: dict[str, float] = {}
        for k in _PATTERN_PROMPTS:
            pos_v, neg_v = self._pat_txt[k][0], self._pat_txt[k][1]
            p = _cosine(image_emb, pos_v)
            n = _cosine(image_emb, neg_v)
            pat_scores[k] = round(_prob(p, n), 4)

        # argmax → 主导模式
        best = max(pat_scores, key=pat_scores.get)  # type: ignore[arg-type]
        out["gameplay_type"] = best
        out["confidence"] = pat_scores[best]
        out["gameplay_clarity"] = pat_scores[best]  # = Gameplay Understanding pattern 分量
        for k in _PATTERN_PROMPTS:
            out[f"{k}_score"] = pat_scores[k]

        # 辅助维度
        for k in _AUX_PROMPTS:
            pos_v, neg_v = self._aux_txt[k][0], self._aux_txt[k][1]
            p = _cosine(image_emb, pos_v)
            n = _cosine(image_emb, neg_v)
            out[k] = round(_prob(p, n), 4)

        return out
