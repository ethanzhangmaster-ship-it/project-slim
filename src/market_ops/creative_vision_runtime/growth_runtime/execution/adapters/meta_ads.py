"""E15.0.9 Meta Ads Adapter — Meta Ads 平台适配器.

将 GrowthAction 转换为 Meta Marketing API 调用，实现:
  - UPDATE_CAMPAIGN_BUDGET: 调整广告系列预算
  - PAUSE_CAMPAIGN:        暂停广告系列
  - RESUME_CAMPAIGN:       恢复广告系列
  - CREATE_CAMPAIGN:       创建广告系列
  - UPLOAD_CREATIVE:       上传素材
  - PAUSE_CREATIVE:        暂停素材

Phase 2: Mock 实现 (模拟 API 调用)
Phase 3: 连接真实 Meta Graph API v18.0
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


class MetaAdsAdapter(ExecutionAdapter):
    """Meta Ads 平台适配器 — 将 GrowthAction 转换为 Meta API 调用.

    支持的 ActionType:
      - UPDATE_CAMPAIGN_BUDGET
      - PAUSE_CAMPAIGN
      - RESUME_CAMPAIGN
      - CREATE_CAMPAIGN
      - UPLOAD_CREATIVE
      - PAUSE_CREATIVE

    用法:
        adapter = MetaAdsAdapter(ad_account_id="act_123", access_token="...")
        result = adapter.execute(action)
    """

    SUPPORTED_ACTIONS: set[ActionType] = {
        ActionType.UPDATE_CAMPAIGN_BUDGET,
        ActionType.PAUSE_CAMPAIGN,
        ActionType.RESUME_CAMPAIGN,
        ActionType.CREATE_CAMPAIGN,
        ActionType.UPLOAD_CREATIVE,
        ActionType.PAUSE_CREATIVE,
    }

    def __init__(
        self,
        ad_account_id: str = "",
        access_token: str = "",
        name: str = "MetaAdsAdapter",
    ):
        super().__init__(name=name)
        self._ad_account_id = ad_account_id
        self._access_token = access_token
        self._campaign_cache: dict[str, dict[str, Any]] = {}
        self._creative_cache: dict[str, dict[str, Any]] = {}

    # ── Execute ───────────────────────────────────────────────

    def execute(self, action: GrowthAction) -> AdapterExecutionResult:
        """执行 Meta Ads 动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            self._record_failure()
            return AdapterExecutionResult.failure_result(
                action,
                error=f"Unsupported action: {action.action_type.value}",
                adapter_name=self._name,
            )

        try:
            if action.action_type == ActionType.UPDATE_CAMPAIGN_BUDGET:
                return self._update_budget(action)
            elif action.action_type == ActionType.PAUSE_CAMPAIGN:
                return self._pause_campaign(action)
            elif action.action_type == ActionType.RESUME_CAMPAIGN:
                return self._resume_campaign(action)
            elif action.action_type == ActionType.CREATE_CAMPAIGN:
                return self._create_campaign(action)
            elif action.action_type == ActionType.UPLOAD_CREATIVE:
                return self._upload_creative(action)
            elif action.action_type == ActionType.PAUSE_CREATIVE:
                return self._pause_creative(action)
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
        """校验 Meta Ads 动作."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False

        if action.action_type == ActionType.UPDATE_CAMPAIGN_BUDGET:
            return (
                "new_budget" in action.parameters
                and isinstance(action.parameters["new_budget"], (int, float))
                and action.parameters["new_budget"] > 0
            )
        elif action.action_type in {
            ActionType.PAUSE_CAMPAIGN,
            ActionType.RESUME_CAMPAIGN,
        }:
            return bool(action.target)
        elif action.action_type == ActionType.CREATE_CAMPAIGN:
            return "name" in action.parameters and bool(action.parameters["name"])
        elif action.action_type == ActionType.UPLOAD_CREATIVE:
            return "asset_id" in action.parameters and bool(action.parameters["asset_id"])
        elif action.action_type == ActionType.PAUSE_CREATIVE:
            return bool(action.target)

        return True

    # ── Rollback ──────────────────────────────────────────────

    def rollback(
        self,
        action: GrowthAction,
        result: AdapterExecutionResult,
    ) -> AdapterExecutionResult:
        """回滚 Meta Ads 动作."""
        self._record_rollback()

        if action.action_type == ActionType.UPDATE_CAMPAIGN_BUDGET:
            old_budget = action.parameters.get("old_budget")
            if old_budget is not None:
                return AdapterExecutionResult.success_result(
                    action,
                    external_id=action.target,
                    adapter_name=self._name,
                    rollback_action="restore_budget",
                    restored_budget=old_budget,
                )

        elif action.action_type == ActionType.CREATE_CAMPAIGN:
            return AdapterExecutionResult.success_result(
                action,
                external_id=result.external_id,
                adapter_name=self._name,
                rollback_action="pause_created_campaign",
            )

        elif action.action_type == ActionType.PAUSE_CAMPAIGN:
            # 回滚暂停 = 恢复
            return AdapterExecutionResult.success_result(
                action,
                external_id=action.target,
                adapter_name=self._name,
                rollback_action="resume_campaign",
            )

        elif action.action_type == ActionType.RESUME_CAMPAIGN:
            # 回滚恢复 = 暂停
            return AdapterExecutionResult.success_result(
                action,
                external_id=action.target,
                adapter_name=self._name,
                rollback_action="pause_campaign",
            )

        return super().rollback(action, result)

    # ── Private: Action Handlers ──────────────────────────────

    def _update_budget(self, action: GrowthAction) -> AdapterExecutionResult:
        old_budget = action.parameters.get("old_budget", 0)
        new_budget = action.parameters["new_budget"]
        campaign_id = action.target

        # Mock: 更新内存缓存
        if campaign_id not in self._campaign_cache:
            self._campaign_cache[campaign_id] = {"budget": old_budget, "status": "ACTIVE"}
        self._campaign_cache[campaign_id]["budget"] = new_budget

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=campaign_id,
            adapter_name=self._name,
            old_budget=old_budget,
            new_budget=new_budget,
            platform="meta",
        )

    def _pause_campaign(self, action: GrowthAction) -> AdapterExecutionResult:
        campaign_id = action.target

        if campaign_id not in self._campaign_cache:
            self._campaign_cache[campaign_id] = {"budget": 0, "status": "ACTIVE"}
        old_status = self._campaign_cache[campaign_id].get("status", "ACTIVE")
        self._campaign_cache[campaign_id]["status"] = "PAUSED"

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=campaign_id,
            adapter_name=self._name,
            old_status=old_status,
            new_status="PAUSED",
            platform="meta",
        )

    def _resume_campaign(self, action: GrowthAction) -> AdapterExecutionResult:
        campaign_id = action.target

        if campaign_id not in self._campaign_cache:
            self._campaign_cache[campaign_id] = {"budget": 0, "status": "PAUSED"}
        old_status = self._campaign_cache[campaign_id].get("status", "PAUSED")
        self._campaign_cache[campaign_id]["status"] = "ACTIVE"

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=campaign_id,
            adapter_name=self._name,
            old_status=old_status,
            new_status="ACTIVE",
            platform="meta",
        )

    def _create_campaign(self, action: GrowthAction) -> AdapterExecutionResult:
        name = action.parameters.get("name", "AI Campaign")
        objective = action.parameters.get("objective", "APP_INSTALLS")
        daily_budget = action.parameters.get("daily_budget", 100.0)

        campaign_id = f"meta_campaign_{uuid.uuid4().hex[:12]}"
        self._campaign_cache[campaign_id] = {
            "name": name,
            "objective": objective,
            "budget": daily_budget,
            "status": "PAUSED",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=campaign_id,
            adapter_name=self._name,
            platform="meta",
            campaign_name=name,
            daily_budget=daily_budget,
        )

    def _upload_creative(self, action: GrowthAction) -> AdapterExecutionResult:
        asset_id = action.parameters["asset_id"]
        platform = action.target or "meta"

        creative_id = f"meta_creative_{uuid.uuid4().hex[:12]}"
        self._creative_cache[creative_id] = {
            "asset_id": asset_id,
            "platform": platform,
            "status": "ACTIVE",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=creative_id,
            adapter_name=self._name,
            platform=platform,
            asset_id=asset_id,
        )

    def _pause_creative(self, action: GrowthAction) -> AdapterExecutionResult:
        creative_id = action.target

        if creative_id not in self._creative_cache:
            self._creative_cache[creative_id] = {"status": "ACTIVE"}
        self._creative_cache[creative_id]["status"] = "PAUSED"

        self._record_success()
        return AdapterExecutionResult.success_result(
            action,
            external_id=creative_id,
            adapter_name=self._name,
            new_status="PAUSED",
            platform="meta",
        )

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        base = super().stats()
        base.update({
            "ad_account_id": self._ad_account_id,
            "campaigns_cached": len(self._campaign_cache),
            "creatives_cached": len(self._creative_cache),
        })
        return base


__all__ = ["MetaAdsAdapter"]