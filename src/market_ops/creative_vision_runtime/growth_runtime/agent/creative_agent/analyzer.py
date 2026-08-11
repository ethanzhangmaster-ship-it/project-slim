"""E14.4.1 Creative Analyzer — 创意表现分析器.

对创意素材进行表现分析，识别疲劳、赢家、潜力素材:

  输入: CreativeMetrics (CTR, CVR, ROAS, fatigue, frequency, ...)
  输出: CreativeDiagnosis (fatigue, winner, underperformer, ...)

诊断类型:
  - CREATIVE_FATIGUE: 素材疲劳 (CTR下降 + fatigue升高)
  - WINNER: 赢家素材 (高ROAS + 低疲劳)
  - UNDERPERFORMER: 低效素材 (ROAS不足)
  - HIGH_POTENTIAL: 高潜力素材 (CTR高但ROAS待验证)
  - SATURATED: 受众饱和 (frequency过高)
  - NEW_CREATIVE: 新素材 (数据不足)
  - STABLE: 稳定贡献 (中等表现 + 低波动)

设计原则:
  - 规则驱动、可解释
  - 基于阈值 + 趋势检测
  - 与 UA Agent 的 Diagnosis 互补 (UA 关注 Campaign 级别，Creative 关注素材级别)
  - 所有诊断附带证据链
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class CreativeDiagnosisType(str, Enum):
    """创意诊断类型."""
    CREATIVE_FATIGUE = "creative_fatigue"      # 素材疲劳
    WINNER = "winner"                           # 赢家素材
    UNDERPERFORMER = "underperformer"           # 低效素材
    HIGH_POTENTIAL = "high_potential"           # 高潜力
    SATURATED = "saturated"                     # 受众饱和
    NEW_CREATIVE = "new_creative"               # 新素材
    STABLE = "stable"                           # 稳定贡献
    UNKNOWN = "unknown"                         # 未知


class CreativeDiagnosisSeverity(str, Enum):
    """创意诊断严重度."""
    CRITICAL = "critical"    # 需要立即处理
    WARNING = "warning"      # 需要关注
    INFO = "info"            # 正常
    POSITIVE = "positive"    # 正向信号


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeMetrics:
    """创意表现指标快照.

    Attributes:
        creative_id: 创意 ID
        creative_name: 创意名称
        campaign_id: 关联广告系列
        platform: 投放平台 (meta/google)
        spend: 花费 (USD)
        revenue: 收入 (USD)
        roas: 广告支出回报率
        ctr: 点击率
        cvr: 转化率
        cpi: 单次安装成本
        fatigue: 疲劳度 (0-1)
        frequency: 展示频次
        impressions: 展示量
        installs: 安装量
        payer_rate: 付费率
        ltv: LTV (D7)
        d7_retention: D7 留存
        days_running: 已运行天数
        timestamp: 数据时间
        metadata: 扩展元数据
    """
    creative_id: str = ""
    creative_name: str = ""
    campaign_id: str = ""
    platform: str = "meta"
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    cpi: float = 0.0
    fatigue: float = 0.0
    frequency: float = 0.0
    impressions: int = 0
    installs: int = 0
    payer_rate: float = 0.0
    ltv: float = 0.0
    d7_retention: float = 0.0
    days_running: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "campaign_id": self.campaign_id,
            "platform": self.platform,
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": self.roas,
            "ctr": self.ctr,
            "cvr": self.cvr,
            "cpi": self.cpi,
            "fatigue": self.fatigue,
            "frequency": self.frequency,
            "impressions": self.impressions,
            "installs": self.installs,
            "payer_rate": self.payer_rate,
            "ltv": self.ltv,
            "d7_retention": self.d7_retention,
            "days_running": self.days_running,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeMetrics:
        return cls(
            creative_id=data.get("creative_id", ""),
            creative_name=data.get("creative_name", ""),
            campaign_id=data.get("campaign_id", ""),
            platform=data.get("platform", "meta"),
            spend=float(data.get("spend", 0)),
            revenue=float(data.get("revenue", 0)),
            roas=float(data.get("roas", 0)),
            ctr=float(data.get("ctr", 0)),
            cvr=float(data.get("cvr", 0)),
            cpi=float(data.get("cpi", 0)),
            fatigue=float(data.get("fatigue", 0)),
            frequency=float(data.get("frequency", 0)),
            impressions=int(data.get("impressions", 0)),
            installs=int(data.get("installs", 0)),
            payer_rate=float(data.get("payer_rate", 0)),
            ltv=float(data.get("ltv", 0)),
            d7_retention=float(data.get("d7_retention", 0)),
            days_running=int(data.get("days_running", 0)),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CreativeDiagnosis:
    """创意诊断结果.

    Attributes:
        diagnosis_id: 诊断 ID
        creative_id: 创意 ID
        diagnosis_type: 诊断类型
        severity: 严重度
        confidence: 置信度 (0-1)
        evidence: 证据链
        metrics_snapshot: 指标快照
        recommendation: 推荐动作
        expected_impact: 预期影响描述
        created_at: 诊断时间
        metadata: 扩展元数据
    """
    diagnosis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creative_id: str = ""
    diagnosis_type: CreativeDiagnosisType = CreativeDiagnosisType.UNKNOWN
    severity: CreativeDiagnosisSeverity = CreativeDiagnosisSeverity.INFO
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    metrics_snapshot: CreativeMetrics | None = None
    recommendation: str = ""
    expected_impact: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "creative_id": self.creative_id,
            "diagnosis_type": self.diagnosis_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "metrics_snapshot": self.metrics_snapshot.to_dict() if self.metrics_snapshot else None,
            "recommendation": self.recommendation,
            "expected_impact": self.expected_impact,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def is_critical(self) -> bool:
        return self.severity == CreativeDiagnosisSeverity.CRITICAL

    @property
    def is_positive(self) -> bool:
        return self.severity == CreativeDiagnosisSeverity.POSITIVE

    @property
    def summary(self) -> str:
        parts = [f"[{self.severity.value.upper()}] {self.diagnosis_type.value}"]
        if self.confidence > 0:
            parts.append(f"confidence={self.confidence:.0%}")
        if self.recommendation:
            parts.append(self.recommendation)
        return " | ".join(parts)


@dataclass
class CreativeAnalysisReport:
    """创意分析报告 — 批量分析结果.

    Attributes:
        report_id: 报告 ID
        diagnoses: 诊断列表
        winner_count: 赢家数量
        fatigue_count: 疲劳数量
        total_creatives: 总创意数
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    diagnoses: list[CreativeDiagnosis] = field(default_factory=list)
    winner_count: int = 0
    fatigue_count: int = 0
    underperformer_count: int = 0
    total_creatives: int = 0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "winner_count": self.winner_count,
            "fatigue_count": self.fatigue_count,
            "underperformer_count": self.underperformer_count,
            "total_creatives": self.total_creatives,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def diagnosis_count(self) -> int:
        return len(self.diagnoses)


