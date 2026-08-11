"""告警通知器 — 将 SystemMonitor 检测的告警推送到外部通知渠道.

设计原则:
  - 渠道解耦: 每个渠道 (邮件/企微/飞书) 独立实现, 互不影响
  - 凭证可选: 缺凭证时降级为仅记录日志, 不抛异常
  - 严重级别过滤: 只推送 critical/warning, info 仅记录日志
  - 幂等去重: 同一 alert_id 在时间窗口内只推送一次
  - 异步友好: 提供 sync 和 async 两种调用方式

通知渠道:
  1. 邮件 (SMTP): 支持 SSL/TLS, 可配置收件人列表
  2. 企业微信 Webhook: markdown 格式卡片
  3. 飞书 Webhook: interactive card 格式

凭证来源 (优先级从高到低):
  1. 环境变量 (SMTP_*, WECOM_WEBHOOK, FEISHU_ALERT_WEBHOOK)
  2. credentials/notify.json 文件
  3. 缺失时降级为日志记录

用法:
    from .alert_notifier import get_alert_notifier

    notifier = get_alert_notifier()
    results = notifier.notify_alerts(alerts_list)
    # results: [{"channel": "email", "success": True, "sent": 2}, ...]

    # 或单独发送单条告警
    notifier.notify_single(alert_dict, channels=["wecom", "feishu"])
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 默认配置 ──────────────────────────────────────────────────

# 幂等去重时间窗口 (秒): 同一 alert_id 在此窗口内只推送一次
DEFAULT_DEDUP_WINDOW_SECONDS = 300  # 5 分钟

# 严重级别 → 是否推送
SEVERITY_PUSH_MAP = {
    "critical": True,
    "warning": True,
    "info": False,  # info 仅记录日志, 不推送
}

# 严重级别 → 颜色 (用于飞书/企微卡片)
SEVERITY_COLOR_MAP = {
    "critical": "red",
    "warning": "yellow",
    "info": "blue",
}

# 严重级别 → emoji
SEVERITY_EMOJI_MAP = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
}


@dataclass
class NotifyResult:
    """单渠道通知结果."""
    channel: str  # email | wecom | feishu | log
    success: bool
    sent: int = 0  # 成功发送条数
    error: str = ""


@dataclass
class AlertNotifierConfig:
    """告警通知器配置 — 从环境变量或 credentials 文件加载."""
    # 邮件 (SMTP)
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = True
    email_from: str = ""
    email_to: list[str] = field(default_factory=list)

    # 企业微信 Webhook
    wecom_webhook: str = ""

    # 飞书 Webhook (告警专用, 与 FEISHU_BOT_WEBHOOK 区分)
    feishu_webhook: str = ""

    # 通用
    dedup_window_seconds: int = DEFAULT_DEDUP_WINDOW_SECONDS
    # 启用的渠道列表 (空则自动检测: 有凭证则启用)
    enabled_channels: list[str] = field(default_factory=list)

    def has_email_config(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.email_to)

    def has_wecom_config(self) -> bool:
        return bool(self.wecom_webhook)

    def has_feishu_config(self) -> bool:
        return bool(self.feishu_webhook)


def load_notifier_config(project_root: str | Path | None = None) -> AlertNotifierConfig:
    """从环境变量和 credentials 文件加载配置.

    优先级: 环境变量 > credentials/notify.json > 默认值

    Args:
        project_root: 项目根目录 (用于定位 credentials/); None 则用 cwd
    """
    root = Path(project_root) if project_root else Path.cwd()

    # 1. 先从 credentials/notify.json 读取基础配置
    notify_file = root / "credentials" / "notify.json"
    file_config: dict[str, Any] = {}
    if notify_file.exists():
        try:
            file_config = json.loads(notify_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("alert_notifier: failed to read %s: %s", notify_file, exc)

    def _get(env_key: str, file_key: str, default: str = "") -> str:
        """环境变量优先, 其次文件, 最后默认值."""
        val = os.environ.get(env_key, "")
        if val:
            return val
        return str(file_config.get(file_key, default))

    # 2. 构建 config
    smtp_host = _get("SMTP_HOST", "smtp_host")
    smtp_port_str = _get("SMTP_PORT", "smtp_port", "465")
    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        smtp_port = 465

    smtp_user = _get("SMTP_USER", "smtp_user")
    smtp_password = _get("SMTP_PASSWORD", "smtp_password")
    email_from = _get("EMAIL_FROM", "email_from", smtp_user)  # 默认用 smtp_user
    email_to_str = _get("EMAIL_TO", "email_to")
    email_to = [e.strip() for e in email_to_str.split(",") if e.strip()] if email_to_str else []

    wecom_webhook = _get("WECOM_WEBHOOK", "wecom_webhook")
    # 飞书告警 webhook: 优先用专用变量, 回退到通用 FEISHU_BOT_WEBHOOK
    feishu_webhook = _get("FEISHU_ALERT_WEBHOOK", "feishu_alert_webhook")
    if not feishu_webhook:
        feishu_webhook = _get("FEISHU_BOT_WEBHOOK", "feishu_bot_webhook")

    return AlertNotifierConfig(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_use_ssl=(smtp_port == 465),
        email_from=email_from,
        email_to=email_to,
        wecom_webhook=wecom_webhook,
        feishu_webhook=feishu_webhook,
    )


class AlertNotifier:
    """告警通知器 — 多渠道推送 + 幂等去重.

    线程安全: 内部锁保护去重缓存.
    """

    def __init__(self, config: AlertNotifierConfig | None = None) -> None:
        self.config = config or AlertNotifierConfig()
        # 去重缓存: {alert_id: last_pushed_timestamp}
        self._dedup_cache: dict[str, float] = {}
        self._dedup_lock = threading.Lock()

    def notify_alerts(
        self,
        alerts: list[dict[str, Any]],
        channels: list[str] | None = None,
    ) -> list[NotifyResult]:
        """批量推送告警到通知渠道.

        Args:
            alerts: SystemMonitor.get_alerts() 返回的告警列表
            channels: 指定渠道列表; None 则自动检测已配置的渠道

        Returns:
            各渠道的通知结果列表
        """
        if not alerts:
            return [NotifyResult(channel="log", success=True, sent=0, error="no alerts")]

        # 过滤: 只推送 critical/warning, 且未在去重窗口内
        to_push = []
        for alert in alerts:
            severity = alert.get("severity", "info")
            if not SEVERITY_PUSH_MAP.get(severity, False):
                continue
            alert_id = alert.get("alert_id", "")
            if self._is_duplicate(alert_id):
                continue
            to_push.append(alert)

        if not to_push:
            logger.info("alert_notifier: all alerts deduplicated or filtered, skipping")
            return [NotifyResult(channel="log", success=True, sent=0, error="all deduplicated")]

        # 确定渠道
        active_channels = channels or self._get_active_channels()
        if not active_channels:
            # 无渠道配置, 降级为日志
            self._log_alerts(to_push)
            return [NotifyResult(channel="log", success=True, sent=len(to_push), error="no channel configured")]

        results: list[NotifyResult] = []
        for channel in active_channels:
            try:
                if channel == "email":
                    result = self._send_email(to_push)
                elif channel == "wecom":
                    result = self._send_wecom(to_push)
                elif channel == "feishu":
                    result = self._send_feishu(to_push)
                else:
                    result = NotifyResult(channel=channel, success=False, error=f"unknown channel: {channel}")
            except Exception as exc:
                logger.error("alert_notifier: %s channel failed: %s", channel, exc)
                result = NotifyResult(channel=channel, success=False, error=str(exc))
            results.append(result)

        # 同时记录日志 (无论渠道是否成功)
        self._log_alerts(to_push)

        return results

    def notify_single(
        self,
        alert: dict[str, Any],
        channels: list[str] | None = None,
    ) -> list[NotifyResult]:
        """推送单条告警."""
        return self.notify_alerts([alert], channels=channels)

    def _get_active_channels(self) -> list[str]:
        """获取已配置的渠道列表."""
        if self.config.enabled_channels:
            return list(self.config.enabled_channels)
        channels: list[str] = []
        if self.config.has_email_config():
            channels.append("email")
        if self.config.has_wecom_config():
            channels.append("wecom")
        if self.config.has_feishu_config():
            channels.append("feishu")
        return channels

    def _is_duplicate(self, alert_id: str) -> bool:
        """检查是否在去重窗口内已推送过."""
        if not alert_id:
            return False
        now = time.time()
        with self._dedup_lock:
            last_pushed = self._dedup_cache.get(alert_id)
            if last_pushed and (now - last_pushed) < self.config.dedup_window_seconds:
                return True
            self._dedup_cache[alert_id] = now
            # 清理过期条目 (简单 GC, 避免缓存无限增长)
            expired = [
                k for k, v in self._dedup_cache.items()
                if (now - v) > self.config.dedup_window_seconds * 2
            ]
            for k in expired:
                del self._dedup_cache[k]
        return False

    def _log_alerts(self, alerts: list[dict[str, Any]]) -> None:
        """记录告警到日志 (降级模式)."""
        for alert in alerts:
            severity = alert.get("severity", "info")
            emoji = SEVERITY_EMOJI_MAP.get(severity, "🔵")
            logger.warning(
                "%s [ALERT] %s: %s (current=%s, threshold=%s)",
                emoji,
                alert.get("alert_id", "unknown"),
                alert.get("message", ""),
                alert.get("current_value", ""),
                alert.get("threshold", ""),
            )

    # ── 渠道实现 ──────────────────────────────────────────────

    def _send_email(self, alerts: list[dict[str, Any]]) -> NotifyResult:
        """通过 SMTP 发送邮件通知."""
        cfg = self.config
        if not cfg.has_email_config():
            return NotifyResult(channel="email", success=False, error="email not configured")

        subject = self._build_email_subject(alerts)
        html_body = self._build_email_html(alerts)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg.email_from
        msg["To"] = ", ".join(cfg.email_to)
        msg.attach(MIMEText(self._build_email_text(alerts), "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            if cfg.smtp_use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=context, timeout=10) as server:
                    server.login(cfg.smtp_user, cfg.smtp_password)
                    server.sendmail(cfg.email_from, cfg.email_to, msg.as_string())
            else:
                with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(cfg.smtp_user, cfg.smtp_password)
                    server.sendmail(cfg.email_from, cfg.email_to, msg.as_string())
            return NotifyResult(channel="email", success=True, sent=len(alerts))
        except (smtplib.SMTPException, OSError) as exc:
            return NotifyResult(channel="email", success=False, error=str(exc))

    def _send_wecom(self, alerts: list[dict[str, Any]]) -> NotifyResult:
        """通过企业微信 Webhook 发送通知."""
        cfg = self.config
        if not cfg.has_wecom_config():
            return NotifyResult(channel="wecom", success=False, error="wecom not configured")

        markdown = self._build_wecom_markdown(alerts)
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": markdown},
        }

        try:
            self._post_json(cfg.wecom_webhook, payload)
            return NotifyResult(channel="wecom", success=True, sent=len(alerts))
        except (urllib.error.URLError, OSError) as exc:
            return NotifyResult(channel="wecom", success=False, error=str(exc))

    def _send_feishu(self, alerts: list[dict[str, Any]]) -> NotifyResult:
        """通过飞书 Webhook 发送通知 (interactive card)."""
        cfg = self.config
        if not cfg.has_feishu_config():
            return NotifyResult(channel="feishu", success=False, error="feishu not configured")

        # 取最高严重级别作为卡片颜色
        max_severity = "info"
        for a in alerts:
            if a.get("severity") == "critical":
                max_severity = "critical"
                break
            if a.get("severity") == "warning":
                max_severity = "warning"

        color_map = {"critical": "red", "warning": "yellow", "info": "blue"}
        header_color = color_map.get(max_severity, "blue")

        # 构建飞书 interactive card
        elements = []
        for alert in alerts:
            severity = alert.get("severity", "info")
            emoji = SEVERITY_EMOJI_MAP.get(severity, "🔵")
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"{emoji} **{alert.get('alert_id', 'unknown')}**\n{alert.get('message', '')}\n当前值: `{alert.get('current_value', '-')}` · 阈值: `{alert.get('threshold', '-')}`",
                },
            })

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"AI Studio 告警通知 ({len(alerts)} 条)"},
                    "template": header_color,
                },
                "elements": elements,
            },
        }

        try:
            self._post_json(cfg.feishu_webhook, payload)
            return NotifyResult(channel="feishu", success=True, sent=len(alerts))
        except (urllib.error.URLError, OSError) as exc:
            return NotifyResult(channel="feishu", success=False, error=str(exc))

    # ── 消息格式构建 ──────────────────────────────────────────

    def _build_email_subject(self, alerts: list[dict[str, Any]]) -> str:
        """构建邮件主题."""
        critical_count = sum(1 for a in alerts if a.get("severity") == "critical")
        warning_count = sum(1 for a in alerts if a.get("severity") == "warning")
        prefix = "🔴 CRITICAL" if critical_count > 0 else "🟡 WARNING"
        return f"{prefix} AI Studio 告警 ({critical_count} critical, {warning_count} warning)"

    def _build_email_text(self, alerts: list[dict[str, Any]]) -> str:
        """构建纯文本邮件正文."""
        lines = [f"AI Game Studio OS 告警通知", f"时间: {datetime.now(timezone.utc).isoformat()}", ""]
        for a in alerts:
            lines.append(f"[{a.get('severity', 'info').upper()}] {a.get('alert_id', 'unknown')}")
            lines.append(f"  消息: {a.get('message', '')}")
            lines.append(f"  当前值: {a.get('current_value', '-')} / 阈值: {a.get('threshold', '-')}")
            lines.append(f"  建议: {a.get('suggestion', '-')}")
            lines.append("")
        return "\n".join(lines)

    def _build_email_html(self, alerts: list[dict[str, Any]]) -> str:
        """构建 HTML 邮件正文."""
        rows = []
        for a in alerts:
            severity = a.get("severity", "info")
            color = {"critical": "#dc2626", "warning": "#d97706", "info": "#2563eb"}.get(severity, "#6b7280")
            rows.append(f"""
            <tr>
              <td style="padding:8px;border:1px solid #e5e7eb;color:{color};font-weight:bold;">{severity.upper()}</td>
              <td style="padding:8px;border:1px solid #e5e7eb;">{a.get('alert_id', '')}</td>
              <td style="padding:8px;border:1px solid #e5e7eb;">{a.get('message', '')}</td>
              <td style="padding:8px;border:1px solid #e5e7eb;">{a.get('current_value', '-')}</td>
              <td style="padding:8px;border:1px solid #e5e7eb;">{a.get('threshold', '-')}</td>
            </tr>""")
        return f"""
        <html><body style="font-family:sans-serif;font-size:14px;color:#374151;">
          <h2 style="color:#111827;">AI Game Studio OS 告警通知</h2>
          <p style="color:#6b7280;font-size:12px;">时间: {datetime.now(timezone.utc).isoformat()}</p>
          <table style="border-collapse:collapse;width:100%;font-size:13px;">
            <thead>
              <tr style="background:#f9fafb;">
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">级别</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">告警 ID</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">消息</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">当前值</th>
                <th style="padding:8px;border:1px solid #e5e7eb;text-align:left;">阈值</th>
              </tr>
            </thead>
            <tbody>{''.join(rows)}
            </tbody>
          </table>
        </body></html>"""

    def _build_wecom_markdown(self, alerts: list[dict[str, Any]]) -> str:
        """构建企业微信 markdown 内容."""
        lines = [f"## AI Studio 告警通知 ({len(alerts)} 条)", ""]
        for a in alerts:
            severity = a.get("severity", "info")
            emoji = SEVERITY_EMOJI_MAP.get(severity, "🔵")
            lines.append(f"{emoji} **{a.get('alert_id', 'unknown')}** ({severity})")
            lines.append(f"> {a.get('message', '')}")
            lines.append(f"> 当前值: `{a.get('current_value', '-')}` · 阈值: `{a.get('threshold', '-')}`")
            lines.append("")
        return "\n".join(lines)

    def _post_json(self, url: str, payload: dict[str, Any]) -> None:
        """发送 JSON POST 请求 (urllib, 无第三方依赖)."""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                raise OSError(f"HTTP {resp.status}: {resp.read().decode('utf-8', errors='replace')}")


# ── 模块级单例 ──────────────────────────────────────────────

_default_notifier: AlertNotifier | None = None
_default_notifier_lock = threading.Lock()


def get_alert_notifier(config: AlertNotifierConfig | None = None) -> AlertNotifier:
    """获取默认的 AlertNotifier 单例.

    首次调用时从环境变量加载配置; 后续调用忽略 config 参数 (返回已初始化的实例).
    如需重新初始化, 传入新 config 并设置 force=True.
    """
    global _default_notifier
    with _default_notifier_lock:
        if _default_notifier is None or config is not None:
            if config is None:
                # 推断项目根目录: 向上查找直到不含 src/market_ops
                cwd = Path.cwd()
                root = cwd
                for parent in [cwd] + list(cwd.parents):
                    if (parent / "src" / "market_ops").exists():
                        root = parent
                        break
                config = load_notifier_config(project_root=root)
            _default_notifier = AlertNotifier(config=config)
        return _default_notifier


def reset_alert_notifier() -> None:
    """重置单例 (主要用于测试)."""
    global _default_notifier
    with _default_notifier_lock:
        _default_notifier = None
