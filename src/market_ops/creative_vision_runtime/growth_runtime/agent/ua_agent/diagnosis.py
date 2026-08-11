"""E14.3.3 UA Diagnosis Engine — 根因诊断引擎.

将分析结果转换为根本原因诊断:

  输入: UAAnalysisResult (从 analyzer 输出)
  输出: UADiagnosis (issue_type, root_cause, confidence, evidence)

诊断规则 (确定性、可解释):
  - CTR↓ + frequency↑ => CREATIVE_FATIGUE
  - CTR正常 + CVR↓ => STORE_ISSUE
  - CPI↑ 单独 => AUDIENCE_SATURATION
  - ROAS↓ + CPI↑ + fatigue↑ => CREATIVE_FATIGUE (复合)
  - 所有指标正常 => HEALTHY

设计原则:
  - 规则驱动，确定性
  - 每个诊断有证据链
  - 置信度基于异常严重程度
  - 支持多诊断 (可同时有多个问题)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict
from typing import Any

from .analyzer import MetricAnomaly, MetricStatus, UAAnalysisResult


# ═══════════════════════════════════════════════════════════════
# Diagnosis Models
# ═══════════════════════════════════════════════════════════════


class DiagnosisType(str, Enum):
    """诊断类型."""
    HEALTHY = "healthy"                        # 健康
    CREATIVE_FATIGUE = "creative_fatigue"       # 素材疲劳
    AUDIENCE_SATURATION = "audience_saturation"  # 受众饱和
    STORE_ISSUE = "store_issue"                 # 商店/落地页问题
    CPI_SPIKE = "cpi_spike"                     # CPI 突增
    BUDGET_INEFFICIENCY = "budget_inefficiency"  # 预算低效
    ROAS_DECLINE = "roas_decline"               # ROAS 下降
    PAYER_DECLINE = "payer_decline"             # 付费率下降
    RETENTION_DECLINE = "retention_decline"      # 留存下降
    LTV_DECLINE = "ltv_decline"                 # LTV 下降
    UNKNOWN = "unknown"                         # 未知


class DiagnosisSeverity(str, Enum):
    """诊断严重度."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class UADiagnosis:
    """UA 诊断结果.

    Attributes:
        diagnosis_id: 诊断 ID
        issue_type: 问题类型
        severity: 严重度
        root_cause: 根因描述
        confidence: 置信度 (0-1)
        evidence: 证据链 (支持诊断的指标异常)
        related_metrics: 相关指标
        recommendation: 初步建议
        created_at: 诊断时间
        metadata: 扩展元数据
    """
    diagnosis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_type: DiagnosisType = DiagnosisType.HEALTHY
    severity: DiagnosisSeverity = DiagnosisSeverity.LOW
    root_cause: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    related_metrics: list[str] = field(default_factory=list)
    recommendation: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "root_cause": self.root_cause,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "related_metrics": self.related_metrics,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Diagnosis Rules
# ═══════════════════════════════════════════════════════════════

# 诊断规则: (条件函数, 诊断类型, 根因模板, 建议模板)
# 每个规则检查特定的异常模式


@dataclass
class DiagnosisRule:
    """诊断规则."""
    name: str
    diagnosis_type: DiagnosisType
    condition: Any  # callable(anomaly_map) -> bool
    root_cause_template: str
    recommendation_template: str
    severity: DiagnosisSeverity = DiagnosisSeverity.MEDIUM


# ═══════════════════════════════════════════════════════════════
# UA Diagnosis Engine
# ═══════════════════════════════════════════════════════════════


