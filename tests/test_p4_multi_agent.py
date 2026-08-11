"""P4.4 MultiAgentGovernor 单元测试 — 最小权限提案仲裁.

测试覆盖:
  1. PERMISSIONS 权限矩阵
  2. authorize() 权限校验
  3. arbitrate() 提案仲裁
  4. arbitrate() 预算约束
  5. arbitrate() 优先级排序
  6. arbitrate() 资源冲突解决
  7. takeover/release 人工接管
  8. 边界场景: 空提案、超额预算
"""
from __future__ import annotations

import pytest

from src.autonomous_growth.fleet import AgentRole
from src.autonomous_growth.multi_agent import (
    AgentProposal,
    MultiAgentGovernor,
    PERMISSIONS,
)


# ═══════════════════════════════════════════════════════════════
# 1. PERMISSIONS 权限矩阵
# ═══════════════════════════════════════════════════════════════


class TestPermissions:
    """PERMISSIONS 权限矩阵."""

    def test_all_roles_have_permissions(self):
        """所有 10 个角色都有权限定义."""
        assert len(PERMISSIONS) == 10
        for role in AgentRole:
            assert role in PERMISSIONS
            assert len(PERMISSIONS[role]) > 0

    def test_strategy_permissions(self):
        """STRATEGY 权限."""
        assert PERMISSIONS[AgentRole.STRATEGY] == {"propose_strategy", "read_all"}

    def test_growth_permissions(self):
        """GROWTH 权限."""
        assert PERMISSIONS[AgentRole.GROWTH] == {"propose_budget", "read_growth"}

    def test_product_permissions(self):
        """PRODUCT 权限."""
        assert PERMISSIONS[AgentRole.PRODUCT] == {"propose_product", "read_product"}

    def test_ua_permissions(self):
        """UA 权限."""
        assert PERMISSIONS[AgentRole.UA] == {"propose_campaign", "read_ads"}

    def test_aso_permissions(self):
        """ASO 权限."""
        assert PERMISSIONS[AgentRole.ASO] == {"propose_store", "read_store"}

    def test_monetization_permissions(self):
        """MONETIZATION 权限."""
        assert PERMISSIONS[AgentRole.MONETIZATION] == {"propose_monetization", "read_revenue"}

    def test_creative_permissions(self):
        """CREATIVE 权限."""
        assert PERMISSIONS[AgentRole.CREATIVE] == {"propose_creative", "read_creative"}

    def test_data_analyst_permissions(self):
        """DATA_ANALYST 权限."""
        assert PERMISSIONS[AgentRole.DATA_ANALYST] == {"propose_analysis", "read_metrics", "generate_reports"}

    def test_player_support_permissions(self):
        """PLAYER_SUPPORT 权限."""
        assert PERMISSIONS[AgentRole.PLAYER_SUPPORT] == {"propose_support", "read_tickets", "manage_faq"}

    def test_market_intelligence_permissions(self):
        """MARKET_INTELLIGENCE 权限."""
        assert PERMISSIONS[AgentRole.MARKET_INTELLIGENCE] == {"propose_market", "read_market", "generate_opportunities"}

    def test_least_privilege_no_overlap(self):
        """最小权限: 写权限互不重叠 (每个 propose_* 只属于一个角色)."""
        propose_perms = []
        for role, perms in PERMISSIONS.items():
            propose_perms.extend(p for p in perms if p.startswith("propose_"))
        assert len(propose_perms) == len(set(propose_perms)), "propose 权限应互不重叠"


# ═══════════════════════════════════════════════════════════════
# 2. authorize() 权限校验
# ═══════════════════════════════════════════════════════════════


class TestAuthorize:
    """authorize() 权限校验."""

    def test_authorized_capability(self):
        """有权限返回 True."""
        governor = MultiAgentGovernor()
        assert governor.authorize(AgentRole.STRATEGY, "propose_strategy") is True
        assert governor.authorize(AgentRole.STRATEGY, "read_all") is True

    def test_unauthorized_capability(self):
        """无权限返回 False."""
        governor = MultiAgentGovernor()
        assert governor.authorize(AgentRole.GROWTH, "propose_strategy") is False
        assert governor.authorize(AgentRole.UA, "read_all") is False

    def test_cross_role_isolation(self):
        """跨角色权限隔离."""
        governor = MultiAgentGovernor()
        # GROWTH 不能执行 UA 的权限
        assert governor.authorize(AgentRole.GROWTH, "propose_campaign") is False
        # UA 不能执行 GROWTH 的权限
        assert governor.authorize(AgentRole.UA, "propose_budget") is False


