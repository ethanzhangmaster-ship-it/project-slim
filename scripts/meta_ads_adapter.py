"""MetaAds 平台适配器 — 连接 V2 ActionExecutor 与 V1 FacebookClient。

将 V2 ExecutionAction 转化为 V1 FacebookClient 的真实 Graph API 调用。
V1 FacebookClient 支持 sandbox 模式（默认）和真实 HTTP 模式。

V2 ExecutionAction → MetaAdsPlatformAdapter → V1 FacebookClient → Graph API

关键转换:
  - UPDATE_BUDGET:  parameters["target_budget"] (美元 float) → daily_budget (cents int)
  - PAUSE_CAMPAIGN: adset_id → campaign_id, POST status=PAUSED
  - RESUME_CAMPAIGN: adset_id → campaign_id, POST status=ACTIVE

预算单位: Meta Graph API 要求 daily_budget 为 cents 整数 (如 50000 = $500.00)
"""

from __future__ import annotations

import logging
from typing import Any

from scripts.action_executor import PlatformAdapter
from scripts.action_planner import ActionType, ExecutionAction

logger = logging.getLogger(__name__)


class MetaAdsPlatformAdapter(PlatformAdapter):
    """Meta Ads 平台适配器 — 封装 V1 FacebookClient。

    使用方式:
        from market_ops.execution_runtime.adapters.facebook import FacebookClient
        client = FacebookClient()  # sandbox=True 默认
        adapter = MetaAdsPlatformAdapter(client)
        executor = ActionExecutor(adapter=adapter)
        result = executor.execute(action)
    """

    def __init__(self, client: Any | None = None) -> None:
        """初始化。

        Args:
            client: V1 FacebookClient 实例。为 None 时自动创建 sandbox 实例。
        """
        if client is None:
            from market_ops.execution_runtime.adapters.facebook import FacebookClient
            client = FacebookClient()
        self._client = client

    def execute(self, action: ExecutionAction) -> dict[str, Any]:
        """执行动作 — 调用 V1 FacebookClient API。

        V2 → V1 映射:
          - UPDATE_BUDGET  → client.update_campaign_budget(campaign_id, cents)
          - PAUSE_CAMPAIGN → client.pause_campaign(campaign_id)
          - RESUME_CAMPAIGN → client.resume_campaign(campaign_id)
        """
        campaign_id = action.adset_id

        if action.action_type == ActionType.UPDATE_BUDGET:
            target_budget = action.parameters.get("target_budget", 0.0)
            # 美元 → cents (Meta API 要求整数 cents)
            daily_budget_cents = int(round(target_budget * 100))

            logger.info(
                "MetaAds: update_budget campaign=%s $%.2f → %d cents",
                campaign_id, target_budget, daily_budget_cents,
            )
            raw = self._client.update_campaign_budget(campaign_id, daily_budget_cents)
            return self._format_response(action, raw, "Budget updated")

        if action.action_type == ActionType.PAUSE_CAMPAIGN:
            logger.info("MetaAds: pause_campaign campaign=%s", campaign_id)
            raw = self._client.pause_campaign(campaign_id)
            return self._format_response(action, raw, "Campaign paused")

        if action.action_type == ActionType.RESUME_CAMPAIGN:
            logger.info("MetaAds: resume_campaign campaign=%s", campaign_id)
            raw = self._client.resume_campaign(campaign_id)
            return self._format_response(action, raw, "Campaign resumed")

        return {"status": "ok", "message": "No action taken", "data": {}}

    def verify(
        self, action: ExecutionAction, response: dict[str, Any]
    ) -> bool:
        """验证执行结果 — 通过 get_campaign 确认状态已生效。"""
        if response.get("status") != "ok":
            return False

        campaign_id = action.adset_id

        try:
            raw = self._client.get_campaign(campaign_id)
            data = raw.get("data", {})

            if action.action_type == ActionType.UPDATE_BUDGET:
                # 验证预算已更新
                target_budget = action.parameters.get("target_budget", 0.0)
                expected_cents = str(int(round(target_budget * 100)))
                actual_budget = data.get("daily_budget", "")
                if actual_budget != expected_cents:
                    logger.warning(
                        "MetaAds verify: budget mismatch — expected %s, got %s",
                        expected_cents, actual_budget,
                    )
                    return False

            if action.action_type == ActionType.PAUSE_CAMPAIGN:
                if data.get("status") != "PAUSED":
                    return False

            if action.action_type == ActionType.RESUME_CAMPAIGN:
                if data.get("status") != "ACTIVE":
                    return False

            return True
        except Exception as exc:
            logger.error("MetaAds verify failed: %s", exc)
            return False

    def rollback(
        self, action: ExecutionAction, response: dict[str, Any]
    ) -> dict[str, Any]:
        """回滚 — 反向操作恢复原始状态。"""
        campaign_id = action.adset_id

        if action.action_type == ActionType.UPDATE_BUDGET:
            original = action.parameters.get("current_budget", 0.0)
            cents = int(round(original * 100))
            raw = self._client.update_campaign_budget(campaign_id, cents)
            return self._format_response(action, raw, "Budget rolled back")

        if action.action_type == ActionType.PAUSE_CAMPAIGN:
            raw = self._client.resume_campaign(campaign_id)
            return self._format_response(action, raw, "Campaign resumed (rollback)")

        if action.action_type == ActionType.RESUME_CAMPAIGN:
            raw = self._client.pause_campaign(campaign_id)
            return self._format_response(action, raw, "Campaign paused (rollback)")

        return {"status": "ok", "message": "Rollback noop", "data": {}}

    def _format_response(
        self,
        action: ExecutionAction,
        raw: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        """将 V1 FacebookClient 响应格式化为 V2 统一格式。"""
        success = raw.get("success", False)
        data = raw.get("data", {})

        if not success:
            return {
                "status": "error",
                "message": f"MetaAds API error: {raw.get('error', 'unknown')}",
                "data": {},
            }

        # 提取执行后的实际值
        result_data: dict[str, Any] = {"adset_id": action.adset_id}

        if action.action_type == ActionType.UPDATE_BUDGET:
            # V1 返回 cents 字符串，转回美元 float
            budget_cents = data.get("daily_budget", "0")
            result_data["budget"] = float(budget_cents) / 100.0
        elif action.action_type == ActionType.PAUSE_CAMPAIGN:
            result_data["status"] = data.get("status", "PAUSED").lower()
        elif action.action_type == ActionType.RESUME_CAMPAIGN:
            result_data["status"] = data.get("status", "ACTIVE").lower()

        return {
            "status": "ok",
            "message": message,
            "data": result_data,
        }
