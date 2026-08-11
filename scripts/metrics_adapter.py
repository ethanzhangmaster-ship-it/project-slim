"""指标适配层 (接线 3) — 将多源数据统一为 creative 级 current_metrics。

核心问题:
  七域快照 (parallel_analyze) 和 PlayerProfile 是产品侧/玩家侧数据,
  维度为 app/channel/segment/player, 不含 creative 级别。
  而 GrowthLoopOrchestrator 期望 {creative_id: {spend, ctr, cpi, ...}}。

适配策略:
  1. 广告平台数据 (aggregate_by_creative) 是主源, 提供 8 个核心字段
  2. 产品侧数据 (七域快照 + PlayerProfile) 是富集源:
     - 用真实 revenue (IAP+IAA) 校验广告侧反推的 revenue
     - 用真实 installs 校验广告侧反推的 installs
     - 附加上下文 (留存/LTV/ARPU) 到 _context 字段

输出契约 (与 DiagnosticEngine._build_snapshot 对齐):
  {creative_id: {
      "spend": float, "clicks": float, "ctr": float, "cpi": float,
      "roas": float, "impressions": float, "installs": float, "revenue": float,
      "_context": {  # 可选, 产品侧上下文 (DiagnosticEngine 忽略)
          "d1_retention": float, "d7_retention": float,
          "arpu": float, "ltv_d7": float,
          "payer_rate": float, "iaa_revenue": float,
          ...
      }
  }}

  注意: spend 和 ctr 至少一个非零, 否则诊断降级为 undiagnosed。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 富集结果数据模型
# ──────────────────────────────────────────────


@dataclass
class EnrichmentReport:
    """适配层富集报告 — 记录校验和替换情况。"""

    total_creatives: int = 0
    revenue_enriched: int = 0       # 用产品侧真实收入替换了广告侧反推值
    installs_enriched: int = 0      # 用产品侧真实 installs 校验/替换
    context_added: int = 0          # 附加了产品上下文的 creative 数
    revenue_discrepancies: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_creatives": self.total_creatives,
            "revenue_enriched": self.revenue_enriched,
            "installs_enriched": self.installs_enriched,
            "context_added": self.context_added,
            "revenue_discrepancies": self.revenue_discrepancies,
        }


# ──────────────────────────────────────────────
# MetricsAdapter 核心
# ──────────────────────────────────────────────


class MetricsAdapter:
    """指标适配层 — 多源数据 → creative 级 current_metrics。

    Usage:
        adapter = MetricsAdapter()
        metrics = adapter.adapt(
            ads_metrics=aggregate_by_creative(rows),
            seven_domain_snapshots=parallel_analyze(td, project_id),
            player_profiles=collector.collect(app_id, start, end),
            creative_attribution={user_id: creative_id},
        )
        # metrics 可直接传入 GrowthLoopOrchestrator.run_cycle(current_metrics=...)
    """

    # revenue 校验阈值: 广告侧 vs 产品侧偏差超过此值时记录 discrepancy
    REVENUE_DISCREPANCY_THRESHOLD = 0.30  # 30%

    def adapt(
        self,
        ads_metrics: dict[str, dict[str, float]],
        seven_domain_snapshots: dict[str, Any] | None = None,
        player_profiles: list[Any] | None = None,
        creative_attribution: dict[str, str] | None = None,
    ) -> tuple[dict[str, dict[str, float]], EnrichmentReport]:
        """适配多源数据为 creative 级 current_metrics。

        Args:
            ads_metrics: 广告平台数据 (aggregate_by_creative 输出)
                {creative_id: {spend, clicks, ctr, cpi, roas, impressions, installs, revenue}}
            seven_domain_snapshots: 七域快照 (parallel_analyze 输出)
                {domain_name: Snapshot} — 用于提取产品上下文
            player_profiles: PlayerProfile 列表 — 用于 IAA revenue 聚合
            creative_attribution: user_id → creative_id 归因映射
                (将玩家级 IAA 收入归因到 creative)

        Returns:
            (adapted_metrics, report)
            - adapted_metrics: {creative_id: {8字段 + _context}}
            - report: EnrichmentReport
        """
        report = EnrichmentReport(total_creatives=len(ads_metrics))

        # Step 1: 以广告侧为主源, 深拷贝
        adapted: dict[str, dict[str, float]] = {}
        for cid, metrics in ads_metrics.items():
            adapted[cid] = dict(metrics)

        # Step 2: 用产品侧真实收入富集 revenue
        if seven_domain_snapshots or player_profiles:
            self._enrich_revenue(
                adapted, seven_domain_snapshots,
                player_profiles, creative_attribution, report,
            )

        # Step 3: 用产品侧真实 installs 校验
        if seven_domain_snapshots:
            self._enrich_installs(adapted, seven_domain_snapshots, report)

        # Step 4: 附加产品上下文
        if seven_domain_snapshots:
            self._add_context(adapted, seven_domain_snapshots, report)

        logger.info(
            "MetricsAdapter: adapted %d creatives "
            "(revenue_enriched=%d, installs_enriched=%d, context_added=%d)",
            report.total_creatives, report.revenue_enriched,
            report.installs_enriched, report.context_added,
        )

        return adapted, report

    # ──────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────

    def _enrich_revenue(
        self,
        metrics: dict[str, dict[str, float]],
        snapshots: dict[str, Any] | None,
        profiles: list[Any] | None,
        attribution: dict[str, str] | None,
        report: EnrichmentReport,
    ) -> None:
        """用产品侧真实收入 (IAP + IAA) 富集 revenue。

        广告侧 revenue = spend * roas (循环推导), 产品侧有真实收入:
        - IAP: MonetizationSnapshot.total_revenue
        - IAA: PlayerProfile.total_ad_revenue 聚合

        策略: 将产品侧真实收入按 creative 分摊, 替换广告侧反推值。
        分摊方式: 按 creative 的 spend 占比分摊 IAP, 按归因分摊 IAA。
        """
        if not metrics:
            return

        # 提取 IAP 总收入 (app 级)
        iap_revenue = 0.0
        if snapshots:
            monetization = snapshots.get("Monetization")
            if monetization and hasattr(monetization, "total_revenue"):
                iap_revenue = monetization.total_revenue or 0.0

        # 聚合 IAA 收入并按 creative 归因
        iaa_by_creative: dict[str, float] = {}
        total_iaa = 0.0
        if profiles and attribution:
            for profile in profiles:
                uid = getattr(profile, "user_id", "")
                ad_rev = getattr(profile, "total_ad_revenue", 0.0)
                cid = attribution.get(uid, "")
                if cid and cid in metrics:
                    iaa_by_creative[cid] = (
                        iaa_by_creative.get(cid, 0.0) + ad_rev
                    )
                total_iaa += ad_rev

        # 无任何产品侧收入数据 → 跳过
        if iap_revenue == 0 and total_iaa == 0:
            return

        # 按 spend 占比分摊 IAP 到各 creative
        total_spend = sum(m.get("spend", 0.0) for m in metrics.values())
        iap_by_creative: dict[str, float] = {}
        if iap_revenue > 0 and total_spend > 0:
            for cid, m in metrics.items():
                spend = m.get("spend", 0.0)
                iap_by_creative[cid] = iap_revenue * (spend / total_spend)

        # 合并 IAP + IAA → 真实收入, 替换广告侧反推值
        for cid, m in metrics.items():
            ads_revenue = m.get("revenue", 0.0)
            real_revenue = iap_by_creative.get(cid, 0.0) + iaa_by_creative.get(cid, 0.0)

            if real_revenue <= 0:
                continue

            # 记录偏差
            if ads_revenue > 0:
                discrepancy = abs(real_revenue - ads_revenue) / ads_revenue
                if discrepancy > self.REVENUE_DISCREPANCY_THRESHOLD:
                    report.revenue_discrepancies.append({
                        "creative_id": cid,
                        "ads_revenue": round(ads_revenue, 2),
                        "real_revenue": round(real_revenue, 2),
                        "discrepancy": round(discrepancy, 3),
                    })

            # 用真实收入替换, 并重新计算 roas
            m["revenue"] = round(real_revenue, 4)
            spend = m.get("spend", 0.0)
            if spend > 0:
                m["roas"] = round(real_revenue / spend, 4)

            report.revenue_enriched += 1

    def _enrich_installs(
        self,
        metrics: dict[str, dict[str, float]],
        snapshots: dict[str, Any],
        report: EnrichmentReport,
    ) -> None:
        """用产品侧真实 installs 校验广告侧反推的 installs。

        广告侧 installs = spend / cpi (反推), 产品侧有:
        - FunnelSnapshot.steps[0].entered (安装步进入人数)
        - RetentionSnapshot.channel_retention[].installs (按渠道)

        策略: 仅记录偏差, 不替换 (广告侧 installs 与归因口径更一致)。
        """
        funnel = snapshots.get("Funnel")
        if not funnel or not hasattr(funnel, "steps") or not funnel.steps:
            return

        # 取第一个 step (安装) 的 entered 作为 app 级真实 installs
        real_installs = funnel.steps[0].entered or 0
        if real_installs <= 0:
            return

        # 计算广告侧总 installs
        total_ads_installs = sum(m.get("installs", 0.0) for m in metrics.values())
        if total_ads_installs <= 0:
            return

        # 记录总体偏差 (不替换单个 creative 的 installs)
        discrepancy = abs(real_installs - total_ads_installs) / max(total_ads_installs, 1)
        if discrepancy > self.REVENUE_DISCREPANCY_THRESHOLD:
            logger.info(
                "Installs discrepancy: ads=%d vs real=%d (%.1f%%)",
                total_ads_installs, real_installs, discrepancy * 100,
            )

        report.installs_enriched += 1

    def _add_context(
        self,
        metrics: dict[str, dict[str, float]],
        snapshots: dict[str, Any],
        report: EnrichmentReport,
    ) -> None:
        """从七域快照提取产品上下文, 附加到每个 creative 的 _context 字段。

        上下文字段 (DiagnosticEngine 会忽略 _ 开头的字段):
        - d1_retention, d7_retention, d30_retention (Lifecycle)
        - arpu, arppu, payer_rate (Monetization)
        - ltv_d7, ltv_d30 (Monetization)
        - d1_retention_by_channel (Retention, 如果有 meta 渠道)
        - avg_value_score (UserValue)
        - churn_risk_rate (Lifecycle)
        """
        context = self._build_product_context(snapshots)
        if not context:
            return

        for cid, m in metrics.items():
            m["_context"] = dict(context)
            report.context_added += 1

    def _build_product_context(
        self, snapshots: dict[str, Any]
    ) -> dict[str, Any]:
        """从七域快照构建产品上下文 dict。"""
        ctx: dict[str, Any] = {}

        # Lifecycle: 留存
        lifecycle = snapshots.get("Lifecycle")
        if lifecycle:
            if hasattr(lifecycle, "d1_retention"):
                ctx["d1_retention"] = lifecycle.d1_retention
            if hasattr(lifecycle, "d7_retention"):
                ctx["d7_retention"] = lifecycle.d7_retention
            if hasattr(lifecycle, "d30_retention"):
                ctx["d30_retention"] = lifecycle.d30_retention
            if hasattr(lifecycle, "churn_risk_rate"):
                ctx["churn_risk_rate"] = lifecycle.churn_risk_rate
            if hasattr(lifecycle, "dau"):
                ctx["dau"] = lifecycle.dau

        # Monetization: 收入指标
        monetization = snapshots.get("Monetization")
        if monetization:
            for field_name in ("arpu", "arppu", "payer_rate", "ltv_d7", "ltv_d30"):
                if hasattr(monetization, field_name):
                    ctx[field_name] = getattr(monetization, field_name)

        # UserValue: 价值评分
        user_value = snapshots.get("UserValue")
        if user_value:
            if hasattr(user_value, "avg_value_score"):
                ctx["avg_value_score"] = user_value.avg_value_score
            if hasattr(user_value, "pareto_ratio"):
                ctx["pareto_ratio"] = user_value.pareto_ratio

        # Gameplay: 关卡通过率
        gameplay = snapshots.get("Gameplay")
        if gameplay:
            if hasattr(gameplay, "total_players"):
                ctx["total_players"] = gameplay.total_players
            if hasattr(gameplay, "avg_session_len"):
                ctx["avg_session_len"] = gameplay.avg_session_len

        return ctx


# ──────────────────────────────────────────────
# 便捷函数
# ──────────────────────────────────────────────


def adapt_metrics(
    ads_metrics: dict[str, dict[str, float]],
    seven_domain_snapshots: dict[str, Any] | None = None,
    player_profiles: list[Any] | None = None,
    creative_attribution: dict[str, str] | None = None,
) -> dict[str, dict[str, float]]:
    """便捷函数: 适配多源数据, 只返回 metrics (不返回 report)。"""
    adapter = MetricsAdapter()
    metrics, _ = adapter.adapt(
        ads_metrics=ads_metrics,
        seven_domain_snapshots=seven_domain_snapshots,
        player_profiles=player_profiles,
        creative_attribution=creative_attribution,
    )
    return metrics
