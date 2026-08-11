"""E14.3.4 UA Strategy Engine — 增长策略生成.

将诊断结果转换为可执行的 UA 增长策略:

  输入: UADiagnosis (从 diagnosis 输出)
  输出: UAStrategy (strategy_type, description, expected_impact, actions)

策略类型:
  - GENERATE_CREATIVE_VARIANTS: 生成新素材变体
  - PAUSE_CAMPAIGN: 暂停广告系列
  - ADJUST_BUDGET: 调整预算
  - CHANGE_AUDIENCE: 更换受众
  - OPTIMIZE_STORE: 优化商店
  - SCALE_WINNER: 放量赢家
  - REDUCE_SPEND: 降低花费
  - REQUEST_CREATIVE_ANALYSIS: 请求 Creative Agent 分析

设计原则:
  - 策略必须可执行
  - 每个策略有预期影响
  - 策略优先级基于诊断严重度
  - 支持 E13 GrowthDecisionExecutor 兼容
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .diagnosis import DiagnosisType, DiagnosisSeverity, UADiagnosis


# ═══════════════════════════════════════════════════════════════
# Strategy Models
# ═══════════════════════════════════════════════════════════════


class StrategyType(str, Enum):
    """策略类型."""
    GENERATE_CREATIVE_VARIANTS = "generate_creative_variants"  # 生成素材变体
    REQUEST_CREATIVE_ANALYSIS = "request_creative_analysis"    # 请求素材分析
    PAUSE_CAMPAIGN = "pause_campaign"                          # 暂停广告
    ADJUST_BUDGET = "adjust_budget"                            # 调整预算
    INCREASE_BUDGET = "increase_budget"                        # 增加预算
    DECREASE_BUDGET = "decrease_budget"                        # 减少预算
    CHANGE_AUDIENCE = "change_audience"                        # 更换受众
    EXPAND_TARGETING = "expand_targeting"                      # 扩展定向
    OPTIMIZE_STORE = "optimize_store"                          # 优化商店
    OPTIMIZE_BID = "optimize_bid"                              # 优化出价
    SCALE_WINNER = "scale_winner"                              # 放量赢家
    REDUCE_SPEND = "reduce_spend"                              # 降低花费
    REALLOCATE_BUDGET = "reallocate_budget"                    # 重新分配预算
    MONITOR_ONLY = "monitor_only"                              # 仅监控
    ESCALATE_TO_SUPERVISOR = "escalate_to_supervisor"          # 升级给主管


@dataclass
class StrategyAction:
    """策略动作.

    Attributes:
        action_type: 动作类型
        target: 目标实体 (campaign_id, adset_id, etc.)
        parameters: 动作参数
        expected_impact: 预期影响描述
        estimated_impact: 预期影响量化
        confidence: 置信度
    """
    action_type: str = ""
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_impact: str = ""
    estimated_impact: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "parameters": self.parameters,
            "expected_impact": self.expected_impact,
            "estimated_impact": self.estimated_impact,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class UAStrategy:
    """UA 增长策略.

    Attributes:
        strategy_id: 策略 ID
        strategy_type: 策略类型
        description: 策略描述
        diagnosis: 来源诊断
        expected_impact: 预期影响描述
        actions: 策略动作列表
        priority: 优先级 (0-1)
        confidence: 置信度 (0-1)
        requires_approval: 是否需要审批
        created_at: 创建时间
        metadata: 扩展元数据
    """
    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_type: StrategyType = StrategyType.MONITOR_ONLY
    description: str = ""
    diagnosis: UADiagnosis | None = None
    expected_impact: str = ""
    actions: list[StrategyAction] = field(default_factory=list)
    priority: float = 0.5
    confidence: float = 0.0
    requires_approval: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type.value,
            "description": self.description,
            "diagnosis": self.diagnosis.to_dict() if self.diagnosis else None,
            "expected_impact": self.expected_impact,
            "actions": [a.to_dict() for a in self.actions],
            "priority": round(self.priority, 4),
            "confidence": round(self.confidence, 4),
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Strategy Mapping
# ═══════════════════════════════════════════════════════════════

# 诊断 → 策略映射
DIAGNOSIS_TO_STRATEGY: dict[DiagnosisType, list[dict[str, Any]]] = {
    DiagnosisType.CREATIVE_FATIGUE: [
        {
            "strategy_type": StrategyType.GENERATE_CREATIVE_VARIANTS,
            "description": "素材疲劳检测，生成新素材变体",
            "expected_impact": "预计 CTR 提升 15-30%，ROAS 恢复",
            "actions": [
                {
                    "action_type": "request_creative_analysis",
                    "expected_impact": "获取 Creative Agent 疲劳分析",
                    "estimated_impact": {"ctr_improvement": 0.15},
                },
                {
                    "action_type": "generate_variants",
                    "expected_impact": "生成新素材变体",
                    "estimated_impact": {"fatigue_reduction": 0.3},
                },
            ],
            "requires_approval": False,
        },
    ],
    DiagnosisType.AUDIENCE_SATURATION: [
        {
            "strategy_type": StrategyType.EXPAND_TARGETING,
            "description": "受众饱和，扩展定向范围",
            "expected_impact": "预计降低 CPI 10-20%",
            "actions": [
                {
                    "action_type": "expand_targeting",
                    "expected_impact": "扩展受众定向",
                    "estimated_impact": {"cpi_reduction": 0.15},
                },
                {
                    "action_type": "change_audience",
                    "expected_impact": "测试新受众分组",
                    "estimated_impact": {"cpi_reduction": 0.10},
                },
            ],
            "requires_approval": False,
        },
    ],
    DiagnosisType.STORE_ISSUE: [
        {
            "strategy_type": StrategyType.OPTIMIZE_STORE,
            "description": "落地页/商店优化",
            "expected_impact": "预计 CVR 提升 10-20%",
            "actions": [
                {
                    "action_type": "optimize_store",
                    "expected_impact": "优化商店页面转化率",
                    "estimated_impact": {"cvr_improvement": 0.15},
                },
            ],
            "requires_approval": True,
        },
    ],
    DiagnosisType.CPI_SPIKE: [
        {
            "strategy_type": StrategyType.OPTIMIZE_BID,
            "description": "CPI 突增，调整出价策略",
            "expected_impact": "预计 CPI 降低 15-25%",
            "actions": [
                {
                    "action_type": "adjust_bid",
                    "expected_impact": "降低出价",
                    "estimated_impact": {"cpi_reduction": 0.20},
                },
                {
                    "action_type": "reduce_budget",
                    "expected_impact": "降低日预算",
                    "estimated_impact": {"spend_reduction": 0.20},
                },
            ],
            "requires_approval": False,
        },
    ],
    DiagnosisType.ROAS_DECLINE: [
        {
            "strategy_type": StrategyType.ADJUST_BUDGET,
            "description": "ROAS 下降，调整预算分配",
            "expected_impact": "预计 ROAS 提升 10-15%",
            "actions": [
                {
                    "action_type": "reallocate_budget",
                    "expected_impact": "重新分配预算",
                    "estimated_impact": {"roas_improvement": 0.10},
                },
                {
                    "action_type": "reduce_budget",
                    "expected_impact": "降低低效系列预算",
                    "estimated_impact": {"roas_improvement": 0.05},
                },
            ],
            "requires_approval": False,
        },
    ],
    DiagnosisType.BUDGET_INEFFICIENCY: [
        {
            "strategy_type": StrategyType.REALLOCATE_BUDGET,
            "description": "预算低效，重新分配",
            "expected_impact": "预计提升预算效率 20-30%",
            "actions": [
                {
                    "action_type": "pause_low_performers",
                    "expected_impact": "暂停低效系列",
                    "estimated_impact": {"roas_improvement": 0.15},
                },
                {
                    "action_type": "reallocate_to_winners",
                    "expected_impact": "预算转移到高ROAS系列",
                    "estimated_impact": {"roas_improvement": 0.15},
                },
            ],
            "requires_approval": False,
        },
    ],
    DiagnosisType.PAYER_DECLINE: [
        {
            "strategy_type": StrategyType.ESCALATE_TO_SUPERVISOR,
            "description": "付费率下降，升级给 Monetization Agent",
            "expected_impact": "需要 Monetization Agent 介入",
            "actions": [
                {
                    "action_type": "escalate_to_monetization",
                    "expected_impact": "升级付费问题",
                    "estimated_impact": {},
                },
            ],
            "requires_approval": True,
        },
    ],
    DiagnosisType.RETENTION_DECLINE: [
        {
            "strategy_type": StrategyType.ESCALATE_TO_SUPERVISOR,
            "description": "留存下降，升级给 Product Agent",
            "expected_impact": "需要 Product Agent 介入",
            "actions": [
                {
                    "action_type": "escalate_to_product",
                    "expected_impact": "升级留存问题",
                    "estimated_impact": {},
                },
            ],
            "requires_approval": True,
        },
    ],
    DiagnosisType.LTV_DECLINE: [
        {
            "strategy_type": StrategyType.ADJUST_BUDGET,
            "description": "LTV 下降，调整投放策略",
            "expected_impact": "缩量保护利润",
            "actions": [
                {
                    "action_type": "decrease_budget",
                    "expected_impact": "降低预算",
                    "estimated_impact": {"spend_reduction": 0.20},
                },
                {
                    "action_type": "pause_negative_roi",
                    "expected_impact": "暂停负ROI系列",
                    "estimated_impact": {"roi_improvement": 0.10},
                },
            ],
            "requires_approval": False,
        },
    ],
    DiagnosisType.HEALTHY: [
        {
            "strategy_type": StrategyType.MONITOR_ONLY,
            "description": "指标正常，继续监控",
            "expected_impact": "维持当前策略",
            "actions": [],
            "requires_approval": False,
        },
    ],
    DiagnosisType.UNKNOWN: [
        {
            "strategy_type": StrategyType.ESCALATE_TO_SUPERVISOR,
            "description": "未知问题，升级给 Supervisor",
            "expected_impact": "需要 Supervisor 人工决策",
            "actions": [
                {
                    "action_type": "escalate_to_supervisor",
                    "expected_impact": "升级给主管",
                    "estimated_impact": {},
                },
            ],
            "requires_approval": True,
        },
    ],
}


# ═══════════════════════════════════════════════════════════════
# UA Strategy Engine
# ═══════════════════════════════════════════════════════════════


class UAStrategyEngine:
    """UA 策略引擎 — 将诊断转换为增长策略.

    用法:
        engine = UAStrategyEngine()
        strategies = engine.generate_strategies(diagnoses)
    """

    def __init__(self):
        self._history: list[UAStrategy] = []

    # ── 策略生成 ──────────────────────────────────────────────

    def generate_strategies(
        self,
        diagnoses: list[UADiagnosis],
        campaign_id: str = "",
        product_id: str = "",
    ) -> list[UAStrategy]:
        """根据诊断生成策略.

        Args:
            diagnoses: 诊断列表
            campaign_id: 广告系列 ID
            product_id: 产品 ID

        Returns:
            策略列表 (按优先级排序)
        """
        strategies = []

        for diagnosis in diagnoses:
            strategy_templates = DIAGNOSIS_TO_STRATEGY.get(
                diagnosis.issue_type,
                DIAGNOSIS_TO_STRATEGY[DiagnosisType.UNKNOWN],
            )

            for template in strategy_templates:
                strategy = self._build_strategy(
                    template, diagnosis, campaign_id, product_id
                )
                strategies.append(strategy)

        # 按优先级排序
        strategies.sort(key=lambda s: s.priority, reverse=True)
        self._history.extend(strategies)
        return strategies

    def generate_for_diagnosis(
        self,
        diagnosis: UADiagnosis,
        campaign_id: str = "",
        product_id: str = "",
    ) -> list[UAStrategy]:
        """为单个诊断生成策略."""
        return self.generate_strategies([diagnosis], campaign_id, product_id)

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_strategy(
        self,
        template: dict[str, Any],
        diagnosis: UADiagnosis,
        campaign_id: str,
        product_id: str,
    ) -> UAStrategy:
        """根据模板构建策略."""
        actions = self._build_actions(template.get("actions", []), campaign_id)

        # 优先级 = 诊断严重度权重 × 诊断置信度
        severity_weights = {
            DiagnosisSeverity.CRITICAL: 1.0,
            DiagnosisSeverity.HIGH: 0.8,
            DiagnosisSeverity.MEDIUM: 0.5,
            DiagnosisSeverity.LOW: 0.2,
        }
        priority = severity_weights.get(diagnosis.severity, 0.5) * diagnosis.confidence

        return UAStrategy(
            strategy_type=template["strategy_type"],
            description=template["description"],
            diagnosis=diagnosis,
            expected_impact=template["expected_impact"],
            actions=actions,
            priority=priority,
            confidence=diagnosis.confidence,
            requires_approval=template.get("requires_approval", False),
            metadata={
                "campaign_id": campaign_id,
                "product_id": product_id,
                "diagnosis_type": diagnosis.issue_type.value,
            },
        )

    def _build_actions(
        self,
        action_templates: list[dict[str, Any]],
        campaign_id: str,
    ) -> list[StrategyAction]:
        """构建动作列表."""
        actions = []
        for at in action_templates:
            action = StrategyAction(
                action_type=at["action_type"],
                target=campaign_id,
                parameters=at.get("parameters", {}),
                expected_impact=at["expected_impact"],
                estimated_impact=at.get("estimated_impact", {}),
                confidence=at.get("confidence", 0.0),
            )
            actions.append(action)
        return actions

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 10) -> list[UAStrategy]:
        return self._history[-n:]

    def get_top_strategies(self, n: int = 3) -> list[UAStrategy]:
        sorted_strategies = sorted(
            self._history, key=lambda s: s.priority, reverse=True
        )
        return sorted_strategies[:n]

    def reset(self) -> None:
        self._history.clear()