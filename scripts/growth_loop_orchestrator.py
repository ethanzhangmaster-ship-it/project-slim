"""Growth Loop V2 — GrowthLoopOrchestrator 编排中枢。

将 Diagnosis → Hypothesis → Strategy → Plan → Execute → Evaluate 串联为
完整的自动化工作流，支持跨重启续跑。

架构:
  ┌──────────────────────────────────────────────────────────┐
  │                  GrowthLoopOrchestrator                    │
  │                                                            │
  │  __init__()  ──→  从 LoopPersistence 恢复状态               │
  │  run_cycle() ──→  Phase A: 评估到期动作                     │
  │                   Phase B: 执行新的 Growth Loop             │
  │                   Phase C: 持久化全部状态                   │
  └──────────────────────────────────────────────────────────┘

V2 集成（Spec docs/p0_approval_gate_v2_spec.md §7, §10.2）：
  - 构造时注入 V2ActionExecutor → Phase B 走 Level 0/1/2 分级执行
  - 未注入 V2ActionExecutor → 完全保留 V1 行为（向后兼容）
  - V2 路径：ExecutionAction → ExecutionIntent → V2ActionExecutor.execute_with_approval
  - V2 阻塞的动作不计入 PendingEvaluation，仅记 audit
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ContextDetail,
    ExperienceRecord,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from scripts.diagnostic_engine import DiagnosticEngine, DiagnosisResult
from scripts.hypothesis_generator import HypothesisGenerator, GrowthHypothesis
from scripts.strategy_selector import StrategySelector, GrowthStrategy
from scripts.action_planner import ActionPlanner, ExecutionAction
from scripts.action_executor import (
    ActionExecutor,
    ExecutionResult,
    PlatformAdapter,
    SafetyGate,
    ActionExecutionStatus,
)
from scripts.outcome_evaluator import OutcomeEvaluator, ActionOutcome
from scripts.loop_state import LoopState
from scripts.pending_evaluation import PendingEvaluation
from scripts.loop_persistence import LoopPersistence, build_cycle_record

# V2 集成（Spec §7）—— 延迟导入避免循环依赖与 V1 强耦合
# 实际类型在 _ensure_v2_ready() 中按需导入

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# V2 辅助：ActionType → ExecutionAction 映射
# ──────────────────────────────────────────────

# scripts.action_planner.ActionType → src.execution.models.ExecutionAction
# RESUME_CAMPAIGN 在 V2 ExecutionAction 枚举中无对应，返回 None 表示走 V1
_ACTION_TYPE_MAP: dict[str, str] = {
    "update_budget": "scale_budget",
    "pause_campaign": "pause_campaign",
}

# action_planner.risk_level（字符串）→ ExecutionIntent.risk_level（float）
_RISK_LEVEL_MAP: dict[str, float] = {
    "low": 0.1,
    "medium": 0.3,
    "high": 0.6,
    "critical": 0.8,
}


# ──────────────────────────────────────────────
# CycleResult — 单轮循环返回值
# ──────────────────────────────────────────────


class CycleResult:
    """单轮循环的执行结果摘要。"""

    def __init__(self) -> None:
        self.cycle_number: int = 0
        self.loop_id: str = ""

        # Phase A: 到期评估
        self.evaluated_count: int = 0
        self.expired_count: int = 0
        self.outcomes: list[ActionOutcome] = []

        # Phase B: 新动作
        self.signal_ids: list[str] = []
        self.diagnoses: list[DiagnosisResult] = []
        self.hypotheses: list[GrowthHypothesis] = []
        self.strategies: list[GrowthStrategy] = []
        self.actions: list[ExecutionAction] = []
        self.execution_results: list[ExecutionResult] = []
        self.pending_created: int = 0
        self.actions_skipped: int = 0

        # V2 统计（Spec §10.2 集成测试观察指标）
        # 仅在注入 V2ActionExecutor 时累加，V1 模式恒为 0
        self.v2_level0_executed: int = 0       # Level 0 自动执行成功
        self.v2_level0_shadow: int = 0          # Level 0 shadow 模式跳过
        self.v2_level1_promoted: int = 0        # Level 1 dry_run 通过后升级
        self.v2_level1_blocked: int = 0         # Level 1 dry_run 失败/未配置
        self.v2_level2_blocked: int = 0         # Level 2 等人工
        self.v2_denied: int = 0                  # DENY（未知动作等）
        self.v2_fallback_v1: int = 0             # V2 路径回退 V1（如 RESUME_CAMPAIGN）
        self.v2_blocked_actions: list[dict[str, Any]] = []  # 阻塞动作详情（用于 audit）

        # Phase C: 持久化
        self.persisted: bool = False
        self.duration_ms: int = 0

    def __repr__(self) -> str:
        base = (
            f"CycleResult(cycle={self.cycle_number}, "
            f"evaluated={self.evaluated_count}, "
            f"expired={self.expired_count}, "
            f"actions={len(self.actions)}, "
            f"skipped={self.actions_skipped}, "
            f"pending={self.pending_created}, "
            f"duration={self.duration_ms}ms)"
        )
        # V2 模式时附加 V2 统计
        v2_total = (
            self.v2_level0_executed + self.v2_level0_shadow
            + self.v2_level1_promoted + self.v2_level1_blocked
            + self.v2_level2_blocked + self.v2_denied + self.v2_fallback_v1
        )
        if v2_total > 0:
            base += (
                f" [V2: L0={self.v2_level0_executed},shadow={self.v2_level0_shadow},"
                f"L1↑={self.v2_level1_promoted},L1✗={self.v2_level1_blocked},"
                f"L2={self.v2_level2_blocked},DENY={self.v2_denied},"
                f"V1退={self.v2_fallback_v1}]"
            )
        return base


# ──────────────────────────────────────────────
# GrowthLoopOrchestrator
# ──────────────────────────────────────────────


class GrowthLoopOrchestrator:
    """Growth Loop 编排中枢。

    将全部模块串联为自动化工作流，支持跨重启续跑。

    Usage:
        # 创建并恢复状态
        orchestrator = GrowthLoopOrchestrator(
            data_dir="data/growth_loop",
            adapter=MetaAdsPlatformAdapter(client),
        )

        # 单次执行 (manual 模式)
        result = orchestrator.run_cycle(
            signals=signals,
            current_metrics=metrics,
            previous_metrics=prev_metrics,
            creative_to_adset_map=...,
            current_budgets=...,
        )

        # 查看状态
        print(orchestrator.state)
        print(f"Pending evaluations: {len(orchestrator.pending_evaluations)}")
    """

    def __init__(
        self,
        data_dir: str = "data/growth_loop",
        adapter: PlatformAdapter | None = None,
        safety_gate: SafetyGate | None = None,
        store: ExperienceStore | None = None,
        observation_window_hours: int = 168,
        dry_run: bool = False,
        reality_scores: dict[str, Any] | None = None,
        game_id_resolver: Any | None = None,
        # V2 集成（Spec §7, §10.2）
        v2_executor: Any | None = None,
    ) -> None:
        """初始化 Orchestrator 并恢复持久化状态。

        Args:
            data_dir: 持久化数据目录
            adapter: 平台适配器 (None → MockPlatformAdapter)
            safety_gate: 安全门控 (None → 默认配置)
            store: 共享 ExperienceStore (None → 新建，从快照恢复)
            observation_window_hours: 观察窗口 (默认 168h = 7 天)
            dry_run: 全局 dry-run 模式 (不调用真实 API)
            reality_scores: RealityGate 可信分字典 {game_id: RealityScore}。
                为 None 时不进行 RealityGate 检查 (向后兼容)。
            game_id_resolver: creative_id → game_id 解析函数。
                为 None 时 RealityGate 检查跳过。
            v2_executor: V2ActionExecutor 实例（Spec §7）。
                为 None 时走纯 V1 路径（向后兼容，不应用 Level 0/1/2 分级）。
                注入后 Phase B 执行路径改为：
                  ExecutionAction → ExecutionIntent → V2ActionExecutor.execute_with_approval
                V2 内部组合 ApprovalPolicy + DryRunVerifier + BudgetWindowTracker。
        """
        self.observation_window_hours = observation_window_hours
        self.dry_run = dry_run

        # ── 持久化管理器 ──
        self.persistence = LoopPersistence(data_dir=data_dir)

        # ── 恢复 LoopState ──
        self.state = self.persistence.load_state()
        logger.info(
            "Orchestrator initialized: loop_id=%s, cycle=%d",
            self.state.loop_id, self.state.cycle_number,
        )

        # ── 恢复 ExperienceStore ──
        if store is not None:
            self.store = store
        else:
            self.store = ExperienceStore()
            self._restore_experience_store()

        # ── 恢复 PendingEvaluations ──
        self.pending_evaluations: list[PendingEvaluation] = (
            self.persistence.load_pending_evaluations()
        )
        logger.info(
            "Restored %d pending evaluations", len(self.pending_evaluations)
        )

        # ── 初始化引擎 (共享同一个 ExperienceStore) ──
        self.diagnostic_engine = DiagnosticEngine()
        self.hypothesis_generator = HypothesisGenerator(store=self.store)
        self.strategy_selector = StrategySelector(store=self.store)
        self.action_planner = ActionPlanner()
        self.action_executor = ActionExecutor(
            adapter=adapter,
            safety_gate=safety_gate,
            reality_scores=reality_scores,
            game_id_resolver=game_id_resolver,
        )
        self.outcome_evaluator = OutcomeEvaluator(store=self.store)

        # ── V2 集成层（Spec §7）──
        # 仅当显式注入 v2_executor 时启用 V2 路径；否则完全保留 V1 行为
        self._v2_executor = v2_executor
        if self._v2_executor is not None:
            logger.info(
                "V2 ApprovalGate enabled: Level 0/1/2 分级执行路径已激活"
            )

    # ──────────────────────────────────────────────
    # V2 集成辅助
    # ──────────────────────────────────────────────

    def _action_to_intent(self, action: ExecutionAction) -> Optional[Any]:
        """将 ExecutionAction（action_planner）转换为 ExecutionIntent（execution.models）。

        V2 路径专用。映射规则：
        - ActionType.UPDATE_BUDGET → ExecutionAction.SCALE_BUDGET
        - ActionType.PAUSE_CAMPAIGN → ExecutionAction.PAUSE_CAMPAIGN
        - ActionType.RESUME_CAMPAIGN → V2 无对应（返回 None，调用方回退 V1）
        - ActionType.NOOP → 调用方已过滤，不应进入此方法

        额外注入 V2 字段 `budget_amount_usd`（来自 action.budget_impact 绝对值），
        policy.evaluate() 通过 getattr 读取。

        Args:
            action: ActionPlanner 产出的 ExecutionAction

        Returns:
            ExecutionIntent 或 None（无法映射时，调用方应回退 V1）
        """
        # 延迟导入避免 V1 强耦合
        from src.execution.models import (
            ExecutionAction as V2ExecutionAction,
            ExecutionDomain,
            ExecutionIntent,
        )

        action_type_str = action.action_type.value if hasattr(
            action.action_type, "value"
        ) else str(action.action_type)

        v2_action_value = _ACTION_TYPE_MAP.get(action_type_str)
        if v2_action_value is None:
            # RESUME_CAMPAIGN 或未知类型 → 无法走 V2
            return None

        try:
            v2_action = V2ExecutionAction(v2_action_value)
        except ValueError:
            return None

        # risk_level 字符串 → float
        risk_str = action.risk_level if isinstance(
            action.risk_level, str
        ) else "medium"
        risk_float = _RISK_LEVEL_MAP.get(risk_str, 0.3)

        # 域推断：默认 UA（V1 action_planner 全部产出 UA 动作）
        # 若 action_type 属于发布类（无），则 RELEASE，此处保守用 UA
        domain = ExecutionDomain.UA

        # target_id：优先用 game_id_resolver（如配置）解析 creative_id
        # 否则用 creative_id 兜底（与 V1 BudgetWindowTracker 的 game_id 一致性由调用方保证）
        target_id = action.creative_id or action.adset_id or "default"

        intent = ExecutionIntent(
            intent_id="",
            decision_id=action.strategy_id or "",
            domain=domain,
            action=v2_action,
            target_id=target_id,
            reason=action.reason or "v2 orchestrator intent",
            confidence=float(action.confidence) if action.confidence else 0.0,
            expected_impact=dict(action.expected_impact) if action.expected_impact else None,
            risk_level=risk_float,
        )
        # V2 金额维度（policy.py 通过 getattr 读取）
        # budget_impact: 正=增, 负=减, 0=无；取绝对值作为金额
        intent.budget_amount_usd = abs(float(action.budget_impact or 0.0))  # type: ignore[attr-defined]
        return intent

    def _execute_via_v2(
        self,
        action: ExecutionAction,
        result: CycleResult,
    ) -> tuple[bool, Optional[ExecutionResult]]:
        """通过 V2ActionExecutor 执行动作。

        V2 路径：
        1. action → intent 转换；失败则回退 V1
        2. v2_executor.execute_with_approval(action, intent) → V2ExecutionOutcome
        3. 按 outcome 分类统计：
           - executed=True → 返回 (True, execution_result)
           - executed=False → 记入 result.v2_blocked_actions，返回 (False, None)

        Args:
            action: ActionPlanner 产出的 ExecutionAction
            result: 当前 CycleResult，用于累加 V2 统计

        Returns:
            (executed, execution_result)
            - executed=True 时 execution_result 为真实执行结果
            - executed=False 时 execution_result 为 None
        """
        # 1) action → intent
        intent = self._action_to_intent(action)
        if intent is None:
            # 无法映射（如 RESUME_CAMPAIGN）→ 回退 V1
            logger.info(
                "V2 fallback to V1: action_id=%s, action_type=%s (no V2 mapping)",
                action.action_id,
                getattr(action.action_type, "value", action.action_type),
            )
            result.v2_fallback_v1 += 1
            v1_result = self.action_executor.execute(
                action, dry_run=self.dry_run
            )
            self.state.total_actions_executed += 1
            return (v1_result.success, v1_result)

        # 2) V2 执行
        try:
            outcome = self._v2_executor.execute_with_approval(action, intent)  # type: ignore[union-attr]
        except Exception as exc:
            # V2 执行异常 → fail-closed，记为阻塞
            logger.error(
                "V2 execute_with_approval raised: action_id=%s, %s: %s",
                action.action_id, type(exc).__name__, exc,
            )
            result.v2_level2_blocked += 1
            result.v2_blocked_actions.append({
                "action_id": action.action_id,
                "reason": f"V2 executor raised: {type(exc).__name__}: {exc}",
                "level": None,
                "outcome": "EXCEPTION",
            })
            return (False, None)

        # 3) 按 decision.level + outcome 分类统计
        decision = outcome.decision
        level = decision.level if decision else None
        outcome_str = decision.outcome if decision else "UNKNOWN"

        if outcome.executed:
            # 真实执行成功
            if level == 0:
                result.v2_level0_executed += 1
            elif level == 1:
                result.v2_level1_promoted += 1
            # level==2 真实执行不应发生（policy 阻塞），但若发生按 executed 处理
            self.state.total_actions_executed += 1
            exec_result = outcome.execution_result
            if exec_result is not None:
                return (True, exec_result)
            # executed=True 但无 execution_result（理论不应发生）→ 视为阻塞
            logger.warning(
                "V2 outcome.executed=True but execution_result=None: action_id=%s",
                action.action_id,
            )
            return (False, None)

        # 未执行 → 按级别归类阻塞
        if level == 0:
            # Level 0 未执行 → shadow 模式
            result.v2_level0_shadow += 1
        elif level == 1:
            result.v2_level1_blocked += 1
        elif level == 2:
            if outcome_str == "DENY":
                result.v2_denied += 1
            else:
                result.v2_level2_blocked += 1
        else:
            # level=None 或未知 → 视为 Level 2 阻塞
            result.v2_level2_blocked += 1

        result.v2_blocked_actions.append({
            "action_id": action.action_id,
            "level": level,
            "outcome": outcome_str,
            "reason": outcome.blocked_reason or "unknown",
        })
        logger.info(
            "V2 blocked: action_id=%s, level=%s, outcome=%s, reason=%s",
            action.action_id, level, outcome_str,
            outcome.blocked_reason,
        )
        return (False, None)

    def update_reality_scores(
        self,
        reality_scores: dict[str, Any],
        game_id_resolver: Any | None = None,
    ) -> None:
        """动态更新 RealityGate 可信分 (每轮 cycle 前调用)。

        Args:
            reality_scores: {game_id: RealityScore} 字典
            game_id_resolver: 可选的新 creative_id → game_id 解析器
        """
        self.action_executor._reality_scores = reality_scores
        if game_id_resolver is not None:
            self.action_executor._game_id_resolver = game_id_resolver
        logger.info(
            "RealityGate scores updated: %d games",
            len(reality_scores),
        )

    # ──────────────────────────────────────────────
    # 启动恢复
    # ──────────────────────────────────────────────

    def _restore_experience_store(self) -> None:
        """从快照恢复 ExperienceStore。"""
        records_data = self.persistence.load_experience_snapshot()
        if not records_data:
            logger.info("No experience snapshot to restore")
            return

        count = 0
        for record_dict in records_data:
            try:
                record = ExperienceRecord.from_dict(record_dict)
                self.store.add(record)
                count += 1
            except Exception as exc:
                logger.error("Failed to restore ExperienceRecord: %s", exc)

        logger.info("Restored %d experience records", count)

    # ──────────────────────────────────────────────
    # 主循环
    # ──────────────────────────────────────────────

    def run_cycle(
        self,
        signals: list[Any] | None = None,
        current_metrics: dict[str, dict[str, float]] | None = None,
        previous_metrics: dict[str, dict[str, float]] | None = None,
        creative_to_adset_map: dict[str, str] | None = None,
        current_budgets: dict[str, float] | None = None,
        post_metrics_provider: Any | None = None,
    ) -> CycleResult:
        """执行一轮完整的 Growth Loop。

        Phase A: 评估到期的 pending evaluations
        Phase B: 对新信号执行 Diagnose → Hypothesize → Select → Plan → Execute
        Phase C: 持久化全部状态

        Args:
            signals: 本轮待处理的反馈信号列表
            current_metrics: creative_id → 指标 dict
            previous_metrics: creative_id → 上一周期指标 dict
            creative_to_adset_map: creative_id → adset_id 映射
            current_budgets: adset_id → 当前日预算
            post_metrics_provider: 可调用对象，传入 PendingEvaluation 返回 post_metrics dict

        Returns:
            CycleResult 包含本轮全部产物
        """
        cycle_start = time.time()
        result = CycleResult()
        result.loop_id = self.state.loop_id

        # 推进轮次
        self.state.advance_cycle()
        result.cycle_number = self.state.cycle_number

        logger.info(
            "═══ Cycle %d START ═══", self.state.cycle_number
        )

        # ── Phase A: 评估到期动作 ──
        self._phase_a_evaluate_pending(result, post_metrics_provider)

        # ── Phase B: 执行新的 Growth Loop ──
        if signals:
            self._phase_b_run_growth_loop(
                signals,
                current_metrics or {},
                previous_metrics or {},
                creative_to_adset_map or {},
                current_budgets or {},
                result,
            )
        else:
            logger.info("Phase B: No new signals, skipping Growth Loop")

        # ── Phase C: 持久化 ──
        result.duration_ms = int((time.time() - cycle_start) * 1000)
        self._phase_c_persist(result)

        logger.info(
            "═══ Cycle %d END ═══ %s",
            self.state.cycle_number, result,
        )

        return result

    # ──────────────────────────────────────────────
    # Phase A: 评估到期动作
    # ──────────────────────────────────────────────

    def _phase_a_evaluate_pending(
        self,
        result: CycleResult,
        post_metrics_provider: Any | None,
    ) -> None:
        """评估到期的 pending evaluations。"""
        if not self.pending_evaluations:
            logger.info("Phase A: No pending evaluations")
            return

        logger.info(
            "Phase A: Checking %d pending evaluations",
            len(self.pending_evaluations),
        )

        still_pending: list[PendingEvaluation] = []
        outcomes: list[ActionOutcome] = []

        for pending in self.pending_evaluations:
            # 检查是否过期
            if pending.is_expired:
                logger.warning(
                    "Pending evaluation expired: action_id=%s, "
                    "elapsed=%.1fh, window=%dh",
                    pending.action_id,
                    pending.elapsed_hours,
                    pending.observation_window_hours,
                )
                pending.status = "expired"
                result.expired_count += 1
                continue

            # 检查是否到期
            if not pending.is_due:
                logger.debug(
                    "Pending not due: action_id=%s, elapsed=%.1fh/%dh",
                    pending.action_id,
                    pending.elapsed_hours,
                    pending.observation_window_hours,
                )
                still_pending.append(pending)
                continue

            # 到期 → 评估
            logger.info(
                "Evaluating pending: action_id=%s, elapsed=%.1fh",
                pending.action_id, pending.elapsed_hours,
            )

            outcome = self._evaluate_single_pending(
                pending, post_metrics_provider
            )
            if outcome is not None:
                outcomes.append(outcome)
                pending.status = "completed"
                result.evaluated_count += 1
                self.state.total_outcomes_evaluated += 1
            else:
                # 评估失败 (如 post_metrics 不可用) → 保留在队列中
                pending.status = "evaluating"
                still_pending.append(pending)

        result.outcomes = outcomes
        self.pending_evaluations = still_pending

        logger.info(
            "Phase A complete: evaluated=%d, expired=%d, remaining=%d",
            result.evaluated_count,
            result.expired_count,
            len(self.pending_evaluations),
        )

    def _evaluate_single_pending(
        self,
        pending: PendingEvaluation,
        post_metrics_provider: Any | None,
    ) -> ActionOutcome | None:
        """评估单个到期的 pending evaluation。

        Args:
            pending: 到期的待评估记录
            post_metrics_provider: 可调用对象，返回 post_metrics

        Returns:
            ActionOutcome 或 None (评估失败时)
        """
        # 获取 post_metrics
        post_metrics: dict[str, float] = {}
        if post_metrics_provider is not None:
            try:
                post_metrics = post_metrics_provider(pending) or {}
            except Exception as exc:
                logger.error(
                    "Failed to get post_metrics for action_id=%s: %s",
                    pending.action_id, exc,
                )
                return None

        if not post_metrics:
            logger.warning(
                "No post_metrics available for action_id=%s, "
                "keeping in queue",
                pending.action_id,
            )
            return None

        # 重建 ExecutionAction (OutcomeEvaluator 需要)
        action = self._reconstruct_action(pending)

        # 评估 (OutcomeEvaluator 会自动写入 ExperienceStore)
        outcome = self.outcome_evaluator.evaluate(
            action=action,
            pre_metrics=pending.pre_metrics,
            post_metrics=post_metrics,
            observation_window_days=pending.observation_window_hours // 24,
        )

        logger.info(
            "Evaluation complete: action_id=%s, outcome=%s, improvement=%.4f",
            pending.action_id,
            outcome.outcome.value,
            outcome.improvement,
        )

        return outcome

    def _reconstruct_action(self, pending: PendingEvaluation) -> ExecutionAction:
        """从 PendingEvaluation 重建 ExecutionAction (用于评估)。

        OutcomeEvaluator 需要 ExecutionAction 对象来读取
        action_type, expected_impact 等字段。
        """
        from scripts.action_planner import ActionType, ActionStatus

        # 解析 action_type 字符串 → 枚举
        try:
            action_type = ActionType(pending.action_type)
        except ValueError:
            action_type = ActionType.NOOP

        return ExecutionAction(
            action_id=pending.action_id,
            strategy_id=pending.strategy_id,
            hypothesis_id=pending.hypothesis_id,
            diagnosis_id=pending.diagnosis_id,
            signal_id=pending.signal_id,
            creative_id=pending.creative_id,
            adset_id=pending.adset_id,
            action_type=action_type,
            parameters=dict(pending.parameters),
            status=ActionStatus.COMPLETED,
            executed_at=pending.executed_at,
        )

    # ──────────────────────────────────────────────
    # Phase B: 执行新的 Growth Loop
    # ──────────────────────────────────────────────

    def _phase_b_run_growth_loop(
        self,
        signals: list[Any],
        current_metrics: dict[str, dict[str, float]],
        previous_metrics: dict[str, dict[str, float]],
        creative_to_adset_map: dict[str, str],
        current_budgets: dict[str, float],
        result: CycleResult,
    ) -> None:
        """对每个信号执行完整的 Growth Loop 链路。"""
        logger.info("Phase B: Processing %d signals", len(signals))

        all_diagnoses: list[DiagnosisResult] = []
        all_hypotheses: list[GrowthHypothesis] = []
        all_strategies: list[GrowthStrategy] = []
        all_actions: list[ExecutionAction] = []
        all_results: list[ExecutionResult] = []

        for signal in signals:
            creative_id = getattr(signal, "creative_id", "")
            signal_id = getattr(signal, "signal_id", "")
            result.signal_ids.append(signal_id)

            # 获取该 creative 的指标
            cur_m = current_metrics.get(creative_id, {})
            prev_m = previous_metrics.get(creative_id, {})

            # 1. 诊断
            diagnosis = self.diagnostic_engine.diagnose(
                signal=signal,
                current_metrics=cur_m,
                previous_metrics=prev_m or None,
            )
            all_diagnoses.append(diagnosis)
            logger.info(
                "  [%s] Diagnosis: root_cause=%s, confidence=%.2f",
                creative_id, diagnosis.root_cause.value,
                diagnosis.confidence,
            )

            # 2. 假设生成
            hypothesis = self.hypothesis_generator.generate(diagnosis)
            all_hypotheses.append(hypothesis)
            logger.info(
                "  [%s] Hypothesis: confidence=%.2f, basis=%s, actionable=%s",
                creative_id, hypothesis.confidence,
                hypothesis.basis, hypothesis.is_actionable,
            )

            # 3. 策略选择
            strategy = self.strategy_selector.select(hypothesis, diagnosis)
            all_strategies.append(strategy)
            logger.info(
                "  [%s] Strategy: type=%s, intensity=%.2f",
                creative_id, strategy.strategy_type.value,
                strategy.intensity,
            )

            # 4. 动作规划
            actions = self.action_planner.plan(
                strategy=strategy,
                creative_to_adset_map=creative_to_adset_map,
                current_budgets=current_budgets,
            )
            all_actions.extend(actions)

        # 5. 批量执行
        # V2 模式（注入 v2_executor）→ 走 Level 0/1/2 分级执行
        # V1 模式 → 原始 execute() 路径（向后兼容）
        v2_enabled = self._v2_executor is not None
        for action in all_actions:
            if action.is_noop or not action.needs_execution:
                result.actions_skipped += 1
                self.state.total_actions_skipped += 1
                logger.info(
                    "  Action skipped: action_id=%s, type=%s",
                    action.action_id, action.action_type.value,
                )
                continue

            if v2_enabled:
                # V2 路径：分级执行
                executed, exec_result = self._execute_via_v2(action, result)
                if not executed or exec_result is None:
                    # V2 阻塞或异常 → 不创建 PendingEvaluation，继续下一个
                    continue
                # V2 真实执行成功 → 走统一的 PendingEvaluation 创建逻辑
                all_results.append(exec_result)
                logger.info(
                    "  Action executed (V2): action_id=%s, success=%s, status=%s",
                    action.action_id, exec_result.success,
                    exec_result.status.value,
                )
            else:
                # V1 路径（原逻辑）
                exec_result = self.action_executor.execute(
                    action, dry_run=self.dry_run
                )
                all_results.append(exec_result)
                self.state.total_actions_executed += 1

                logger.info(
                    "  Action executed: action_id=%s, success=%s, status=%s",
                    action.action_id, exec_result.success,
                    exec_result.status.value,
                )

            # 执行成功 → 创建 PendingEvaluation
            if exec_result.success and not exec_result.dry_run:
                # 获取执行前指标快照
                creative_id = action.creative_id
                pre_metrics = current_metrics.get(creative_id, {})

                pending = PendingEvaluation.from_action(
                    action=action,
                    execution_result=exec_result,
                    pre_metrics=pre_metrics,
                    observation_window_hours=self.observation_window_hours,
                )
                self.pending_evaluations.append(pending)
                result.pending_created += 1
                logger.info(
                    "  PendingEvaluation created: action_id=%s, "
                    "window=%dh",
                    action.action_id, self.observation_window_hours,
                )

        # 存入 result
        result.diagnoses = all_diagnoses
        result.hypotheses = all_hypotheses
        result.strategies = all_strategies
        result.actions = all_actions
        result.execution_results = all_results

        logger.info(
            "Phase B complete: diagnoses=%d, actions=%d, "
            "executed=%d, skipped=%d, pending_created=%d"
            + (" [V2: L0=%d shadow=%d L1↑=%d L1✗=%d L2=%d DENY=%d V1退=%d]"
               % (
                   result.v2_level0_executed, result.v2_level0_shadow,
                   result.v2_level1_promoted, result.v2_level1_blocked,
                   result.v2_level2_blocked, result.v2_denied,
                   result.v2_fallback_v1,
               ) if v2_enabled else ""),
            len(all_diagnoses), len(all_actions),
            len(all_results), result.actions_skipped,
            result.pending_created,
        )

    # ──────────────────────────────────────────────
    # Phase C: 持久化
    # ──────────────────────────────────────────────

    def _phase_c_persist(self, result: CycleResult) -> None:
        """持久化全部状态。"""
        # 更新 LoopState 统计
        stats = self.store.get_stats()
        self.state.experience_count = stats.total_records
        self.state.success_rate = stats.success_rate

        # 构建 CycleRecord
        cycle_rec = build_cycle_record(
            loop_id=self.state.loop_id,
            cycle_number=self.state.cycle_number,
            started_at=result.signal_ids and datetime.now(timezone.utc).isoformat() or "",
            completed_at=datetime.now(timezone.utc).isoformat(),
            duration_ms=result.duration_ms,
            signal_ids=result.signal_ids,
            diagnosis=result.diagnoses[0].to_dict() if result.diagnoses else {},
            hypothesis=result.hypotheses[0].to_dict() if result.hypotheses else {},
            strategy=result.strategies[0].to_dict() if result.strategies else {},
            actions=[a.to_dict() for a in result.actions],
            execution_results=[r.to_dict() for r in result.execution_results],
            outcomes=[o.to_dict() for o in result.outcomes],
            actions_planned=len(result.actions),
            actions_executed=len(result.execution_results),
            actions_skipped=result.actions_skipped,
            pending_evaluations_created=result.pending_created,
            pending_evaluations_completed=result.evaluated_count,
        )

        # 一次性保存全部
        self.persistence.save_all(
            state=self.state,
            pending_list=self.pending_evaluations,
            experience_records=self.store.to_dict_list(),
            cycle_record=cycle_rec,
        )

        result.persisted = True
        logger.info(
            "Phase C complete: state saved (experience=%d, success_rate=%.2f, "
            "pending=%d)",
            self.state.experience_count,
            self.state.success_rate,
            len(self.pending_evaluations),
        )

    # ──────────────────────────────────────────────
    # 便捷方法
    # ──────────────────────────────────────────────

    @property
    def pending_count(self) -> int:
        """当前待评估动作数。"""
        return len(self.pending_evaluations)

    @property
    def due_count(self) -> int:
        """已到期可评估的动作数。"""
        return sum(1 for p in self.pending_evaluations if p.is_due)

    @property
    def expired_count(self) -> int:
        """已过期的动作数。"""
        return sum(1 for p in self.pending_evaluations if p.is_expired)

    def get_status(self) -> dict[str, Any]:
        """获取当前 Orchestrator 状态摘要。"""
        return {
            "loop_id": self.state.loop_id,
            "cycle_number": self.state.cycle_number,
            "mode": self.state.mode,
            "total_cycles": self.state.total_cycles,
            "total_actions_executed": self.state.total_actions_executed,
            "total_actions_skipped": self.state.total_actions_skipped,
            "total_outcomes_evaluated": self.state.total_outcomes_evaluated,
            "experience_count": self.state.experience_count,
            "success_rate": round(self.state.success_rate, 4),
            "pending_evaluations": self.pending_count,
            "due_evaluations": self.due_count,
            "expired_evaluations": self.expired_count,
            "dry_run": self.dry_run,
            # V2 状态（Spec §10.2 集成测试观察指标）
            "v2_approval_gate_enabled": self._v2_executor is not None,
        }
