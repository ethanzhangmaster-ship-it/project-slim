"""LiveOps 活动执行层 — 接入 ApprovalGate 与执行引擎.

将 WinbackCampaign 从"dry-run 方案"升级为"实际下发奖励和推送"的闭环。
复用 V2 审批基础设施的核心组件:
  - Level 0/1/2 三级分级 (ApprovalGate V2 Spec §6)
  - BudgetWindowTracker 日累计窗口 (防小额高频绕过)
  - audit log JSONL 持久化 (Spec §8)
  - dry_run 验证升级 (Level 1)

设计纪律:
  - 不修改 ExecutionAction 枚举 (UA 专用，保持 V1 兼容)
  - LiveOps 活动有自己的动作语义 (reward_grant / push_notification / email / in_app_message)
  - 复用 V2 的分级思想和 BudgetWindowTracker 组件，不强行套用 V2ActionExecutor
  - 所有真实写操作通过 WinbackCampaignAdapter (PlatformAdapter 子类) 执行
  - 默认 dry_run: 执行请求只记录不真实下发
  - fail-closed: 审批未通过时不执行任何写操作

分级规则 (基于 rewards_pool 金额 + 动作风险):
  - push_notification / email / in_app_message → Level 0 (低风险，自动)
  - reward_grant + rewards_pool < $50 → Level 0 (小额奖励，自动)
  - reward_grant + $50 ≤ rewards_pool < $500 → Level 1 (需 dry_run 验证)
  - rewards_pool ≥ $500 → Level 2 (需人工审批)
  - special_offer 类型 → 至少 Level 1
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 常量 — 分级阈值 (Spec §6 对齐)
# ═══════════════════════════════════════════════════════════════

# Level 0 自动执行阈值
LEVEL0_REWARD_MAX_USD = 50.0
# Level 1 dry_run 验证阈值
LEVEL1_REWARD_MAX_USD = 500.0
# 日累计窗口阈值 (防小额高频)
DAILY_CUMULATIVE_USD = 200.0

# 低风险动作 (总是 Level 0)
LOW_RISK_ACTIONS = frozenset({"push_notification", "email", "in_app_message"})
# 奖励动作 (金额分级)
REWARD_ACTION = "reward_grant"

# 审批级别
LEVEL_0 = 0  # 自动执行
LEVEL_1 = 1  # dry_run 验证后执行
LEVEL_2 = 2  # 人工审批后执行

# 执行状态
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_EXECUTING = "executing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"
STATUS_DRY_RUN = "dry_run"


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass
class CampaignExecutionAction:
    """单个活动动作的执行单元 — 从 CampaignAction 转换而来."""

    action_id: str
    campaign_id: str
    game_id: str
    action_type: str            # reward_grant / push_notification / email / in_app_message
    target_count: int
    content: str
    trigger_delay_hours: int
    rewards_amount: float       # 该动作的奖励金额 (reward_grant 才有)
    risk_level: str             # low / medium / high
    approval_level: int         # 0 / 1 / 2
    status: str = STATUS_PENDING
    error_message: str = ""
    executed_at: str = ""
    platform_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CampaignExecutionResult:
    """活动执行结果 — 包含审批决策和每个动作的执行状态."""

    execution_id: str
    campaign_id: str
    game_id: str
    campaign_type: str
    target_segment: str
    target_count: int
    rewards_pool: float
    dry_run: bool
    approval_level: int         # 整体审批级别 (取最高)
    status: str                 # pending / blocked / dry_run / completed / failed
    blocked_reason: str = ""
    actions: list[CampaignExecutionAction] = field(default_factory=list)
    approved_by: str = ""
    approved_at: str = ""
    created_at: str = ""
    completed_at: str = ""
    audit_record: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.execution_id:
            self.execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "campaign_id": self.campaign_id,
            "game_id": self.game_id,
            "campaign_type": self.campaign_type,
            "target_segment": self.target_segment,
            "target_count": self.target_count,
            "rewards_pool": round(self.rewards_pool, 2),
            "dry_run": self.dry_run,
            "approval_level": self.approval_level,
            "status": self.status,
            "blocked_reason": self.blocked_reason,
            "actions": [a.to_dict() for a in self.actions],
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ═══════════════════════════════════════════════════════════════
# WinbackCampaignAdapter — PlatformAdapter 子类
# ═══════════════════════════════════════════════════════════════


class WinbackCampaignAdapter:
    """回流活动执行适配器 — 模拟下发奖励、推送、邮件、应用内消息.

    实现类似 PlatformAdapter 的 execute / verify / rollback 接口，
    但针对 LiveOps 活动语义定制。

    执行模式:
      - dry_run=True: 只记录执行日志，不真实下发 (默认)
      - dry_run=False: 记录到 execution log JSONL (模拟真实下发)

    真实集成时，可在此处对接:
      - push_notification → FCM / APNs 推送服务
      - email → SES / SendGrid
      - reward_grant → 游戏服务器奖励发放 API
      - in_app_message → 应用内消息系统
    """

    def __init__(
        self,
        data_dir: str = "data",
        dry_run: bool = True,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.dry_run = dry_run
        self._execution_log_path = self.data_dir / "liveops" / "execution_log.jsonl"

    def execute(self, action: CampaignExecutionAction) -> dict[str, Any]:
        """执行单个活动动作 — 返回平台响应."""
        self._execution_log_path.parent.mkdir(parents=True, exist_ok=True)

        # 模拟平台响应
        response = {
            "action_id": action.action_id,
            "action_type": action.action_type,
            "target_count": action.target_count,
            "delivered_count": action.target_count if not self.dry_run else 0,
            "dry_run": self.dry_run,
            "status": "simulated" if self.dry_run else "delivered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": self._get_provider(action.action_type),
        }

        if not self.dry_run:
            # 真实模式: 记录到 execution log (模拟下发)
            response["delivered_count"] = action.target_count
            response["status"] = "delivered"
            self._persist_execution(action, response)

        return response

    def verify(self, action: CampaignExecutionAction, response: dict[str, Any]) -> bool:
        """验证执行是否成功 — dry_run 模式检查 status, live 模式检查 delivered_count."""
        if self.dry_run:
            # dry_run 模式: simulated 状态即视为成功
            return response.get("status") == "simulated"
        # live 模式: delivered_count == target_count
        delivered = response.get("delivered_count", 0)
        target = action.target_count
        return delivered == target

    def rollback(self, action: CampaignExecutionAction, response: dict[str, Any]) -> dict[str, Any]:
        """回滚动作 — 奖励发放不可逆，记录补偿日志."""
        rollback_response = {
            "action_id": action.action_id,
            "original_status": response.get("status", ""),
            "rollback_status": "compensation_logged",
            "rollback_timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "reward_grant 不可逆，已记录补偿日志",
        }
        # 记录回滚日志
        try:
            rollback_log = self.data_dir / "liveops" / "rollback_log.jsonl"
            rollback_log.parent.mkdir(parents=True, exist_ok=True)
            with rollback_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(
                    {"action": action.to_dict(), "rollback": rollback_response},
                    ensure_ascii=False,
                ) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist rollback log: %s", exc)
        return rollback_response

    def _get_provider(self, action_type: str) -> str:
        """获取动作对应的服务提供方 (模拟)."""
        providers = {
            "push_notification": "FCM/APNs",
            "email": "SES",
            "reward_grant": "GameServer-RewardAPI",
            "in_app_message": "InAppMessaging",
        }
        return providers.get(action_type, "unknown")

    def _persist_execution(
        self, action: CampaignExecutionAction, response: dict[str, Any]
    ) -> None:
        """持久化执行记录到 JSONL."""
        try:
            with self._execution_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(
                    {"action": action.to_dict(), "response": response},
                    ensure_ascii=False,
                ) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist execution log: %s", exc)


# ═══════════════════════════════════════════════════════════════
# BudgetWindowTracker — 复用 V2 组件
# ═══════════════════════════════════════════════════════════════


class LiveOpsBudgetWindowTracker:
    """LiveOps 日累计窗口追踪 — 复用 V2 BudgetWindowTracker 思想.

    按 (game_id, action_type, day) 聚合奖励金额，
    防小额高频奖励发放绕过单次阈值。
    """

    def __init__(self, audit_log_dir: str = "data/liveops") -> None:
        self.audit_log_dir = Path(audit_log_dir)
        self._window_path = self.audit_log_dir / "budget_window.jsonl"

    def get_cumulative(
        self, game_id: str, action_type: str, day: Optional[date] = None
    ) -> float:
        """获取当日累计奖励金额."""
        if day is None:
            day = date.today()
        day_str = day.isoformat()
        total = 0.0
        if not self._window_path.exists():
            return 0.0
        try:
            for line in self._window_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    record.get("game_id") == game_id
                    and record.get("action_type") == action_type
                    and record.get("day") == day_str
                ):
                    total += float(record.get("amount_usd", 0.0))
        except OSError:
            return 0.0
        return total

    def record(
        self,
        game_id: str,
        action_type: str,
        amount_usd: float,
        action_id: str,
        day: Optional[date] = None,
    ) -> None:
        """记录一笔奖励发放到窗口."""
        if day is None:
            day = date.today()
        try:
            self._window_path.parent.mkdir(parents=True, exist_ok=True)
            with self._window_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "game_id": game_id,
                    "action_type": action_type,
                    "amount_usd": round(amount_usd, 2),
                    "action_id": action_id,
                    "day": day.isoformat(),
                }, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("BudgetWindowTracker.record failed: %s", exc)

    def reset(self) -> None:
        """重置窗口 (仅测试用)."""
        try:
            self._window_path.unlink(missing_ok=True)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════
# LiveOpsApprovalGate — 审批门控
# ═══════════════════════════════════════════════════════════════


@dataclass
class ApprovalDecision:
    """审批决策结果."""

    outcome: str             # auto / dry_run / manual / deny
    level: int               # 0 / 1 / 2
    reason: str
    auto_approved: bool = False
    dry_run_required: bool = False
    blocked_reason: str = ""


class LiveOpsApprovalGate:
    """LiveOps 审批门控 — 基于 rewards_pool 金额和动作类型分级.

    复用 V2 ApprovalGate 的核心思想 (Level 0/1/2)，
    但针对 LiveOps 活动语义定制分级规则。

    分级规则:
      Level 0 (自动执行):
        - push_notification / email / in_app_message (低风险)
        - reward_grant + rewards_pool < $50 + 日累计 < $200
      Level 1 (dry_run 验证):
        - reward_grant + $50 ≤ rewards_pool < $500
        - special_offer 类型 (至少 Level 1)
      Level 2 (人工审批):
        - rewards_pool ≥ $500
        - 日累计 ≥ $200 (防小额高频)
    """

    def __init__(
        self,
        window_tracker: Optional[LiveOpsBudgetWindowTracker] = None,
        level0_reward_max: float = LEVEL0_REWARD_MAX_USD,
        level1_reward_max: float = LEVEL1_REWARD_MAX_USD,
        daily_cumulative_max: float = DAILY_CUMULATIVE_USD,
    ) -> None:
        self.window_tracker = window_tracker or LiveOpsBudgetWindowTracker()
        self.level0_max = level0_reward_max
        self.level1_max = level1_reward_max
        self.daily_max = daily_cumulative_max

    def evaluate(
        self,
        campaign_type: str,
        action_type: str,
        rewards_amount: float,
        game_id: str,
    ) -> ApprovalDecision:
        """评估单个动作的审批级别."""
        # 日累计检查 (防小额高频)
        cumulative = self.window_tracker.get_cumulative(game_id, action_type)
        if cumulative + rewards_amount > self.daily_max:
            return ApprovalDecision(
                outcome="manual",
                level=LEVEL_2,
                reason=(
                    f"日累计 ${cumulative:.2f} + 本次 ${rewards_amount:.2f} "
                    f"超过阈值 ${self.daily_max:.2f}"
                ),
                blocked_reason="日累计窗口超限，需人工审批",
            )

        # 低风险动作 → Level 0
        if action_type in LOW_RISK_ACTIONS:
            return ApprovalDecision(
                outcome="auto",
                level=LEVEL_0,
                reason=f"低风险动作 {action_type} 自动执行",
                auto_approved=True,
            )

        # special_offer 类型 → 至少 Level 1
        if campaign_type == "special_offer" and rewards_amount > 0:
            if rewards_amount >= self.level1_max:
                return ApprovalDecision(
                    outcome="manual",
                    level=LEVEL_2,
                    reason=f"special_offer 金额 ${rewards_amount:.2f} ≥ ${self.level1_max:.2f}",
                    blocked_reason="大额 special_offer 需人工审批",
                )
            return ApprovalDecision(
                outcome="dry_run",
                level=LEVEL_1,
                reason=f"special_offer 需 dry_run 验证 (金额 ${rewards_amount:.2f})",
                dry_run_required=True,
            )

        # reward_grant 按金额分级
        if action_type == REWARD_ACTION:
            if rewards_amount >= self.level1_max:
                return ApprovalDecision(
                    outcome="manual",
                    level=LEVEL_2,
                    reason=f"奖励金额 ${rewards_amount:.2f} ≥ ${self.level1_max:.2f}",
                    blocked_reason="大额奖励需人工审批",
                )
            if rewards_amount >= self.level0_max:
                return ApprovalDecision(
                    outcome="dry_run",
                    level=LEVEL_1,
                    reason=f"奖励金额 ${rewards_amount:.2f} 需 dry_run 验证",
                    dry_run_required=True,
                )
            # 小额奖励 → Level 0
            return ApprovalDecision(
                outcome="auto",
                level=LEVEL_0,
                reason=f"小额奖励 ${rewards_amount:.2f} < ${self.level0_max:.2f} 自动执行",
                auto_approved=True,
            )

        # 默认 → Level 1
        return ApprovalDecision(
            outcome="dry_run",
            level=LEVEL_1,
            reason=f"未知动作类型 {action_type}，需 dry_run 验证",
            dry_run_required=True,
        )


# ═══════════════════════════════════════════════════════════════
# WinbackCampaignExecutor — 主执行器
# ═══════════════════════════════════════════════════════════════


class WinbackCampaignExecutor:
    """回流活动执行器 — 组合 ApprovalGate + Adapter + Audit Log.

    执行流程:
      1. 将 WinbackCampaign 拆分为单个 CampaignExecutionAction
      2. 对每个动作调用 ApprovalGate.evaluate → ApprovalDecision
      3. Level 0 + auto_approved → 直接执行 (或 shadow 模式跳过)
      4. Level 1 + dry_run_required → dry_run 验证后执行
      5. Level 2 → 阻塞，等人工审批
      6. 所有决策和执行结果落盘 audit log

    用法:
        executor = WinbackCampaignExecutor(data_dir="data", dry_run=True)
        result = executor.execute_campaign(campaign)
        if result.status == "blocked":
            # 等待人工审批
            executor.approve(result.execution_id, approver="admin")
    """

    def __init__(
        self,
        data_dir: str = "data",
        dry_run: bool = True,
        adapter: Optional[WinbackCampaignAdapter] = None,
        approval_gate: Optional[LiveOpsApprovalGate] = None,
        shadow_mode: bool = False,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.dry_run = dry_run
        self.adapter = adapter or WinbackCampaignAdapter(data_dir=data_dir, dry_run=dry_run)
        # 默认 gate 必须复用 executor 的 data_dir，否则 BudgetWindowTracker 会落到
        # 全局 data/liveops，破坏测试隔离（日累计被其他测试污染）
        if approval_gate is None:
            window_tracker = LiveOpsBudgetWindowTracker(
                audit_log_dir=str(self.data_dir / "liveops")
            )
            self.gate = LiveOpsApprovalGate(window_tracker=window_tracker)
        else:
            self.gate = approval_gate
        self.shadow_mode = shadow_mode
        self._audit_path = self.data_dir / "liveops" / "approval_decisions.jsonl"
        self._executions_path = self.data_dir / "liveops" / "campaign_executions.jsonl"

    def execute_campaign(self, campaign: Any) -> CampaignExecutionResult:
        """执行回流活动方案 — 主入口."""
        # 拆分活动为执行动作
        exec_actions = self._campaign_to_actions(campaign)

        # 评估每个动作的审批级别
        max_level = 0
        for ea in exec_actions:
            decision = self.gate.evaluate(
                campaign_type=campaign.campaign_type,
                action_type=ea.action_type,
                rewards_amount=ea.rewards_amount,
                game_id=campaign.game_id,
            )
            ea.approval_level = decision.level
            ea.risk_level = self._risk_level_for(decision.level)
            if decision.level > max_level:
                max_level = decision.level

        result = CampaignExecutionResult(
            execution_id="",
            campaign_id=campaign.campaign_id,
            game_id=campaign.game_id,
            campaign_type=campaign.campaign_type,
            target_segment=campaign.target_segment,
            target_count=campaign.target_count,
            rewards_pool=campaign.rewards_pool,
            dry_run=self.dry_run,
            approval_level=max_level,
            status=STATUS_PENDING,
            actions=exec_actions,
        )

        # 根据 max_level 决定整体执行策略
        if max_level == LEVEL_0:
            # 全部 Level 0 → 自动执行
            self._execute_all(result, exec_actions)
        elif max_level == LEVEL_1:
            # Level 1 → dry_run 验证后执行
            if self.dry_run:
                # dry_run 模式: 只记录不执行
                result.status = STATUS_DRY_RUN
                result.blocked_reason = "Level 1 dry_run 模式: 已生成执行计划，未真实下发"
                for ea in exec_actions:
                    ea.status = STATUS_DRY_RUN
            else:
                # live 模式: dry_run 验证后执行
                self._execute_with_dry_run(result, exec_actions)
        else:
            # Level 2 → 阻塞等人工审批
            result.status = STATUS_BLOCKED
            result.blocked_reason = (
                f"Level 2 需人工审批 (rewards_pool=${campaign.rewards_pool:.2f})"
            )
            for ea in exec_actions:
                ea.status = STATUS_BLOCKED

        # 持久化执行结果和 audit log
        result.completed_at = datetime.now(timezone.utc).isoformat()
        self._persist_execution(result)
        self._audit_campaign(campaign, result)

        return result

    def approve(
        self,
        execution_id: str,
        approver: str = "admin",
    ) -> CampaignExecutionResult | None:
        """人工审批通过 — 执行阻塞的活动."""
        result = self._load_execution(execution_id)
        if result is None:
            return None
        if result.status not in (STATUS_BLOCKED, STATUS_DRY_RUN, STATUS_PENDING):
            return result

        result.approved_by = approver
        result.approved_at = datetime.now(timezone.utc).isoformat()
        result.status = STATUS_APPROVED

        # 审批通过后执行 — 按 result.dry_run 决定 adapter 模式
        # (blocked 来自 live 执行 → 真实下发; dry_run 执行 → 模拟下发)
        original_adapter_dry_run = self.adapter.dry_run
        self.adapter.dry_run = result.dry_run
        try:
            self._execute_all(result, result.actions)
        finally:
            self.adapter.dry_run = original_adapter_dry_run
        result.completed_at = datetime.now(timezone.utc).isoformat()
        self._persist_execution(result)
        self._audit_approval(result, approved=True, approver=approver)
        return result

    def reject(
        self,
        execution_id: str,
        approver: str = "admin",
        reason: str = "",
    ) -> CampaignExecutionResult | None:
        """人工审批拒绝."""
        result = self._load_execution(execution_id)
        if result is None:
            return None
        result.approved_by = approver
        result.approved_at = datetime.now(timezone.utc).isoformat()
        result.status = STATUS_REJECTED
        result.blocked_reason = reason or "人工审批拒绝"
        for ea in result.actions:
            ea.status = STATUS_REJECTED
        self._persist_execution(result)
        self._audit_approval(result, approved=False, approver=approver, reason=reason)
        return result

    def get_execution(self, execution_id: str) -> CampaignExecutionResult | None:
        """查询执行状态."""
        return self._load_execution(execution_id)

    def list_executions(
        self, campaign_id: str | None = None
    ) -> list[CampaignExecutionResult]:
        """列出执行记录 (可按 campaign_id 过滤).

        JSONL 是 append-only，同一 execution_id 可能有多次记录 (blocked → completed)，
        按 execution_id 去重保留最新一条。
        """
        if not self._executions_path.exists():
            return []
        # 按 execution_id 去重，后出现的覆盖先出现的 (保留最新状态)
        latest: dict[str, dict[str, Any]] = {}
        try:
            text = self._executions_path.read_text(encoding="utf-8")
        except OSError:
            return []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if campaign_id and record.get("campaign_id") != campaign_id:
                continue
            exec_id = record.get("execution_id", "")
            latest[exec_id] = record  # 后出现的覆盖
        return [self._dict_to_result(r) for r in latest.values()]

    def list_pending_approvals(self) -> list[CampaignExecutionResult]:
        """列出待审批的执行 (status=blocked)."""
        all_execs = self.list_executions()
        return [e for e in all_execs if e.status == STATUS_BLOCKED]

    # ── 内部方法 ──────────────────────────────────────────────

    def _campaign_to_actions(
        self, campaign: Any
    ) -> list[CampaignExecutionAction]:
        """将 WinbackCampaign.actions 转换为 CampaignExecutionAction 列表."""
        # 每个动作的奖励金额 = rewards_pool / len(actions) (均分)
        per_action_reward = 0.0
        reward_actions = [
            a for a in campaign.actions if a.action_type == REWARD_ACTION
        ]
        if reward_actions:
            per_action_reward = campaign.rewards_pool / len(reward_actions)

        exec_actions: list[CampaignExecutionAction] = []
        for action in campaign.actions:
            rewards_amount = per_action_reward if action.action_type == REWARD_ACTION else 0.0
            exec_actions.append(CampaignExecutionAction(
                action_id=f"act_{uuid.uuid4().hex[:8]}",
                campaign_id=campaign.campaign_id,
                game_id=campaign.game_id,
                action_type=action.action_type,
                target_count=action.target_count,
                content=action.content,
                trigger_delay_hours=action.trigger_delay_hours,
                rewards_amount=round(rewards_amount, 2),
                risk_level="low",
                approval_level=LEVEL_0,
            ))
        return exec_actions

    def _execute_all(
        self,
        result: CampaignExecutionResult,
        actions: list[CampaignExecutionAction],
    ) -> None:
        """执行所有动作 (Level 0 自动 或 审批通过后)."""
        if self.shadow_mode:
            result.status = STATUS_DRY_RUN
            result.blocked_reason = "Shadow 模式: 决策已记录，执行已跳过"
            for ea in actions:
                ea.status = STATUS_DRY_RUN
            return

        all_success = True
        for ea in actions:
            ea.status = STATUS_EXECUTING
            try:
                response = self.adapter.execute(ea)
                ea.platform_response = response
                if self.adapter.verify(ea, response):
                    ea.status = STATUS_COMPLETED
                    ea.executed_at = datetime.now(timezone.utc).isoformat()
                    # 记账 (reward_grant 才计入窗口)
                    if ea.action_type == REWARD_ACTION and ea.rewards_amount > 0:
                        self.gate.window_tracker.record(
                            game_id=ea.game_id,
                            action_type=ea.action_type,
                            amount_usd=ea.rewards_amount,
                            action_id=ea.action_id,
                        )
                else:
                    ea.status = STATUS_FAILED
                    ea.error_message = "verify failed: delivered_count mismatch"
                    all_success = False
                    # 回滚
                    self.adapter.rollback(ea, response)
            except Exception as exc:
                ea.status = STATUS_FAILED
                ea.error_message = f"{type(exc).__name__}: {exc}"
                all_success = False

        result.status = STATUS_COMPLETED if all_success else STATUS_FAILED
        if not all_success:
            result.blocked_reason = "部分动作执行失败，已回滚"

    def _execute_with_dry_run(
        self,
        result: CampaignExecutionResult,
        actions: list[CampaignExecutionAction],
    ) -> None:
        """Level 1: dry_run 验证后执行."""
        # 1) dry_run 验证
        original_dry_run = self.adapter.dry_run
        self.adapter.dry_run = True
        dry_run_ok = True
        for ea in actions:
            if ea.approval_level < LEVEL_1:
                continue  # Level 0 动作跳过验证
            try:
                response = self.adapter.execute(ea)
                if not self.adapter.verify(ea, response):
                    dry_run_ok = False
                    ea.status = STATUS_FAILED
                    ea.error_message = "dry_run verify failed"
                    break
            except Exception as exc:
                dry_run_ok = False
                ea.status = STATUS_FAILED
                ea.error_message = f"dry_run raised: {exc}"
                break

        # 2) 恢复 dry_run 设置
        self.adapter.dry_run = original_dry_run

        if not dry_run_ok:
            result.status = STATUS_BLOCKED
            result.blocked_reason = "Level 1 dry_run 验证失败，需人工审批"
            for ea in actions:
                if ea.status not in (STATUS_FAILED, STATUS_COMPLETED):
                    ea.status = STATUS_BLOCKED
            return

        # 3) dry_run 通过 → 真实执行
        self._execute_all(result, actions)

    def _risk_level_for(self, level: int) -> str:
        """审批级别 → 风险等级字符串."""
        return {0: "low", 1: "medium", 2: "high"}.get(level, "medium")

    def _persist_execution(self, result: CampaignExecutionResult) -> None:
        """持久化执行结果到 JSONL."""
        try:
            self._executions_path.parent.mkdir(parents=True, exist_ok=True)
            with self._executions_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist execution: %s", exc)

    def _load_execution(self, execution_id: str) -> CampaignExecutionResult | None:
        """从 JSONL 加载执行记录 (取最后一条匹配)."""
        if not self._executions_path.exists():
            return None
        try:
            text = self._executions_path.read_text(encoding="utf-8")
        except OSError:
            return None
        record = None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("execution_id") == execution_id:
                record = r  # 取最后一条
        if record is None:
            return None
        return self._dict_to_result(record)

    def _audit_campaign(self, campaign: Any, result: CampaignExecutionResult) -> None:
        """记录活动执行 audit log."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "execution_id": result.execution_id,
            "campaign_id": campaign.campaign_id,
            "game_id": campaign.game_id,
            "campaign_type": campaign.campaign_type,
            "target_segment": campaign.target_segment,
            "rewards_pool": round(campaign.rewards_pool, 2),
            "dry_run": result.dry_run,
            "approval_level": result.approval_level,
            "status": result.status,
            "shadow": self.shadow_mode,
            "blocked_reason": result.blocked_reason,
            "action_count": len(result.actions),
            "actions_summary": [
                {
                    "action_id": a.action_id,
                    "action_type": a.action_type,
                    "level": a.approval_level,
                    "rewards_amount": a.rewards_amount,
                    "status": a.status,
                }
                for a in result.actions
            ],
        }
        result.audit_record = record
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist audit log: %s", exc)

    def _audit_approval(
        self,
        result: CampaignExecutionResult,
        approved: bool,
        approver: str,
        reason: str = "",
    ) -> None:
        """记录审批 audit log."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "execution_id": result.execution_id,
            "campaign_id": result.campaign_id,
            "approved": approved,
            "approver": approver,
            "reason": reason,
            "status": result.status,
        }
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to persist approval audit: %s", exc)

    @staticmethod
    def _dict_to_result(record: dict[str, Any]) -> CampaignExecutionResult:
        """从 dict 恢复 CampaignExecutionResult."""
        actions = [
            CampaignExecutionAction(
                action_id=a.get("action_id", ""),
                campaign_id=a.get("campaign_id", ""),
                game_id=a.get("game_id", ""),
                action_type=a.get("action_type", ""),
                target_count=int(a.get("target_count", 0)),
                content=a.get("content", ""),
                trigger_delay_hours=int(a.get("trigger_delay_hours", 0)),
                rewards_amount=float(a.get("rewards_amount", 0.0)),
                risk_level=a.get("risk_level", "low"),
                approval_level=int(a.get("approval_level", 0)),
                status=a.get("status", STATUS_PENDING),
                error_message=a.get("error_message", ""),
                executed_at=a.get("executed_at", ""),
                platform_response=a.get("platform_response", {}),
            )
            for a in (record.get("actions") or [])
        ]
        return CampaignExecutionResult(
            execution_id=record.get("execution_id", ""),
            campaign_id=record.get("campaign_id", ""),
            game_id=record.get("game_id", ""),
            campaign_type=record.get("campaign_type", ""),
            target_segment=record.get("target_segment", ""),
            target_count=int(record.get("target_count", 0)),
            rewards_pool=float(record.get("rewards_pool", 0.0)),
            dry_run=bool(record.get("dry_run", True)),
            approval_level=int(record.get("approval_level", 0)),
            status=record.get("status", STATUS_PENDING),
            blocked_reason=record.get("blocked_reason", ""),
            actions=actions,
            approved_by=record.get("approved_by", ""),
            approved_at=record.get("approved_at", ""),
            created_at=record.get("created_at", ""),
            completed_at=record.get("completed_at", ""),
        )


# ═══════════════════════════════════════════════════════════════
# LiveOpsStatsAggregator — 执行结果统计聚合 (Dashboard 回流)
# ═══════════════════════════════════════════════════════════════


class LiveOpsStatsAggregator:
    """LiveOps 执行结果统计聚合器 — 从 JSONL 聚合为 Dashboard 概览.

    数据源: data/liveops/campaign_executions.jsonl (append-only)
    去重策略: 按 execution_id 保留最新一条记录 (blocked → completed)

    输出 LiveOpsOverview:
      - 执行总数 / 各状态分布
      - 累计下发奖励金额 (仅 live completed)
      - 推送/奖励/邮件送达总数
      - 按游戏分组的执行统计
      - 最近 N 条执行记录摘要
    """

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = Path(data_dir)
        self._executions_path = self.data_dir / "liveops" / "campaign_executions.jsonl"

    def aggregate(self, recent_limit: int = 10) -> dict[str, Any]:
        """聚合 LiveOps 执行结果统计."""
        results = self._load_latest_executions()
        if not results:
            return self._empty_overview()

        # 状态分布
        status_counts: dict[str, int] = {}
        # 下发统计 (仅 live completed)
        total_rewards_distributed = 0.0
        total_push_delivered = 0
        total_reward_grant_delivered = 0
        total_email_delivered = 0
        total_in_app_delivered = 0
        # 按游戏分组
        by_game: dict[str, dict[str, Any]] = {}

        for r in results:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

            game_stat = by_game.setdefault(r.game_id, {
                "executions": 0, "completed": 0, "blocked": 0,
                "rewards_distributed": 0.0, "target_count": 0,
            })
            game_stat["executions"] += 1
            if r.status == STATUS_COMPLETED:
                game_stat["completed"] += 1
            elif r.status == STATUS_BLOCKED:
                game_stat["blocked"] += 1
            game_stat["target_count"] += r.target_count

            # 统计下发量 (仅 live 模式且 completed)
            if r.status == STATUS_COMPLETED and not r.dry_run:
                for a in r.actions:
                    if a.status != STATUS_COMPLETED:
                        continue
                    delivered = a.platform_response.get("delivered_count", 0)
                    if a.action_type == "push_notification":
                        total_push_delivered += delivered
                    elif a.action_type == "reward_grant":
                        total_reward_grant_delivered += delivered
                        total_rewards_distributed += a.rewards_amount
                        game_stat["rewards_distributed"] += a.rewards_amount
                    elif a.action_type == "email":
                        total_email_delivered += delivered
                    elif a.action_type == "in_app_message":
                        total_in_app_delivered += delivered

        # 最近 N 条 (按 created_at 倒序)
        recent = sorted(results, key=lambda x: x.created_at, reverse=True)[:recent_limit]
        recent_summaries = [self._result_to_summary(r) for r in recent]

        total = len(results)
        completed = status_counts.get(STATUS_COMPLETED, 0)
        return {
            "total_executions": total,
            "status_breakdown": status_counts,
            "completed": completed,
            "blocked": status_counts.get(STATUS_BLOCKED, 0),
            "dry_run": status_counts.get(STATUS_DRY_RUN, 0),
            "failed": status_counts.get(STATUS_FAILED, 0),
            "rejected": status_counts.get(STATUS_REJECTED, 0),
            "success_rate": round(completed / max(total, 1), 4),
            "total_rewards_distributed": round(total_rewards_distributed, 2),
            "total_push_delivered": total_push_delivered,
            "total_reward_grant_delivered": total_reward_grant_delivered,
            "total_email_delivered": total_email_delivered,
            "total_in_app_delivered": total_in_app_delivered,
            "by_game": by_game,
            "recent_executions": recent_summaries,
        }

    def _load_latest_executions(self) -> list[CampaignExecutionResult]:
        """加载所有执行记录 (按 execution_id 去重保留最新)."""
        if not self._executions_path.exists():
            return []
        latest: dict[str, dict[str, Any]] = {}
        try:
            text = self._executions_path.read_text(encoding="utf-8")
        except OSError:
            return []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            exec_id = record.get("execution_id", "")
            latest[exec_id] = record
        return [WinbackCampaignExecutor._dict_to_result(r) for r in latest.values()]

    @staticmethod
    def _result_to_summary(r: CampaignExecutionResult) -> dict[str, Any]:
        """执行结果 → 精简摘要 (Dashboard 展示用)."""
        action_summary: dict[str, int] = {}
        for a in r.actions:
            action_summary[a.action_type] = action_summary.get(a.action_type, 0) + 1
        return {
            "execution_id": r.execution_id,
            "campaign_id": r.campaign_id,
            "game_id": r.game_id,
            "campaign_type": r.campaign_type,
            "target_segment": r.target_segment,
            "target_count": r.target_count,
            "rewards_pool": round(r.rewards_pool, 2),
            "dry_run": r.dry_run,
            "approval_level": r.approval_level,
            "status": r.status,
            "blocked_reason": r.blocked_reason,
            "action_count": len(r.actions),
            "action_summary": action_summary,
            "approved_by": r.approved_by,
            "created_at": r.created_at,
            "completed_at": r.completed_at,
        }

    @staticmethod
    def _empty_overview() -> dict[str, Any]:
        return {
            "total_executions": 0,
            "status_breakdown": {},
            "completed": 0,
            "blocked": 0,
            "dry_run": 0,
            "failed": 0,
            "rejected": 0,
            "success_rate": 0.0,
            "total_rewards_distributed": 0.0,
            "total_push_delivered": 0,
            "total_reward_grant_delivered": 0,
            "total_email_delivered": 0,
            "total_in_app_delivered": 0,
            "by_game": {},
            "recent_executions": [],
        }


__all__ = [
    "CampaignExecutionAction",
    "CampaignExecutionResult",
    "WinbackCampaignAdapter",
    "LiveOpsBudgetWindowTracker",
    "ApprovalDecision",
    "LiveOpsApprovalGate",
    "WinbackCampaignExecutor",
    "LiveOpsStatsAggregator",
    "LEVEL_0",
    "LEVEL_1",
    "LEVEL_2",
    "STATUS_PENDING",
    "STATUS_APPROVED",
    "STATUS_REJECTED",
    "STATUS_EXECUTING",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_BLOCKED",
    "STATUS_DRY_RUN",
]
