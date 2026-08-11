"""
E15.2.5 — MAX Config Recommender (Autonomous IAA Optimization, increment 1).

Turns raw MAX Report rows into a per-(app, geo, format) TARGET MAX CONFIG:
  * recommended network priority order (ranked by eCPM x fill)
  * demote candidates (parasite backfill networks dragging the blend)
  * per-network bid-floor / price-floor range suggestions

This is the "Waterfall / Bidding auto-optimization" half of the user's P0.
It is RECOMMENDATION-ONLY: the operator applies the target config manually
in the MAX dashboard (MAX Management API forbids writes on expanded-targeting
waterfalls — PATCH 403/422). Floor suggestions reuse BidFloorAdvisor so there
is a single source of truth; the network-ranking order is the new output.

Deterministic rules, no LLM, no MAX writes.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, Dict, List, Optional

from operation.optimizer.intel_models import SegmentStat
from operation.optimizer.analyzers.bid_floor_advisor import BidFloorAdvisor


@dataclass
class NetworkRank:
    """One network's standing inside a single (app, geo, format) segment."""
    network: str
    ecpm: float
    fill_rate: float          # responses / attempts
    impression_share: float   # this network / segment impressions
    revenue: float
    score: float              # eCPM x fill — ranking proxy
    rank: int                 # 1 = top priority

    def to_dict(self) -> Dict[str, Any]:
        return {
            "network": self.network, "ecpm": round(self.ecpm, 2),
            "fill_rate": round(self.fill_rate, 4),
            "impression_share": round(self.impression_share, 4),
            "revenue": round(self.revenue, 2),
            "score": round(self.score, 4), "rank": self.rank,
        }


@dataclass
class SegmentConfig:
    """Recommended MAX config for one (app, geo, format) segment."""
    app: str
    geo: str
    ad_format: str
    segment_blend_ecpm: float
    segment_impressions: int
    networks: List[NetworkRank] = field(default_factory=list)
    recommended_order: List[str] = field(default_factory=list)
    demote_candidates: List[str] = field(default_factory=list)
    floor_suggestions: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app": self.app, "geo": self.geo, "ad_format": self.ad_format,
            "segment_blend_ecpm": round(self.segment_blend_ecpm, 2),
            "segment_impressions": self.segment_impressions,
            "networks": [n.to_dict() for n in self.networks],
            "recommended_order": self.recommended_order,
            "demote_candidates": self.demote_candidates,
            "floor_suggestions": self.floor_suggestions,
        }


@dataclass
class AccountConfigRecommendation:
    """Full Target MAX Config artifact for one account over a period."""
    account: str
    period_start: str
    period_end: str
    generated_at: str
    overall_blend_ecpm: float = 0.0
    segments: List[SegmentConfig] = field(default_factory=list)

    @property
    def n_segments(self) -> int:
        return len(self.segments)

    @property
    def n_demote(self) -> int:
        return sum(len(s.demote_candidates) for s in self.segments)

    @property
    def n_floor(self) -> int:
        return sum(len(s.floor_suggestions) for s in self.segments)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account": self.account,
            "period": {"start": self.period_start, "end": self.period_end},
            "generated_at": self.generated_at,
            "overall_blend_ecpm": round(self.overall_blend_ecpm, 2),
            "summary": {"segments": self.n_segments,
                        "demote_candidates": self.n_demote,
                        "floor_suggestions": self.n_floor},
            "segments": [s.to_dict() for s in self.segments],
        }


