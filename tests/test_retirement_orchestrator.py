"""游戏退役编排器测试 — GameRetirementOrchestrator 完整覆盖.

覆盖范围:
  1. 退役决策评估 (ROAS / LTV / retention 低于阈值, 边界情况)
  2. 退役计划创建 (stages 框架填充)
  3. 退役执行 (dry_run 模式, 各阶段状态推进)
  4. 数据归档 (本地文件生成, 内容正确性)
  5. 资源释放编排 (本地 vs 需凭证动作标记)
  6. 下架请求编排 (dry_run 标记 needs_credential)
  7. 状态持久化 (plans.jsonl upsert, get_plan, list_plans)
  8. 取消退役 (成功 / 已完成不可取消)
  9. API 端点测试 (7 个端点)
 10. 统计信息 (by_stage / by_trigger / by_decision / success_rate)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.market_ops.workspace.retirement_orchestrator import (
    DEFAULT_THRESHOLDS,
    GameRetirementOrchestrator,
    RetirementDecision,
    RetirementPlan,
    RetirementStage,
    RetirementTrigger,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_metrics(
    roas_d30: float = 0.9,
    ltv_d30: float = 0.6,
    d1_retention: float = 0.4,
) -> dict:
    """构造测试指标 (默认均高于阈值)."""
    return {
        "roas_d30": roas_d30,
        "ltv_d30": ltv_d30,
        "d1_retention": d1_retention,
    }


def _make_decision(
    game_id: str = "test_game",
    trigger: str = RetirementTrigger.MANUAL_DECISION,
    decision: str = "retire",
) -> RetirementDecision:
    """构造测试用 RetirementDecision."""
    return RetirementDecision(
        game_id=game_id,
        trigger=trigger,
        metrics=_make_metrics(),
        threshold_values=dict(DEFAULT_THRESHOLDS),
        decision=decision,
        confidence=0.85,
        decided_at="2026-08-10T00:00:00+00:00",
        decided_by="auto",
    )


# ═══════════════════════════════════════════════════════════════
# 1. 退役决策评估
# ═══════════════════════════════════════════════════════════════


class TestEvaluateRetirement:
    """evaluate_retirement 退役决策评估测试."""

    def test_roas_below_threshold_triggers_retire(self, tmp_path):
        """ROAS 低于阈值 → retire + ROAS_BELOW_THRESHOLD."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 0.5, "ltv_d30": 0.6, "d1_retention": 0.4},
        )
        assert decision.decision == "retire"
        assert decision.trigger == RetirementTrigger.ROAS_BELOW_THRESHOLD
        assert decision.confidence > 0.5
        assert decision.decided_by == "auto"
        assert decision.game_id == "g1"

    def test_ltv_below_threshold_triggers_retire(self, tmp_path):
        """LTV 低于阈值 → retire + LTV_BELOW_THRESHOLD."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 0.9, "ltv_d30": 0.3, "d1_retention": 0.4},
        )
        assert decision.decision == "retire"
        assert decision.trigger == RetirementTrigger.LTV_BELOW_THRESHOLD

    def test_retention_below_threshold_triggers_retire(self, tmp_path):
        """D1 retention 低于阈值 → retire + RETENTION_BELOW_THRESHOLD."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 0.9, "ltv_d30": 0.6, "d1_retention": 0.2},
        )
        assert decision.decision == "retire"
        assert decision.trigger == RetirementTrigger.RETENTION_BELOW_THRESHOLD

    def test_all_metrics_healthy_returns_keep(self, tmp_path):
        """所有指标健康 → keep."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 1.5, "ltv_d30": 0.9, "d1_retention": 0.5},
        )
        assert decision.decision == "keep"
        assert decision.confidence >= 0.9
        assert decision.trigger == RetirementTrigger.MANUAL_DECISION

    def test_metrics_near_threshold_returns_review(self, tmp_path):
        """指标接近阈值 (10% buffer 内) → review."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        # roas_d30_min=0.8, buffer 10% → 在 0.8~0.88 内属于 review
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 0.85, "ltv_d30": 0.9, "d1_retention": 0.5},
        )
        assert decision.decision == "review"
        assert decision.confidence == 0.4

    def test_custom_thresholds_override_defaults(self, tmp_path):
        """自定义阈值覆盖默认阈值."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        # 默认 roas_d30_min=0.8, 提到 1.0 → 0.9 现在低于阈值
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 0.9, "ltv_d30": 0.9, "d1_retention": 0.5},
            thresholds={"roas_d30_min": 1.0},
        )
        assert decision.decision == "retire"
        assert decision.trigger == RetirementTrigger.ROAS_BELOW_THRESHOLD
        assert decision.threshold_values["roas_d30_min"] == 1.0
        # 未覆盖的仍为默认值
        assert decision.threshold_values["ltv_d30_min"] == 0.5

    def test_missing_metrics_does_not_crash(self, tmp_path):
        """缺失指标不应导致崩溃."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={},
        )
        # 无任何指标 → keep (无可违反的阈值)
        assert decision.decision == "keep"

    def test_decision_to_dict_round_trip(self, tmp_path):
        """decision.to_dict() 序列化字段完整."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = orch.evaluate_retirement(
            game_id="g1",
            metrics={"roas_d30": 0.5, "ltv_d30": 0.6, "d1_retention": 0.4},
        )
        d = decision.to_dict()
        assert d["game_id"] == "g1"
        assert d["decision"] == "retire"
        assert "metrics" in d
        assert "threshold_values" in d
        assert "confidence" in d
        assert "decided_at" in d


# ═══════════════════════════════════════════════════════════════
# 2. 退役计划创建
# ═══════════════════════════════════════════════════════════════


class TestCreatePlan:
    """create_plan 退役计划创建测试."""

    def test_create_plan_generates_plan_id(self, tmp_path):
        """创建计划自动生成 plan_id."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = _make_decision()
        plan = orch.create_plan(decision)
        assert plan.plan_id.startswith("ret_")
        assert len(plan.plan_id) > 4
        assert plan.game_id == "test_game"

    def test_create_plan_initializes_stages(self, tmp_path):
        """计划创建时填充 5 个 stages (DECIDING 已完成, 其余 pending)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = _make_decision()
        plan = orch.create_plan(decision)
        stage_names = [s["stage"] for s in plan.stages]
        assert RetirementStage.DECIDING.value in stage_names
        assert RetirementStage.PENDING.value in stage_names
        assert RetirementStage.ARCHIVING.value in stage_names
        assert RetirementStage.RELEASING.value in stage_names
        assert RetirementStage.TAKING_DOWN.value in stage_names
        # DECIDING 已完成
        deciding = next(s for s in plan.stages if s["stage"] == "deciding")
        assert deciding["status"] == "completed"

    def test_create_plan_persists_to_disk(self, tmp_path):
        """创建计划后状态持久化到 plans.jsonl."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = _make_decision()
        plan = orch.create_plan(decision)
        # 文件存在
        plans_path = tmp_path / "retirement" / "plans.jsonl"
        assert plans_path.exists()
        # 内容包含该 plan
        plans = orch.list_plans()
        assert any(p.plan_id == plan.plan_id for p in plans)

    def test_create_plan_current_stage_pending(self, tmp_path):
        """创建后 current_stage = pending."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = _make_decision()
        plan = orch.create_plan(decision)
        assert plan.current_stage == RetirementStage.PENDING.value
        assert plan.completed_at == ""


# ═══════════════════════════════════════════════════════════════
# 3. 退役执行 (dry_run)
# ═══════════════════════════════════════════════════════════════


class TestExecuteRetirement:
    """execute_retirement 退役执行测试."""

    def test_dry_run_completes_all_stages(self, tmp_path):
        """dry_run 模式下完成所有 stages 并标记 COMPLETED."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = _make_decision()
        plan = orch.create_plan(decision)
        updated = orch.execute_retirement(plan, dry_run=True)

        assert updated.current_stage == RetirementStage.COMPLETED.value
        assert updated.completed_at != ""
        # archive_path 已填充
        assert updated.archive_path != ""
        # resource_release_actions / takedown_actions 都已填充
        assert len(updated.resource_release_actions) > 0
        assert len(updated.takedown_actions) > 0
        # stages 都已完成
        for stage in updated.stages:
            if stage["stage"] == RetirementStage.PENDING.value:
                continue
            assert stage["status"] == "completed", (
                f"stage {stage['stage']} status={stage['status']}"
            )

    def test_dry_run_marks_credential_actions_needs_credential(self, tmp_path):
        """dry_run=True 时需凭证的动作标记为 needs_credential."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        updated = orch.execute_retirement(plan, dry_run=True)

        # pause_all_campaigns 需凭证
        pause_action = next(
            a for a in updated.resource_release_actions
            if a["action"] == "pause_all_campaigns"
        )
        assert pause_action["needs_credential"] is True
        assert pause_action["status"] == "needs_credential"
        assert "credential_hint" in pause_action

        # revoke_credentials 需凭证
        revoke_action = next(
            a for a in updated.resource_release_actions
            if a["action"] == "revoke_credentials"
        )
        assert revoke_action["status"] == "needs_credential"

    def test_dry_run_completes_local_actions(self, tmp_path):
        """dry_run=True 时本地动作完成."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        updated = orch.execute_retirement(plan, dry_run=True)

        archive_creatives = next(
            a for a in updated.resource_release_actions
            if a["action"] == "archive_creatives"
        )
        assert archive_creatives["needs_credential"] is False
        assert archive_creatives["status"] == "completed"

        release_eagle = next(
            a for a in updated.resource_release_actions
            if a["action"] == "release_eagle_assets"
        )
        assert release_eagle["status"] == "completed"

    def test_dry_run_takedown_actions_marked_needs_credential(self, tmp_path):
        """dry_run=True 时下架动作标记 needs_credential."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        updated = orch.execute_retirement(plan, dry_run=True)

        # 2 个平台下架动作
        platforms = {a["platform"] for a in updated.takedown_actions}
        assert "app_store" in platforms
        assert "google_play" in platforms

        for action in updated.takedown_actions:
            assert action["needs_credential"] is True
            assert action["status"] == "needs_credential"
            assert "credential_hint" in action

    def test_non_dry_run_still_marks_pending_credential(self, tmp_path):
        """dry_run=False 时编排层仍标记 pending_credential (不实际调用外部 API)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        updated = orch.execute_retirement(plan, dry_run=False)

        # 需凭证动作标记为 pending_credential (而不是真实调用)
        pause_action = next(
            a for a in updated.resource_release_actions
            if a["action"] == "pause_all_campaigns"
        )
        assert pause_action["status"] == "pending_credential"
        assert pause_action["error"] != ""  # 有错误说明

        # takedown 动作也是 pending_credential
        for action in updated.takedown_actions:
            assert action["status"] == "pending_credential"

    def test_already_completed_plan_returns_unchanged(self, tmp_path):
        """已完成计划再次执行直接返回."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        first = orch.execute_retirement(plan, dry_run=True)
        assert first.current_stage == RetirementStage.COMPLETED.value

        # 第二次执行 — 直接返回, 不重复归档
        second = orch.execute_retirement(first, dry_run=True)
        assert second.current_stage == RetirementStage.COMPLETED.value
        assert second.plan_id == first.plan_id


# ═══════════════════════════════════════════════════════════════
# 4. 数据归档
# ═══════════════════════════════════════════════════════════════


class TestArchiveGameData:
    """archive_game_data 数据归档测试."""

    def test_archive_creates_directory(self, tmp_path):
        """归档创建 {game_id}/ 目录."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        archive_path = orch.archive_game_data("g_archive")
        assert Path(archive_path).exists()
        assert Path(archive_path).is_dir()
        assert "g_archive" in archive_path

    def test_archive_creates_all_files(self, tmp_path):
        """归档目录包含 5 个必备文件."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        archive_path = Path(orch.archive_game_data("g_files"))
        expected_files = {
            "game_config.json",
            "campaigns_history.jsonl",
            "creative_mappings.jsonl",
            "performance.json",
            "audit_log.jsonl",
        }
        actual_files = {f.name for f in archive_path.iterdir() if f.is_file()}
        assert expected_files.issubset(actual_files), (
            f"missing: {expected_files - actual_files}"
        )

    def test_game_config_contains_game_id_and_archive_metadata(self, tmp_path):
        """game_config.json 包含 game_id 和归档时间戳."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        archive_path = Path(orch.archive_game_data("g_cfg"))
        config_path = archive_path / "game_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["game_id"] == "g_cfg"
        assert "archived_at" in config
        assert config["source"] == "local_archive"

    def test_audit_log_contains_retirement_archive_record(self, tmp_path):
        """audit_log.jsonl 包含本次归档动作自身的审计记录."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        archive_path = Path(orch.archive_game_data("g_audit"))
        audit_path = archive_path / "audit_log.jsonl"
        records = [
            json.loads(line)
            for line in audit_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # 至少有一条 retirement_archive 记录
        archive_records = [r for r in records if r.get("action") == "retirement_archive"]
        assert len(archive_records) >= 1
        assert archive_records[0]["game_id"] == "g_audit"

    def test_archive_reads_existing_campaigns_jsonl(self, tmp_path):
        """若 liveops/campaigns.jsonl 存在, 归档时按 game_id 过滤."""
        # 准备 campaigns.jsonl
        liveops_dir = tmp_path / "liveops"
        liveops_dir.mkdir(parents=True)
        campaigns_file = liveops_dir / "campaigns.jsonl"
        campaigns_file.write_text(
            json.dumps({"campaign_id": "c1", "game_id": "g_campaign"}, ensure_ascii=False) + "\n"
            + json.dumps({"campaign_id": "c2", "game_id": "other_game"}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        archive_path = Path(orch.archive_game_data("g_campaign"))
        campaigns_history_path = archive_path / "campaigns_history.jsonl"
        records = [
            json.loads(line)
            for line in campaigns_history_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # 只归档 g_campaign 的记录
        assert len(records) == 1
        assert records[0]["game_id"] == "g_campaign"

    def test_archive_handles_empty_data_dir(self, tmp_path):
        """空 data 目录时归档仍成功 (无副作用)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        archive_path = orch.archive_game_data("g_empty")
        assert Path(archive_path).exists()


