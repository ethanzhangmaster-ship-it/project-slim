"""E12.3 — UA Intelligence Agent。

市场/UA Agent —— 消费 RetentionSnapshot + RealitySnapshot，
输出投放优化行动建议。

回答：
  - 哪个渠道值得扩量？
  - 哪个渠道应该暂停？
  - 哪些用户值得继续投放？
  - Lookalike 受众怎么建？

Usage:
    agent = UAIntelligenceAgent()
    actions = agent.decide(retention_snapshot, campaign_reality_list)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base_agent import ActionPriority, BaseAgent, OptimizationAction

if TYPE_CHECKING:
    from ...analyzers.retention_analyzer import RetentionSnapshot
    from ...models import CampaignReality


class UAOptimizationAction(OptimizationAction):
    """投放优化行动（带 UA 专属字段）。"""

    domain: str = "ua"          # 优化域 (scale/pause/creative/audience)
    channel: str = ""           # 目标渠道
    campaign_id: str = ""       # 目标 Campaign


class UAIntelligenceAgent(BaseAgent):
    """市场/UA Agent。

    消费 RetentionSnapshot + CampaignReality，
    输出 UAOptimizationAction 列表。

    Attributes:
        total_decisions: 累计决策数
    """

    agent_type = "ua"

    # ROAS 判定阈值
    ROAS_SCALE_THRESHOLD = 0.15    # D7 ROAS > 15% → 扩量
    ROAS_PAUSE_THRESHOLD = 0.05    # D7 ROAS < 5% → 暂停
    CTR_FATIGUE_THRESHOLD = 0.015  # CTR < 1.5% → 素材疲劳

    def _generate_actions(
        self,
        retention: RetentionSnapshot | None = None,
        campaigns: list[CampaignReality] | None = None,
    ) -> list[OptimizationAction]:
        """生成投放优化行动。

        Args:
            retention:  留存快照
            campaigns:  Campaign 现实数据列表

        Returns:
            UAOptimizationAction 列表
        """
        if not retention and not campaigns:
            return self._mock_actions()

        actions: list[OptimizationAction] = []

        # 1. 渠道留存分析 → 扩量/暂停
        if retention:
            actions.extend(self._analyze_channels(retention))

        # 2. Campaign 级别 ROAS 分析
        if campaigns:
            actions.extend(self._analyze_campaigns(campaigns))

        # 3. Lookalike 建议
        if retention:
            actions.extend(self._recommend_lookalike(retention))

        return actions

    # ── 渠道分析 ────────────────────────────────────────

    def _analyze_channels(
        self,
        snapshot: RetentionSnapshot,
    ) -> list[OptimizationAction]:
        """分析各渠道留存，生成扩量/暂停建议。"""
        actions: list[OptimizationAction] = []

        for ch in snapshot.channel_retention:
            # 高留存渠道 → 扩量
            if ch.d7 > self.ROAS_SCALE_THRESHOLD and ch.d30 > 0.10:
                actions.append(self._create_action(
                    action_type="scale_channel",
                    target=ch.channel,
                    priority=ActionPriority.P1_HIGH,
                    expected_impact=f"{ch.channel} D7={ch.d7:.0%} 渠道扩量 +50%",
                    confidence=0.85,
                    evidence=[
                        f"{ch.channel} D7 留存 {ch.d7:.0%}，D30 留存 {ch.d30:.0%}",
                        f"安装量 {ch.installs}",
                        "用户质量优秀，留存高于均值",
                    ],
                    recommendation=(
                        f"扩大 {ch.channel} 渠道预算 +50%，"
                        f"增加相似受众定向"
                    ),
                    domain="scale",
                    channel=ch.channel,
                ))

            # 低留存渠道 → 暂停或减少
            elif ch.d7 < self.ROAS_PAUSE_THRESHOLD:
                actions.append(self._create_action(
                    action_type="pause_channel",
                    target=ch.channel,
                    priority=ActionPriority.P0_CRITICAL,
                    expected_impact=f"暂停 {ch.channel}，节省预算",
                    confidence=0.80,
                    evidence=[
                        f"{ch.channel} D7 留存仅 {ch.d7:.0%}",
                        f"D30 留存 {ch.d30:.0%}，用户质量差",
                        f"安装量 {ch.installs}",
                    ],
                    recommendation=(
                        f"暂停 {ch.channel} 渠道投放，"
                        f"或更换素材/受众重新测试"
                    ),
                    domain="pause",
                    channel=ch.channel,
                ))

            # 中等留存 → 优化素材
            elif ch.d7 < 0.20 and ch.d7 >= self.ROAS_PAUSE_THRESHOLD:
                actions.append(self._create_action(
                    action_type="optimize_creative",
                    target=ch.channel,
                    priority=ActionPriority.P2_MEDIUM,
                    expected_impact=f"{ch.channel} 留存 +30%",
                    confidence=0.65,
                    evidence=[
                        f"{ch.channel} D7 留存 {ch.d7:.0%}，中等偏低",
                    ],
                    recommendation=(
                        f"更换 {ch.channel} 渠道素材，"
                        f"A/B 测试新 Hook 和玩法展示"
                    ),
                    domain="creative",
                    channel=ch.channel,
                ))

        return actions

    # ── Campaign 分析 ───────────────────────────────────

    def _analyze_campaigns(
        self,
        campaigns: list[CampaignReality],
    ) -> list[OptimizationAction]:
        """Campaign 级别 ROAS 分析。"""
        actions: list[OptimizationAction] = []

        for c in campaigns:
            # 高 ROAS → 扩量
            if c.roas_d7 > self.ROAS_SCALE_THRESHOLD and c.spend > 0:
                actions.append(self._create_action(
                    action_type="scale_campaign",
                    target=c.campaign_id,
                    priority=ActionPriority.P1_HIGH,
                    expected_impact=f"Campaign {c.campaign_id} 扩量 +30%",
                    confidence=0.85,
                    evidence=[
                        f"D7 ROAS={c.roas_d7:.2%}",
                        f"D30 ROAS={c.roas_d30:.2%}",
                        f"花费 ${c.spend:.0f}，收入 ${c.revenue_d30:.0f}",
                    ],
                    recommendation=(
                        f"扩大 Campaign {c.campaign_id} 预算 +30%，"
                        f"素材表现优秀可复制到相似受众"
                    ),
                    domain="scale",
                    campaign_id=c.campaign_id,
                ))

            # 低 ROAS → 暂停
            elif c.roas_d7 < self.ROAS_PAUSE_THRESHOLD and c.spend > 0:
                actions.append(self._create_action(
                    action_type="pause_campaign",
                    target=c.campaign_id,
                    priority=ActionPriority.P0_CRITICAL,
                    expected_impact=f"暂停 Campaign {c.campaign_id}，止损",
                    confidence=0.80,
                    evidence=[
                        f"D7 ROAS={c.roas_d7:.2%}，极低",
                        f"花费 ${c.spend:.0f}，收入 ${c.revenue_d30:.0f}",
                        f"CPI=${c.cpi:.2f}",
                    ],
                    recommendation=(
                        f"暂停 Campaign {c.campaign_id}，"
                        f"分析素材/受众/出价问题后重新测试"
                    ),
                    domain="pause",
                    campaign_id=c.campaign_id,
                ))

            # CTR 低 → 素材疲劳
            if c.ctr > 0 and c.ctr < self.CTR_FATIGUE_THRESHOLD:
                actions.append(self._create_action(
                    action_type="refresh_creative",
                    target=c.campaign_id,
                    priority=ActionPriority.P2_MEDIUM,
                    expected_impact=f"CTR +{((0.03 - c.ctr) / c.ctr * 100):.0f}%",
                    confidence=0.70,
                    evidence=[
                        f"CTR={c.ctr:.2%}，低于 {self.CTR_FATIGUE_THRESHOLD:.1%} 疲劳线",
                        f"展示 {c.impressions}，点击 {c.clicks}",
                    ],
                    recommendation=(
                        f"Campaign {c.campaign_id} 素材疲劳，"
                        f"更换 Hook 视频前 3 秒"
                    ),
                    domain="creative",
                    campaign_id=c.campaign_id,
                ))

        return actions

    # ── Lookalike 建议 ──────────────────────────────────

    def _recommend_lookalike(
        self,
        snapshot: RetentionSnapshot,
    ) -> list[OptimizationAction]:
        """基于留存驱动因素推荐 Lookalike 受众。"""
        actions: list[OptimizationAction] = []

        if snapshot.best_channel and snapshot.retention_drivers:
            actions.append(self._create_action(
                action_type="create_lookalike",
                target=f"lookalike_from_{snapshot.best_channel}",
                priority=ActionPriority.P2_MEDIUM,
                expected_impact="新受众 CPI -20%，D7 留存 +10%",
                confidence=0.70,
                evidence=[
                    f"最佳渠道 {snapshot.best_channel} D7 留存最高",
                    f"留存驱动行为: {', '.join(snapshot.retention_drivers[:3])}",
                ],
                recommendation=(
                    f"从 {snapshot.best_channel} 渠道的高留存用户中"
                    f"提取种子受众，创建 1% Lookalike 扩展到新渠道"
                ),
                domain="audience",
                channel=snapshot.best_channel,
            ))

        return actions

    # ── Mock ───────────────────────────────────────────

    def _mock_actions(self) -> list[OptimizationAction]:
        """无输入时生成 mock 建议。"""
        return [
            self._create_action(
                action_type="scale_channel",
                target="asa",
                priority=ActionPriority.P1_HIGH,
                expected_impact="asa 渠道扩量 +50%",
                confidence=0.85,
                evidence=["asa D7=35%，D30=18%，留存最优"],
                recommendation="扩大 ASA 预算 +50%",
                domain="scale",
                channel="asa",
            ),
            self._create_action(
                action_type="pause_channel",
                target="tiktok",
                priority=ActionPriority.P0_CRITICAL,
                expected_impact="暂停 tiktok，节省预算",
                confidence=0.80,
                evidence=["tiktok D7=8%，D30=4%，用户质量差"],
                recommendation="暂停 TikTok 投放",
                domain="pause",
                channel="tiktok",
            ),
            self._create_action(
                action_type="create_lookalike",
                target="lookalike_from_asa",
                priority=ActionPriority.P2_MEDIUM,
                expected_impact="新受众 CPI -20%",
                confidence=0.70,
                evidence=["asa 渠道高留存用户作为种子"],
                recommendation="从 ASA 高留存用户创建 1% Lookalike",
                domain="audience",
                channel="asa",
            ),
        ]
