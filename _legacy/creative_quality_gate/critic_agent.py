"""Phase 2.1.6 — Creative Critic Agent。

输入：
  creative_image.png + winner_reference.png + creative_strategy.json
输出：
  {
    "creative_id": "creative_001",
    "scores": {
      "hook_strength": 0.82, "gameplay_clarity": 0.91, "merge_visibility": 0.88,
      "reward_visibility": 0.85, "visual_quality": 0.90, "commercial_readiness": 0.87
    },
    "decision": "PASS",
    "issues": []
  }

commercial_readiness 在本实现中 = production_score（广告综合就绪度），
与 PRD 示例字段对齐。
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
    _cosine,
)

from creative_quality_gate.models import CreativeScore  # noqa: E402
from creative_quality_gate.visual_checker import (  # noqa: E402
    aspect_matches,
    reward_area_ratio,
    ai_text_density,
)
from creative_quality_gate.gameplay_checker import GameplayChecker  # noqa: E402
from creative_quality_gate.ad_structure_checker import AdStructureChecker  # noqa: E402
from creative_quality_gate.scoring import (  # noqa: E402
    production_score_v2,
    gameplay_understanding,
    apply_hard_reject,
)
from creative_composition.composition_validator import evaluate as composition_evaluate  # noqa: E402

# winner 长宽比基准（真实 winner_001 = 1:1）；可由策略文件覆盖
DEFAULT_REF_RATIO = 1.0


class CriticAgent:
    def __init__(self, device: str = "cpu") -> None:
        self.encoder = OpenCLIPEncoder(device=device)
        self.gameplay = GameplayChecker(self.encoder)
        self.adstruct = AdStructureChecker(self.encoder)
        self._winner_cache: dict[str, np.ndarray] = {}

    def _winner_emb(self, winner_path: str | Path) -> np.ndarray:
        p = str(winner_path)
        if p not in self._winner_cache:
            self._winner_cache[p] = self.encoder.encode_image(winner_path)
        return self._winner_cache[p]

    def evaluate(
        self,
        creative_path: str | Path,
        winner_path: str | Path,
        creative_id: str,
        group: str = "",
        mutation_type: str = "",
        ref_ratio: float = DEFAULT_REF_RATIO,
    ) -> CreativeScore:
        cs = CreativeScore(
            creative_id=creative_id,
            file=str(creative_path),
            group=group,
            mutation_type=mutation_type,
        )

        # --- 视觉基础检查 ---
        cs.aspect_ok, cs.aspect_ratio = aspect_matches(creative_path, ref_ratio)
        cs.reward_area_ratio = reward_area_ratio(creative_path)
        text_density = ai_text_density(creative_path)

        # --- CLIP 图像 embedding（一次编码复用）---
        img_emb = self.encoder.encode_image(creative_path)

        # --- 语义维度（多模式 Gameplay Understanding）---
        g = self.gameplay.score(img_emb)
        cs.gameplay_type = g["gameplay_type"]
        cs.gameplay_confidence = g["confidence"]
        cs.gameplay_clarity = g["gameplay_clarity"]          # = max(4 模式分)
        # 多模式子分数（可审计：4 个模式得分在 JSON 中可见）
        cs.merge_score = g["merge_score"]
        cs.evolution_score = g["evolution_score"]
        cs.collection_score = g["collection_score"]
        cs.reward_score = g["reward_reveal_score"]
        cs.merge_visibility = g["merge_score"]               # 兼容展示
        cs.reward_visibility = g["reward_visibility"]
        cs.hook_strength = g["hook_strength"]
        cs.visual_quality = g["visual_quality"]
        cs.action_visibility = g["action_visibility"]
        # ai_artifact 由连通域文字检测（scipy）主判。
        # 两个 CLIP 维度（文字/渲染畸形）在本数据集方向均反转，不可靠，已弃用。
        cs.ai_artifact_score = round(text_density, 4)

        # --- 广告结构 ---
        ad = self.adstruct.score(creative_path)
        ad_structure_score = ad["ad_structure_score"]
        cs.ad_structure_score = ad_structure_score

        # --- 构图校验（2.1.6.2 Composition Validator）---
        comp = composition_evaluate(
            img_emb, cs.reward_visibility, cs.gameplay_clarity, self.encoder
        )
        cs.composition_match = comp["composition_match"]
        cs.character_attention = comp["character_attention"]
        cs.gameplay_area_ratio = comp["gameplay_area_ratio"]
        cs.state_transition_score = comp["state_transition_score"]

        # --- CLIP 相似度（vs winner）---
        w_emb = self._winner_emb(winner_path)
        cs.clip_similarity = round((_cosine(img_emb, w_emb) + 1.0) / 2.0, 4)

        # --- 总分 ---
        cs.gameplay_understanding = gameplay_understanding(
            pattern_match=cs.gameplay_clarity,
            action_visibility=cs.action_visibility,
            reward_visibility=cs.reward_visibility,
        )
        # diversity 在单张评估时先用 0.5 占位，批次级由 run 脚本覆写
        cs.diversity = 0.5
        cs.production_score = production_score_v2(
            {
                "gameplay_understanding": cs.gameplay_understanding,
                "reward_visibility": cs.reward_visibility,
                "composition_match": cs.composition_match,
                "visual_quality": cs.visual_quality,
                "clip_similarity": cs.clip_similarity,
                "diversity": cs.diversity,
            }
        )

        # --- Hard Reject + 维度阈值判定 ---
        decision, reason = apply_hard_reject(cs, cs.aspect_ok, cs.ai_artifact_score, ad_structure_score)
        cs.decision = decision
        cs.hard_reject_reason = reason
        if reason:
            cs.issues.append(reason)

        # reward 占比辅助提示（不单独 reject，但记录）
        if cs.reward_area_ratio < 0.15:
            cs.issues.append(
                f"Reward area ratio {cs.reward_area_ratio:.2f} < 0.15 (reward not prominent enough)"
            )

        return cs

    def to_critic_json(self, cs: CreativeScore) -> dict:
        """输出 PRD 指定的 critic agent JSON 形状（2.1.6.1 升级版）。

        gameplay 块按 PRD §8 输出 {gameplay_type, confidence, clarity}；
        scores 块以 gameplay_understanding 替代旧 gameplay_clarity。
        """
        return {
            "creative_id": cs.creative_id,
            "gameplay": {
                "gameplay_type": cs.gameplay_type,
                "confidence": cs.gameplay_confidence,
                "clarity": cs.gameplay_clarity,
            },
            "scores": {
                "gameplay_understanding": cs.gameplay_understanding,
                "merge_visibility": cs.merge_visibility,
                "reward_visibility": cs.reward_visibility,
                "hook_strength": cs.hook_strength,
                "ad_structure": cs.ad_structure_score,
                "visual_quality": cs.visual_quality,
                "clip_similarity": cs.clip_similarity,
                "composition_match": cs.composition_match,
                "character_attention": cs.character_attention,
                "gameplay_area_ratio": cs.gameplay_area_ratio,
                "state_transition_score": cs.state_transition_score,
                "diversity": cs.diversity,
                "commercial_readiness": cs.production_score,
            },
            "decision": cs.decision,
            "issues": cs.issues,
        }
