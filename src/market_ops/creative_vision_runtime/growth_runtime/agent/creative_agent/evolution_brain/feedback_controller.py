"""E14.6.3 Evolution Feedback Controller — 进化反馈控制器.

E14.6 最后闭环节点 — 将实验报告转化为进化记忆、基因组适应度、下一轮进化信号.

职责:
  1. 将 ExperimentReport (E14.6.2) 转换为 EvolutionFeedback
  2. 更新 Genome Fitness (E11.3.1 FitnessScore)
  3. 生成 Memory Pattern 写入 E14.5.6 EvolutionMemoryGraph
  4. 生成下一轮 EvolutionSignal 供 E14.5.3 EvolutionPlanner 使用
  5. Winner Promotion / Loser Suppression / Exploration Signal

核心概念:
  - EvolutionFeedback: 单个基因组的进化反馈
  - MemoryPattern: 从实验中学到的模式 (写入 EvolutionMemoryGraph)
  - EvolutionSignal: 下一轮进化方向信号 (供 EvolutionPlanner 使用)
  - FeedbackReport: 汇总反馈报告

数据流:
  ExperimentReport (E14.6.2)
       ↓
  EvolutionFeedbackController.process_report()
       ↓
  ├─ EvolutionFeedback[] (每个基因组一条反馈)
  ├─ MemoryPattern[] (写入 E14.5.6)
  ├─ EvolutionSignal[] (下一轮 E14.5.3)
  └─ FeedbackReport (汇总)
       ↓
  E14.5.6 EvolutionMemoryGraph ← MemoryPattern
  E14.5.3 EvolutionPlanner ← EvolutionSignal
  E11.3.1 FitnessScore ← 更新适应度
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.experiment_controller import (
    ExperimentReport,
    ExperimentResult,
    GroupType,
    ExperimentStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_memory import (
    EvolutionMemoryGraph,
    EvolutionNode,
    EvolutionEdge,
    NodeType,
    EdgeType,
)
from market_ops.e11.evolution.fitness_schema import (
    FitnessScore,
    FitnessMetric,
    FitnessDirection,
    FitnessSnapshot,
)


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class FeedbackType(str, Enum):
    """进化反馈类型.

    WINNER_PROMOTION  — 强化赢家 DNA (amplify)
    LOSER_SUPPRESSION — 降低失败 DNA (suppress)
    PATTERN_LEARNED   — 形成进化经验 (pattern)
    EXPLORATION_SIGNAL— 探索新方向 (explore)
    NO_SIGNAL         — 数据不足，无信号
    """
    WINNER_PROMOTION = "winner_promotion"
    LOSER_SUPPRESSION = "loser_suppression"
    PATTERN_LEARNED = "pattern_learned"
    EXPLORATION_SIGNAL = "exploration_signal"
    NO_SIGNAL = "no_signal"


class SignalAction(str, Enum):
    """下一轮进化信号的动作类型."""
    AMPLIFY = "amplify"       # 放大该基因方向
    SUPPRESS = "suppress"     # 抑制该基因方向
    EXPLORE = "explore"       # 探索新方向
    MAINTAIN = "maintain"     # 维持现状
    RETEST = "retest"         # 需要更多数据


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionFeedback:
    """单个基因组的进化反馈.

    代表一次实验后对该基因组的进化建议.

    Attributes:
        feedback_id: 反馈 ID
        experiment_id: 来源实验 ID
        genome_id: 目标基因组 ID
        feedback_type: 反馈类型
        fitness_score: 适应度评分
        reward: 奖励值 (roas lift, 可正可负)
        confidence: 置信度
        mutation_direction: 建议变异方向
        recommendation: 文字建议
        created_at: 创建时间
    """
    feedback_id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:8]}")
    experiment_id: str = ""
    genome_id: str = ""
    feedback_type: FeedbackType = FeedbackType.NO_SIGNAL
    fitness_score: float = 0.0
    reward: float = 0.0
    confidence: float = 0.0
    mutation_direction: str = ""
    recommendation: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "experiment_id": self.experiment_id,
            "genome_id": self.genome_id,
            "feedback_type": self.feedback_type.value,
            "fitness_score": round(self.fitness_score, 4),
            "reward": round(self.reward, 4),
            "confidence": round(self.confidence, 4),
            "mutation_direction": self.mutation_direction,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionFeedback:
        return cls(
            feedback_id=data.get("feedback_id", ""),
            experiment_id=data.get("experiment_id", ""),
            genome_id=data.get("genome_id", ""),
            feedback_type=FeedbackType(data.get("feedback_type", "no_signal")),
            fitness_score=data.get("fitness_score", 0.0),
            reward=data.get("reward", 0.0),
            confidence=data.get("confidence", 0.0),
            mutation_direction=data.get("mutation_direction", ""),
            recommendation=data.get("recommendation", ""),
            created_at=data.get("created_at", ""),
        )


@dataclass
class MemoryPattern:
    """从实验中学习到的模式 — 连接 E14.5.6 EvolutionMemoryGraph.

    例如:
        实验: hook_strength +30%
        结果: ROAS +34%
        模式: hook_strength_increase → positive → confidence 0.91

    Attributes:
        pattern_id: 模式 ID
        pattern_name: 模式名称
        pattern_type: 模式类型 (gene_amplify / gene_suppress / context_effect)
        source_genome_ids: 来源基因组 ID
        source_experiment_id: 来源实验 ID
        gene_category: 基因类别
        direction: 变异方向
        reward: 奖励值
        confidence: 置信度
        sample_size: 样本量
        created_at: 创建时间
    """
    pattern_id: str = field(default_factory=lambda: f"mp_{uuid.uuid4().hex[:8]}")
    pattern_name: str = ""
    pattern_type: str = ""
    source_genome_ids: list[str] = field(default_factory=list)
    source_experiment_id: str = ""
    gene_category: str = ""
    direction: str = ""
    reward: float = 0.0
    confidence: float = 0.0
    sample_size: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "source_genome_ids": self.source_genome_ids,
            "source_experiment_id": self.source_experiment_id,
            "gene_category": self.gene_category,
            "direction": self.direction,
            "reward": round(self.reward, 4),
            "confidence": round(self.confidence, 4),
            "sample_size": self.sample_size,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryPattern:
        return cls(
            pattern_id=data.get("pattern_id", ""),
            pattern_name=data.get("pattern_name", ""),
            pattern_type=data.get("pattern_type", ""),
            source_genome_ids=data.get("source_genome_ids", []),
            source_experiment_id=data.get("source_experiment_id", ""),
            gene_category=data.get("gene_category", ""),
            direction=data.get("direction", ""),
            reward=data.get("reward", 0.0),
            confidence=data.get("confidence", 0.0),
            sample_size=data.get("sample_size", 0),
            created_at=data.get("created_at", ""),
        )


@dataclass
class EvolutionSignal:
    """下一轮进化方向信号 — 供 E14.5.3 EvolutionPlanner 使用.

    例如:
        Winner: genome_023, hook=rescue, ROAS=1.34
        信号: AMPLIFY hook=rescue, confidence=0.92

    Attributes:
        signal_id: 信号 ID
        action: 建议动作 (AMPLIFY / SUPPRESS / EXPLORE / MAINTAIN / RETEST)
        gene_category: 目标基因类别
        target_value: 目标基因值 (如 "rescue", "transformation")
        confidence: 置信度
        expected_impact: 预期影响
        source_feedback_id: 来源反馈 ID
        source_experiment_id: 来源实验 ID
        created_at: 创建时间
    """
    signal_id: str = field(default_factory=lambda: f"sig_{uuid.uuid4().hex[:8]}")
    action: SignalAction = SignalAction.MAINTAIN
    gene_category: str = ""
    target_value: str = ""
    confidence: float = 0.0
    expected_impact: str = ""
    source_feedback_id: str = ""
    source_experiment_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "action": self.action.value,
            "gene_category": self.gene_category,
            "target_value": self.target_value,
            "confidence": round(self.confidence, 4),
            "expected_impact": self.expected_impact,
            "source_feedback_id": self.source_feedback_id,
            "source_experiment_id": self.source_experiment_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionSignal:
        return cls(
            signal_id=data.get("signal_id", ""),
            action=SignalAction(data.get("action", "maintain")),
            gene_category=data.get("gene_category", ""),
            target_value=data.get("target_value", ""),
            confidence=data.get("confidence", 0.0),
            expected_impact=data.get("expected_impact", ""),
            source_feedback_id=data.get("source_feedback_id", ""),
            source_experiment_id=data.get("source_experiment_id", ""),
            created_at=data.get("created_at", ""),
        )


@dataclass
class FeedbackReport:
    """进化反馈汇总报告.

    Attributes:
        report_id: 报告 ID
        experiment_id: 来源实验 ID
        experiment_name: 实验名称
        total_feedbacks: 总反馈数
        winner_promotions: Winner 推广数
        loser_suppressions: Loser 抑制数
        patterns_learned: 学习到的模式数
        signals_generated: 生成的信号数
        feedbacks: 所有反馈
        patterns: 所有模式
        signals: 所有信号
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: f"fbr_{uuid.uuid4().hex[:8]}")
    experiment_id: str = ""
    experiment_name: str = ""
    total_feedbacks: int = 0
    winner_promotions: int = 0
    loser_suppressions: int = 0
    patterns_learned: int = 0
    signals_generated: int = 0
    feedbacks: list[EvolutionFeedback] = field(default_factory=list)
    patterns: list[MemoryPattern] = field(default_factory=list)
    signals: list[EvolutionSignal] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def has_winner_signal(self) -> bool:
        return self.winner_promotions > 0

    @property
    def has_actionable_signals(self) -> bool:
        return self.signals_generated > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "total_feedbacks": self.total_feedbacks,
            "winner_promotions": self.winner_promotions,
            "loser_suppressions": self.loser_suppressions,
            "patterns_learned": self.patterns_learned,
            "signals_generated": self.signals_generated,
            "has_winner_signal": self.has_winner_signal,
            "has_actionable_signals": self.has_actionable_signals,
            "feedbacks": [f.to_dict() for f in self.feedbacks],
            "patterns": [p.to_dict() for p in self.patterns],
            "signals": [s.to_dict() for s in self.signals],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# EvolutionFeedbackController — 核心引擎