# ═══════════════════════════════════════════════════════════════
# 5. 资源释放编排
# ═══════════════════════════════════════════════════════════════


class TestReleaseResources:
    """release_resources 资源释放编排测试."""

    def test_returns_four_actions(self, tmp_path):
        """返回 4 个动作 (2 本地 + 2 需凭证)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.release_resources("g1", dry_run=True)
        assert len(actions) == 4
        action_names = {a["action"] for a in actions}
        assert action_names == {
            "pause_all_campaigns",
            "archive_creatives",
            "revoke_credentials",
            "release_eagle_assets",
        }

    def test_local_actions_complete_in_dry_run(self, tmp_path):
        """dry_run 模式下本地动作完成."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.release_resources("g1", dry_run=True)
        for action in actions:
            if not action["needs_credential"]:
                assert action["status"] == "completed"
                assert action["error"] == ""

    def test_credential_actions_marked_in_dry_run(self, tmp_path):
        """dry_run 模式下需凭证动作标记 needs_credential."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.release_resources("g1", dry_run=True)
        for action in actions:
            if action["needs_credential"]:
                assert action["status"] == "needs_credential"
                assert "credential_hint" in action

    def test_credential_actions_pending_in_non_dry_run(self, tmp_path):
        """非 dry_run 模式下需凭证动作标记 pending_credential (编排层不真实调用)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.release_resources("g1", dry_run=False)
        for action in actions:
            if action["needs_credential"]:
                assert action["status"] == "pending_credential"
                assert action["error"] != ""

    def test_each_action_has_executed_at_timestamp(self, tmp_path):
        """每个动作都包含 executed_at 时间戳."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.release_resources("g1", dry_run=True)
        for action in actions:
            assert "executed_at" in action
            assert action["executed_at"] != ""


# ═══════════════════════════════════════════════════════════════
# 6. 下架请求编排
# ═══════════════════════════════════════════════════════════════


class TestRequestTakedown:
    """request_takedown 下架请求编排测试."""

    def test_returns_two_platforms(self, tmp_path):
        """返回 app_store + google_play 两个平台动作."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.request_takedown("g1", dry_run=True)
        assert len(actions) == 2
        platforms = {a["platform"] for a in actions}
        assert platforms == {"app_store", "google_play"}

    def test_dry_run_marks_needs_credential(self, tmp_path):
        """dry_run=True 时所有动作标记 needs_credential."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.request_takedown("g1", dry_run=True)
        for action in actions:
            assert action["status"] == "needs_credential"
            assert action["needs_credential"] is True
            assert "credential_hint" in action

    def test_non_dry_run_marks_pending_credential(self, tmp_path):
        """dry_run=False 时所有动作标记 pending_credential (编排层不真实调用)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.request_takedown("g1", dry_run=False)
        for action in actions:
            assert action["status"] == "pending_credential"
            assert action["error"] != ""

    def test_app_store_action_has_correct_credential_hint(self, tmp_path):
        """App Store 动作的 credential_hint 为 APP_STORE_CONNECT_API_KEY."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.request_takedown("g1", dry_run=True)
        app_store = next(a for a in actions if a["platform"] == "app_store")
        assert app_store["credential_hint"] == "APP_STORE_CONNECT_API_KEY"
        assert app_store["action"] == "app_store_takedown"

    def test_google_play_action_has_correct_credential_hint(self, tmp_path):
        """Google Play 动作的 credential_hint 为 GOOGLE_PLAY_SERVICE_ACCOUNT_JSON."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.request_takedown("g1", dry_run=True)
        google_play = next(a for a in actions if a["platform"] == "google_play")
        assert google_play["credential_hint"] == "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON"
        assert google_play["action"] == "google_play_unpublish"

    def test_actions_include_game_id(self, tmp_path):
        """每个动作都包含 game_id 字段."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        actions = orch.request_takedown("g_takedown", dry_run=True)
        for action in actions:
            assert action["game_id"] == "g_takedown"


# ═══════════════════════════════════════════════════════════════
# 7. 状态持久化
# ═══════════════════════════════════════════════════════════════


class TestPersistence:
    """状态持久化测试."""

    def test_get_plan_returns_persisted_plan(self, tmp_path):
        """get_plan 返回持久化的计划."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = _make_decision()
        plan = orch.create_plan(decision)

        # 重新创建 orchestrator (模拟进程重启)
        orch2 = GameRetirementOrchestrator(data_dir=str(tmp_path))
        loaded = orch2.get_plan(plan.plan_id)
        assert loaded is not None
        assert loaded.plan_id == plan.plan_id
        assert loaded.game_id == plan.game_id

    def test_get_plan_returns_none_for_unknown(self, tmp_path):
        """未知 plan_id 返回 None."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        assert orch.get_plan("nonexistent") is None

    def test_list_plans_returns_all(self, tmp_path):
        """list_plans 返回所有计划."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        orch.create_plan(_make_decision(game_id="g1"))
        orch.create_plan(_make_decision(game_id="g2"))
        plans = orch.list_plans()
        assert len(plans) == 2

    def test_list_plans_filter_by_status(self, tmp_path):
        """list_plans 按 current_stage 过滤."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan1 = orch.create_plan(_make_decision(game_id="g1"))
        plan2 = orch.create_plan(_make_decision(game_id="g2"))
        # 执行 plan1 → COMPLETED
        orch.execute_retirement(plan1, dry_run=True)
        # plan2 仍 PENDING

        pending_plans = orch.list_plans(status=RetirementStage.PENDING.value)
        assert any(p.plan_id == plan2.plan_id for p in pending_plans)
        assert not any(p.plan_id == plan1.plan_id for p in pending_plans)

        completed_plans = orch.list_plans(status=RetirementStage.COMPLETED.value)
        assert any(p.plan_id == plan1.plan_id for p in completed_plans)

    def test_persist_plan_upserts_existing(self, tmp_path):
        """同 plan_id 重复持久化时 upsert (不重复追加)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        plan_id = plan.plan_id

        # 再次创建一个同 plan_id 的计划 (修改某字段)
        plan.archive_path = "/updated/path"
        orch._persist_plan(plan)

        # 应该只有一条记录
        plans = orch.list_plans()
        matching = [p for p in plans if p.plan_id == plan_id]
        assert len(matching) == 1
        assert matching[0].archive_path == "/updated/path"

    def test_plan_to_dict_round_trip(self, tmp_path):
        """to_dict + from_dict 往返一致."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = _make_decision()
        plan = orch.create_plan(decision)
        plan_dict = plan.to_dict()
        restored = RetirementPlan.from_dict(plan_dict)
        assert restored.plan_id == plan.plan_id
        assert restored.game_id == plan.game_id
        assert restored.decision.game_id == decision.game_id
        assert restored.decision.trigger == decision.trigger
        assert restored.current_stage == plan.current_stage

    def test_execute_retirement_persists_final_state(self, tmp_path):
        """执行后最终状态被持久化."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        plan_id = plan.plan_id
        orch.execute_retirement(plan, dry_run=True)

        # 用新 orchestrator 加载验证
        orch2 = GameRetirementOrchestrator(data_dir=str(tmp_path))
        loaded = orch2.get_plan(plan_id)
        assert loaded is not None
        assert loaded.current_stage == RetirementStage.COMPLETED.value
        assert loaded.archive_path != ""