# ═══════════════════════════════════════════════════════════════
# Default Thresholds
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeThresholds:
    """创意分析阈值配置.

    Attributes:
        fatigue_threshold: 疲劳度阈值 (默认 0.6)
        ctr_decay_threshold: CTR 下降阈值 (默认 -20%)
        roas_winner_threshold: 赢家 ROAS 阈值 (默认 1.5)
        roas_underperformer_threshold: 低效 ROAS 阈值 (默认 0.8)
        frequency_saturation_threshold: 频次饱和阈值 (默认 5.0)
        high_potential_ctr_threshold: 高潜力 CTR 阈值 (默认 2.0%)
        min_impressions_for_analysis: 最小展示量 (默认 5000)
        min_days_for_fatigue: 最少运行天数才能检测疲劳 (默认 3)
        winner_min_spend: 赢家最小花费 (默认 500)
        cpi_threshold: CPI 阈值 (默认 3.0)
    """
    fatigue_threshold: float = 0.6
    ctr_decay_threshold: float = -0.2
    roas_winner_threshold: float = 1.5
    roas_underperformer_threshold: float = 0.8
    frequency_saturation_threshold: float = 5.0
    high_potential_ctr_threshold: float = 0.02
    min_impressions_for_analysis: int = 5000
    min_days_for_fatigue: int = 3
    winner_min_spend: float = 500.0
    cpi_threshold: float = 3.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fatigue_threshold": self.fatigue_threshold,
            "ctr_decay_threshold": self.ctr_decay_threshold,
            "roas_winner_threshold": self.roas_winner_threshold,
            "roas_underperformer_threshold": self.roas_underperformer_threshold,
            "frequency_saturation_threshold": self.frequency_saturation_threshold,
            "high_potential_ctr_threshold": self.high_potential_ctr_threshold,
            "min_impressions_for_analysis": self.min_impressions_for_analysis,
            "min_days_for_fatigue": self.min_days_for_fatigue,
            "winner_min_spend": self.winner_min_spend,
            "cpi_threshold": self.cpi_threshold,
        }


