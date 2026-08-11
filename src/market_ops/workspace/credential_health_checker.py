"""凭证健康检查工具 — 为金丝雀执行铺路.

系统性检查所有外部凭证/配置项的就绪状态，映射到 P0 上线证据 (E1-E7)，
帮助运维团队快速定位缺口，确认是否满足金丝雀 (E4-E6) 前置条件。

检查维度:
  1. Meta/Facebook 凭证 (E1: MAX_REPORT_KEY + META_ACCESS_TOKEN + META_APP_ID/SECRET)
  2. Google Play 服务账号 (E2: PLAY_SERVICE_ACCOUNT_JSON)
  3. 人工审批人配置 (E3: credentials/approver.json)
  4. App Store Connect 凭证 (U1: store_keys.json app_store_connect)
  5. 闭环投放配置 (O4: CLOSED_LOOP_ADSET_ID + CLOSED_LOOP_PAGE_ID)
  6. 告警通知渠道 (O2: SMTP/Wecom/Feishu)
  7. Google Ads 凭证组
  8. AI Provider (OPENAI_API_KEY)
  9. 数据平台 (ThinkingData / Adjust)
 10. Token 过期状态 (E7: 复用 TokenMonitor)

用法:
  from market_ops.workspace.credential_health_checker import CredentialHealthChecker
  checker = CredentialHealthChecker()
  report = checker.check_all()
  print(report.to_dict())
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────

_CANARY_EVIDENCE_IDS = {"E1", "E2", "E3"}
_PRODUCTION_EVIDENCE_IDS = {"E1", "E2", "E3", "E4", "E5", "E6", "E7"}

# 占位符检测 (复用 ProductionReadinessGate._missing_or_placeholder 逻辑)
_PLACEHOLDER_VALUES = {"changeme", "xxx", "your_api_key", "your_token", ""}


def _is_placeholder(value: str) -> bool:
    """检测值是否为空或占位符."""
    text = str(value or "").strip().lower()
    return (
        not text
        or text.startswith("your_")
        or text.startswith("placeholder")
        or text in _PLACEHOLDER_VALUES
    )


def _mask(value: str) -> str:
    """脱敏: 保留前3+后3, 中间用 *** 替代."""
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-3:]}"


# ── 数据模型 ──────────────────────────────────────────────────

@dataclass
class CredentialCheck:
    """单个凭证/配置项的检查结果."""

    check_id: str                       # e.g. "E1", "E2", "O4"
    name: str                           # 人类可读名称
    category: str                       # "P0" | "P1" | "optional"
    status: str                         # "pass" | "fail" | "warning" | "skip"
    required_vars: List[str] = field(default_factory=list)
    missing_vars: List[str] = field(default_factory=list)
    placeholder_vars: List[str] = field(default_factory=list)
    masked_values: Dict[str, str] = field(default_factory=dict)
    file_checks: Dict[str, bool] = field(default_factory=dict)
    real_time_ok: Optional[bool] = None
    message: str = ""
    recommendation: str = ""

    @property
    def is_canary_blocker(self) -> bool:
        """是否为金丝雀阻塞项 (E1-E3 未通过)."""
        return self.check_id in _CANARY_EVIDENCE_IDS and self.status == "fail"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "required_vars": self.required_vars,
            "missing_vars": self.missing_vars,
            "placeholder_vars": self.placeholder_vars,
            "masked_values": self.masked_values,
            "file_checks": self.file_checks,
            "real_time_ok": self.real_time_ok,
            "message": self.message,
            "recommendation": self.recommendation,
            "is_canary_blocker": self.is_canary_blocker,
        }


@dataclass
class CredentialHealthReport:
    """凭证健康整体报告."""

    overall_status: str                 # "ready" | "blocked" | "degraded"
    canary_ready: bool                  # E1+E2+E3 全部 pass
    production_ready: bool              # E1-E7 全部 pass
    timestamp: str
    checks: List[CredentialCheck] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=lambda: {"pass": 0, "fail": 0, "warning": 0, "skip": 0})
    canary_blockers: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "canary_ready": self.canary_ready,
            "production_ready": self.production_ready,
            "timestamp": self.timestamp,
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary,
            "canary_blockers": self.canary_blockers,
            "recommendations": self.recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ── 核心检查器 ────────────────────────────────────────────────

class CredentialHealthChecker:
    """凭证健康检查器 — 检查所有外部凭证/配置就绪状态.

    线程安全, 可复用. 每次 check_all() 产生新报告.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        environ: Optional[Dict[str, str]] = None,
    ) -> None:
        if project_root is None:
            project_root = Path(__file__).resolve().parents[3]
        self._root = Path(project_root)
        self._environ = dict(environ if environ is not None else os.environ)
        self._lock = threading.Lock()

    # ── 公共 API ──

    def check_all(self, include_real_time: bool = False) -> CredentialHealthReport:
        """执行全部检查并生成报告.

        Args:
            include_real_time: 是否包含 Meta token 实时检查 (需要网络).
                              默认 False, 仅做本地配置检查.
        """
        with self._lock:
            checks: List[CredentialCheck] = []
            checks.append(self._check_meta_credentials(include_real_time))
            checks.append(self._check_google_play())
            checks.append(self._check_approver())
            checks.append(self._check_app_store_connect())
            checks.append(self._check_closed_loop())
            checks.append(self._check_alert_channels())
            checks.append(self._check_google_ads())
            checks.append(self._check_ai_provider())
            checks.append(self._check_data_platforms())
            checks.append(self._check_credential_rotation())

            return self._build_report(checks)

    def check_canary_prerequisites(self) -> CredentialHealthReport:
        """仅检查金丝雀前置条件 (E1-E3)."""
        with self._lock:
            checks = [
                self._check_meta_credentials(include_real_time=True),
                self._check_google_play(),
                self._check_approver(),
            ]
            return self._build_report(checks)

    # ── E1: Meta/Facebook 凭证 ──

    def _check_meta_credentials(self, include_real_time: bool = False) -> CredentialCheck:
        """E1: 检查 Meta API 凭证 (MAX_REPORT_KEY + META_ACCESS_TOKEN + META_APP_ID/SECRET)."""
        required_vars = [
            "MAX_REPORT_KEY",
            "META_ACCESS_TOKEN",
            "META_AD_ACCOUNT_ID",
        ]
        optional_vars = ["META_APP_ID", "META_APP_SECRET"]

        all_vars = required_vars + optional_vars
        masked: Dict[str, str] = {}
        missing: List[str] = []
        placeholders: List[str] = []

        for var in all_vars:
            value = self._environ.get(var, "")
            masked[var] = _mask(value) if value else ""
            if not value:
                if var in required_vars:
                    missing.append(var)
            elif _is_placeholder(value):
                placeholders.append(var)

        real_time_ok: Optional[bool] = None
        message_parts: List[str] = []

        if include_real_time and not missing:
            real_time_ok = self._real_time_meta_check(message_parts)
        elif include_real_time and missing:
            message_parts.append("实时检查已跳过 (缺少必需凭证)")

        if missing:
            status = "fail"
            message = f"缺少必需凭证: {', '.join(missing)}"
            recommendation = "在 .env 中配置缺失的 Meta API 凭证"
        elif placeholders:
            status = "fail"
            message = f"检测到占位符值: {', '.join(placeholders)}"
            recommendation = "将占位符替换为真实 Meta API 凭证"
        elif real_time_ok is False:
            status = "fail"
            message = "; ".join(message_parts) if message_parts else "Meta token 实时验证失败"
            recommendation = "检查 META_ACCESS_TOKEN 是否有效, 或重新生成 token"
        elif real_time_ok is True:
            status = "pass"
            message = "全部 Meta 凭证已配置且 token 实时验证通过"
            recommendation = ""
        else:
            status = "pass"
            message = "全部 Meta 凭证已配置 (未执行实时验证)"
            recommendation = "建议执行实时验证确认 token 有效性"

        return CredentialCheck(
            check_id="E1",
            name="Meta/Facebook API 凭证",
            category="P0",
            status=status,
            required_vars=all_vars,
            missing_vars=missing,
            placeholder_vars=placeholders,
            masked_values=masked,
            real_time_ok=real_time_ok,
            message=message,
            recommendation=recommendation,
        )

    def _real_time_meta_check(self, message_parts: List[str]) -> bool:
        """通过 TokenMonitor 执行 Meta token 实时验证."""
        try:
            from .token_monitor import get_token_monitor
            monitor = get_token_monitor(
                data_dir=str(self._root / "data" / "token_monitor")
            )
            status = monitor.check_meta_token_from_env()
            if status is None:
                message_parts.append("META_ACCESS_TOKEN 未配置, 无法实时检查")
                return False
            if status.is_valid:
                message_parts.append(
                    f"Token 有效, 过期时间: {datetime.fromtimestamp(status.expires_at, tz=timezone.utc).isoformat() if status.expires_at else '永不过期'}"
                )
                return True
            else:
                message_parts.append(f"Token 无效: {status.error}")
                return False
        except Exception as exc:
            message_parts.append(f"实时检查异常: {exc}")
            return False

    # ── E2: Google Play 服务账号 ──

    def _check_google_play(self) -> CredentialCheck:
        """E2: 检查 Google Play 服务账号 JSON 文件."""
        required_vars = ["PLAY_SERVICE_ACCOUNT_JSON"]
        masked: Dict[str, str] = {}
        missing: List[str] = []
        placeholders: List[str] = []
        file_checks: Dict[str, bool] = {}

        for var in required_vars:
            value = self._environ.get(var, "")
            masked[var] = _mask(value) if value else ""
            if not value:
                missing.append(var)
            elif _is_placeholder(value):
                placeholders.append(var)

        # 检查文件是否存在
        sa_path = self._environ.get("PLAY_SERVICE_ACCOUNT_JSON", "")
        if sa_path and not _is_placeholder(sa_path):
            p = Path(sa_path)
            if not p.is_absolute():
                p = self._root / p
            file_checks[str(p)] = p.is_file()
            if not p.is_file():
                missing.append(f"{var} (文件不存在)")

        var = "PLAY_SERVICE_ACCOUNT_JSON"
        if missing:
            status = "fail"
            message = f"Google Play 服务账号缺失: {', '.join(missing)}"
            recommendation = "在 Google Cloud Console 创建服务账号, 下载 JSON, 在 .env 中设置 PLAY_SERVICE_ACCOUNT_JSON 路径"
        elif placeholders:
            status = "fail"
            message = f"检测到占位符: {', '.join(placeholders)}"
            recommendation = "将占位符替换为真实服务账号 JSON 路径"
        else:
            # 同时检查 store_keys.json 中的 google_play 配置
            try:
                from operation.providers.live import store_keys
                gp = store_keys.get_googleplay()
                store_ok = gp is not None
            except Exception:
                store_ok = False

            if store_ok:
                status = "pass"
                message = "Google Play 服务账号已配置 (env + store_keys.json)"
                recommendation = ""
            else:
                status = "pass"
                message = "Google Play 服务账号 env 已配置 (store_keys.json 未配置, 可选)"
                recommendation = "建议同步配置 credentials/store_keys.json"

        return CredentialCheck(
            check_id="E2",
            name="Google Play 服务账号",
            category="P0",
            status=status,
            required_vars=required_vars,
            missing_vars=missing,
            placeholder_vars=placeholders,
            masked_values=masked,
            file_checks=file_checks,
            message=message,
            recommendation=recommendation,
        )

    # ── E3: 人工审批人 ──

    def _check_approver(self) -> CredentialCheck:
        """E3: 检查人工审批人是否已指定."""
        approver_file = self._root / "credentials" / "approver.json"
        file_checks: Dict[str, bool] = {str(approver_file): approver_file.is_file()}

        approver_data: Dict[str, Any] = {}
        if approver_file.is_file():
            try:
                approver_data = json.loads(
                    approver_file.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError) as exc:
                return CredentialCheck(
                    check_id="E3",
                    name="人工审批人",
                    category="P0",
                    status="fail",
                    file_checks=file_checks,
                    message=f"approver.json 解析失败: {exc}",
                    recommendation="修复 credentials/approver.json 格式",
                )

        required_fields = ["approver_name", "approver_contact"]
        missing_fields = [
            f for f in required_fields if not approver_data.get(f)
        ]

        masked: Dict[str, str] = {}
        for f in required_fields:
            val = approver_data.get(f, "")
            masked[f] = _mask(str(val)) if val else ""

        if not approver_file.is_file():
            status = "fail"
            message = "credentials/approver.json 不存在"
            recommendation = "创建 credentials/approver.json, 填入 approver_name 和 approver_contact"
        elif missing_fields:
            status = "fail"
            message = f"approver.json 缺少字段: {', '.join(missing_fields)}"
            recommendation = f"在 approver.json 中补充: {', '.join(missing_fields)}"
        else:
            status = "pass"
            approver_name = approver_data.get("approver_name", "")
            message = f"审批人已指定: {_mask(str(approver_name))}"
            recommendation = ""

        return CredentialCheck(
            check_id="E3",
            name="人工审批人",
            category="P0",
            status=status,
            required_vars=["credentials/approver.json"],
            missing_vars=missing_fields,
            masked_values=masked,
            file_checks=file_checks,
            message=message,
            recommendation=recommendation,
        )

    # ── E7: 凭证轮转 ──

    def _check_credential_rotation(self) -> CredentialCheck:
        """E7: 检查凭证轮转责任人和 on-call 联系方式."""
        rotation_file = self._root / "credentials" / "rotation_owner.json"
        file_checks: Dict[str, bool] = {str(rotation_file): rotation_file.is_file()}

        rot_data: Dict[str, Any] = {}
        if rotation_file.is_file():
            try:
                rot_data = json.loads(rotation_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        required_fields = ["rotation_owner", "oncall_contact"]
        missing_fields = [f for f in required_fields if not rot_data.get(f)]

        masked: Dict[str, str] = {}
        for f in required_fields:
            val = rot_data.get(f, "")
            masked[f] = _mask(str(val)) if val else ""

        if not rotation_file.is_file():
            status = "fail"
            message = "credentials/rotation_owner.json 不存在"
            recommendation = "创建 credentials/rotation_owner.json, 填入 rotation_owner 和 oncall_contact"
        elif missing_fields:
            status = "fail"
            message = f"rotation_owner.json 缺少字段: {', '.join(missing_fields)}"
            recommendation = f"补充字段: {', '.join(missing_fields)}"
        else:
            status = "pass"
            message = "凭证轮转责任人已文档化"
            recommendation = ""

        return CredentialCheck(
            check_id="E7",
            name="凭证轮转责任人",
            category="P0",
            status=status,
            required_vars=["credentials/rotation_owner.json"],
            missing_vars=missing_fields,
            masked_values=masked,
            file_checks=file_checks,
            message=message,
            recommendation=recommendation,
        )

    # ── U1: App Store Connect ──

    def _check_app_store_connect(self) -> CredentialCheck:
        """U1: 检查 App Store Connect 凭证 (store_keys.json + env)."""
        file_checks: Dict[str, bool] = {}
        masked: Dict[str, str] = {}

        # 方法 1: store_keys.json
        try:
            from operation.providers.live import store_keys
            cred = store_keys.get_appstore()
        except Exception:
            cred = None

        store_ok = cred is not None
        if store_ok:
            masked["key_id"] = _mask(cred.get("key_id", ""))
            masked["issuer_id"] = _mask(cred.get("issuer_id", ""))
            masked["private_key_p8"] = "***" if cred.get("private_key_p8") else ""

        # 方法 2: 环境变量
        env_vars = ["APPSTORE_API_KEY_ID", "APPSTORE_API_ISSUER_ID", "APPSTORE_PRIVATE_KEY_P8_PATH"]
        env_ok = True
        for var in env_vars:
            val = self._environ.get(var, "")
            masked[f"env:{var}"] = _mask(val) if val else ""
            if not val or _is_placeholder(val):
                env_ok = False

        # .p8 文件存在性
        p8_path = self._environ.get("APPSTORE_PRIVATE_KEY_P8_PATH", "")
        if p8_path and not _is_placeholder(p8_path):
            p = Path(p8_path)
            if not p.is_absolute():
                p = self._root / p
            file_checks[str(p)] = p.is_file()

        if store_ok:
            status = "pass"
            message = "App Store Connect 凭证已配置 (store_keys.json)"
            recommendation = ""
        elif env_ok:
            status = "pass"
            message = "App Store Connect 凭证已配置 (环境变量)"
            recommendation = ""
        else:
            status = "warning"
            message = "App Store Connect 凭证未配置 (SIMULATION 模式可用, 真实上传需要)"
            recommendation = "在 credentials/store_keys.json 中配置 app_store_connect, 或设置 APPSTORE_* 环境变量"

        return CredentialCheck(
            check_id="U1",
            name="App Store Connect 凭证",
            category="P1",
            status=status,
            required_vars=env_vars,
            masked_values=masked,
            file_checks=file_checks,
            message=message,
            recommendation=recommendation,
        )

    # ── O4: 闭环投放配置 ──

    def _check_closed_loop(self) -> CredentialCheck:
        """O4: 检查闭环投放配置 (CLOSED_LOOP_ADSET_ID + CLOSED_LOOP_PAGE_ID)."""
        required_vars = ["CLOSED_LOOP_ADSET_ID", "CLOSED_LOOP_PAGE_ID"]
        masked: Dict[str, str] = {}
        missing: List[str] = []
        placeholders: List[str] = []

        for var in required_vars:
            value = self._environ.get(var, "")
            masked[var] = _mask(value) if value else ""
            if not value:
                missing.append(var)
            elif _is_placeholder(value):
                placeholders.append(var)

        if missing:
            status = "warning"
            message = f"闭环投放配置缺失: {', '.join(missing)}"
            recommendation = "在 .env.closed_loop 中配置 Facebook AdSet ID 和 Page ID"
        elif placeholders:
            status = "warning"
            message = f"检测到占位符: {', '.join(placeholders)}"
            recommendation = "替换为真实 Facebook 广告资产 ID"
        else:
            status = "pass"
            message = "闭环投放配置已就绪"
            recommendation = ""

        return CredentialCheck(
            check_id="O4",
            name="闭环投放配置",
            category="P1",
            status=status,
            required_vars=required_vars,
            missing_vars=missing,
            placeholder_vars=placeholders,
            masked_values=masked,
            message=message,
            recommendation=recommendation,
        )

    # ── O2: 告警通知渠道 ──

    def _check_alert_channels(self) -> CredentialCheck:
        """O2: 检查告警通知渠道 (Email/Wecom/Feishu)."""
        try:
            from .alert_notifier import load_notifier_config
            config = load_notifier_config(project_root=self._root)
        except Exception:
            config = None

        masked: Dict[str, str] = {}
        channels_ok: List[str] = []

        if config:
            if config.has_email_config():
                channels_ok.append("email")
                masked["smtp_host"] = _mask(config.smtp_host)
                masked["email_from"] = _mask(config.email_from)
            if config.has_wecom_config():
                channels_ok.append("wecom")
                masked["wecom_webhook"] = _mask(config.wecom_webhook)
            if config.has_feishu_config():
                channels_ok.append("feishu")
                masked["feishu_webhook"] = _mask(config.feishu_webhook)

        if channels_ok:
            status = "pass"
            message = f"告警渠道已配置: {', '.join(channels_ok)}"
            recommendation = ""
        else:
            status = "warning"
            message = "未配置任何告警通知渠道 (降级模式: 仅日志)"
            recommendation = "配置 credentials/notify.json 或设置 SMTP_*/WECOM_WEBHOOK/FEISHU_ALERT_WEBHOOK 环境变量"

        return CredentialCheck(
            check_id="O2",
            name="告警通知渠道",
            category="P1",
            status=status,
            masked_values=masked,
            message=message,
            recommendation=recommendation,
        )

    # ── Google Ads 凭证组 ──

    def _check_google_ads(self) -> CredentialCheck:
        """检查 Google Ads API 凭证组."""
        required_vars = [
            "GOOGLE_ADS_DEVELOPER_TOKEN",
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_CUSTOMER_ID",
        ]
        masked: Dict[str, str] = {}
        missing: List[str] = []
        placeholders: List[str] = []

        for var in required_vars:
            value = self._environ.get(var, "")
            masked[var] = _mask(value) if value else ""
            if not value:
                missing.append(var)
            elif _is_placeholder(value):
                placeholders.append(var)

        if not missing and not placeholders:
            status = "pass"
            message = "Google Ads 凭证组已配置"
            recommendation = ""
        elif missing == required_vars:
            status = "skip"
            message = "Google Ads 凭证未配置 (非必需, 仅 Google Ads 投放时需要)"
            recommendation = ""
        else:
            status = "warning"
            msg_parts = []
            if missing:
                msg_parts.append(f"缺少: {', '.join(missing)}")
            if placeholders:
                msg_parts.append(f"占位符: {', '.join(placeholders)}")
            message = "; ".join(msg_parts)
            recommendation = "在 .env 中配置完整的 Google Ads 凭证组"

        return CredentialCheck(
            check_id="GA",
            name="Google Ads 凭证组",
            category="optional",
            status=status,
            required_vars=required_vars,
            missing_vars=missing,
            placeholder_vars=placeholders,
            masked_values=masked,
            message=message,
            recommendation=recommendation,
        )

    # ── AI Provider ──

    def _check_ai_provider(self) -> CredentialCheck:
        """检查 AI 模型 Provider 凭证."""
        provider = self._environ.get("AI_PROVIDER", "mock")
        required_var = "OPENAI_API_KEY"
        masked: Dict[str, str] = {"AI_PROVIDER": provider}

        api_key = self._environ.get(required_var, "")
        masked[required_var] = _mask(api_key) if api_key else ""

        if provider == "mock":
            status = "skip"
            message = "AI Provider 为 mock 模式 (无需真实 API Key)"
            recommendation = "生产环境建议设置 AI_PROVIDER=openai 并配置 OPENAI_API_KEY"
        elif not api_key:
            status = "warning"
            message = f"AI_PROVIDER={provider} 但 {required_var} 未配置"
            recommendation = f"配置 {required_var}"
        elif _is_placeholder(api_key):
            status = "warning"
            message = f"{required_var} 检测到占位符"
            recommendation = "替换为真实 OpenAI API Key"
        else:
            status = "pass"
            message = f"AI Provider ({provider}) 凭证已配置"
            recommendation = ""

        return CredentialCheck(
            check_id="AI",
            name="AI Provider 凭证",
            category="optional",
            status=status,
            required_vars=[required_var, "AI_PROVIDER"],
            masked_values=masked,
            message=message,
            recommendation=recommendation,
        )

    # ── 数据平台 ──

    def _check_data_platforms(self) -> CredentialCheck:
        """检查第三方数据平台凭证 (ThinkingData / Adjust)."""
        platforms = {
            "ThinkingData": ["THINKINGDATA_BASE_URL", "THINKINGDATA_TOKEN"],
            "Adjust": ["ADJUST_API_TOKEN"],
        }
        masked: Dict[str, str] = {}
        configured: List[str] = []
        partial: List[str] = []

        for platform, vars_list in platforms.items():
            all_set = True
            for var in vars_list:
                val = self._environ.get(var, "")
                masked[var] = _mask(val) if val else ""
                if not val or _is_placeholder(val):
                    all_set = False
            if all_set:
                configured.append(platform)
            elif any(self._environ.get(v, "") for v in vars_list):
                partial.append(platform)

        if configured and not partial:
            status = "pass"
            message = f"数据平台已配置: {', '.join(configured)}"
            recommendation = ""
        elif configured and partial:
            status = "warning"
            message = f"完整: {', '.join(configured)}; 部分配置: {', '.join(partial)}"
            recommendation = f"补全 {', '.join(partial)} 的缺失凭证"
        elif partial:
            status = "warning"
            message = f"部分配置: {', '.join(partial)}"
            recommendation = "补全缺失凭证或忽略 (非必需)"
        else:
            status = "skip"
            message = "数据平台凭证未配置 (非必需)"
            recommendation = ""

        return CredentialCheck(
            check_id="DP",
            name="数据平台凭证",
            category="optional",
            status=status,
            required_vars=sum(platforms.values(), []),
            masked_values=masked,
            message=message,
            recommendation=recommendation,
        )

    # ── 报告构建 ──

    def _build_report(self, checks: List[CredentialCheck]) -> CredentialHealthReport:
        """汇总检查结果为整体报告."""
        summary = {"pass": 0, "fail": 0, "warning": 0, "skip": 0}
        canary_blockers: List[str] = []
        recommendations: List[str] = []

        for check in checks:
            summary[check.status] = summary.get(check.status, 0) + 1
            if check.is_canary_blocker:
                canary_blockers.append(check.check_id)
            if check.status == "fail" and check.recommendation:
                recommendations.append(f"[{check.check_id}] {check.recommendation}")

        # 金丝雀就绪: E1-E3 全部 pass
        canary_ready = all(
            c.status == "pass"
            for c in checks
            if c.check_id in _CANARY_EVIDENCE_IDS
        )

        # 生产就绪: E1-E7 全部 pass
        p0_checks = [c for c in checks if c.category == "P0"]
        production_ready = all(c.status == "pass" for c in p0_checks)

        if summary["fail"] > 0:
            overall = "blocked"
        elif summary["warning"] > 0:
            overall = "degraded"
        else:
            overall = "ready"

        if not recommendations:
            if canary_ready:
                recommendations.append("金丝雀前置条件已满足, 可执行 E4 (低风险金丝雀)")
            if production_ready:
                recommendations.append("全部 P0 证据已闭环, 可解除 Fail-Closed 进入生产模式")

        return CredentialHealthReport(
            overall_status=overall,
            canary_ready=canary_ready,
            production_ready=production_ready,
            timestamp=datetime.now(timezone.utc).isoformat(),
            checks=checks,
            summary=summary,
            canary_blockers=canary_blockers,
            recommendations=recommendations,
        )


# ── 单例 ──────────────────────────────────────────────────────

_instance: Optional[CredentialHealthChecker] = None
_instance_lock = threading.Lock()


def get_credential_health_checker(
    project_root: Optional[Path] = None,
    environ: Optional[Dict[str, str]] = None,
) -> CredentialHealthChecker:
    """获取单例实例. 传 project_root 或 environ 会重新创建."""
    global _instance
    if project_root is not None or environ is not None:
        with _instance_lock:
            _instance = CredentialHealthChecker(project_root=project_root, environ=environ)
            return _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CredentialHealthChecker()
    return _instance


def reset_credential_health_checker() -> None:
    """重置单例 (用于测试)."""
    global _instance
    with _instance_lock:
        _instance = None


__all__ = [
    "CredentialCheck",
    "CredentialHealthReport",
    "CredentialHealthChecker",
    "get_credential_health_checker",
    "reset_credential_health_checker",
]
