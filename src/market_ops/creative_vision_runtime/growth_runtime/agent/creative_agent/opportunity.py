"""E14.4.2.1 Creative Opportunity Engine — 创意机会识别.

将 UA Agent 信号转化为 Creative Opportunity:

  输入: CreativeSignal (来自 UA Agent 的 issue + metrics)
  输出: CreativeOpportunity (type, priority, target, reason, expected_impact)

核心能力:
  - 信号→机会映射: 将 UA 问题信号转化为可执行的创意机会
  - 优先级排序: 基于置信度、业务影响、DNA 数据综合排序
  - 历史参考: 利用 Creative Memory 查找类似历史成功经验
  - 批量处理: 支持多信号同时处理

设计原则:
  - 确定性映射，不依赖 AI
  - 与 E13.3 Growth Opportunity Engine 互补
  - 与 Creative Memory 和 DNA Engine 协同
  - 所有机会附带证据和预期影响
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .analyzer import CreativeDiagnosisType, CreativeDiagnosisSeverity
from .memory import CreativeMemory, CreativeDecisionOutcome, CreativeActionType
from .dna_engine import DNAEngine, CreativeDNAProfile


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class CreativeOpportunityType(str, Enum):
    """创意机会类型."""
    REFRESH_CREATIVE = "refresh_creative"          # 刷新素材 (疲劳)
    REPLACE_HOOK = "replace_hook"                  # 替换 Hook
    CHANGE_VISUAL = "change_visual"                 # 改变视觉风格
    CHANGE_GAMEPLAY = "change_gameplay"             # 改变玩法展示
    CHANGE_EMOTION = "change_emotion"               # 改变情绪驱动
    COPY_WINNER_DNA = "copy_winner_dna"             # 复制赢家 DNA
    EXPLORE_NEW_AUDIENCE = "explore_new_audience"   # 探索新受众
    EXPLORE_NEW_DNA = "explore_new_dna"             # 探索全新 DNA
    SCALE_WINNER = "scale_winner"                   # 扩大赢家投放
    OPTIMIZE_OPENING = "optimize_opening"            # 优化前3秒
    TEST_NEW_CONCEPT = "test_new_concept"            # 测试新概念
    UNKNOWN = "unknown"


class OpportunityPriority(str, Enum):
    """机会优先级."""
    CRITICAL = "critical"    # 紧急: 正在损失预算
    HIGH = "high"            # 重要: 影响核心指标
    MEDIUM = "medium"        # 正常: 优化空间
    LOW = "low"              # 低优: 积累数据


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeSignal:
    """来自 UA Agent 的创意信号.

    Attributes:
        signal_id: 信号 ID
        creative_id: 创意 ID
        issue: 问题类型 (对应 CreativeDiagnosisType)
        confidence: 置信度 (0-1)
        metrics: 指标快照
        source: 来源 (ua_agent/supervisor/manual)
        severity: 严重度
        campaign_id: 关联广告系列
        platform: 投放平台
        created_at: 信号时间
        metadata: 扩展元数据
    """
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    creative_id: str = ""
    issue: str = ""
    confidence: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    source: str = "ua_agent"
    severity: str = "warning"
    campaign_id: str = ""
    platform: str = "meta"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "creative_id": self.creative_id,
            "issue": self.issue,
            "confidence": self.confidence,
            "metrics": self.metrics,
            "source": self.source,
            "severity": self.severity,
            "campaign_id": self.campaign_id,
            "platform": self.platform,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CreativeSignal:
        return cls(
            signal_id=data.get("signal_id", ""),
            creative_id=data.get("creative_id", ""),
            issue=data.get("issue", ""),
            confidence=float(data.get("confidence", 0)),
            metrics=data.get("metrics", {}),
            source=data.get("source", "ua_agent"),
            severity=data.get("severity", "warning"),
            campaign_id=data.get("campaign_id", ""),
            platform=data.get("platform", "meta"),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"

    @property
    def is_fatigue_signal(self) -> bool:
        return self.issue in ("creative_fatigue", "fatigue")

    @property
    def is_winner_signal(self) -> bool:
        return self.issue in ("winner", "winner_detected")


@dataclass
class CreativeOpportunity:
    """创意机会 — 可执行的创意改进方向.

    Attributes:
        opportunity_id: 机会 ID
        type: 机会类型
        priority: 优先级
        target_creative_id: 目标创意 ID
        signal_id: 触发信号 ID
        confidence: 机会置信度
        reason: 原因描述
        evidence: 证据链
        expected_impact: 预期影响
        recommended_actions: 推荐动作
        past_references: 历史参考 (类似情况的成功经验)
        winner_dna_refs: 赢家 DNA 参考
        created_at: 创建时间
        expires_at: 过期时间
        metadata: 扩展元数据
    """
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: CreativeOpportunityType = CreativeOpportunityType.UNKNOWN
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    target_creative_id: str = ""
    signal_id: str = ""
    confidence: float = 0.0
    reason: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    expected_impact: str = ""
    recommended_actions: list[str] = field(default_factory=list)
    past_references: list[dict[str, Any]] = field(default_factory=list)
    winner_dna_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "type": self.type.value,
            "priority": self.priority.value,
            "target_creative_id": self.target_creative_id,
            "signal_id": self.signal_id,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": self.evidence,
            "expected_impact": self.expected_impact,
            "recommended_actions": self.recommended_actions,
            "past_references": self.past_references,
            "winner_dna_refs": self.winner_dna_refs,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }

    @property
    def is_critical(self) -> bool:
        return self.priority == OpportunityPriority.CRITICAL

    @property
    def is_high_priority(self) -> bool:
        return self.priority in (OpportunityPriority.CRITICAL, OpportunityPriority.HIGH)

    @property
    def summary(self) -> str:
        parts = [f"[{self.priority.value.upper()}] {self.type.value}"]
        if self.target_creative_id:
            parts.append(f"for {self.target_creative_id}")
        if self.reason:
            parts.append(f"({self.reason[0]})")
        return " ".join(parts)


@dataclass
class OpportunityReport:
    """机会报告 — 批量机会分析结果.

    Attributes:
        report_id: 报告 ID
        opportunities: 机会列表
        critical_count: 紧急数量
        high_count: 高优先级数量
        total_signals: 总信号数
        total_opportunities: 总机会数
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunities: list[CreativeOpportunity] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    total_signals: int = 0
    total_opportunities: int = 0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "total_signals": self.total_signals,
            "total_opportunities": self.total_opportunities,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def opportunity_count(self) -> int:
        return len(self.opportunities)


