"""E15.4 Execution Trigger 测试 — Reality → Execution 桥接测试.

测试覆盖:
  - Action 映射 (OPPORTUNITY_TO_TEMPLATE)
  - trigger() 基本流程
  - 置信度过滤
  - 优先级排序
  - ExecutionContext 创建
  - 真实场景模拟 (ROAS drop + fatigue → creative_refresh)
  - 统计查询
  - 边界情况
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.workflow.execution_trigger import (
    ExecutionTrigger,
    TriggerResult,
    OPPORTUNITY_TO_TEMPLATE,
    SEVERITY_TO_PRIORITY,
    map_action_to_template,
)
from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.models import (
    PlanStatus,
)


class TestActionMapping:
    """Action 映射测试."""

    def test_map_scale(self):
        assert map_action_to_template("SCALE") == "scale"
        assert map_action_to_template("scale") == "scale"

    def test_map_pause(self):
        assert map_action_to_template("PAUSE") == "pause_campaign"
        assert map_action_to_template("pause") == "pause_campaign"

    def test_map_stop(self):
        assert map_action_to_template("STOP") == "pause_campaign"
        assert map_action_to_template("stop") == "pause_campaign"

    def test_map_mutate(self):
        assert map_action_to_template("MUTATE") == "replace_creative"
        assert map_action_to_template("mutate") == "replace_creative"

    def test_map_increase_budget(self):
        assert map_action_to_template("INCREASE_BUDGET") == "increase_budget"
        assert map_action_to_template("increase_budget") == "increase_budget"

    def test_map_decrease_budget(self):
        assert map_action_to_template("DECREASE_BUDGET") == "increase_budget"

    def test_map_launch_experiment(self):
        assert map_action_to_template("LAUNCH_EXPERIMENT") == "replace_creative"

    def test_map_duplicate_winner(self):
        assert map_action_to_template("DUPLICATE_WINNER") == "scale"

    def test_map_unknown_action_fallback(self):
        """未知 Action 返回原始值."""
        assert map_action_to_template("UNKNOWN_ACTION") == "UNKNOWN_ACTION"

    def test_all_mappings_have_values(self):
        """所有映射值都非空."""
        for key, value in OPPORTUNITY_TO_TEMPLATE.items():
            assert value != "", f"Mapping for '{key}' is empty"

    def test_severity_mapping(self):
        assert SEVERITY_TO_PRIORITY["critical"] == "critical"
        assert SEVERITY_TO_PRIORITY["CRITICAL"] == "critical"
        assert SEVERITY_TO_PRIORITY["high"] == "high"
        assert SEVERITY_TO_PRIORITY["medium"] == "medium"
        assert SEVERITY_TO_PRIORITY["low"] == "low"


class TestExecutionTriggerBasic:
    """ExecutionTrigger 基本功能测试."""

    def setup_method(self):
        self.trigger = ExecutionTrigger()

    def test_create(self):
        assert self.trigger._total_triggers == 0
        assert len(self.trigger._trigger_history) == 0

    def test_trigger_empty(self):
        results = self.trigger.trigger([])
        assert results == []

    def test_trigger_single_pause(self):
        """PAUSE → pause_campaign template."""
        opp = {
            "action": "PAUSE",
            "creative_id": "crt_001",
            "reason": "Severe fatigue",
            "confidence": 0.92,
            "severity": "critical",
        }
        results = self.trigger.trigger([opp], {"game_id": "P04"})
        assert len(results) == 1
        assert results[0].is_valid
        assert results[0].mapped_action == "pause_campaign"
        assert results[0].plan.workflow_type.value == "campaign_pause"

    def test_trigger_single_mutate(self):
        """MUTATE → replace_creative template."""
        opp = {
            "action": "MUTATE",
            "creative_id": "crt_002",
            "reason": "ROAS decay",
            "confidence": 0.88,
            "severity": "high",
        }
        results = self.trigger.trigger([opp])
        assert len(results) == 1
        assert results[0].is_valid
        assert results[0].mapped_action == "replace_creative"
        assert results[0].plan.workflow_type.value == "creative_refresh"

    def test_trigger_single_scale(self):
        """SCALE → scale template."""
        opp = {
            "action": "SCALE",
            "creative_id": "crt_003",
            "reason": "High ROAS winner",
            "confidence": 0.85,
            "severity": "medium",
            "budget_multiplier": 1.3,
            "target_budget": 650.0,
            "current_budget": 500.0,
        }
        results = self.trigger.trigger([opp])
        assert len(results) == 1
        assert results[0].is_valid
        assert results[0].mapped_action == "scale"


class TestExecutionTriggerFiltering:
    """ExecutionTrigger 过滤与排序测试."""

    def setup_method(self):
        self.trigger = ExecutionTrigger(min_confidence=0.6)

    def test_low_confidence_filtered(self):
        """置信度低于阈值被过滤."""
        opp = {
            "action": "PAUSE",
            "confidence": 0.3,
            "severity": "low",
        }
        results = self.trigger.trigger([opp])
        assert len(results) == 0

    def test_boundary_confidence_accepted(self):
        """置信度等于阈值被接受."""
        opp = {
            "action": "PAUSE",
            "confidence": 0.6,
            "severity": "medium",
        }
        results = self.trigger.trigger([opp])
        assert len(results) == 1

    def test_priority_sorting(self):
        """按优先级排序: critical > high > medium > low."""
        opps = [
            {"action": "SCALE", "confidence": 0.7, "severity": "low"},
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"},
            {"action": "MUTATE", "confidence": 0.9, "severity": "high"},
            {"action": "SCALE", "confidence": 0.75, "severity": "medium"},
        ]
        results = self.trigger.trigger(opps)
        assert len(results) == 4
        # critical first
        assert results[0].priority == "critical"
        # high second
        assert results[1].priority == "high"
        # medium third
        assert results[2].priority == "medium"
        # low last
        assert results[3].priority == "low"

    def test_max_plans_limit(self):
        """超过最大计划数时截断."""
        trigger = ExecutionTrigger(min_confidence=0.5, max_plans_per_trigger=3)
        opps = [
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"}
            for _ in range(5)
        ]
        results = trigger.trigger(opps)
        assert len(results) == 3


class TestExecutionContextCreation:
    """ExecutionContext 创建测试."""

    def setup_method(self):
        self.trigger = ExecutionTrigger()

    def test_create_context_from_plan(self):
        opp = {
            "action": "PAUSE",
            "creative_id": "crt_001",
            "confidence": 0.92,
            "severity": "critical",
        }
        results = self.trigger.trigger([opp])
        plan = results[0].plan

        ctx = self.trigger.create_context(
            plan,
            variables={"game": "P04", "campaign": "fb_android"},
        )
        assert ctx is not None
        assert ctx.workflow_name != ""
        assert len(ctx.task_states) > 0
        assert ctx.get_variable("game") == "P04"
        assert ctx.metadata["plan_id"] == plan.plan_id

    def test_create_contexts_batch(self):
        opps = [
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"},
            {"action": "MUTATE", "confidence": 0.85, "severity": "high"},
        ]
        results = self.trigger.trigger(opps)
        contexts = self.trigger.create_contexts(results, variables={"game": "P04"})
        assert len(contexts) == 2
        for ctx in contexts:
            assert ctx.get_variable("game") == "P04"
            assert "trigger_id" in ctx.metadata

    def test_create_contexts_skips_invalid(self):
        """create_contexts 跳过无效计划."""
        opps = [
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"},
        ]
        results = self.trigger.trigger(opps)
        # 手动使 plan 无效
        results[0].plan.status = PlanStatus.REJECTED
        contexts = self.trigger.create_contexts(results)
        assert len(contexts) == 0


class TestRealWorldScenario:
    """真实场景模拟测试."""

    def setup_method(self):
        self.trigger = ExecutionTrigger()

    def test_roas_drop_fatigue_scenario(self):
        """模拟用户场景: ROAS drop + fatigue → creative_refresh + pause."""
        # Adjust 信号:
        #   D7 ROAS drop -35%
        #   frequency > 5
        #   creative fatigue > 0.75
        opportunities = [
            {
                "action": "MUTATE",
                "creative_id": "crt_fatigue_001",
                "product_id": "P04",
                "reason": "ROAS decay -35%, fatigue score 0.82",
                "confidence": 0.88,
                "severity": "high",
            },
            {
                "action": "PAUSE",
                "creative_id": "crt_fatigue_002",
                "product_id": "P04",
                "reason": "Severe fatigue, ROAS dropped below 0.3",
                "confidence": 0.92,
                "severity": "critical",
            },
        ]

        results = self.trigger.trigger(
            opportunities,
            context={"game_id": "P04", "source": "adjust_signal"},
        )

        # 验证排序: critical (PAUSE) 在前
        assert len(results) == 2
        assert results[0].priority == "critical"
        assert results[0].mapped_action == "pause_campaign"
        assert results[1].priority == "high"
        assert results[1].mapped_action == "replace_creative"

        # 两个计划都有效
        assert results[0].is_valid
        assert results[1].is_valid

        # PAUSE 计划有 4 tasks (verify_anomaly → pause → record → monitor)
        pause_plan = results[0].plan
        assert len(pause_plan.tasks) == 4

        # MUTATE 计划有 5 tasks (generate → validate → upload → test → monitor)
        mutate_plan = results[1].plan
        assert len(mutate_plan.tasks) == 5

    def test_create_contexts_from_scenario(self):
        """从真实场景创建 ExecutionContext 并验证."""
        opportunities = [
            {
                "action": "MUTATE",
                "creative_id": "crt_fatigue_001",
                "confidence": 0.88,
                "severity": "high",
            },
        ]
        results = self.trigger.trigger(opportunities)
        contexts = self.trigger.create_contexts(
            results,
            variables={"game": "P04", "fatigue_score": 0.82},
        )
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.get_variable("fatigue_score") == 0.82
        assert ctx.metadata["confidence"] == 0.88


class TestTriggerStats:
    """统计查询测试."""

    def setup_method(self):
        self.trigger = ExecutionTrigger()

    def test_stats_initial(self):
        stats = self.trigger.stats()
        assert stats["total_triggers"] == 0
        assert stats["total_results"] == 0
        assert stats["valid_plans"] == 0

    def test_stats_after_trigger(self):
        opps = [
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"},
            {"action": "MUTATE", "confidence": 0.85, "severity": "high"},
        ]
        self.trigger.trigger(opps)
        stats = self.trigger.stats()
        assert stats["total_triggers"] == 1
        assert stats["total_results"] == 2
        assert stats["valid_plans"] == 2
        assert "pause_campaign" in stats["by_action"]
        assert "replace_creative" in stats["by_action"]

    def test_get_history(self):
        opps = [
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"},
        ]
        self.trigger.trigger(opps)
        history = self.trigger.get_history()
        assert len(history) == 1
        assert history[0].mapped_action == "pause_campaign"

    def test_get_valid_plans(self):
        opps = [
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"},
            {"action": "MUTATE", "confidence": 0.85, "severity": "high"},
        ]
        self.trigger.trigger(opps)
        plans = self.trigger.get_valid_plans()
        assert len(plans) == 2

    def test_reset(self):
        self.trigger.trigger([
            {"action": "PAUSE", "confidence": 0.8, "severity": "critical"},
        ])
        self.trigger.reset()
        stats = self.trigger.stats()
        assert stats["total_triggers"] == 0
        assert stats["total_results"] == 0


class TestTriggerResult:
    """TriggerResult 数据模型测试."""

    def test_is_valid(self):
        from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.models import (
            ExecutionPlan,
            PlanStatus,
        )
        plan = ExecutionPlan(status=PlanStatus.VALIDATED)
        result = TriggerResult(plan=plan, mapped_action="pause_campaign")
        assert result.is_valid

    def test_is_rejected(self):
        from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.models import (
            ExecutionPlan,
            PlanStatus,
        )
        plan = ExecutionPlan(status=PlanStatus.REJECTED)
        result = TriggerResult(plan=plan, mapped_action="scale")
        assert result.is_rejected
        assert not result.is_valid

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.workflow.planner.models import (
            ExecutionPlan,
            PlanStatus,
        )
        plan = ExecutionPlan(action_type="pause_campaign", status=PlanStatus.VALIDATED)
        result = TriggerResult(
            trigger_id="trig_001",
            opportunity_id="opp_001",
            plan=plan,
            mapped_action="pause_campaign",
            confidence=0.92,
            priority="critical",
        )
        d = result.to_dict()
        assert d["trigger_id"] == "trig_001"
        assert d["mapped_action"] == "pause_campaign"
        assert d["is_valid"] is True
        assert d["plan"] is not None