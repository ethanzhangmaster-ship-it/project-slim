"""P0 ApprovalGate V2 — ApprovalConfig 单元测试。

Spec: docs/p0_approval_gate_v2_spec.md §3, §5.1, §10.1

覆盖：
- 默认值（无环境变量时）
- 每个环境变量单独覆盖
- 布尔解析（true/false/1/0/yes/on 等大小写）
- 浮点解析失败回退默认值（fail-safe）
- 字符串解析
- validate() 单调性 / 范围校验
- frozen=True 不可变
- from_env(env=None) 读 os.environ
"""
from __future__ import annotations

import os

import pytest

from src.execution.approval.config import (
    DEFAULT_AUDIT_LOG_DIR,
    DEFAULT_AUTO_BUDGET_THRESHOLD_USD,
    DEFAULT_AUTO_DAILY_CUMULATIVE_USD,
    DEFAULT_AUTO_MAX_RISK,
    DEFAULT_AUTO_MIN_CONFIDENCE,
    DEFAULT_DRY_RUN_VERIFY_ENABLED,
    DEFAULT_LEVEL0_ENABLED,
    DEFAULT_LEVEL1_BUDGET_THRESHOLD_USD,
    DEFAULT_LEVEL1_MAX_RISK,
    DEFAULT_SHADOW_MODE,
    ENV_AUDIT_LOG_DIR,
    ENV_AUTO_BUDGET_THRESHOLD_USD,
    ENV_AUTO_DAILY_CUMULATIVE_USD,
    ENV_AUTO_MAX_RISK,
    ENV_AUTO_MIN_CONFIDENCE,
    ENV_DRY_RUN_VERIFY_ENABLED,
    ENV_LEVEL0_ENABLED,
    ENV_LEVEL1_BUDGET_THRESHOLD_USD,
    ENV_LEVEL1_MAX_RISK,
    ENV_SHADOW_MODE,
    ApprovalConfig,
)


# ──────────────────────────────────────────────
# 默认值
# ──────────────────────────────────────────────


class TestDefaults:
    """无环境变量时应返回 Spec §3 的默认值。"""

    def test_from_env_empty_returns_all_defaults(self):
        cfg = ApprovalConfig.from_env(env={})
        assert cfg.auto_budget_threshold_usd == DEFAULT_AUTO_BUDGET_THRESHOLD_USD
        assert cfg.auto_daily_cumulative_usd == DEFAULT_AUTO_DAILY_CUMULATIVE_USD
        assert cfg.level1_budget_threshold_usd == DEFAULT_LEVEL1_BUDGET_THRESHOLD_USD
        assert cfg.auto_max_risk == DEFAULT_AUTO_MAX_RISK
        assert cfg.auto_min_confidence == DEFAULT_AUTO_MIN_CONFIDENCE
        assert cfg.level1_max_risk == DEFAULT_LEVEL1_MAX_RISK
        assert cfg.level0_enabled == DEFAULT_LEVEL0_ENABLED
        assert cfg.shadow_mode == DEFAULT_SHADOW_MODE
        assert cfg.dry_run_verify_enabled == DEFAULT_DRY_RUN_VERIFY_ENABLED
        assert cfg.audit_log_dir == DEFAULT_AUDIT_LOG_DIR

    def test_default_safety_switches_are_off(self):
        """fail-safe：默认所有自动执行开关关闭。"""
        cfg = ApprovalConfig.from_env(env={})
        assert cfg.level0_enabled is False
        assert cfg.shadow_mode is False
        assert cfg.dry_run_verify_enabled is False

    def test_default_thresholds_monotonic(self):
        """默认阈值满足 Level 0 < Level 1 单调性。"""
        cfg = ApprovalConfig.from_env(env={})
        assert cfg.auto_budget_threshold_usd < cfg.level1_budget_threshold_usd
        assert cfg.auto_max_risk < cfg.level1_max_risk

    def test_default_config_validates_clean(self):
        cfg = ApprovalConfig.from_env(env={})
        assert cfg.validate() == []


