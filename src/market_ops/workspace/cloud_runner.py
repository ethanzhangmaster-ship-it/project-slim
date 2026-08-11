"""云端可执行的 ASO 自动优化 CLI 入口.

与机器/账号/关机状态解耦的命令行工具.
每次运行是独立、无状态的:
  - 从 STATE_STORE 读入历史 (自动续跑断点)
  - 执行: 单产品或全量优化循环
  - 把结果写回 STATE_STORE
  - 退出 (GitHub Actions cron 会在第二天再触发一次)

可直接被任何 cron 系统 (GitHub Actions / GitLab CI / Cloud Scheduler / Windows 任务计划 / cron)
或任何其他机器 (换电脑、换 IDE 账号、离线) 调用.

用法:
    # 跑一次 bible quiz 单产品
    python -m market_ops.workspace.cloud_runner --game com.born2play.biblequiz

    # 跑一次全量 + 生成日报
    python -m market_ops.workspace.cloud_runner --all --dashboard

    # 只输出多渠道推广任务清单 (不执行优化)
    python -m market_ops.workspace.cloud_runner --multichannel-plan com.born2play.biblequiz

    # 验证 STATE_STORE 连接
    python -m market_ops.workspace.cloud_runner --healthcheck

退出码:
    0  成功
    1  参数错误
    2  STATE_STORE 健康检查失败
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from .state_store import StateStore, get_state_store

logger = logging.getLogger("cloud_runner")


def _setup_logging() -> None:
    level = os.environ.get("CLOUD_RUNNER_LOGLEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_dotenv_if_available() -> None:
    """仅当本地有 .env 文件时加载 (CI/云端不走这里, 用 env/secret)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for candidate in (".env", ".env.local", "workspace/.env.local"):
        if os.path.isfile(candidate):
            load_dotenv(candidate, override=False)  # 不覆盖已设 env


def _startup_recovery(store: StateStore) -> Dict[str, Any]:
    """启动时断点续跑检查.

    检查策略:
      - 如果有最近的 in_progress 记录 (超过 1h 未更新), 视为崩溃中断,
        回滚到 pending 状态, retry_count += 1
      - 返回 recovery 报告 (写入日志 + 上传到 store)
    """
    report: Dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "interrupted_tasks_recovered": 0,
        "details": [],
    }
    # 检查所有运行中的 cycle 标记文件
    lock_keys = [k for k in store.list_keys(".locks/") if k.endswith(".lock.json")]
    import time as _time
    now = _time.time()
    for lk in lock_keys:
        lock = store.read_json(lk)
        if not isinstance(lock, dict):
            continue
        started = lock.get("started_ts", 0)
        status = lock.get("status")
        if status == "in_progress" and (now - started) > 3600:  # 1h 超时
            lock["status"] = "recovered_pending"
            lock["recovered_at"] = datetime.now(timezone.utc).isoformat()
            lock["retry_count"] = lock.get("retry_count", 0) + 1
            store.write_json(lk, lock)
            report["interrupted_tasks_recovered"] += 1
            report["details"].append(
                {"lock": lk, "game_id": lock.get("game_id"), "prev_retry": lock.get("retry_count", 0) - 1}
            )
    if report["interrupted_tasks_recovered"]:
        store.append_jsonl(
            "aso_deploy/recovery_log.jsonl",
            report,
        )
        logger.warning(
            f"[recovery] 检测到 {report['interrupted_tasks_recovered']} 个中断任务, "
            f"已推回 pending 状态并增加 retry_count"
        )
    return report


def _healthcheck(store: StateStore) -> int:
    result = store.health_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


def _run_single(store: StateStore, game_id: str, force_new_variant: bool = False) -> Dict[str, Any]:
    """运行单产品自动优化循环 (使用 state_store 中的持久化配置)."""
    # 惰性导入 — 避免 --healthcheck 时加载重型依赖
    from .aso_optimization_loop import get_aso_optimization_loop

    # 为了让优化循环也走可移植 state_store, 临时把 data_dir 映射到 state backend root
    # 注意: LocalFS 后端时 data_dir 直接取 LocalFS.root; 云端后端会在本地 cache 一份再上传
    data_dir = _resolve_local_data_dir(store)
    project_root = os.environ.get("CLOUD_PROJECT_ROOT", os.getcwd())

    loop = get_aso_optimization_loop(
        data_dir=data_dir,
        project_root=project_root,
    )
    result = loop.run_single_game_auto_cycle(
        game_id=game_id,
        force_new_variant=force_new_variant,
    )
    # 运行完后云端后端需要把本地改动同步回去
    _sync_local_back_to_cloud_if_needed(store, data_dir)
    return result


