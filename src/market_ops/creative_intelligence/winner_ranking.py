"""P04 IAP Creative Winner Ranking System V2

从单一 iap_score 排序升级为多维度综合评估：
  - Revenue Quality (40%) : 真实收入能力
  - Scale Confidence (25%): 放量置信度（避免小样本）
  - User Value (20%)      : 用户质量
  - Hook Score (15%)      : 素材吸引力

输出多种 Winner 类型，供不同策略场景使用。
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class WinnerRankItem:
    creative_id: str
    cdn_url: str
    visual_dna: dict[str, Any]
    # Raw metrics
    iap_score: float = 0.0
    spend: float = 0.0
    installs: int = 0
    ctr: float = 0.0
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    roas_d60: float = 0.0
    roas_d120: float = 0.0
    purchase_rate: float = 0.0
    cpi_rate: float = 0.0
    # Computed scores
    revenue_quality: float = 0.0
    scale_confidence: float = 0.0
    user_value: float = 0.0
    hook_score: float = 0.0
    winner_score: float = 0.0


@dataclass(slots=True)
class WinnerRankingV2:
    total_winners: int = 0
    ranked: list[WinnerRankItem] = field(default_factory=list)
    # Typed winners
    revenue_winner: dict[str, Any] = field(default_factory=dict)
    scale_winner: dict[str, Any] = field(default_factory=dict)
    hook_winner: dict[str, Any] = field(default_factory=dict)
    balanced_winner: dict[str, Any] = field(default_factory=dict)
    iap_intent_winner: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ranking Engine
# ---------------------------------------------------------------------------
class WinnerRankingEngine:
    """Multi-dimensional winner ranking for IAP game creatives."""

    # Weights for composite winner_score
    W_REVENUE = 0.40
    W_SCALE = 0.25
    W_USER = 0.20
    W_HOOK = 0.15

    def __init__(self, dna_path: Path | str | None = None) -> None:
        self._dna_path = Path(dna_path) if dna_path else None

    # ----- public API -----

    def rank(self, dna_path: Path | str | None = None) -> WinnerRankingV2:
        """Load winner DNA and compute V2 ranking."""
        path = Path(dna_path) if dna_path else self._dna_path
        if not path:
            raise ValueError("No DNA path provided")

        raw = json.loads(path.read_text(encoding="utf-8"))
        items = self._parse_items(raw)

        # Compute sub-scores
        for item in items:
            item.revenue_quality = self._calc_revenue_quality(item)
            item.scale_confidence = self._calc_scale_confidence(item)
            item.user_value = self._calc_user_value(item)
            item.hook_score = self._calc_hook_score(item)
            item.winner_score = (
                self.W_REVENUE * item.revenue_quality
                + self.W_SCALE * item.scale_confidence
                + self.W_USER * item.user_value
                + self.W_HOOK * item.hook_score
            )

        # Sort by composite winner_score descending
        items.sort(key=lambda x: x.winner_score, reverse=True)

        # Pick typed winners
        revenue_winner = max(items, key=lambda x: x.revenue_quality)
        scale_winner = max(items, key=lambda x: x.scale_confidence)
        hook_winner = max(items, key=lambda x: x.hook_score)
        balanced_winner = items[0]  # highest composite
        iap_intent_winner = max(items, key=lambda x: x.user_value)

        return WinnerRankingV2(
            total_winners=len(items),
            ranked=items,
            revenue_winner=self._winner_dict(revenue_winner, "revenue"),
            scale_winner=self._winner_dict(scale_winner, "scale"),
            hook_winner=self._winner_dict(hook_winner, "hook"),
            balanced_winner=self._winner_dict(balanced_winner, "balanced"),
            iap_intent_winner=self._winner_dict(iap_intent_winner, "iap_intent"),
        )

    def save(self, ranking: WinnerRankingV2, output_path: Path | str) -> Path:
        """Save ranking result to JSON."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "total_winners": ranking.total_winners,
            "revenue_winner": ranking.revenue_winner,
            "scale_winner": ranking.scale_winner,
            "hook_winner": ranking.hook_winner,
            "balanced_winner": ranking.balanced_winner,
            "iap_intent_winner": ranking.iap_intent_winner,
            "top_10": [
                {
                    "rank": i + 1,
                    "creative_id": item.creative_id,
                    "winner_score": round(item.winner_score, 4),
                    "revenue_quality": round(item.revenue_quality, 4),
                    "scale_confidence": round(item.scale_confidence, 4),
                    "user_value": round(item.user_value, 4),
                    "hook_score": round(item.hook_score, 4),
                    "spend": item.spend,
                    "installs": item.installs,
                    "ctr": item.ctr,
                    "roas_d7": item.roas_d7,
                    "iap_score": item.iap_score,
                }
                for i, item in enumerate(ranking.ranked[:10])
            ],
            "all_ranked": [
                {
                    "rank": i + 1,
                    "creative_id": item.creative_id,
                    "winner_score": round(item.winner_score, 4),
                    "revenue_quality": round(item.revenue_quality, 4),
                    "scale_confidence": round(item.scale_confidence, 4),
                    "user_value": round(item.user_value, 4),
                    "hook_score": round(item.hook_score, 4),
                    "spend": item.spend,
                    "installs": item.installs,
                    "ctr": item.ctr,
                    "roas_d7": item.roas_d7,
                    "iap_score": item.iap_score,
                }
                for i, item in enumerate(ranking.ranked)
            ],
        }
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out

    # ----- internal -----

    def _parse_items(self, raw: list[dict[str, Any]]) -> list[WinnerRankItem]:
        items: list[WinnerRankItem] = []
        for entry in raw:
            cdn_url = entry.get("_cdn_url", "").strip()
            if not cdn_url:
                continue
            items.append(WinnerRankItem(
                creative_id=entry.get("creative_id", ""),
                cdn_url=cdn_url,
                visual_dna={
                    "subject": entry.get("subject", ""),
                    "composition": entry.get("composition", ""),
                    "palette": entry.get("palette", ""),
                    "lighting": entry.get("lighting", ""),
                    "overlay_text": entry.get("overlay_text", ""),
                    "character_pose": entry.get("character_pose", ""),
                    "mood": entry.get("mood", ""),
                    "hook_type": entry.get("hook_type", "collection"),
                    "standout_features": entry.get("standout_features", []),
                    "overall_summary": entry.get("overall_summary", ""),
                },
                iap_score=float(entry.get("iap_score") or 0),
                spend=float(entry.get("spend") or 0),
                installs=int(entry.get("installs") or 0),
                ctr=float(entry.get("ctr") or 0),
                roas_d7=float(entry.get("roas_d7") or 0),
                roas_d30=float(entry.get("roas_d30") or 0),
                roas_d60=float(entry.get("roas_d60") or 0),
                roas_d120=float(entry.get("roas_d120") or 0),
                purchase_rate=float(entry.get("purchase_rate") or 0),
                cpi_rate=float(entry.get("cpi_rate") or 0),
            ))
        return items

    def _calc_revenue_quality(self, item: WinnerRankItem) -> float:
        """Revenue Quality = weighted ROAS over time.

        Prefer: roas_d30 > roas_d60 > roas_d120
        Fallback: roas_d7
        """
        if item.roas_d30 > 0:
            return min(
                0.5 * item.roas_d30
                + 0.3 * (item.roas_d60 if item.roas_d60 > 0 else item.roas_d30)
                + 0.2 * (item.roas_d120 if item.roas_d120 > 0 else item.roas_d30),
                2.0,  # cap at 2.0 to prevent extreme outliers from dominating
            )
        # Fallback: use roas_d7 if no longer-term data
        if item.roas_d7 > 0:
            return min(item.roas_d7, 2.0)
        return 0.0

    def _calc_scale_confidence(self, item: WinnerRankItem) -> float:
        """Scale Confidence = log10(spend) normalized.

        Spend < $500   → low confidence
        $500-$3000     → normal
        >$3000         → highest confidence
        """
        spend = max(item.spend, 1.0)
        return min(math.log10(spend + 1) / 4.0, 1.0)

    def _calc_user_value(self, item: WinnerRankItem) -> float:
        """User Value = purchase_rate if available, else iap_score."""
        if item.purchase_rate > 0:
            return min(item.purchase_rate, 1.0)
        return min(item.iap_score, 1.0)

    def _calc_hook_score(self, item: WinnerRankItem) -> float:
        """Hook Score = normalized CTR.

        Typical game ad CTR range: 0.5% - 2.0%
        Normalize to 0-1 scale.
        """
        if item.ctr <= 0:
            return 0.0
        # Normalize: 2.0% CTR = 1.0 score, linear below
        return min(item.ctr / 2.0, 1.0)

    def _winner_dict(self, item: WinnerRankItem, winner_type: str) -> dict[str, Any]:
        return {
            "creative_id": item.creative_id,
            "cdn_url": item.cdn_url,
            "winner_type": winner_type,
            "score": round(item.winner_score, 4),
            "revenue_quality": round(item.revenue_quality, 4),
            "scale_confidence": round(item.scale_confidence, 4),
            "user_value": round(item.user_value, 4),
            "hook_score": round(item.hook_score, 4),
            "spend": item.spend,
            "installs": item.installs,
            "ctr": item.ctr,
            "roas_d7": item.roas_d7,
            "iap_score": item.iap_score,
            "visual_dna_summary": {
                "subject": item.visual_dna.get("subject", ""),
                "palette": item.visual_dna.get("palette", ""),
                "overlay_text": item.visual_dna.get("overlay_text", ""),
                "mood": item.visual_dna.get("mood", ""),
            },
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    import sys

    root = Path(__file__).resolve().parent.parent.parent.parent
    dna_path = root / "output" / "creative_analysis" / "dna_cache" / "winners_dna.json"
    output_path = root / "output" / "creative_analysis" / "winner_ranking_v2.json"

    if not dna_path.exists():
        print(f"[ERROR] Winner DNA not found: {dna_path}")
        return 1

    engine = WinnerRankingEngine()
    ranking = engine.rank(dna_path)
    engine.save(ranking, output_path)

    print("=" * 60)
    print("  Winner Ranking V2 Complete")
    print("=" * 60)
    print(f"\n  Total Winners : {ranking.total_winners}")
    print(f"\n  🏆 Balanced Winner    : {ranking.balanced_winner.get('creative_id', 'N/A')}")
    print(f"     Score={ranking.balanced_winner.get('score', 0):.4f}")
    print(f"\n  💰 Revenue Winner     : {ranking.revenue_winner.get('creative_id', 'N/A')}")
    print(f"     Score={ranking.revenue_winner.get('score', 0):.4f}")
    print(f"\n  📈 Scale Winner       : {ranking.scale_winner.get('creative_id', 'N/A')}")
    print(f"     Score={ranking.scale_winner.get('score', 0):.4f}")
    print(f"\n  🪝 Hook Winner        : {ranking.hook_winner.get('creative_id', 'N/A')}")
    print(f"     Score={ranking.hook_winner.get('score', 0):.4f}")
    print(f"\n  🎯 IAP Intent Winner  : {ranking.iap_intent_winner.get('creative_id', 'N/A')}")
    print(f"     Score={ranking.iap_intent_winner.get('score', 0):.4f}")
    print(f"\n  Output: {output_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
