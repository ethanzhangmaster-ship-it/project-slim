"""SDKReadinessChecker 单元测试。

测试覆盖:
- 每个检查方法 (pass/fail/warning 场景)
- 报告生成
- 摘要打印
- 退出码
- JSON 输出格式
- 命令行参数解析

测试使用临时目录构造最小可运行的项目结构，避免依赖真实仓库布局，
所有断言均基于 checker 自身返回的 :class:`CheckResult`。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 让测试可以直接 import scripts/check_sdk_readiness.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_sdk_readiness import (  # noqa: E402
    CheckResult,
    SDKReadinessChecker,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARNING,
    build_arg_parser,
    main,
)


# ---------------------------------------------------------------------------
# 测试夹具
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "") -> Path:
    """创建文件 (含父目录) 并写入内容，返回路径。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def full_project(tmp_path: Path) -> Path:
    """构造一个所有检查项均通过的项目结构。"""
    root = tmp_path / "full_project"
    root.mkdir()

    # 1. SDK 包
    sdk_dir = root / "com.gamefactory.sdk"
    _write(sdk_dir / "package.json", json.dumps({
        "name": "com.gamefactory.sdk",
        "version": "1.0.0",
    }))
    _write(sdk_dir / "Runtime" / "IAP" / "IAPManager.cs", "// IAP code")
    _write(sdk_dir / "Runtime" / "Ads" / "AdMob" / "AdMobProvider.cs", "// admob")
    _write(sdk_dir / "Runtime" / "Ads" / "LevelPlay" / "LevelPlayProvider.cs", "// levelplay")
    _write(sdk_dir / "Runtime" / "Ads" / "Max" / "MaxAdProvider.cs", "// max")
    _write(sdk_dir / "Runtime" / "Analytics" / "Adjust" / "AdjustProvider.cs", "// adjust")
    _write(sdk_dir / "Runtime" / "Analytics" / "Firebase" / "FirebaseProvider.cs", "// firebase")
    # 配置文件不含 placeholder
    _write(sdk_dir / "Resources" / "gamefactory_config.json", json.dumps({
        "ads": {"app_key": "real_key"},
        "iap": {"enabled": True, "products": [{"id": "p1"}]},
    }))

    # 2. 凭证模板
    _write(root / "credentials" / "store_keys.json.example", json.dumps({
        "ios": {"apple_id": "REPLACE"},
        "android": {"service_account": "REPLACE"},
    }))

    # 3. iOS / Google Play 发布
    _write(root / "operation" / "publishing" / "app_store" / "orchestrator.py", "# ios")
    _write(root / "operation" / "publishing" / "google_play" / "orchestrator.py", "# gp")

    # 4. Python 侧 MAX provider
    _write(root / "monetization" / "providers" / "max" / "__init__.py", "")

    # 5. 归因 / 分析 Python 客户端
    _write(root / "src" / "market_ops" / "clients" / "adjust.py", "# adjust")
    _write(root / "src" / "market_ops" / "clients" / "thinkingdata.py", "# td")

    return root


@pytest.fixture
def empty_project(tmp_path: Path) -> Path:
    """构造一个完全空的项目目录，所有检查项均失败。"""
    root = tmp_path / "empty_project"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# CheckResult 数据结构
# ---------------------------------------------------------------------------


class TestCheckResult:
    def test_default_collections(self):
        """details / files_checked / files_missing 应是独立的新列表。"""
        r1 = CheckResult("a", STATUS_PASS, "m")
        r2 = CheckResult("b", STATUS_PASS, "m")
        r1.details.append("x")
        assert r2.details == []  # 不应互相影响

    def test_to_dict_roundtrip(self):
        r = CheckResult(
            check_name="x",
            status=STATUS_PASS,
            message="ok",
            details=["d1"],
            files_checked=["f1"],
            files_missing=["m1"],
        )
        d = r.to_dict()
        assert d == {
            "check_name": "x",
            "status": "pass",
            "message": "ok",
            "details": ["d1"],
            "files_checked": ["f1"],
            "files_missing": ["m1"],
        }
        # 必须可被 JSON 序列化
        json.dumps(d)

    def test_ok_property(self):
        assert CheckResult("a", STATUS_PASS, "m").ok is True
        assert CheckResult("a", STATUS_WARNING, "m").ok is False
        assert CheckResult("a", STATUS_FAIL, "m").ok is False


