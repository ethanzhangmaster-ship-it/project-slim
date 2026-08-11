"""一键创建 Gist 状态存储 + 迁移本地 data/ 状态.

用法:
  # 前提: 有一个能创建 gist 的 GitHub Personal Access Token
  # 生成 token: https://github.com/settings/tokens → 勾选 Gist 权限 + 读 repo 权限

  # 交互式 (会问你 token, 或从 env 读)
  python scripts/bootstrap_gist_state.py

  # 或者直接把 token 设到环境变量里 (推荐 CI/脚本方式)
  $env:GITHUB_TOKEN="ghp_xxxxx"  # PowerShell
  python scripts/bootstrap_gist_state.py

功能:
  1. 如果 STATE_STORE_ROOT (gist id) 已有, 跳过创建并直接复用
  2. 否则创建一个新的 secret gist (标题: "market-ops aso state")
  3. 把本地 data/ 里所有已有状态迁移过去
  4. 最后打印:
     - STATE_STORE_BACKEND=gist
     - STATE_STORE_ROOT=<你的 gist id>
     - 要复制到 GitHub Actions Secrets 的清单
     - 以及手动触发一次 healthcheck 的命令
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("bootstrap_gist")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _project_root() -> Path:
    here = Path(__file__).resolve().parent.parent  # scripts/ → project_root
    assert (here / "pyproject.toml").exists()
    return here


def _read_token(args: argparse.Namespace) -> str:
    candidates = [
        args.token,
        os.environ.get("GITHUB_TOKEN"),
        os.environ.get("GIST_TOKEN"),
    ]
    for c in candidates:
        if c and c.strip():
            return c.strip()
    # 交互式兜底
    try:
        token = input(
            "\n请粘贴你的 GitHub Personal Access Token (需勾选 Gist 权限)\n"
            "  Token 生成入口: https://github.com/settings/tokens\n"
            "  Token: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        token = ""
    if not token:
        raise SystemExit(
            "❌ 缺少 GITHUB_TOKEN. 请先从 https://github.com/settings/tokens 生成 "
            "(Scopes 只需勾选 Gist), 然后设为环境变量 $env:GITHUB_TOKEN 或通过 --token 参数."
        )
    return token


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def _github_api(method: str, url: str, token: str, body: Any = None) -> Any:
    data = None
    headers = _headers(token)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        raise SystemExit(
            f"❌ GitHub API {method} {url} 失败 HTTP {e.code}: {err[:500]}"
        )


def _create_secret_gist(token: str, existing_root: str = "") -> str:
    if existing_root:
        logger.info(f"✅ 复用已存在的 Gist: STATE_STORE_ROOT={existing_root[:8]}...")
        # 验证一下 gist 存在
        try:
            _github_api("GET", f"https://api.github.com/gists/{existing_root}", token)
        except SystemExit:
            logger.warning(f"⚠️ 提供的 gist {existing_root[:8]} 访问失败, 会新建一个.")
        else:
            return existing_root
    body = {
        "description": f"market-ops ASO state (auto-generated {datetime.now(timezone.utc).date()})",
        "public": False,
        "files": {
            "README_STATE_STORE.md": {
                "content": (
                    "# market-ops ASO State Store (Gist Backend)\n\n"
                    "这个 Gist 是 market-ops project 的跨机器状态存储.\n"
                    "所有文件由 state_store.py 自动读写, 请勿手动编辑.\n\n"
                    "- 每个 JSON/JSONL = 原 data/ 目录下的同名文件\n"
                    "- Markdown/文本文件 = 以 JSON {__text__:...} 格式包装\n"
                )
            }
        },
    }
    r = _github_api("POST", "https://api.github.com/gists", token, body)
    gid = r["id"]
    html_url = r.get("html_url", "")
    logger.info(f"✅ 新建 secret gist 成功: id={gid[:12]}... url={html_url}")
    return gid


def _list_local_state_files(root: Path, data_dir: Path = None) -> List[Path]:
    """扫描本地 data/ + aso_deploy 目录下应该上传的所有状态文件."""
    if data_dir is None:
        data_dir = root / "data"
    out: List[Path] = []
    suffixes = (".json", ".jsonl", ".md")
    if not data_dir.exists():
        return out
    for p in data_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in suffixes:
            out.append(p)
    return out


def _migrate_local_to_gist(token: str, gist_id: str, project_root: Path) -> Dict[str, int]:
    """把本地 data/ 下的现有状态文件全量上传到 gist."""
    data_dir = project_root / "data"
    local_files = _list_local_state_files(project_root, data_dir)
    logger.info(f"📦 发现 {len(local_files)} 个本地状态文件, 准备迁移到 gist...")

    # Gist 单次 PATCH 可接受批量文件, 我们按 ~20 个文件一批处理 (避免 payload 过大)
    batches: List[List[Path]] = []
    for i in range(0, len(local_files), 20):
        batches.append(local_files[i:i + 20])

    uploaded = 0
    skipped_empty = 0
    for batch_idx, batch in enumerate(batches, 1):
        files_payload: Dict[str, Dict[str, str]] = {}
        for f in batch:
            rel = str(f.relative_to(project_root)).replace("\\", "/")
            try:
                text = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # 非 UTF-8 跳过
                skipped_empty += 1
                continue
            if not text.strip():
                skipped_empty += 1
                continue
            if f.suffix.lower() == ".json":
                try:
                    json.loads(text)
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ 跳过坏 JSON: {rel}")
                    skipped_empty += 1
                    continue
                files_payload[rel] = {"content": text}
            elif f.suffix.lower() == ".jsonl":
                files_payload[rel] = {"content": text}
            else:  # .md / 其他文本 → 用 {"__text__": "..."} 包装 (与 cloud_runner 桥接一致)
                wrapped = json.dumps({"__text__": text, "__format__": "text"}, ensure_ascii=False)
                files_payload[rel] = {"content": wrapped}
        if not files_payload:
            continue
        _github_api(
            "PATCH",
            f"https://api.github.com/gists/{gist_id}",
            token,
            {"files": files_payload},
        )
        n = len(files_payload)
        uploaded += n
        logger.info(f"  Batch {batch_idx}/{len(batches)}: 上传 {n} 个文件")

    return {
        "uploaded": uploaded,
        "skipped": skipped_empty,
        "total_discovered": len(local_files),
    }


def _verify_gist(token: str, gist_id: str) -> None:
    # 通过我们的 state_store 走 health_check 验证端到端
    logger.info("🧪 端到端验证: GistStateStore.health_check...")
    sys.path.insert(0, str(_project_root() / "src"))
    from market_ops.workspace.state_store import GistStateStore
    store = GistStateStore(gist_id=gist_id, token=token)
    r = store.health_check()
    if not r.get("ok"):
        raise SystemExit(f"❌ Gist 状态存储健康检查失败: {r}")
    logger.info(f"✅ 端到端验证通过: {r}")


def _print_setup_guide(gist_id: str, uploaded: Dict[str, int]) -> None:
    print("\n" + "=" * 72)
    print("🎉 Gist 状态存储引导完成")
    print("=" * 72)
    print()
    print("【本地立刻试用】执行以下 PowerShell 命令体验 gist 后端:")
    print(f'  $env:STATE_STORE_BACKEND="gist"')
    print(f'  $env:STATE_STORE_ROOT="{gist_id}"')
    print(f'  $env:GITHUB_TOKEN="<你的 token>"')
    print(f'  python -m market_ops.workspace.cloud_runner --healthcheck --no-dotenv')
    print()
    print("【GitHub Actions Secrets 配置 (必需)】")
    print("  打开 GitHub Repo → Settings → Secrets and variables → Actions:")
    print()
    print("  ① 切换到 Variables 标签, 新增:")
    print(f'     NAME : STATE_STORE_BACKEND')
    print(f'     VALUE: gist')
    print()
    print("  ② 切换到 Secrets 标签, 新增 2 条:")
    print(f'     NAME : STATE_STORE_ROOT')
    print(f'     VALUE: {gist_id}')
    print()
    print(f'     NAME : GIST_TOKEN')
    print(f'     VALUE: <刚才用的 GitHub PAT (Gist 权限) 再贴一次>')
    print()
    print("  ③ (可选, 接 LLM 生成激进变体) 再加 Secrets:")
    print(f'     OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL')
    print()
    print("  ④ (可选, 接真 Play Console 数据) 再加 Secret:")
    print(f'     GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64')
    print(f'     (生成方式: [Convert]::ToBase64String([IO.File]::ReadAllBytes("服务账号.json")) )')
    print()
    print(f"【迁移报告】发现 {uploaded['total_discovered']} 个本地状态文件, "
          f"上传 {uploaded['uploaded']}, 跳过空/坏文件 {uploaded['skipped']}")
    print()
    print("【下一步】推送代码到 GitHub 后, 到 Actions 页面点 Run workflow: ")
    print("  Workflow: ASO Auto Optimization - Cloud Cron")
    print("  或先 Push 代码, workflow_dispatch 可直接触发第一次全量运行.")
    print("=" * 72)


def _save_bootstrap_report(project_root: Path, gist_id: str, uploaded: Dict[str, int]) -> None:
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "gist",
        "gist_id": gist_id,
        "uploaded_files": uploaded["uploaded"],
        "skipped_files": uploaded["skipped"],
        "discovered_files": uploaded["total_discovered"],
        "next_actions": [
            "复制上方 GitHub Actions Variables/Secrets 到仓库配置",
            "执行 `git push origin master` (或其他分支)",
            "在 Actions → ASO Auto Optimization - Cloud Cron 手动触发 workflow_dispatch 验证",
        ],
    }
    out_dir = project_root / "outputs" / "deploy"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gist_bootstrap_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"📄 引导报告已保存: {out_path}")


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="一键创建 Gist 状态存储 + 迁移本地状态")
    p.add_argument("--token", help="GitHub PAT (Gist 权限). 默认读 env GITHUB_TOKEN/GIST_TOKEN")
    p.add_argument("--gist-id", dest="gist_id",
                   help="指定现有 gist id (不创建新的, 直接迁移), 默认读 STATE_STORE_ROOT env")
    p.add_argument("--skip-migrate", action="store_true", help="只创建 gist, 不迁移状态")
    p.add_argument("--skip-verify", action="store_true", help="不做 end-to-end health_check 验证")
    args = p.parse_args(argv)
    _setup_logging()

    project_root = _project_root()
    token = _read_token(args)
    existing = args.gist_id or os.environ.get("STATE_STORE_ROOT", "")

    gist_id = _create_secret_gist(token, existing)

    uploaded = {"uploaded": 0, "skipped": 0, "total_discovered": 0}
    if not args.skip_migrate:
        uploaded = _migrate_local_to_gist(token, gist_id, project_root)

    if not args.skip_verify:
        _verify_gist(token, gist_id)

    _save_bootstrap_report(project_root, gist_id, uploaded)
    _print_setup_guide(gist_id, uploaded)

    # 最后把 gist id 写入 .env.local 供本机试用 (不写入 .env 仓库)
    env_local = project_root / ".env.local"
    lines: List[str] = []
    if env_local.is_file():
        lines = env_local.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("STATE_STORE_BACKEND="):
            new_lines.append("STATE_STORE_BACKEND=gist")
            updated = True
        elif s.startswith("STATE_STORE_ROOT="):
            new_lines.append(f"STATE_STORE_ROOT={gist_id}")
            updated = True
        else:
            new_lines.append(ln)
    if not updated:
        new_lines.append("")
        new_lines.append("# Gist 状态存储 (由 scripts/bootstrap_gist_state.py 自动添加)")
        new_lines.append("STATE_STORE_BACKEND=gist")
        new_lines.append(f"STATE_STORE_ROOT={gist_id}")
    env_local.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    logger.info(f"📝 已把 STATE_STORE_BACKEND/ROOT 追加写入 {env_local}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
