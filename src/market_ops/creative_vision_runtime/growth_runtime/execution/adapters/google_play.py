"""E15.0.9 Google Play Adapter — Google Play 平台适配器.

将 GrowthAction 转换为 Google Play Developer API 调用，实现:
  - PUBLISH_RELEASE:      发布新版本到 production track
  - UPDATE_STORE_METADATA: 更新商店页元数据
  - START_ROLLOUT:        开始分阶段发布

Phase 2: Mock 实现 (模拟 API 调用)
Phase 3: 连接真实 Google Play Developer API
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..adapter_base import (
    AdapterExecutionResult,
    ExecutionAdapter,
)
from ..growth_action import ActionType, GrowthAction


class GooglePlayAdapter(ExecutionAdapter):
    """Google Play 平台适配器 — 将 GrowthAction 转换为 Google Play API 调用.

    支持的 ActionType:
      - PUBLISH_RELEASE
      - UPDATE_STORE_METADATA
      - START_ROLLOUT

    用法:
        adapter = GooglePlayAdapter(package_name="com.example.game")
        result = adapter.execute(action)
    """

    SUPPORTED_ACTIONS: set[ActionType] = {
        ActionType.PUBLISH_RELEASE,
        ActionType.UPDATE_STORE_METADATA,
        ActionType.START_ROLLOUT,
    }

    def __init__(
        self,
        package_name: str = "",
        service_account_json: str = "",
        name: str = "GooglePlayAdapter",
    ):
        super().__init__(name=name)
        self._package_name = package_name
        self._service_account_json = service_account_json
        self._releases: list[dict[str, Any]] = []
        self._current_metadata: dict[str, Any] = {}

    # ── Execute ───────────────────────────────────────────────

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        """执行 Google Play 动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            self._record_failure()
            return AdapterExecutionResult.failure_result(
                action,
                error=f"Unsupported action: {action.action_type.value}",
                adapter_name=self._name,
            )

        try:
            if action.action_type == ActionType.PUBLISH_RELEASE:
                return self._publish_release(action)
            elif action.action_type == ActionType.UPDATE_STORE_METADATA:
                return self._update_metadata(action)
            elif action.action_type == ActionType.START_ROLLOUT:
                return self._start_rollout(action)
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
        """校验 Google Play 动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False

        if action.action_type == ActionType.PUBLISH_RELEASE:
            return (
                "version" in action.parameters
                and bool(action.parameters["version"])
            )
        elif action.action_type == ActionType.UPDATE_STORE_METADATA:
            return "metadata" in action.parameters and bool(action.parameters["metadata"])
        elif action.action_type == ActionType.START_ROLLOUT:
            return (
                "version" in action.parameters
                and "percentage" in action.parameters
            )

        return True

    # ── Rollback ──────────────────────────────────────────────

    def rollback(
        self,
        action: GrowthAction,
        result: AdapterExecutionResult,
    ) -> AdapterExecutionResult:
        """回滚 Google Play 动作."""
        self._record_rollback()

        if action.action_type == ActionType.PUBLISH_RELEASE:
            # 回滚发布 = 暂停 rollout 或下架
            return AdapterExecutionResult.success_result(
                action,
                external_id=action.target,
                adapter_name=self._name,
                rollback_action="halt_release",
            )

        elif action.action_type == ActionType.UPDATE_STORE_METADATA:
            # 回滚元数据 = 恢复旧元数据
            return AdapterExecutionResult.success_result(
                action,
                external_id=action.target,
                adapter_name=self._name,
                rollback_action="restore_metadata",
            )

        elif action.action_type == ActionType.START_ROLLOUT:
            # 回滚 rollout = 停止 rollout
            return AdapterExecutionResult.success_result(
                action,
                external_id=action.target,
                adapter_name=self._name,
                rollback_action="halt_rollout",
            )

        return super().rollback(action, result)

    # ── Private: Action Handlers ──────────────────────────────

    def _publish_release(self, action: GrowthAction) -> AdapterExecutionResult:
        package_name = action.target or self._package_name
        version = action.parameters["version"]
        track = action.parameters.get("track", "production")

        release_id = f"play_release_{uuid.uuid4().hex[:12]}"
        release = {
            "release_id": release_id,
            "package_name": package_name,
            "version": version,
            "track": track,
            "status": "completed",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        self._releases.append(release)

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=release_id,
            adapter_name=self._name,
            platform="google_play",
            package_name=package_name,
            version=version,
            track=track,
        )

    def _update_metadata(self, action: GrowthAction) -> AdapterExecutionResult:
        package_name = action.target or self._package_name
        metadata = action.parameters["metadata"]

        update_id = f"play_meta_{uuid.uuid4().hex[:12]}"
        self._current_metadata[package_name] = {
            "update_id": update_id,
            "metadata": metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=update_id,
            adapter_name=self._name,
            platform="google_play",
            package_name=package_name,
        )

    def _start_rollout(self, action: GrowthAction) -> AdapterExecutionResult:
        package_name = action.target or self._package_name
        version = action.parameters["version"]
        percentage = action.parameters["percentage"]

        rollout_id = f"play_rollout_{uuid.uuid4().hex[:12]}"
        self._releases.append({
            "rollout_id": rollout_id,
            "package_name": package_name,
            "version": version,
            "percentage": percentage,
            "status": "in_progress",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=rollout_id,
            adapter_name=self._name,
            platform="google_play",
            package_name=package_name,
            version=version,
            percentage=percentage,
        )

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        base = super().stats()
        base.update({
            "package_name": self._package_name,
            "releases_count": len(self._releases),
        })
        return base


__all__ = ["GooglePlayAdapter"]