"""P0 ApprovalGate V2 — V2ActionExecutor 集成层。

Spec: docs/p0_approval_gate_v2_spec.md §7 (action_executor 集成), §8 (audit log)

职责：组合 ApprovalPolicy + DryRunVerifier + BudgetWindowTracker + ActionExecutor，
实现 Level 0/1/2 三级执行流程。这是 ApprovalGate V2 与既有 ActionExecutor 之间的
薄集成层，不修改 ActionExecutor 本身（保持 V1 兼容）。

V2 执行流程（Spec §7）：
  1. policy.evaluate(intent) → ApprovalDecision
  2. Level 0 + auto_approved:
     - shadow_mode → 只记 audit，不执行
     - 否则 → BudgetWindowTracker.record + 真实执行
  3. Level 1 + dry_run_required:
     - DryRunVerifier.verify_and_promote → 通过则升级真实执行
     - 失败 → 阻塞，等人工
  4. Level 1 (dry_run disabled) / Level 2:
     - 阻塞，等人工

设计纪律：
- 不修改 scripts/action_executor.py 的 ActionExecutor（V1 兼容）
- audit log 落盘 JSONL（Spec §8）
- 所有失败 fail-closed，不抛异常中断主流程
- 返回 V2ExecutionOutcome 统一结构
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.execution.approval.config import ApprovalConfig
from src.execution.approval.policy import (
    OUTCOME_AUTO,
    OUTCOME_DENY,
    ApprovalDecision,
    ApprovalPolicy,
)
from src.execution.approval.budget_window import BudgetWindowTracker
from src.execution.approval.dry_run_verifier import DryRunVerifier

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

DEFAULT_AUDIT_FILENAME = "approval_decisions.jsonl"


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────


@dataclass
class V2ExecutionOutcome:
    """V2 执行结果（统一封装 policy 决策 + 执行结果）。

    Attributes:
        executed: 是否真实执行了动作（Level 0 + 非 shadow / Level 1 + dry_run 通过）
        blocked_reason: 未执行的原因（None 表示已执行）
        decision: ApprovalPolicy 的决策
        dry_run_result: dry_run 验证结果（仅 Level 1，含 (ok, reason)）
        execution_result: 真实执行返回的 ExecutionResult（未执行时为 None）
        audit_record: 落盘的 audit 记录 dict
    """
    executed: bool = False
    blocked_reason: Optional[str] = None
    decision: Optional[ApprovalDecision] = None
    dry_run_result: Optional[tuple[bool, str]] = None
    execution_result: Any = None
    audit_record: dict = field(default_factory=dict)


# ──────────────────────────────────────────────
# 主类
# ──────────────────────────────────────────────


class V2ActionExecutor:
    """ApprovalGate V2 集成执行器。

    组合 V1 ActionExecutor + V2 审批/验证/记账，实现无人值守 Level 0 自动执行。

    用法：
        v2_executor = V2ActionExecutor(
            executor=action_executor,  # V1 ActionExecutor
            policy=ApprovalPolicy(config=cfg, window_tracker=tracker),
            config=cfg,
            window_tracker=tracker,
            dry_run_verifier=DryRunVerifier(executor=action_executor),
        )
        outcome = v2_executor.execute_with_approval(action, intent)

    V1 兼容：若不传 policy/config，V2ActionExecutor 退化为直接调 V1 executor
    （不应用 Level 0/1/2 分级）。
    """

    def __init__(
        self,
        executor: Any,  # ActionExecutor（V1）
        policy: Optional[ApprovalPolicy] = None,
        config: Optional[ApprovalConfig] = None,
        window_tracker: Optional[BudgetWindowTracker] = None,
        dry_run_verifier: Optional[DryRunVerifier] = None,
    ) -> None:
        self._executor = executor
        self._policy = policy
        self._config = config
        self._window = window_tracker
        self._verifier = dry_run_verifier
        # audit log 路径
        audit_dir = (
            config.audit_log_dir if config else "outputs/approval_audit"
        )
        self._audit_path = os.path.join(audit_dir, DEFAULT_AUDIT_FILENAME)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def execute_with_approval(
        self,
        action: Any,  # ExecutionAction
        intent: Any,  # ExecutionIntent
    ) -> V2ExecutionOutcome:
        """带 V2 审批的执行流程。

        Args:
            action: ExecutionAction（scripts/action_planner.py）
            intent: ExecutionIntent（src/execution/models.py）

        Returns:
            V2ExecutionOutcome
        """
        # V1 兼容路径：无 policy → 直接调 V1 executor
        if self._policy is None or self._config is None:
            result = self._executor.execute(action, dry_run=False)
            return V2ExecutionOutcome(
                executed=getattr(result, "success", False),
                execution_result=result,
                audit_record={"mode": "v1_compat", "executed": True},
            )

        # V2 路径
        decision = self._policy.evaluate(intent)
        cfg = self._config

        # 0) DENY → 直接阻塞
        if decision.outcome == OUTCOME_DENY:
            outcome = V2ExecutionOutcome(
                executed=False,
                blocked_reason=f"DENY: {decision.reason}",
                decision=decision,
            )
            self._audit(action, intent, decision, outcome)
            return outcome

        # 1) Level 0 + auto_approved
        if decision.level == 0 and decision.auto_approved:
            return self._execute_level0(action, intent, decision)

        # 2) Level 1 + dry_run_required
        if decision.level == 1 and decision.dry_run_required:
            return self._execute_level1_with_dry_run(action, intent, decision)

        # 3) Level 1 (dry_run disabled) / Level 2 → 阻塞等人工
        outcome = V2ExecutionOutcome(
            executed=False,
            blocked_reason=(
                f"Level {decision.level} requires manual approval: "
                f"{decision.reason}"
            ),
            decision=decision,
        )
        self._audit(action, intent, decision, outcome)
        return outcome

    # ------------------------------------------------------------------
    # Level 0 执行
    # ------------------------------------------------------------------

    def _execute_level0(
        self,
        action: Any,
        intent: Any,
        decision: ApprovalDecision,
    ) -> V2ExecutionOutcome:
        """Level 0 自动执行（含 shadow 模式跳过）。"""
        cfg = self._config

        # Shadow 模式：只记 audit，不执行
        if cfg.shadow_mode:
            outcome = V2ExecutionOutcome(
                executed=False,
                blocked_reason="Level 0 shadow mode: decision logged, execution skipped",
                decision=decision,
            )
            self._audit(action, intent, decision, outcome)
            return outcome

        # 真实执行
        # 1) 先记账（Spec §7: record 后再执行，防执行失败但已记账的偏差）
        #    实际：执行成功才记账更准确，但 Spec §7 伪代码是先 record 再 execute。
        #    这里采用 Spec §7 顺序：record → execute → audit
        if self._window is not None:
            game_id = getattr(intent, "target_id", "") or "default"
            amount_usd = abs(float(getattr(intent, "budget_amount_usd", 0.0) or 0.0))
            action_type = str(getattr(intent, "action", ""))
            action_id = getattr(action, "action_id", "")
            try:
                self._window.record(game_id, action_type, amount_usd, action_id)
            except Exception as exc:
                logger.warning(
                    "V2ActionExecutor: BudgetWindowTracker.record failed: %s", exc
                )

        # 2) 执行
        try:
            result = self._executor.execute(action, dry_run=False)
        except Exception as exc:
            outcome = V2ExecutionOutcome(
                executed=False,
                blocked_reason=f"Level 0 execution raised: {type(exc).__name__}: {exc}",
                decision=decision,
            )
            self._audit(action, intent, decision, outcome)
            return outcome

        outcome = V2ExecutionOutcome(
            executed=getattr(result, "success", False),
            decision=decision,
            execution_result=result,
            blocked_reason=None if getattr(result, "success", False) else (
                f"Level 0 execution failed: {getattr(result, 'error_message', 'unknown')}"
            ),
        )
        self._audit(action, intent, decision, outcome)
        return outcome

    # ------------------------------------------------------------------
    # Level 1 + dry_run 验证
    # ------------------------------------------------------------------

    def _execute_level1_with_dry_run(
        self,
        action: Any,
        intent: Any,
        decision: ApprovalDecision,
    ) -> V2ExecutionOutcome:
        """Level 1：dry_run 验证通过后升级真实执行。"""
        if self._verifier is None:
            outcome = V2ExecutionOutcome(
                executed=False,
                blocked_reason="Level 1 dry_run required but no DryRunVerifier configured",
                decision=decision,
            )
            self._audit(action, intent, decision, outcome)
            return outcome

        # 1) dry_run 验证
        try:
            ok, reason = self._verifier.verify_and_promote(action)
        except Exception as exc:
            outcome = V2ExecutionOutcome(
                executed=False,
                blocked_reason=f"DryRunVerifier raised: {type(exc).__name__}: {exc}",
                decision=decision,
                dry_run_result=(False, str(exc)),
            )
            self._audit(action, intent, decision, outcome)
            return outcome

        outcome = V2ExecutionOutcome(decision=decision, dry_run_result=(ok, reason))

        # 2) dry_run 失败 → 阻塞
        if not ok:
            outcome.blocked_reason = f"dry_run verification failed: {reason}"
            self._audit(action, intent, decision, outcome)
            return outcome

        # 3) dry_run 通过 → 升级真实执行
        #    记账（Level 1 升级后也计入累计窗口）
        if self._window is not None:
            game_id = getattr(intent, "target_id", "") or "default"
            amount_usd = abs(float(getattr(intent, "budget_amount_usd", 0.0) or 0.0))
            action_type = str(getattr(intent, "action", ""))
            action_id = getattr(action, "action_id", "")
            try:
                self._window.record(game_id, action_type, amount_usd, action_id)
            except Exception as exc:
                logger.warning(
                    "V2ActionExecutor: BudgetWindowTracker.record failed: %s", exc
                )

        # 4) 真实执行
        try:
            result = self._executor.execute(action, dry_run=False)
            outcome.execution_result = result
            outcome.executed = getattr(result, "success", False)
            if not outcome.executed:
                outcome.blocked_reason = (
                    f"Level 1 execution failed after dry_run pass: "
                    f"{getattr(result, 'error_message', 'unknown')}"
                )
        except Exception as exc:
            outcome.blocked_reason = (
                f"Level 1 execution raised: {type(exc).__name__}: {exc}"
            )

        self._audit(action, intent, decision, outcome)
        return outcome

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def _audit(
        self,
        action: Any,
        intent: Any,
        decision: ApprovalDecision,
        outcome: V2ExecutionOutcome,
    ) -> None:
        """落盘 audit log（Spec §8 JSONL 格式）。"""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action_id": getattr(action, "action_id", ""),
            "game_id": getattr(intent, "target_id", "") or "default",
            "action_type": str(getattr(intent, "action", "")),
            "amount_usd": float(getattr(intent, "budget_amount_usd", 0.0) or 0.0),
            "risk": float(getattr(intent, "risk_level", 0.0) or 0.0),
            "confidence": float(getattr(intent, "confidence", 0.0) or 0.0),
            "level": decision.level,
            "outcome": decision.outcome,
            "shadow": self._config.shadow_mode if self._config else False,
            "executed": outcome.executed,
            "dry_run_required": decision.dry_run_required,
            "dry_run_result": (
                {"ok": outcome.dry_run_result[0], "reason": outcome.dry_run_result[1]}
                if outcome.dry_run_result
                else None
            ),
            "reason": decision.reason,
            "blocked_reason": outcome.blocked_reason,
        }
        outcome.audit_record = record
        # 持久化（fail-safe：IO 失败不中断主流程）
        try:
            directory = os.path.dirname(self._audit_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self._audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(
                "V2ActionExecutor: audit log persist failed: %s", exc
            )


__all__ = [
    "V2ActionExecutor",
    "V2ExecutionOutcome",
    "DEFAULT_AUDIT_FILENAME",
]
