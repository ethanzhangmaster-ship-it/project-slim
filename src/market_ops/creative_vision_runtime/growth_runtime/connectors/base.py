"""E13.1.1 Base Connector — 所有外部数据连接器的抽象基类."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from .models import (
    CampaignMetrics,
    ConnectorConfig,
    ConnectorHealth,
    ConnectorInfo,
    ConnectorStatus,
    CreativeMetrics,
    DataSource,
    GameplayMetrics,
    GrowthDataEvent,
    RetentionCurve,
    UserRevenueCurve,
)


class BaseConnector(ABC):
    """所有外部数据连接器的抽象基类.

    子类必须实现:
      - _do_connect():       建立连接
      - _do_disconnect():    断开连接
      - _do_health_check():  健康检查
      - _do_authenticate():  认证

    子类按需实现:
      - fetch_campaigns():      拉取 Campaign 数据
      - fetch_adsets():         拉取 AdSet 数据
      - fetch_creatives():      拉取 Creative 数据
      - fetch_revenue_curve():  拉取收入曲线
      - fetch_retention():      拉取留存数据
      - fetch_gameplay():       拉取游戏数据
    """

    def __init__(self, config: ConnectorConfig):
        self._config = config
        self._info = ConnectorInfo(
            name=self.__class__.__name__,
            source=config.connector_type,
        )

        self._connected: bool = False
        self._authenticated: bool = False
        self._last_request_time: float = 0.0

    # ── Properties ────────────────────────────────────────────

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    @property
    def info(self) -> ConnectorInfo:
        return self._info

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    def name(self) -> str:
        return self._info.name

    @property
    def source(self) -> DataSource:
        return self._config.connector_type

    # ── Lifecycle ─────────────────────────────────────────────

    def connect(self) -> bool:
        """建立连接."""
        self._info.status = ConnectorStatus.INITIALIZING
        try:
            self._do_connect()
            self._connected = True
            self._info.status = ConnectorStatus.CONNECTED
            self._info.last_success_at = datetime.now(timezone.utc).isoformat()
            return True
        except Exception as e:
            self._info.status = ConnectorStatus.ERROR
            self._info.last_error_message = str(e)
            self._info.last_error_at = datetime.now(timezone.utc).isoformat()
            return False

    def disconnect(self) -> None:
        """断开连接."""
        self._do_disconnect()
        self._connected = False
        self._authenticated = False
        self._info.status = ConnectorStatus.DISCONNECTED

    def authenticate(self) -> bool:
        """认证."""
        if not self._connected:
            return False
        try:
            self._do_authenticate()
            self._authenticated = True
            return True
        except Exception:
            self._info.status = ConnectorStatus.AUTH_EXPIRED
            return False

    def health_check(self) -> ConnectorHealth:
        """健康检查."""
        if not self._connected:
            self._info.health = ConnectorHealth.UNHEALTHY
            return ConnectorHealth.UNHEALTHY

        try:
            health = self._do_health_check()
            self._info.health = health
            return health
        except Exception:
            self._info.health = ConnectorHealth.UNHEALTHY
            return ConnectorHealth.UNHEALTHY

    # ── Abstract Methods ──────────────────────────────────────

    @abstractmethod
    def _do_connect(self) -> None:
        """子类实现: 建立连接."""
        ...

    @abstractmethod
    def _do_disconnect(self) -> None:
        """子类实现: 断开连接."""
        ...

    @abstractmethod
    def _do_authenticate(self) -> None:
        """子类实现: 认证."""
        ...

    @abstractmethod
    def _do_health_check(self) -> ConnectorHealth:
        """子类实现: 健康检查."""
        ...

    # ── Data Fetching (Optional Override) ─────────────────────

    def fetch_campaigns(
        self, product_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[CampaignMetrics]:
        """拉取 Campaign 数据."""
        return []

    def fetch_adsets(
        self, campaign_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[dict[str, Any]]:
        """拉取 AdSet 数据."""
        return []

    def fetch_creatives(
        self, adset_id: str = "", date_from: str = "", date_to: str = "",
    ) -> list[CreativeMetrics]:
        """拉取 Creative 数据."""
        return []

    def fetch_revenue_curve(
        self, product_id: str = "", cohort_date: str = "",
    ) -> UserRevenueCurve | None:
        """拉取用户收入曲线."""
        return None

    def fetch_retention(
        self, product_id: str = "", cohort_date: str = "",
    ) -> RetentionCurve | None:
        """拉取留存数据."""
        return None

    def fetch_gameplay(
        self, product_id: str = "", date: str = "",
    ) -> GameplayMetrics | None:
        """拉取游戏数据."""
        return None

    # ── Rate Limiting ─────────────────────────────────────────

    def _check_rate_limit(self) -> bool:
        """检查是否超过速率限制."""
        now = time.time()

        # Reset counters if minute/hour has passed
        if now - self._last_request_time >= 60.0:
            self._info.requests_this_minute = 0
        if now - self._last_request_time >= 3600.0:
            self._info.requests_this_hour = 0

        if self._info.requests_this_minute >= self._config.max_requests_per_minute:
            self._info.is_rate_limited = True
            self._info.status = ConnectorStatus.RATE_LIMITED
            return False

        if self._info.requests_this_hour >= self._config.max_requests_per_hour:
            self._info.is_rate_limited = True
            self._info.status = ConnectorStatus.RATE_LIMITED
            return False

        self._info.is_rate_limited = False
        return True

    def _record_request(self, success: bool = True) -> None:
        """记录请求."""
        self._last_request_time = time.time()
        self._info.total_requests += 1
        self._info.requests_this_minute += 1
        self._info.requests_this_hour += 1

        if success:
            self._info.successful_requests += 1
            self._info.last_success_at = datetime.now(timezone.utc).isoformat()
        else:
            self._info.failed_requests += 1
            self._info.last_error_at = datetime.now(timezone.utc).isoformat()

    # ── Retry ─────────────────────────────────────────────────

    def _retry(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """带重试的执行."""
        last_error: Exception | None = None
        for attempt in range(self._config.retry_max_attempts):
            try:
                result = func(*args, **kwargs)
                self._record_request(success=True)
                return result
            except Exception as e:
                last_error = e
                self._record_request(success=False)
                if attempt < self._config.retry_max_attempts - 1:
                    backoff = self._config.retry_backoff_seconds * (2 ** attempt)
                    time.sleep(backoff)

        raise last_error or RuntimeError("Retry failed")

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            **self._info.to_dict(),
            "config": self._config.to_dict(),
            "connected": self._connected,
            "authenticated": self._authenticated,
        }