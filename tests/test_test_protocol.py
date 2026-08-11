"""E11 Phase 2.5 — Test Protocol & Decision Engine Tests。

测试覆盖：
  1. TestProtocol 预定义模板 (build_protocol)
  2. TestRecord 序列化
  3. TestProtocolEngine.decide_objective() — AEO/ROAS 决策树
  4. TestProtocolEngine.judge() — 测试结果判定
  5. TestProtocolEngine.decide_disposition() — 处置决策矩阵
  6. TestLifecycle 状态机转换
  7. TestLifecycleManager 批量管理
  8. BudgetManager 预算缩放
  9. BudgetManager 批量操作
  10. 完整决策流程集成测试
"""

from __future__ import annotations

import pytest

from market_ops.creative_repository import CreativeEntity
from market_ops.creative_repository.models.creative_entity import (
    AcquisitionData,
    RevenueData,
    CreativePerformance,
    CreativeSources,
    CreativeAsset,
    CreativeIdentity,
    CreativeAnalysis,
)
from market_ops.test_protocol import (
    TestObjective,
    TestResult,
    TestDecision,
    TestProtocol,
    TestRecord,
    CreativeMaturity,
    DEFAULT_PROTOCOLS,
    build_protocol,
    TestProtocolEngine,
    ObjectiveDecision,
    JudgementResult,
    DispositionDecision,
    TestStatus,
    TestLifecycle,
    TestLifecycleManager,
    BudgetAction,
    BudgetActionType,
    BudgetManager,
)


# ═══════════════════════════════════════════════════════════
# Helper: 创建测试用 CreativeEntity
# ═══════════════════════════════════════════════════════════

def _make_entity(
    creative_asset_id: str = "MW_IMG_260721_000123",
    spend: float = 5000.0,
    impressions: int = 100_000,
    clicks: int = 5_000,
    installs: int = 2000,
    iap_d1: float = 800.0,
    iap_d7: float = 3000.0,
    iap_d30: float = 10000.0,
    ad_d1: float = 200.0,
    ad_d7: float = 500.0,
    ad_d30: float = 2000.0,
) -> CreativeEntity:
    """创建带完整数据的测试 CreativeEntity。"""
    acq = AcquisitionData(
        spend=spend,
        impressions=impressions,
        clicks=clicks,
        installs=installs,
    )
    rev = RevenueData(
        iap_d1=iap_d1,
        iap_d7=iap_d7,
        iap_d30=iap_d30,
        ad_d1=ad_d1,
        ad_d7=ad_d7,
        ad_d30=ad_d30,
    )
    perf = CreativePerformance(acquisition=acq, revenue=rev)
    return CreativeEntity(
        creative_asset_id=creative_asset_id,
        identity=CreativeIdentity(name="test_creative"),
        sources=CreativeSources(facebook_id="fb_001"),
        asset=CreativeAsset(),
        performance=perf,
        analysis=CreativeAnalysis(),
        synced_sources={"facebook", "adjust"},
    )


# ═══════════════════════════════════════════════════════════
# Test 1: build_protocol 预定义模板
# ═══════════════════════════════════════════════════════════

