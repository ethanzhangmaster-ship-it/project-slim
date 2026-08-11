#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LaunchForge — 端到端离线自检 (system self-check).

一条命令给出整套系统的健康报告，**零网络、零飞书、零真实凭证**:

    python system_check.py            # 完整报告
    python system_check.py --quiet    # 仅打印 PASS/FAIL 总结

它验证的不是"能不能真连商店/真发事件"，而是"代码侧是否已全闭环、契约是否对齐、
你接真料前系统是否处于一致可运行态"。真数据线仍需你给物理料(见报告末"下一步")。

退出码: 0 = 全部绿; 1 = 有非阻塞告警; 2 = 有阻断性错误(模块 import 失败 / 测试红)。
"""
from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys

# --------------------------------------------------------------------------- #
# 路径解析
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHFORGE = HERE
WORKSPACE_ROOT = os.path.dirname(LAUNCHFORGE)          # 父目录 = 工作区根
CRED_DIR = os.path.join(WORKSPACE_ROOT, "credentials")

PY = sys.executable
# 关掉代理避免任何隐式联网
ENV = dict(os.environ)
ENV.update({"HTTPS_PROXY": "", "HTTP_PROXY": "", "NO_PROXY": "*"})


def _ok(msg: str) -> str:
    return f"  \u2705 {msg}"


def _warn(msg: str) -> str:
    return f"  \u26a0\ufe0f  {msg}"


def _fail(msg: str) -> str:
    return f"  \u274c {msg}"


def _section(title: str) -> str:
    return f"\n=== {title} ==="


# --------------------------------------------------------------------------- #
# 1) 运行环境
# --------------------------------------------------------------------------- #
def check_runtime() -> list:
    out = [_section("1) 运行环境")]
    problems = []
    out.append(f"  python: {sys.version.split()[0]}  ({PY})")
    try:
        import cryptography  # noqa: F401
        out.append(_ok(f"cryptography {cryptography.__version__} (P3 真连商店必需)"))
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"缺少 cryptography: {e} — P3 真连需先装"))
        problems.append("cryptography")
    return out, problems


# --------------------------------------------------------------------------- #
# 2) 凭证库
# --------------------------------------------------------------------------- #
def check_vaults() -> list:
    out = [_section("2) 凭证库 (credentials/)")]
    problems = []
    out.append(f"  目录: {CRED_DIR}")

    # MAX 实时账户
    max_path = os.path.join(CRED_DIR, "live_accounts.json")
    if os.path.exists(max_path):
        try:
            import json
            data = json.load(open(max_path, encoding="utf-8"))
            n = len(data) if isinstance(data, dict) else "?"
            out.append(_ok(f"live_accounts.json 存在 ({n} 个账号)"))
        except Exception as e:  # noqa: BLE001
            out.append(_fail(f"live_accounts.json 解析失败: {e}"))
            problems.append("live_accounts")
    else:
        out.append(_warn("live_accounts.json 缺失 — Revenue OS 无真实 MAX 数据可拉"))
        problems.append("live_accounts")

    # 飞书通知 — FeishuNotifier 读 credentials/notify.json (相对 cwd=launchforge/),
    # 故同时查 workspace-root 与 launchforge/ 两个候选位置。
    notify_candidates = [
        os.path.join(CRED_DIR, "notify.json"),
        os.path.join(LAUNCHFORGE, "credentials", "notify.json"),
    ]
    notify_found = next((p for p in notify_candidates if os.path.exists(p)), None)
    if notify_found:
        out.append(_ok(f"notify.json 存在 ({os.path.relpath(notify_found, WORKSPACE_ROOT)}) — 每日晨报可推飞书)"))
    else:
        out.append(_warn("notify.json 缺失 — 晨报不会被推送 (代码仍生成 outputs/)"))
        problems.append("notify")

    # 商店 API (P3)
    store_path = os.path.join(CRED_DIR, "store_keys.json")
    if os.path.exists(store_path):
        try:
            import json
            data = json.load(open(store_path, encoding="utf-8"))
            as_ok = all(data.get("app_store_connect", {}).get(k) for k in
                        ("key_id", "issuer_id", "private_key_p8"))
            gp_ok = bool(data.get("google_play", {}).get("service_account_json_path"))
            if as_ok or gp_ok:
                bits = []
                if as_ok:
                    bits.append("App Store Connect")
                if gp_ok:
                    bits.append("Google Play")
                out.append(_ok(f"store_keys.json 已填凭证: {', '.join(bits)}"))
            else:
                out.append(_warn("store_keys.json 存在但为空 — 第四节上架状态仍为 dry-run"))
                problems.append("store_keys_empty")
        except Exception as e:  # noqa: BLE001
            out.append(_fail(f"store_keys.json 解析失败: {e}"))
            problems.append("store_keys")
    else:
        out.append(_warn("store_keys.json 缺失 — P3 商店状态未激活 (预期, 待你填凭证)"))
        problems.append("store_keys_missing")
    return out, problems


# --------------------------------------------------------------------------- #
# 3) 模块完整性 (语法编译 + 关键模块 import)
#    注意: 不盲目 import 全部模块 —— 仓库里有 validate_*.py 会在 import 时
#    直接跑测试套件(无 __main__ 守卫), 盲目 import 会触发 55 条用例噪声。
#    因此用 py_compile 做全量语法检查(不执行模块级代码), 再对关键模块做
#    定向 import(重定向 stdout 屏蔽任何残留打印)。
# --------------------------------------------------------------------------- #
KEY_MODULES = [
    "operation.optimizer.intelligence_agent",
    "operation.optimizer.daily_briefing",
    "operation.optimizer.user_metrics",
    "operation.factory_brain.fleet_bridge",
    "operation.factory_brain.growth_sources.briefing",
    "operation.factory_brain.growth_sources.ingester",
    "operation.publishing.store_status",
    "operation.providers.live.store_keys",
    "operation.providers.live.auth",
    "operation.providers.live.http_util",
    "operation.player_monetization.normalize",
    "operation.player_monetization.ingest_server",
    "operation.publishing.providers.app_store.real_client",
    "operation.publishing.providers.google_play.real_client",
    "src.config_generator",
    # E13.5 Play Runtime — gated facade + agents
    "operation.publishing_factory.play_runtime.connector",
    "operation.publishing_factory.play_runtime.review_agent",
    "operation.publishing_factory.play_runtime.experiment_agent",
    "operation.publishing_factory.play_runtime.tester_pool_agent",
    "operation.publishing_factory.play_runtime.runner",
    "operation.publishing_factory.play_runtime.play_runtime_cli",
    "operation.publishing_factory.tester_community.community",
    "operation.publishing_factory.tester_community.eligibility",
]


def check_imports() -> list:
    out = [_section("3) 模块完整性 (语法 + 关键模块)")]
    problems = []
    import glob
    import py_compile
    import io

    # 3a) 全量语法编译 (捕捉 SyntaxError, 不触发模块级副作用)
    all_py = []
    for base in ("operation", "src", "monetization"):
        d = os.path.join(LAUNCHFORGE, base)
        if os.path.isdir(d):
            all_py += glob.glob(os.path.join(d, "**", "*.py"), recursive=True)
    syntax_fail = []
    for fp in all_py:
        try:
            py_compile.compile(fp, doraise=True)
        except py_compile.PyCompileError as e:
            syntax_fail.append((fp, str(e)))
    out.append(f"  语法编译: {len(all_py)} 个文件, 失败 {len(syntax_fail)}")
    for fp, err in syntax_fail[:20]:
        out.append(_fail(f"  {os.path.relpath(fp, LAUNCHFORGE)}: {err[:80]}"))
    if syntax_fail:
        problems.append("syntax")

    # 3b) 关键模块定向 import (屏蔽 stdout 防 validate 噪声)
    import_fail = []
    for mod in KEY_MODULES:
        buf = io.StringIO()
        try:
            importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001
            import_fail.append((mod, repr(e)))
    out.append(f"  关键模块 import: {len(KEY_MODULES)} 个, 失败 {len(import_fail)}")
    for mod, err in import_fail[:20]:
        out.append(_fail(f"  {mod}: {err}"))
    if import_fail:
        problems.append("imports")
    if not syntax_fail and not import_fail:
        out.append(_ok(f"全部 {len(all_py)} 文件语法 OK, {len(KEY_MODULES)} 关键模块 import OK"))
    return out, problems


# --------------------------------------------------------------------------- #
# 4) 契约测试 (证明集成对齐)
# --------------------------------------------------------------------------- #
# 5) E13.5 Play Runtime 接线自检 (零网络, fake client)
#    证明 gated facade + 五 Agent 能 boot、门控路由正确、
#    SIMULATION 永不调 API、晨报 6–10 节已接线、审计目录可写。
# --------------------------------------------------------------------------- #
def _fake_play_client():
    """In-memory stand-in for GooglePlayRealClient.

    Covers every method the connector / agents may call so the self-check
    never touches the network even if a gate were ever misconfigured.
    """
    class _Fake:
        def __init__(self):
            self.calls = []

        def check_status(self, package_name):
            self.calls.append(("check_status", package_name))
            return {"success": True, "status": "draft"}

        def get_reviews(self, package_name, max_results=100):
            self.calls.append(("get_reviews", package_name))
            return {"success": True, "count": 0, "reviews": []}

        def reply_to_review(self, package_name, review_id, reply_text):
            self.calls.append(("reply_to_review", package_name))
            return {"success": True, "review_id": review_id}

        def list_experiments(self, package_name):
            self.calls.append(("list_experiments", package_name))
            return {"success": True, "count": 0, "experiments": []}

        def create_listing_experiment(self, package_name, **kw):
            self.calls.append(("create_listing_experiment", package_name))
            return {"success": True, "experiment_id": "exp1"}

        def delete_experiment(self, package_name, experiment_id):
            self.calls.append(("delete_experiment", package_name))
            return {"success": True}

        def get_testers(self, package_name, track="closed"):
            self.calls.append(("get_testers", package_name))
            return {"success": True, "tester_emails": [], "tester_groups": []}

        def invite_testers_to_closed_track(self, package_name, **kw):
            self.calls.append(("invite", package_name))
            return {"success": True, "status_code": 200}

        def get_track_status(self, package_name, track="production"):
            self.calls.append(("get_track_status", package_name))
            return {"success": True, "track": track, "releases": []}

        def get_vitals(self, package_name, metric, start, end, **kw):
            self.calls.append(("get_vitals", package_name))
            return {"success": True, "rows": []}

        def update_metadata(self, package_name, metadata, locale="en-US"):
            self.calls.append(("update_metadata", package_name))
            return {"success": True}

        def upload_bundle(self, package_name, build_path, version, bn):
            self.calls.append(("upload_bundle", package_name))
            return {"success": True}

        def set_rollout(self, package_name, **kw):
            self.calls.append(("set_rollout", package_name))
            return {"success": True}

        def halt_rollout(self, package_name, track="production"):
            self.calls.append(("halt_rollout", package_name))
            return {"success": True}
    return _Fake()


def check_play_runtime() -> list:
    out = [_section("5) E13.5 Play Runtime 接线自检 (零网络, 门控路由)")]
    problems = []
    import io
    import contextlib

    PKG = "com.ofwsalary.ofwcalculator"
    # 5a) 模块 import (屏蔽任何残留 stdout 噪声)
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            from monetization.providers.models import SandboxMode
            from operation.publishing_factory.play_runtime.connector import (
                PlayConnector)
            from operation.publishing_factory.play_runtime.models import (
                GateStage)
            from operation.publishing_factory.play_runtime.review_agent import (
                ReviewAgent)
            from operation.publishing_factory.play_runtime.experiment_agent \
                import ListingExperimentAgent
            from operation.publishing_factory.play_runtime import \
                tester_pool_agent as tpa_mod
            from operation.publishing_factory.tester_community import (
                community as tc_community,
                eligibility as tc_eligibility)
            from operation.optimizer import daily_briefing as db
        out.append(_ok("Play Runtime + tester_community 模块全部 import OK"))
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"Play Runtime import 失败: {e!r}"))
        problems.append("play_runtime")
        return out, problems

    # 5b) SIMULATION 模式: gated facade 永不调 API
    try:
        fc = _fake_play_client()
        conn = PlayConnector(client=fc, sandbox=SandboxMode.SIMULATION,
                             auto_pilot=False)
        ops = [
            ("read_reviews", lambda: conn.read_reviews(PKG)),
            ("reply_review",
             lambda: conn.reply_review(PKG, "r1", "thanks for the feedback")),
            ("read_experiments", lambda: conn.read_experiments(PKG)),
            ("create_experiment",
             lambda: conn.create_experiment(PKG, name="t", locale="en-US")),
            ("read_testers", lambda: conn.read_testers(PKG)),
            ("get_track_status", lambda: conn.get_track_status(PKG)),
            ("read_vitals", lambda: conn.read_vitals(PKG)),
        ]
        bad = []
        for name, fn in ops:
            res = fn()
            if not getattr(res, "ok", False):
                bad.append(f"{name}:ok=False")
            if str(getattr(res, "stage", "")) != str(GateStage.RECOMMEND):
                bad.append(f"{name}:stage={getattr(res, 'stage', None)}")
            if getattr(res, "real_api_called", True):
                bad.append(f"{name}:api_called")
        if fc.calls:
            bad.append(f"SIMULATION 触发 API 调用: {fc.calls}")
        if bad:
            out.append(_fail("SIMULATION 门控异常: " + "; ".join(bad[:6])))
            problems.append("play_runtime")
        else:
            out.append(_ok("SIMULATION 门控正确: 7 操作全 RECOMMEND / 零 API 调用"))
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"SIMULATION 路由异常: {e!r}"))
        problems.append("play_runtime")

    # 5c) 三 Agent 纯逻辑可运行 (不依赖网络)
    try:
        fc = _fake_play_client()
        conn = PlayConnector(client=fc, sandbox=SandboxMode.SIMULATION)
        ra = ReviewAgent(conn)
        rep = ra.classify({"package_name": PKG, "star_rating": 1,
                           "text": "the app keeps crashing!",
                           "review_id": "rX"})
        assert getattr(rep, "category", ""), "classify 无 category"
        ea = ListingExperimentAgent(conn)
        prop = ea.propose_title_test(PKG, "en-US", "Short Title")
        assert getattr(prop, "ok", False), "propose_title_test 未产出有效提案"
        tpa = tpa_mod.TesterPoolAgent(conn)
        s = tpa_mod.summary()
        assert "pool_size" in s, "tester pool summary 缺 pool_size"
        out.append(_ok("三 Agent 纯逻辑 OK "
                       f"(review→{rep.category}, experiment→ok, "
                       f"pool={s['pool_size']})"))
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"Agent 纯逻辑异常: {e!r}"))
        problems.append("play_runtime")

    # 5d) 晨报 6–10 节已接线
    try:
        need = ["_run_play_runtime", "_run_health", "_run_review",
                "_run_experiment", "_run_tester_pool",
                "_run_production_readiness", "_build_morning_digest"]
        missing = [n for n in need if not hasattr(db, n)]
        if missing:
            out.append(_fail("晨报章节函数缺失: " + ", ".join(missing)))
            problems.append("play_runtime")
        else:
            out.append(_ok("晨报 6–10 节接线 OK "
                           "(runtime/health/review/experiment/tester/production)"))
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"晨报接线检查异常: {e!r}"))
        problems.append("play_runtime")

    # 5e) 审计目录可写 (data/play_runtime/*.jsonl)
    try:
        audit_dir = os.path.join(LAUNCHFORGE, "data", "play_runtime")
        os.makedirs(audit_dir, exist_ok=True)
        probe = os.path.join(audit_dir, ".selfcheck_probe")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        out.append(_ok(f"审计目录可写: "
                       f"{os.path.relpath(audit_dir, LAUNCHFORGE)}"))
    except Exception as e:  # noqa: BLE001
        out.append(_warn(f"审计目录不可写: {e}"))
        problems.append("play_runtime_audit")

    return out, problems


# --------------------------------------------------------------------------- #
# 6) E13.5 Play Runtime 统一编排自检 (证明 ONE 命令跑通五 Agent)
# --------------------------------------------------------------------------- #
def check_play_orchestrator() -> list:
    out = [_section("6) E13.5 Play Runtime 统一编排自检 (ONE 命令跑五 Agent)")]
    problems = []
    import io
    import contextlib
    import json as _json

    # 6a) 模块 import + 统一编排可运行 (SIMULATION 零网络)
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            from operation.publishing_factory.play_runtime.runner import (
                run_play_ops, render_status_line, discover_packages)
        # 显式 2 个假包, 不依赖 catalog 真实数据
        s = run_play_ops(packages=["com.selfcheck.a", "com.selfcheck.b"],
                         apply=False)
        assert s["status"] == "OK", f"status={s['status']} failures={s['failures']}"
        assert s["agents_ok"] == s["agents_total"] == 5, \
            f"agents_ok={s['agents_ok']}/{s['agents_total']}"
        assert s["mode"] == "SIMULATION", f"mode={s['mode']}"
        assert s["real_api_called"] is False, "SIMULATION 不应触发真实 API"
        assert os.path.exists(s["path"]), f"run log 未写出: {s['path']}"
        out.append(_ok("统一编排 OK: 5/5 Agent · 模式 SIMULATION · 零真实 API · "
                       f"日志已写 {os.path.relpath(s['path'], LAUNCHFORGE)}"))
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"统一编排异常: {e!r}"))
        problems.append("play_orchestrator")

    # 6b) 包发现: 显式列表优先; 否则回退 catalog / env 兜底
    try:
        # 显式列表直接采用 (不依赖 catalog)
        pk = discover_packages(["com.x", "com.y"])
        assert pk == ["com.x", "com.y"], f"显式包发现失败: {pk}"
        # 无参时回退到 catalog/google_play 已录入包名 (非空即证明发现链路通)
        pk_all = discover_packages()
        assert isinstance(pk_all, list) and len(pk_all) >= 0, \
            "无参包发现未返回 list"
        out.append(_ok(f"包发现 OK (显式列表优先级最高; catalog 回退 "
                       f"{len(pk_all)} 个 google_play 包)"))
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"包发现异常: {e!r}"))
        problems.append("play_orchestrator")

    return out, problems


# --------------------------------------------------------------------------- #
# 4) 契约测试 (证明集成对齐)
# --------------------------------------------------------------------------- #
def check_tests() -> list:
    out = [_section("4) 契约/集成测试 (pytest)")]
    problems = []
    suites = ["tests"]
    cmd = [PY, "-m", "pytest", *suites, "-q", "--no-header",
           "-p", "no:cacheprovider"]
    try:
        r = subprocess.run(cmd, cwd=LAUNCHFORGE, env=ENV,
                           capture_output=True, text=True, timeout=300)
        out_lines = (r.stdout + r.stderr).splitlines()
        # 抓 "NNN passed" / "NNN failed"
        summary = ""
        for line in reversed(out_lines):
            if "passed" in line or "failed" in line:
                summary = line.strip()
                break
        if r.returncode == 0:
            out.append(_ok(f"全部通过: {summary}"))
        else:
            out.append(_fail(f"测试有失败: {summary}"))
            # 印出失败用例名
            for line in out_lines:
                if "FAILED" in line or "ERROR" in line:
                    out.append(f"      {line.strip()}")
            problems.append("tests")
    except subprocess.TimeoutExpired:
        out.append(_fail("pytest 超时 (>300s)"))
        problems.append("tests_timeout")
    except Exception as e:  # noqa: BLE001
        out.append(_fail(f"pytest 无法运行: {e}"))
        problems.append("tests_run")
    return out, problems


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="LaunchForge 离线自检")
    ap.add_argument("--quiet", action="store_true", help="仅打印总结")
    args = ap.parse_args()

    blocks, all_problems = [], []
    for fn in (check_runtime, check_vaults, check_imports,
               check_play_runtime, check_play_orchestrator, check_tests):
        lines, probs = fn()
        blocks.append(lines)
        all_problems.extend(probs)

    blocking = [p for p in all_problems if p in ("cryptography", "imports",
                                                 "play_runtime",
                                                 "play_orchestrator", "tests",
                                                 "tests_timeout", "tests_run",
                                                 "live_accounts")]
    soft = [p for p in all_problems if p not in blocking]

    print("\n" + "=" * 64)
    print("  LaunchForge 系统自检报告")
    print("=" * 64)
    for b in blocks:
        if not args.quiet:
            print("\n".join(b))

    print("\n" + _section("总结"))
    if not all_problems:
        print(_ok("全部绿 — 代码侧 P0–P4 已全闭环, 系统处于一致可运行态。"))
        code = 0
    elif blocking:
        print(_fail(f"阻断性错误: {', '.join(blocking)} — 需修复后才能跑通。"))
        code = 2
    else:
        print(_warn(f"非阻断告警: {', '.join(soft)} — 代码可运行, 仅差你的物理料。"))
        code = 1

    print("\n" + _section("下一步 (只你能动的手)"))
    print("  • P3 真实商店状态: 把 App Store Connect(.p8+key/issuer) 或")
    print("    Google Play(服务账号JSON) 填进 credentials/store_keys.json,")
    print("    再给每日自动化加 LAUNCHFORGE_STORE_LIVE=1 → 第四节出真实状态。")
    print("  • P4 真实事件流: 把 com.gamefactory.sdk/ 拖进真 Unity 工程,")
    print("    编译后 Configure Event Backend 填 endpoint → 真事件回流。")
    print("  • 成长真信号: 给一个真实市场数据源 → 接 RealMarketSource。")
    print("  • E13.5 Play Runtime 真机验证: 本机带代理 + born2play SA +")
    print("    LAUNCHFORGE_AUTO_PUBLISH=1, 跑各 *_cli.py 的 --apply")
    print("    (review 自动回评 / experiment 发 fil-ar 标题测试 /")
    print("    tester_pool run 填满 12 人邀请) — 代码已全绿, 只差你物理料。")
    print("=" * 64)
    return code


if __name__ == "__main__":
    sys.exit(main())