# ═══════════════════════════════════════════════════════════════
# 3. arbitrate() 提案仲裁
# ═══════════════════════════════════════════════════════════════


class TestArbitrate:
    """arbitrate() 提案仲裁."""

    def test_selects_all_within_budget(self):
        """预算内全部选中."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.8, confidence=0.9, requested_budget=100),
            AgentProposal(role=AgentRole.UA, game_id="g2", resource="campaign",
                          action="create", priority=0.7, confidence=0.85, requested_budget=50),
        ]
        selected = governor.arbitrate(proposals, budget=200)
        assert len(selected) == 2

    def test_empty_proposals(self):
        """空提案列表返回空."""
        governor = MultiAgentGovernor()
        assert governor.arbitrate([], budget=100) == []

    def test_single_proposal_within_budget(self):
        """单个提案预算内选中."""
        governor = MultiAgentGovernor()
        proposal = AgentProposal(
            role=AgentRole.GROWTH, game_id="g1", resource="budget",
            action="increase", priority=0.8, confidence=0.9, requested_budget=100,
        )
        selected = governor.arbitrate([proposal], budget=200)
        assert len(selected) == 1
        assert selected[0] == proposal


# ═══════════════════════════════════════════════════════════════
# 4. arbitrate() 预算约束
# ═══════════════════════════════════════════════════════════════


class TestBudgetConstraint:
    """arbitrate() 预算约束."""

    def test_exceeds_budget_skipped(self):
        """超预算的提案被跳过."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=150),
            AgentProposal(role=AgentRole.UA, game_id="g2", resource="campaign",
                          action="create", priority=0.5, confidence=0.8, requested_budget=100),
        ]
        selected = governor.arbitrate(proposals, budget=200)
        # 高优先级 150 选中, 剩余 50 不够 100, 跳过
        assert len(selected) == 1
        assert selected[0].requested_budget == 150

    def test_exact_budget(self):
        """恰好用完预算."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=100),
            AgentProposal(role=AgentRole.UA, game_id="g2", resource="campaign",
                          action="create", priority=0.5, confidence=0.8, requested_budget=100),
        ]
        selected = governor.arbitrate(proposals, budget=200)
        assert len(selected) == 2

    def test_zero_budget_selects_nothing(self):
        """零预算不选任何提案."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=100),
        ]
        selected = governor.arbitrate(proposals, budget=0)
        assert len(selected) == 0

    def test_zero_cost_proposal_always_selected(self):
        """零成本提案总被选中 (只要预算>=0)."""
        governor = MultiAgentGovernor()
        proposal = AgentProposal(
            role=AgentRole.STRATEGY, game_id="g1", resource="strategy",
            action="propose", priority=0.5, confidence=0.5, requested_budget=0,
        )
        selected = governor.arbitrate([proposal], budget=0)
        assert len(selected) == 1


# ═══════════════════════════════════════════════════════════════
# 5. arbitrate() 优先级排序
# ═══════════════════════════════════════════════════════════════


class TestPriorityOrdering:
    """arbitrate() 优先级排序."""

    def test_higher_priority_selected_first(self):
        """高优先级先选."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.UA, game_id="g2", resource="campaign",
                          action="create", priority=0.5, confidence=0.8, requested_budget=100),
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=100),
        ]
        selected = governor.arbitrate(proposals, budget=100)
        assert len(selected) == 1
        assert selected[0].priority == 0.9

    def test_tie_break_by_confidence(self):
        """同优先级按 confidence 排序."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.UA, game_id="g2", resource="campaign",
                          action="create", priority=0.8, confidence=0.7, requested_budget=100),
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.8, confidence=0.9, requested_budget=100),
        ]
        selected = governor.arbitrate(proposals, budget=100)
        assert len(selected) == 1
        assert selected[0].confidence == 0.9