class TestBuildProtocol:
    """测试 build_protocol() 预定义模板。"""

    def test_image_new_protocol(self):
        p = build_protocol("image", CreativeMaturity.NEW)
        assert p.creative_type == "image"
        assert p.maturity == CreativeMaturity.NEW
        assert p.test_objective == TestObjective.AEO_IAP
        assert p.test_budget == 50.0
        assert p.test_duration_days == 5
        assert p.min_installs == 50
        assert p.pass_roas_d7_min == 0.6
        assert p.pass_cpi_max == 5.0
        assert p.borderline_roas_min == 0.3
        assert p.winner_budget_multiplier == 2.0
        assert p.winner_max_budget == 300.0

    def test_image_variant_protocol(self):
        p = build_protocol("image", CreativeMaturity.VARIANT)
        assert p.creative_type == "image"
        assert p.maturity == CreativeMaturity.VARIANT
        assert p.test_duration_days == 3
        assert p.min_installs == 30
        assert p.pass_roas_d7_min == 0.8
        assert p.winner_budget_multiplier == 3.0
        assert p.winner_max_budget == 500.0

    def test_video_new_protocol(self):
        p = build_protocol("video", CreativeMaturity.NEW)
        assert p.creative_type == "video"
        assert p.test_budget == 80.0
        assert p.test_duration_days == 7
        assert p.min_installs == 70
        assert p.pass_roas_d7_min == 0.6
        assert p.pass_cpi_max == 6.0
        assert p.winner_max_budget == 400.0

    def test_video_variant_protocol(self):
        p = build_protocol("video", CreativeMaturity.VARIANT)
        assert p.creative_type == "video"
        assert p.test_duration_days == 5
        assert p.min_installs == 50
        assert p.pass_roas_d7_min == 0.8
        assert p.winner_max_budget == 600.0

    def test_scale_roas_protocol(self):
        p = build_protocol("image", CreativeMaturity.LEGACY)
        assert p.maturity == CreativeMaturity.LEGACY
        assert p.test_objective == TestObjective.AEO_ROAS
        assert p.test_budget == 200.0
        assert p.test_duration_days == 14
        assert p.min_installs == 100
        assert p.pass_roas_d7_min == 1.0
        assert p.winner_max_budget == 1000.0

    def test_fallback_to_default(self):
        p = build_protocol("3d_model", CreativeMaturity.NEW)
        assert p.creative_type == "image"  # fallback
        assert p.test_budget == 50.0

    def test_all_default_protocols_have_required_fields(self):
        for key, p in DEFAULT_PROTOCOLS.items():
            assert p.test_budget > 0, f"{key}: test_budget"
            assert p.test_duration_days > 0, f"{key}: test_duration_days"
            assert p.min_installs > 0, f"{key}: min_installs"
            assert p.pass_roas_d7_min > 0, f"{key}: pass_roas_d7_min"
            assert p.pass_cpi_max > 0, f"{key}: pass_cpi_max"

    def test_protocol_to_dict_from_dict(self):
        p = build_protocol("image", CreativeMaturity.NEW)
        d = p.to_dict()
        p2 = TestProtocol.from_dict(d)
        assert p2.creative_type == p.creative_type
        assert p2.test_budget == p.test_budget
        assert p2.test_objective == p.test_objective


# ═══════════════════════════════════════════════════════════
# Test 2: TestProtocolEngine.decide_objective() — AEO/ROAS 决策树
# ═══════════════════════════════════════════════════════════

