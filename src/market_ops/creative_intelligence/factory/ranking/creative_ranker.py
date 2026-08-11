"""Creative Ranking Score V2 — Phase 2.1 综合排序（0-1 尺度）。

Final Score =
    40%  CLIP Winner Similarity
    30%  DNA Mutation Quality
    20%  Visual Quality
    10%  Diversity Score

输出候选含 ranking_mode（openclip / clip / heuristic），各子分与总分均为 0-1。
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from market_ops.creative_intelligence.factory.dna.dna_mutator import DNAMutator
from market_ops.creative_intelligence.factory.ranking.clip_ranker import CLIPRanker

_REWARD_TIER = {
    "legendary shadow dragon": 3,
    "celestial phoenix": 3,
    "crown of starlight": 3,
    "treasure vault of coins": 2,
    "golden grimoire": 2,
    "blooming celestial flower": 2,
}

_GOOD_COMPOSITIONS = {
    "before_after",
    "collection",
    "upgrade_moment",
    "merge_evolution",
    "reward_reveal",
}


class CreativeRanker:
    def __init__(self, clip_mode: str = "auto", embeddings_dir: str | Path | None = None) -> None:
        self.clip_mode = clip_mode
        self.embeddings_dir = embeddings_dir
        self._mutator = DNAMutator()

    # ------------------------------------------------------------------
    def rank(
        self,
        winner: dict[str, Any],
        creatives: list[dict[str, Any]],
        reference: dict[str, Any] | None,
        top_k: int = 10,
    ) -> dict[str, Any]:
        base = self._mutator._extract_base_dna(winner)
        winner_code = winner.get("winner_code", "000")

        # 1) CLIP 胜者相似度
        clip = CLIPRanker(self.clip_mode, self.embeddings_dir)
        clip_rank = clip.rank(
            winner, reference.get("path") if reference else None, creatives, winner_code=winner_code
        )
        sim_map = {r["creative_id"]: r["similarity"] for r in clip_rank}

        # 2) DNA / Visual / Diversity 子分（0-100）→ 0-1
        dnaq = {
            c["creative_id"]: self._dna_quality(base, c.get("dna", {})) / 100.0
            for c in creatives
        }
        visq = {
            c["creative_id"]: self._visual_quality(c.get("dna", {})) / 100.0
            for c in creatives
        }
        div = self._diversity(creatives)

        # 3) Final Score（0-1）
        rows: list[dict[str, Any]] = []
        for c in creatives:
            cid = c["creative_id"]
            clip_sim = sim_map[cid]
            final = (
                0.4 * clip_sim
                + 0.3 * dnaq[cid]
                + 0.2 * visq[cid]
                + 0.1 * (div[cid] / 100.0)
            )
            rows.append(
                {
                    "creative_id": cid,
                    "mutation_id": c.get("mutation_id"),
                    "mutation_reason": c.get("mutation_reason", ""),
                    "dna": c.get("dna", {}),
                    "ranking_mode": clip.mode,
                    "clip_similarity": round(clip_sim, 4),
                    "dna_score": round(dnaq[cid], 4),
                    "visual_score": round(visq[cid], 4),
                    "diversity_score": round(div[cid] / 100.0, 4),
                    "final_score": round(final, 4),
                }
            )

        rows.sort(key=lambda r: -r["final_score"])
        top = rows[:top_k]

        comp_counts = Counter(c["dna"].get("composition", "?") for c in creatives)
        return {
            "clip_mode": clip.mode,
            "top_k": top_k,
            "composition_clusters": len(comp_counts),
            "composition_distribution": dict(comp_counts),
            "candidates": top,
            "all_scores": rows,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _dna_quality(base: dict[str, Any], dna: dict[str, Any]) -> int:
        q = 60
        if dna.get("character") == base["character"]:
            q += 12
        if dna.get("color") == base["color"]:
            q += 10
        if dna.get("hook") == base["hook"]:
            q += 8
        tier = _REWARD_TIER.get(dna.get("reward", ""), 1)
        q += min(10, tier * 3)
        return max(0, min(100, q))

    @staticmethod
    def _visual_quality(dna: dict[str, Any]) -> int:
        q = 70
        if dna.get("composition") in _GOOD_COMPOSITIONS:
            q += 10
        if dna.get("color"):
            q += 8
        if dna.get("background"):
            q += 7
        if dna.get("reward"):
            q += 5
        return max(0, min(100, q))

    @staticmethod
    def _diversity(creatives: list[dict[str, Any]]) -> dict[str, int]:
        comps = [c["dna"].get("composition", "?") for c in creatives]
        cnt = Counter(comps)
        maxc = max(cnt.values()) if cnt else 1
        out: dict[str, int] = {}
        for c in creatives:
            comp = c["dna"].get("composition", "?")
            out[c["creative_id"]] = round(100 * (maxc - cnt[comp] + 1) / maxc)
        return out
