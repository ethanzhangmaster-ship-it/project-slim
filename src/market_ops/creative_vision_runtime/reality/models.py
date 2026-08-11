"""E12.1 — Unified Reality Data Models。

定义 E12 统一现实数据模型，桥接 E11 Evolution 内部模型与
真实世界数据源（Meta Ads、Adjust）。

设计原则：
  - 字段名与 E11 内部模型（CreativeDNA, PerformanceSignal）对齐
  - 所有货币值统一为 USD
  - 所有比率统一为 0-1 浮点数
  - 支持 to_dict() 方便序列化
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ── Enums ──────────────────────────────────────────────────


class RealitySource(str, Enum):
    """数据来源。"""

    META_ADS = "meta_ads"
    ADJUST = "adjust"
    APPSTORE = "appstore"
    GOOGLE_PLAY = "google_play"
    FIREBASE = "firebase"
    THINKING_DATA = "thinking_data"  # 数数 · 玩家行为真相层
    MERGED = "merged"  # 多源合并


# ── Ad Performance ─────────────────────────────────────────


@dataclass
class AdPerformanceRecord:
    """Meta Ads 广告级性能记录。

    从 FacebookAdsAdapter.get_metrics() 或 Facebook Insights API 拉取，
    经过统一格式化后的标准化广告性能数据。

    Attributes:
        ad_id:         Facebook Ad ID
        campaign_id:   Facebook Campaign ID
        adset_id:      Facebook Ad Set ID
        creative_id:   内部 Creative ID（用于 DNA 关联）
        spend:         花费（USD）
        impressions:   展示量
        clicks:        点击量
        installs:      安装量
        ctr:           点击率（0-1）
        cpm:           千次展示成本（USD）
        cpc:           单次点击成本（USD）
        cpi:           单次安装成本（USD）
        date:          数据日期
        source:        数据来源
    """

    ad_id: str = ""
    campaign_id: str = ""
    adset_id: str = ""
    creative_id: str = ""

    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0

    ctr: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0
    cpi: float = 0.0

    date: str = ""
    source: RealitySource = RealitySource.META_ADS

    record_id: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()
        if not self.date:
            self.date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "ad_id": self.ad_id,
            "campaign_id": self.campaign_id,
            "creative_id": self.creative_id,
            "spend": round(self.spend, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "ctr": round(self.ctr, 4),
            "cpm": round(self.cpm, 2),
            "cpc": round(self.cpc, 2),
            "cpi": round(self.cpi, 2),
            "date": self.date,
            "source": self.source.value,
            "recorded_at": self.recorded_at,
        }

    def __repr__(self) -> str:
        return (
            f"AdPerformanceRecord(ad={self.ad_id}, "
            f"spend={self.spend:.2f}, installs={self.installs}, "
            f"ctr={self.ctr:.4f})"
        )


# ── Revenue Performance ────────────────────────────────────


@dataclass
class RevenuePerformance:
    """Adjust 收入性能数据。

    从 AdjustTracker.get_campaign_metrics() 拉取，
    包含 D1-D120 的 ROAS、LTV、留存等关键指标。

    Attributes:
        campaign_id:        Campaign ID
        creative_id:        内部 Creative ID
        installs:           安装量
        revenue_d1:         D1 收入
        revenue_d7:         D7 收入
        revenue_d30:        D30 收入
        revenue_d120:       D120 收入（如有）
        ltv:                预估 LTV
        roas_d1:            D1 ROAS
        roas_d7:            D7 ROAS
        roas_d30:           D30 ROAS
        roas_d120:          D120 ROAS（如有）
        retention_d1:       D1 留存率
        retention_d7:       D7 留存率
        retention_d30:      D30 留存率
        payer_rate:         付费率
        arppu:              ARPPU（每付费用户平均收入）
        cohort_size:        队列大小
        source:             数据来源
    """

    campaign_id: str = ""
    creative_id: str = ""

    installs: int = 0

    revenue_d1: float = 0.0
    revenue_d7: float = 0.0
    revenue_d30: float = 0.0
    revenue_d120: float = 0.0
    ltv: float = 0.0

    roas_d1: float = 0.0
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    roas_d120: float = 0.0

    retention_d1: float = 0.0
    retention_d7: float = 0.0
    retention_d30: float = 0.0

    payer_rate: float = 0.0
    arppu: float = 0.0
    cohort_size: int = 0

    source: RealitySource = RealitySource.ADJUST

    record_id: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "campaign_id": self.campaign_id,
            "creative_id": self.creative_id,
            "installs": self.installs,
            "revenue_d1": round(self.revenue_d1, 2),
            "revenue_d7": round(self.revenue_d7, 2),
            "revenue_d30": round(self.revenue_d30, 2),
            "revenue_d120": round(self.revenue_d120, 2),
            "ltv": round(self.ltv, 2),
            "roas_d1": round(self.roas_d1, 4),
            "roas_d7": round(self.roas_d7, 4),
            "roas_d30": round(self.roas_d30, 4),
            "roas_d120": round(self.roas_d120, 4),
            "retention_d1": round(self.retention_d1, 4),
            "retention_d7": round(self.retention_d7, 4),
            "retention_d30": round(self.retention_d30, 4),
            "payer_rate": round(self.payer_rate, 4),
            "arppu": round(self.arppu, 2),
            "cohort_size": self.cohort_size,
            "source": self.source.value,
            "recorded_at": self.recorded_at,
        }

    def __repr__(self) -> str:
        return (
            f"RevenuePerformance(campaign={self.campaign_id}, "
            f"roas_d7={self.roas_d7:.4f}, ltv={self.ltv:.2f})"
        )


# ── Product Behavior Record ────────────────────────────────


@dataclass
class ProductBehaviorRecord:
    """ThinkingData 玩家行为记录。

    从 ThinkingData Open API 拉取，包含用户生命周期、留存、付费、
    游戏进度、渠道归因等产品行为真相数据。

    定位：ThinkingData = 游戏产品 Reality 数据中心（玩家行为真相层）

    Attributes:
        project_id:          数数项目 ID
        user_id:             玩家 ID
        install_date:        安装日期
        last_active_date:    最后活跃日期
        lifecycle_stage:     生命周期阶段 (install/activation/retention/engagement/churn)
        d1_retention:        D1 留存率
        d7_retention:        D7 留存率
        d30_retention:       D30 留存率
        session_count:       会话次数
        avg_session_duration:平均会话时长（秒）
        level:               玩家等级
        stage:               关卡/阶段
        is_payer:            是否付费
        first_pay_date:      首次付费日期
        total_revenue:       累计付费金额
        pay_count:           付费次数
        payer_segment:       付费分层 (non_payer/first_payer/repeat_payer/whale)
        arpu:                ARPU
        channel:             获客渠道
        campaign_id:         投放 Campaign ID（与 Meta Ads 关联）
        creative_id:         投放 Creative ID
        country:             国家
        device:              设备
        platform:            平台 (ios/android)
        source:              数据来源
    """

    project_id: int = 0
    user_id: str = ""

    # 生命周期
    install_date: str = ""
    last_active_date: str = ""
    lifecycle_stage: str = ""

    # 留存
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0

    # 活跃
    session_count: int = 0
    avg_session_duration: float = 0.0

    # 游戏进度
    level: int = 0
    stage: str = ""

    # 付费
    is_payer: bool = False
    first_pay_date: str = ""
    total_revenue: float = 0.0
    pay_count: int = 0
    payer_segment: str = "non_payer"
    arpu: float = 0.0

    # 渠道归因
    channel: str = ""
    campaign_id: str = ""
    creative_id: str = ""
    country: str = ""
    device: str = ""
    platform: str = ""

    source: RealitySource = RealitySource.THINKING_DATA

    record_id: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()
        if self.is_payer and self.payer_segment == "non_payer":
            if self.total_revenue >= 500.0:
                self.payer_segment = "whale"
            elif self.pay_count > 1:
                self.payer_segment = "repeat_payer"
            else:
                self.payer_segment = "first_payer"
        if not self.is_payer:
            self.payer_segment = "non_payer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "install_date": self.install_date,
            "last_active_date": self.last_active_date,
            "lifecycle_stage": self.lifecycle_stage,
            "d1_retention": round(self.d1_retention, 4),
            "d7_retention": round(self.d7_retention, 4),
            "d30_retention": round(self.d30_retention, 4),
            "session_count": self.session_count,
            "avg_session_duration": round(self.avg_session_duration, 2),
            "level": self.level,
            "stage": self.stage,
            "is_payer": self.is_payer,
            "first_pay_date": self.first_pay_date,
            "total_revenue": round(self.total_revenue, 2),
            "pay_count": self.pay_count,
            "payer_segment": self.payer_segment,
            "arpu": round(self.arpu, 2),
            "channel": self.channel,
            "campaign_id": self.campaign_id,
            "creative_id": self.creative_id,
            "country": self.country,
            "device": self.device,
            "platform": self.platform,
            "source": self.source.value,
            "recorded_at": self.recorded_at,
        }

    def __repr__(self) -> str:
        return (
            f"ProductBehaviorRecord(user={self.user_id}, "
            f"stage={self.lifecycle_stage}, "
            f"d7_retention={self.d7_retention:.4f}, "
            f"payer={self.is_payer})"
        )


# ── Campaign Reality ───────────────────────────────────────


@dataclass
class CampaignReality:
    """统一 Campaign 现实视图。

    合并 Meta Ads（花费、展示）和 Adjust（收入、ROAS）数据，
    形成单一 Campaign 的完整现实画像。
    """

    campaign_id: str = ""
    campaign_name: str = ""

    # From Meta Ads
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    ctr: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0
    cpi: float = 0.0

    # From Adjust
    revenue_d7: float = 0.0
    revenue_d30: float = 0.0
    ltv: float = 0.0
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    retention_d7: float = 0.0
    payer_rate: float = 0.0

    # Derived
    roi: float = 0.0
    profit: float = 0.0

    period: str = ""
    creatives: list[str] = field(default_factory=list)

    record_id: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()
        if self.revenue_d30 > 0 and self.spend > 0 and self.roi == 0.0:
            self.roi = round(self.revenue_d30 / self.spend, 4)
        if self.revenue_d30 > 0 and self.profit == 0.0:
            self.profit = round(self.revenue_d30 - self.spend, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "spend": round(self.spend, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "ctr": round(self.ctr, 4),
            "cpm": round(self.cpm, 2),
            "cpc": round(self.cpc, 2),
            "cpi": round(self.cpi, 2),
            "revenue_d7": round(self.revenue_d7, 2),
            "revenue_d30": round(self.revenue_d30, 2),
            "ltv": round(self.ltv, 2),
            "roas_d7": round(self.roas_d7, 4),
            "roas_d30": round(self.roas_d30, 4),
            "retention_d7": round(self.retention_d7, 4),
            "payer_rate": round(self.payer_rate, 4),
            "roi": round(self.roi, 4),
            "profit": round(self.profit, 2),
            "period": self.period,
            "creatives": self.creatives,
            "recorded_at": self.recorded_at,
        }

    def __repr__(self) -> str:
        return (
            f"CampaignReality(campaign={self.campaign_id}, "
            f"roi={self.roi:.4f}, profit={self.profit:.2f})"
        )


# ── Creative Reality ───────────────────────────────────────


@dataclass
class CreativeReality:
    """Creative DNA × 真实商业结果。

    建立 Creative DNA 与真实赚钱能力之间的映射。
    这是 E12 最核心的数据模型 —— 回答：

      "这个 DNA 配置在真实市场中的表现如何？"

    Attributes:
        creative_id:    内部 Creative ID
        dna_id:         Creative DNA ID（genome_id）
        genome_name:    DNA 名称
        hook_gene:      Hook 基因值
        spend:          花费
        revenue:        收入
        roi:            ROI
        roas_d7:        D7 ROAS
        roas_d30:       D30 ROAS
        ctr:            点击率
        cpi:            单次安装成本
        installs:       安装量
        payer_rate:     付费率
        ltv:            预估 LTV
        performance_score: 综合表现评分（0-1）
    """

    creative_id: str = ""
    dna_id: str = ""
    genome_name: str = ""

    # DNA genes
    hook_gene: str = ""
    visual_gene: str = ""
    gameplay_gene: str = ""
    monetization_gene: str = ""
    audience_gene: str = ""
    psychology_gene: str = ""
    context_gene: str = ""

    # Performance
    spend: float = 0.0
    revenue: float = 0.0
    roi: float = 0.0
    roas_d7: float = 0.0
    roas_d30: float = 0.0
    ctr: float = 0.0
    cpi: float = 0.0
    installs: int = 0
    payer_rate: float = 0.0
    ltv: float = 0.0

    performance_score: float = 0.0

    record_id: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "creative_id": self.creative_id,
            "dna_id": self.dna_id,
            "genome_name": self.genome_name,
            "hook_gene": self.hook_gene,
            "visual_gene": self.visual_gene,
            "gameplay_gene": self.gameplay_gene,
            "monetization_gene": self.monetization_gene,
            "audience_gene": self.audience_gene,
            "psychology_gene": self.psychology_gene,
            "context_gene": self.context_gene,
            "spend": round(self.spend, 2),
            "revenue": round(self.revenue, 2),
            "roi": round(self.roi, 4),
            "roas_d7": round(self.roas_d7, 4),
            "roas_d30": round(self.roas_d30, 4),
            "ctr": round(self.ctr, 4),
            "cpi": round(self.cpi, 2),
            "installs": self.installs,
            "payer_rate": round(self.payer_rate, 4),
            "ltv": round(self.ltv, 2),
            "performance_score": round(self.performance_score, 4),
            "recorded_at": self.recorded_at,
        }

    def to_gene_performance(self) -> dict[str, float]:
        """提取基因级性能权重。

        将 CreativeReality 分解为各个基因的贡献权重。
        简化版：按 performance_score 均匀分配。

        Returns:
            {gene_name: weight} 映射
        """
        if self.performance_score <= 0:
            return {}

        gene_map = {
            "hook": self.hook_gene,
            "visual": self.visual_gene,
            "gameplay": self.gameplay_gene,
            "monetization": self.monetization_gene,
            "audience": self.audience_gene,
            "psychology": self.psychology_gene,
            "context": self.context_gene,
        }
        active_genes = [k for k, v in gene_map.items() if v]
        if not active_genes:
            return {}

        weight_per_gene = self.performance_score / len(active_genes)
        return {g: weight_per_gene for g in active_genes}

    def __repr__(self) -> str:
        return (
            f"CreativeReality(creative={self.creative_id}, "
            f"dna={self.dna_id}, roi={self.roi:.4f}, "
            f"score={self.performance_score:.4f})"
        )


# ── Reality Snapshot ───────────────────────────────────────


@dataclass
class RealitySnapshot:
    """跨平台综合现实快照。

    合并 Meta Ads + Adjust 数据，生成 E11 Evolution 可消费的
    统一现实视图。每次 poll() 产生一个快照。

    Attributes:
        snapshot_id:     快照 ID
        timestamp:       快照时间
        period_start:    数据起始日期
        period_end:      数据结束日期
        campaigns:       所有 Campaign 现实
        creatives:       所有 Creative 现实
        total_spend:     总花费
        total_revenue:   总收入
        total_roi:       总 ROI
        total_installs:  总安装量
        summary:         快照摘要
    """

    snapshot_id: str = ""
    timestamp: str = ""
    period_start: str = ""
    period_end: str = ""

    campaigns: list[CampaignReality] = field(default_factory=list)
    creatives: list[CreativeReality] = field(default_factory=list)

    total_spend: float = 0.0
    total_revenue: float = 0.0
    total_roi: float = 0.0
    total_installs: int = 0

    summary: str = ""

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            self.snapshot_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "campaigns": [c.to_dict() for c in self.campaigns],
            "creatives": [c.to_dict() for c in self.creatives],
            "total_spend": round(self.total_spend, 2),
            "total_revenue": round(self.total_revenue, 2),
            "total_roi": round(self.total_roi, 4),
            "total_installs": self.total_installs,
            "summary": self.summary,
        }

    def get_top_creatives(self, n: int = 5) -> list[CreativeReality]:
        """获取表现最好的 N 个 Creative。"""
        return sorted(
            self.creatives,
            key=lambda c: c.performance_score,
            reverse=True,
        )[:n]

    def get_bottom_creatives(self, n: int = 5) -> list[CreativeReality]:
        """获取表现最差的 N 个 Creative。"""
        return sorted(
            self.creatives,
            key=lambda c: c.performance_score,
        )[:n]

    def __repr__(self) -> str:
        return (
            f"RealitySnapshot(id={self.snapshot_id[:8]}, "
            f"campaigns={len(self.campaigns)}, "
            f"creatives={len(self.creatives)}, "
            f"roi={self.total_roi:.4f})"
        )