class UADiagnosisEngine:
    """UA 诊断引擎 — 根据异常模式诊断根因.

    用法:
        engine = UADiagnosisEngine()
        diagnosis = engine.diagnose(analysis_result)
    """

    def __init__(self):
        self._rules: list[DiagnosisRule] = self._build_rules()
        self._history: list[UADiagnosis] = []

    def _build_rules(self) -> list[DiagnosisRule]:
        """构建诊断规则集."""
        return [
            # 素材疲劳: CTR下降 + frequency上升 或 fatigue高
            DiagnosisRule(
                name="creative_fatigue_ctr_freq",
                diagnosis_type=DiagnosisType.CREATIVE_FATIGUE,
                condition=lambda am: (
                    self._has_anomaly(am, "ctr", MetricStatus.WARNING)
                    and self._has_anomaly(am, "frequency", MetricStatus.WARNING)
                ) or self._has_anomaly(am, "fatigue", MetricStatus.CRITICAL),
                root_cause_template="素材疲劳: CTR={ctr}%, frequency={frequency}, fatigue={fatigue}",
                recommendation_template="需要新素材: 检测 winning DNA、生成新变体",
                severity=DiagnosisSeverity.HIGH,
            ),
            # 受众饱和: CPI上升 但 CTR正常
            DiagnosisRule(
                name="audience_saturation_cpi",
                diagnosis_type=DiagnosisType.AUDIENCE_SATURATION,
                condition=lambda am: (
                    self._has_anomaly(am, "cpi", MetricStatus.WARNING)
                    and not self._has_anomaly(am, "ctr", MetricStatus.WARNING)
                    and not self._has_anomaly(am, "fatigue", MetricStatus.WARNING)
                ),
                root_cause_template="受众饱和: CPI={cpi}, CTR正常，说明受众已覆盖",
                recommendation_template="扩展受众定向、测试新受众分组",
                severity=DiagnosisSeverity.MEDIUM,
            ),
            # 商店/落地页问题: CTR正常 but CVR下降
            DiagnosisRule(
                name="store_issue_cvr",
                diagnosis_type=DiagnosisType.STORE_ISSUE,
                condition=lambda am: (
                    self._has_anomaly(am, "cvr", MetricStatus.WARNING)
                    and not self._has_anomaly(am, "ctr", MetricStatus.WARNING)
                ),
                root_cause_template="落地页/商店问题: CTR正常但CVR={cvr}%",
                recommendation_template="检查商店页面、优化落地页转化",
                severity=DiagnosisSeverity.HIGH,
            ),
            # CPI 单独突增
            DiagnosisRule(
                name="cpi_spike",
                diagnosis_type=DiagnosisType.CPI_SPIKE,
                condition=lambda am: (
                    self._has_anomaly(am, "cpi", MetricStatus.CRITICAL)
                    and not self._has_anomaly(am, "fatigue", MetricStatus.CRITICAL)
                ),
                root_cause_template="CPI突增: CPI={cpi}",
                recommendation_template="检查竞价环境、调整出价策略",
                severity=DiagnosisSeverity.CRITICAL,
            ),
            # ROAS 下降 (非疲劳导致)
            DiagnosisRule(
                name="roas_decline",
                diagnosis_type=DiagnosisType.ROAS_DECLINE,
                condition=lambda am: (
                    self._has_anomaly(am, "roas", MetricStatus.WARNING)
                    and not self._has_anomaly(am, "fatigue", MetricStatus.CRITICAL)
                    and not self._has_anomaly(am, "cpi", MetricStatus.WARNING)
                ),
                root_cause_template="ROAS下降: ROAS={roas}, 非疲劳非CPI导致",
                recommendation_template="检查收入端、分析LTV和付费率",
                severity=DiagnosisSeverity.HIGH,
            ),
            # 付费率下降
            DiagnosisRule(
                name="payer_decline",
                diagnosis_type=DiagnosisType.PAYER_DECLINE,
                condition=lambda am: self._has_anomaly(am, "payer_rate", MetricStatus.WARNING),
                root_cause_template="付费率下降: payer_rate={payer_rate}%",
                recommendation_template="优化付费转化、检查礼包和定价",
                severity=DiagnosisSeverity.MEDIUM,
            ),
            # 留存下降
            DiagnosisRule(
                name="retention_decline",
                diagnosis_type=DiagnosisType.RETENTION_DECLINE,
                condition=lambda am: self._has_anomaly(am, "d7_retention", MetricStatus.WARNING),
                root_cause_template="留存下降: D7={d7_retention}%",
                recommendation_template="优化FTUE、调整关卡难度",
                severity=DiagnosisSeverity.MEDIUM,
            ),
            # LTV 下降
            DiagnosisRule(
                name="ltv_decline",
                diagnosis_type=DiagnosisType.LTV_DECLINE,
                condition=lambda am: self._has_anomaly(am, "ltv", MetricStatus.WARNING),
                root_cause_template="LTV下降: LTV={ltv}",
                recommendation_template="分析LTV下降原因、检查付费和留存",
                severity=DiagnosisSeverity.HIGH,
            ),
            # 预算低效: ROAS低 + CPI正常
            DiagnosisRule(
                name="budget_inefficiency",
                diagnosis_type=DiagnosisType.BUDGET_INEFFICIENCY,
                condition=lambda am: (
                    self._has_anomaly(am, "roas", MetricStatus.CRITICAL)
                    and not self._has_anomaly(am, "cpi", MetricStatus.WARNING)
                ),
                root_cause_template="预算低效: ROAS={roas}但CPI正常",
                recommendation_template="重新分配预算、暂停低效系列",
                severity=DiagnosisSeverity.HIGH,
            ),
        ]

    # ── 核心诊断 ──────────────────────────────────────────────

    def diagnose(self, analysis: UAAnalysisResult) -> list[UADiagnosis]:
        """根据分析结果诊断根因.

        Args:
            analysis: UA 分析结果

        Returns:
            诊断列表 (可能多个同时存在)
        """
        anomaly_map = self._build_anomaly_map(analysis)

        if not anomaly_map:
            return [self._healthy_diagnosis()]

        diagnoses = []
        for rule in self._rules:
            if rule.condition(anomaly_map):
                diagnosis = self._apply_rule(rule, anomaly_map)
                diagnoses.append(diagnosis)

        if not diagnoses:
            return [self._unknown_diagnosis(anomaly_map)]

        self._history.extend(diagnoses)
        return diagnoses

    def diagnose_from_anomalies(
        self,
        anomalies: list[MetricAnomaly],
    ) -> list[UADiagnosis]:
        """直接从异常列表诊断."""
        analysis = UAAnalysisResult(anomalies=anomalies)
        return self.diagnose(analysis)

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_anomaly_map(
        self,
        analysis: UAAnalysisResult,
    ) -> dict[str, MetricAnomaly]:
        """构建异常映射: {metric_name: MetricAnomaly}."""
        return {a.metric: a for a in analysis.anomalies}

    @staticmethod
    def _has_anomaly(
        anomaly_map: dict[str, MetricAnomaly],
        metric: str,
        min_status: MetricStatus = MetricStatus.WARNING,
    ) -> bool:
        """检查是否有指定级别的异常."""
        a = anomaly_map.get(metric)
        if not a:
            return False
        if min_status == MetricStatus.WARNING:
            return a.status in (MetricStatus.WARNING, MetricStatus.CRITICAL)
        if min_status == MetricStatus.CRITICAL:
            return a.status == MetricStatus.CRITICAL
        return True

    def _apply_rule(
        self,
        rule: DiagnosisRule,
        anomaly_map: dict[str, MetricAnomaly],
    ) -> UADiagnosis:
        """应用规则生成诊断."""
        # 收集证据
        evidence = []
        related_metrics = []
        for metric_name, anomaly in anomaly_map.items():
            if anomaly.status in (MetricStatus.WARNING, MetricStatus.CRITICAL):
                evidence.append(
                    f"{metric_name}={anomaly.current_value} "
                    f"(expected={anomaly.expected_value}, "
                    f"deviation={anomaly.deviation:.2%})"
                )
                related_metrics.append(metric_name)

        # 格式化根因
        # 格式化根因 (使用 defaultdict 避免 KeyError)
        metric_values: dict[str, Any] = defaultdict(
            lambda: "N/A",
            {m: anomaly_map[m].current_value for m in anomaly_map},
        )
        root_cause = rule.root_cause_template.format_map(metric_values)
        recommendation = rule.recommendation_template.format_map(metric_values)

        # 置信度: 基于异常严重度和数量
        confidence = self._compute_confidence(anomaly_map, rule)

        return UADiagnosis(
            issue_type=rule.diagnosis_type,
            severity=rule.severity,
            root_cause=root_cause,
            confidence=confidence,
            evidence=evidence,
            related_metrics=related_metrics,
            recommendation=recommendation,
        )

    def _compute_confidence(
        self,
        anomaly_map: dict[str, MetricAnomaly],
        rule: DiagnosisRule,
    ) -> float:
        """计算诊断置信度."""
        if not anomaly_map:
            return 0.0

        confidences = [a.confidence for a in anomaly_map.values()]
        avg_conf = sum(confidences) / len(confidences)

        # 异常越多，置信度越高 (但有限制)
        count_bonus = min(len(anomaly_map) * 0.05, 0.15)
        return min(avg_conf + count_bonus, 1.0)

    def _healthy_diagnosis(self) -> UADiagnosis:
        """生成健康诊断."""
        return UADiagnosis(
            issue_type=DiagnosisType.HEALTHY,
            severity=DiagnosisSeverity.LOW,
            root_cause="所有指标正常，未检测到异常",
            confidence=0.95,
            evidence=["所有指标在健康范围内"],
            recommendation="继续监控，保持当前策略",
        )

    def _unknown_diagnosis(
        self,
        anomaly_map: dict[str, MetricAnomaly],
    ) -> UADiagnosis:
        """生成未知诊断."""
        anomalies_desc = [
            f"{a.metric}={a.current_value} ({a.status.value})"
            for a in anomaly_map.values()
        ]
        return UADiagnosis(
            issue_type=DiagnosisType.UNKNOWN,
            severity=DiagnosisSeverity.MEDIUM,
            root_cause=f"异常模式不匹配已知规则: {', '.join(anomalies_desc)}",
            confidence=0.3,
            evidence=[f"异常: {', '.join(anomalies_desc)}"],
            recommendation="需要人工分析",
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 10) -> list[UADiagnosis]:
        return self._history[-n:]

    def get_by_type(self, diagnosis_type: DiagnosisType) -> list[UADiagnosis]:
        return [d for d in self._history if d.issue_type == diagnosis_type]

    def reset(self) -> None:
        self._history.clear()