# ═══════════════════════════════════════════════════════════════
# Signal → Opportunity Mapping
# ═══════════════════════════════════════════════════════════════

SIGNAL_TO_OPPORTUNITY: dict[str, list[CreativeOpportunityType]] = {
    "creative_fatigue": [
        CreativeOpportunityType.REFRESH_CREATIVE,
        CreativeOpportunityType.REPLACE_HOOK,
        CreativeOpportunityType.OPTIMIZE_OPENING,
    ],
    "fatigue": [
        CreativeOpportunityType.REFRESH_CREATIVE,
        CreativeOpportunityType.REPLACE_HOOK,
    ],
    "ctr_decay": [
        CreativeOpportunityType.REPLACE_HOOK,
        CreativeOpportunityType.OPTIMIZE_OPENING,
        CreativeOpportunityType.CHANGE_VISUAL,
    ],
    "frequency_saturation": [
        CreativeOpportunityType.EXPLORE_NEW_AUDIENCE,
        CreativeOpportunityType.CHANGE_GAMEPLAY,
    ],
    "winner": [
        CreativeOpportunityType.SCALE_WINNER,
        CreativeOpportunityType.COPY_WINNER_DNA,
    ],
    "winner_detected": [
        CreativeOpportunityType.SCALE_WINNER,
        CreativeOpportunityType.COPY_WINNER_DNA,
    ],
    "roas_decay": [
        CreativeOpportunityType.REFRESH_CREATIVE,
        CreativeOpportunityType.EXPLORE_NEW_DNA,
    ],
    "underperformer": [
        CreativeOpportunityType.EXPLORE_NEW_DNA,
        CreativeOpportunityType.TEST_NEW_CONCEPT,
    ],
    "high_potential": [
        CreativeOpportunityType.CHANGE_EMOTION,
        CreativeOpportunityType.OPTIMIZE_OPENING,
    ],
    "audience_saturation": [
        CreativeOpportunityType.EXPLORE_NEW_AUDIENCE,
        CreativeOpportunityType.CHANGE_GAMEPLAY,
    ],
    "cpi_spike": [
        CreativeOpportunityType.REPLACE_HOOK,
        CreativeOpportunityType.CHANGE_VISUAL,
    ],
    "retention_decline": [
        CreativeOpportunityType.CHANGE_GAMEPLAY,
        CreativeOpportunityType.OPTIMIZE_OPENING,
    ],
    "payer_decline": [
        CreativeOpportunityType.CHANGE_EMOTION,
        CreativeOpportunityType.CHANGE_GAMEPLAY,
    ],
}


