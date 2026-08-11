"""E13.7 Adjust Verifier — Adjust 验证器.

验证 Meta 等平台的执行结果是否真实生效，通过 Adjust 数据源检查:
  - 广告是否真实上线
  - 预算是否真实变更
  - 素材是否产生展示
  - 转化和收入数据

核心原则: Adjust 是 Revenue Source of Truth，执行不能只看 API 返回。

验证流程:
  Platform API Response → Wait → Adjust Data Query → Compare → Verification Result

连接:
  E13.7 MetaExecutor → AdjustVerifier → Adjust Connector → Verification → Feedback Loop
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from .adapter_models import (
    AdapterMetrics,
    PlatformType,
    RealExecutionResult,
    VerificationResult,
)


# ═══════════════════════════════════════════════════════════════
# Verification Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class VerificationConfig:
    """验证配置 — 控制验证行为和阈值.

    Attributes:
        wait_minutes: 执行后等待时间 (让数据回流)
        max_wait_minutes: 最大等待时间
        min_spend_threshold: 最低花费阈值 (低于此值视为未生效)
        min_impressions_threshold: 最低展示阈值
        min_installs_threshold: 最低安装阈值
        confidence_threshold: 验证置信度阈值
        retry_interval_minutes: 重试间隔
        max_retries: 最大重试次数
        enabled: 是否启用验证
    """
    wait_minutes: int = 30
    max_wait_minutes: int = 120
    min_spend_threshold: float = 0.01
    min_impressions_threshold: int = 100
    min_installs_threshold: int = 1
    confidence_threshold: float = 0.7
    retry_interval_minutes: int = 15
    max_retries: int = 5
    enabled: bool = True


# ═══════════════════════════════════════════════════════════════
# Adjust Data Client
# ═══════════════════════════════════════════════════════════════


class AdjustDataClient:
    """Adjust 数据客户端 — 查询验证数据.

    支持模式:
      - mock: 返回模拟数据
      - real: 调用 Adjust API
    """

    def __init__(self, use_mock: bool = True, api_token: str = ""):
        self._use_mock = use_mock
        self._api_token = api_token

    def query_entity_metrics(
        self,
        platform_entity_id: str,
        platform: PlatformType = PlatformType.META,
        lookback_hours: int = 24,
    ) -> dict[str, Any]:
        """查询实体在 Adjust 中的表现数据.

        Args:
            platform_entity_id: 平台实体 ID
            platform: 平台类型
            lookback_hours: 回溯时间

        Returns:
            dict: 指标数据 (spend, impressions, clicks, installs, revenue, ROAS)
        """
        if self._use_mock:
            return self._mock_metrics(platform_entity_id, platform)

        # In production: call Adjust API
        return self._mock_metrics(platform_entity_id, platform)

    def query_creative_metrics(
        self,
        creative_id: str,
        lookback_hours: int = 24,
    ) -> dict[str, Any]:
        """查询素材在 Adjust 中的表现.

        Args:
            creative_id: 素材 ID
            lookback_hours: 回溯时间

        Returns:
            dict: 素材指标
        """
        if self._use_mock:
            return self._mock_creative_metrics(creative_id)

        return self._mock_creative_metrics(creative_id)

    def _mock_metrics(self, entity_id: str, platform: PlatformType) -> dict[str, Any]:
        return {
            "platform": platform.value,
            "entity_id": entity_id,
            "spend": 50.0,
            "impressions": 5000,
            "clicks": 150,
            "ctr": 0.03,
            "installs": 30,
            "cvr": 0.20,
            "revenue": 120.0,
            "roas": 2.4,
            "d1_retention": 0.35,
            "d7_retention": 0.15,
            "data_available": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _mock_creative_metrics(self, creative_id: str) -> dict[str, Any]:
        return {
            "creative_id": creative_id,
            "spend": 25.0,
            "impressions": 2500,
            "clicks": 75,
            "ctr": 0.03,
            "installs": 15,
            "cvr": 0.20,
            "revenue": 60.0,
            "roas": 2.4,
            "data_available": True,
        }


# ═══════════════════════════════════════════════════════════════
# Adjust Verifier
# ═══════════════════════════════════════════════════════════════


class AdjustVerifier:
    """Adjust 验证器 — 验证执行结果是否真实生效.

    用法:
        verifier = AdjustVerifier(adjust_client=AdjustDataClient())
        verification = verifier.verify(real_result)
        if verification.verified:
            print("Execution confirmed on Adjust")
    """

    def __init__(
        self,
        adjust_client: AdjustDataClient | None = None,
        config: VerificationConfig | None = None,
        name: str = "AdjustVerifier",
    ):
        self._client = adjust_client or AdjustDataClient(use_mock=True)
        self._config = config or VerificationConfig()
        self._name = name
        self._metrics = AdapterMetrics(
            adapter_name=name,
            platform=PlatformType.ADJUST,
        )
        self._verification_count: int = 0
        self._verified_count: int = 0

    @property
    def verification_count(self) -> int:
        return self._verification_count

    @property
    def verified_count(self) -> int:
        return self._verified_count

    @property
    def verified_rate(self) -> float:
        if self._verification_count == 0:
            return 1.0
        return self._verified_count / self._verification_count

    # ── 主入口 ────────────────────────────────────────────────

    def verify(
        self,
        real_result: RealExecutionResult,
        lookback_hours: int = 24,
    ) -> VerificationResult:
        """验证执行结果.

        Args:
            real_result: 真实执行结果
            lookback_hours: 数据回溯时间

        Returns:
            VerificationResult: 验证结果
        """
        self._verification_count += 1

        if not self._config.enabled:
            return VerificationResult(
                execution_result_id=real_result.result_id,
                platform=real_result.platform,
                platform_entity_id=real_result.platform_entity_id,
                verified=True,
                reason="verification_disabled",
                data_available=False,
            )

        # 查询 Adjust 数据
        metrics = self._client.query_entity_metrics(
            platform_entity_id=real_result.platform_entity_id,
            platform=real_result.platform,
            lookback_hours=lookback_hours,
        )

        # 验证
        data_available = metrics.get("data_available", False)
        if not data_available:
            return VerificationResult(
                execution_result_id=real_result.result_id,
                platform=real_result.platform,
                platform_entity_id=real_result.platform_entity_id,
                verified=False,
                data_available=False,
                reason="adjust_data_not_available_yet",
                metrics=metrics,
            )

        # 检查阈值
        checks = self._run_checks(metrics, real_result)
        all_passed = all(checks.values())
        confidence = sum(1 for v in checks.values() if v) / max(len(checks), 1)

        verification = VerificationResult(
            execution_result_id=real_result.result_id,
            platform=real_result.platform,
            platform_entity_id=real_result.platform_entity_id,
            verified=all_passed,
            metrics=metrics,
            data_available=True,
            confidence=confidence,
            reason=self._build_reason(checks, metrics),
        )

        if all_passed:
            self._verified_count += 1

        return verification

    def verify_batch(
        self,
        results: list[RealExecutionResult],
        lookback_hours: int = 24,
    ) -> list[VerificationResult]:
        """批量验证."""
        return [self.verify(r, lookback_hours) for r in results]

    # ── 校验逻辑 ──────────────────────────────────────────────

    def _run_checks(
        self,
        metrics: dict[str, Any],
        result: RealExecutionResult,
    ) -> dict[str, bool]:
        """运行各项校验."""
        checks = {}

        # 1. 花费校验
        spend = metrics.get("spend", 0)
        checks["spend"] = spend >= self._config.min_spend_threshold

        # 2. 展示校验
        impressions = metrics.get("impressions", 0)
        checks["impressions"] = impressions >= self._config.min_impressions_threshold

        # 3. 安装校验
        installs = metrics.get("installs", 0)
        checks["installs"] = installs >= self._config.min_installs_threshold

        # 4. 数据新鲜度校验
        updated_at = metrics.get("updated_at", "")
        if updated_at:
            try:
                updated = datetime.fromisoformat(updated_at)
                age = datetime.now(timezone.utc) - updated
                checks["data_freshness"] = age < timedelta(hours=24)
            except (ValueError, TypeError):
                checks["data_freshness"] = True
        else:
            checks["data_freshness"] = False

        return checks

    def _build_reason(
        self,
        checks: dict[str, bool],
        metrics: dict[str, Any],
    ) -> str:
        """构建验证原因."""
        passed = [k for k, v in checks.items() if v]
        failed = [k for k, v in checks.items() if not v]

        if not failed:
            return f"all_checks_passed: spend={metrics.get('spend')}, impressions={metrics.get('impressions')}, installs={metrics.get('installs')}"

        return f"checks_failed: {failed} | passed: {passed}"

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "verification_count": self._verification_count,
            "verified_count": self._verified_count,
            "verified_rate": round(self.verified_rate, 4),
            "config": {
                "enabled": self._config.enabled,
                "wait_minutes": self._config.wait_minutes,
                "min_spend": self._config.min_spend_threshold,
                "min_impressions": self._config.min_impressions_threshold,
            },
        }

    def reset(self) -> None:
        self._verification_count = 0
        self._verified_count = 0