class ConfigRecommender:
    """Builds a Target MAX Config recommendation from raw report rows.

    Grouping: rows -> (app, geo, ad_format) -> per-network SegmentStat.
    Ranking score: eCPM x fill_rate (high eCPM with real fill ranks first).
    """

    MIN_SEGMENT_IMPRESSIONS = 200      # ignore thin segments (noisy ranking)
    ECPM_PARASITE_RATIO = 0.15        # mirror BidFloorAdvisor threshold
    MIN_IMPRESSION_SHARE = 0.03

    def __init__(self) -> None:
        self._floor = BidFloorAdvisor()   # single source of truth for floors

    # ------------------------------------------------------------------ #
    def recommend(self, rows: List[dict], account: str,
                  period_start: str, period_end: str,
                  overall_blend_ecpm: float = 0.0,
                  today: Optional[str] = None) -> AccountConfigRecommendation:
        # group (app, geo, format, network) -> SegmentStat
        seg: Dict[tuple, Dict[str, SegmentStat]] = {}
        total_rev = 0.0
        total_imp = 0
        for r in rows:
            app = r.get("application") or "?"
            geo = (r.get("country") or "?").lower()
            fmt = r.get("ad_format") or "?"
            net = r.get("network") or "?"
            rev = float(r.get("estimated_revenue") or 0.0)
            imp = int(float(r.get("impressions") or 0))
            att = int(float(r.get("attempts") or 0))
            resp = int(float(r.get("responses") or 0))
            total_rev += rev
            total_imp += imp
            key = (app, geo, fmt)
            netmap = seg.setdefault(key, {})
            st = netmap.get(net)
            if st is None:
                st = SegmentStat(key=net)
                netmap[net] = st
            st.revenue += rev
            st.impressions += imp
            st.attempts += att
            st.responses += resp
            st.days = max(st.days, 1)

        rec = AccountConfigRecommendation(
            account=account, period_start=period_start, period_end=period_end,
            generated_at=today or _date.today().isoformat(),
            overall_blend_ecpm=overall_blend_ecpm or (
                total_rev / total_imp * 1000.0 if total_imp else 0.0),
        )
        # Parasite / floor benchmark = ACCOUNT-level blend (same source of
        # truth as BidFloorAdvisor in the daily report). A network is a
        # floor/demote candidate when its eCPM is far below the account
        # benchmark while still taking meaningful impression share *within
        # this segment* -- so the operator knows which (app,geo,format)
        # segments to apply the change in.
        blend = rec.overall_blend_ecpm

        for (app, geo, fmt), netmap in seg.items():
            seg_imp = sum(s.impressions for s in netmap.values())
            if seg_imp < self.MIN_SEGMENT_IMPRESSIONS:
                continue
            seg_blend = (sum(s.revenue for s in netmap.values())
                         / seg_imp * 1000.0) if seg_imp else 0.0

            # rank networks by eCPM x fill
            ranks: List[NetworkRank] = []
            for net, s in netmap.items():
                if s.impressions <= 0:
                    continue
                fill = s.fill_rate
                score = s.ecpm * fill
                ranks.append(NetworkRank(
                    network=net, ecpm=s.ecpm, fill_rate=fill,
                    impression_share=s.impressions / seg_imp,
                    revenue=s.revenue, score=score, rank=0))
            ranks.sort(key=lambda n: -n.score)
            for i, n in enumerate(ranks, 1):
                n.rank = i
            recommended_order = [n.network for n in ranks]

            # demote candidates: parasite backfill (mirror BidFloorAdvisor,
            # benchmarked on the account blend)
            demote: List[str] = []
            for n in ranks:
                if (n.ecpm < blend * self.ECPM_PARASITE_RATIO
                        and n.impression_share >= self.MIN_IMPRESSION_SHARE):
                    demote.append(n.network)

            # floor suggestions reuse BidFloorAdvisor (account blend) so the
            # config artifact stays consistent with the daily report.
            floor_signals = self._floor.analyze(netmap, blend, seg_imp)
            floor_sugg: Dict[str, Dict[str, Any]] = {}
            for sig in floor_signals:
                rng = sig.metrics.get(
                    "recommended_floor_range",
                    [sig.metrics["recommended_min_floor"]] * 2)
                floor_sugg[sig.target] = {
                    "constraint_type": sig.metrics.get("constraint_type"),
                    "recommended_floor_range": [round(x, 2) for x in rng],
                    "ecpm": round(sig.metrics.get("ecpm", 0.0), 2),
                    "impression_share": sig.metrics.get("impression_share"),
                    "requires_manual_apply": True,
                }

            rec.segments.append(SegmentConfig(
                app=app, geo=geo, ad_format=fmt,
                segment_blend_ecpm=seg_blend, segment_impressions=seg_imp,
                networks=ranks, recommended_order=recommended_order,
                demote_candidates=demote, floor_suggestions=floor_sugg))

        # stable order: biggest segments first
        rec.segments.sort(key=lambda s: -s.segment_impressions)
        return rec

    # ------------------------------------------------------------------ #
    def render_markdown(self, rec: AccountConfigRecommendation) -> str:
        lines = [
            f"# Target MAX Config — {rec.account}",
            "",
            f"**Period:** {rec.period_start} → {rec.period_end}",
            f"  |  **Overall blend eCPM:** ${rec.overall_blend_ecpm:.2f}",
            f"  |  **Segments:** {rec.n_segments} "
            f"(demote {rec.n_demote}, floor {rec.n_floor})",
            "",
            "> Recommendation-only. MAX Management API cannot write "
            "expanded-targeting waterfalls — apply this target config "
            "manually in the MAX dashboard, then let the Experiment Layer "
            "verify the revenue/fill impact.",
            "",
        ]
        for s in rec.segments:
            lines += [
                f"## {s.app} · {s.geo} · {s.ad_format}",
                f"_blend eCPM ${s.segment_blend_ecpm:.2f} · "
                f"{s.segment_impressions:,} imp_",
                "",
                "**Recommended network priority (top → bottom):**",
            ]
            for n in s.networks:
                tag = " ⬇️ demote" if n.network in s.demote_candidates else ""
                fl = s.floor_suggestions.get(n.network)
                ftag = (f" · floor ${fl['recommended_floor_range'][0]:.2f}"
                        f"-${fl['recommended_floor_range'][1]:.2f}"
                        ) if fl else ""
                lines.append(
                    f"{n.rank}. **{n.network}** — eCPM ${n.ecpm:.2f} · "
                    f"fill {n.fill_rate:.1%} · share {n.impression_share:.1%}"
                    f"{tag}{ftag}")
            lines.append("")
        return "\n".join(lines)

    def save(self, rec: AccountConfigRecommendation,
             out_dir: str = "outputs/config_recommendations") -> Dict[str, str]:
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.join(out_dir, f"{rec.account}_{rec.period_end}")
        md_path, json_path = base + ".md", base + ".json"
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(self.render_markdown(rec))
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(rec.to_dict(), fh, ensure_ascii=False, indent=2)
        return {"markdown": md_path, "json": json_path}
