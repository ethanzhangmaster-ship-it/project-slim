#!/usr/bin/env python
"""凭证健康检查 CLI — 快速诊断所有外部凭证/配置就绪状态.

用法:
  python scripts/check_credentials.py                  # 本地检查 (不含实时验证)
  python scripts/check_credentials.py --real-time       # 含 Meta token 实时验证
  python scripts/check_credentials.py --canary-only     # 仅检查金丝雀前置 (E1-E3)
  python scripts/check_credentials.py --json            # JSON 输出 (便于 CI/CD)
  python scripts/check_credentials.py --quiet           # 仅输出阻塞项
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.market_ops.workspace.credential_health_checker import (
    CredentialHealthChecker,
    get_credential_health_checker,
    reset_credential_health_checker,
)


# ── 颜色输出 ──

_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[91m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_BLUE = "\033[94m"
_GRAY = "\033[90m"

_STATUS_COLOR = {
    "pass": _GREEN,
    "fail": _RED,
    "warning": _YELLOW,
    "skip": _GRAY,
}

_STATUS_ICON = {
    "pass": "[OK]",
    "fail": "[FAIL]",
    "warning": "[WARN]",
    "skip": "[SKIP]",
}


def _color(text: str, color: str) -> str:
    return f"{color}{text}{_RESET}"


def _print_report(report, quiet: bool = False) -> None:
    """格式化输出报告."""
    # 头部
    overall_color = {
        "ready": _GREEN,
        "blocked": _RED,
        "degraded": _YELLOW,
    }.get(report.overall_status, _GRAY)

    print()
    print(_color("=" * 70, _BOLD))
    print(_color("  LaunchForge 凭证健康检查报告", _BOLD))
    print(_color("=" * 70, _BOLD))
    print(f"  时间: {report.timestamp}")
    print(f"  整体状态: {_color(report.overall_status.upper(), overall_color)}")
    print(f"  金丝雀就绪 (E1-E3): {_color('YES' if report.canary_ready else 'NO', _GREEN if report.canary_ready else _RED)}")
    print(f"  生产就绪 (E1-E7): {_color('YES' if report.production_ready else 'NO', _GREEN if report.production_ready else _RED)}")
    print(f"  汇总: pass={report.summary['pass']} fail={report.summary['fail']} warning={report.summary['warning']} skip={report.summary['skip']}")
    print()

    if report.canary_blockers:
        print(_color("  [金丝雀阻塞项]", _RED))
        for blocker in report.canary_blockers:
            print(f"    {_color('-', _RED)} {blocker}")
        print()

    # 逐项检查
    if not quiet:
        print(_color("  ── 检查明细 ──", _BOLD))
        print()
        for check in report.checks:
            color = _STATUS_COLOR.get(check.status, _GRAY)
            icon = _STATUS_ICON.get(check.status, "[?]")
            cat_tag = f"[{check.category}]" if check.category != "optional" else ""
            print(f"  {_color(icon, color)} {check.check_id:>3} {cat_tag:<5} {check.name}")
            print(f"        {check.message}")

            if check.missing_vars:
                print(f"        {_color('缺失:', _RED)} {', '.join(check.missing_vars)}")
            if check.placeholder_vars:
                print(f"        {_color('占位符:', _YELLOW)} {', '.join(check.placeholder_vars)}")
            if check.recommendation:
                print(f"        {_color('建议:', _BLUE)} {check.recommendation}")
            if check.masked_values:
                masked_str = "  ".join(f"{k}={v}" for k, v in check.masked_values.items() if v)
                if masked_str:
                    print(f"        {_color('当前值:', _GRAY)} {masked_str}")
            if check.file_checks:
                for fpath, exists in check.file_checks.items():
                    icon_f = _color("[OK]", _GREEN) if exists else _color("[MISSING]", _RED)
                    print(f"        {icon_f} {fpath}")
            print()

    # 建议
    if report.recommendations:
        print(_color("  ── 下一步行动 ──", _BOLD))
        for rec in report.recommendations:
            print(f"    {_color('->', _BLUE)} {rec}")
        print()

    # 金丝雀就绪判断
    if report.canary_ready:
        print(_color("  >>> 金丝雀前置条件已满足, 可执行 E4 (低风险金丝雀) <<<", _GREEN + _BOLD))
    else:
        print(_color(f"  >>> 金丝雀阻塞: {', '.join(report.canary_blockers)} 需要闭环 <<<", _RED + _BOLD))
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LaunchForge 凭证健康检查工具"
    )
    parser.add_argument(
        "--real-time",
        action="store_true",
        help="包含 Meta token 实时验证 (需要网络)",
    )
    parser.add_argument(
        "--canary-only",
        action="store_true",
        help="仅检查金丝雀前置条件 (E1-E3)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="JSON 输出 (便于 CI/CD 集成)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="仅输出阻塞项和行动建议",
    )
    args = parser.parse_args()

    # 重置单例确保使用当前环境变量
    reset_credential_health_checker()
    checker = get_credential_health_checker()

    if args.canary_only:
        report = checker.check_canary_prerequisites()
    else:
        report = checker.check_all(include_real_time=args.real_time)

    if args.json_output:
        print(report.to_json())
    else:
        _print_report(report, quiet=args.quiet)

    # 退出码: 0=ready, 1=degraded, 2=blocked
    if report.overall_status == "blocked":
        return 2
    elif report.overall_status == "degraded":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