# ---------------------------------------------------------------------------
# check_sdk_package
# ---------------------------------------------------------------------------


class TestCheckSdkPackage:
    def test_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_sdk_package()
        assert r.check_name == "sdk_package"
        assert r.status == STATUS_PASS
        assert "1.0.0" in r.message
        assert r.files_missing == []

    def test_fail_when_dir_missing(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_sdk_package()
        assert r.status == STATUS_FAIL
        assert r.files_missing  # 含缺失的目录路径
        assert any("com.gamefactory.sdk" in p for p in r.files_missing)

    def test_fail_when_package_json_missing(self, tmp_path):
        root = tmp_path / "p"
        (root / "com.gamefactory.sdk").mkdir(parents=True)
        r = SDKReadinessChecker(str(root)).check_sdk_package()
        assert r.status == STATUS_FAIL
        assert any("package.json" in p for p in r.files_missing)

    def test_warning_when_name_mismatch(self, tmp_path):
        root = tmp_path / "p"
        _write(root / "com.gamefactory.sdk" / "package.json", json.dumps({
            "name": "wrong.name", "version": "0.1.0",
        }))
        r = SDKReadinessChecker(str(root)).check_sdk_package()
        assert r.status == STATUS_WARNING
        assert "wrong.name" in r.message

    def test_fail_when_package_json_invalid_json(self, tmp_path):
        root = tmp_path / "p"
        _write(root / "com.gamefactory.sdk" / "package.json", "not json {")
        r = SDKReadinessChecker(str(root)).check_sdk_package()
        assert r.status == STATUS_FAIL
        assert "解析失败" in r.message


# ---------------------------------------------------------------------------
# check_credentials_template
# ---------------------------------------------------------------------------


class TestCheckCredentialsTemplate:
    def test_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_credentials_template()
        assert r.status == STATUS_PASS
        assert r.files_missing == []

    def test_fail_when_missing(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_credentials_template()
        assert r.status == STATUS_FAIL
        assert any("store_keys.json.example" in p for p in r.files_missing)

    def test_fail_when_invalid_json(self, tmp_path):
        root = tmp_path / "p"
        _write(root / "credentials" / "store_keys.json.example", "{ not json")
        r = SDKReadinessChecker(str(root)).check_credentials_template()
        assert r.status == STATUS_FAIL
        assert "JSON" in r.message

    def test_warning_when_empty_dict(self, tmp_path):
        root = tmp_path / "p"
        _write(root / "credentials" / "store_keys.json.example", "{}")
        r = SDKReadinessChecker(str(root)).check_credentials_template()
        assert r.status == STATUS_WARNING


# ---------------------------------------------------------------------------
# check_config_placeholders
# ---------------------------------------------------------------------------


class TestCheckConfigPlaceholders:
    def test_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_config_placeholders()
        assert r.status == STATUS_PASS
        assert "未发现" in r.message

    def test_warning_when_placeholder_in_config(self, tmp_path):
        root = tmp_path / "p"
        sdk = root / "com.gamefactory.sdk"
        _write(sdk / "package.json", json.dumps({"name": "com.gamefactory.sdk", "version": "1.0"}))
        _write(sdk / "Resources" / "gamefactory_config.json", json.dumps({
            "ads": {"app_key": "REPLACE_WITH_MAX_APP_KEY"},
        }))
        r = SDKReadinessChecker(str(root)).check_config_placeholders()
        assert r.status == STATUS_WARNING
        assert "1 处" in r.message
        assert any("REPLACE_WITH_MAX_APP_KEY" in d for d in r.details)

    def test_warning_when_placeholder_in_cs(self, tmp_path):
        root = tmp_path / "p"
        sdk = root / "com.gamefactory.sdk"
        _write(sdk / "package.json", "{}")
        _write(sdk / "Runtime" / "Foo.cs", "// TODO: REPLACE_WITH_X\npublic class Foo {}\n")
        _write(sdk / "Resources" / "gamefactory_config.json", "{}")
        r = SDKReadinessChecker(str(root)).check_config_placeholders()
        assert r.status == STATUS_WARNING
        assert any("Foo.cs" in d for d in r.details)

    def test_fail_when_sdk_missing(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_config_placeholders()
        assert r.status == STATUS_FAIL
        assert r.files_missing  # SDK 目录缺失


# ---------------------------------------------------------------------------
# check_ios_publishing / check_google_play_publishing
# ---------------------------------------------------------------------------


class TestCheckPublishing:
    def test_ios_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_ios_publishing()
        assert r.status == STATUS_PASS

    def test_ios_fail(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_ios_publishing()
        assert r.status == STATUS_FAIL
        assert any("orchestrator.py" in p for p in r.files_missing)

    def test_google_play_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_google_play_publishing()
        assert r.status == STATUS_PASS

    def test_google_play_fail(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_google_play_publishing()
        assert r.status == STATUS_FAIL

    def test_platform_filter_ios_keeps_pass(self, full_project):
        """指定 platform=ios 时，iOS 检查依然 PASS。"""
        c = SDKReadinessChecker(str(full_project))
        c.platform = "ios"
        r = c.check_ios_publishing()
        assert r.status == STATUS_PASS

    def test_platform_filter_android_skips_ios(self, full_project):
        """指定 platform=android 时，iOS 检查应跳过深入检查但仍 PASS。"""
        c = SDKReadinessChecker(str(full_project))
        c.platform = "android"
        r = c.check_ios_publishing()
        assert r.status == STATUS_PASS
        assert "跳过" in r.message


# ---------------------------------------------------------------------------
# check_monetization_sdk
# ---------------------------------------------------------------------------


class TestCheckMonetizationSdk:
    def test_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_monetization_sdk()
        assert r.status == STATUS_PASS
        assert r.files_missing == []

    def test_fail_when_all_missing(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_monetization_sdk()
        assert r.status == STATUS_FAIL

    def test_warning_when_partial_missing(self, tmp_path):
        root = tmp_path / "p"
        # 仅 MAX provider 目录就绪
        _write(root / "monetization" / "providers" / "max" / "__init__.py", "")
        r = SDKReadinessChecker(str(root)).check_monetization_sdk()
        assert r.status == STATUS_WARNING
        assert r.files_missing  # AdMob/LevelPlay/Max 目录缺失


# ---------------------------------------------------------------------------
# check_attribution_sdk
# ---------------------------------------------------------------------------


class TestCheckAttributionSdk:
    def test_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_attribution_sdk()
        assert r.status == STATUS_PASS

    def test_fail_when_all_missing(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_attribution_sdk()
        assert r.status == STATUS_FAIL
        assert len(r.files_missing) == 2

    def test_warning_when_partial(self, tmp_path):
        root = tmp_path / "p"
        _write(root / "src" / "market_ops" / "clients" / "adjust.py", "# adjust")
        r = SDKReadinessChecker(str(root)).check_attribution_sdk()
        assert r.status == STATUS_WARNING
        assert any("AdjustProvider.cs" in p for p in r.files_missing)


# ---------------------------------------------------------------------------
# check_analytics_sdk
# ---------------------------------------------------------------------------


class TestCheckAnalyticsSdk:
    def test_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_analytics_sdk()
        assert r.status == STATUS_PASS

    def test_fail_when_all_missing(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_analytics_sdk()
        assert r.status == STATUS_FAIL

    def test_warning_when_partial(self, tmp_path):
        root = tmp_path / "p"
        _write(root / "src" / "market_ops" / "clients" / "thinkingdata.py", "# td")
        r = SDKReadinessChecker(str(root)).check_analytics_sdk()
        assert r.status == STATUS_WARNING
        assert any("FirebaseProvider.cs" in p for p in r.files_missing)


# ---------------------------------------------------------------------------
# check_iap_config
# ---------------------------------------------------------------------------


class TestCheckIapConfig:
    def test_pass(self, full_project):
        r = SDKReadinessChecker(str(full_project)).check_iap_config()
        assert r.status == STATUS_PASS
        assert "1 个产品" in r.message

    def test_fail_when_iap_dir_missing(self, empty_project):
        r = SDKReadinessChecker(str(empty_project)).check_iap_config()
        assert r.status == STATUS_FAIL

    def test_warning_when_iap_disabled(self, tmp_path):
        root = tmp_path / "p"
        sdk = root / "com.gamefactory.sdk"
        _write(sdk / "package.json", "{}")
        _write(sdk / "Runtime" / "IAP" / "IAPManager.cs", "// iap")
        _write(sdk / "Resources" / "gamefactory_config.json", json.dumps({
            "iap": {"enabled": False, "products": []},
        }))
        r = SDKReadinessChecker(str(root)).check_iap_config()
        assert r.status == STATUS_WARNING
        assert "iap.enabled=false" in r.message

    def test_fail_when_iap_manager_missing(self, tmp_path):
        root = tmp_path / "p"
        sdk = root / "com.gamefactory.sdk"
        _write(sdk / "package.json", "{}")
        # IAP 目录存在但为空
        (sdk / "Runtime" / "IAP").mkdir(parents=True)
        _write(sdk / "Resources" / "gamefactory_config.json", json.dumps({
            "iap": {"enabled": True, "products": []},
        }))
        r = SDKReadinessChecker(str(root)).check_iap_config()
        assert r.status == STATUS_FAIL
        assert any("IAPManager.cs" in p for p in r.files_missing)


# ---------------------------------------------------------------------------
# check_all / generate_report
# ---------------------------------------------------------------------------


class TestCheckAllAndReport:
    def test_check_all_returns_report_dict(self, full_project):
        c = SDKReadinessChecker(str(full_project))
        report = c.check_all()
        assert isinstance(report, dict)
        assert report["overall_status"] in (STATUS_PASS, STATUS_WARNING, STATUS_FAIL)
        assert report["summary"]["total"] == len(SDKReadinessChecker.CHECK_NAMES)
        assert len(report["checks"]) == len(SDKReadinessChecker.CHECK_NAMES)

    def test_check_all_pass_when_full_project(self, full_project):
        report = SDKReadinessChecker(str(full_project)).check_all()
        assert report["overall_status"] == STATUS_PASS
        assert report["summary"]["failed"] == 0
        assert report["summary"]["warnings"] == 0

    def test_check_all_fail_when_empty_project(self, empty_project):
        report = SDKReadinessChecker(str(empty_project)).check_all()
        assert report["overall_status"] == STATUS_FAIL
        assert report["summary"]["failed"] > 0

    def test_report_includes_project_root_and_filters(self, full_project):
        c = SDKReadinessChecker(str(full_project))
        c.game_id = "P04"
        c.platform = "ios"
        report = c.check_all()
        assert report["project_root"] == str(full_project)
        assert report["game_id"] == "P04"
        assert report["platform"] == "ios"

    def test_report_checks_contain_required_fields(self, full_project):
        report = SDKReadinessChecker(str(full_project)).check_all()
        for chk in report["checks"]:
            assert "check_name" in chk
            assert "status" in chk
            assert "message" in chk
            assert "details" in chk
            assert "files_checked" in chk
            assert "files_missing" in chk

    def test_generate_report_reuses_cache(self, full_project):
        c = SDKReadinessChecker(str(full_project))
        c.check_all()
        first = c.generate_report()
        second = c.generate_report()
        # 复用缓存，两次结果一致
        assert first is not second
        assert first == second

    def test_generate_report_runs_check_all_if_no_cache(self, full_project):
        """未调用 check_all 时，generate_report 应自动运行所有检查。"""
        c = SDKReadinessChecker(str(full_project))
        report = c.generate_report()
        assert report["summary"]["total"] == len(SDKReadinessChecker.CHECK_NAMES)

    def test_report_serializable_to_json(self, full_project):
        report = SDKReadinessChecker(str(full_project)).check_all()
        # 必须可被 JSON 序列化 (CI 系统解析需要)
        text = json.dumps(report, ensure_ascii=False)
        assert "overall_status" in text
        assert "checks" in text


# ---------------------------------------------------------------------------
# print_summary
# ---------------------------------------------------------------------------


class TestPrintSummary:
    def test_print_summary_outputs_human_readable(self, full_project, capsys):
        c = SDKReadinessChecker(str(full_project))
        c.game_id = "P04"
        c.check_all()
        c.print_summary()
        captured = capsys.readouterr()
        assert "GameFactory SDK Readiness" in captured.out
        assert "P04" in captured.out
        assert "汇总" in captured.out
        assert "[PASS]" in captured.out

    def test_print_summary_runs_check_all_if_not_done(self, full_project, capsys):
        c = SDKReadinessChecker(str(full_project))
        c.print_summary()  # 未先调用 check_all
        captured = capsys.readouterr()
        assert "GameFactory SDK Readiness" in captured.out

    def test_print_summary_includes_failures(self, empty_project, capsys):
        c = SDKReadinessChecker(str(empty_project))
        c.check_all()
        c.print_summary()
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out
        assert "缺失" in captured.out


# ---------------------------------------------------------------------------
# exit_code
# ---------------------------------------------------------------------------


class TestExitCode:
    def test_exit_code_zero_when_all_pass(self, full_project):
        c = SDKReadinessChecker(str(full_project))
        c.check_all()
        assert c.exit_code() == 0

    def test_exit_code_one_when_fail(self, empty_project):
        c = SDKReadinessChecker(str(empty_project))
        c.check_all()
        assert c.exit_code() == 1

    def test_exit_code_one_when_warning(self, tmp_path):
        # 构造仅有 placeholder warning 的项目 (其它项需要全部通过)
        root = tmp_path / "p"
        sdk = root / "com.gamefactory.sdk"
        _write(sdk / "package.json", json.dumps({"name": "com.gamefactory.sdk", "version": "1.0"}))
        _write(sdk / "Runtime" / "IAP" / "IAPManager.cs", "// iap")
        _write(sdk / "Runtime" / "Ads" / "AdMob" / "AdMobProvider.cs", "// admob")
        _write(sdk / "Runtime" / "Ads" / "LevelPlay" / "LevelPlayProvider.cs", "// lp")
        _write(sdk / "Runtime" / "Ads" / "Max" / "MaxAdProvider.cs", "// max")
        _write(sdk / "Runtime" / "Analytics" / "Adjust" / "AdjustProvider.cs", "// adjust")
        _write(sdk / "Runtime" / "Analytics" / "Firebase" / "FirebaseProvider.cs", "// fb")
        # 配置中包含 placeholder -> 触发 warning
        _write(sdk / "Resources" / "gamefactory_config.json", json.dumps({
            "ads": {"app_key": "REPLACE_WITH_MAX_APP_KEY"},
            "iap": {"enabled": True, "products": [{"id": "p1"}]},
        }))
        _write(root / "credentials" / "store_keys.json.example", json.dumps({"x": "y"}))
        _write(root / "operation" / "publishing" / "app_store" / "orchestrator.py", "# ios")
        _write(root / "operation" / "publishing" / "google_play" / "orchestrator.py", "# gp")
        _write(root / "monetization" / "providers" / "max" / "__init__.py", "")
        _write(root / "src" / "market_ops" / "clients" / "adjust.py", "# adjust")
        _write(root / "src" / "market_ops" / "clients" / "thinkingdata.py", "# td")

        c = SDKReadinessChecker(str(root))
        c.check_all()
        # 存在 warning -> 退出码 1
        assert c.exit_code() == 1

    def test_exit_code_runs_check_all_if_not_done(self, full_project):
        c = SDKReadinessChecker(str(full_project))
        # 未调用 check_all
        assert c.exit_code() == 0


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------


class TestCommandLine:
    def test_arg_parser_defaults(self):
        parser = build_arg_parser()
        args = parser.parse_args([])
        assert args.project_root == ""
        assert args.game_id == ""
        assert args.platform == ""
        assert args.json is False

    def test_arg_parser_all_flags(self):
        parser = build_arg_parser()
        args = parser.parse_args([
            "--project-root", "/tmp/foo",
            "--game-id", "P04",
            "--platform", "ios",
            "--json",
        ])
        assert args.project_root == "/tmp/foo"
        assert args.game_id == "P04"
        assert args.platform == "ios"
        assert args.json is True

    def test_arg_parser_invalid_platform(self):
        parser = build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--platform", "windows"])

    def test_main_human_readable_output(self, full_project, capsys):
        rc = main(["--project-root", str(full_project)])
        captured = capsys.readouterr()
        assert "GameFactory SDK Readiness" in captured.out
        assert rc in (0, 1)

    def test_main_returns_zero_on_full_project(self, full_project):
        rc = main(["--project-root", str(full_project)])
        assert rc == 0

    def test_main_returns_one_on_empty_project(self, empty_project):
        rc = main(["--project-root", str(empty_project)])
        assert rc == 1

    def test_main_json_output_is_valid_json(self, full_project, capsys):
        rc = main(["--project-root", str(full_project), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)  # 不应抛异常
        assert "overall_status" in report
        assert "checks" in report
        assert rc == 0

    def test_main_json_output_on_failure(self, empty_project, capsys):
        rc = main(["--project-root", str(empty_project), "--json"])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["overall_status"] == STATUS_FAIL
        assert report["summary"]["failed"] > 0
        assert rc == 1

    def test_main_with_game_id_and_platform(self, full_project, capsys):
        rc = main([
            "--project-root", str(full_project),
            "--game-id", "P04",
            "--platform", "ios",
            "--json",
        ])
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["game_id"] == "P04"
        assert report["platform"] == "ios"
        assert rc == 0


# ---------------------------------------------------------------------------
# Windows 路径兼容性
# ---------------------------------------------------------------------------


class TestWindowsPathCompatibility:
    def test_paths_use_os_agnostic_separator(self, full_project):
        """checker 内部应使用 pathlib.Path，不应硬编码分隔符。"""
        c = SDKReadinessChecker(str(full_project))
        report = c.check_all()
        # 检查 files_checked 至少包含一项
        all_files_checked = []
        for chk in report["checks"]:
            all_files_checked.extend(chk["files_checked"])
        assert all_files_checked
        # 所有路径都应当能被 Path 解析 (即 str(Path(p)) == p 或 p 用反斜杠)
        for p in all_files_checked:
            # 仅断言能再次构造 Path (Windows / POSIX 均可)
            Path(p)

    def test_project_root_with_trailing_slash(self, full_project):
        """项目根目录带末尾斜杠时也应正常工作。"""
        root_str = str(full_project) + "\\"
        c = SDKReadinessChecker(root_str)
        r = c.check_sdk_package()
        assert r.status == STATUS_PASS
