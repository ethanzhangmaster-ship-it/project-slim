"""凭证 Token 过期监控 — Spec production_roadmap.md O5.

监控所有外部服务 Token 的过期状态, 提前告警, 避免线上服务因 Token 过期而中断.

支持的 Token 类型:
  1. **Meta Access Token** — 通过 Graph API `/debug_token` 实时查询过期时间
  2. **手动注册的 Token** — 通过 `register_token()` 注册 (token_id + expires_at)
     用于 OAuth token / Service Account JWT 等无法实时查询的 token

告警阈值:
  - critical: 距过期 < 1 天 (86400 秒)
  - warning:  距过期 < 7 天 (604800 秒)
  - info:     距过期 < 30 天 (2592000 秒) — 仅记录日志

告警集成:
  - 生成的告警兼容 SystemMonitor.get_alerts() 格式
  - 可通过 AlertNotifier 推送到邮件/企微/飞书
  - 持久化到 data/token_monitor/status.json

用法:
    from .token_monitor import get_token_monitor

    monitor = get_token_monitor()
    monitor.check_meta_token(access_token="...", app_id="...", app_secret="...")
    monitor.register_token("google_play_oauth", expires_at=1234567890)
    alerts = monitor.get_alerts()
    status = monitor.get_status()
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 告警阈值 (秒) ──────────────────────────────────────────────

CRITICAL_THRESHOLD_SECONDS = 86400       # 1 天
WARNING_THRESHOLD_SECONDS = 604800        # 7 天
INFO_THRESHOLD_SECONDS = 2592000          # 30 天 (仅日志)

# Meta Graph API debug_token 端点
META_DEBUG_TOKEN_URL = "https://graph.facebook.com/{version}/debug_token"

# Token 类型
TOKEN_TYPE_META = "meta_access_token"
TOKEN_TYPE_GOOGLE_PLAY = "google_play_oauth"
TOKEN_TYPE_APPLE = "apple_jwt"
TOKEN_TYPE_CUSTOM = "custom"


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class TokenStatus:
    """单个 Token 的状态快照."""
    token_id: str                       # 唯一标识 (e.g. "meta_access_token")
    token_type: str                     # TOKEN_TYPE_*
    is_valid: bool                      # token 是否有效
    expires_at: float                   # Unix timestamp (0 = 永不过期)
    checked_at: str                     # ISO8601 最后检查时间
    source: str = ""                    # 来源 (e.g. "graph_api_debug_token")
    error: str = ""                     # 检查失败原因
    scopes: List[str] = field(default_factory=list)  # Meta token scopes
    app_id: str = ""                    # Meta app_id
    token_preview: str = ""             # token 前 8 字符 (用于识别, 不暴露完整值)

    @property
    def expires_in_seconds(self) -> float:
        """距过期的秒数 (负数 = 已过期)."""
        if self.expires_at <= 0:
            return float("inf")  # 永不过期
        return self.expires_at - time.time()

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and self.expires_in_seconds <= 0

    @property
    def is_never_expiring(self) -> bool:
        return self.expires_at <= 0

    @property
    def severity(self) -> str:
        """根据剩余时间返回严重级别."""
        if not self.is_valid:
            return "critical"
        if self.is_never_expiring:
            return "info"
        remaining = self.expires_in_seconds
        if remaining <= 0:
            return "critical"
        if remaining <= CRITICAL_THRESHOLD_SECONDS:
            return "critical"
        if remaining <= WARNING_THRESHOLD_SECONDS:
            return "warning"
        if remaining <= INFO_THRESHOLD_SECONDS:
            return "info"
        return "info"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["expires_in_seconds"] = (
            None if self.is_never_expiring else self.expires_in_seconds
        )
        d["is_expired"] = self.is_expired
        d["severity"] = self.severity
        return d


# ── 监控器 ────────────────────────────────────────────────────


class TokenMonitor:
    """Token 过期监控器.

    职责:
      1. 实时查询 Meta Access Token 过期时间 (Graph API debug_token)
      2. 手动注册其他 Token 的过期时间 (Google Play OAuth / Apple JWT 等)
      3. 生成告警 (兼容 SystemMonitor.get_alerts() 格式)
      4. 持久化状态到 data/token_monitor/status.json
    """

    def __init__(self, data_dir: str = "data/token_monitor") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._status_file = self.data_dir / "status.json"
        self._lock = threading.Lock()
        self._tokens: Dict[str, TokenStatus] = {}
        self._load_persisted_status()

    # ── 状态持久化 ──

    def _load_persisted_status(self) -> None:
        """从磁盘加载历史 token 状态."""
        if not self._status_file.exists():
            return
        try:
            data = json.loads(self._status_file.read_text(encoding="utf-8"))
            for token_id, tdict in data.items():
                # 兼容旧数据: 缺少字段用默认值
                tdict.setdefault("scopes", [])
                tdict.setdefault("app_id", "")
                tdict.setdefault("token_preview", "")
                tdict.setdefault("source", "")
                tdict.setdefault("error", "")
                try:
                    self._tokens[token_id] = TokenStatus(**tdict)
                except TypeError:
                    logger.warning("token_monitor: skipping malformed entry %s", token_id)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("token_monitor: failed to load status: %s", exc)

    def _persist_status(self) -> None:
        """持久化 token 状态到磁盘."""
        try:
            data = {
                tid: {k: v for k, v in t.to_dict().items()
                      if k not in ("expires_in_seconds", "is_expired", "severity")}
                for tid, t in self._tokens.items()
            }
            self._status_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("token_monitor: failed to persist status: %s", exc)

    # ── Meta Token 实时检查 ──

    def check_meta_token(
        self,
        access_token: str,
        app_id: str = "",
        app_secret: str = "",
        api_version: str = "v22.0",
        token_id: str = TOKEN_TYPE_META,
    ) -> TokenStatus:
        """通过 Graph API debug_token 检查 Meta Access Token 过期时间.

        Args:
            access_token: 要检查的 Meta access token
            app_id: Meta App ID (可选, 用于构造 app access token)
            app_secret: Meta App Secret (可选)
            api_version: Graph API 版本
            token_id: 内部 token 标识

        Returns:
            TokenStatus 检查结果
        """
        # token 预览 (前 8 字符) 用于识别, 不暴露完整值
        token_preview = access_token[:8] + "..." if len(access_token) > 8 else "***"
        now_iso = datetime.now(timezone.utc).isoformat()

        if not access_token:
            status = TokenStatus(
                token_id=token_id,
                token_type=TOKEN_TYPE_META,
                is_valid=False,
                expires_at=0,
                checked_at=now_iso,
                source="graph_api_debug_token",
                error="access_token is empty",
                token_preview=token_preview,
            )
            with self._lock:
                self._tokens[token_id] = status
                self._persist_status()
            return status

        # 构造 debug_token 请求
        # access_token 参数可以用: app_id|app_secret (app token) 或 token 自身
        if app_id and app_secret:
            app_access_token = f"{app_id}|{app_secret}"
        else:
            app_access_token = access_token  # 自查模式

        url = META_DEBUG_TOKEN_URL.format(version=api_version)
        params = {
            "input_token": access_token,
            "access_token": app_access_token,
        }

        try:
            import requests
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            token_data = data.get("data", {})

            is_valid = bool(token_data.get("is_valid", False))
            expires_at = int(token_data.get("expires_at", 0) or 0)
            scopes = token_data.get("scopes", []) or []
            returned_app_id = token_data.get("app_id", "")

            error = ""
            if not is_valid:
                error = token_data.get("error", {}).get("message", "token invalid")

            status = TokenStatus(
                token_id=token_id,
                token_type=TOKEN_TYPE_META,
                is_valid=is_valid,
                expires_at=float(expires_at),
                checked_at=now_iso,
                source="graph_api_debug_token",
                error=error,
                scopes=list(scopes),
                app_id=returned_app_id,
                token_preview=token_preview,
            )
            logger.info(
                "token_monitor: Meta token checked, valid=%s, expires_at=%s",
                is_valid, expires_at,
            )
        except Exception as exc:
            status = TokenStatus(
                token_id=token_id,
                token_type=TOKEN_TYPE_META,
                is_valid=False,
                expires_at=0,
                checked_at=now_iso,
                source="graph_api_debug_token",
                error=f"check failed: {exc}",
                token_preview=token_preview,
            )
            logger.warning("token_monitor: Meta token check failed: %s", exc)

        with self._lock:
            self._tokens[token_id] = status
            self._persist_status()
        return status

    # ── 手动注册 Token ──

    def register_token(
        self,
        token_id: str,
        expires_at: float,
        token_type: str = TOKEN_TYPE_CUSTOM,
        is_valid: bool = True,
        source: str = "manual",
        token_preview: str = "",
        error: str = "",
    ) -> TokenStatus:
        """手动注册一个 Token 的过期时间.

        用于 OAuth token / Service Account JWT 等无法实时查询的 token.
        调用方需在获取 token 时记录 expires_at (Unix timestamp).

        Args:
            token_id: 唯一标识
            expires_at: 过期 Unix timestamp (0 = 永不过期)
            token_type: TOKEN_TYPE_* 常量
            is_valid: token 当前是否有效
            source: 来源标记
            token_preview: token 前 8 字符 (可选)
            error: 错误信息 (可选)

        Returns:
            注册后的 TokenStatus
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        status = TokenStatus(
            token_id=token_id,
            token_type=token_type,
            is_valid=is_valid,
            expires_at=float(expires_at),
            checked_at=now_iso,
            source=source,
            error=error,
            token_preview=token_preview,
        )
        with self._lock:
            self._tokens[token_id] = status
            self._persist_status()
        logger.info(
            "token_monitor: registered token %s, expires_at=%s",
            token_id, expires_at,
        )
        return status

    def unregister_token(self, token_id: str) -> bool:
        """移除已注册的 Token."""
        with self._lock:
            if token_id in self._tokens:
                del self._tokens[token_id]
                self._persist_status()
                return True
            return False

    # ── 状态查询 ──

    def get_token_status(self, token_id: str) -> Optional[TokenStatus]:
        """查询单个 Token 状态."""
        with self._lock:
            return self._tokens.get(token_id)

    def get_all_tokens(self) -> List[TokenStatus]:
        """列出所有 Token 状态."""
        with self._lock:
            return list(self._tokens.values())

    def get_status(self) -> Dict[str, Any]:
        """获取整体监控状态摘要 (供 Dashboard / API)."""
        with self._lock:
            tokens = list(self._tokens.values())

        critical_count = sum(1 for t in tokens if t.severity == "critical")
        warning_count = sum(1 for t in tokens if t.severity == "warning")
        expired_count = sum(1 for t in tokens if t.is_expired)

        if critical_count > 0:
            status = "critical"
        elif warning_count > 0:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tokens": len(tokens),
            "expired_count": expired_count,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "thresholds": {
                "critical_seconds": CRITICAL_THRESHOLD_SECONDS,
                "warning_seconds": WARNING_THRESHOLD_SECONDS,
                "info_seconds": INFO_THRESHOLD_SECONDS,
            },
            "tokens": [t.to_dict() for t in tokens],
        }

    # ── 告警生成 ──

    def get_alerts(self) -> List[Dict[str, Any]]:
        """生成告警列表 (兼容 SystemMonitor.get_alerts() 格式).

        Returns:
            [{"alert_id", "severity", "message", "current_value",
              "threshold", "category", "timestamp"}, ...]
        """
        with self._lock:
            tokens = list(self._tokens.values())

        alerts: List[Dict[str, Any]] = []
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        for t in tokens:
            if t.is_never_expiring and t.is_valid:
                continue  # 永不过期的有效 token 不告警

            severity = t.severity
            if severity == "info" and t.is_valid and not t.is_expired:
                # info 级别仅在距过期 < 30 天时记录, 但不作为告警返回
                # (与 AlertNotifier 的 SEVERITY_PUSH_MAP 一致: info 不推送)
                continue

            if t.is_expired:
                message = f"Token '{t.token_id}' 已过期 (类型: {t.token_type})"
                current_value = "expired"
            elif not t.is_valid:
                message = f"Token '{t.token_id}' 无效 (类型: {t.token_type}, 错误: {t.error})"
                current_value = "invalid"
            else:
                remaining_days = t.expires_in_seconds / 86400.0
                if severity == "critical":
                    message = (
                        f"Token '{t.token_id}' 即将过期: 剩余 {remaining_days:.1f} 天 "
                        f"(类型: {t.token_type})"
                    )
                else:  # warning
                    message = (
                        f"Token '{t.token_id}' 即将过期: 剩余 {remaining_days:.1f} 天 "
                        f"(类型: {t.token_type})"
                    )
                current_value = f"{remaining_days:.1f} days"

            threshold = (
                f"{CRITICAL_THRESHOLD_SECONDS / 86400:.0f} days"
                if severity == "critical"
                else f"{WARNING_THRESHOLD_SECONDS / 86400:.0f} days"
            )

            alerts.append({
                "alert_id": f"token_expiry_{t.token_id}",
                "severity": severity,
                "message": message,
                "current_value": current_value,
                "threshold": threshold,
                "category": "token_expiry",
                "token_id": t.token_id,
                "token_type": t.token_type,
                "expires_at": t.expires_at,
                "checked_at": t.checked_at,
                "timestamp": now_iso,
            })

        return alerts

    # ── 便捷方法: 从环境变量自动检查 Meta token ──

    def check_meta_token_from_env(self) -> Optional[TokenStatus]:
        """从环境变量读取 Meta token 并检查.

        环境变量:
          - META_ACCESS_TOKEN (必需)
          - META_APP_ID (可选)
          - META_APP_SECRET (可选)
          - META_API_VERSION (可选, 默认 v22.0)

        Returns:
            TokenStatus, 若未配置 META_ACCESS_TOKEN 则返回 None
        """
        access_token = os.getenv("META_ACCESS_TOKEN", "")
        if not access_token:
            return None
        app_id = os.getenv("META_APP_ID", "")
        app_secret = os.getenv("META_APP_SECRET", "")
        api_version = os.getenv("META_API_VERSION", "v22.0")
        return self.check_meta_token(
            access_token=access_token,
            app_id=app_id,
            app_secret=app_secret,
            api_version=api_version,
        )

    # ── 便捷方法: 检查所有可自动检查的 token ──

    def check_all_auto_tokens(self) -> List[TokenStatus]:
        """检查所有可自动检查的 token (目前仅 Meta)."""
        results: List[TokenStatus] = []
        meta_status = self.check_meta_token_from_env()
        if meta_status is not None:
            results.append(meta_status)
        return results