DEFAULT_CREATIVE_THRESHOLDS = CreativeThresholds()


# ═══════════════════════════════════════════════════════════════
# Creative Analyzer
# ═══════════════════════════════════════════════════════════════


class CreativeAnalyzer:
    """创意分析器 — 对素材表现进行诊断.

    职责:
      1. 分析单个创意素材的表现
      2. 识别疲劳、赢家、低效等类型
      3. 生成诊断报告和推荐动作

    诊断规则:
      - CREATIVE_FATIGUE: fatigue >= 0.6 AND days_running >= 3
      - WINNER: roas >= 1.5 AND spend >= 500 AND fatigue < 0.5
      - UNDERPERFORMER: roas < 0.8 AND impressions >= 5000
      - HIGH_POTENTIAL: ctr >= 2.0% AND roas >= 1.0 AND impressions < 10000
      - SATURATED: frequency >= 5.0
      - NEW_CREATIVE: impressions < 5000 AND days_running < 3
      - STABLE: 不满足上述条件的中等表现素材

    用法:
        analyzer = CreativeAnalyzer()
        diagnosis = analyzer.analyze(CreativeMetrics(
            creative_id="C102", ctr=0.018, roas=0.45, fatigue=0.82,
        ))
    """

    def __init__(self, thresholds: CreativeThresholds | None = None):
        self._thresholds = thresholds or DEFAULT_CREATIVE_THRESHOLDS
        self._history: list[CreativeDiagnosis] = []

    @property
    def thresholds(self) -> CreativeThresholds:
        return self._thresholds

    # ── 核心分析 ──────────────────────────────────────────────

    def analyze(self, metrics: CreativeMetrics) -> CreativeDiagnosis:
        """分析单个创意素材.

        Args:
            metrics: 创意表现指标

        Returns:
            CreativeDiagnosis: 诊断结果
        """
        diagnosis_type = CreativeDiagnosisType.UNKNOWN
        severity = CreativeDiagnosisSeverity.INFO
        evidence: list[str] = []
        recommendation = ""
        confidence = 0.0

        t = self._thresholds

        # 1. 新素材检测
        if metrics.impressions < t.min_impressions_for_analysis and metrics.days_running < t.min_days_for_fatigue:
            diagnosis_type = CreativeDiagnosisType.NEW_CREATIVE
            severity = CreativeDiagnosisSeverity.INFO
            confidence = 0.8
            evidence.append(f"impressions={metrics.impressions} < {t.min_impressions_for_analysis}")
            evidence.append(f"days_running={metrics.days_running} < {t.min_days_for_fatigue}")
            recommendation = "继续观察，积累数据后再分析"

        # 2. 疲劳检测
        elif metrics.fatigue >= t.fatigue_threshold and metrics.days_running >= t.min_days_for_fatigue:
            diagnosis_type = CreativeDiagnosisType.CREATIVE_FATIGUE
            severity = CreativeDiagnosisSeverity.CRITICAL if metrics.fatigue >= 0.8 else CreativeDiagnosisSeverity.WARNING
            confidence = min(metrics.fatigue, 0.95)
            evidence.append(f"fatigue={metrics.fatigue:.0%} >= {t.fatigue_threshold:.0%}")
            if metrics.ctr < 0.01:
                evidence.append(f"ctr={metrics.ctr:.1%} (low)")
            if metrics.roas < 1.0:
                evidence.append(f"roas={metrics.roas:.2f} (below 1.0)")
            recommendation = "建议生成变体或替换素材"

        # 3. 受众饱和
        elif metrics.frequency >= t.frequency_saturation_threshold:
            diagnosis_type = CreativeDiagnosisType.SATURATED
            severity = CreativeDiagnosisSeverity.WARNING
            confidence = min(metrics.frequency / 10.0, 0.9)
            evidence.append(f"frequency={metrics.frequency:.1f} >= {t.frequency_saturation_threshold}")
            recommendation = "建议扩展受众或创建新素材"

        # 4. 赢家检测
        elif metrics.roas >= t.roas_winner_threshold and metrics.spend >= t.winner_min_spend:
            if metrics.fatigue < 0.5:
                diagnosis_type = CreativeDiagnosisType.WINNER
                severity = CreativeDiagnosisSeverity.POSITIVE
                confidence = min(metrics.roas / 3.0, 0.95)
                evidence.append(f"roas={metrics.roas:.2f} >= {t.roas_winner_threshold}")
                evidence.append(f"spend={metrics.spend:.0f} >= {t.winner_min_spend}")
                evidence.append(f"fatigue={metrics.fatigue:.0%} (low)")
                recommendation = "建议加大投放，提取DNA用于复制"
            else:
                # 高ROAS但疲劳度高 → 仍是赢家但有风险
                diagnosis_type = CreativeDiagnosisType.WINNER
                severity = CreativeDiagnosisSeverity.POSITIVE
                confidence = 0.7
                evidence.append(f"roas={metrics.roas:.2f} >= {t.roas_winner_threshold}")
                evidence.append(f"fatigue={metrics.fatigue:.0%} (warning: elevated)")
                recommendation = "赢家素材但有疲劳风险，建议生成变体"

        # 5. 高潜力
        elif metrics.ctr >= t.high_potential_ctr_threshold and metrics.roas >= 1.0:
            diagnosis_type = CreativeDiagnosisType.HIGH_POTENTIAL
            severity = CreativeDiagnosisSeverity.INFO
            confidence = 0.65
            evidence.append(f"ctr={metrics.ctr:.1%} >= {t.high_potential_ctr_threshold:.1%}")
            evidence.append(f"roas={metrics.roas:.2f} (adequate)")
            recommendation = "高CTR素材，建议增加投放验证ROAS"

        # 6. 低效检测
        elif metrics.roas < t.roas_underperformer_threshold and metrics.impressions >= t.min_impressions_for_analysis:
            diagnosis_type = CreativeDiagnosisType.UNDERPERFORMER
            severity = CreativeDiagnosisSeverity.CRITICAL if metrics.roas < 0.5 else CreativeDiagnosisSeverity.WARNING
            confidence = min(1.0 - metrics.roas, 0.9)
            evidence.append(f"roas={metrics.roas:.2f} < {t.roas_underperformer_threshold}")
            evidence.append(f"impressions={metrics.impressions} >= {t.min_impressions_for_analysis}")
            if metrics.cpi > t.cpi_threshold:
                evidence.append(f"cpi={metrics.cpi:.2f} > {t.cpi_threshold}")
            recommendation = "低效素材，建议暂停或分析DNA后重新设计"

        # 7. 稳定贡献
        else:
            diagnosis_type = CreativeDiagnosisType.STABLE
            severity = CreativeDiagnosisSeverity.INFO
            confidence = 0.6
            evidence.append("moderate performance across all metrics")
            recommendation = "稳定贡献，继续观察"

        diagnosis = CreativeDiagnosis(
            creative_id=metrics.creative_id,
            diagnosis_type=diagnosis_type,
            severity=severity,
            confidence=confidence,
            evidence=evidence,
            metrics_snapshot=metrics,
            recommendation=recommendation,
            expected_impact=self._estimate_impact(diagnosis_type, metrics),
        )

        self._history.append(diagnosis)
        return diagnosis

    def analyze_batch(self, metrics_list: list[CreativeMetrics]) -> CreativeAnalysisReport:
        """批量分析创意素材.

        Args:
            metrics_list: 创意指标列表

        Returns:
            CreativeAnalysisReport: 批量分析报告
        """
        diagnoses = [self.analyze(m) for m in metrics_list]

        winners = [d for d in diagnoses if d.diagnosis_type == CreativeDiagnosisType.WINNER]
        fatigued = [d for d in diagnoses if d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE]
        underperformers = [d for d in diagnoses if d.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER]

        summary_parts = []
        if winners:
            summary_parts.append(f"{len(winners)} 个赢家素材")
        if fatigued:
            summary_parts.append(f"{len(fatigued)} 个疲劳素材")
        if underperformers:
            summary_parts.append(f"{len(underperformers)} 个低效素材")

        return CreativeAnalysisReport(
            diagnoses=diagnoses,
            winner_count=len(winners),
            fatigue_count=len(fatigued),
            underperformer_count=len(underperformers),
            total_creatives=len(metrics_list),
            summary=" | ".join(summary_parts) if summary_parts else "无异常",
        )

    # ── 快捷方法 ──────────────────────────────────────────────

    def detect_winners(self, metrics_list: list[CreativeMetrics]) -> list[CreativeDiagnosis]:
        """检测赢家素材."""
        report = self.analyze_batch(metrics_list)
        return [d for d in report.diagnoses if d.diagnosis_type == CreativeDiagnosisType.WINNER]

    def detect_fatigue(self, metrics_list: list[CreativeMetrics]) -> list[CreativeDiagnosis]:
        """检测疲劳素材."""
        report = self.analyze_batch(metrics_list)
        return [d for d in report.diagnoses if d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE]

    def detect_underperformers(self, metrics_list: list[CreativeMetrics]) -> list[CreativeDiagnosis]:
        """检测低效素材."""
        report = self.analyze_batch(metrics_list)
        return [d for d in report.diagnoses if d.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER]

    def quick_analysis(
        self,
        creative_id: str,
        roas: float = 0.0,
        ctr: float = 0.0,
        fatigue: float = 0.0,
        frequency: float = 0.0,
        spend: float = 0.0,
        impressions: int = 0,
        days_running: int = 0,
        **kwargs: Any,
    ) -> CreativeDiagnosis:
        """快捷分析 — 从关键指标直接诊断.

        Args:
            creative_id: 创意 ID
            roas: ROAS
            ctr: 点击率
            fatigue: 疲劳度
            frequency: 频次
            spend: 花费
            impressions: 展示量
            days_running: 运行天数
            **kwargs: 其他指标

        Returns:
            CreativeDiagnosis
        """
        metrics = CreativeMetrics(
            creative_id=creative_id,
            roas=roas,
            ctr=ctr,
            fatigue=fatigue,
            frequency=frequency,
            spend=spend,
            impressions=impressions,
            days_running=days_running,
            **kwargs,
        )
        return self.analyze(metrics)

    # ── 内部方法 ──────────────────────────────────────────────

    def _estimate_impact(
        self,
        diagnosis_type: CreativeDiagnosisType,
        metrics: CreativeMetrics,
    ) -> str:
        """预估诊断影响."""
        if diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE:
            return f"CTR预计继续下降{metrics.fatigue * 30:.0f}%，ROAS可能跌破1.0"
        elif diagnosis_type == CreativeDiagnosisType.WINNER:
            return f"预计可扩大投放{metrics.roas * 50:.0f}%并保持ROAS>1.5"
        elif diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER:
            return f"继续投放预计损失{metrics.spend * (1 - metrics.roas):.0f} USD/天"
        elif diagnosis_type == CreativeDiagnosisType.HIGH_POTENTIAL:
            return "验证后ROAS有望达到1.5+"
        elif diagnosis_type == CreativeDiagnosisType.SATURATED:
            return "相同受众下CTR将持续下降"
        else:
            return "继续观察"

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[CreativeDiagnosis]:
        return self._history[-n:]

    def get_winners(self) -> list[CreativeDiagnosis]:
        return [d for d in self._history if d.diagnosis_type == CreativeDiagnosisType.WINNER]

    def get_fatigued(self) -> list[CreativeDiagnosis]:
        return [d for d in self._history if d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE]

    def stats(self) -> dict[str, Any]:
        total = len(self._history)
        if total == 0:
            return {"total": 0}
        return {
            "total": total,
            "winners": sum(1 for d in self._history if d.diagnosis_type == CreativeDiagnosisType.WINNER),
            "fatigued": sum(1 for d in self._history if d.diagnosis_type == CreativeDiagnosisType.CREATIVE_FATIGUE),
            "underperformers": sum(1 for d in self._history if d.diagnosis_type == CreativeDiagnosisType.UNDERPERFORMER),
            "high_potential": sum(1 for d in self._history if d.diagnosis_type == CreativeDiagnosisType.HIGH_POTENTIAL),
            "stable": sum(1 for d in self._history if d.diagnosis_type == CreativeDiagnosisType.STABLE),
        }

    def reset(self) -> None:
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_creative_analyzer(
    fatigue_threshold: float = 0.6,
    roas_winner_threshold: float = 1.5,
) -> CreativeAnalyzer:
    """创建默认创意分析器."""
    thresholds = CreativeThresholds(
        fatigue_threshold=fatigue_threshold,
        roas_winner_threshold=roas_winner_threshold,
    )
    return CreativeAnalyzer(thresholds)