# ═══════════════════════════════════════════════════════════════
# 8. 取消退役
# ═══════════════════════════════════════════════════════════════


class TestCancelRetirement:
    """cancel_retirement 取消退役测试."""

    def test_cancel_pending_plan_succeeds(self, tmp_path):
        """PENDING 状态的计划可以取消."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        success = orch.cancel_retirement(plan.plan_id)
        assert success is True

        loaded = orch.get_plan(plan.plan_id)
        assert loaded.current_stage == RetirementStage.CANCELLED.value
        assert loaded.completed_at != ""

    def test_cancel_completed_plan_fails(self, tmp_path):
        """COMPLETED 状态的计划不可取消."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        orch.execute_retirement(plan, dry_run=True)

        success = orch.cancel_retirement(plan.plan_id)
        assert success is False

    def test_cancel_nonexistent_returns_false(self, tmp_path):
        """取消不存在的 plan_id 返回 False."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        success = orch.cancel_retirement("nonexistent")
        assert success is False

    def test_cancel_failed_plan_fails(self, tmp_path):
        """FAILED 状态的计划不可取消."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        # 手动标记 FAILED
        plan.current_stage = RetirementStage.FAILED.value
        orch._persist_plan(plan)

        success = orch.cancel_retirement(plan.plan_id)
        assert success is False

    def test_cancel_persists_cancelled_state(self, tmp_path):
        """取消后状态持久化."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        plan = orch.create_plan(_make_decision())
        plan_id = plan.plan_id
        orch.cancel_retirement(plan_id)

        # 新 orchestrator 加载
        orch2 = GameRetirementOrchestrator(data_dir=str(tmp_path))
        loaded = orch2.get_plan(plan_id)
        assert loaded.current_stage == RetirementStage.CANCELLED.value


# ═══════════════════════════════════════════════════════════════
# 9. 统计信息
# ═══════════════════════════════════════════════════════════════


class TestGetStats:
    """get_stats 统计信息测试."""

    def test_empty_stats(self, tmp_path):
        """无计划时返回零值统计."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        stats = orch.get_stats()
        assert stats["total_plans"] == 0
        assert stats["completed"] == 0
        assert stats["cancelled"] == 0
        assert stats["failed"] == 0
        assert stats["in_progress"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["by_stage"] == {}
        assert stats["by_trigger"] == {}

    def test_stats_with_mixed_plans(self, tmp_path):
        """混合状态的计划统计正确."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))

        # 2 个 PENDING (其中一个将执行)
        plan1 = orch.create_plan(_make_decision(game_id="g1"))
        plan2 = orch.create_plan(_make_decision(game_id="g2"))
        # 1 个 COMPLETED
        orch.execute_retirement(plan1, dry_run=True)
        # 1 个 CANCELLED
        plan3 = orch.create_plan(_make_decision(game_id="g3"))
        orch.cancel_retirement(plan3.plan_id)

        stats = orch.get_stats()
        assert stats["total_plans"] == 3
        assert stats["completed"] == 1
        assert stats["cancelled"] == 1
        assert stats["in_progress"] == 1  # plan2 仍 PENDING
        assert stats["by_stage"]["completed"] == 1
        assert stats["by_stage"]["cancelled"] == 1
        assert stats["by_stage"]["pending"] == 1

    def test_stats_by_trigger(self, tmp_path):
        """按触发器分类统计."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        # 手动构造不同 trigger 的 decision
        d1 = _make_decision(game_id="g1", trigger=RetirementTrigger.ROAS_BELOW_THRESHOLD)
        d2 = _make_decision(game_id="g2", trigger=RetirementTrigger.LTV_BELOW_THRESHOLD)
        orch.create_plan(d1)
        orch.create_plan(d2)

        stats = orch.get_stats()
        assert stats["by_trigger"][RetirementTrigger.ROAS_BELOW_THRESHOLD] == 1
        assert stats["by_trigger"][RetirementTrigger.LTV_BELOW_THRESHOLD] == 1

    def test_stats_by_decision(self, tmp_path):
        """按决策分类统计."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        orch.create_plan(_make_decision(game_id="g1", decision="retire"))
        orch.create_plan(_make_decision(game_id="g2", decision="keep"))

        stats = orch.get_stats()
        assert stats["by_decision"]["retire"] == 1
        assert stats["by_decision"]["keep"] == 1

    def test_success_rate_calculation(self, tmp_path):
        """success_rate = completed / (completed + failed)."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))

        # 1 个 COMPLETED
        plan1 = orch.create_plan(_make_decision(game_id="g1"))
        orch.execute_retirement(plan1, dry_run=True)

        # 1 个 FAILED (手动构造)
        plan2 = orch.create_plan(_make_decision(game_id="g2"))
        plan2.current_stage = RetirementStage.FAILED.value
        orch._persist_plan(plan2)

        stats = orch.get_stats()
        # 1 完成 + 1 失败 = 50% 成功率
        assert stats["completed"] == 1
        assert stats["failed"] == 1
        assert stats["success_rate"] == 0.5


# ═══════════════════════════════════════════════════════════════
# 10. API 端点测试
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def retirement_workspace_env(tmp_path: Path, monkeypatch):
    """设置退役编排器测试环境.

    关键: 把 _get_retirement_orchestrator 单例清空, 让其用 tmp_path 重建.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from src.market_ops.workspace import app as app_module
    monkeypatch.setattr(app_module, "_PROJECT_ROOT", tmp_path)

    # 清空单例
    if hasattr(app_module._get_retirement_orchestrator, "_instance"):
        monkeypatch.delattr(
            app_module._get_retirement_orchestrator, "_instance"
        )

    return {"data_dir": data_dir, "tmp_path": tmp_path}


@pytest.fixture
def retirement_client(retirement_workspace_env):
    """FastAPI TestClient."""
    from src.market_ops.workspace.app import app
    return TestClient(app)


class TestRetirementAPI:
    """退役编排 API 端点测试."""

    def test_evaluate_returns_decision(self, retirement_client):
        """POST /api/retirement/evaluate 返回 RetirementDecision."""
        resp = retirement_client.post(
            "/api/retirement/evaluate",
            json={
                "game_id": "api_g1",
                "metrics": {"roas_d30": 0.5, "ltv_d30": 0.6, "d1_retention": 0.4},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "api_g1"
        assert data["decision"] == "retire"
        assert data["trigger"] == RetirementTrigger.ROAS_BELOW_THRESHOLD
        assert "confidence" in data
        assert "decided_at" in data

    def test_evaluate_missing_game_id_returns_400(self, retirement_client):
        """缺少 game_id → 400."""
        resp = retirement_client.post(
            "/api/retirement/evaluate",
            json={"metrics": {"roas_d30": 0.5}},
        )
        assert resp.status_code == 400

    def test_evaluate_missing_metrics_returns_400(self, retirement_client):
        """缺少 metrics → 400."""
        resp = retirement_client.post(
            "/api/retirement/evaluate",
            json={"game_id": "g1"},
        )
        assert resp.status_code == 400

    def test_plan_creates_plan(self, retirement_client):
        """POST /api/retirement/plan 创建退役计划."""
        decision = {
            "game_id": "api_g2",
            "trigger": RetirementTrigger.MANUAL_DECISION,
            "metrics": {"roas_d30": 0.5},
            "threshold_values": {"roas_d30_min": 0.8},
            "decision": "retire",
            "confidence": 0.85,
            "decided_at": "2026-08-10T00:00:00+00:00",
            "decided_by": "auto",
        }
        resp = retirement_client.post(
            "/api/retirement/plan",
            json={"decision": decision},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"].startswith("ret_")
        assert data["game_id"] == "api_g2"
        assert data["current_stage"] == RetirementStage.PENDING.value
        assert "stages" in data
        assert len(data["stages"]) > 0

    def test_plan_missing_decision_returns_400(self, retirement_client):
        """缺少 decision → 400."""
        resp = retirement_client.post(
            "/api/retirement/plan",
            json={},
        )
        assert resp.status_code == 400

    def test_execute_completes_plan(self, retirement_client):
        """POST /api/retirement/execute 完成退役流程."""
        # 先创建计划
        decision = {
            "game_id": "api_g3",
            "trigger": RetirementTrigger.MANUAL_DECISION,
            "metrics": {"roas_d30": 0.5},
            "threshold_values": {"roas_d30_min": 0.8},
            "decision": "retire",
            "confidence": 0.85,
            "decided_at": "2026-08-10T00:00:00+00:00",
            "decided_by": "auto",
        }
        plan_resp = retirement_client.post(
            "/api/retirement/plan", json={"decision": decision}
        )
        plan_id = plan_resp.json()["plan_id"]

        # 执行
        resp = retirement_client.post(
            "/api/retirement/execute",
            json={"plan_id": plan_id, "dry_run": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_stage"] == RetirementStage.COMPLETED.value
        assert data["archive_path"] != ""
        assert len(data["resource_release_actions"]) > 0
        assert len(data["takedown_actions"]) > 0

    def test_execute_missing_plan_id_returns_400(self, retirement_client):
        """缺少 plan_id → 400."""
        resp = retirement_client.post(
            "/api/retirement/execute",
            json={"dry_run": True},
        )
        assert resp.status_code == 400

    def test_execute_unknown_plan_returns_404(self, retirement_client):
        """未知 plan_id → 404."""
        resp = retirement_client.post(
            "/api/retirement/execute",
            json={"plan_id": "nonexistent", "dry_run": True},
        )
        assert resp.status_code == 404

    def test_list_plans_returns_all(self, retirement_client):
        """GET /api/retirement/plans 列出所有计划."""
        # 创建 2 个计划
        for i in range(2):
            retirement_client.post(
                "/api/retirement/plan",
                json={
                    "decision": {
                        "game_id": f"api_list_{i}",
                        "trigger": RetirementTrigger.MANUAL_DECISION,
                        "metrics": {"roas_d30": 0.5},
                        "threshold_values": {},
                        "decision": "retire",
                        "confidence": 0.5,
                        "decided_at": "2026-08-10T00:00:00+00:00",
                        "decided_by": "auto",
                    }
                },
            )
        resp = retirement_client.get("/api/retirement/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        assert len(data["plans"]) >= 2

    def test_list_plans_filter_by_status(self, retirement_client):
        """GET /api/retirement/plans?status=completed 过滤."""
        # 创建并执行 1 个计划
        decision = {
            "game_id": "api_filter",
            "trigger": RetirementTrigger.MANUAL_DECISION,
            "metrics": {"roas_d30": 0.5},
            "threshold_values": {},
            "decision": "retire",
            "confidence": 0.5,
            "decided_at": "2026-08-10T00:00:00+00:00",
            "decided_by": "auto",
        }
        plan_resp = retirement_client.post(
            "/api/retirement/plan", json={"decision": decision}
        )
        plan_id = plan_resp.json()["plan_id"]
        retirement_client.post(
            "/api/retirement/execute",
            json={"plan_id": plan_id, "dry_run": True},
        )

        # 过滤 completed
        resp = retirement_client.get(
            f"/api/retirement/plans?status={RetirementStage.COMPLETED.value}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(
            p["current_stage"] == RetirementStage.COMPLETED.value
            for p in data["plans"]
        )

    def test_get_plan_returns_detail(self, retirement_client):
        """GET /api/retirement/plans/{plan_id} 返回详情."""
        decision = {
            "game_id": "api_detail",
            "trigger": RetirementTrigger.MANUAL_DECISION,
            "metrics": {"roas_d30": 0.5},
            "threshold_values": {},
            "decision": "retire",
            "confidence": 0.5,
            "decided_at": "2026-08-10T00:00:00+00:00",
            "decided_by": "auto",
        }
        plan_resp = retirement_client.post(
            "/api/retirement/plan", json={"decision": decision}
        )
        plan_id = plan_resp.json()["plan_id"]

        resp = retirement_client.get(f"/api/retirement/plans/{plan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == plan_id
        assert data["game_id"] == "api_detail"

    def test_get_plan_not_found_returns_404(self, retirement_client):
        """GET /api/retirement/plans/nonexistent → 404."""
        resp = retirement_client.get("/api/retirement/plans/nonexistent")
        assert resp.status_code == 404

    def test_cancel_plan_succeeds(self, retirement_client):
        """POST /api/retirement/cancel/{plan_id} 取消 PENDING 计划."""
        decision = {
            "game_id": "api_cancel",
            "trigger": RetirementTrigger.MANUAL_DECISION,
            "metrics": {"roas_d30": 0.5},
            "threshold_values": {},
            "decision": "retire",
            "confidence": 0.5,
            "decided_at": "2026-08-10T00:00:00+00:00",
            "decided_by": "auto",
        }
        plan_resp = retirement_client.post(
            "/api/retirement/plan", json={"decision": decision}
        )
        plan_id = plan_resp.json()["plan_id"]

        resp = retirement_client.post(f"/api/retirement/cancel/{plan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_stage"] == RetirementStage.CANCELLED.value

    def test_cancel_completed_plan_returns_400(self, retirement_client):
        """取消已 COMPLETED 的计划 → 400."""
        decision = {
            "game_id": "api_cancel_completed",
            "trigger": RetirementTrigger.MANUAL_DECISION,
            "metrics": {"roas_d30": 0.5},
            "threshold_values": {},
            "decision": "retire",
            "confidence": 0.5,
            "decided_at": "2026-08-10T00:00:00+00:00",
            "decided_by": "auto",
        }
        plan_resp = retirement_client.post(
            "/api/retirement/plan", json={"decision": decision}
        )
        plan_id = plan_resp.json()["plan_id"]
        # 先执行完成
        retirement_client.post(
            "/api/retirement/execute",
            json={"plan_id": plan_id, "dry_run": True},
        )
        # 再尝试取消
        resp = retirement_client.post(f"/api/retirement/cancel/{plan_id}")
        assert resp.status_code == 400

    def test_cancel_unknown_plan_returns_404(self, retirement_client):
        """取消不存在的计划 → 404."""
        resp = retirement_client.post("/api/retirement/cancel/nonexistent")
        assert resp.status_code == 404

    def test_stats_returns_overview(self, retirement_client):
        """GET /api/retirement/stats 返回统计信息."""
        # 创建 1 个计划
        retirement_client.post(
            "/api/retirement/plan",
            json={
                "decision": {
                    "game_id": "api_stats",
                    "trigger": RetirementTrigger.MANUAL_DECISION,
                    "metrics": {"roas_d30": 0.5},
                    "threshold_values": {},
                    "decision": "retire",
                    "confidence": 0.5,
                    "decided_at": "2026-08-10T00:00:00+00:00",
                    "decided_by": "auto",
                }
            },
        )
        resp = retirement_client.get("/api/retirement/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_plans"] >= 1
        assert "by_stage" in data
        assert "by_trigger" in data
        assert "success_rate" in data


# ═══════════════════════════════════════════════════════════════
# 11. 端到端集成测试
# ═══════════════════════════════════════════════════════════════


class TestEndToEnd:
    """端到端集成测试 — 完整 7 步流程."""

    def test_full_retirement_flow_with_roas_violation(self, tmp_path):
        """完整流程: ROAS 低于阈值 → 退役 → 归档 → 释放 → 下架 → 完成."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))

        # Step 1: 评估退役
        decision = orch.evaluate_retirement(
            game_id="e2e_game",
            metrics={"roas_d30": 0.3, "ltv_d30": 0.7, "d1_retention": 0.5},
        )
        assert decision.decision == "retire"
        assert decision.trigger == RetirementTrigger.ROAS_BELOW_THRESHOLD

        # Step 2: 创建计划
        plan = orch.create_plan(decision)
        assert plan.current_stage == RetirementStage.PENDING.value

        # Step 3-7: 执行退役
        updated = orch.execute_retirement(plan, dry_run=True)

        # 验证完成
        assert updated.current_stage == RetirementStage.COMPLETED.value
        assert updated.completed_at != ""
        assert "e2e_game" in updated.archive_path

        # 资源释放动作验证
        assert len(updated.resource_release_actions) == 4
        # 本地动作完成
        for action in updated.resource_release_actions:
            if not action["needs_credential"]:
                assert action["status"] == "completed"
            else:
                assert action["status"] == "needs_credential"

        # 下架动作验证
        assert len(updated.takedown_actions) == 2
        for action in updated.takedown_actions:
            assert action["status"] == "needs_credential"

        # 归档文件存在
        archive_dir = Path(updated.archive_path)
        assert (archive_dir / "game_config.json").exists()
        assert (archive_dir / "audit_log.jsonl").exists()

        # 状态持久化 (新 orchestrator 加载)
        orch2 = GameRetirementOrchestrator(data_dir=str(tmp_path))
        loaded = orch2.get_plan(plan.plan_id)
        assert loaded is not None
        assert loaded.current_stage == RetirementStage.COMPLETED.value

    def test_full_flow_with_multiple_kpi_violations(self, tmp_path):
        """多个 KPI 同时违反 → 选最严重的作为主触发器."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        # 三项都低于阈值, ROAS 差距比例最大 (0.8 - 0.1)/0.8 = 0.875
        decision = orch.evaluate_retirement(
            game_id="multi_violation",
            metrics={"roas_d30": 0.1, "ltv_d30": 0.4, "d1_retention": 0.3},
        )
        assert decision.decision == "retire"
        # 主触发器应该是差距比例最大的 ROAS
        assert decision.trigger == RetirementTrigger.ROAS_BELOW_THRESHOLD

        plan = orch.create_plan(decision)
        updated = orch.execute_retirement(plan, dry_run=True)
        assert updated.current_stage == RetirementStage.COMPLETED.value

    def test_full_flow_with_keep_decision(self, tmp_path):
        """指标健康 → keep → 仍可强制创建计划退役."""
        orch = GameRetirementOrchestrator(data_dir=str(tmp_path))
        decision = orch.evaluate_retirement(
            game_id="healthy_game",
            metrics={"roas_d30": 1.5, "ltv_d30": 0.9, "d1_retention": 0.6},
        )
        assert decision.decision == "keep"
        # 即使决策是 keep, 仍可创建计划 (人工强制退役场景)
        plan = orch.create_plan(decision)
        updated = orch.execute_retirement(plan, dry_run=True)
        assert updated.current_stage == RetirementStage.COMPLETED.value
