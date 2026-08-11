"""P2.4.5 Execution Sandbox — 安全闸门（Rule 1~3 + Post Verify）。

SafeExecutor 的「控制平面」：每个闸门只回答一个问题，绝不拥有决策权
（决策权在 E17.3；授权权在 P2.3；本层只负责「现在敢不敢动手」）。

Execution Policy 落点：
    Rule 1  授权缺失 / 过期 / 动作不符 -> BLOCK   （check_authorization）
    Rule 2  幂等冲突（RUNNING / ROLLED_BACK）-> BLOCK（check_idempotency 包装）
    Rule 3  Snapshot 失败 -> BLOCK                 （executor 内 try SnapshotError）
    风险闸门：risk_score >= block_threshold -> BLOCK（生产模式硬顶）
    Post Verify：执行后结果完整性校验（Rule 4 的触发判据）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from src.execution.safe_executor.idempotency import (
    ExecutionIdempotencyStore,
    VERDICT_ALLOW,
    VERDICT_ALLOW_RETRY,
    VERDICT_BLOCK_ROLLED_BACK,
    VERDICT_REJECT_RUNNING,
    VERDICT_RETURN_EXISTING,
    check_idempotency,
)

# 生产模式风险硬顶：risk_score >= 0.9 无论是否有授权一律 BLOCK
DEFAULT_RISK_BLOCK_THRESHOLD = 0.9


@dataclass
class GateCheck:
    """一次闸门检查的结果。"""

    ok: bool
    gate: str
    reason: str
    verdict: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "gate": self.gate,
            "reason": self.reason,
            "verdict": self.verdict,
        }


def _as_str(value: Any) -> str:
    return str(getattr(value, "value", value))


class ExecutionSandbox:
    """安全闸门集合。所有方法均为纯判定，不触碰外部系统。"""

    def __init__(
        self,
        risk_block_threshold: float = DEFAULT_RISK_BLOCK_THRESHOLD,
    ) -> None:
        self.risk_block_threshold = risk_block_threshold

    # ------------------------------------------------------------------
    # Rule 1：授权验证（仅 PRODUCTION 模式强制）
    # ------------------------------------------------------------------
    def check_authorization(self, request: Any) -> GateCheck:
        """复用 P2.3 ExecutionAuthorization：allows(action) + is_expired()。

        - 非 PRODUCTION：直接放行（SIM / DRY_RUN 无需授权）
        - PRODUCTION 且无 authorization -> BLOCK
        - authorization.allows(action) 不匹配 -> BLOCK
        - authorization.is_expired() -> BLOCK（Rule 1：Approval 过期）
        """
        mode = _as_str(getattr(request, "mode", "dry_run"))
        if mode != "production":
            return GateCheck(True, "authorization", f"非生产模式（{mode}），无需授权")

        authorization = getattr(request, "authorization", None)
        if authorization is None:
            return GateCheck(
                False, "authorization", "生产模式缺少 ExecutionAuthorization（Rule 1）"
            )

        action = _as_str(getattr(getattr(request, "intent", None), "action", ""))
        allows = getattr(authorization, "allows", None)
        if callable(allows) and not allows(action):
            allowed = _as_str(getattr(authorization, "allowed_action", ""))
            return GateCheck(
                False,
                "authorization",
                f"授权动作不匹配：允许 {allowed}，请求 {action}（Rule 1）",
            )

        is_expired = getattr(authorization, "is_expired", None)
        if callable(is_expired) and is_expired():
            return GateCheck(
                False,
                "authorization",
                f"授权已过期（expires_at={getattr(authorization, 'expires_at', '?')}，Rule 1）",
            )

        return GateCheck(
            True,
            "authorization",
            f"授权有效：{getattr(authorization, 'approval_id', '')} 允许 {action}",
        )

    # ------------------------------------------------------------------
    # 风险闸门：生产模式硬顶
    # ------------------------------------------------------------------
    def check_risk(self, request: Any) -> GateCheck:
        mode = _as_str(getattr(request, "mode", "dry_run"))
        risk = float(getattr(getattr(request, "intent", None), "risk_level", 0.0) or 0.0)
        if mode == "production" and risk >= self.risk_block_threshold:
            return GateCheck(
                False,
                "risk",
                f"风险分 {risk:.2f} >= 硬顶 {self.risk_block_threshold:.2f}，生产模式禁止执行",
            )
        return GateCheck(True, "risk", f"风险分 {risk:.2f} 通过（模式 {mode}）")

    # ------------------------------------------------------------------
    # Rule 2：幂等闸门（包装 idempotency.check_idempotency）
    # ------------------------------------------------------------------
    def check_idempotency(
        self, store: Optional[ExecutionIdempotencyStore], key: str
    ) -> Tuple[GateCheck, Optional[Any]]:
        """返回 (GateCheck, existing_record)。

        verdict 语义：
            ALLOW / ALLOW_RETRY   -> ok=True，正常执行
            RETURN_EXISTING       -> ok=True，但 executor 应短路返回历史结果
            REJECT_RUNNING        -> ok=False（Rule 2 BLOCK）
            BLOCK_ROLLED_BACK     -> ok=False（禁止自动重试）
        """
        if store is None:
            return GateCheck(True, "idempotency", "未配置幂等存储，跳过", VERDICT_ALLOW), None

        verdict, record = check_idempotency(store, key)
        if verdict in (VERDICT_ALLOW, VERDICT_ALLOW_RETRY):
            reason = "首次执行" if verdict == VERDICT_ALLOW else "上次 FAILED，允许重试"
            return GateCheck(True, "idempotency", reason, verdict), record
        if verdict == VERDICT_RETURN_EXISTING:
            return (
                GateCheck(True, "idempotency", "已有 SUCCESS 记录，返回历史结果", verdict),
                record,
            )
        if verdict == VERDICT_REJECT_RUNNING:
            return (
                GateCheck(
                    False,
                    "idempotency",
                    f"相同幂等键正在执行中（execution_id={record.execution_id}），"
                    "拒绝重复执行（Rule 2）",
                    verdict,
                ),
                record,
            )
        # BLOCK_ROLLED_BACK
        return (
            GateCheck(
                False,
                "idempotency",
                f"该动作曾被回滚（execution_id={record.execution_id}），"
                "禁止自动重试，需人工确认",
                verdict,
            ),
            record,
        )

    # ------------------------------------------------------------------
    # Post Verify：执行后校验（Rule 4 触发判据）
    # ------------------------------------------------------------------
    def post_verify(self, result: Any) -> GateCheck:
        """执行后结果完整性校验。

        - result 为 None -> 失败
        - status FAILED -> 失败（触发 Rule 4 回滚流程）
        - status BLOCKED -> ok=False 但 verdict=BLOCKED（不回滚：从未动手）
        - 其余（SUCCESS / DRY_RUN）-> 通过
        """
        if result is None:
            return GateCheck(False, "post_verify", "Provider 未返回结果", "FAILED")
        status = str(getattr(result, "status", ""))
        if status == "failed":
            return GateCheck(
                False,
                "post_verify",
                f"Provider 执行失败：{getattr(result, 'error', '')}（Rule 4 触发回滚）",
                "FAILED",
            )
        if status == "blocked":
            return GateCheck(
                False,
                "post_verify",
                f"Provider/Router 拦截：{getattr(result, 'error', '')}",
                "BLOCKED",
            )
        return GateCheck(True, "post_verify", f"执行结果状态 {status} 校验通过")


__all__ = [
    "DEFAULT_RISK_BLOCK_THRESHOLD",
    "GateCheck",
    "ExecutionSandbox",
]
