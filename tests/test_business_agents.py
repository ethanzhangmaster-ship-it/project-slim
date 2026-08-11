"""三个业务 Agent 单元测试。

验证 ProductIntelligenceAgent / MonetizationIntelligenceAgent / UAIntelligenceAgent
在 Mock 和真实 Snapshot 输入下的决策生成逻辑。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from market_ops.creative_vision_runtime.reality.analyzers import (
    LifecycleAnalyzer,
    FunnelAnalyzer,
    RetentionAnalyzer,
    MonetizationAnalyzer,
)
from market_ops.creative_vision_runtime.reality.models import CampaignReality
from market_ops.creative_vision_runtime.reality.intelligence.agents import (
    ActionPriority,
    OptimizationAction,
    ProductIntelligenceAgent,
    MonetizationIntelligenceAgent,
    UAIntelligenceAgent,
)


# ── ProductIntelligenceAgent ───────────────────────────────


class TestProductAgent:
    """产品优化 Agent 测试。"""

    def test_mock_mode(self):
        """无输入时生成 mock 建议。"""
        agent = ProductIntelligenceAgent()
        actions = agent.decide()

        assert len(actions) > 0
        assert all(isinstance(a, OptimizationAction) for a in actions)
        assert all(a.agent_type == "product" for a in actions)
        assert agent.total_decisions == len(actions)

    def test_actions_sorted_by_priority(self):
        """行动按优先级排序。"""
        agent = ProductIntelligenceAgent()
        actions = agent.decide()

        priorities = [a.priority for a in actions]
        priority_order = {
            ActionPriority.P0_CRITICAL: 0,
            ActionPriority.P1_HIGH: 1,
            ActionPriority.P2_MEDIUM: 2,
            ActionPriority.P3_LOW: 3,
        }
        order_values = [priority_order.get(p, 99) for p in priorities]
        assert order_values == sorted(order_values)

    def test_with_lifecycle_snapshot(self):
        """消费 LifecycleSnapshot。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleSnapshot,
        )
        # 构造一个会触发行动的快照
        lifecycle = LifecycleSnapshot(
            project_id=102,
            d1_retention=0.25,  # 低于 30% → 触发 onboarding fix
            d7_retention=0.10,  # 低于 15% → 触发 core gameplay fix
            d30_retention=0.05,
            tutorial_completion_rate=0.60,
            churn_risk_rate=0.25,  # 高于 20% → 触发 churn recovery
            churn_risk_count=250,
            stage_distribution={"churn": 250},
            dau=100,
        )
        agent = ProductIntelligenceAgent()
        actions = agent.decide(lifecycle=lifecycle)

        assert len(actions) > 0
        # 应包含留存或流失相关行动
        action_types = {a.action_type for a in actions}
        assert any(
            "onboarding" in t or "gameplay" in t or "churn" in t or "d1_d7" in t
            for t in action_types
        )

    def test_with_funnel_snapshot(self):
        """消费 FunnelSnapshot。"""
        funnel = FunnelAnalyzer().analyze(102)
        agent = ProductIntelligenceAgent()
        actions = agent.decide(funnel=funnel)

        assert len(actions) > 0
        # 应包含漏斗修复行动
        action_types = {a.action_type for a in actions}
        assert any("funnel" in t or "first_step" in t for t in action_types)

    def test_with_both_snapshots(self):
        """同时消费两个 Snapshot。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleSnapshot,
        )
        lifecycle = LifecycleSnapshot(
            project_id=102,
            d1_retention=0.25,
            d7_retention=0.10,
            churn_risk_rate=0.25,
            churn_risk_count=250,
        )
        funnel = FunnelAnalyzer().analyze(102)
        agent = ProductIntelligenceAgent()
        actions = agent.decide(lifecycle=lifecycle, funnel=funnel)

        assert len(actions) > 2  # 两个域都有行动

    def test_low_d1_retention_triggers_onboarding_fix(self):
        """D1 留存低 → 触发新手引导修复。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleSnapshot,
        )
        snapshot = LifecycleSnapshot(
            project_id=102,
            d1_retention=0.20,  # 低于 30%
            d7_retention=0.10,
            d30_retention=0.05,
            tutorial_completion_rate=0.60,
            churn_risk_rate=0.25,
            churn_risk_count=250,
            stage_distribution={"churn": 250},
            dau=100,
        )
        agent = ProductIntelligenceAgent()
        actions = agent.decide(lifecycle=snapshot)

        onboarding = [a for a in actions if a.action_type == "fix_onboarding"]
        assert len(onboarding) == 1
        assert onboarding[0].priority == ActionPriority.P1_HIGH
        assert "D1" in onboarding[0].expected_impact

    def test_high_churn_triggers_recovery(self):
        """高流失率 → 触发召回。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            LifecycleSnapshot,
        )
        snapshot = LifecycleSnapshot(
            project_id=102,
            d1_retention=0.50,
            d7_retention=0.30,
            churn_risk_rate=0.30,
            churn_risk_count=300,
        )
        agent = ProductIntelligenceAgent()
        actions = agent.decide(lifecycle=snapshot)

        recovery = [a for a in actions if a.action_type == "churn_recovery"]
        assert len(recovery) == 1
        assert recovery[0].priority == ActionPriority.P1_HIGH

    def test_action_to_dict(self):
        """to_dict 完整。"""
        agent = ProductIntelligenceAgent()
        actions = agent.decide()

        d = actions[0].to_dict()
        assert "action_id" in d
        assert "agent_type" in d
        assert "action_type" in d
        assert "priority" in d
        assert "evidence" in d
        assert "recommendation" in d
        assert "created_at" in d


# ── MonetizationIntelligenceAgent ─────────────────────────


class TestMonetizationAgent:
    """商业化 Agent 测试。"""

    def test_mock_mode(self):
        """无输入时生成 mock 建议。"""
        agent = MonetizationIntelligenceAgent()
        actions = agent.decide()

        assert len(actions) > 0
        assert all(a.agent_type == "monetization" for a in actions)

    def test_with_monetization_snapshot(self):
        """消费 MonetizationSnapshot。"""
        snapshot = MonetizationAnalyzer().analyze(102)
        agent = MonetizationIntelligenceAgent()
        actions = agent.decide(snapshot)

        assert len(actions) > 0
        # 应包含付费率/Offer/定价相关行动
        action_types = {a.action_type for a in actions}
        assert any(
            "starter_pack" in t or "offer" in t or "pricing" in t or "first_pay" in t
            for t in action_types
        )

    def test_low_payer_rate_triggers_starter_pack(self):
        """低付费率 → 触发首充礼包。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            MonetizationSnapshot,
        )
        snapshot = MonetizationSnapshot(
            project_id=102,
            total_users=10000,
            total_payers=100,
            total_revenue=5000.0,
            payer_rate=0.01,
            arpu=0.50,
            arppu=50.0,
        )
        agent = MonetizationIntelligenceAgent()
        actions = agent.decide(snapshot)

        starter = [a for a in actions if a.action_type == "add_starter_pack"]
        assert len(starter) == 1
        assert starter[0].priority == ActionPriority.P0_CRITICAL

    def test_low_arppu_triggers_pricing_adjustment(self):
        """低 ARPPU → 触发定价优化。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            MonetizationSnapshot,
        )
        snapshot = MonetizationSnapshot(
            project_id=102,
            total_users=10000,
            total_payers=500,
            total_revenue=5000.0,
            payer_rate=0.05,
            arpu=0.50,
            arppu=10.0,  # 低于 $20
        )
        agent = MonetizationIntelligenceAgent()
        actions = agent.decide(snapshot)

        pricing = [a for a in actions if a.action_type == "adjust_pricing_tiers"]
        assert len(pricing) == 1

    def test_whale_concentration_triggers_retention_risk(self):
        """大R集中度高 → 触发大R维护。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            MonetizationSnapshot,
        )
        snapshot = MonetizationSnapshot(
            project_id=102,
            total_users=10000,
            total_payers=500,
            total_revenue=50000.0,
            payer_rate=0.05,
            arpu=5.0,
            arppu=100.0,
            payer_segments={
                "non_payer": 9500,
                "first_payer": 100,
                "repeat_payer": 300,
                "whale": 100,  # 20% of payers
            },
        )
        agent = MonetizationIntelligenceAgent()
        actions = agent.decide(snapshot)

        whale = [a for a in actions if a.action_type == "whale_retention_risk"]
        assert len(whale) == 1
        assert whale[0].priority == ActionPriority.P1_HIGH

    def test_best_offer_scaled(self):
        """收入最高 Offer → 扩大曝光。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            MonetizationSnapshot,
            OfferPerformance,
        )
        snapshot = MonetizationSnapshot(
            project_id=102,
            total_users=10000,
            total_payers=500,
            total_revenue=30000.0,
            payer_rate=0.05,
            arpu=3.0,
            arppu=60.0,
            offers=[
                OfferPerformance("礼包A", 10000, 500, 0.05, 5000, 10),
                OfferPerformance("礼包B", 5000, 100, 0.02, 8000, 80),
            ],
        )
        agent = MonetizationIntelligenceAgent()
        actions = agent.decide(snapshot)

        scale = [a for a in actions if a.action_type == "scale_best_offer"]
        assert len(scale) == 1
        assert "礼包B" in scale[0].target


# ── UAIntelligenceAgent ────────────────────────────────────


class TestUAAgent:
    """市场/UA Agent 测试。"""

    def test_mock_mode(self):
        """无输入时生成 mock 建议。"""
        agent = UAIntelligenceAgent()
        actions = agent.decide()

        assert len(actions) > 0
        assert all(a.agent_type == "ua" for a in actions)

    def test_with_retention_snapshot(self):
        """消费 RetentionSnapshot。"""
        snapshot = RetentionAnalyzer().analyze(102)
        agent = UAIntelligenceAgent()
        actions = agent.decide(retention=snapshot)

        assert len(actions) > 0
        # 应包含渠道扩量/暂停/Lookalike 行动
        action_types = {a.action_type for a in actions}
        assert any(
            "scale" in t or "pause" in t or "lookalike" in t or "creative" in t
            for t in action_types
        )

    def test_best_channel_scaled(self):
        """最佳渠道 → 扩量。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            RetentionSnapshot,
            ChannelRetention,
        )
        snapshot = RetentionSnapshot(
            project_id=102,
            channel_retention=[
                ChannelRetention("asa", 0.52, 0.35, 0.18, 1500),
                ChannelRetention("tiktok", 0.38, 0.18, 0.06, 1200),
            ],
            best_channel="asa",
            worst_channel="tiktok",
            retention_drivers=["purchase", "level_complete"],
        )
        agent = UAIntelligenceAgent()
        actions = agent.decide(retention=snapshot)

        scale = [a for a in actions if a.action_type == "scale_channel"]
        assert len(scale) >= 1
        assert any("asa" in a.target for a in scale)

    def test_worst_channel_paused(self):
        """最差渠道 → 暂停。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            RetentionSnapshot,
            ChannelRetention,
        )
        snapshot = RetentionSnapshot(
            project_id=102,
            channel_retention=[
                ChannelRetention("asa", 0.52, 0.35, 0.18, 1500),
                ChannelRetention("tiktok", 0.38, 0.04, 0.01, 1200),  # D7 < 5%
            ],
            best_channel="asa",
            worst_channel="tiktok",
            retention_drivers=["daily_login"],
        )
        agent = UAIntelligenceAgent()
        actions = agent.decide(retention=snapshot)

        pause = [a for a in actions if a.action_type == "pause_channel"]
        assert len(pause) >= 1
        assert any("tiktok" in a.target for a in pause)
        assert any(a.priority == ActionPriority.P0_CRITICAL for a in pause)

    def test_lookalike_recommended(self):
        """生成 Lookalike 建议。"""
        from market_ops.creative_vision_runtime.reality.analyzers import (
            RetentionSnapshot,
        )
        snapshot = RetentionSnapshot(
            project_id=102,
            best_channel="asa",
            retention_drivers=["purchase", "level_complete", "daily_login"],
        )
        agent = UAIntelligenceAgent()
        actions = agent.decide(retention=snapshot)

        lookalike = [a for a in actions if a.action_type == "create_lookalike"]
        assert len(lookalike) == 1
        assert "asa" in lookalike[0].target

    def test_with_campaign_reality(self):
        """消费 CampaignReality 列表。"""
        campaigns = [
            CampaignReality(
                campaign_id="camp_high",
                spend=1000.0,
                impressions=100000,
                clicks=5000,
                installs=800,
                ctr=0.05,
                cpi=1.25,
                revenue_d7=200.0,
                revenue_d30=2000.0,
                roas_d7=0.20,  # 高 ROAS → 扩量
                roas_d30=0.20,
            ),
            CampaignReality(
                campaign_id="camp_low",
                spend=500.0,
                impressions=50000,
                clicks=1000,
                installs=200,
                ctr=0.02,
                cpi=2.50,
                revenue_d7=10.0,
                revenue_d30=50.0,
                roas_d7=0.02,  # 低 ROAS → 暂停
                roas_d30=0.10,
            ),
        ]
        agent = UAIntelligenceAgent()
        actions = agent.decide(campaigns=campaigns)

        scale = [a for a in actions if a.action_type == "scale_campaign"]
        pause = [a for a in actions if a.action_type == "pause_campaign"]
        assert len(scale) >= 1
        assert len(pause) >= 1
        assert any("camp_high" in a.target for a in scale)
        assert any("camp_low" in a.target for a in pause)

    def test_low_ctr_triggers_creative_refresh(self):
        """低 CTR → 素材疲劳。"""
        campaigns = [
            CampaignReality(
                campaign_id="camp_fatigue",
                spend=500.0,
                impressions=100000,
                clicks=1000,
                installs=200,
                ctr=0.01,  # 低于 1.5%
                cpi=2.50,
                roas_d7=0.10,
                roas_d30=0.15,
            ),
        ]
        agent = UAIntelligenceAgent()
        actions = agent.decide(campaigns=campaigns)

        refresh = [a for a in actions if a.action_type == "refresh_creative"]
        assert len(refresh) == 1


# ── 交叉测试 ────────────────────────────────────────────────


class TestCrossAgent:
    """三个 Agent 协同测试。"""

    def test_all_three_agents_run(self):
        """三个 Agent 同时运行。"""
        lifecycle = LifecycleAnalyzer().analyze(102)
        funnel = FunnelAnalyzer().analyze(102)
        retention = RetentionAnalyzer().analyze(102)
        monetization = MonetizationAnalyzer().analyze(102)

        product_agent = ProductIntelligenceAgent()
        monetization_agent = MonetizationIntelligenceAgent()
        ua_agent = UAIntelligenceAgent()

        product_actions = product_agent.decide(lifecycle=lifecycle, funnel=funnel)
        monetization_actions = monetization_agent.decide(monetization)
        ua_actions = ua_agent.decide(retention=retention)

        # 三个 Agent 都生成了行动
        assert len(product_actions) > 0
        assert len(monetization_actions) > 0
        assert len(ua_actions) > 0

        # 行动类型不重叠
        product_types = {a.action_type for a in product_actions}
        monetization_types = {a.action_type for a in monetization_actions}
        ua_types = {a.action_type for a in ua_actions}
        assert not product_types & monetization_types
        assert not product_types & ua_types

    def test_agent_types_distinct(self):
        """三个 Agent 类型不同。"""
        assert ProductIntelligenceAgent().agent_type == "product"
        assert MonetizationIntelligenceAgent().agent_type == "monetization"
        assert UAIntelligenceAgent().agent_type == "ua"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
