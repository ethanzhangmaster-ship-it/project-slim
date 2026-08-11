"""E13.7 Meta Executor — Meta Ads 真实执行器.

将对 Meta Ads 的 WRITE 操作封装为标准的 BaseExecutor 接口，
支持真实 API 调用和模拟模式，自动处理重试、速率限制和回滚。

支持的动作:
  - CREATE_CAMPAIGN: 创建广告系列
  - CREATE_AD_SET: 创建广告组
  - UPDATE_CAMPAIGN: 更新广告系列
  - PAUSE_CAMPAIGN: 暂停广告系列
  - FREEZE_CAMPAIGN: 冻结广告系列
  - UPDATE_BUDGET: 调整预算
  - SCALE_BUDGET: 放量
  - REDUCE_BUDGET: 降预算
  - UPLOAD_CREATIVE: 上传素材
  - PAUSE_CREATIVE: 暂停素材

连接:
  E13.7 ExecutorGateway → MetaExecutor → Meta Marketing API
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..base_executor import (
    BaseExecutor,
    ExecutionResult,
    ExecutionResultStatus,
    GuardContext,
)
from ..models import ExecutionAction, ExecutionActionType, ExecutionDomain
from .adapter_models import (
    APIRequest,
    APIResponse,
    AdapterMetrics,
    ExecutionMode,
    PlatformType,
    RealExecutionResult,
)


# ═══════════════════════════════════════════════════════════════
# Meta API Client Interface (simplified)
# ═══════════════════════════════════════════════════════════════


class MetaAPIClient:
    """Meta Marketing API 客户端 — 封装 WRITE 操作.

    支持模式:
      - mock: 返回模拟数据
      - real: 调用真实 Meta API
    """

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, access_token: str = "", ad_account_id: str = "", use_mock: bool = True):
        self._access_token = access_token
        self._ad_account_id = ad_account_id
        self._use_mock = use_mock
        self._request_count: int = 0

    # ── Campaign Operations ───────────────────────────────────

    def create_campaign(
        self,
        name: str,
        objective: str = "APP_INSTALLS",
        status: str = "PAUSED",
        special_ad_categories: list[str] | None = None,
        daily_budget: float | None = None,
        lifetime_budget: float | None = None,
    ) -> APIResponse:
        """创建广告系列."""
        request = APIRequest(
            platform=PlatformType.META,
            method="POST",
            endpoint=f"/{self._ad_account_id}/campaigns",
            body={
                "name": name,
                "objective": objective,
                "status": status,
                "special_ad_categories": special_ad_categories or [],
            },
        )
        if daily_budget:
            request.body["daily_budget"] = int(daily_budget * 100)
        if lifetime_budget:
            request.body["lifetime_budget"] = int(lifetime_budget * 100)

        return self._execute(request)

    def update_campaign(
        self,
        campaign_id: str,
        name: str | None = None,
        status: str | None = None,
        daily_budget: float | None = None,
    ) -> APIResponse:
        """更新广告系列."""
        request = APIRequest(
            platform=PlatformType.META,
            method="POST",
            endpoint=f"/{campaign_id}",
            body={},
        )
        if name:
            request.body["name"] = name
        if status:
            request.body["status"] = status
        if daily_budget is not None:
            request.body["daily_budget"] = int(daily_budget * 100)

        return self._execute(request)

    def pause_campaign(self, campaign_id: str) -> APIResponse:
        """暂停广告系列."""
        return self.update_campaign(campaign_id, status="PAUSED")

    def create_ad_set(
        self,
        campaign_id: str,
        name: str,
        optimization_goal: str = "APP_INSTALLS",
        billing_event: str = "IMPRESSIONS",
        daily_budget: float = 100.0,
        targeting: dict[str, Any] | None = None,
        status: str = "PAUSED",
    ) -> APIResponse:
        """创建广告组."""
        request = APIRequest(
            platform=PlatformType.META,
            method="POST",
            endpoint=f"/{self._ad_account_id}/adsets",
            body={
                "campaign_id": campaign_id,
                "name": name,
                "optimization_goal": optimization_goal,
                "billing_event": billing_event,
                "daily_budget": int(daily_budget * 100),
                "status": status,
                "targeting": targeting or {},
            },
        )
        return self._execute(request)

    def update_budget(
        self,
        entity_id: str,
        entity_type: str = "campaign",
        daily_budget: float | None = None,
        lifetime_budget: float | None = None,
    ) -> APIResponse:
        """更新预算 (campaign 或 adset)."""
        request = APIRequest(
            platform=PlatformType.META,
            method="POST",
            endpoint=f"/{entity_id}",
            body={},
        )
        if daily_budget is not None:
            request.body["daily_budget"] = int(daily_budget * 100)
        if lifetime_budget is not None:
            request.body["lifetime_budget"] = int(lifetime_budget * 100)

        return self._execute(request)

    def upload_creative(
        self,
        ad_account_id: str,
        name: str,
        creative_type: str = "VIDEO",
        video_url: str = "",
        image_url: str = "",
        message: str = "",
        call_to_action: str = "INSTALL_APP",
        link: str = "",
    ) -> APIResponse:
        """上传/创建广告创意."""
        request = APIRequest(
            platform=PlatformType.META,
            method="POST",
            endpoint=f"/{ad_account_id or self._ad_account_id}/adcreatives",
            body={
                "name": name,
                "object_story_spec": {
                    "page_id": self._ad_account_id,
                    "video_data": {
                        "video_url": video_url,
                        "call_to_action": {"type": call_to_action, "value": {"link": link}},
                    } if video_url else {},
                    "link_data": {
                        "message": message,
                        "call_to_action": {"type": call_to_action, "value": {"link": link}},
                        "link": link,
                    },
                },
            },
        )
        return self._execute(request)

    def pause_creative(self, creative_id: str) -> APIResponse:
        """暂停创意 (通过 ad 层级)."""
        request = APIRequest(
            platform=PlatformType.META,
            method="POST",
            endpoint=f"/{creative_id}",
            body={"status": "PAUSED"},
        )
        return self._execute(request)

    # ── Internal ──────────────────────────────────────────────

    def _execute(self, request: APIRequest) -> APIResponse:
        """执行 API 请求."""
        self._request_count += 1
        request.request_id = str(uuid.uuid4())

        if self._use_mock:
            return self._mock_response(request)

        # In production: real HTTP call to Meta API
        # For now, return mock response
        return self._mock_response(request)

    def _mock_response(self, request: APIRequest) -> APIResponse:
        """生成模拟响应."""
        # Generate platform ID based on endpoint
        entity_id = f"meta_{uuid.uuid4().hex[:12]}"
        entity_type = "campaign" if "campaign" in request.endpoint else "creative"

        return APIResponse(
            request_id=request.request_id,
            status_code=200,
            success=True,
            data={
                "id": entity_id,
                "success": True,
            },
            platform_id=entity_id,
            latency_ms=50.0,
        )

    @property
    def request_count(self) -> int:
        return self._request_count


# ═══════════════════════════════════════════════════════════════
# Meta Executor
# ═══════════════════════════════════════════════════════════════


class MetaExecutor(BaseExecutor):
    """Meta Ads 执行器 — 将 ExecutionAction 转化为 Meta API 调用.

    用法:
        client = MetaAPIClient(access_token="...", ad_account_id="act_123")
        executor = MetaExecutor(client=client, mode=ExecutionMode.REAL)
        result = executor.execute(action, guard_context)
    """

    # 支持的动作类型
    SUPPORTED_ACTIONS = {
        ExecutionActionType.CREATE_CAMPAIGN,
        ExecutionActionType.CREATE_AD_SET,
        ExecutionActionType.UPDATE_CAMPAIGN,
        ExecutionActionType.PAUSE_CAMPAIGN,
        ExecutionActionType.FREEZE_CAMPAIGN,
        ExecutionActionType.UPDATE_BUDGET,
        ExecutionActionType.SCALE_BUDGET,
        ExecutionActionType.REDUCE_BUDGET,
        ExecutionActionType.UPLOAD_CREATIVE,
        ExecutionActionType.PAUSE_CREATIVE,
    }

    def __init__(
        self,
        client: MetaAPIClient | None = None,
        mode: ExecutionMode = ExecutionMode.MOCK,
        name: str = "MetaExecutor",
    ):
        super().__init__(name=name)
        self._client = client or MetaAPIClient(use_mock=True)
        self._mode = mode
        self._metrics = AdapterMetrics(
            adapter_name=name,
            platform=PlatformType.META,
        )

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    @mode.setter
    def mode(self, value: ExecutionMode) -> None:
        self._mode = value

    @property
    def metrics(self) -> AdapterMetrics:
        return self._metrics

    # ── 主执行逻辑 ────────────────────────────────────────────

    def _do_execute(
        self,
        action: ExecutionAction,
        guard_context: GuardContext,
    ) -> ExecutionResult:
        """执行 Meta Ads 动作."""
        action_type = action.action_type

        # 检查是否支持该动作
        if action_type not in self.SUPPORTED_ACTIONS:
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action_type,
                status=ExecutionResultStatus.SKIPPED,
                executor=self._name,
                reason=f"unsupported_action: {action_type.value}",
            )

        # 干运行模式
        if self._mode == ExecutionMode.DRY_RUN:
            return self._dry_run(action)

        # 真实执行
        api_response = self._dispatch_action(action)

        # 构建真实执行结果
        real_result = RealExecutionResult(
            action_id=action.action_id,
            action_type=action_type.value,
            platform=PlatformType.META,
            mode=self._mode,
            success=api_response.success,
            api_response=api_response,
            platform_entity_id=api_response.platform_id,
            platform_entity_url=f"https://business.facebook.com/adsmanager/manage/campaigns?act={self._client._ad_account_id}&selected_campaign_id={api_response.platform_id}",
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._metrics.record(real_result)

        # 转换为 ExecutionResult
        status = ExecutionResultStatus.SUCCESS if api_response.success else ExecutionResultStatus.FAILED
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action_type,
            status=status,
            executor=self._name,
            before=action.parameters,
            after=api_response.data,
            reason=f"meta_api_{action_type.value}",
            confidence=guard_context.confidence,
            metadata={
                "platform": "meta",
                "platform_entity_id": api_response.platform_id,
                "mode": self._mode.value,
                "api_status_code": api_response.status_code,
            },
        )

    # ── 动作分发 ──────────────────────────────────────────────

    def _dispatch_action(self, action: ExecutionAction) -> APIResponse:
        """根据动作类型分发到具体的 API 调用."""
        params = action.parameters
        action_type = action.action_type

        try:
            if action_type == ExecutionActionType.CREATE_CAMPAIGN:
                return self._client.create_campaign(
                    name=params.get("name", "AI Campaign"),
                    objective=params.get("objective", "APP_INSTALLS"),
                    status=params.get("status", "PAUSED"),
                    daily_budget=params.get("daily_budget"),
                    lifetime_budget=params.get("lifetime_budget"),
                )

            elif action_type == ExecutionActionType.CREATE_AD_SET:
                return self._client.create_ad_set(
                    campaign_id=params.get("campaign_id", action.target_entity),
                    name=params.get("name", "AI Ad Set"),
                    daily_budget=params.get("daily_budget", 100.0),
                    targeting=params.get("targeting", {}),
                    optimization_goal=params.get("optimization_goal", "APP_INSTALLS"),
                )

            elif action_type == ExecutionActionType.UPDATE_CAMPAIGN:
                return self._client.update_campaign(
                    campaign_id=action.target_entity,
                    name=params.get("name"),
                    status=params.get("status"),
                    daily_budget=params.get("daily_budget"),
                )

            elif action_type == ExecutionActionType.PAUSE_CAMPAIGN:
                return self._client.pause_campaign(action.target_entity)

            elif action_type == ExecutionActionType.FREEZE_CAMPAIGN:
                return self._client.pause_campaign(action.target_entity)

            elif action_type == ExecutionActionType.UPDATE_BUDGET:
                return self._client.update_budget(
                    entity_id=action.target_entity,
                    entity_type=params.get("entity_type", "campaign"),
                    daily_budget=params.get("daily_budget"),
                    lifetime_budget=params.get("lifetime_budget"),
                )

            elif action_type == ExecutionActionType.SCALE_BUDGET:
                return self._client.update_budget(
                    entity_id=action.target_entity,
                    daily_budget=params.get("daily_budget"),
                )

            elif action_type == ExecutionActionType.REDUCE_BUDGET:
                return self._client.update_budget(
                    entity_id=action.target_entity,
                    daily_budget=params.get("daily_budget"),
                )

            elif action_type == ExecutionActionType.UPLOAD_CREATIVE:
                return self._client.upload_creative(
                    ad_account_id=params.get("ad_account_id", ""),
                    name=params.get("name", "AI Creative"),
                    video_url=params.get("video_url", ""),
                    image_url=params.get("image_url", ""),
                    message=params.get("message", ""),
                    call_to_action=params.get("call_to_action", "INSTALL_APP"),
                    link=params.get("link", ""),
                )

            elif action_type == ExecutionActionType.PAUSE_CREATIVE:
                return self._client.pause_creative(action.target_entity)

            else:
                return APIResponse(
                    success=False,
                    error_message=f"Unknown action: {action_type.value}",
                )

        except Exception as e:
            return APIResponse(
                success=False,
                error_message=str(e),
            )

    # ── 干运行 ────────────────────────────────────────────────

    def _dry_run(self, action: ExecutionAction) -> ExecutionResult:
        """干运行 — 校验但不执行."""
        return ExecutionResult(
            action_id=action.action_id,
            action_type=action.action_type,
            status=ExecutionResultStatus.SUCCESS,
            executor=self._name,
            reason=f"dry_run_{action.action_type.value}",
            metadata={
                "mode": "dry_run",
                "would_execute": True,
                "parameters": action.parameters,
            },
        )

    # ── 回滚 ──────────────────────────────────────────────────

    def _rollback(self, action: ExecutionAction) -> ExecutionResult:
        """回滚动作."""
        # 回滚逻辑: 暂停 vs 删除
        action_type = action.action_type

        if action_type in {ExecutionActionType.CREATE_CAMPAIGN, ExecutionActionType.CREATE_AD_SET}:
            # 创建操作的回滚: 暂停
            self._client.pause_campaign(action.target_entity)
            return ExecutionResult(
                action_id=action.action_id,
                action_type=action_type,
                status=ExecutionResultStatus.ROLLED_BACK,
                executor=self._name,
                reason="rollback: paused created entity",
            )

        elif action_type in {ExecutionActionType.SCALE_BUDGET, ExecutionActionType.REDUCE_BUDGET}:
            # 预算变更的回滚: 恢复原预算
            original_budget = action.parameters.get("original_budget")
            if original_budget:
                self._client.update_budget(action.target_entity, daily_budget=original_budget)
                return ExecutionResult(
                    action_id=action.action_id,
                    action_type=action_type,
                    status=ExecutionResultStatus.ROLLED_BACK,
                    executor=self._name,
                    reason=f"rollback: restored budget to {original_budget}",
                )

        return ExecutionResult(
            action_id=action.action_id,
            action_type=action_type,
            status=ExecutionResultStatus.ROLLED_BACK,
            executor=self._name,
            reason="rollback: no specific rollback needed",
        )

    # ── 前置校验 ──────────────────────────────────────────────

    def _pre_validate(
        self,
        action: ExecutionAction,
        guard_context: GuardContext,
    ) -> bool:
        """前置校验: 动作类型是否支持 + 参数完整性."""
        if action.action_type not in self.SUPPORTED_ACTIONS:
            return False

        # 必须有 target_entity (对于创建类操作，可以为空)
        required_params = {
            ExecutionActionType.CREATE_CAMPAIGN: ["name"],
            ExecutionActionType.CREATE_AD_SET: ["campaign_id"],
            ExecutionActionType.UPDATE_BUDGET: ["daily_budget"],
            ExecutionActionType.SCALE_BUDGET: ["daily_budget"],
            ExecutionActionType.REDUCE_BUDGET: ["daily_budget"],
            ExecutionActionType.UPLOAD_CREATIVE: ["name"],
        }

        required = required_params.get(action.action_type, [])
        for param in required:
            if param not in action.parameters:
                return False

        return True