class TestDecideObjective:
    """测试 AEO/ROAS 决策树。"""

    def test_new_creative_returns_aeo(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(maturity=CreativeMaturity.NEW)
        assert decision.objective == TestObjective.AEO_IAP
        assert decision.confidence > 0.9

    def test_new_creative_with_entity_returns_aeo(self):
        entity = _make_entity(spend=100, installs=20)
        engine = TestProtocolEngine()
        decision = engine.decide_objective(entity=entity, maturity=CreativeMaturity.NEW)
        assert decision.objective == TestObjective.AEO_IAP

    def test_variant_no_data_returns_aeo(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            maturity=CreativeMaturity.VARIANT,
            has_historical_data=False,
        )
        assert decision.objective == TestObjective.AEO_IAP

    def test_variant_with_good_roas_returns_roas(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            maturity=CreativeMaturity.VARIANT,
            has_historical_data=True,
            historical_roas_d7=0.9,
        )
        assert decision.objective == TestObjective.AEO_ROAS
        assert decision.confidence > 0.8

    def test_variant_with_moderate_roas_returns_roas(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            maturity=CreativeMaturity.VARIANT,
            has_historical_data=True,
            historical_roas_d7=0.65,
        )
        assert decision.objective == TestObjective.AEO_ROAS
        assert decision.confidence > 0.5

    def test_variant_low_roas_returns_aeo(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            maturity=CreativeMaturity.VARIANT,
            has_historical_data=True,
            historical_roas_d7=0.3,
        )
        assert decision.objective == TestObjective.AEO_IAP

    def test_legacy_high_roas_returns_roas(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            maturity=CreativeMaturity.LEGACY,
            has_historical_data=True,
            historical_roas_d7=1.5,
        )
        assert decision.objective == TestObjective.AEO_ROAS
        assert decision.confidence > 0.85

    def test_legacy_borderline_roas_returns_roas_cautiously(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            maturity=CreativeMaturity.LEGACY,
            has_historical_data=True,
            historical_roas_d7=0.75,
        )
        assert decision.objective == TestObjective.AEO_ROAS
        assert decision.confidence < 0.7

    def test_legacy_low_roas_returns_aeo(self):
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            maturity=CreativeMaturity.LEGACY,
            has_historical_data=True,
            historical_roas_d7=0.5,
        )
        assert decision.objective == TestObjective.AEO_IAP

    def test_entity_with_revenue_switches_to_roas(self):
        """有 revenue 数据的 entity 自动切换到 ROAS。"""
        entity = _make_entity(spend=5000, installs=2000, iap_d30=15000, ad_d30=3000)
        # ROAS = 18000/5000 = 3.6
        engine = TestProtocolEngine()
        decision = engine.decide_objective(
            entity=entity,
            maturity=CreativeMaturity.VARIANT,
        )
        assert decision.objective == TestObjective.AEO_ROAS

    def test_objective_decision_to_dict(self):
        d = ObjectiveDecision(
            objective=TestObjective.AEO_ROAS,
            reason="test",
            confidence=0.85,
        )
        assert d.to_dict()["objective"] == "AEO_ROAS"


# ═══════════════════════════════════════════════════════════
# Test 3: TestProtocolEngine.judge() — 测试结果判定
# ═══════════════════════════════════════════════════════════