def _run_all(store: StateStore, dashboard: bool = False) -> Dict[str, Any]:
    from .aso_optimization_loop import get_aso_optimization_loop

    data_dir = _resolve_local_data_dir(store)
    project_root = os.environ.get("CLOUD_PROJECT_ROOT", os.getcwd())
    loop = get_aso_optimization_loop(
        data_dir=data_dir,
        project_root=project_root,
    )
    result = loop.run_cycle()
    _sync_local_back_to_cloud_if_needed(store, data_dir)
    if dashboard:
        try:
            dash = loop.get_dashboard()
            dash_dict = dash.to_dict() if hasattr(dash, "to_dict") else dash.__dict__
            report_key = f"aso_deploy/dashboard/daily_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
            store.write_json(report_key, dash_dict)
            result["dashboard_report"] = report_key
        except Exception as e:
            logger.exception("dashboard 生成失败")
            result["dashboard_error"] = f"{type(e).__name__}: {e}"
    return result


def _run_multichannel_plan(store: StateStore, game_id: str) -> Dict[str, Any]:
    from .multichannel_organic_engine import get_multichannel_organic_engine
    from .aso_optimization_loop import get_aso_optimization_loop

    data_dir = _resolve_local_data_dir(store)
    project_root = os.environ.get("CLOUD_PROJECT_ROOT", os.getcwd())
    loop = get_aso_optimization_loop(data_dir=data_dir, project_root=project_root)
    games = loop.get_games()
    game = next((g for g in games if g.game_id == game_id), None)
    engine = get_multichannel_organic_engine()
    plan = engine.generate_growth_plan(
        game_id=game_id,
        package_name=game.package_name if game else game_id,
        game_display_name=game.display_name if game else "",
        genre=game.genre if game else "casual",
    )
    report_key = f"aso_deploy/{game_id}/multichannel_plan_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    store.write_json(report_key, plan.to_dict())
    return {"saved_to": report_key, "channels": len(plan.channels),
            "estimated_30d_installs": plan.estimated_30d_installs}


# ── LocalFS 桥接: 云端后端时本地缓存目录 ────────────────────────
# 说明: 现有 aso_optimization_loop 写的是本地文件.
# 当 store 为 gist/s3 时, cloud_runner 会:
#   1) 在启动时把云端内容同步到临时目录 LOCAL_CACHE
#   2) 循环跑 (写本地)
#   3) 跑完后把变化的文件再写回云端
# 这样零侵入现有业务逻辑, 同时状态在云端持久.

def _cache_dir_for_cloud(store: StateStore) -> str:
    import tempfile
    d = os.environ.get("CLOUD_RUNNER_CACHE_DIR")
    if not d:
        d = tempfile.mkdtemp(prefix=f"market_ops_state_{store.backend}_")
    os.makedirs(d, exist_ok=True)
    return d