# ═══════════════════════════════════════════════════════════════
# Creative Opportunity Engine
# ═══════════════════════════════════════════════════════════════


class CreativeOpportunityEngine:
    """创意机会引擎 — 将 UA 信号转化为可执行的创意机会.

    职责:
      1. 信号→机会映射: 根据信号类型确定机会方向
      2. 优先级排序: 综合置信度、业务影响、历史经验
      3. 历史参考: 查找类似情况的成功经验
      4. 赢家 DNA 参考: 关联赢家 DNA 提供变异方向

    用法:
        engine = CreativeOpportunityEngine(memory=creative_memory, dna_engine=dna_engine)
        opportunity = engine.detect(signal)
    """

    def __init__(
        self,
        memory: CreativeMemory | None = None,
        dna_engine: DNAEngine | None = None,
    ):
        self._memory = memory or CreativeMemory()
        self._dna_engine = dna_engine or DNAEngine()
        self._history: list[CreativeOpportunity] = []

    # ── 核心检测 ──────────────────────────────────────────────

    def detect(self, signal: CreativeSignal | dict[str, Any]) -> CreativeOpportunity:
        """检测单个信号对应的创意机会.

        Args:
            signal: 创意信号 (CreativeSignal 或 dict)

        Returns:
            CreativeOpportunity: 创意机会
        """
        if isinstance(signal, dict):
            signal = CreativeSignal.from_dict(signal)

        # 1. 确定机会类型
        opportunity_type = self._map_signal_to_opportunity(signal)

        # 2. 优先级排序
        priority = self._calculate_priority(signal, opportunity_type)

        # 3. 构建原因
        reason = self._build_reason(signal, opportunity_type)

        # 4. 查找历史参考
        past_refs = self._find_past_references(signal)

        # 5. 查找赢家 DNA 参考
        winner_refs = self._find_winner_dna_refs(signal)

        # 6. 预期影响
        expected_impact = self._estimate_impact(signal, opportunity_type)

        # 7. 推荐动作
        recommended_actions = self._recommend_actions(opportunity_type, signal)

        opportunity = CreativeOpportunity(
            type=opportunity_type,
            priority=priority,
            target_creative_id=signal.creative_id,
            signal_id=signal.signal_id,
            confidence=signal.confidence,
            reason=reason,
            evidence={
                "signal_issue": signal.issue,
                "signal_confidence": signal.confidence,
                "metrics": signal.metrics,
            },
            expected_impact=expected_impact,
            recommended_actions=recommended_actions,
            past_references=past_refs,
            winner_dna_refs=winner_refs,
        )

        self._history.append(opportunity)
        return opportunity

    def detect_batch(
        self,
        signals: list[CreativeSignal | dict[str, Any]],
    ) -> OpportunityReport:
        """批量检测创意机会.

        Args:
            signals: 信号列表

        Returns:
            OpportunityReport: 机会报告
        """
        opportunities = [self.detect(s) for s in signals]

        critical = [o for o in opportunities if o.is_critical]
        high = [o for o in opportunities if o.priority == OpportunityPriority.HIGH]

        summary_parts = []
        if critical:
            summary_parts.append(f"{len(critical)} 个紧急机会")
        if high:
            summary_parts.append(f"{len(high)} 个高优先级机会")
        if not summary_parts:
            summary_parts.append("无紧急/高优机会")

        return OpportunityReport(
            opportunities=opportunities,
            critical_count=len(critical),
            high_count=len(high),
            total_signals=len(signals),
            total_opportunities=len(opportunities),
            summary=" | ".join(summary_parts),
        )

    def detect_from_dicts(
        self,
        signal_dicts: list[dict[str, Any]],
    ) -> OpportunityReport:
        """从字典列表批量检测."""
        return self.detect_batch(signal_dicts)

    # ── 内部映射 ──────────────────────────────────────────────

    def _map_signal_to_opportunity(
        self,
        signal: CreativeSignal,
    ) -> CreativeOpportunityType:
        """信号问题 → 机会类型映射."""
        issue = signal.issue.lower()
        candidates = SIGNAL_TO_OPPORTUNITY.get(issue, [CreativeOpportunityType.UNKNOWN])

        if not candidates or candidates == [CreativeOpportunityType.UNKNOWN]:
            return CreativeOpportunityType.UNKNOWN

        # 默认返回第一个最匹配的机会类型
        return candidates[0]

    def _calculate_priority(
        self,
        signal: CreativeSignal,
        opportunity_type: CreativeOpportunityType,
    ) -> OpportunityPriority:
        """计算机会优先级.

        综合因素:
          - 信号置信度
          - 信号严重度
          - 机会类型紧急性
        """
        # 紧急机会类型
        urgent_types = {
            CreativeOpportunityType.REFRESH_CREATIVE,
            CreativeOpportunityType.REPLACE_HOOK,
        }
        important_types = {
            CreativeOpportunityType.SCALE_WINNER,
            CreativeOpportunityType.COPY_WINNER_DNA,
        }

        if signal.is_critical:
            return OpportunityPriority.CRITICAL
        if signal.confidence >= 0.8 and opportunity_type in urgent_types:
            return OpportunityPriority.CRITICAL
        if signal.confidence >= 0.7 and opportunity_type in urgent_types:
            return OpportunityPriority.HIGH
        if opportunity_type in important_types:
            return OpportunityPriority.HIGH
        if signal.confidence >= 0.6:
            return OpportunityPriority.MEDIUM
        if signal.confidence < 0.3:
            return OpportunityPriority.LOW
        return OpportunityPriority.MEDIUM

    def _build_reason(
        self,
        signal: CreativeSignal,
        opportunity_type: CreativeOpportunityType,
    ) -> list[str]:
        """构建原因描述."""
        reasons = []
        issue = signal.issue

        # 问题描述
        issue_labels = {
            "creative_fatigue": "素材疲劳，CTR/ROAS持续下降",
            "fatigue": "素材疲劳信号",
            "ctr_decay": "CTR 衰减",
            "frequency_saturation": "受众频次饱和",
            "winner": "检测到赢家素材",
            "winner_detected": "发现赢家素材",
            "roas_decay": "ROAS 下降",
            "underperformer": "素材表现低于预期",
            "high_potential": "高潜力素材待验证",
            "audience_saturation": "受众饱和",
            "cpi_spike": "CPI 上涨",
            "retention_decline": "留存下降",
            "payer_decline": "付费率下降",
        }
        reasons.append(issue_labels.get(issue, issue))

        # 机会描述
        opportunity_labels = {
            CreativeOpportunityType.REFRESH_CREATIVE: "需要刷新素材以恢复表现",
            CreativeOpportunityType.REPLACE_HOOK: "建议更换前3秒 Hook",
            CreativeOpportunityType.CHANGE_VISUAL: "建议改变视觉风格",
            CreativeOpportunityType.CHANGE_GAMEPLAY: "建议改变玩法展示方式",
            CreativeOpportunityType.CHANGE_EMOTION: "建议改变情绪驱动方向",
            CreativeOpportunityType.COPY_WINNER_DNA: "可复制赢家 DNA 模式",
            CreativeOpportunityType.EXPLORE_NEW_AUDIENCE: "可探索新受众群体",
            CreativeOpportunityType.EXPLORE_NEW_DNA: "建议尝试全新 DNA 组合",
            CreativeOpportunityType.SCALE_WINNER: "可以扩大投放规模",
            CreativeOpportunityType.OPTIMIZE_OPENING: "建议优化前3秒内容",
            CreativeOpportunityType.TEST_NEW_CONCEPT: "可以测试新创意概念",
        }
        label = opportunity_labels.get(opportunity_type, "")
        if label:
            reasons.append(label)

        # 置信度
        if signal.confidence >= 0.8:
            reasons.append(f"置信度: 高 ({signal.confidence:.0%})")

        return reasons

    def _find_past_references(
        self,
        signal: CreativeSignal,
    ) -> list[dict[str, Any]]:
        """查找历史类似情况的成功经验."""
        refs = []
        try:
            # 按诊断类型找历史成功记录
            diagnosis_type = _signal_to_diagnosis_type(signal.issue)
            exp = self._memory.get_experience(
                diagnosis_type=diagnosis_type,
                action_type=CreativeActionType.GENERATE_VARIANTS,
            )
            if exp and exp.success_count > 0:
                refs.append({
                    "type": "similar_diagnosis",
                    "diagnosis": diagnosis_type.value,
                    "action": "generate_variants",
                    "success_rate": round(exp.success_rate, 2),
                    "total_count": exp.total_count,
                    "avg_reward": round(exp.avg_reward, 4),
                    "confidence_boost": round(exp.confidence_boost, 4),
                })

            # 找赢家 DNA
            winner_dnas = self._memory.get_winner_dnas()
            if winner_dnas:
                refs.append({
                    "type": "winner_dna_available",
                    "count": len(winner_dnas),
                    "hint": "有赢家 DNA 可参考用于变异方向",
                })
        except Exception:
            pass
        return refs

    def _find_winner_dna_refs(
        self,
        signal: CreativeSignal,
    ) -> list[str]:
        """查找赢家 DNA 参考."""
        refs = []
        try:
            winners = self._memory.get_winner_dnas()
            for w in winners[:3]:
                if w.dna and w.dna.dominant_hook:
                    refs.append(f"hook={w.dna.dominant_hook}")
                if w.dna and w.dna.dominant_emotion:
                    refs.append(f"emotion={w.dna.dominant_emotion}")
        except Exception:
            pass
        return refs[:5]

    def _estimate_impact(
        self,
        signal: CreativeSignal,
        opportunity_type: CreativeOpportunityType,
    ) -> str:
        """预估机会影响."""
        impacts = {
            CreativeOpportunityType.REFRESH_CREATIVE: "刷新后预计 CTR 提升 15-25%，ROAS 恢复至 1.0+",
            CreativeOpportunityType.REPLACE_HOOK: "更换 Hook 后预计 CTR 提升 20-30%",
            CreativeOpportunityType.CHANGE_VISUAL: "视觉更新后预计 CTR 提升 10-20%",
            CreativeOpportunityType.CHANGE_GAMEPLAY: "玩法展示变化后预计留存率提升 5-10%",
            CreativeOpportunityType.CHANGE_EMOTION: "情绪调整后预计付费率提升 5-15%",
            CreativeOpportunityType.COPY_WINNER_DNA: "复制赢家 DNA 预计 ROAS 达到 1.5+",
            CreativeOpportunityType.EXPLORE_NEW_AUDIENCE: "新受众探索预计扩大 20-30% 覆盖",
            CreativeOpportunityType.EXPLORE_NEW_DNA: "探索新 DNA 组合可能发现新赢家",
            CreativeOpportunityType.SCALE_WINNER: "扩大投放预计保持 ROAS 1.5+",
            CreativeOpportunityType.OPTIMIZE_OPENING: "优化前3秒后预计 CTR 提升 15-25%",
            CreativeOpportunityType.TEST_NEW_CONCEPT: "新概念测试可能发现蓝海方向",
        }
        return impacts.get(opportunity_type, "继续观察")

    def _recommend_actions(
        self,
        opportunity_type: CreativeOpportunityType,
        signal: CreativeSignal,
    ) -> list[str]:
        """推荐后续动作."""
        action_map = {
            CreativeOpportunityType.REFRESH_CREATIVE: [
                "提取当前素材 DNA",
                "保持核心基因，变异 Hook 和视觉",
                "生成 5-10 个变体",
            ],
            CreativeOpportunityType.REPLACE_HOOK: [
                "分析当前 Hook 类型",
                "参考赢家 DNA 的 Hook 模式",
                "生成 3-5 个新 Hook 变体",
            ],
            CreativeOpportunityType.CHANGE_VISUAL: [
                "提取当前视觉 DNA",
                "选择 2-3 个新视觉方向",
                "生成视觉变体素材",
            ],
            CreativeOpportunityType.COPY_WINNER_DNA: [
                "提取赢家 DNA 完整画像",
                "将赢家基因应用到当前素材",
                "生成 5-10 个变体测试",
            ],
            CreativeOpportunityType.SCALE_WINNER: [
                "增加 50% 预算",
                "扩展到相似受众",
                "监控疲劳度变化",
            ],
            CreativeOpportunityType.EXPLORE_NEW_AUDIENCE: [
                "分析当前受众 DNA",
                "选择 2-3 个新受众方向",
                "创建新受众测试 Campaign",
            ],
            CreativeOpportunityType.EXPLORE_NEW_DNA: [
                "提取所有赢家 DNA",
                "选择 2-3 个未探索的基因组合",
                "生成探索性变体",
            ],
            CreativeOpportunityType.OPTIMIZE_OPENING: [
                "分析前3秒内容",
                "参考高 CTR 素材的开场模式",
                "生成 3-5 个开场变体",
            ],
            CreativeOpportunityType.TEST_NEW_CONCEPT: [
                "定义新概念假设",
                "设计验证实验",
                "生成 3-5 个概念变体",
            ],
            CreativeOpportunityType.CHANGE_GAMEPLAY: [
                "提取当前玩法展示基因",
                "选择 2-3 个新的玩法展示角度",
                "生成玩法展示变体",
            ],
            CreativeOpportunityType.CHANGE_EMOTION: [
                "分析当前情绪基因",
                "选择 2-3 个新情绪方向",
                "生成情绪变体素材",
            ],
        }
        return action_map.get(opportunity_type, ["分析信号来源", "确定后续方向"])

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[CreativeOpportunity]:
        return self._history[-n:]

    def get_critical(self) -> list[CreativeOpportunity]:
        return [o for o in self._history if o.is_critical]

    def get_by_type(
        self,
        opp_type: CreativeOpportunityType,
    ) -> list[CreativeOpportunity]:
        return [o for o in self._history if o.type == opp_type]

    def get_by_creative(self, creative_id: str) -> list[CreativeOpportunity]:
        return [o for o in self._history if o.target_creative_id == creative_id]

    def stats(self) -> dict[str, Any]:
        total = len(self._history)
        if total == 0:
            return {"total": 0}
        return {
            "total": total,
            "critical": len(self.get_critical()),
            "high": sum(1 for o in self._history if o.priority == OpportunityPriority.HIGH),
            "medium": sum(1 for o in self._history if o.priority == OpportunityPriority.MEDIUM),
            "low": sum(1 for o in self._history if o.priority == OpportunityPriority.LOW),
        }

    def reset(self) -> None:
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _signal_to_diagnosis_type(issue: str) -> CreativeDiagnosisType:
    """信号 issue → CreativeDiagnosisType 映射."""
    mapping = {
        "creative_fatigue": CreativeDiagnosisType.CREATIVE_FATIGUE,
        "fatigue": CreativeDiagnosisType.CREATIVE_FATIGUE,
        "winner": CreativeDiagnosisType.WINNER,
        "winner_detected": CreativeDiagnosisType.WINNER,
        "underperformer": CreativeDiagnosisType.UNDERPERFORMER,
        "high_potential": CreativeDiagnosisType.HIGH_POTENTIAL,
        "ctr_decay": CreativeDiagnosisType.CREATIVE_FATIGUE,
        "frequency_saturation": CreativeDiagnosisType.SATURATED,
        "audience_saturation": CreativeDiagnosisType.SATURATED,
        "roas_decay": CreativeDiagnosisType.UNDERPERFORMER,
    }
    return mapping.get(issue.lower(), CreativeDiagnosisType.UNKNOWN)


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_opportunity_engine(
    memory: CreativeMemory | None = None,
    dna_engine: DNAEngine | None = None,
) -> CreativeOpportunityEngine:
    """创建默认创意机会引擎."""
    return CreativeOpportunityEngine(memory=memory, dna_engine=dna_engine)