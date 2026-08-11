"""SDK 就绪检查命令行工具 — CI/CD 自动化。

本脚本将原 Unity Editor 窗口 ``com.gamefactory.sdk/Editor/GameFactoryReadiness.cs``
提供的可视化 SDK 就绪检查逻辑，导出为可在 CI/CD 中无 Unity 环境直接运行的命令行版本。

检查基于文件系统扫描，不依赖 Unity 编辑器，因此非常适合在 GitHub Actions / Jenkins /
GitLab CI 中作为发布门禁使用。

检查内容:
1. Unity SDK 包是否存在 (com.gamefactory.sdk)
2. 依赖配置文件是否存在 (credentials/store_keys.json.example)
3. 配置 placeholder 扫描 (REPLACE_WITH_* 标记)
4. iOS 发布配置完整性
5. Google Play 发布配置完整性
6. 变现 SDK 配置完整性 (AdMob/LevelPlay/Max)
7. 归因 SDK 配置完整性 (Adjust)
8. 分析 SDK 配置完整性 (Firebase/ThinkingData)
9. IAP 配置完整性

输出:
- JSON 报告 (可被 CI 系统解析)
- 控制台摘要 (人类可读)
- 退出码: 0 = 全部通过, 1 = 有失败项

用法:
    python scripts/check_sdk_readiness.py
    python scripts/check_sdk_readiness.py --json > report.json
    python scripts/check_sdk_readiness.py --game-id P04 --platform ios
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """单项检查结果。

    Attributes:
        check_name: 检查项标识 (例如 ``sdk_package``)
        status: 检查状态，``pass`` / ``fail`` / ``warning``
        message: 给人类阅读的一行摘要
        details: 多行详细信息
        files_checked: 本次检查扫描到的文件 (绝对或相对路径)
        files_missing: 缺失的文件路径
    """

    check_name: str
    status: str  # "pass" | "fail" | "warning"
    message: str
    details: list[str] = field(default_factory=list)
    files_checked: list[str] = field(default_factory=list)
    files_missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为可被 JSON 序列化的字典。"""
        return asdict(self)

    @property
    def ok(self) -> bool:
        """是否通过 (pass 视为通过，warning/fail 视为未通过)。"""
        return self.status == "pass"


# 占位符前缀，与 Unity Editor 内的 ``HasPlaceholder`` 逻辑保持一致
PLACEHOLDER_MARKER = "REPLACE_WITH_"

# CI 友好的状态常量
STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_WARNING = "warning"


# ---------------------------------------------------------------------------
# 检查器
# ---------------------------------------------------------------------------


