"""E15.0.9 Adjust Adapter — Adjust 归因平台适配器.

将 GrowthAction 转换为 Adjust API 调用，实现:
  - VERIFY_ATTRIBUTION: 验证归因数据 (spend/revenue 一致性)
  - SYNC_METADATA:      同步元数据 (campaign / creative 映射)

Phase 2: Mock 实现 (模拟 API 调用)
Phase 3: 连接真实 Adjust API
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..adapter_base import (
    AdapterExecutionResult,
    AdapterResultStatus,
    ExecutionAdapter,
)
from ..growth_action import ActionType, GrowthAction


class AdjustAdapter(ExecutionAdapter):
    """Adjust 归因平台适配器 — 验证执行结果与同步元数据.

    支持的 ActionType:
      - VERIFY_ATTRIBUTION
      - SYNC_METADATA

    用法:
        adapter = AdjustAdapter(app_token="abc123")
        result = adapter.execute(action)
    """

    SUPPORTED_ACTIONS: set[ActionType] = {
        ActionType.VERIFY_ATTRIBUTION,
        ActionType.SYNC_METADATA,
    }

    def __init__(
        self,
        app_token: str = "",
        name: str = "AdjustAdapter",
    ):
        super().__init__(name=name)
        self._app_token = app_token
        self._verifications: list[dict[str, Any]] = []
        self._metadata_syncs: list[dict[str, Any]] = []

    # ── Execute ───────────────────────────────────────────────

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        """执行 Adjust 动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            self._record_failure()
            return AdapterExecutionResult.failure_result(
                action,
                error=f"Unsupported action: {action.action_type.value}",
                adapter_name=self._name,
            )

        try:
            if action.action_type == ActionType.VERIFY_ATTRIBUTION:
                return self._verify_attribution(action)
            elif action.action_type == ActionType.SYNC_METADATA:
                return self._sync_metadata(action)
            else:
                return AdapterExecutionResult.failure_result(
                    action, error=f"Unhandled action: {action.action_type.value}",
                    adapter_name=self._name,
                )
        except Exception as e:
            self._record_failure()
            return AdapterExecutionResult.failure_result(
                action, error=str(e), adapter_name=self._name,
            )

    # ── Validate ──────────────────────────────────────────────

    def validate(self, action: GrowthAction) -> bool:
        """校验 Adjust 动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False

        if action.action_type == ActionType.VERIFY_ATTRIBUTION:
            # 需要 campaign_id 或 expected_metrics
            return (
                bool(action.target)
                or "expected_metrics" in action.parameters
            )
        elif action.action_type == ActionType.SYNC_METADATA:
            return "metadata" in action.parameters and bool(action.parameters["metadata"])

        return True

    # ── Rollback ──────────────────────────────────────────────

    def rollback(
        self,
        action: GrowthAction,
        result: AdapterExecutionResult,
    ) -> AdapterExecutionResult:
        """回滚 Adjust 动作 (无实际操作，仅标记)."""
        self._record_rollback()
        return AdapterExecutionResult.success_result(
            action,
            external_id=result.external_id,
            adapter_name=self._name,
            rollback_action="noop_adjust",
            note="Adjust operations are read-only or metadata-only",
        )

    # ── Private: Action Handlers ──────────────────────────────

    def _verify_attribution(self, action: GrowthAction) -> AdapterExecutionResult:
        campaign_id = action.target
        expected_metrics = action.parameters.get("expected_metrics", {})

        # Mock: 模拟 Adjust 数据验证
        verification_id = f"adjust_verify_{uuid.uuid4().hex[:12]}"
        mock_metrics = {
            "spend": expected_metrics.get("spend", 0),
            "revenue": expected_metrics.get("revenue", 0),
            "impressions": expected_metrics.get("impressions", 0),
            "clicks": expected_metrics.get("clicks", 0),
            "installs": expected_metrics.get("installs", 0),
            "roas": expected_metrics.get("roas", 0),
        }

        verification = {
            "verification_id": verification_id,
            "campaign_id": campaign_id,
            "metrics": mock_metrics,
            "verified": True,
            "confidence": 0.95,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
        self._verifications.append(verification)

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=verification_id,
            adapter_name=self._name,
            platform="adjust",
            campaign_id=campaign_id,
            verified=True,
            metrics=mock_metrics,
        )

    def _sync_metadata(self, action: GrowthAction) -> AdapterExecutionResult:
        metadata = action.parameters["metadata"]

        sync_id = f"adjust_sync_{uuid.uuid4().hex[:12]}"
        sync_record = {
            "sync_id": sync_id,
            "game_id": action.game_id,
            "metadata": metadata,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        self._metadata_syncs.append(sync_record)

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=sync_id,
            adapter_name=self._name,
            platform="adjust",
            synced_fields=list(metadata.keys()),
        )

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        base = super().stats()
        base.update({
            "app_token": self._app_token[:4] + "****" if self._app_token else "",
            "verifications": len(self._verifications),
            "metadata_syncs": len(self._metadata_syncs),
        })
        return base


__all__ = ["AdjustAdapter"]