def _resolve_local_data_dir(store: StateStore) -> str:
    if isinstance(store, StateStore) and store.backend == "local":
        # LocalFS: 直接用它的 root (保持向后兼容)
        import inspect
        src = inspect.getsource(store.__class__.__init__)  # skip
        return str(getattr(store, "_root", Path("data")))
    # 云端后端: 先下载到本地缓存目录
    cache_dir = _cache_dir_for_cloud(store)
    for k in store.list_keys():
        try:
            if k.endswith(".json") or k.endswith(".jsonl") or k.endswith(".md"):
                if k.endswith(".json"):
                    data = store.read_json(k)
                    if data is not None:
                        tgt = os.path.join(cache_dir, k)
                        os.makedirs(os.path.dirname(tgt), exist_ok=True)
                        with open(tgt, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                elif k.endswith(".jsonl"):
                    records = store.read_jsonl(k)
                    tgt = os.path.join(cache_dir, k)
                    os.makedirs(os.path.dirname(tgt), exist_ok=True)
                    with open(tgt, "a", encoding="utf-8") as f:
                        for r in records:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
                else:
                    # 文本文件 (md) 以 json 里 content 字段存 (占位策略)
                    tgt = os.path.join(cache_dir, k)
                    os.makedirs(os.path.dirname(tgt), exist_ok=True)
                    raw = store.read_json(k)
                    if isinstance(raw, dict) and "__text__" in raw:
                        with open(tgt, "w", encoding="utf-8") as f:
                            f.write(raw["__text__"])
        except Exception as e:
            logger.warning(f"预下载 {k} 到缓存失败 (忽略继续): {e}")
    logger.info(f"[state_bridge] 云端状态预下载完成, cache_dir={cache_dir}")
    return cache_dir


def _sync_local_back_to_cloud_if_needed(store: StateStore, local_data_dir: str) -> None:
    if store.backend == "local":
        return  # LocalFS 无需回传
    logger.info(f"[state_bridge] 上传本地缓存到 {store.backend} 后端...")
    root = Path(local_data_dir)
    uploaded = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        try:
            if rel.endswith(".json"):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                store.write_json(rel, data)
                uploaded += 1
            elif rel.endswith(".jsonl"):
                # 简单策略: 全量读取后按条 append 到云端 (若云端空则直接写)
                with open(path, "r", encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f.readlines() if ln.strip()]
                if not store.exists(rel):
                    # 空的话先写个桩再逐条 append
                    store.write_json(rel + ".bootstrap", {"__placeholder": True})
                for ln in lines:
                    try:
                        store.append_jsonl(rel, json.loads(ln))
                    except json.JSONDecodeError:
                        continue
                uploaded += 1
            else:
                # Markdown / 其他文本: 以 JSON {"__text__": "..."} 格式保存
                with open(path, "r", encoding="utf-8") as f:
                    store.write_json(rel, {"__text__": f.read(), "__format__": "text"})
                uploaded += 1
        except Exception as e:
            logger.warning(f"上传 {rel} 失败 (忽略继续): {e}")
    logger.info(f"[state_bridge] 上传完成: {uploaded} 个文件")


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cloud_runner",
        description="跨机器/关电脑/换账号 不中断的 ASO 自动优化 CLI",
    )
    p.add_argument("--game", metavar="GAME_ID", help="单产品优化循环 (如 com.born2play.biblequiz)")
    p.add_argument("--all", action="store_true", help="跑全量游戏优化循环")
    p.add_argument("--dashboard", action="store_true", help="跑完后生成并上传 Dashboard 日报")
    p.add_argument(
        "--multichannel-plan", metavar="GAME_ID",
        help="生成并上传多渠道推广方案 JSON",
    )
    p.add_argument("--force-new-variant", action="store_true",
                   help="强制生成新的 Listing 变体 (忽略指标是否达标)")
    p.add_argument("--healthcheck", action="store_true",
                   help="仅做 STATE_STORE 健康检查 (CI 启动前验证)")
    p.add_argument("--no-dotenv", action="store_true",
                   help="不自动加载 .env / .env.local (纯 CI 环境)")
    p.add_argument("--json", action="store_true", dest="json_output",
                   help="以 JSON 打印结果")
    return p


def main(argv: List[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    _setup_logging()
    if not args.no_dotenv:
        _load_dotenv_if_available()

    store = get_state_store()

    # 2. 启动断点续跑检查 (必须先跑, 即使只 healthcheck 也要把中断任务恢复)
    recovery = _startup_recovery(store)

    # 1. Healthcheck 快速路径
    if args.healthcheck:
        return _healthcheck(store)

    # 3. 任务分支
    result: Dict[str, Any] = {"recovery": recovery}
    try:
        if args.multichannel_plan:
            result["multichannel_plan"] = _run_multichannel_plan(store, args.multichannel_plan)
        if args.game:
            result["single_game"] = _run_single(
                store, args.game, force_new_variant=args.force_new_variant
            )
        if args.all:
            result["all_games"] = _run_all(store, dashboard=args.dashboard)
        if not (args.multichannel_plan or args.game or args.all):
            _build_arg_parser().print_help()
            return 1
    except Exception as e:
        logger.exception("任务执行异常")
        result["error"] = f"{type(e).__name__}: {e}"
        result["success"] = False
        # 即使抛异常也要把已写到本地的缓存上传
        try:
            local_dir = _resolve_local_data_dir(store) if store.backend != "local" else None
            if local_dir:
                _sync_local_back_to_cloud_if_needed(store, local_dir)
        except Exception:
            pass

    result.setdefault("success", "error" not in result)
    result.setdefault("finished_at", datetime.now(timezone.utc).isoformat())

    # 4. 日志输出
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"[cloud_runner] success={result['success']}; finished={result['finished_at']}")
        if "single_game" in result:
            s = result["single_game"]
            print(f"  game_id={s.get('game_id')} status={s.get('status')} "
                  f"variant={s.get('variant_generated')} reason={s.get('reason')}")
        if "multichannel_plan" in result:
            p = result["multichannel_plan"]
            print(f"  多渠道方案: channels={p['channels']} 预估30d={p['estimated_30d_installs']} 存储={p['saved_to']}")
        if "dashboard_report" in result:
            print(f"  Dashboard: {result['dashboard_report']}")

    return 0 if result["success"] else 3


# ── 从 pathlib 导出 Path 给 _resolve_local_data_dir ─────────────
from pathlib import Path  # noqa: E402  (放到这里避免循环风险)


if __name__ == "__main__":
    sys.exit(main())
