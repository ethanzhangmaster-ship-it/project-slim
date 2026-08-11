"""E11.2.5 — Growth Connector Layer 测试。

测试范围：
  - WinnerDetector:    WinnerProfile 构建 + 推荐动作
  - LearningSignalBuilder: WinnerProfile → E10.1 LearningSignal
  - DNATrigger:        触发条件评估 + 优先级
  - GrowthConnector:   完整桥接流程
  - 端到端:            WINNER_DETECTED → LearningSignal → DNATriggerSignal
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_ops.creative_asset_runtime.events.asset_events import (
    AssetEvent,
    AssetEventType,
)
from market_ops.creative_asset_runtime.events.event_bus_adapter import AssetEventBus
from market_ops.creative_asset_runtime.learning.winner_detector import (
    WinnerDetector,
    WinnerProfile,
)
from market_ops.creative_asset_runtime.learning.signal_builder import (
    LearningSignalBuilder,
)
from market_ops.creative_asset_runtime.learning.dna_trigger import (
    DNATrigger,
    DNATriggerSignal,
)
from market_ops.creative_asset_runtime.learning.growth_connector import (
    GrowthConnector,
)
from market_ops.execution_runtime.schemas import (
    LearningSignal,
    FeedbackType,
)


# ════════════════════════════════════════════════════════════════════
# WinnerDetector
# ════════════════════════════════════════════════════════════════════

class TestWinnerDetector:
    """WinnerDetector 测试。"""

    @pytest.fixture
    def detector(self):
        return WinnerDetector()

    def test_on_winner_creates_profile(self, detector):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "spend": 500,
                "revenue": 1000,
                "roas": 2.0,
                "impressions": 5000,
                "installs": 200,
                "eagle_filename": "P4-v2601536.mp4",
                "a_number": "A536",
            },
        )
        profile = detector.on_winner(event)
        assert profile is not None
        assert profile.creative_id == "111"
        assert profile.eagle_v_number == "v2601536"
        assert profile.roas == 2.0
        assert profile.recommended_action == "ANALYZE"
        assert profile.action_confidence == 0.8

    def test_scale_candidate(self, detector):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="222",
            eagle_v_number="v2601537",
            payload={
                "spend": 1000,
                "revenue": 5000,
                "roas": 5.0,
                "impressions": 10000,
            },
        )
        profile = detector.on_winner(event)
        assert profile.recommended_action == "SCALE"
        assert profile.action_confidence == 0.9

    def test_retest_candidate(self, detector):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="333",
            eagle_v_number="v2601538",
            payload={
                "spend": 200,
                "revenue": 220,
                "roas": 1.1,
                "impressions": 2000,
            },
        )
        profile = detector.on_winner(event)
        assert profile.recommended_action == "RETEST"
        assert profile.action_confidence == 0.6

    def test_get_all_winners(self, detector):
        for i, (roas, cid) in enumerate([(2.0, "111"), (3.0, "222"), (1.5, "333")]):
            detector.on_winner(AssetEvent(
                event_type=AssetEventType.ASSET_WINNER_DETECTED,
                creative_id=cid,
                eagle_v_number=f"v{i}",
                payload={"roas": roas, "spend": 500, "impressions": 5000},
            ))

        assert detector.winner_count == 3
        assert len(detector.get_all_winners()) == 3
        assert len(detector.get_scale_candidates()) == 1  # roas 3.0
        assert len(detector.get_analyze_candidates()) == 2  # roas 2.0, 1.5

    def test_on_performance_updated(self, detector):
        # 先创建 winner
        detector.on_winner(AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={"roas": 2.0, "spend": 500, "impressions": 5000},
        ))

        # 更新性能数据
        detector.on_performance_updated(AssetEvent(
            event_type=AssetEventType.PERFORMANCE_UPDATED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={"roas": 5.0, "spend": 1000, "impressions": 15000},
        ))

        profile = detector.get_profile("v2601536")
        assert profile.roas == 5.0
        assert profile.recommended_action == "SCALE"

    def test_get_profile_none(self, detector):
        assert detector.get_profile("nonexistent") is None

    def test_winner_profile_to_dict(self):
        profile = WinnerProfile(
            creative_id="111",
            eagle_v_number="v2601536",
            roas=2.0,
            spend=500,
            recommended_action="ANALYZE",
        )
        d = profile.to_dict()
        assert d["creative_id"] == "111"
        assert d["roas"] == 2.0
        assert d["recommended_action"] == "ANALYZE"


# ════════════════════════════════════════════════════════════════════
# LearningSignalBuilder
# ════════════════════════════════════════════════════════════════════

class TestLearningSignalBuilder:
    """LearningSignalBuilder 测试。"""

    @pytest.fixture
    def builder(self):
        return LearningSignalBuilder()

    @pytest.fixture
    def profile(self):
        return WinnerProfile(
            creative_id="111",
            eagle_v_number="v2601536",
            eagle_filename="P4-v2601536.mp4",
            a_number="A536",
            spend=500,
            revenue=1500,
            roas=3.0,
            revenue_d7=1200,
            revenue_d30=3000,
            impressions=5000,
            installs=200,
            retention_d1=0.45,
            retention_d7=0.22,
            payer_count_d30=30,
            recommended_action="SCALE",
            action_confidence=0.9,
        )

    def test_build_learning_signal(self, builder, profile):
        signal = builder.build(profile)

        assert isinstance(signal, LearningSignal)
        assert signal.feedback_type == FeedbackType.SUCCESS.value
        assert signal.action_type == "SCALE"
        assert signal.confidence == 0.9
        assert signal.metrics["roas"] == 3.0
        assert signal.metrics["eagle_v_number"] == "v2601536"
        assert "SCALE" in signal.recommendation

    def test_build_analyze_signal(self, builder):
        profile = WinnerProfile(
            creative_id="222",
            eagle_v_number="v2601537",
            roas=2.0,
            spend=500,
            recommended_action="ANALYZE",
            action_confidence=0.8,
        )
        signal = builder.build(profile)
        assert signal.feedback_type == FeedbackType.NEUTRAL.value
        assert signal.action_type == "ANALYZE"

    def test_build_from_event(self, builder):
        event = AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "spend": 500,
                "revenue": 1500,
                "roas": 3.0,
                "impressions": 5000,
                "installs": 200,
                "status": "WINNER",
            },
        )
        signal = builder.build_from_event(event)
        assert signal.action_type == "SCALE"
        assert signal.confidence == 0.9
        assert signal.metrics["roas"] == 3.0

    def test_get_signals(self, builder, profile):
        builder.build(profile)
        builder.build(profile)
        assert builder.signal_count == 2
        assert len(builder.get_signals()) == 2

    def test_get_signals_by_type(self, builder):
        scale_profile = WinnerProfile(
            creative_id="111", roas=3.0, recommended_action="SCALE",
            action_confidence=0.9,
        )
        analyze_profile = WinnerProfile(
            creative_id="222", roas=2.0, recommended_action="ANALYZE",
            action_confidence=0.8,
        )

        builder.build(scale_profile)
        builder.build(analyze_profile)

        successes = builder.get_signals_by_type(FeedbackType.SUCCESS)
        neutrals = builder.get_signals_by_type(FeedbackType.NEUTRAL)
        assert len(successes) == 1
        assert len(neutrals) == 1


# ════════════════════════════════════════════════════════════════════
# DNATrigger
# ════════════════════════════════════════════════════════════════════

class TestDNATrigger:
    """DNATrigger 测试。"""

    @pytest.fixture
    def trigger(self):
        return DNATrigger()

    def test_evaluate_high_priority(self, trigger):
        signal = LearningSignal(
            signal_id="sig_001",
            task_id="task_001",
            action_type="SCALE",
            feedback_type=FeedbackType.SUCCESS.value,
            confidence=0.9,
            metrics={
                "creative_id": "111",
                "eagle_v_number": "v2601536",
                "roas": 5.0,
                "impressions": 5000,
            },
        )
        result = trigger.evaluate(signal)
        assert result is not None
        assert result.priority == "HIGH"
        assert "5.0" in result.reason

    def test_evaluate_medium_priority(self, trigger):
        signal = LearningSignal(
            signal_id="sig_002",
            task_id="task_002",
            action_type="ANALYZE",
            feedback_type=FeedbackType.NEUTRAL.value,
            confidence=0.8,
            metrics={
                "creative_id": "222",
                "roas": 2.0,
                "impressions": 3000,
            },
        )
        result = trigger.evaluate(signal)
        assert result is not None
        assert result.priority == "MEDIUM"

    def test_evaluate_skipped_low_confidence(self, trigger):
        signal = LearningSignal(
            signal_id="sig_003",
            task_id="task_003",
            feedback_type=FeedbackType.NEUTRAL.value,
            confidence=0.5,  # < 0.6
            metrics={
                "creative_id": "333",
                "roas": 2.0,
                "impressions": 5000,
            },
        )
        result = trigger.evaluate(signal)
        assert result is None

    def test_evaluate_skipped_low_impressions(self, trigger):
        signal = LearningSignal(
            signal_id="sig_004",
            task_id="task_004",
            feedback_type=FeedbackType.NEUTRAL.value,
            confidence=0.8,
            metrics={
                "creative_id": "444",
                "roas": 2.0,
                "impressions": 500,  # < 1000
            },
        )
        result = trigger.evaluate(signal)
        assert result is None

    def test_evaluate_skipped_low_roas(self, trigger):
        signal = LearningSignal(
            signal_id="sig_005",
            task_id="task_005",
            feedback_type=FeedbackType.NEUTRAL.value,
            confidence=0.8,
            metrics={
                "creative_id": "555",
                "roas": 0.5,  # < 1.0
                "impressions": 5000,
            },
        )
        result = trigger.evaluate(signal)
        assert result is None

    def test_evaluate_skipped_warning(self, trigger):
        signal = LearningSignal(
            signal_id="sig_006",
            task_id="task_006",
            feedback_type=FeedbackType.WARNING.value,  # 失败信号
            confidence=0.9,
            metrics={
                "creative_id": "666",
                "roas": 0.3,
                "impressions": 5000,
            },
        )
        result = trigger.evaluate(signal)
        assert result is None

    def test_evaluate_profile(self, trigger):
        profile = WinnerProfile(
            creative_id="111",
            eagle_v_number="v2601536",
            eagle_filename="P4-v2601536.mp4",
            a_number="A536",
            roas=4.0,
            spend=1000,
            revenue=4000,
            impressions=10000,
        )
        result = trigger.evaluate_profile(profile)
        assert result is not None
        assert result.priority == "HIGH"
        assert result.creative_id == "111"

    def test_evaluate_profile_skipped(self, trigger):
        profile = WinnerProfile(
            creative_id="777",
            roas=2.0,
            impressions=500,  # < 1000
        )
        result = trigger.evaluate_profile(profile)
        assert result is None

    def test_get_high_priority(self, trigger):
        signal1 = LearningSignal(
            signal_id="sig_a", task_id="a",
            feedback_type=FeedbackType.SUCCESS.value,
            confidence=0.9,
            metrics={"creative_id": "1", "roas": 5.0, "impressions": 5000},
        )
        signal2 = LearningSignal(
            signal_id="sig_b", task_id="b",
            feedback_type=FeedbackType.NEUTRAL.value,
            confidence=0.8,
            metrics={"creative_id": "2", "roas": 2.0, "impressions": 3000},
        )

        trigger.evaluate(signal1)
        trigger.evaluate(signal2)

        assert trigger.trigger_count == 2
        high = trigger.get_high_priority()
        assert len(high) == 1

    def test_dna_trigger_signal_to_dict(self):
        ts = DNATriggerSignal(
            creative_id="111",
            eagle_v_number="v2601536",
            priority="HIGH",
            reason="test",
        )
        d = ts.to_dict()
        assert d["creative_id"] == "111"
        assert d["priority"] == "HIGH"


# ════════════════════════════════════════════════════════════════════
# GrowthConnector
# ════════════════════════════════════════════════════════════════════

class TestGrowthConnector:
    """GrowthConnector 完整桥接流程测试。"""

    @pytest.fixture
    def connector(self, tmp_path):
        bus = AssetEventBus()
        return GrowthConnector(
            event_bus=bus,
            signal_output_dir=str(tmp_path / "signals"),
        )

    def test_start_and_stop(self, connector):
        connector.start()
        assert connector._started is True
        connector.stop()
        assert connector._started is False

    def test_on_winner_generates_signals(self, connector, tmp_path):
        connector.start()

        event = AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "spend": 500,
                "revenue": 1500,
                "roas": 3.0,
                "impressions": 5000,
                "installs": 200,
                "eagle_filename": "P4-v2601536.mp4",
                "a_number": "A536",
                "status": "WINNER",
            },
        )
        connector._on_winner_detected(event)

        # 验证 LearningSignal
        assert len(connector.learning_signals) == 1
        signal = connector.learning_signals[0]
        assert signal.action_type == "SCALE"
        assert signal.confidence == 0.9

        # 验证 DNATrigger
        assert len(connector.dna_triggers) == 1
        dna = connector.dna_triggers[0]
        assert dna.priority == "HIGH"

        # 验证信号持久化
        signal_files = list(tmp_path.glob("signals/signal_*.json"))
        assert len(signal_files) == 1

    def test_multiple_winners(self, connector):
        connector.start()

        for i, (roas, cid) in enumerate([
            (3.0, "111"), (2.0, "222"), (5.0, "333"),
        ]):
            connector._on_winner_detected(AssetEvent(
                event_type=AssetEventType.ASSET_WINNER_DETECTED,
                creative_id=cid,
                eagle_v_number=f"v{i}",
                payload={
                    "roas": roas,
                    "spend": 500,
                    "impressions": 5000,
                    "status": "WINNER",
                },
            ))

        assert len(connector.learning_signals) == 3
        assert len(connector.dna_triggers) == 3
        assert len(connector.winner_profiles) == 3

    def test_get_status(self, connector):
        connector.start()
        connector._on_winner_detected(AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "roas": 3.0,
                "spend": 500,
                "impressions": 5000,
                "status": "WINNER",
            },
        ))

        status = connector.get_status()
        assert status["signals_generated"] == 1
        assert status["winners_detected"] == 1
        assert status["dna_triggers"] == 1
        assert status["scale_candidates"] == 1

    def test_get_scale_candidates(self, connector):
        connector.start()
        connector._on_winner_detected(AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "roas": 4.0, "spend": 500, "impressions": 5000, "status": "WINNER",
            },
        ))

        scale = connector.get_scale_candidates()
        assert len(scale) == 1
        assert scale[0].recommended_action == "SCALE"

    def test_get_high_priority_dna(self, connector):
        connector.start()
        connector._on_winner_detected(AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="111",
            eagle_v_number="v2601536",
            payload={
                "roas": 5.0, "spend": 500, "impressions": 5000, "status": "WINNER",
            },
        ))

        high = connector.get_high_priority_dna()
        assert len(high) == 1
        assert high[0].priority == "HIGH"

    def test_full_bridge_flow(self, connector, tmp_path):
        """端到端测试：WINNER_DETECTED → LearningSignal → DNATriggerSignal → 持久化。

        模拟完整桥接流程：
          E11 Runtime 产生 WINNER
          → GrowthConnector 生成 LearningSignal
          → DNATrigger 评估触发条件
          → 信号持久化到磁盘
        """
        connector.start()

        # 模拟 E11 Runtime 产生的 WINNER 事件
        event = AssetEvent(
            event_type=AssetEventType.ASSET_WINNER_DETECTED,
            creative_id="2453146861847495",
            eagle_v_number="v2601536",
            payload={
                "spend": 5000,
                "revenue": 15000,
                "roas": 3.0,
                "revenue_d7": 8000,
                "revenue_d30": 18000,
                "impressions": 20000,
                "installs": 800,
                "retention_d1": 0.48,
                "retention_d7": 0.25,
                "payer_count_d30": 50,
                "eagle_filename": "P4-v2601536-mg-2d-juesezhanshi-en-42s.mp4",
                "a_number": "A536",
                "status": "WINNER",
            },
        )

        # 触发桥接
        connector._on_winner_detected(event)

        # 验证 LearningSignal
        signals = connector.learning_signals
        assert len(signals) == 1
        signal = signals[0]
        assert signal.action_type == "SCALE"
        assert signal.feedback_type == FeedbackType.SUCCESS.value
        assert signal.confidence == 0.9
        assert signal.metrics["roas"] == 3.0
        assert signal.metrics["eagle_v_number"] == "v2601536"
        assert "SCALE" in signal.recommendation

        # 验证 DNATriggerSignal
        triggers = connector.dna_triggers
        assert len(triggers) == 1
        dna = triggers[0]
        assert dna.priority == "HIGH"
        assert dna.creative_id == "2453146861847495"
        assert dna.eagle_v_number == "v2601536"

        # 验证持久化
        signal_files = list(tmp_path.glob("signals/signal_*.json"))
        assert len(signal_files) == 1

        with open(signal_files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "learning_signal" in data
        assert "dna_trigger" in data
        assert data["dna_trigger"] is not None
        assert data["dna_trigger"]["priority"] == "HIGH"

        connector.stop()