class TestJudge:
    """测试 judge() 判定逻辑。"""

    def test_pass_high_roas_low_cpi(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=0.8,
            cpi=3.0,
            installs=100,
            spend=200.0,
        )
        assert result.result == TestResult.PASSED

    def test_pass_borderline_roas_ok_cpi(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=0.65,
            cpi=4.0,
            installs=80,
            spend=150.0,
        )
        assert result.result == TestResult.PASSED

    def test_fail_low_roas(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=0.2,
            cpi=4.0,
            installs=100,
            spend=200.0,
        )
        assert result.result == TestResult.FAILED

    def test_borderline_roas_between(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=0.5,
            cpi=7.0,
            installs=100,
            spend=200.0,
        )
        assert result.result == TestResult.BORDERLINE

    def test_borderline_roas_ok_but_cpi_high(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=0.7,
            cpi=6.0,
            installs=100,
            spend=200.0,
        )
        assert result.result == TestResult.BORDERLINE

    def test_insufficient_installs(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=10.0,
            cpi=1.0,
            installs=10,
            spend=200.0,
        )
        assert result.result == TestResult.INSUFFICIENT_DATA

    def test_insufficient_spend(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=10.0,
            cpi=1.0,
            installs=100,
            spend=50.0,
        )
        assert result.result == TestResult.INSUFFICIENT_DATA

    def test_judge_from_entity(self):
        """从 CreativeEntity 读取数据判定。"""
        entity = _make_entity(spend=5000, installs=2000, iap_d30=15000, ad_d30=3000)
        protocol = build_protocol("image", CreativeMaturity.NEW)
        engine = TestProtocolEngine()
        result = engine.judge(entity=entity, protocol=protocol)
        # ROAS_D7 = (3000+500)/5000 = 0.7, CPI = 5000/2000 = 2.5
        assert result.result == TestResult.PASSED

    def test_judgement_result_to_dict(self):
        r = JudgementResult(
            result=TestResult.PASSED,
            roas_d7=1.5,
            cpi=2.0,
            installs=200,
            spend=400.0,
            reason="test",
        )
        d = r.to_dict()
        assert d["result"] == "PASSED"
        assert d["roas_d7"] == 1.5

    def test_zero_installs_edge_case(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        result = engine.judge(
            protocol=protocol,
            roas_d7=0.0,
            cpi=0.0,
            installs=0,
            spend=0.0,
        )
        assert result.result == TestResult.INSUFFICIENT_DATA


# ═══════════════════════════════════════════════════════════
# Test 4: TestProtocolEngine.decide_disposition() — 处置决策矩阵
# ═══════════════════════════════════════════════════════════

class TestDecideDisposition:
    """测试处置决策矩阵。"""

    def test_passed_strong_winner_scale_3x(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        judgement = JudgementResult(
            result=TestResult.PASSED,
            roas_d7=1.5,
            cpi=2.0,
            installs=100,
            spend=200.0,
        )
        disp = engine.decide_disposition(judgement, protocol)
        assert disp.decision == TestDecision.SCALE
        assert disp.should_create_new_campaign is True
        assert disp.new_objective == TestObjective.AEO_ROAS
        assert disp.new_budget == 150.0  # 50 * 3 = 150

    def test_passed_standard_winner_scale_2x(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        judgement = JudgementResult(
            result=TestResult.PASSED,
            roas_d7=0.9,
            cpi=4.0,
            installs=100,
            spend=200.0,
        )
        disp = engine.decide_disposition(judgement, protocol)
        assert disp.decision == TestDecision.SCALE
        assert disp.new_budget == 100.0  # 50 * 2 = 100

    def test_failed_clear_kill(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        judgement = JudgementResult(
            result=TestResult.FAILED,
            roas_d7=0.1,
            cpi=10.0,
            installs=100,
            spend=200.0,
        )
        disp = engine.decide_disposition(judgement, protocol)
        assert disp.decision == TestDecision.KILL
        assert disp.new_budget == 0.0

    def test_failed_borderline_reduce(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        judgement = JudgementResult(
            result=TestResult.FAILED,
            roas_d7=0.25,
            cpi=5.0,
            installs=100,
            spend=200.0,
        )
        disp = engine.decide_disposition(judgement, protocol)
        assert disp.decision == TestDecision.REDUCE
        assert disp.new_budget == 25.0  # 50 * 0.5 = 25

    def test_borderline_extend(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        judgement = JudgementResult(
            result=TestResult.BORDERLINE,
            roas_d7=0.5,
            cpi=5.0,
            installs=100,
            spend=200.0,
        )
        disp = engine.decide_disposition(judgement, protocol, extend_count=0)
        assert disp.decision == TestDecision.EXTEND
        assert disp.new_budget == protocol.test_budget

    def test_borderline_max_extends_reduce(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        judgement = JudgementResult(
            result=TestResult.BORDERLINE,
            roas_d7=0.5,
            cpi=5.0,
            installs=100,
            spend=200.0,
        )
        disp = engine.decide_disposition(judgement, protocol, extend_count=2, max_extends=2)
        assert disp.decision == TestDecision.REDUCE

    def test_insufficient_keep(self):
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)
        judgement = JudgementResult(
            result=TestResult.INSUFFICIENT_DATA,
            roas_d7=0.0,
            cpi=0.0,
            installs=10,
            spend=30.0,
        )
        disp = engine.decide_disposition(judgement, protocol)
        assert disp.decision == TestDecision.KEEP

    def test_video_protocol_scale_capped(self):
        """视频 Winner 放量受 winner_max_budget 限制。"""
        engine = TestProtocolEngine()
        protocol = build_protocol("video", CreativeMaturity.VARIANT)
        judgement = JudgementResult(
            result=TestResult.PASSED,
            roas_d7=1.5,
            cpi=2.0,
            installs=100,
            spend=400.0,
        )
        disp = engine.decide_disposition(judgement, protocol)
        assert disp.new_budget <= protocol.winner_max_budget  # 600

    def test_disposition_decision_to_dict(self):
        d = DispositionDecision(
            decision=TestDecision.SCALE,
            action="scale up",
            new_budget=150.0,
            new_objective=TestObjective.AEO_ROAS,
            should_create_new_campaign=True,
        )
        dd = d.to_dict()
        assert dd["decision"] == "SCALE"
        assert dd["new_objective"] == "AEO_ROAS"


# ═══════════════════════════════════════════════════════════
# Test 5: TestLifecycle 状态机
# ═══════════════════════════════════════════════════════════

class TestLifecycleTransitions:
    """测试 TestLifecycle 状态转换。"""

    def test_create_lifecycle(self):
        lc = TestLifecycle.create("test_001", "MW_IMG_001")
        assert lc.status == TestStatus.CREATED
        assert lc.test_id == "test_001"
        assert lc.transition_count == 1

    def test_normal_flow_to_active(self):
        """完整成功流程：CREATED → RUNNING → JUDGING → PASSED → SCALING → ACTIVE。"""
        lc = TestLifecycle.create("test_001", "MW_IMG_001")
        lc.start()
        assert lc.status == TestStatus.RUNNING
        lc.judge()
        assert lc.status == TestStatus.JUDGING
        lc.mark_passed()
        assert lc.status == TestStatus.PASSED
        lc.start_scaling()
        assert lc.status == TestStatus.SCALING
        lc.mark_active()
        assert lc.status == TestStatus.ACTIVE
        assert lc.is_terminal is True

    def test_fail_flow(self):
        """失败流程：CREATED → RUNNING → JUDGING → FAILED → KILLED。"""
        lc = TestLifecycle.create("test_002", "MW_IMG_002")
        lc.start()
        lc.judge()
        lc.mark_failed()
        assert lc.status == TestStatus.FAILED
        lc.kill()
        assert lc.status == TestStatus.KILLED

    def test_borderline_extend_flow(self):
        """边缘延长流程：CREATED → RUNNING → JUDGING → BORDERLINE → EXTENDED → RUNNING。"""
        lc = TestLifecycle.create("test_003", "MW_IMG_003")
        lc.start()
        lc.judge()
        lc.mark_borderline()
        assert lc.status == TestStatus.BORDERLINE
        lc.extend()
        assert lc.status == TestStatus.EXTENDED
        lc.judge()
        assert lc.status == TestStatus.JUDGING

    def test_early_kill_from_running(self):
        lc = TestLifecycle.create("test_004", "MW_IMG_004")
        lc.start()
        lc.kill()
        assert lc.status == TestStatus.KILLED

    def test_invalid_transition_raises(self):
        lc = TestLifecycle.create("test_005", "MW_IMG_005")
        with pytest.raises(ValueError, match="Invalid transition"):
            lc.mark_passed()  # CREATED → PASSED not allowed

    def test_terminal_cannot_transition(self):
        lc = TestLifecycle.create("test_006", "MW_IMG_006")
        lc.start()
        lc.kill()
        with pytest.raises(ValueError, match="Invalid transition"):
            lc.start()  # KILLED → RUNNING not allowed

    def test_status_history_tracking(self):
        lc = TestLifecycle.create("test_007", "MW_IMG_007")
        lc.start()
        lc.judge()
        lc.mark_passed()
        assert lc.transition_count == 4  # created + 3 transitions
        assert lc.status_history[0]["to"] == "CREATED"
        assert lc.status_history[1]["to"] == "RUNNING"
        assert lc.status_history[2]["to"] == "JUDGING"
        assert lc.status_history[3]["to"] == "PASSED"

    def test_is_active_property(self):
        lc = TestLifecycle.create("test_008", "MW_IMG_008")
        assert lc.is_active is False
        lc.start()
        assert lc.is_active is True
        lc.judge()
        assert lc.is_active is False

    def test_to_dict_from_dict(self):
        lc = TestLifecycle.create("test_009", "MW_IMG_009")
        lc.start()
        d = lc.to_dict()
        lc2 = TestLifecycle.from_dict(d)
        assert lc2.test_id == "test_009"
        assert lc2.status == TestStatus.RUNNING

    def test_failed_borderline_flow(self):
        """边缘失败流程：BORDERLINE → FAILED_BORDERLINE → KILLED。"""
        lc = TestLifecycle.create("test_010", "MW_IMG_010")
        lc.start()
        lc.judge()
        lc.mark_borderline()
        lc.mark_failed_borderline()
        assert lc.status == TestStatus.FAILED_BORDERLINE
        lc.kill()
        assert lc.status == TestStatus.KILLED


# ═══════════════════════════════════════════════════════════
# Test 6: TestLifecycleManager
# ═══════════════════════════════════════════════════════════

class TestLifecycleManagerTests:
    """测试 TestLifecycleManager 批量管理。"""

    def test_create_and_get(self):
        mgr = TestLifecycleManager()
        lc = mgr.create_test("t1", "MW_001")
        assert mgr.get("t1") is lc
        assert mgr.total_tests == 1

    def test_get_by_creative(self):
        mgr = TestLifecycleManager()
        mgr.create_test("t1", "MW_001")
        mgr.create_test("t2", "MW_001")
        mgr.create_test("t3", "MW_002")
        results = mgr.get_by_creative("MW_001")
        assert len(results) == 2

    def test_get_active_tests(self):
        mgr = TestLifecycleManager()
        t1 = mgr.create_test("t1", "MW_001")
        t2 = mgr.create_test("t2", "MW_002")
        t1.start()
        assert len(mgr.get_active_tests()) == 1

    def test_get_terminal_tests(self):
        mgr = TestLifecycleManager()
        t1 = mgr.create_test("t1", "MW_001")
        t1.start()
        t1.kill()
        assert len(mgr.get_terminal_tests()) == 1

    def test_get_by_status(self):
        mgr = TestLifecycleManager()
        t1 = mgr.create_test("t1", "MW_001")
        t2 = mgr.create_test("t2", "MW_002")
        t1.start()
        assert len(mgr.get_by_status(TestStatus.CREATED)) == 1
        assert len(mgr.get_by_status(TestStatus.RUNNING)) == 1

    def test_count_by_status(self):
        mgr = TestLifecycleManager()
        mgr.create_test("t1", "MW_001")
        mgr.create_test("t2", "MW_002")
        mgr.create_test("t3", "MW_003")
        counts = mgr.count_by_status()
        assert counts["CREATED"] == 3

    def test_to_dict(self):
        mgr = TestLifecycleManager()
        mgr.create_test("t1", "MW_001")
        d = mgr.to_dict()
        assert d["total"] == 1
        assert "t1" in d["tests"]


# ═══════════════════════════════════════════════════════════
# Test 7: BudgetManager
# ═══════════════════════════════════════════════════════════

class TestBudgetManager:
    """测试 BudgetManager 预算计算。"""

    def test_scale_up_2x(self):
        mgr = BudgetManager()
        action = mgr.calculate_scale_up("MW_001", current_budget=50, multiplier=2.0)
        assert action.action_type == BudgetActionType.SCALE_UP
        assert action.new_budget == 100.0
        assert action.requires_new_campaign is True
        assert action.cooldown_days == 3

    def test_scale_up_3x_capped_at_2x(self):
        """阶梯限制：单次最多 2x。"""
        mgr = BudgetManager()
        action = mgr.calculate_scale_up("MW_001", current_budget=50, multiplier=3.0)
        assert action.new_budget == 100.0  # 50 * 2 = 100, not 150

    def test_scale_up_max_budget_cap(self):
        mgr = BudgetManager(max_budget=200.0)
        action = mgr.calculate_scale_up("MW_001", current_budget=150, multiplier=2.0)
        assert action.new_budget == 200.0  # capped at max

    def test_scale_up_custom_max(self):
        mgr = BudgetManager()
        action = mgr.calculate_scale_up(
            "MW_001", current_budget=50, multiplier=2.0, max_budget=80.0,
        )
        assert action.new_budget == 80.0

    def test_scale_up_already_at_max(self):
        mgr = BudgetManager(max_budget=100.0)
        action = mgr.calculate_scale_up("MW_001", current_budget=100, multiplier=2.0)
        assert action.is_noop is True

    def test_scale_down_50pct(self):
        mgr = BudgetManager()
        action = mgr.calculate_scale_down("MW_001", current_budget=100, reduce_ratio=0.5)
        assert action.action_type == BudgetActionType.SCALE_DOWN
        assert action.new_budget == 50.0

    def test_scale_down_below_min_pauses(self):
        mgr = BudgetManager(min_budget=10.0)
        action = mgr.calculate_scale_down("MW_001", current_budget=15, reduce_ratio=0.5)
        assert action.action_type == BudgetActionType.PAUSE
        assert action.new_budget == 0.0

    def test_pause_action(self):
        mgr = BudgetManager()
        action = mgr.calculate_pause("MW_001", current_budget=100)
        assert action.action_type == BudgetActionType.PAUSE
        assert action.new_budget == 0.0

    def test_new_campaign_budget(self):
        mgr = BudgetManager()
        action = mgr.calculate_new_campaign_budget("MW_001", test_budget=50, multiplier=2.0)
        assert action.action_type == BudgetActionType.NEW_CAMPAIGN
        assert action.new_budget == 100.0
        assert action.requires_new_campaign is True
        assert action.risk_level == "low"

    def test_new_campaign_high_budget_risk_medium(self):
        mgr = BudgetManager()
        action = mgr.calculate_new_campaign_budget("MW_001", test_budget=300, multiplier=2.0)
        assert action.risk_level == "medium"

    def test_budget_change_pct(self):
        action = BudgetAction(
            action_type=BudgetActionType.SCALE_UP,
            current_budget=50,
            new_budget=100,
        )
        assert action.budget_change_pct == 1.0

    def test_budget_action_to_dict(self):
        action = BudgetAction(
            action_type=BudgetActionType.SCALE_UP,
            creative_asset_id="MW_001",
            current_budget=50,
            new_budget=100,
            reason="test",
            requires_new_campaign=True,
        )
        d = action.to_dict()
        assert d["action_type"] == "SCALE_UP"
        assert d["new_budget"] == 100.0

    def test_batch_calculate(self):
        mgr = BudgetManager()
        actions = [
            {"action_type": "scale_up", "creative_asset_id": "A", "current_budget": 50, "multiplier": 2.0},
            {"action_type": "scale_down", "creative_asset_id": "B", "current_budget": 100, "reduce_ratio": 0.5},
            {"action_type": "pause", "creative_asset_id": "C", "current_budget": 30},
            {"action_type": "new_campaign", "creative_asset_id": "D", "test_budget": 50, "multiplier": 3.0},
        ]
        results = mgr.calculate_batch(actions)
        assert len(results) == 4
        assert results[0].new_budget == 100.0
        assert results[1].new_budget == 50.0
        assert results[2].action_type == BudgetActionType.PAUSE
        assert results[3].new_budget == 150.0  # 50 * 3 = 150

    def test_summarize(self):
        mgr = BudgetManager()
        actions = [
            mgr.calculate_scale_up("A", 50, 2.0),
            mgr.calculate_scale_up("B", 50, 2.0),
            mgr.calculate_scale_down("C", 100, 0.5),
        ]
        summary = mgr.summarize(actions)
        assert summary["total_actions"] == 3
        assert summary["scale_ups"] == 2
        assert summary["scale_downs"] == 1
        assert summary["total_new_budget"] == 250.0  # 100 + 100 + 50

    def test_repr(self):
        mgr = BudgetManager()
        assert "BudgetManager" in repr(mgr)

    def test_scale_up_risk_level(self):
        mgr = BudgetManager()
        low = mgr.calculate_scale_up("A", 50, 2.0)
        assert low.risk_level == "low"
        high = mgr.calculate_scale_up("B", 150, 2.0)
        assert high.risk_level == "medium"


# ═══════════════════════════════════════════════════════════
# Test 8: TestRecord 序列化
# ═══════════════════════════════════════════════════════════

class TestTestRecord:
    """测试 TestRecord 序列化。"""

    def test_to_dict_from_dict(self):
        protocol = build_protocol("image", CreativeMaturity.NEW)
        record = TestRecord(
            record_id="rec_001",
            creative_asset_id="MW_IMG_001",
            protocol=protocol,
            status="RUNNING",
            result=TestResult.INSUFFICIENT_DATA,
            decision=TestDecision.KEEP,
            days_elapsed=3,
            actual_spend=150.0,
            actual_installs=30,
            actual_roas_d7=0.5,
            actual_cpi=5.0,
        )
        d = record.to_dict()
        r2 = TestRecord.from_dict(d)
        assert r2.record_id == "rec_001"
        assert r2.status == "RUNNING"
        assert r2.actual_spend == 150.0

    def test_default_record(self):
        record = TestRecord()
        assert record.result == TestResult.INSUFFICIENT_DATA
        assert record.decision == TestDecision.KEEP


# ═══════════════════════════════════════════════════════════
# Test 9: 完整决策流程集成测试
# ═══════════════════════════════════════════════════════════

class TestIntegration:
    """完整决策流程集成测试。"""

    def test_full_winner_flow(self):
        """完整 Winner 测试流程。"""
        entity = _make_entity(spend=5000, installs=2000, iap_d30=15000, ad_d30=3000)
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)

        # 1. 决定测试目标
        objective = engine.decide_objective(entity=entity, maturity=CreativeMaturity.NEW)
        assert objective.objective == TestObjective.AEO_IAP

        # 2. 判定测试结果
        judgement = engine.judge(entity=entity, protocol=protocol)
        assert judgement.result == TestResult.PASSED

        # 3. 处置决策
        disposition = engine.decide_disposition(judgement, protocol)
        assert disposition.decision == TestDecision.SCALE
        assert disposition.should_create_new_campaign is True
        assert disposition.new_objective == TestObjective.AEO_ROAS

        # 4. 预算计算
        mgr = BudgetManager()
        budget_action = mgr.calculate_new_campaign_budget(
            entity.creative_asset_id,
            test_budget=protocol.test_budget,
            multiplier=protocol.winner_budget_multiplier,
        )
        assert budget_action.new_budget == 100.0  # 50 * 2
        assert budget_action.action_type == BudgetActionType.NEW_CAMPAIGN

        # 5. 生命周期
        lifecycle = TestLifecycle.create("test_full", entity.creative_asset_id)
        lifecycle.start()
        lifecycle.judge()
        lifecycle.mark_passed()
        lifecycle.start_scaling()
        assert lifecycle.status == TestStatus.SCALING

    def test_full_failure_flow(self):
        """完整失败素材流程。"""
        entity = _make_entity(spend=5000, installs=200, iap_d7=200, ad_d7=100)
        # ROAS_D7 = 300/5000 = 0.06
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)

        judgement = engine.judge(entity=entity, protocol=protocol)
        assert judgement.result == TestResult.FAILED

        disposition = engine.decide_disposition(judgement, protocol)
        assert disposition.decision == TestDecision.KILL

        mgr = BudgetManager()
        action = mgr.calculate_pause(entity.creative_asset_id, protocol.test_budget)
        assert action.action_type == BudgetActionType.PAUSE

    def test_full_borderline_extend_flow(self):
        """完整边缘素材延长流程。"""
        entity = _make_entity(spend=5000, installs=2000, iap_d7=2000, ad_d7=500)
        # ROAS_D7 = 2500/5000 = 0.5
        engine = TestProtocolEngine()
        protocol = build_protocol("image", CreativeMaturity.NEW)

        judgement = engine.judge(entity=entity, protocol=protocol)
        assert judgement.result == TestResult.BORDERLINE

        # 第一次延长
        disp1 = engine.decide_disposition(judgement, protocol, extend_count=0)
        assert disp1.decision == TestDecision.EXTEND

        # 第二次延长（最后一次）
        disp2 = engine.decide_disposition(judgement, protocol, extend_count=1)
        assert disp2.decision == TestDecision.EXTEND

        # 第三次延长（用尽）→ REDUCE
        disp3 = engine.decide_disposition(judgement, protocol, extend_count=2, max_extends=2)
        assert disp3.decision == TestDecision.REDUCE