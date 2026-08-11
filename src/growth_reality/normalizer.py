"""E17.1 Growth Reality Hub — 归一化层（P1.4 真实覆盖感知）。

把 collector 产出的原始 domain dict 转成强类型 Fact，并补派生指标：
- arpdau = daily_revenue / dau（当 revenue 未直接给出且 product.dau>0）
- roas    = daily_revenue * 30 / spend（仅当收入与花费均为真实源时计算，P1.4）
- organic/paid 分解：启发式（见 RealityAttribution），仅真实配对时给出

P1.4 关键硬化：
- `real_domains`（collector 标记的真实源域）驱动 `real_confidence`；
  当存在真实域时，`confidence` 取真实覆盖度（避免 SIM 假数据虚高），
  纯 SIM 时回退到全量覆盖度（向后兼容 SIM 演示/旧测试）。
- ROAS 仅在「收入真实 且 花费真实」时计算；否则置 0（不臆造）。
- 同时真实收入+花费才产出 `RealityAttribution`（有机 vs 付费估计）。

缺失字段按 0 填充；不做任何 LLM 推断。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    AcquisitionFact,
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    ProductFact,
    RealityAttribution,
    RevenueFact,
)

_VALID = ("revenue", "acquisition", "aso", "creative", "product")


class RealityNormalizer:
    def normalize_game(
        self, game_id: str, as_of: str, raw: Dict[str, Any]
    ) -> GrowthRealitySnapshot:
        domains = raw.get("domains", {})
        real_domains: List[str] = [
            d for d in raw.get("real_domains", []) if d in _VALID
        ]
        real_set = set(real_domains)

        revenue = self._rev(domains.get("revenue"))
        acquisition = self._acq(domains.get("acquisition"))
        aso = self._aso(domains.get("aso"))
        creative = self._creative(domains.get("creative"))
        product = self._prod(domains.get("product"))

        # --- 派生指标 ---
        if revenue and product and product.dau > 0 and revenue.arpdau == 0.0:
            # 重算 arpdau，但保留 MAX / IAA 原生变现字段（网络分布、ecpm、
            # 激励视频收入、曝光等），否则在「Adjust IAP + MAX 广告」共存时会被
            # 整段清零（Adjust revenue bundle 恒 arpdau=0.0，每次都会触发此分支）。
            revenue = RevenueFact(
                daily_revenue=revenue.daily_revenue,
                payer_count=revenue.payer_count,
                arpdau=revenue.daily_revenue / product.dau,
                ltv=revenue.ltv,
                impressions=revenue.impressions,
                requests=revenue.requests,
                ecpm=revenue.ecpm,
                rewarded_video_revenue=revenue.rewarded_video_revenue,
                network_distribution=revenue.network_distribution,
            )

        # P1.4：ROAS 仅当收入与花费均来自真实源时计算
        rev_real = revenue is not None and "revenue" in real_set
        acq_real = acquisition is not None and "acquisition" in real_set
        attribution: Optional[RealityAttribution] = None
        if (
            acquisition
            and revenue
            and acquisition.roas == 0.0
            and acquisition.spend > 0
            and rev_real
            and acq_real
        ):
            monthly_rev = revenue.daily_revenue * 30.0
            roas = monthly_rev / acquisition.spend
            paid_share = min(1.0, acquisition.spend / monthly_rev) if monthly_rev > 0 else 0.0
            acquisition = AcquisitionFact(
                spend=acquisition.spend,
                installs=acquisition.installs,
                cpi=acquisition.cpi,
                roas=roas,
            )
            attribution = RealityAttribution(
                roas=roas,
                paid_share_est=round(paid_share, 4),
                organic_share_est=round(1.0 - paid_share, 4),
                method="heuristic_revenue_minus_spend",
                is_real=True,
            )

        covered = [f for f in (revenue, acquisition, aso, creative, product) if f]
        total_cov = len(covered) / 5.0 if covered else 0.0
        real_cov = len(real_set) / 5.0

        # 存在真实域 → 置信度按真实覆盖度（防止 SIM 虚高）；
        # 纯 SIM → 回退全量覆盖度（向后兼容 SIM 演示）
        confidence = real_cov if real_domains else total_cov

        return GrowthRealitySnapshot(
            game_id=game_id,
            timestamp=as_of,
            revenue=revenue,
            acquisition=acquisition,
            aso=aso,
            creative=creative,
            product=product,
            confidence=confidence,
            sources=raw.get("sources", []),
            real_confidence=real_cov,
            real_domains=real_domains,
            attribution=attribution,
        )

    # -- 单域解析（缺失即 None） --
    @staticmethod
    def _rev(d: Optional[Dict[str, Any]]) -> Optional[RevenueFact]:
        if not d:
            return None
        nd = d.get("network_distribution") or {}
        return RevenueFact(
            daily_revenue=float(d.get("daily_revenue", 0.0)),
            payer_count=int(d.get("payer_count", 0)),
            arpdau=float(d.get("arpdau", 0.0)),
            ltv=float(d.get("ltv", 0.0)),
            # P1.2：MAX / IAA 原生变现指标（源已算好，原样透传）
            impressions=int(d.get("impressions", 0)),
            requests=int(d.get("requests", 0)),
            ecpm=float(d.get("ecpm", 0.0)),
            rewarded_video_revenue=float(d.get("rewarded_video_revenue", 0.0)),
            network_distribution=dict(nd) if isinstance(nd, dict) else {},
        )

    @staticmethod
    def _acq(d: Optional[Dict[str, Any]]) -> Optional[AcquisitionFact]:
        if not d:
            return None
        return AcquisitionFact(
            spend=float(d.get("spend", 0.0)),
            installs=int(d.get("installs", 0)),
            cpi=float(d.get("cpi", 0.0)),
            roas=float(d.get("roas", 0.0)),
        )

    @staticmethod
    def _aso(d: Optional[Dict[str, Any]]) -> Optional[AsoFact]:
        if not d:
            return None
        return AsoFact(
            ranking=int(d.get("ranking", 0)),
            store_cvr=float(d.get("store_cvr", 0.0)),
            rating=float(d.get("rating", 0.0)),
            review_velocity=float(d.get("review_velocity", 0.0)),
        )

    @staticmethod
    def _creative(d: Optional[Dict[str, Any]]) -> Optional[CreativeFact]:
        if not d:
            return None
        return CreativeFact(
            ctr=float(d.get("ctr", 0.0)),
            fatigue_score=float(d.get("fatigue_score", 0.0)),
            creative_score=float(d.get("creative_score", 0.0)),
        )

    @staticmethod
    def _prod(d: Optional[Dict[str, Any]]) -> Optional[ProductFact]:
        if not d:
            return None
        return ProductFact(
            dau=int(d.get("dau", 0)),
            retention=float(d.get("retention", 0.0)),
            conversion=float(d.get("conversion", 0.0)),
        )
