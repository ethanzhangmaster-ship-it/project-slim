"""P0 ApprovalGate V2 — ApprovalConfig.

Spec: docs/p0_approval_gate_v2_spec.md §3, §5.1

职责：把 10 个审批阈值/开关从环境变量加载到一个不可变 dataclass，
供 ApprovalPolicy 构造时注入。禁止在业务逻辑中散落 os.getenv。

设计纪律（继承全库 + Spec §1）：
- 纯 dataclass + from_env，无 LLM、无 IO、无网络
- 所有阈值有默认值（fail-safe：默认关 Level 0 / Shadow / dry_run）
- 失败语义 fail-closed：解析失败回退默认值，绝不抛异常中断主流程
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


# ──────────────────────────────────────────────
# 默认值常量（与 Spec §3 一一对应，禁止在业务代码中重复硬编码）
# ──────────────────────────────────────────────

DEFAULT_AUTO_BUDGET_THRESHOLD_USD: float = 50.0
DEFAULT_AUTO_DAILY_CUMULATIVE_USD: float = 200.0
DEFAULT_LEVEL1_BUDGET_THRESHOLD_USD: float = 500.0
DEFAULT_AUTO_MAX_RISK: float = 0.3
DEFAULT_AUTO_MIN_CONFIDENCE: float = 0.9
DEFAULT_LEVEL1_MAX_RISK: float = 0.6
DEFAULT_LEVEL0_ENABLED: bool = False
DEFAULT_SHADOW_MODE: bool = False
DEFAULT_DRY_RUN_VERIFY_ENABLED: bool = False
DEFAULT_AUDIT_LOG_DIR: str = "outputs/approval_audit"

# 环境变量名（Spec §3）
ENV_AUTO_BUDGET_THRESHOLD_USD = "APPROVAL_AUTO_BUDGET_THRESHOLD_USD"
ENV_AUTO_DAILY_CUMULATIVE_USD = "APPROVAL_AUTO_DAILY_CUMULATIVE_USD"
ENV_LEVEL1_BUDGET_THRESHOLD_USD = "APPROVAL_LEVEL1_BUDGET_THRESHOLD_USD"
ENV_AUTO_MAX_RISK = "APPROVAL_AUTO_MAX_RISK"
ENV_AUTO_MIN_CONFIDENCE = "APPROVAL_AUTO_MIN_CONFIDENCE"
ENV_LEVEL1_MAX_RISK = "APPROVAL_LEVEL1_MAX_RISK"
ENV_LEVEL0_ENABLED = "APPROVAL_LEVEL0_ENABLED"
ENV_SHADOW_MODE = "APPROVAL_SHADOW_MODE"
ENV_DRY_RUN_VERIFY_ENABLED = "APPROVAL_DRY_RUN_VERIFY_ENABLED"
ENV_AUDIT_LOG_DIR = "APPROVAL_AUDIT_LOG_DIR"

# 布尔真值集合（大小写不敏感）
_TRUE_STRINGS = {"1", "true", "yes", "on", "y", "t"}


@dataclass(frozen=True)
class ApprovalConfig:
    """ApprovalGate V2 配置（不可变）。

    所有字段对应 Spec §3 配置参数表。frozen=True 保证 Policy 拿到的是
    不可变快照，运行中不会被外部修改。

    Attributes:
        auto_budget_threshold_usd: Level 0 单次金额上限（USD）。
            单次绝对金额 < 此值才可能进 Level 0。
        auto_daily_cumulative_usd: Level 0 日累计上限（USD）。
            按 game_id + action_type 聚合，超过即强制 Level 2。
        level1_budget_threshold_usd: Level 1 单次金额上限（USD）。
            amount >= 此值直接 Level 2。
        auto_max_risk: Level 0 风险上限（沿用 V1 AUTO_MAX_RISK）。
        auto_min_confidence: Level 0 置信度下限（沿用 V1 AUTO_MIN_CONFIDENCE）。
        level1_max_risk: Level 1 风险上限，超过即 Level 2。
        level0_enabled: Level 0 自动执行总开关（默认 False，灰度切换）。
        shadow_mode: Shadow 模式：Level 0 决策只记录不执行（默认 False）。
        dry_run_verify_enabled: Level 1 dry_run 升级开关（默认 False）。
        audit_log_dir: audit log 目录（Spec §8）。
    """

    auto_budget_threshold_usd: float = DEFAULT_AUTO_BUDGET_THRESHOLD_USD
    auto_daily_cumulative_usd: float = DEFAULT_AUTO_DAILY_CUMULATIVE_USD
    level1_budget_threshold_usd: float = DEFAULT_LEVEL1_BUDGET_THRESHOLD_USD
    auto_max_risk: float = DEFAULT_AUTO_MAX_RISK
    auto_min_confidence: float = DEFAULT_AUTO_MIN_CONFIDENCE
    level1_max_risk: float = DEFAULT_LEVEL1_MAX_RISK
    level0_enabled: bool = DEFAULT_LEVEL0_ENABLED
    shadow_mode: bool = DEFAULT_SHADOW_MODE
    dry_run_verify_enabled: bool = DEFAULT_DRY_RUN_VERIFY_ENABLED
    audit_log_dir: str = DEFAULT_AUDIT_LOG_DIR

    # ------------------------------------------------------------------
    # 工厂
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None
    ) -> "ApprovalConfig":
        """从环境变量构造 ApprovalConfig。

        Args:
            env: 可选的环境变量映射（测试注入用）。None 时读 os.environ。

        Returns:
            ApprovalConfig 实例。解析失败的字段回退默认值（fail-safe），
            不抛异常。
        """
        e = os.environ if env is None else env
        return cls(
            auto_budget_threshold_usd=_parse_float(
                e.get(ENV_AUTO_BUDGET_THRESHOLD_USD),
                DEFAULT_AUTO_BUDGET_THRESHOLD_USD,
            ),
            auto_daily_cumulative_usd=_parse_float(
                e.get(ENV_AUTO_DAILY_CUMULATIVE_USD),
                DEFAULT_AUTO_DAILY_CUMULATIVE_USD,
            ),
            level1_budget_threshold_usd=_parse_float(
                e.get(ENV_LEVEL1_BUDGET_THRESHOLD_USD),
                DEFAULT_LEVEL1_BUDGET_THRESHOLD_USD,
            ),
            auto_max_risk=_parse_float(
                e.get(ENV_AUTO_MAX_RISK), DEFAULT_AUTO_MAX_RISK
            ),
            auto_min_confidence=_parse_float(
                e.get(ENV_AUTO_MIN_CONFIDENCE), DEFAULT_AUTO_MIN_CONFIDENCE
            ),
            level1_max_risk=_parse_float(
                e.get(ENV_LEVEL1_MAX_RISK), DEFAULT_LEVEL1_MAX_RISK
            ),
            level0_enabled=_parse_bool(
                e.get(ENV_LEVEL0_ENABLED), DEFAULT_LEVEL0_ENABLED
            ),
            shadow_mode=_parse_bool(
                e.get(ENV_SHADOW_MODE), DEFAULT_SHADOW_MODE
            ),
            dry_run_verify_enabled=_parse_bool(
                e.get(ENV_DRY_RUN_VERIFY_ENABLED),
                DEFAULT_DRY_RUN_VERIFY_ENABLED,
            ),
            audit_log_dir=_parse_str(
                e.get(ENV_AUDIT_LOG_DIR), DEFAULT_AUDIT_LOG_DIR
            ),
        )

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """返回校验错误列表（空列表表示配置合法）。

        校验规则（Spec §2 分级语义）：
        - 金额阈值单调递增：auto_budget < level1_budget
        - 风险阈值单调递增：auto_max_risk < level1_max_risk
        - 置信度 ∈ [0, 1]
        - 风险 ∈ [0, 1]
        - 金额阈值非负
        - audit_log_dir 非空
        """
        errors: list[str] = []
        if self.auto_budget_threshold_usd < 0:
            errors.append(
                f"auto_budget_threshold_usd must be >= 0, got "
                f"{self.auto_budget_threshold_usd}"
            )
        if self.auto_daily_cumulative_usd < 0:
            errors.append(
                f"auto_daily_cumulative_usd must be >= 0, got "
                f"{self.auto_daily_cumulative_usd}"
            )
        if self.level1_budget_threshold_usd < 0:
            errors.append(
                f"level1_budget_threshold_usd must be >= 0, got "
                f"{self.level1_budget_threshold_usd}"
            )
        # 金额单调性：Level 0 上限必须 < Level 1 上限
        if (
            self.auto_budget_threshold_usd
            >= self.level1_budget_threshold_usd
        ):
            errors.append(
                f"auto_budget_threshold_usd ("
                f"{self.auto_budget_threshold_usd}) must be < "
                f"level1_budget_threshold_usd ("
                f"{self.level1_budget_threshold_usd})"
            )
        # 风险单调性
        if not 0.0 <= self.auto_max_risk <= 1.0:
            errors.append(
                f"auto_max_risk must be in [0,1], got "
                f"{self.auto_max_risk}"
            )
        if not 0.0 <= self.level1_max_risk <= 1.0:
            errors.append(
                f"level1_max_risk must be in [0,1], got "
                f"{self.level1_max_risk}"
            )
        if self.auto_max_risk >= self.level1_max_risk:
            errors.append(
                f"auto_max_risk ({self.auto_max_risk}) must be < "
                f"level1_max_risk ({self.level1_max_risk})"
            )
        if not 0.0 <= self.auto_min_confidence <= 1.0:
            errors.append(
                f"auto_min_confidence must be in [0,1], got "
                f"{self.auto_min_confidence}"
            )
        if not self.audit_log_dir:
            errors.append("audit_log_dir must be non-empty")
        return errors


# ──────────────────────────────────────────────
# 私有解析工具（fail-safe，绝不抛异常）
# ──────────────────────────────────────────────


def _parse_float(raw: str | None, default: float) -> float:
    """解析浮点，失败回退默认值。"""
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _parse_bool(raw: str | None, default: bool) -> bool:
    """解析布尔（大小写不敏感），失败回退默认值。

    真值集合：1 / true / yes / on / y / t（大小写不敏感）
    其它非空字符串视为假；None / 空字符串回退默认值。
    """
    if raw is None or raw == "":
        return default
    if raw.strip().lower() in _TRUE_STRINGS:
        return True
    return False


def _parse_str(raw: str | None, default: str) -> str:
    """解析字符串，None/空回退默认值。"""
    if raw is None or raw == "":
        return default
    return raw


__all__ = [
    "ApprovalConfig",
    # 默认值常量（供测试断言与文档引用）
    "DEFAULT_AUTO_BUDGET_THRESHOLD_USD",
    "DEFAULT_AUTO_DAILY_CUMULATIVE_USD",
    "DEFAULT_LEVEL1_BUDGET_THRESHOLD_USD",
    "DEFAULT_AUTO_MAX_RISK",
    "DEFAULT_AUTO_MIN_CONFIDENCE",
    "DEFAULT_LEVEL1_MAX_RISK",
    "DEFAULT_LEVEL0_ENABLED",
    "DEFAULT_SHADOW_MODE",
    "DEFAULT_DRY_RUN_VERIFY_ENABLED",
    "DEFAULT_AUDIT_LOG_DIR",
    # 环境变量名常量
    "ENV_AUTO_BUDGET_THRESHOLD_USD",
    "ENV_AUTO_DAILY_CUMULATIVE_USD",
    "ENV_LEVEL1_BUDGET_THRESHOLD_USD",
    "ENV_AUTO_MAX_RISK",
    "ENV_AUTO_MIN_CONFIDENCE",
    "ENV_LEVEL1_MAX_RISK",
    "ENV_LEVEL0_ENABLED",
    "ENV_SHADOW_MODE",
    "ENV_DRY_RUN_VERIFY_ENABLED",
    "ENV_AUDIT_LOG_DIR",
]