# ── 模块级单例 ──────────────────────────────────────────────


_default_monitor: Optional[TokenMonitor] = None
_default_monitor_lock = threading.Lock()


def get_token_monitor(data_dir: str = "") -> TokenMonitor:
    """获取默认的 TokenMonitor 单例.

    首次调用时会推断项目根目录并使用 data/token_monitor 作为持久化目录.
    传入 data_dir 可覆盖 (主要用于测试).
    """
    global _default_monitor
    with _default_monitor_lock:
        if _default_monitor is None or data_dir:
            if not data_dir:
                # 推断项目根目录
                cwd = Path.cwd()
                root = cwd
                for parent in [cwd] + list(cwd.parents):
                    if (parent / "src" / "market_ops").exists():
                        root = parent
                        break
                data_dir = str(root / "data" / "token_monitor")
            _default_monitor = TokenMonitor(data_dir=data_dir)
        return _default_monitor


def reset_token_monitor() -> None:
    """重置单例 (主要用于测试)."""
    global _default_monitor
    with _default_monitor_lock:
        _default_monitor = None


__all__ = [
    "TokenMonitor",
    "TokenStatus",
    "get_token_monitor",
    "reset_token_monitor",
    "TOKEN_TYPE_META",
    "TOKEN_TYPE_GOOGLE_PLAY",
    "TOKEN_TYPE_APPLE",
    "TOKEN_TYPE_CUSTOM",
    "CRITICAL_THRESHOLD_SECONDS",
    "WARNING_THRESHOLD_SECONDS",
    "INFO_THRESHOLD_SECONDS",
]