# ──────────────────────────────────────────────
# 环境变量覆盖
# ──────────────────────────────────────────────


class TestEnvOverride:
    """每个环境变量单独覆盖默认值。"""

    def test_override_auto_budget_threshold_usd(self):
        cfg = ApprovalConfig.from_env(env={ENV_AUTO_BUDGET_THRESHOLD_USD: "75.5"})
        assert cfg.auto_budget_threshold_usd == 75.5

    def test_override_auto_daily_cumulative_usd(self):
        cfg = ApprovalConfig.from_env(env={ENV_AUTO_DAILY_CUMULATIVE_USD: "350"})
        assert cfg.auto_daily_cumulative_usd == 350.0

    def test_override_level1_budget_threshold_usd(self):
        cfg = ApprovalConfig.from_env(env={ENV_LEVEL1_BUDGET_THRESHOLD_USD: "1000"})
        assert cfg.level1_budget_threshold_usd == 1000.0

    def test_override_auto_max_risk(self):
        cfg = ApprovalConfig.from_env(env={ENV_AUTO_MAX_RISK: "0.25"})
        assert cfg.auto_max_risk == 0.25

    def test_override_auto_min_confidence(self):
        cfg = ApprovalConfig.from_env(env={ENV_AUTO_MIN_CONFIDENCE: "0.85"})
        assert cfg.auto_min_confidence == 0.85

    def test_override_level1_max_risk(self):
        cfg = ApprovalConfig.from_env(env={ENV_LEVEL1_MAX_RISK: "0.55"})
        assert cfg.level1_max_risk == 0.55

    def test_override_audit_log_dir(self):
        cfg = ApprovalConfig.from_env(env={ENV_AUDIT_LOG_DIR: "/tmp/approval"})
        assert cfg.audit_log_dir == "/tmp/approval"


# ──────────────────────────────────────────────
# 布尔解析
# ──────────────────────────────────────────────


