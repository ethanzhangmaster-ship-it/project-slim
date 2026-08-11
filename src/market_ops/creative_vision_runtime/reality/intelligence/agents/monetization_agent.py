"""E12.3 — Monetization Intelligence Agent。

商业化 Agent —— 消费 MonetizationSnapshot，
输出收入优化行动建议。

回答：
  - 付费率怎么提升？
  - 定价是否合理？
  - 哪个 Offer 需要优化？
  - 大R用户怎么维护？

Usage:
    agent = MonetizationIntelligenceAgent()
    actions = agent.decide(monetization_snapshot)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base_agent import ActionPriority, BaseAgent, OptimizationAction

if TYPE_CHECKING:
    from ...analyzers.monetization_analyzer import MonetizationSnapshot


class RevenueOptimizationAction(OptimizationAction):
    """收入优化行动（带商业化专属字段）。"""

    domain: str = "monetization"  # 优化域 (payer_rate/arpu/offer/ltv/whale)
    revenue_impact: float = 0.0   # 预估收入影响 (USD)


class MonetizationIntelligenceAgent(BaseAgent):
    """商业化 Agent。

    消费 MonetizationSnapshot，输出 RevenueOptimizationAction 列表。

    Attributes:
        total_decisions: 累计决策数
    """

    agent_type = "monetization"

    def _generate_actions(
        self,
        snapshot: MonetizationSnapshot | None = None,
    ) -> list[OptimizationAction]:
        """生成收入优化行动。

        Args:
            snapshot: 商业化快照

        Returns:
            RevenueOptimizationAction 列表
        """
        if not snapshot:
            return self._mock_actions()

        actions: list[OptimizationAction] = []

        # 1. 付费率优化
        actions.extend(self._analyze_payer_rate(snapshot))

        # 2. ARPPU / 定价优化
        actions.extend(self._analyze_arppu(snapshot))

        # 3. Offer 表现优化
        actions.extend(self._analyze_offers(snapshot))

        # 4. 大R用户维护
        actions.extend(self._analyze_whales(snapshot))

        # 5. 首充时间优化
        actions.extend(self._analyze_first_pay(snapshot))

        return actions

    # ── 付费率 ──────────────────────────────────────────

    def _analyze_payer_rate(
        self,
        snapshot: MonetizationSnapshot,
    ) -> list[OptimizationAction]:
        """分析付费率。"""
        actions: list[OptimizationAction] = []

        if snapshot.payer_rate < 0.02:
            actions.append(self._create_action(
                action_type="add_starter_pack",
                target="first_purchase_offer",
                priority=ActionPriority.P0_CRITICAL,
                expected_impact=f"付费率 +{(0.05 - snapshot.payer_rate) * 100:.1f}%",
                confidence=0.85,
                evidence=[
                    f"付费率 {snapshot.payer_rate:.1%}，极低",
                    f"总用户 {snapshot.total_users}，付费用户仅 {snapshot.total_payers}",
                ],
                recommendation=(
                    "增加 $0.99 限时首充礼包，"
                    "在玩家首次资源不足时触发"
                ),
                domain="payer_rate",
                revenue_impact=snapshot.total_users * 0.03 * 0.99,
            ))

        elif snapshot.payer_rate < 0.05:
            actions.append(self._create_action(
                action_type="optimize_first_pay_trigger",
                target="resource_scarcity_moment",
                priority=ActionPriority.P1_HIGH,
                expected_impact=f"付费率 +{(0.08 - snapshot.payer_rate) * 100:.1f}%",
                confidence=0.80,
                evidence=[
                    f"付费率 {snapshot.payer_rate:.1%}，低于 5% 基准",
                ],
                recommendation=(
                    "在第 3-5 天增加资源短缺触发点，"
                    "配合限时低价礼包引导首充"
                ),
                domain="payer_rate",
                revenue_impact=snapshot.total_users * 0.03 * 5.0,
            ))

        return actions

    # ── ARPPU / 定价 ────────────────────────────────────

    def _analyze_arppu(
        self,
        snapshot: MonetizationSnapshot,
    ) -> list[OptimizationAction]:
        """分析 ARPPU 和定价。"""
        actions: list[OptimizationAction] = []

        if snapshot.arppu > 0 and snapshot.arppu < 20:
            actions.append(self._create_action(
                action_type="adjust_pricing_tiers",
                target="pricing_structure",
                priority=ActionPriority.P2_MEDIUM,
                expected_impact=f"ARPPU +${(30 - snapshot.arppu):.0f}",
                confidence=0.65,
                evidence=[
                    f"ARPPU ${snapshot.arppu:.2f}，低于 $20 基准",
                    f"ARPU ${snapshot.arpu:.2f}",
                ],
                recommendation=(
                    "增加中高档位礼包（$19.99 / $49.99），"
                    "提供阶梯式奖励引导用户提升消费"
                ),
                domain="arpu",
                revenue_impact=snapshot.total_payers * (30 - snapshot.arppu) * 0.3,
            ))

        elif snapshot.arppu > 100:
            actions.append(self._create_action(
                action_type="add_mid_tier_offers",
                target="mid_tier_payers",
                priority=ActionPriority.P3_LOW,
                expected_impact="扩大付费用户基数",
                confidence=0.60,
                evidence=[
                    f"ARPPU ${snapshot.arppu:.2f}，较高",
                    "付费用户可能集中在高价档位",
                ],
                recommendation=(
                    "增加 $4.99 / $9.99 中间档位，"
                    "降低首次付费门槛扩大付费漏斗"
                ),
                domain="arpu",
                revenue_impact=snapshot.total_users * 0.02 * 9.99,
            ))

        return actions

    # ── Offer 表现 ──────────────────────────────────────

    def _analyze_offers(
        self,
        snapshot: MonetizationSnapshot,
    ) -> list[OptimizationAction]:
        """分析 Offer 表现。"""
        actions: list[OptimizationAction] = []

        if not snapshot.offers:
            return actions

        # 转化率最低的 Offer
        worst_offer = min(snapshot.offers, key=lambda o: o.conversion_rate)
        if worst_offer.conversion_rate < 0.03:
            actions.append(self._create_action(
                action_type="optimize_offer",
                target=worst_offer.offer_name,
                priority=ActionPriority.P2_MEDIUM,
                expected_impact=f"'{worst_offer.offer_name}' 转化率 +{worst_offer.conversion_rate * 100:.0f}%",
                confidence=0.70,
                evidence=[
                    f"'{worst_offer.offer_name}' 转化率 {worst_offer.conversion_rate:.1%}",
                    f"曝光 {worst_offer.impressions}，购买 {worst_offer.purchases}",
                ],
                recommendation=(
                    f"优化 '{worst_offer.offer_name}' 的展示时机和定价，"
                    f"考虑在用户最需要时触发"
                ),
                domain="offer",
                revenue_impact=worst_offer.impressions * 0.05 * worst_offer.avg_order_value,
            ))

        # 收入最高的 Offer → 扩大曝光
        best_offer = max(snapshot.offers, key=lambda o: o.revenue)
        if best_offer.revenue > 0:
            actions.append(self._create_action(
                action_type="scale_best_offer",
                target=best_offer.offer_name,
                priority=ActionPriority.P2_MEDIUM,
                expected_impact=f"'{best_offer.offer_name}' 收入 +30%",
                confidence=0.80,
                evidence=[
                    f"'{best_offer.offer_name}' 收入 ${best_offer.revenue:,.0f}",
                    f"转化率 {best_offer.conversion_rate:.1%}",
                    f"ARPU per buyer ${best_offer.avg_order_value:.2f}",
                ],
                recommendation=(
                    f"增加 '{best_offer.offer_name}' 的曝光频次，"
                    f"考虑作为常规商品而非限时活动"
                ),
                domain="offer",
                revenue_impact=best_offer.revenue * 0.30,
            ))

        return actions

    # ── 大R用户 ─────────────────────────────────────────

    def _analyze_whales(
        self,
        snapshot: MonetizationSnapshot,
    ) -> list[OptimizationAction]:
        """分析大R用户。"""
        actions: list[OptimizationAction] = []

        whale_count = snapshot.payer_segments.get("whale", 0)
        if whale_count == 0:
            return actions

        total_payers = snapshot.total_payers or 1
        whale_ratio = whale_count / total_payers

        if whale_ratio >= 0.20:
            actions.append(self._create_action(
                action_type="whale_retention_risk",
                target=f"whale_users ({whale_count})",
                priority=ActionPriority.P1_HIGH,
                expected_impact="保护 40%+ 收入来源",
                confidence=0.85,
                evidence=[
                    f"大R用户 {whale_count} 人，占付费用户 {whale_ratio:.0%}",
                    f"收入集中度高，流失风险大",
                ],
                recommendation=(
                    "建立大R专属运营体系：专属客服、"
                    "提前体验新内容、VIP 礼包、个性化关怀"
                ),
                domain="whale",
                revenue_impact=snapshot.total_revenue * 0.40,
            ))

        # 大R数量少 → 需要培育
        if whale_count < 50 and total_payers > 200:
            actions.append(self._create_action(
                action_type="whale_cultivation",
                target="repeat_payer_to_whale",
                priority=ActionPriority.P2_MEDIUM,
                expected_impact="培育 20+ 新大R",
                confidence=0.65,
                evidence=[
                    f"大R仅 {whale_count} 人",
                    f"重复付费用户 {snapshot.payer_segments.get('repeat_payer', 0)} 人可培育",
                ],
                recommendation=(
                    "对 repeat_payer 用户推送高价值礼包，"
                    "设计消费引导路径，培育大R"
                ),
                domain="whale",
                revenue_impact=20 * 500,
            ))

        return actions

    # ── 首充时间 ────────────────────────────────────────

    def _analyze_first_pay(
        self,
        snapshot: MonetizationSnapshot,
    ) -> list[OptimizationAction]:
        """分析首充时间。"""
        actions: list[OptimizationAction] = []

        if snapshot.avg_first_pay_days > 5:
            actions.append(self._create_action(
                action_type="accelerate_first_pay",
                target="day_1_to_3_monetization",
                priority=ActionPriority.P1_HIGH,
                expected_impact="首充时间缩短至 3 天内",
                confidence=0.75,
                evidence=[
                    f"平均首充时间 {snapshot.avg_first_pay_days:.1f} 天",
                    "理想首充时间应 < 3 天",
                ],
                recommendation=(
                    "在前 3 天设计 3 个资源短缺触发点，"
                    "配合 $0.99 / $1.99 限时礼包引导首充"
                ),
                domain="payer_rate",
                revenue_impact=snapshot.total_payers * 5.0,
            ))

        return actions

    # ── Mock ───────────────────────────────────────────

    def _mock_actions(self) -> list[OptimizationAction]:
        """无输入时生成 mock 建议。"""
        return [
            self._create_action(
                action_type="add_starter_pack",
                target="first_purchase_offer",
                priority=ActionPriority.P0_CRITICAL,
                expected_impact="付费率 +3%",
                confidence=0.85,
                evidence=["付费率 2.1%，极低"],
                recommendation="增加 $0.99 限时首充礼包",
                domain="payer_rate",
                revenue_impact=3000.0,
            ),
            self._create_action(
                action_type="scale_best_offer",
                target="限时特惠",
                priority=ActionPriority.P2_MEDIUM,
                expected_impact="收入 +30%",
                confidence=0.80,
                evidence=["限时特惠收入 $8,000，ARPU最高"],
                recommendation="增加限时特惠曝光频次",
                domain="offer",
                revenue_impact=2400.0,
            ),
        ]