class SDKReadinessChecker:
    """SDK 就绪检查器。

    所有检查方法均返回 :class:`CheckResult`，可独立调用，也可通过 :meth:`check_all`
    一次性运行所有检查。
    """

    # 检查项标识 (与 check_xxx 方法一一对应，便于报告引用)
    CHECK_NAMES = [
        "sdk_package",
        "credentials_template",
        "config_placeholders",
        "ios_publishing",
        "google_play_publishing",
        "monetization_sdk",
        "attribution_sdk",
        "analytics_sdk",
        "iap_config",
    ]

    def __init__(self, project_root: str = ""):
        """初始化检查器。

        Args:
            project_root: 项目根目录。空字符串表示自动推断为脚本所在目录的上一级。
        """
        if project_root:
            self.project_root = Path(project_root).resolve()
        else:
            # scripts/check_sdk_readiness.py 的上一级即项目根目录
            self.project_root = Path(__file__).resolve().parents[1]

        # 可选的过滤参数 (由命令行注入)
        self.game_id: Optional[str] = None
        self.platform: Optional[str] = None

        # 缓存上一次 check_all 的结果，便于 print_summary 复用
        self._last_results: list[CheckResult] = []

    # ------------------------------------------------------------------
    # 路径助手
    # ------------------------------------------------------------------

    def _resolve(self, *parts: str) -> Path:
        """以项目根目录为基准，拼接相对路径并返回 Path 对象。"""
        return self.project_root.joinpath(*parts)

    @staticmethod
    def _exists(path: Path) -> bool:
        """同时兼容文件与目录的存检查。"""
        return path.exists()

    # ------------------------------------------------------------------
    # 单项检查
    # ------------------------------------------------------------------

    def check_sdk_package(self) -> CheckResult:
        """检查 Unity SDK 包是否存在。"""
        sdk_dir = self._resolve("com.gamefactory.sdk")
        package_json = sdk_dir / "package.json"

        files_checked = [str(sdk_dir), str(package_json)]
        files_missing: list[str] = []

        if not sdk_dir.exists():
            files_missing.append(str(sdk_dir))
            return CheckResult(
                check_name="sdk_package",
                status=STATUS_FAIL,
                message="Unity SDK 包目录缺失: com.gamefactory.sdk/",
                details=["CI/CD 流水线需要 SDK 包已检入仓库。"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        if not package_json.exists():
            files_missing.append(str(package_json))
            return CheckResult(
                check_name="sdk_package",
                status=STATUS_FAIL,
                message="SDK package.json 缺失",
                details=["com.gamefactory.sdk/package.json 必须存在以被 Unity 识别为 UPM 包。"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        # 校验 package.json 内容可解析
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            pkg_name = data.get("name", "")
            pkg_version = data.get("version", "")
        except (OSError, json.JSONDecodeError) as exc:
            return CheckResult(
                check_name="sdk_package",
                status=STATUS_FAIL,
                message=f"SDK package.json 解析失败: {exc}",
                details=[f"路径: {package_json}"],
                files_checked=files_checked,
                files_missing=[],
            )

        if pkg_name != "com.gamefactory.sdk":
            return CheckResult(
                check_name="sdk_package",
                status=STATUS_WARNING,
                message=f"package.json name 字段异常: {pkg_name!r}",
                details=[f"期望: 'com.gamefactory.sdk'，实际: {pkg_name!r}"],
                files_checked=files_checked,
                files_missing=[],
            )

        return CheckResult(
            check_name="sdk_package",
            status=STATUS_PASS,
            message=f"SDK 包就绪 (v{pkg_version})",
            details=[f"包名: {pkg_name}", f"版本: {pkg_version}"],
            files_checked=files_checked,
            files_missing=[],
        )

    def check_credentials_template(self) -> CheckResult:
        """检查凭证模板文件。"""
        template_path = self._resolve("credentials", "store_keys.json.example")
        files_checked = [str(template_path)]

        if not template_path.exists():
            return CheckResult(
                check_name="credentials_template",
                status=STATUS_FAIL,
                message="凭证模板缺失: credentials/store_keys.json.example",
                details=["该模板为开发者拷贝凭证文件的依据，缺失会阻塞 CI 流程。"],
                files_checked=files_checked,
                files_missing=[str(template_path)],
            )

        # 校验模板内容是合法 JSON
        try:
            data = json.loads(template_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return CheckResult(
                check_name="credentials_template",
                status=STATUS_FAIL,
                message=f"凭证模板不是合法 JSON: {exc}",
                details=[f"路径: {template_path}"],
                files_checked=files_checked,
                files_missing=[],
            )

        # 模板应当包含至少一个 key 占位
        if not isinstance(data, dict) or not data:
            return CheckResult(
                check_name="credentials_template",
                status=STATUS_WARNING,
                message="凭证模板为空对象或非对象",
                details=[f"路径: {template_path}", f"内容类型: {type(data).__name__}"],
                files_checked=files_checked,
                files_missing=[],
            )

        return CheckResult(
            check_name="credentials_template",
            status=STATUS_PASS,
            message="凭证模板就绪",
            details=[f"路径: {template_path}", f"顶层键数: {len(data)}"],
            files_checked=files_checked,
            files_missing=[],
        )

    def check_config_placeholders(self) -> CheckResult:
        """扫描配置 placeholder (REPLACE_WITH_*)。

        覆盖两类文件:
        - ``com.gamefactory.sdk`` 下的 ``.cs`` 文件 (与 Unity Editor 内逻辑保持一致)
        - ``com.gamefactory.sdk/Resources/gamefactory_config.json`` 配置文件
        """
        sdk_dir = self._resolve("com.gamefactory.sdk")
        config_path = sdk_dir / "Resources" / "gamefactory_config.json"

        files_checked: list[str] = []
        files_missing: list[str] = []
        hits: list[str] = []  # 每条形如 "file:line: 内容片段"

        if not sdk_dir.exists():
            files_missing.append(str(sdk_dir))
            return CheckResult(
                check_name="config_placeholders",
                status=STATUS_FAIL,
                message="SDK 包不存在，无法扫描 placeholder",
                details=["请先通过 sdk_package 检查。"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        # 1) 扫描 .cs 文件 (Unity Editor 仅在配置中检查，这里扩大到 .cs 以便 CI 更稳健)
        cs_files = sorted(sdk_dir.rglob("*.cs"))
        files_checked.extend(str(p) for p in cs_files)

        for cs_file in cs_files:
            try:
                lines = cs_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines, start=1):
                if PLACEHOLDER_MARKER in line:
                    snippet = line.strip()[:200]
                    hits.append(f"{cs_file.relative_to(self.project_root)}:{idx}: {snippet}")

        # 2) 扫描 gamefactory_config.json (按字段粒度定位)
        if config_path.exists():
            files_checked.append(str(config_path))
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                for field_path, value in _walk_json(config):
                    if isinstance(value, str) and PLACEHOLDER_MARKER in value:
                        hits.append(
                            f"{config_path.relative_to(self.project_root)}:{field_path}: {value}"
                        )
            except (OSError, json.JSONDecodeError):
                # 解析失败不在此检查项报告，由 sdk_package / 后续检查负责
                pass
        else:
            files_missing.append(str(config_path))

        if hits:
            # 占位符存在即视为 warning：项目可运行但发布前必须替换
            return CheckResult(
                check_name="config_placeholders",
                status=STATUS_WARNING,
                message=f"发现 {len(hits)} 处 REPLACE_WITH_* 占位符",
                details=hits,
                files_checked=files_checked,
                files_missing=files_missing,
            )

        return CheckResult(
            check_name="config_placeholders",
            status=STATUS_PASS,
            message="未发现 REPLACE_WITH_* 占位符",
            details=["扫描范围: com.gamefactory.sdk/**/*.cs 以及 gamefactory_config.json"],
            files_checked=files_checked,
            files_missing=files_missing,
        )

    def check_ios_publishing(self) -> CheckResult:
        """检查 iOS 发布配置完整性。"""
        orchestrator = self._resolve("operation", "publishing", "app_store", "orchestrator.py")
        files_checked = [str(orchestrator)]

        if not orchestrator.exists():
            return CheckResult(
                check_name="ios_publishing",
                status=STATUS_FAIL,
                message="iOS 发布编排器缺失",
                details=["期望: operation/publishing/app_store/orchestrator.py"],
                files_checked=files_checked,
                files_missing=[str(orchestrator)],
            )

        # 若指定了 platform 过滤，且当前不为 ios，则跳过
        if self.platform and self.platform.lower() not in ("ios", "app_store", "all"):
            return CheckResult(
                check_name="ios_publishing",
                status=STATUS_PASS,
                message=f"iOS 发布配置存在 (当前 platform={self.platform}，跳过深入检查)",
                details=[f"路径: {orchestrator}"],
                files_checked=files_checked,
                files_missing=[],
            )

        return CheckResult(
            check_name="ios_publishing",
            status=STATUS_PASS,
            message="iOS 发布编排器就绪",
            details=[f"路径: {orchestrator}"],
            files_checked=files_checked,
            files_missing=[],
        )

    def check_google_play_publishing(self) -> CheckResult:
        """检查 Google Play 发布配置完整性。"""
        orchestrator = self._resolve("operation", "publishing", "google_play", "orchestrator.py")
        files_checked = [str(orchestrator)]

        if not orchestrator.exists():
            return CheckResult(
                check_name="google_play_publishing",
                status=STATUS_FAIL,
                message="Google Play 发布编排器缺失",
                details=["期望: operation/publishing/google_play/orchestrator.py"],
                files_checked=files_checked,
                files_missing=[str(orchestrator)],
            )

        if self.platform and self.platform.lower() not in ("android", "google_play", "all"):
            return CheckResult(
                check_name="google_play_publishing",
                status=STATUS_PASS,
                message=f"Google Play 发布配置存在 (当前 platform={self.platform}，跳过深入检查)",
                details=[f"路径: {orchestrator}"],
                files_checked=files_checked,
                files_missing=[],
            )

        return CheckResult(
            check_name="google_play_publishing",
            status=STATUS_PASS,
            message="Google Play 发布编排器就绪",
            details=[f"路径: {orchestrator}"],
            files_checked=files_checked,
            files_missing=[],
        )

    def check_monetization_sdk(self) -> CheckResult:
        """检查变现 SDK 配置 (AdMob/LevelPlay/Max)。"""
        sdk_dir = self._resolve("com.gamefactory.sdk")
        ads_dir = sdk_dir / "Runtime" / "Ads"
        max_provider_dir = self._resolve("monetization", "providers", "max")

        files_checked = [
            str(ads_dir),
            str(max_provider_dir),
        ]
        files_missing: list[str] = []
        present: list[str] = []

        # 检查 SDK 内的三家变现 provider 目录
        for provider in ("AdMob", "LevelPlay", "Max"):
            provider_dir = ads_dir / provider
            files_checked.append(str(provider_dir))
            if provider_dir.exists() and any(provider_dir.iterdir()):
                present.append(f"com.gamefactory.sdk/Runtime/Ads/{provider}")
            else:
                files_missing.append(str(provider_dir))

        # 检查 Python 侧的 MAX provider 目录 (CI 数据回路使用)
        if max_provider_dir.exists():
            present.append("monetization/providers/max")
        else:
            files_missing.append(str(max_provider_dir))

        if not present:
            return CheckResult(
                check_name="monetization_sdk",
                status=STATUS_FAIL,
                message="变现 SDK 全部缺失 (AdMob/LevelPlay/Max)",
                details=["至少需要 Max provider 就绪才能驱动变现回路。"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        if files_missing:
            return CheckResult(
                check_name="monetization_sdk",
                status=STATUS_WARNING,
                message=f"部分变现 SDK 缺失 ({len(files_missing)} 项)",
                details=[f"已就绪: {', '.join(present)}", f"缺失: {', '.join(files_missing)}"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        return CheckResult(
            check_name="monetization_sdk",
            status=STATUS_PASS,
            message="变现 SDK 配置完整 (AdMob/LevelPlay/Max)",
            details=[f"已就绪: {', '.join(present)}"],
            files_checked=files_checked,
            files_missing=files_missing,
        )

    def check_attribution_sdk(self) -> CheckResult:
        """检查归因 SDK 配置 (Adjust)。"""
        adjust_py = self._resolve("src", "market_ops", "clients", "adjust.py")
        adjust_provider_cs = self._resolve(
            "com.gamefactory.sdk", "Runtime", "Analytics", "Adjust", "AdjustProvider.cs"
        )

        files_checked = [str(adjust_py), str(adjust_provider_cs)]
        files_missing: list[str] = []
        present: list[str] = []

        if adjust_py.exists():
            present.append("src/market_ops/clients/adjust.py")
        else:
            files_missing.append(str(adjust_py))

        if adjust_provider_cs.exists():
            present.append("com.gamefactory.sdk/Runtime/Analytics/Adjust/AdjustProvider.cs")
        else:
            files_missing.append(str(adjust_provider_cs))

        if not present:
            return CheckResult(
                check_name="attribution_sdk",
                status=STATUS_FAIL,
                message="Adjust 归因 SDK 全部缺失",
                details=["CI 数据回路和 SDK 上报均需要 Adjust 模块。"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        if files_missing:
            return CheckResult(
                check_name="attribution_sdk",
                status=STATUS_WARNING,
                message="Adjust 归因 SDK 部分缺失",
                details=[f"已就绪: {', '.join(present)}", f"缺失: {', '.join(files_missing)}"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        return CheckResult(
            check_name="attribution_sdk",
            status=STATUS_PASS,
            message="Adjust 归因 SDK 配置完整",
            details=[f"已就绪: {', '.join(present)}"],
            files_checked=files_checked,
            files_missing=files_missing,
        )

    def check_analytics_sdk(self) -> CheckResult:
        """检查分析 SDK 配置 (Firebase/ThinkingData)。"""
        thinkingdata_py = self._resolve("src", "market_ops", "clients", "thinkingdata.py")
        firebase_provider_cs = self._resolve(
            "com.gamefactory.sdk", "Runtime", "Analytics", "Firebase", "FirebaseProvider.cs"
        )

        files_checked = [str(thinkingdata_py), str(firebase_provider_cs)]
        files_missing: list[str] = []
        present: list[str] = []

        if thinkingdata_py.exists():
            present.append("src/market_ops/clients/thinkingdata.py")
        else:
            files_missing.append(str(thinkingdata_py))

        if firebase_provider_cs.exists():
            present.append("com.gamefactory.sdk/Runtime/Analytics/Firebase/FirebaseProvider.cs")
        else:
            files_missing.append(str(firebase_provider_cs))

        if not present:
            return CheckResult(
                check_name="analytics_sdk",
                status=STATUS_FAIL,
                message="分析 SDK 全部缺失 (Firebase/ThinkingData)",
                details=["分析 SDK 至少需要一项就绪以驱动数据采集。"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        if files_missing:
            return CheckResult(
                check_name="analytics_sdk",
                status=STATUS_WARNING,
                message="分析 SDK 部分缺失",
                details=[f"已就绪: {', '.join(present)}", f"缺失: {', '.join(files_missing)}"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        return CheckResult(
            check_name="analytics_sdk",
            status=STATUS_PASS,
            message="分析 SDK 配置完整 (Firebase/ThinkingData)",
            details=[f"已就绪: {', '.join(present)}"],
            files_checked=files_checked,
            files_missing=files_missing,
        )

    def check_iap_config(self) -> CheckResult:
        """检查 IAP 配置完整性。"""
        iap_dir = self._resolve("com.gamefactory.sdk", "Runtime", "IAP")
        iap_manager = iap_dir / "IAPManager.cs"
        config_path = self._resolve("com.gamefactory.sdk", "Resources", "gamefactory_config.json")

        files_checked = [str(iap_dir), str(iap_manager), str(config_path)]
        files_missing: list[str] = []

        if not iap_dir.exists():
            files_missing.append(str(iap_dir))
            return CheckResult(
                check_name="iap_config",
                status=STATUS_FAIL,
                message="IAP 目录缺失: com.gamefactory.sdk/Runtime/IAP/",
                details=["IAP 模块未集成，无法进行内购。"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        if not iap_manager.exists():
            files_missing.append(str(iap_manager))

        # 检查配置文件中的 iap.enabled 与 products 列表
        iap_enabled: Optional[bool] = None
        product_count = 0
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                iap_cfg = config.get("iap") or {}
                iap_enabled = bool(iap_cfg.get("enabled", False))
                products = iap_cfg.get("products") or []
                if isinstance(products, list):
                    product_count = len(products)
            except (OSError, json.JSONDecodeError):
                # 解析失败由 config_placeholders / sdk_package 检查负责
                pass
        else:
            files_missing.append(str(config_path))

        if files_missing:
            return CheckResult(
                check_name="iap_config",
                status=STATUS_FAIL,
                message="IAP 关键文件缺失",
                details=[f"缺失: {', '.join(files_missing)}"],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        if iap_enabled is False:
            return CheckResult(
                check_name="iap_config",
                status=STATUS_WARNING,
                message="IAP 模块就绪但 gamefactory_config.json 中 iap.enabled=false",
                details=[
                    f"代码模块: {iap_manager}",
                    f"配置内产品数: {product_count}",
                    "上线前需在配置中启用 iap.enabled=true。",
                ],
                files_checked=files_checked,
                files_missing=files_missing,
            )

        return CheckResult(
            check_name="iap_config",
            status=STATUS_PASS,
            message=f"IAP 配置就绪 (enabled={iap_enabled}, {product_count} 个产品)",
            details=[
                f"代码模块: {iap_manager}",
                f"配置内产品数: {product_count}",
            ],
            files_checked=files_checked,
            files_missing=files_missing,
        )

    # ------------------------------------------------------------------
    # 聚合 / 输出
    # ------------------------------------------------------------------

    def check_all(self) -> dict:
        """运行所有检查并返回结果字典。

        Returns:
            与 :meth:`generate_report` 相同结构的字典。
        """
        results: list[CheckResult] = [
            self.check_sdk_package(),
            self.check_credentials_template(),
            self.check_config_placeholders(),
            self.check_ios_publishing(),
            self.check_google_play_publishing(),
            self.check_monetization_sdk(),
            self.check_attribution_sdk(),
            self.check_analytics_sdk(),
            self.check_iap_config(),
        ]
        self._last_results = results
        return self.generate_report()

    def generate_report(self) -> dict:
        """生成完整报告。

        如果之前调用过 :meth:`check_all`，则复用其结果；否则重新执行所有检查。
        """
        if not self._last_results:
            return self.check_all()

        results = self._last_results
        passed = sum(1 for r in results if r.status == STATUS_PASS)
        warnings = sum(1 for r in results if r.status == STATUS_WARNING)
        failed = sum(1 for r in results if r.status == STATUS_FAIL)

        # 整体状态: 全部 pass -> pass；存在 fail -> fail；否则 warning
        if failed > 0:
            overall = STATUS_FAIL
        elif warnings > 0:
            overall = STATUS_WARNING
        else:
            overall = STATUS_PASS

        return {
            "overall_status": overall,
            "summary": {
                "total": len(results),
                "passed": passed,
                "warnings": warnings,
                "failed": failed,
            },
            "project_root": str(self.project_root),
            "game_id": self.game_id,
            "platform": self.platform,
            "checks": [r.to_dict() for r in results],
        }

    def print_summary(self) -> None:
        """打印控制台摘要 (人类可读)。"""
        if not self._last_results:
            self.check_all()

        report = self.generate_report()
        summary = report["summary"]
        overall = report["overall_status"]

        print("=" * 72)
        print("GameFactory SDK Readiness — CI/CD Report")
        print("=" * 72)
        print(f"项目根目录: {self.project_root}")
        if self.game_id:
            print(f"游戏 ID: {self.game_id}")
        if self.platform:
            print(f"目标平台: {self.platform}")
        print("-" * 72)

        for result in self._last_results:
            symbol = {
                STATUS_PASS: "[PASS]",
                STATUS_FAIL: "[FAIL]",
                STATUS_WARNING: "[WARN]",
            }.get(result.status, "[????]")
            print(f"{symbol} {result.check_name:<28} {result.message}")
            for detail in result.details:
                print(f"        {detail}")
            for missing in result.files_missing:
                print(f"        缺失: {missing}")

        print("-" * 72)
        print(
            f"汇总: {summary['passed']}/{summary['total']} 通过, "
            f"{summary['warnings']} 警告, {summary['failed']} 失败 — 整体: {overall.upper()}"
        )
        if overall == STATUS_PASS:
            print("SDK 全部就绪，可以继续 CI/CD 流程。")
        elif overall == STATUS_WARNING:
            print("存在警告项，发布前请人工确认。")
        else:
            print("存在失败项，CI/CD 流程应中断。")
        print("=" * 72)

    # ------------------------------------------------------------------
    # 退出码
    # ------------------------------------------------------------------

    def exit_code(self) -> int:
        """根据最近一次检查结果返回退出码。

        - 0: 全部 pass
        - 1: 存在 fail 或 warning

        与文档约定一致: 0 = 全部通过, 1 = 有失败项 (含 warning)。
        """
        if not self._last_results:
            self.check_all()

        report = self.generate_report()
        # warning 也算 "未全部通过"，与 ``--json`` 报告中的 overall_status 等价
        if report["overall_status"] == STATUS_PASS:
            return 0
        return 1


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _walk_json(node, prefix: str = ""):
    """递归遍历 JSON 节点，产出 (字段路径, 叶子值) 对。

    字段路径示例: ``ads.app_key``、``analytics.providers[0]``。
    """
    if isinstance(node, dict):
        for key, value in node.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            yield from _walk_json(value, new_prefix)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            new_prefix = f"{prefix}[{idx}]"
            yield from _walk_json(value, new_prefix)
    else:
        yield prefix, node


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="check_sdk_readiness",
        description="GameFactory SDK 就绪检查命令行工具 (CI/CD 自动化)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--project-root",
        default="",
        help="项目根目录 (默认: 脚本所在目录的上一级)",
    )
    parser.add_argument(
        "--game-id",
        default="",
        help="指定游戏 ID (例如 P04)，仅用于报告标注",
    )
    parser.add_argument(
        "--platform",
        default="",
        choices=["", "ios", "android", "app_store", "google_play", "all"],
        help="目标平台过滤 (ios/android/app_store/google_play/all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="仅输出 JSON 报告到 stdout (适合 CI 系统解析)",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="与 --json 一起使用，跳过人类可读摘要",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """命令行入口。

    Args:
        argv: 命令行参数 (默认从 ``sys.argv`` 读取)。

    Returns:
        退出码: 0 = 全部通过, 1 = 有失败项
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    checker = SDKReadinessChecker(project_root=args.project_root)
    if args.game_id:
        checker.game_id = args.game_id
    if args.platform:
        checker.platform = args.platform

    # 执行所有检查
    checker.check_all()

    if args.json:
        # 仅打印 JSON 报告
        report = checker.generate_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        # 打印人类可读摘要
        checker.print_summary()

    return checker.exit_code()


if __name__ == "__main__":
    sys.exit(main())
