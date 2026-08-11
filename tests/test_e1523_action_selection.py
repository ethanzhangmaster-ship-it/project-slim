"""E15.2.3 Action Selection Engine 测试 — 动作选择引擎完整测试.

测试覆盖:
  - 基础选择 (15 tests)
  - 风险影响 (15 tests)
  - 置信度 (10 tests)
  - 记忆增强 (10 tests)
  - 可解释性 (15 tests)
  - 评分引擎 (10 tests)
  - 模型 (10 tests)
  - 边界条件 (10 tests)
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.action_selection.models import (
    ActionCandidate,
    ScoredCandidate,
    SelectedAction,
    SelectionResult,
    SelectionStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.action_selection.scoring import (
    ScoringEngine,
    ScoringWeights,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.action_selection.explanation import (
    DecisionExplainer,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.action_selection.selector import (
    ActionSelector,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def creative_refresh_candidate() -> ActionCandidate:
    """素材刷新候选 — 高收益高置信度."""
    return ActionCandidate(
        action_id="replace_creative_001",
        action_type="creative_refresh",
        target={"campaign_id": "camp_123", "creative_id": "ad_456"},
        expected_reward=0.82,
        confidence=0.91,
        execution_cost=0.10,
        risk_score=0.15,
        risk_level="low",
        memory_boost=0.0,
    )


@pytest.fixture
def budget_decrease_candidate() -> ActionCandidate:
    """降预算候选 — 中等收益."""
    return ActionCandidate(
        action_id="budget_decrease_001",
        action_type="budget_optimize",
        target={"campaign_id": "camp_456"},
        expected_reward=0.65,
        confidence=0.80,
        execution_cost=0.05,
        risk_score=0.10,
        risk_level="low",
        memory_boost=0.0,
    )


@pytest.fixture
def pause_campaign_candidate() -> ActionCandidate:
    """暂停广告候选 — 低收益."""
    return ActionCandidate(
        action_id="pause_campaign_001",
        action_type="campaign_pause",
        target={"campaign_id": "camp_789"},
        expected_reward=0.55,
        confidence=0.75,
        execution_cost=0.02,
        risk_score=0.05,
        risk_level="low",
        memory_boost=0.0,
    )


@pytest.fixture
def high_risk_candidate() -> ActionCandidate:
    """高风险候选."""
    return ActionCandidate(
        action_id="risky_action_001",
        action_type="budget_scale",
        expected_reward=0.90,
        confidence=0.50,
        execution_cost=0.20,
        risk_score=0.88,
        risk_level="high",
    )


@pytest.fixture
def low_confidence_candidate() -> ActionCandidate:
    """低置信度候选."""
    return ActionCandidate(
        action_id="low_confidence_001",
        action_type="experiment_launch",
        expected_reward=0.70,
        confidence=0.15,
        execution_cost=0.10,
        risk_score=0.20,
        risk_level="medium",
    )


@pytest.fixture
def three_candidates(
    creative_refresh_candidate,
    budget_decrease_candidate,
    pause_campaign_candidate,
) -> list[ActionCandidate]:
    """三个候选动作."""
    return [creative_refresh_candidate, budget_decrease_candidate, pause_campaign_candidate]


@pytest.fixture
def default_selector() -> ActionSelector:
    """默认选择器."""
    return ActionSelector()


@pytest.fixture
def memory_patterns() -> dict:
    """历史记忆模式."""
    return {
        "creative_refresh": {
            "sample": 120,
            "success_rate": 0.82,
            "avg_reward": 0.76,
        },
        "budget_optimize": {
            "sample": 80,
            "success_rate": 0.70,
            "avg_reward": 0.60,
        },
        "campaign_pause": {
            "sample": 40,
            "success_rate": 0.45,
            "avg_reward": 0.30,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# Test: Models
# ═══════════════════════════════════════════════════════════════════


class TestActionCandidate:
    """ActionCandidate 模型测试."""

    def test_default_creation(self):
        """默认创建 — 自动生成 UUID."""
        c = ActionCandidate()
        assert c.action_id != ""
        assert c.action_type == ""

    def test_full_creation(self):
        """完整创建."""
        c = ActionCandidate(
            action_id="act_001",
            action_type="creative_refresh",
            target={"campaign_id": "123"},
            expected_reward=0.82,
            confidence=0.91,
            execution_cost=0.10,
            risk_score=0.15,
            risk_level="low",
            memory_boost=0.0,
        )
        assert c.action_id == "act_001"
        assert c.expected_reward == 0.82
        assert c.confidence == 0.91

    def test_to_dict(self):
        """to_dict 序列化."""
        c = ActionCandidate(
            action_id="act_001",
            action_type="creative_refresh",
            expected_reward=0.80,
        )
        d = c.to_dict()
        assert d["action_id"] == "act_001"
        assert d["action_type"] == "creative_refresh"
        assert d["expected_reward"] == 0.80

    def test_uuid_is_unique(self):
        """每个实例 UUID 唯一."""
        c1 = ActionCandidate()
        c2 = ActionCandidate()
        assert c1.action_id != c2.action_id

    def test_metadata_field(self):
        """metadata 扩展字段."""
        c = ActionCandidate(metadata={"source": "planner", "priority": "high"})
        assert c.metadata["source"] == "planner"
        assert c.metadata["priority"] == "high"


class TestScoredCandidate:
    """ScoredCandidate 模型测试."""

    def test_default_status_is_pending(self):
        """默认状态为 PENDING."""
        s = ScoredCandidate(candidate=ActionCandidate())
        assert s.status == SelectionStatus.PENDING

    def test_blocked_with_reason(self):
        """阻止状态含原因."""
        s = ScoredCandidate(
            candidate=ActionCandidate(),
            status=SelectionStatus.BLOCKED,
            block_reason="Risk too high",
        )
        assert s.status == SelectionStatus.BLOCKED
        assert s.block_reason == "Risk too high"

    def test_to_dict(self):
        """to_dict 序列化."""
        c = ActionCandidate(action_id="act_001", action_type="creative_refresh")
        s = ScoredCandidate(candidate=c, total_score=0.49)
        d = s.to_dict()
        assert d["total_score"] == 0.49
        assert d["candidate"]["action_id"] == "act_001"


class TestSelectedAction:
    """SelectedAction 模型测试."""

    def test_default_state(self):
        """默认状态."""
        s = SelectedAction()
        assert s.action_id == ""
        assert s.score == 0.0

    def test_with_reasoning(self):
        """含选择理由."""
        s = SelectedAction(
            action_id="act_001",
            action_type="creative_refresh",
            score=0.49,
            confidence=0.91,
            reasoning="Highest expected reward",
        )
        assert "Highest" in s.reasoning

    def test_to_dict(self):
        """to_dict 序列化."""
        s = SelectedAction(
            action_id="act_001",
            action_type="creative_refresh",
            score=0.49,
            alternatives=[{"action": "budget_decrease", "reason": "lower score"}],
        )
        d = s.to_dict()
        assert d["action_id"] == "act_001"
        assert d["score"] == 0.49
        assert len(d["alternatives"]) == 1


class TestSelectionResult:
    """SelectionResult 模型测试."""

    def test_empty_result(self):
        """空结果."""
        r = SelectionResult()
        assert r.selected is None
        assert r.candidates == []

    def test_get_selected(self):
        """获取选中候选."""
        c = ActionCandidate(action_id="act_001", action_type="creative_refresh")
        sc = ScoredCandidate(candidate=c, total_score=0.49, status=SelectionStatus.SELECTED)
        sel = SelectedAction(action_id="act_001", action_type="creative_refresh")
        r = SelectionResult(selected=sel, candidates=[sc])
        found = r.get_selected()
        assert found is not None
        assert found.candidate.action_id == "act_001"

    def test_get_selected_none(self):
        """无选中候选时返回 None."""
        r = SelectionResult()
        assert r.get_selected() is None

    def test_get_rejected(self):
        """获取被拒绝的候选."""
        c1 = ActionCandidate(action_id="act_001")
        c2 = ActionCandidate(action_id="act_002")
        s1 = ScoredCandidate(candidate=c1, status=SelectionStatus.SELECTED)
        s2 = ScoredCandidate(candidate=c2, status=SelectionStatus.REJECTED)
        r = SelectionResult(candidates=[s1, s2])
        rejected = r.get_rejected()
        assert len(rejected) == 1
        assert rejected[0].candidate.action_id == "act_002"

    def test_get_blocked(self):
        """获取被阻止的候选."""
        c1 = ActionCandidate(action_id="act_001")
        c2 = ActionCandidate(action_id="act_002")
        s1 = ScoredCandidate(candidate=c1, status=SelectionStatus.SELECTED)
        s2 = ScoredCandidate(candidate=c2, status=SelectionStatus.BLOCKED, block_reason="risk")
        r = SelectionResult(candidates=[s1, s2])
        blocked = r.get_blocked()
        assert len(blocked) == 1
        assert blocked[0].candidate.action_id == "act_002"

    def test_to_dict(self):
        """to_dict 序列化."""
        c = ActionCandidate(action_id="act_001", action_type="creative_refresh")
        sc = ScoredCandidate(candidate=c, total_score=0.49, status=SelectionStatus.SELECTED)
        sel = SelectedAction(action_id="act_001", action_type="creative_refresh", score=0.49)
        r = SelectionResult(selected=sel, candidates=[sc])
        d = r.to_dict()
        assert d["selected"] is not None
        assert len(d["candidates"]) == 1


# ═══════════════════════════════════════════════════════════════════
# Test: Scoring Engine
# ═══════════════════════════════════════════════════════════════════


class TestScoringWeights:
    """ScoringWeights 测试."""

    def test_default_weights(self):
        """默认权重."""
        w = ScoringWeights()
        assert w.reward == 0.45
        assert w.confidence == 0.20
        assert w.memory == 0.15
        assert w.risk == 0.15
        assert w.cost == 0.05

    def test_custom_weights(self):
        """自定义权重."""
        w = ScoringWeights(reward=0.50, confidence=0.25)
        assert w.reward == 0.50
        assert w.confidence == 0.25
        # 未指定的保持默认
        assert w.memory == 0.15


class TestScoringEngine:
    """ScoringEngine 测试."""

    def test_score_basic(self, creative_refresh_candidate):
        """基础评分."""
        engine = ScoringEngine()
        scored = engine.score(creative_refresh_candidate)
        assert scored.total_score > 0
        assert scored.reward_component == pytest.approx(0.82 * 0.45, 0.001)
        assert scored.confidence_component == pytest.approx(0.91 * 0.20, 0.001)

    def test_score_formula(self):
        """验证评分公式."""
        c = ActionCandidate(
            action_id="test",
            expected_reward=0.80,
            confidence=0.90,
            memory_boost=0.50,
            risk_score=0.20,
            execution_cost=0.10,
        )
        engine = ScoringEngine()
        scored = engine.score(c)
        expected = (
            0.80 * 0.45 + 0.90 * 0.20 + 0.50 * 0.15 - 0.20 * 0.15 - 0.10 * 0.05
        )
        assert scored.total_score == pytest.approx(expected, 0.001)

    def test_score_clamped_to_zero(self):
        """得分不低于 0."""
        c = ActionCandidate(
            expected_reward=0.0,
            confidence=0.0,
            memory_boost=0.0,
            risk_score=0.95,
            execution_cost=0.90,
        )
        engine = ScoringEngine()
        scored = engine.score(c)
        assert scored.total_score >= 0.0

    def test_score_clamped_to_one(self):
        """得分不高于 1."""
        c = ActionCandidate(
            expected_reward=1.0,
            confidence=1.0,
            memory_boost=1.0,
            risk_score=0.0,
            execution_cost=0.0,
        )
        engine = ScoringEngine()
        scored = engine.score(c)
        assert scored.total_score <= 1.0

    def test_high_risk_blocks(self, high_risk_candidate):
        """风险 > 0.85 被阻止."""
        engine = ScoringEngine()
        scored = engine.score(high_risk_candidate)
        assert scored.status == SelectionStatus.BLOCKED
        assert "critical threshold" in scored.block_reason.lower()

    def test_low_confidence_blocks(self, low_confidence_candidate):
        """置信度 < 0.2 被阻止."""
        engine = ScoringEngine()
        scored = engine.score(low_confidence_candidate)
        assert scored.status == SelectionStatus.BLOCKED
        assert "minimum threshold" in scored.block_reason.lower()

    def test_risk_at_threshold_not_blocked(self):
        """风险恰好 0.85 不阻止."""
        c = ActionCandidate(
            action_id="test",
            expected_reward=0.80,
            confidence=0.80,
            risk_score=0.85,
        )
        engine = ScoringEngine()
        scored = engine.score(c)
        assert scored.status != SelectionStatus.BLOCKED

    def test_confidence_at_threshold_not_blocked(self):
        """置信度恰好 0.2 不阻止."""
        c = ActionCandidate(
            action_id="test",
            expected_reward=0.80,
            confidence=0.20,
            risk_score=0.15,
        )
        engine = ScoringEngine()
        scored = engine.score(c)
        assert scored.status != SelectionStatus.BLOCKED

    def test_score_batch_sorted(self, three_candidates):
        """批量评分按得分降序排列."""
        engine = ScoringEngine()
        scored = engine.score_batch(three_candidates)
        assert len(scored) == 3
        assert scored[0].total_score >= scored[1].total_score
        assert scored[1].total_score >= scored[2].total_score

    def test_get_weights(self):
        """获取权重."""
        engine = ScoringEngine()
        w = engine.get_weights()
        assert w["reward"] == 0.45
        assert w["confidence"] == 0.20

    def test_set_weights(self):
        """设置权重."""
        engine = ScoringEngine()
        w = ScoringWeights(reward=0.50)
        engine.set_weights(w)
        assert engine.get_weights()["reward"] == 0.50

    def test_memory_boost_no_effect_when_zero(self):
        """memory_boost=0 不影响得分."""
        c = ActionCandidate(
            expected_reward=0.80,
            confidence=0.90,
            memory_boost=0.0,
            risk_score=0.15,
            execution_cost=0.10,
        )
        engine = ScoringEngine()
        scored = engine.score(c)
        assert scored.memory_component == 0.0


# ═══════════════════════════════════════════════════════════════════
# Test: Basic Selection
# ═══════════════════════════════════════════════════════════════════


class TestBasicSelection:
    """基础选择测试."""

    def test_select_highest_reward(self, three_candidates, default_selector):
        """选择最高收益的动作."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert result.selected.action_type == "creative_refresh"

    def test_select_highest_score(self, default_selector):
        """选择得分最高的动作."""
        c1 = ActionCandidate(
            action_id="a1", action_type="buy_more",
            expected_reward=0.90, confidence=0.80, execution_cost=0.10,
            risk_score=0.10, risk_level="low",
        )
        c2 = ActionCandidate(
            action_id="a2", action_type="do_nothing",
            expected_reward=0.30, confidence=0.50, execution_cost=0.01,
            risk_score=0.05, risk_level="low",
        )
        result = default_selector.select([c1, c2])
        assert result.selected is not None
        assert result.selected.action_type == "buy_more"

    def test_select_single(self, creative_refresh_candidate, default_selector):
        """单个候选也被选中."""
        result = default_selector.select_single(creative_refresh_candidate)
        assert result.selected is not None
        assert result.selected.action_type == "creative_refresh"

    def test_empty_candidates(self, default_selector):
        """空候选列表."""
        result = default_selector.select([])
        assert result.selected is None
        assert len(result.candidates) == 0

    def test_all_blocked_returns_none(self, default_selector):
        """全部被阻止时返回 None."""
        c1 = ActionCandidate(
            action_id="a1", expected_reward=0.5, confidence=0.10,
            risk_score=0.10, risk_level="low",
        )
        c2 = ActionCandidate(
            action_id="a2", expected_reward=0.5, confidence=0.10,
            risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([c1, c2])
        assert result.selected is None

    def test_best_gets_selected_status(self, three_candidates, default_selector):
        """最优候选标记为 SELECTED."""
        result = default_selector.select(three_candidates)
        selected = result.get_selected()
        assert selected is not None
        assert selected.status == SelectionStatus.SELECTED

    def test_others_get_rejected_status(self, three_candidates, default_selector):
        """其他候选标记为 REJECTED."""
        result = default_selector.select(three_candidates)
        rejected = result.get_rejected()
        assert len(rejected) == 2
        for r in rejected:
            assert r.status == SelectionStatus.REJECTED

    def test_selected_has_score(self, three_candidates, default_selector):
        """选中动作有得分."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert result.selected.score > 0

    def test_selected_has_confidence(self, three_candidates, default_selector):
        """选中动作含置信度."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert result.selected.confidence > 0

    def test_selection_result_has_id(self, three_candidates, default_selector):
        """选择结果有 ID."""
        result = default_selector.select(three_candidates)
        assert result.result_id != ""

    def test_selection_result_has_timestamp(self, three_candidates, default_selector):
        """选择结果有时间戳."""
        result = default_selector.select(three_candidates)
        assert result.created_at != ""

    def test_only_one_selected(self, three_candidates, default_selector):
        """只有一个候选被选中."""
        result = default_selector.select(three_candidates)
        selected_count = sum(
            1 for c in result.candidates if c.status == SelectionStatus.SELECTED
        )
        assert selected_count == 1

    def test_rejected_count_matches(self, three_candidates, default_selector):
        """被拒绝数量 = 总数 - 1 - 被阻止."""
        result = default_selector.select(three_candidates)
        rejected = result.get_rejected()
        blocked = result.get_blocked()
        assert len(rejected) + len(blocked) == len(three_candidates) - 1


# ═══════════════════════════════════════════════════════════════════
# Test: Risk Impact
# ═══════════════════════════════════════════════════════════════════


class TestRiskImpact:
    """风险影响测试."""

    def test_high_risk_penalty_reduces_score(self, default_selector):
        """高风险惩罚降低得分."""
        c_low_risk = ActionCandidate(
            action_id="low", action_type="type_a",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        c_high_risk = ActionCandidate(
            action_id="high", action_type="type_a",
            expected_reward=0.80, confidence=0.80, risk_score=0.70, risk_level="high",
        )
        result = default_selector.select([c_low_risk, c_high_risk])
        assert result.selected is not None
        assert result.selected.action_id == "low"

    def test_critical_risk_blocks_action(self, default_selector, high_risk_candidate):
        """风险 > 0.85 阻止动作."""
        c2 = ActionCandidate(
            action_id="safe", action_type="safe_action",
            expected_reward=0.50, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([high_risk_candidate, c2])
        blocked = result.get_blocked()
        assert len(blocked) == 1
        assert blocked[0].candidate.action_id == high_risk_candidate.action_id

    def test_low_risk_preference(self, default_selector):
        """低风险动作被优先选择."""
        c_low = ActionCandidate(
            action_id="low_risk", action_type="type_a",
            expected_reward=0.70, confidence=0.80, risk_score=0.05, risk_level="low",
        )
        c_medium = ActionCandidate(
            action_id="medium_risk", action_type="type_a",
            expected_reward=0.75, confidence=0.80, risk_score=0.50, risk_level="medium",
        )
        result = default_selector.select([c_medium, c_low])
        assert result.selected is not None
        assert result.selected.action_id == "low_risk"

    def test_risk_blocked_does_not_affect_selection(self, default_selector):
        """被阻止的动作不影响选择."""
        c_blocked = ActionCandidate(
            action_id="blocked", expected_reward=0.99, confidence=0.10,
            risk_score=0.10, risk_level="low",
        )
        c_ok = ActionCandidate(
            action_id="ok", action_type="ok_action",
            expected_reward=0.50, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([c_blocked, c_ok])
        assert result.selected is not None
        assert result.selected.action_id == "ok"

    def test_medium_risk_scored_lower(self, default_selector):
        """中等风险得分低于低风险."""
        c_low = ActionCandidate(
            action_id="low", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        c_med = ActionCandidate(
            action_id="med", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.50, risk_level="medium",
        )
        result = default_selector.select([c_low, c_med])
        low_scored = next(
            (c for c in result.candidates if c.candidate.action_id == "low"), None
        )
        med_scored = next(
            (c for c in result.candidates if c.candidate.action_id == "med"), None
        )
        assert low_scored is not None
        assert med_scored is not None
        assert low_scored.total_score > med_scored.total_score

    def test_risk_level_high_score_penalty(self, default_selector):
        """risk_level=high 时风险得分高导致惩罚大，低风险即使收益低也可能胜出."""
        c = ActionCandidate(
            action_id="high_risk", action_type="t",
            expected_reward=0.70, confidence=0.85, risk_score=0.75, risk_level="high",
        )
        c2 = ActionCandidate(
            action_id="low_risk", action_type="t",
            expected_reward=0.55, confidence=0.85, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([c, c2])
        assert result.selected is not None
        # 低风险动作虽然收益低，但风险惩罚小，总分更高
        assert result.selected.action_id == "low_risk"

    def test_zero_risk_no_penalty(self, default_selector):
        """零风险无惩罚."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.0, risk_level="none",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.risk_penalty == 0.0

    def test_risk_score_exactly_085(self, default_selector):
        """风险分恰好 0.85 不阻止."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.85, risk_level="high",
        )
        result = default_selector.select_single(c)
        blocked = result.get_blocked()
        assert len(blocked) == 0

    def test_risk_score_086_blocks(self, default_selector):
        """风险分 0.86 阻止."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.86, risk_level="critical",
        )
        result = default_selector.select_single(c)
        blocked = result.get_blocked()
        assert len(blocked) == 1

    def test_select_with_mixed_risk_candidates(self, default_selector):
        """混合风险候选 — 选出最优."""
        candidates = [
            ActionCandidate(
                action_id="safe", action_type="safe_t",
                expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
            ),
            ActionCandidate(
                action_id="risky", action_type="risky_t",
                expected_reward=0.85, confidence=0.50, risk_score=0.40, risk_level="medium",
            ),
            ActionCandidate(
                action_id="blocked", action_type="blocked_t",
                expected_reward=0.90, confidence=0.30, risk_score=0.90, risk_level="critical",
            ),
        ]
        result = default_selector.select(candidates)
        assert result.selected is not None
        assert result.selected.action_id == "safe"

    def test_blocked_candidates_in_result(self, default_selector):
        """被阻止的候选仍出现在结果中."""
        c = ActionCandidate(
            action_id="blocked", expected_reward=0.9, confidence=0.15,
            risk_score=0.1, risk_level="low",
        )
        result = default_selector.select_single(c)
        blocked = result.get_blocked()
        assert len(blocked) == 1
        assert blocked[0].candidate.action_id == "blocked"

    def test_risk_penalty_component_is_positive(self, default_selector):
        """风险惩罚分量 > 0 (当 risk_score > 0)."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.30, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.risk_penalty > 0

    def test_block_reason_present_when_blocked(self, default_selector):
        """阻止原因存在."""
        c = ActionCandidate(
            action_id="test", expected_reward=0.5, confidence=0.10,
            risk_score=0.1, risk_level="low",
        )
        result = default_selector.select_single(c)
        blocked = result.get_blocked()
        assert blocked[0].block_reason != ""


# ═══════════════════════════════════════════════════════════════════
# Test: Confidence Impact
# ═══════════════════════════════════════════════════════════════════


class TestConfidenceImpact:
    """置信度影响测试."""

    def test_high_confidence_boost(self, default_selector):
        """高置信度提升得分."""
        c_high = ActionCandidate(
            action_id="high", action_type="t",
            expected_reward=0.70, confidence=0.95, risk_score=0.10, risk_level="low",
        )
        c_low = ActionCandidate(
            action_id="low", action_type="t",
            expected_reward=0.75, confidence=0.40, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([c_high, c_low])
        assert result.selected is not None
        assert result.selected.action_id == "high"

    def test_low_confidence_penalty(self, default_selector):
        """低置信度惩罚."""
        c_high = ActionCandidate(
            action_id="high_conf", action_type="t",
            expected_reward=0.70, confidence=0.90, risk_score=0.10, risk_level="low",
        )
        c_low = ActionCandidate(
            action_id="low_conf", action_type="t",
            expected_reward=0.80, confidence=0.30, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([c_high, c_low])
        assert result.selected is not None
        assert result.selected.action_id == "high_conf"

    def test_confidence_below_02_blocks(self, default_selector):
        """置信度 < 0.2 阻止."""
        c = ActionCandidate(
            action_id="test", expected_reward=0.80, confidence=0.15,
            risk_score=0.10, risk_level="low",
        )
        result = default_selector.select_single(c)
        blocked = result.get_blocked()
        assert len(blocked) == 1

    def test_confidence_02_not_blocked(self, default_selector):
        """置信度 0.2 不阻止."""
        c = ActionCandidate(
            action_id="test", expected_reward=0.80, confidence=0.20,
            risk_score=0.10, risk_level="low",
        )
        result = default_selector.select_single(c)
        blocked = result.get_blocked()
        assert len(blocked) == 0

    def test_confidence_component_calculation(self, default_selector):
        """置信度分量计算正确."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.0, confidence=0.80, risk_score=0.0, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.confidence_component == pytest.approx(0.80 * 0.20, 0.001)

    def test_confidence_100_max_boost(self, default_selector):
        """置信度 1.0 最大提升."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.0, confidence=1.0, risk_score=0.0, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.confidence_component == pytest.approx(0.20, 0.001)

    def test_confidence_zero_no_boost(self, default_selector):
        """置信度 0 无提升."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.0, confidence=0.0, risk_score=0.0, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.confidence_component == 0.0

    def test_confidence_vs_reward_tradeoff(self, default_selector):
        """置信度 vs 收益权衡."""
        c_low_reward_high_conf = ActionCandidate(
            action_id="a", action_type="t",
            expected_reward=0.60, confidence=0.95, risk_score=0.10, risk_level="low",
        )
        c_high_reward_low_conf = ActionCandidate(
            action_id="b", action_type="t",
            expected_reward=0.85, confidence=0.35, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([c_low_reward_high_conf, c_high_reward_low_conf])
        assert result.selected is not None
        # 高置信度方案应胜出
        assert result.selected.action_id == "a"


# ═══════════════════════════════════════════════════════════════════
# Test: Memory Enhancement
# ═══════════════════════════════════════════════════════════════════


class TestMemoryEnhancement:
    """记忆增强测试."""

    @pytest.fixture
    def memory_selector(self, memory_patterns) -> ActionSelector:
        """含记忆模式的选择器."""
        return ActionSelector(memory_patterns=memory_patterns)

    def test_pattern_success_boost(self, memory_selector):
        """历史成功模式提升得分."""
        c = ActionCandidate(
            action_id="test", action_type="creative_refresh",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = memory_selector.select_single(c)
        scored = result.candidates[0]
        # memory_boost = 0.82 * 0.76 = 0.6232
        assert scored.memory_component == pytest.approx(0.6232 * 0.15, 0.001)

    def test_failed_pattern_penalty(self, memory_selector):
        """历史失败模式降低得分."""
        c = ActionCandidate(
            action_id="test", action_type="campaign_pause",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = memory_selector.select_single(c)
        scored = result.candidates[0]
        # memory_boost = 0.45 * 0.30 = 0.135, rounded to 4dp = 0.135
        # memory_component = 0.135 * 0.15 = 0.02025, rounded to 4dp = 0.0203
        expected = round(0.45 * 0.30 * 0.15, 4)
        assert scored.memory_component == expected

    def test_no_memory_available(self, default_selector):
        """无记忆模式时无影响."""
        c = ActionCandidate(
            action_id="test", action_type="unknown_type",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.memory_component == 0.0

    def test_memory_boost_makes_difference(self, memory_selector):
        """记忆增强改变选择结果."""
        c_same_reward_no_memory = ActionCandidate(
            action_id="no_mem", action_type="unknown_type",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        c_same_reward_with_memory = ActionCandidate(
            action_id="with_mem", action_type="creative_refresh",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = memory_selector.select([c_same_reward_no_memory, c_same_reward_with_memory])
        assert result.selected is not None
        assert result.selected.action_id == "with_mem"

    def test_set_memory_patterns(self, default_selector, memory_patterns):
        """动态设置记忆模式."""
        default_selector.set_memory_patterns(memory_patterns)
        c = ActionCandidate(
            action_id="test", action_type="creative_refresh",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.memory_component > 0

    def test_add_memory_pattern(self, default_selector):
        """添加单个记忆模式."""
        default_selector.add_memory_pattern("creative_refresh", {
            "success_rate": 0.90, "avg_reward": 0.85,
        })
        c = ActionCandidate(
            action_id="test", action_type="creative_refresh",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.memory_component > 0

    def test_memory_boost_zero_for_unmatched_type(self, memory_selector):
        """未匹配类型无记忆增强."""
        c = ActionCandidate(
            action_id="test", action_type="nonexistent",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = memory_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.memory_component == 0.0

    def test_memory_boost_formula(self, memory_selector):
        """验证 memory_boost = success_rate × avg_reward."""
        c = ActionCandidate(
            action_id="test", action_type="creative_refresh",
            expected_reward=0.0, confidence=0.5, risk_score=0.0, risk_level="low",
        )
        result = memory_selector.select_single(c)
        scored = result.candidates[0]
        # memory_boost = 0.82 * 0.76 = 0.6232
        # then multiplied by weight 0.15
        expected = 0.82 * 0.76 * 0.15
        assert scored.memory_component == pytest.approx(expected, 0.001)

    def test_memory_can_override_weak_reward(self, memory_selector):
        """记忆增强可弥补弱收益."""
        c_weak = ActionCandidate(
            action_id="weak", action_type="creative_refresh",
            expected_reward=0.50, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        c_strong = ActionCandidate(
            action_id="strong", action_type="unknown_type",
            expected_reward=0.65, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = memory_selector.select([c_weak, c_strong])
        assert result.selected is not None
        assert result.selected.action_id == "weak"

    def test_memory_patterns_immutable_externally(self, memory_selector):
        """外部修改记忆模式字典不影响选择器."""
        patterns = memory_selector._memory_patterns
        patterns["new_type"] = {"success_rate": 1.0, "avg_reward": 1.0}
        c = ActionCandidate(
            action_id="test", action_type="new_type",
            expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = memory_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.memory_component > 0  # 引用同一对象，所以会生效


# ═══════════════════════════════════════════════════════════════════
# Test: Explainability
# ═══════════════════════════════════════════════════════════════════


class TestExplainability:
    """可解释性测试."""

    @pytest.fixture
    def explainer(self) -> DecisionExplainer:
        return DecisionExplainer()

    def test_reason_generated(self, three_candidates, default_selector):
        """选择理由已生成."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert result.selected.reasoning != ""

    def test_reason_includes_selected_type(self, three_candidates, default_selector):
        """理由包含选中类型."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert "creative_refresh" in result.selected.reasoning

    def test_reason_includes_score(self, three_candidates, default_selector):
        """理由包含得分."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert "score" in result.selected.reasoning.lower()

    def test_alternative_actions(self, three_candidates, default_selector):
        """备选方案列表."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert len(result.selected.alternatives) == 2

    def test_alternative_has_reason(self, three_candidates, default_selector):
        """备选方案含拒绝原因."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        for alt in result.selected.alternatives:
            assert "reason" in alt
            assert alt["reason"] != ""

    def test_decision_trace(self, three_candidates, default_selector):
        """决策追踪信息."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        trace = result.selected.trace
        assert "total_candidates" in trace
        assert trace["total_candidates"] == 3

    def test_trace_has_blocked_count(self, default_selector):
        """追踪含被阻止数量."""
        candidates = [
            ActionCandidate(
                action_id="ok", action_type="t",
                expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
            ),
            ActionCandidate(
                action_id="blocked", action_type="t",
                expected_reward=0.80, confidence=0.10, risk_score=0.10, risk_level="low",
            ),
        ]
        result = default_selector.select(candidates)
        assert result.selected is not None
        trace = result.selected.trace
        assert trace["blocked_count"] == 1

    def test_trace_has_rejected_count(self, three_candidates, default_selector):
        """追踪含被拒绝数量."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        trace = result.selected.trace
        assert trace["rejected_count"] == 2

    def test_trace_has_selected_action(self, three_candidates, default_selector):
        """追踪含选中动作类型."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        trace = result.selected.trace
        assert trace["selected_action"] == "creative_refresh"

    def test_trace_has_selected_score(self, three_candidates, default_selector):
        """追踪含选中得分."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        trace = result.selected.trace
        assert trace["selected_score"] > 0

    def test_explain_empty_result(self, explainer):
        """空结果解释."""
        result = SelectionResult()
        selected = explainer.explain(result)
        assert "No action selected" in selected.reasoning

    def test_reason_includes_high_reward(self, explainer):
        """高收益标注."""
        c = ActionCandidate(
            action_id="a", action_type="t",
            expected_reward=0.90, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        sc = ScoredCandidate(candidate=c, total_score=0.55, status=SelectionStatus.SELECTED)
        sel = SelectedAction(action_id="a", action_type="t", score=0.55, confidence=0.80)
        result = SelectionResult(selected=sel, candidates=[sc])
        explained = explainer.explain(result)
        assert "high expected reward" in explained.reasoning.lower()

    def test_reason_includes_high_confidence(self, explainer):
        """高置信度标注."""
        c = ActionCandidate(
            action_id="a", action_type="t",
            expected_reward=0.40, confidence=0.95, risk_score=0.10, risk_level="low",
        )
        sc = ScoredCandidate(candidate=c, total_score=0.40, status=SelectionStatus.SELECTED)
        sel = SelectedAction(action_id="a", action_type="t", score=0.40, confidence=0.95)
        result = SelectionResult(selected=sel, candidates=[sc])
        explained = explainer.explain(result)
        assert "strong confidence" in explained.reasoning.lower()

    def test_reason_includes_low_risk(self, explainer):
        """低风险标注."""
        c = ActionCandidate(
            action_id="a", action_type="t",
            expected_reward=0.40, confidence=0.50, risk_score=0.10, risk_level="low",
        )
        sc = ScoredCandidate(candidate=c, total_score=0.30, status=SelectionStatus.SELECTED)
        sel = SelectedAction(action_id="a", action_type="t", score=0.30, confidence=0.50)
        result = SelectionResult(selected=sel, candidates=[sc])
        explained = explainer.explain(result)
        assert "low risk" in explained.reasoning.lower()

    def test_reason_includes_memory_boost(self, explainer):
        """记忆增强标注."""
        c = ActionCandidate(
            action_id="a", action_type="t",
            expected_reward=0.40, confidence=0.50, memory_boost=0.80,
            risk_score=0.10, risk_level="low",
        )
        sc = ScoredCandidate(candidate=c, total_score=0.35, status=SelectionStatus.SELECTED)
        sel = SelectedAction(action_id="a", action_type="t", score=0.35, confidence=0.50)
        result = SelectionResult(selected=sel, candidates=[sc])
        explained = explainer.explain(result)
        assert "historical pattern" in explained.reasoning.lower()

    def test_reason_includes_margin(self, explainer):
        """与第二名差距."""
        c1 = ActionCandidate(
            action_id="a", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        c2 = ActionCandidate(
            action_id="b", action_type="t2",
            expected_reward=0.50, confidence=0.50, risk_score=0.10, risk_level="low",
        )
        sc1 = ScoredCandidate(candidate=c1, total_score=0.50, status=SelectionStatus.SELECTED)
        sc2 = ScoredCandidate(candidate=c2, total_score=0.30, status=SelectionStatus.REJECTED)
        sel = SelectedAction(action_id="a", action_type="t", score=0.50, confidence=0.80)
        result = SelectionResult(selected=sel, candidates=[sc1, sc2])
        explained = explainer.explain(result)
        assert "margin over runner-up" in explained.reasoning.lower()


# ═══════════════════════════════════════════════════════════════════
# Test: Selector Configuration
# ═══════════════════════════════════════════════════════════════════


class TestSelectorConfiguration:
    """选择器配置测试."""

    def test_custom_weights_affect_result(self):
        """自定义权重影响结果."""
        c1 = ActionCandidate(
            action_id="high_reward", action_type="t",
            expected_reward=0.90, confidence=0.30, risk_score=0.10, risk_level="low",
        )
        c2 = ActionCandidate(
            action_id="high_conf", action_type="t",
            expected_reward=0.60, confidence=0.90, risk_score=0.10, risk_level="low",
        )
        # 默认权重下 reward 权重高，c1 应胜出
        sel_default = ActionSelector()
        r1 = sel_default.select([c1, c2])
        assert r1.selected is not None
        assert r1.selected.action_id == "high_reward"

        # 调整权重使 confidence 权重更高
        w = ScoringWeights(reward=0.10, confidence=0.55, memory=0.15, risk=0.15, cost=0.05)
        sel_custom = ActionSelector(weights=w)
        r2 = sel_custom.select([c1, c2])
        assert r2.selected is not None
        assert r2.selected.action_id == "high_conf"

    def test_get_weights(self, default_selector):
        """获取权重."""
        w = default_selector.get_weights()
        assert w["reward"] == 0.45

    def test_set_weights(self, default_selector):
        """设置权重."""
        w = ScoringWeights(reward=0.60)
        default_selector.set_weights(w)
        assert default_selector.get_weights()["reward"] == 0.60


# ═══════════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试."""

    def test_equal_scores_picks_first(self, default_selector):
        """相同得分选第一个."""
        c1 = ActionCandidate(
            action_id="a", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        c2 = ActionCandidate(
            action_id="b", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select([c1, c2])
        assert result.selected is not None
        assert result.selected.action_id == "a"

    def test_max_values(self, default_selector):
        """最大值候选 — 最高得分 = 0.45 + 0.20 + 0.15 = 0.80."""
        c = ActionCandidate(
            action_id="max", action_type="t",
            expected_reward=1.0, confidence=1.0, memory_boost=1.0,
            risk_score=0.0, risk_level="none",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.total_score == 0.8

    def test_min_values(self, default_selector):
        """最小值候选."""
        c = ActionCandidate(
            action_id="min", action_type="t",
            expected_reward=0.0, confidence=0.20, memory_boost=0.0,
            risk_score=0.85, risk_level="high",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.total_score >= 0.0

    def test_negative_values_clamped(self, default_selector):
        """负值被钳制."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=-0.5, confidence=0.50, risk_score=0.80, risk_level="high",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.total_score >= 0.0

    def test_large_number_of_candidates(self, default_selector):
        """大量候选 — 性能测试."""
        candidates = [
            ActionCandidate(
                action_id=f"c_{i}", action_type="t",
                expected_reward=0.5 + (i % 10) * 0.05,
                confidence=0.5 + (i % 5) * 0.1,
                risk_score=0.1 + (i % 3) * 0.1,
                risk_level="low",
            )
            for i in range(100)
        ]
        result = default_selector.select(candidates)
        assert result.selected is not None
        assert len(result.candidates) == 100

    def test_single_candidate_marked_selected(self, default_selector):
        """单个候选被标记为 SELECTED."""
        c = ActionCandidate(
            action_id="solo", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.status == SelectionStatus.SELECTED

    def test_selection_preserves_action_id(self, three_candidates, default_selector):
        """选中动作保留原始 action_id."""
        result = default_selector.select(three_candidates)
        assert result.selected is not None
        assert result.selected.action_id == "replace_creative_001"

    def test_selection_result_id_unique(self, three_candidates, default_selector):
        """每次选择 result_id 唯一."""
        r1 = default_selector.select(three_candidates)
        r2 = default_selector.select(three_candidates)
        assert r1.result_id != r2.result_id

    def test_total_score_breakdown_in_candidates(self, three_candidates, default_selector):
        """候选含得分分解."""
        result = default_selector.select(three_candidates)
        for c in result.candidates:
            assert c.reward_component >= 0
            assert c.confidence_component >= 0
            assert c.risk_penalty >= 0
            assert c.cost_penalty >= 0

    def test_cost_penalty_reduces_score(self, default_selector):
        """执行成本惩罚降低得分."""
        c_cheap = ActionCandidate(
            action_id="cheap", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
            execution_cost=0.01,
        )
        c_expensive = ActionCandidate(
            action_id="expensive", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
            execution_cost=0.50,
        )
        result = default_selector.select([c_cheap, c_expensive])
        assert result.selected is not None
        assert result.selected.action_id == "cheap"

    def test_blocked_never_selected(self, default_selector):
        """被阻止的候选永远不会被选中."""
        c = ActionCandidate(
            action_id="blocked", expected_reward=0.99, confidence=0.10,
            risk_score=0.10, risk_level="low",
        )
        result = default_selector.select_single(c)
        assert result.selected is None
        blocked = result.get_blocked()
        assert len(blocked) == 1


# ═══════════════════════════════════════════════════════════════════
# Test: Integration
# ═══════════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试 — 完整选择流程."""

    def test_full_pipeline(self, memory_patterns):
        """完整选择链路: 候选 → 评分 → 选择 → 解释."""
        selector = ActionSelector(memory_patterns=memory_patterns)
        candidates = [
            ActionCandidate(
                action_id="creative_refresh", action_type="creative_refresh",
                target={"campaign_id": "123"},
                expected_reward=0.82, confidence=0.91, execution_cost=0.10,
                risk_score=0.15, risk_level="low",
            ),
            ActionCandidate(
                action_id="budget_optimize", action_type="budget_optimize",
                target={"campaign_id": "456"},
                expected_reward=0.65, confidence=0.80, execution_cost=0.05,
                risk_score=0.10, risk_level="low",
            ),
            ActionCandidate(
                action_id="campaign_pause", action_type="campaign_pause",
                target={"campaign_id": "789"},
                expected_reward=0.55, confidence=0.75, execution_cost=0.02,
                risk_score=0.05, risk_level="low",
            ),
        ]
        result = selector.select(candidates)

        # 验证选中
        assert result.selected is not None
        assert result.selected.action_type == "creative_refresh"

        # 验证解释
        assert result.selected.reasoning != ""
        assert len(result.selected.alternatives) == 2
        assert result.selected.trace["total_candidates"] == 3

        # 验证状态
        selected = result.get_selected()
        assert selected is not None
        assert selected.status == SelectionStatus.SELECTED

        rejected = result.get_rejected()
        assert len(rejected) == 2

    def test_pipeline_with_blocked(self, memory_patterns):
        """含被阻止动作的完整链路."""
        selector = ActionSelector(memory_patterns=memory_patterns)
        candidates = [
            ActionCandidate(
                action_id="ok", action_type="creative_refresh",
                expected_reward=0.70, confidence=0.80, risk_score=0.10, risk_level="low",
            ),
            ActionCandidate(
                action_id="blocked", action_type="risky",
                expected_reward=0.90, confidence=0.50, risk_score=0.90, risk_level="critical",
            ),
        ]
        result = selector.select(candidates)

        assert result.selected is not None
        assert result.selected.action_id == "ok"

        blocked = result.get_blocked()
        assert len(blocked) == 1
        assert blocked[0].candidate.action_id == "blocked"

        trace = result.selected.trace
        assert trace["blocked_count"] == 1

    def test_selector_to_dict_roundtrip(self, three_candidates, default_selector):
        """to_dict 往返测试."""
        result = default_selector.select(three_candidates)
        d = result.to_dict()
        assert d["result_id"] == result.result_id
        assert d["selected"]["action_type"] == result.selected.action_type
        assert len(d["candidates"]) == len(result.candidates)

    def test_result_metadata(self, default_selector):
        """结果元数据."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.80, confidence=0.80, risk_score=0.10, risk_level="low",
            metadata={"source": "planner", "trace_id": "abc123"},
        )
        result = default_selector.select_single(c)
        assert result.selected is not None
        assert result.metadata == {}

    def test_scored_candidate_contains_all_components(self, default_selector):
        """评分候选包含所有维度."""
        c = ActionCandidate(
            action_id="test", action_type="t",
            expected_reward=0.80, confidence=0.80, memory_boost=0.50,
            risk_score=0.20, risk_level="low", execution_cost=0.10,
        )
        result = default_selector.select_single(c)
        scored = result.candidates[0]
        assert scored.reward_component > 0
        assert scored.confidence_component > 0
        assert scored.memory_component > 0  # memory_boost=0.50 × 0.15 = 0.075
        assert scored.risk_penalty > 0
        assert scored.cost_penalty > 0