# ═══════════════════════════════════════════════════════════════
# 6. arbitrate() 资源冲突解决
# ═══════════════════════════════════════════════════════════════


class TestResourceConflict:
    """arbitrate() 资源冲突解决."""

    def test_same_resource_only_one_winner(self):
        """同 game+resource 只有一个赢家."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.7, confidence=0.8, requested_budget=100),
            AgentProposal(role=AgentRole.UA, game_id="g1", resource="budget",
                          action="reallocate", priority=0.9, confidence=0.9, requested_budget=100),
        ]
        selected = governor.arbitrate(proposals, budget=200)
        assert len(selected) == 1
        assert selected[0].priority == 0.9  # 高优先级胜出

    def test_different_resources_both_selected(self):
        """不同 resource 都可被选."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=100),
            AgentProposal(role=AgentRole.UA, game_id="g1", resource="campaign",
                          action="create", priority=0.5, confidence=0.8, requested_budget=50),
        ]
        selected = governor.arbitrate(proposals, budget=200)
        assert len(selected) == 2

    def test_different_games_same_resource_both_selected(self):
        """不同 game 同 resource 都可被选."""
        governor = MultiAgentGovernor()
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=100),
            AgentProposal(role=AgentRole.GROWTH, game_id="g2", resource="budget",
                          action="increase", priority=0.5, confidence=0.8, requested_budget=50),
        ]
        selected = governor.arbitrate(proposals, budget=200)
        assert len(selected) == 2


# ═══════════════════════════════════════════════════════════════
# 7. takeover/release 人工接管
# ═══════════════════════════════════════════════════════════════


class TestHumanTakeover:
    """takeover/release 人工接管."""

    def test_takeover_requires_authorization(self):
        """takeover 需要授权."""
        governor = MultiAgentGovernor()
        assert governor.takeover(authorized=False) is False
        assert governor.human_takeover is False

    def test_takeover_succeeds_when_authorized(self):
        """授权后 takeover 成功."""
        governor = MultiAgentGovernor()
        assert governor.takeover(authorized=True) is True
        assert governor.human_takeover is True

    def test_takeover_blocks_arbitration(self):
        """接管后 arbitrate 返回空."""
        governor = MultiAgentGovernor()
        governor.takeover(authorized=True)
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=100),
        ]
        assert governor.arbitrate(proposals, budget=200) == []

    def test_release_requires_authorization(self):
        """release 需要授权."""
        governor = MultiAgentGovernor()
        governor.takeover(authorized=True)
        assert governor.release(authorized=False) is False
        assert governor.human_takeover is True

    def test_release_succeeds_when_authorized(self):
        """授权后 release 成功."""
        governor = MultiAgentGovernor()
        governor.takeover(authorized=True)
        assert governor.release(authorized=True) is True
        assert governor.human_takeover is False

    def test_release_restores_arbitration(self):
        """release 后恢复仲裁."""
        governor = MultiAgentGovernor()
        governor.takeover(authorized=True)
        governor.release(authorized=True)
        proposals = [
            AgentProposal(role=AgentRole.GROWTH, game_id="g1", resource="budget",
                          action="increase", priority=0.9, confidence=0.9, requested_budget=100),
        ]
        selected = governor.arbitrate(proposals, budget=200)
        assert len(selected) == 1


# ═══════════════════════════════════════════════════════════════
# 8. AgentProposal 数据结构
# ═══════════════════════════════════════════════════════════════


class TestAgentProposal:
    """AgentProposal 数据结构."""

    def test_default_budget_zero(self):
        """默认 requested_budget=0."""
        proposal = AgentProposal(
            role=AgentRole.STRATEGY, game_id="g1", resource="strategy",
            action="propose", priority=0.5, confidence=0.5,
        )
        assert proposal.requested_budget == 0.0

    def test_proposal_is_frozen(self):
        """AgentProposal 是 frozen dataclass."""
        proposal = AgentProposal(
            role=AgentRole.STRATEGY, game_id="g1", resource="strategy",
            action="propose", priority=0.5, confidence=0.5,
        )
        with pytest.raises(Exception):
            proposal.priority = 0.9  # type: ignore