# ═══════════════════════════════════════════════════════════

class EvolutionFeedbackController:
    """进化反馈控制器 — 实验报告 → 进化记忆 + 适应度 + 下一轮信号.

    核心职责:
      1. 解析 ExperimentReport 生成 EvolutionFeedback
      2. 更新 Genome Fitness (E11.3.1)
      3. 生成 MemoryPattern 写入 EvolutionMemoryGraph (E14.5.6)
      4. 生成 EvolutionSignal 供 EvolutionPlanner (E14.5.3) 使用
      5. Winner Promotion / Loser Suppression / Exploration Signal

    用法:
        controller = EvolutionFeedbackController(memory_graph)
        feedback_report = controller.process_report(experiment_report)
        print(f"生成 {feedback_report.signals_generated} 个进化信号")
    """

    # 阈值配置
    WINNER_LIFT_THRESHOLD = 0.05     # Winner lift > 5% 才触发 PROMOTION
    LOSER_LIFT_THRESHOLD = -0.05     # Loser lift < -5% 才触发 SUPPRESSION
    MIN_CONFIDENCE = 0.5             # 最低置信度
    MIN_SAMPLE_SIZE = 1000           # 最低样本量

    def __init__(
        self,
        memory_graph: EvolutionMemoryGraph | None = None,
        winner_threshold: float = 0.05,
        loser_threshold: float = -0.05,
        min_confidence: float = 0.5,
        min_sample_size: int = 1000,
    ):
        self._memory_graph = memory_graph or EvolutionMemoryGraph()
        self._winner_threshold = winner_threshold
        self._loser_threshold = loser_threshold
        self._min_confidence = min_confidence
        self._min_sample_size = min_sample_size
        self._feedbacks: dict[str, EvolutionFeedback] = {}
        self._patterns: dict[str, MemoryPattern] = {}
        self._signals: dict[str, EvolutionSignal] = {}
        self._fitness_snapshots: dict[str, FitnessSnapshot] = {}

    # ── 核心: 处理实验报告 ──────────────────────────────────

    def process_report(self, report: ExperimentReport) -> FeedbackReport:
        """处理 ExperimentReport 生成完整反馈闭环.

        Args:
            report: E14.6.2 产生的实验报告

        Returns:
            FeedbackReport: 包含 feedbacks, patterns, signals 的汇总报告
        """
        feedbacks: list[EvolutionFeedback] = []
        patterns: list[MemoryPattern] = []
        signals: list[EvolutionSignal] = []

        if not report.results:
            return FeedbackReport(
                experiment_id=report.experiment_id,
                experiment_name=report.experiment_name,
                summary="无实验结果数据，无法生成反馈",
            )

        # 计算对照组基线
        control_baseline = self._compute_control_baseline(report)

        # Step 1: 为每个实验结果生成反馈
        for result in report.results:
            feedback = self._process_single_result(result, report, control_baseline)
            feedbacks.append(feedback)
            self._feedbacks[feedback.feedback_id] = feedback

        # Step 2: 生成 Memory Patterns
        patterns = self._generate_memory_patterns(report, feedbacks)
        for p in patterns:
            self._patterns[p.pattern_id] = p
            self._write_pattern_to_memory(p)

        # Step 3: 生成 Evolution Signals
        signals = self._generate_evolution_signals(report, feedbacks, patterns)
        for s in signals:
            self._signals[s.signal_id] = s

        # Step 4: 更新 Fitness
        self._update_genome_fitness(report)

        # 汇总统计
        winner_count = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.WINNER_PROMOTION)
        loser_count = sum(1 for f in feedbacks if f.feedback_type == FeedbackType.LOSER_SUPPRESSION)

        summary = (
            f"实验 {report.experiment_name}: "
            f"生成 {len(feedbacks)} 条反馈, "
            f"{winner_count} 个 Winner Promotion, "
            f"{loser_count} 个 Loser Suppression, "
            f"{len(patterns)} 个 Memory Pattern, "
            f"{len(signals)} 个 Evolution Signal"
        )

        return FeedbackReport(
            experiment_id=report.experiment_id,
            experiment_name=report.experiment_name,
            total_feedbacks=len(feedbacks),
            winner_promotions=winner_count,
            loser_suppressions=loser_count,
            patterns_learned=len(patterns),
            signals_generated=len(signals),
            feedbacks=feedbacks,
            patterns=patterns,
            signals=signals,
            summary=summary,
        )

    # ── Step 1: 单结果处理 ──────────────────────────────────

    def _process_single_result(
        self,
        result: ExperimentResult,
        report: ExperimentReport,
        control_baseline: dict[str, float],
    ) -> EvolutionFeedback:
        """处理单个实验结果，生成反馈.

        Args:
            result: 单个基因组实验结果
            report: 所属实验报告
            control_baseline: 对照组基线指标

        Returns:
            EvolutionFeedback: 进化反馈
        """
        # 计算 reward: 相对对照组的 ROAS lift
        control_roas = control_baseline.get("roas", 0.0)
        result_roas = result.roas
        reward = (result_roas - control_roas) / max(control_roas, 0.001) if control_roas > 0 else 0.0

        # 判定反馈类型
        feedback_type = self._determine_feedback_type(result, reward, report)

        # 生成建议
        recommendation = self._generate_recommendation(result, feedback_type, reward)

        # 置信度: 基于统计显著性和样本量
        confidence = min(result.statistical_significance or 0.5, 0.99)
        if result.sample_size < self._min_sample_size:
            confidence *= 0.5  # 样本量不足时降低置信度

        return EvolutionFeedback(
            experiment_id=report.experiment_id,
            genome_id=result.genome_id,
            feedback_type=feedback_type,
            fitness_score=result.score,
            reward=reward,
            confidence=confidence,
            mutation_direction=self._extract_mutation_direction(result),
            recommendation=recommendation,
        )

    def _determine_feedback_type(
        self,
        result: ExperimentResult,
        reward: float,
        report: ExperimentReport,
    ) -> FeedbackType:
        """判定反馈类型."""
        # Winner: 被标记为 winner 或 reward 超过阈值
        if result.is_winner or reward >= self._winner_threshold:
            return FeedbackType.WINNER_PROMOTION

        # Loser: reward 低于负阈值
        if reward <= self._loser_threshold:
            return FeedbackType.LOSER_SUPPRESSION

        # Variant 有数据但无明显差异 → 探索信号
        if result.group_type == GroupType.VARIANT and result.sample_size >= self._min_sample_size:
            return FeedbackType.EXPLORATION_SIGNAL

        # 对照组有数据 → 模式学习
        if result.group_type == GroupType.CONTROL and result.sample_size >= self._min_sample_size:
            return FeedbackType.PATTERN_LEARNED

        return FeedbackType.NO_SIGNAL

    def _generate_recommendation(
        self,
        result: ExperimentResult,
        feedback_type: FeedbackType,
        reward: float,
    ) -> str:
        """生成文字建议."""
        if feedback_type == FeedbackType.WINNER_PROMOTION:
            return (
                f"AMPLIFY: {result.genome_id} ROAS lift=+{reward*100:.1f}%, "
                f"score={result.score:.3f}, 建议放大该基因方向"
            )
        elif feedback_type == FeedbackType.LOSER_SUPPRESSION:
            return (
                f"SUPPRESS: {result.genome_id} ROAS lift={reward*100:.1f}%, "
                f"score={result.score:.3f}, 建议降低该基因权重"
            )
        elif feedback_type == FeedbackType.EXPLORATION_SIGNAL:
            return (
                f"EXPLORE: {result.genome_id} 数据不足, "
                f"ROAS={result.roas:.2f}, CTR={result.ctr:.3f}, 建议继续探索"
            )
        else:
            return f"NO_SIGNAL: {result.genome_id} 样本量不足或无显著差异"

    def _extract_mutation_direction(self, result: ExperimentResult) -> str:
        """从结果指标中提取变异方向描述."""
        parts = []
        if result.roas > 0:
            parts.append(f"roas_{result.roas:.2f}")
        if result.ctr > 0:
            parts.append(f"ctr_{result.ctr*100:.1f}%")
        if result.payer_rate > 0:
            parts.append(f"payer_{result.payer_rate*100:.1f}%")
        return "_".join(parts) if parts else "unknown"

    # ── Step 2: Memory Pattern ──────────────────────────────

    def _generate_memory_patterns(
        self,
        report: ExperimentReport,
        feedbacks: list[EvolutionFeedback],
    ) -> list[MemoryPattern]:
        """从反馈中生成 Memory Patterns.

        Returns:
            list[MemoryPattern]: 可写入 EvolutionMemoryGraph 的模式列表
        """
        patterns: list[MemoryPattern] = []

        # 1. Winner Pattern: 从 Winner 反馈中提取模式
        for fb in feedbacks:
            if fb.feedback_type == FeedbackType.WINNER_PROMOTION:
                p = MemoryPattern(
                    pattern_name=f"winner_{fb.genome_id}",
                    pattern_type="gene_amplify",
                    source_genome_ids=[fb.genome_id],
                    source_experiment_id=report.experiment_id,
                    gene_category="",  # 后续可从 genome 基因中提取
                    direction="amplify",
                    reward=fb.reward,
                    confidence=fb.confidence,
                    sample_size=0,
                )
                patterns.append(p)

        # 2. Loser Pattern: 从 Loser 反馈中提取模式
        for fb in feedbacks:
            if fb.feedback_type == FeedbackType.LOSER_SUPPRESSION:
                p = MemoryPattern(
                    pattern_name=f"loser_{fb.genome_id}",
                    pattern_type="gene_suppress",
                    source_genome_ids=[fb.genome_id],
                    source_experiment_id=report.experiment_id,
                    gene_category="",
                    direction="suppress",
                    reward=fb.reward,
                    confidence=fb.confidence,
                    sample_size=0,
                )
                patterns.append(p)

        # 3. Experiment-level Pattern: 整个实验的模式
        if report.has_winner:
            winner_fb = next((f for f in feedbacks if f.genome_id == report.winner_genome_id), None)
            if winner_fb:
                p = MemoryPattern(
                    pattern_name=f"experiment_{report.experiment_id}",
                    pattern_type="experiment_summary",
                    source_genome_ids=[report.winner_genome_id],
                    source_experiment_id=report.experiment_id,
                    gene_category="",
                    direction=f"winner_lift_{report.winner_lift*100:.1f}%",
                    reward=report.winner_lift,
                    confidence=winner_fb.confidence,
                    sample_size=0,
                )
                patterns.append(p)

        return patterns

    def _write_pattern_to_memory(self, pattern: MemoryPattern) -> EvolutionNode:
        """将 MemoryPattern 写入 EvolutionMemoryGraph (E14.5.6).

        Args:
            pattern: 学习到的模式

        Returns:
            EvolutionNode: 创建的模式节点
        """
        return self._memory_graph.record_pattern(
            pattern_id=pattern.pattern_id,
            pattern_name=pattern.pattern_name,
            source_genome_ids=pattern.source_genome_ids,
            pattern_type=pattern.pattern_type,
            confidence=pattern.confidence,
            label=f"Pattern: {pattern.pattern_name} (reward={pattern.reward:.3f})",
        )

    # ── Step 3: Evolution Signal ────────────────────────────

    def _generate_evolution_signals(
        self,
        report: ExperimentReport,
        feedbacks: list[EvolutionFeedback],
        patterns: list[MemoryPattern],
    ) -> list[EvolutionSignal]:
        """生成下一轮进化信号 — 供 E14.5.3 EvolutionPlanner 使用.

        Returns:
            list[EvolutionSignal]: 下一轮进化方向信号
        """
        signals: list[EvolutionSignal] = []

        # 1. Winner Promotion Signal
        for fb in feedbacks:
            if fb.feedback_type == FeedbackType.WINNER_PROMOTION:
                s = EvolutionSignal(
                    action=SignalAction.AMPLIFY,
                    gene_category="",  # 后续可从 genome 基因中提取
                    target_value=fb.mutation_direction,
                    confidence=fb.confidence,
                    expected_impact=f"预期 ROAS lift +{fb.reward*100:.1f}% (基于实验 {report.experiment_id})",
                    source_feedback_id=fb.feedback_id,
                    source_experiment_id=report.experiment_id,
                )
                signals.append(s)

        # 2. Loser Suppression Signal
        for fb in feedbacks:
            if fb.feedback_type == FeedbackType.LOSER_SUPPRESSION:
                s = EvolutionSignal(
                    action=SignalAction.SUPPRESS,
                    gene_category="",
                    target_value=fb.mutation_direction,
                    confidence=fb.confidence,
                    expected_impact=f"预期避免 ROAS 损失 {abs(fb.reward)*100:.1f}%",
                    source_feedback_id=fb.feedback_id,
                    source_experiment_id=report.experiment_id,
                )
                signals.append(s)

        # 3. Exploration Signal: 如果无 Winner 但有足够数据
        if not report.has_winner and any(
            f.feedback_type == FeedbackType.EXPLORATION_SIGNAL for f in feedbacks
        ):
            s = EvolutionSignal(
                action=SignalAction.EXPLORE,
                gene_category="",
                target_value="new_direction",
                confidence=0.5,
                expected_impact=f"探索新方向 (实验 {report.experiment_name} 无显著 Winner)",
                source_feedback_id="",
                source_experiment_id=report.experiment_id,
            )
            signals.append(s)

        # 4. Retest Signal: 样本量不足
        low_sample_results = [f for f in feedbacks if f.feedback_type == FeedbackType.NO_SIGNAL]
        if low_sample_results and not signals:
            s = EvolutionSignal(
                action=SignalAction.RETEST,
                gene_category="",
                target_value="increase_sample",
                confidence=0.3,
                expected_impact=f"需要更多数据 (当前实验 {report.experiment_name} 样本量不足)",
                source_feedback_id="",
                source_experiment_id=report.experiment_id,
            )
            signals.append(s)

        return signals

    # ── Step 4: Fitness Update ──────────────────────────────

    def _update_genome_fitness(self, report: ExperimentReport) -> dict[str, FitnessSnapshot]:
        """更新基因组适应度评分.

        将实验结果中的性能指标转换为 FitnessScore 并记录快照.

        Args:
            report: 实验报告

        Returns:
            dict[genome_id, FitnessSnapshot]: 更新后的适应度快照
        """
        snapshots: dict[str, FitnessSnapshot] = {}

        for result in report.results:
            metrics = self._build_fitness_metrics(result)
            fitness = FitnessScore(
                genome_id=result.genome_id,
                metrics=metrics,
            )

            snapshot = FitnessSnapshot(
                genome_id=result.genome_id,
                fitness_score=fitness,
            )

            snapshots[result.genome_id] = snapshot
            self._fitness_snapshots[result.genome_id] = snapshot

            # 同时记录到 EvolutionMemoryGraph
            self._memory_graph.record_genome(
                genome_id=result.genome_id,
                fitness={
                    "score": fitness.score,
                    "roas": result.roas,
                    "ctr": result.ctr,
                    "cvr": result.cvr,
                    "payer_rate": result.payer_rate,
                    "cpi": result.cpi,
                },
            )

        return snapshots

    def _build_fitness_metrics(self, result: ExperimentResult) -> list[FitnessMetric]:
        """从实验结果构建 FitnessMetric 列表.

        使用 E11.6.3 加权公式: revenue×0.4 + efficiency×0.3 + payer×0.3
        """
        metrics = []

        # ROAS (收入维度, 权重 0.4)
        if result.roas > 0:
            metrics.append(FitnessMetric(
                name="roas",
                value=min(result.roas, 1.0),
                weight=0.4,
                direction=FitnessDirection.MAXIMIZE,
            ))

        # CTR (效率维度, 权重 0.15)
        if result.ctr > 0:
            metrics.append(FitnessMetric(
                name="ctr",
                value=min(result.ctr * 10, 1.0),
                weight=0.15,
                direction=FitnessDirection.MAXIMIZE,
            ))

        # CVR (效率维度, 权重 0.15)
        if result.cvr > 0:
            metrics.append(FitnessMetric(
                name="cvr",
                value=min(result.cvr, 1.0),
                weight=0.15,
                direction=FitnessDirection.MAXIMIZE,
            ))

        # Payer Rate (付费维度, 权重 0.3)
        if result.payer_rate > 0:
            metrics.append(FitnessMetric(
                name="payer_rate",
                value=min(result.payer_rate, 1.0),
                weight=0.3,
                direction=FitnessDirection.MAXIMIZE,
            ))

        # CPI (成本维度, MINIMIZE)
        if result.cpi > 0:
            normalized_cpi = min(result.cpi / 10.0, 1.0)
            metrics.append(FitnessMetric(
                name="cpi",
                value=normalized_cpi,
                weight=0.1,
                direction=FitnessDirection.MINIMIZE,
            ))

        if not metrics:
            metrics = [FitnessMetric(
                name="default",
                value=0.0,
                weight=1.0,
                direction=FitnessDirection.MAXIMIZE,
            )]

        return metrics

    # ── 辅助: 对照组基线 ──────────────────────────────────

    def _compute_control_baseline(self, report: ExperimentReport) -> dict[str, float]:
        """计算对照组基线指标 (平均值).

        Args:
            report: 实验报告

        Returns:
            dict: {metric_name: avg_value}
        """
        control_results = report.control_results
        if not control_results:
            return {}

        baseline: dict[str, float] = {}
        metric_keys = ["roas", "ctr", "cvr", "cpi", "payer_rate", "d1_retention", "d7_retention"]

        for key in metric_keys:
            values = [r.metrics.get(key, 0.0) for r in control_results if key in r.metrics]
            if values:
                baseline[key] = sum(values) / len(values)

        return baseline

    # ── 查询 ──────────────────────────────────────────────

    def get_feedback(self, feedback_id: str) -> EvolutionFeedback | None:
        """获取反馈."""
        return self._feedbacks.get(feedback_id)

    def get_pattern(self, pattern_id: str) -> MemoryPattern | None:
        """获取模式."""
        return self._patterns.get(pattern_id)

    def get_signal(self, signal_id: str) -> EvolutionSignal | None:
        """获取信号."""
        return self._signals.get(signal_id)

    def get_fitness_snapshot(self, genome_id: str) -> FitnessSnapshot | None:
        """获取适应度快照."""
        return self._fitness_snapshots.get(genome_id)

    def get_feedbacks_by_type(self, feedback_type: FeedbackType) -> list[EvolutionFeedback]:
        """按类型获取反馈."""
        return [f for f in self._feedbacks.values() if f.feedback_type == feedback_type]

    def get_winner_feedbacks(self) -> list[EvolutionFeedback]:
        """获取所有 Winner 反馈."""
        return self.get_feedbacks_by_type(FeedbackType.WINNER_PROMOTION)

    def get_loser_feedbacks(self) -> list[EvolutionFeedback]:
        """获取所有 Loser 反馈."""
        return self.get_feedbacks_by_type(FeedbackType.LOSER_SUPPRESSION)

    def get_signals_by_action(self, action: SignalAction) -> list[EvolutionSignal]:
        """按动作类型获取信号."""
        return [s for s in self._signals.values() if s.action == action]

    def get_amplify_signals(self) -> list[EvolutionSignal]:
        """获取所有 AMPLIFY 信号."""
        return self.get_signals_by_action(SignalAction.AMPLIFY)

    def get_suppress_signals(self) -> list[EvolutionSignal]:
        """获取所有 SUPPRESS 信号."""
        return self.get_signals_by_action(SignalAction.SUPPRESS)

    # ── 统计 ──────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取控制器统计信息."""
        return {
            "total_feedbacks": len(self._feedbacks),
            "total_patterns": len(self._patterns),
            "total_signals": len(self._signals),
            "total_fitness_snapshots": len(self._fitness_snapshots),
            "feedbacks_by_type": {
                t.value: len(self.get_feedbacks_by_type(t))
                for t in FeedbackType
            },
            "signals_by_action": {
                a.value: len(self.get_signals_by_action(a))
                for a in SignalAction
            },
            "winner_feedbacks": len(self.get_winner_feedbacks()),
            "loser_feedbacks": len(self.get_loser_feedbacks()),
            "amplify_signals": len(self.get_amplify_signals()),
            "suppress_signals": len(self.get_suppress_signals()),
        }

    def reset(self) -> None:
        """重置所有状态."""
        self._feedbacks.clear()
        self._patterns.clear()
        self._signals.clear()
        self._fitness_snapshots.clear()
        self._memory_graph = EvolutionMemoryGraph()

    # ── Memory Graph 访问 ──────────────────────────────────

    @property
    def memory_graph(self) -> EvolutionMemoryGraph:
        """获取关联的 EvolutionMemoryGraph."""
        return self._memory_graph


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_feedback_controller(
    memory_graph: EvolutionMemoryGraph | None = None,
    winner_threshold: float = 0.05,
    loser_threshold: float = -0.05,
) -> EvolutionFeedbackController:
    """创建默认 EvolutionFeedbackController."""
    return EvolutionFeedbackController(
        memory_graph=memory_graph,
        winner_threshold=winner_threshold,
        loser_threshold=loser_threshold,
    )