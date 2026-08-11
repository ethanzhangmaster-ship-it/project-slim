"""E12.3 — Product Intelligence Agent。

产品优化 Agent —— 消费 LifecycleSnapshot + FunnelSnapshot，
输出产品优化行动建议。

回答：
  - 哪个关卡导致流失？
  - 新手引导是否有效？
  - 哪个功能需要优化？
  - 流失用户怎么召回？

Usage:
    agent = ProductIntelligenceAgent()
    actions = agent.decide(lifecycle_snapshot, funnel_snapshot)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base_agent import ActionPriority, BaseAgent, OptimizationAction

if TYPE_CHECKING:
    from ...analyzers.lifecycle_analyzer import LifecycleSnapshot
    from ...analyzers.funnel_analyzer import FunnelSnapshot


class ProductOptimizationAction(OptimizationAction):
    """产品优化行动（带产品专属字段）。"""

    domain: str = "product"  # 优化域 (retention/funnel/activation/churn)
    affected_metric: str = ""  # 受影响指标 (如 D7_retention)


class ProductIntelligenceAgent(BaseAgent):
    """产品优化 Agent。

    消费 LifecycleSnapshot + FunnelSnapshot，
    输出 ProductOptimizationAction 列表。

    Attributes:
        total_decisions: 累计决策数
    """

    agent_type = "product"

    def _generate_actions(
        self,
        lifecycle: LifecycleSnapshot | None = None,
        funnel: FunnelSnapshot | None = None,
    ) -> list[OptimizationAction]:
        """生成产品优化行动。

        Args:
            lifecycle: 生命周期快照
            funnel:    漏斗快照

        Returns:
            ProductOptimizationAction 列表
        """
        actions: list[OptimizationAction] = []

        if lifecycle:
            actions.extend(self._analyze_lifecycle(lifecycle))

        if funnel:
            actions.extend(self._analyze_funnel(funnel))

        # 如果没有输入，生成 mock 建议
        if not lifecycle and not funnel:
            actions.extend(self._mock_actions())

        return actions

    # ── Lifecycle 分析 ──────────────────────────────────

    def _analyze_lifecycle(
        self,
        snapshot: LifecycleSnapshot,
    ) -> list[OptimizationAction]:
        """从生命周期快照生成行动。"""
        actions: list[OptimizationAction] = []

        # D1 留存低 → 优化新手引导
        if snapshot.d1_retention < 0.30:
            actions.append(self._create_action(
                action_type="fix_onboarding",
                target="new_player_tutorial",
                priority=ActionPriority.P1_HIGH,
                expected_impact=f"D1 留存 +{(0.40 - snapshot.d1_retention) * 100:.0f}%",
                confidence=0.80,
                evidence=[
                    f"当前 D1 留存 {snapshot.d1_retention:.0%}，低于 30% 基准",
                    f"教程完成率 {snapshot.tutorial_completion_rate:.0%}",
                ],
                recommendation=(
                    "优化新手引导流程：简化前 3 分钟体验，"
                    "增加引导奖励，确保玩家到达 'aha moment'"
                ),
                domain="activation",
                affected_metric="d1_retention",
            ))

        # D7 留存低 → 核心玩法问题
        if snapshot.d7_retention < 0.15:
            actions.append(self._create_action(
                action_type="fix_core_gameplay",
                target="core_loop",
                priority=ActionPriority.P0_CRITICAL,
                expected_impact=f"D7 留存 +{(0.25 - snapshot.d7_retention) * 100:.0f}%",
                confidence=0.75,
                evidence=[
                    f"当前 D7 留存 {snapshot.d7_retention:.0%}，低于 15% 危险线",
                    f"DAU={snapshot.dau}",
                ],
                recommendation=(
                    "排查第 2-7 天体验断点，检查核心循环是否有 "
                    "'玩 3 天就觉得没意思' 的问题"
                ),
                domain="retention",
                affected_metric="d7_retention",
            ))

        # D1→D7 衰减严重
        if snapshot.d1_retention > 0:
            decay = (snapshot.d1_retention - snapshot.d7_retention) / snapshot.d1_retention
            if decay > 0.50:
                actions.append(self._create_action(
                    action_type="fix_d1_d7_gap",
                    target="day_2_to_7_experience",
                    priority=ActionPriority.P1_HIGH,
                    expected_impact="D7 留存 +5%",
                    confidence=0.70,
                    evidence=[
                        f"D1→D7 流失率 {decay:.0%}，超过 50% 警戒线",
                        f"D1={snapshot.d1_retention:.0%} → D7={snapshot.d7_retention:.0%}",
                    ],
                    recommendation=(
                        "在第 2-7 天增加目标系统和每日任务，"
                        "建立用户回访理由"
                    ),
                    domain="retention",
                    affected_metric="d7_retention",
                ))

        # 流失风险用户多 → 召回策略
        if snapshot.churn_risk_rate > 0.20:
            actions.append(self._create_action(
                action_type="churn_recovery",
                target=f"churn_risk_users ({snapshot.churn_risk_count})",
                priority=ActionPriority.P1_HIGH,
                expected_impact="挽回 10-15% 流失用户",
                confidence=0.65,
                evidence=[
                    f"流失风险用户 {snapshot.churn_risk_count} 人 "
                    f"({snapshot.churn_risk_rate:.0%})",
                ],
                recommendation=(
                    "启动召回策略：推送通知 + 回归奖励 + "
                    "邮件触达，针对 7-30 天未登录用户"
                ),
                domain="churn",
                affected_metric="churn_rate",
            ))

        return actions

    # ── Funnel 分析 ─────────────────────────────────────

    def _analyze_funnel(
        self,
        snapshot: FunnelSnapshot,
    ) -> list[OptimizationAction]:
        """从漏斗快照生成行动。"""
        actions: list[OptimizationAction] = []

        # 流失最严重的步骤
        for step_name in snapshot.drop_off_steps:
            step = next(
                (s for s in snapshot.steps if s.step_name == step_name),
                None,
            )
            if step and step.drop_off_rate > 0.30:
                actions.append(self._create_action(
                    action_type="fix_funnel_drop",
                    target=step.step_name,
                    priority=ActionPriority.P1_HIGH if step.drop_off_rate > 0.50 else ActionPriority.P2_MEDIUM,
                    expected_impact=f"'{step.step_name}' 转化率 +{step.drop_off_rate * 50:.0f}%",
                    confidence=0.75,
                    evidence=[
                        f"'{step.step_name}' 流失率 {step.drop_off_rate:.0%}",
                        f"进入 {step.entered} → 完成 {step.completed}",
                        f"平均耗时 {step.avg_time_seconds:.0f} 秒",
                    ],
                    recommendation=self._funnel_fix_recommendation(step_name, step.drop_off_rate),
                    domain="funnel",
                    affected_metric="conversion_rate",
                ))

        # 首步转化率低
        if snapshot.steps:
            first = snapshot.steps[0]
            if first.conversion_rate < 0.80:
                actions.append(self._create_action(
                    action_type="fix_first_step",
                    target=first.step_name,
                    priority=ActionPriority.P1_HIGH,
                    expected_impact=f"首步转化 +{(0.90 - first.conversion_rate) * 100:.0f}%",
                    confidence=0.70,
                    evidence=[
                        f"首步 '{first.step_name}' 转化率仅 {first.conversion_rate:.0%}",
                    ],
                    recommendation=(
                        "检查安装到首次进入游戏的链路，"
                        "可能存在加载慢、崩溃或注册门槛"
                    ),
                    domain="funnel",
                    affected_metric="conversion_rate",
                ))

        # 整体转化率极低
        if snapshot.overall_conversion < 0.02:
            actions.append(self._create_action(
                action_type="systematic_funnel_review",
                target="entire_funnel",
                priority=ActionPriority.P0_CRITICAL,
                expected_impact="整体转化 +100%",
                confidence=0.60,
                evidence=[
                    f"整体转化率 {snapshot.overall_conversion:.2%}，极低",
                ],
                recommendation=(
                    "系统性优化整个漏斗，从安装到首次付费每个环节都需要审查"
                ),
                domain="funnel",
                affected_metric="overall_conversion",
            ))

        return actions

    @staticmethod
    def _funnel_fix_recommendation(step_name: str, drop_rate: float) -> str:
        """根据漏斗步骤生成修复建议。"""
        name = step_name.lower()
        if "教程" in step_name or "tutorial" in name:
            return "简化教程步骤，增加交互引导，确保核心玩法在前 60 秒展示"
        if "关" in step_name or "level" in name:
            return f"调整 {step_name} 难度曲线，检查数值是否合理，增加通关奖励"
        if "付费" in step_name or "purchase" in name.lower():
            return "增加首充礼包，降低首次付费门槛（如 $0.99 限时特惠）"
        if "安装" in step_name or "install" in name:
            return "检查安装包大小和初始化速度，优化首次启动体验"
        return f"优化 '{step_name}' 环节，减少用户流失"

    # ── Mock ───────────────────────────────────────────

    def _mock_actions(self) -> list[OptimizationAction]:
        """无输入时生成 mock 建议。"""
        return [
            self._create_action(
                action_type="fix_onboarding",
                target="new_player_tutorial",
                priority=ActionPriority.P1_HIGH,
                expected_impact="D1 留存 +10%",
                confidence=0.75,
                evidence=["D1 留存 28%，低于 30% 基准"],
                recommendation="优化新手引导前 3 分钟体验",
                domain="activation",
                affected_metric="d1_retention",
            ),
            self._create_action(
                action_type="fix_funnel_drop",
                target="第5关",
                priority=ActionPriority.P2_MEDIUM,
                expected_impact="转化率 +15%",
                confidence=0.70,
                evidence=["第5关流失率 45%"],
                recommendation="调整第5关难度，增加通关奖励",
                domain="funnel",
                affected_metric="conversion_rate",
            ),
        ]