class TestBoolParsing:
    """level0_enabled / shadow_mode / dry_run_verify_enabled 的布尔解析。"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("Yes", True),
            ("on", True),
            ("y", True),
            ("t", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("n", False),
            ("f", False),
            ("garbage", False),
            ("", None),  # 空字符串 → 默认值（由参数决定）
        ],
    )
    def test_bool_truth_table(self, raw, expected):
        default = True  # 用 True 作默认，验证空字符串回退
        from src.execution.approval.config import _parse_bool
        if expected is None:
            assert _parse_bool(raw, default) == default
        else:
            assert _parse_bool(raw, default) == expected

    @pytest.mark.parametrize("env_var", [ENV_LEVEL0_ENABLED, ENV_SHADOW_MODE, ENV_DRY_RUN_VERIFY_ENABLED])
    def test_enable_via_env_true(self, env_var):
        cfg = ApprovalConfig.from_env(env={env_var: "true"})
        assert getattr(cfg, _env_var_to_attr(env_var)) is True

    @pytest.mark.parametrize("env_var", [ENV_LEVEL0_ENABLED, ENV_SHADOW_MODE, ENV_DRY_RUN_VERIFY_ENABLED])
    def test_enable_via_env_false(self, env_var):
        cfg = ApprovalConfig.from_env(env={env_var: "false"})
        assert getattr(cfg, _env_var_to_attr(env_var)) is False


def _env_var_to_attr(env_var: str) -> str:
    """APPROVAL_FOO_BAR → foo_bar（去掉 APPROVAL_ 前缀并小写）。"""
    prefix = "APPROVAL_"
    assert env_var.startswith(prefix), f"env var {env_var} must start with {prefix}"
    return env_var[len(prefix):].lower()


# ──────────────────────────────────────────────
# 浮点解析 fail-safe
# ──────────────────────────────────────────────


class TestFloatFailSafe:
    """非法浮点输入回退默认值，不抛异常。"""

    @pytest.mark.parametrize("raw", ["not_a_number", "abc", "12.3.4", "-", "None"])
    def test_invalid_float_falls_back(self, raw):
        cfg = ApprovalConfig.from_env(env={ENV_AUTO_BUDGET_THRESHOLD_USD: raw})
        assert cfg.auto_budget_threshold_usd == DEFAULT_AUTO_BUDGET_THRESHOLD_USD

    def test_none_env_value_uses_default(self):
        """env 字典中值为 None 时回退默认值。"""
        cfg = ApprovalConfig.from_env(env={ENV_AUTO_MAX_RISK: None})  # type: ignore[dict-item]
        assert cfg.auto_max_risk == DEFAULT_AUTO_MAX_RISK


# ──────────────────────────────────────────────
# validate() 校验
# ──────────────────────────────────────────────


class TestValidate:
    """validate() 返回错误列表。"""

    def test_clean_config_no_errors(self):
        cfg = ApprovalConfig()
        assert cfg.validate() == []

    def test_budget_threshold_not_monotonic(self):
        """Level 0 金额上限 >= Level 1 金额上限 → 报错。"""
        cfg = ApprovalConfig(
            auto_budget_threshold_usd=500.0,
            level1_budget_threshold_usd=500.0,
        )
        errors = cfg.validate()
        assert any("auto_budget_threshold_usd" in e for e in errors)

    def test_risk_not_monotonic(self):
        """auto_max_risk >= level1_max_risk → 报错。"""
        cfg = ApprovalConfig(
            auto_max_risk=0.7,
            level1_max_risk=0.6,
        )
        errors = cfg.validate()
        assert any("auto_max_risk" in e for e in errors)

    def test_risk_out_of_range(self):
        cfg = ApprovalConfig(auto_max_risk=1.5)
        errors = cfg.validate()
        assert any("[0,1]" in e for e in errors)

    def test_confidence_out_of_range(self):
        cfg = ApprovalConfig(auto_min_confidence=1.5)
        errors = cfg.validate()
        assert any("auto_min_confidence" in e for e in errors)

    def test_negative_budget_threshold(self):
        cfg = ApprovalConfig(auto_budget_threshold_usd=-10.0)
        errors = cfg.validate()
        assert any(">= 0" in e for e in errors)

    def test_empty_audit_log_dir(self):
        cfg = ApprovalConfig(audit_log_dir="")
        errors = cfg.validate()
        assert any("audit_log_dir" in e for e in errors)


# ──────────────────────────────────────────────
# 不可变性
# ──────────────────────────────────────────────


class TestImmutability:
    """frozen=True 保证运行中配置不可被修改。"""

    def test_frozen_raises_on_setattr(self):
        cfg = ApprovalConfig()
        with pytest.raises((AttributeError, Exception)):
            cfg.auto_max_risk = 0.5  # type: ignore[misc]

    def test_frozen_raises_on_new_attr(self):
        cfg = ApprovalConfig()
        with pytest.raises((AttributeError, Exception)):
            cfg.new_field = "x"  # type: ignore[attr-defined]


# ──────────────────────────────────────────────
# from_env(env=None) 读 os.environ
# ──────────────────────────────────────────────


class TestReadsOsEnviron:
    """env=None 时应读真实 os.environ（集成验证）。"""

    def test_from_env_none_reads_os_environ(self, monkeypatch):
        monkeypatch.setenv(ENV_AUTO_BUDGET_THRESHOLD_USD, "123.45")
        try:
            cfg = ApprovalConfig.from_env(env=None)
            assert cfg.auto_budget_threshold_usd == 123.45
        finally:
            # 清理：monkeypatch.setenv 会在测试结束自动还原，
            # 但显式 del 更安全（防止其它测试读到污染）。
            os.environ.pop(ENV_AUTO_BUDGET_THRESHOLD_USD, None)
