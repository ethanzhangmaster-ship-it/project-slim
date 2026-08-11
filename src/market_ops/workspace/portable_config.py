"""可移植配置加载器 — 不绑定单台机器 / 单个账号.

优先级 (由高到低, 前一个找到就不看后面):
  1. 进程环境变量 (CI/云端/容器 用这个, 不需要任何文件)
  2. .env.local (本机私有, 已加入 .gitignore, 不在版本控制里)
  3. .env (仓库级样例, 不含密钥, 仅默认值占位)
  4. 内置 fallback 默认值 (仅非敏感字段)

敏感字段 (API key / token 等) 若全部四层都没找到:
  - 不抛异常, get_secret() 返回 None, 让调用方决定是否 mock/fail-closed

核心原则:
  - 任何机器上只要环境变量对, 立刻能跑
  - 换账号不换机器: 只要改 env 即可 (无需改任何文件)
  - 关电脑不丢状态: 状态在 state_store (gist/s3 后端)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    """定位项目根 (基于当前文件所在位置找市场_ops 的 workspace 上级)."""
    here = Path(__file__).resolve().parent  # workspace/
    # 向上 3 级: workspace → market_ops → src → project_root
    candidate = here.parent.parent.parent
    if (candidate / "pyproject.toml").exists():
        return candidate
    # 退而求其次: cwd
    return Path.cwd()


def _load_env_file(path: Path) -> bool:
    """仅当 python-dotenv 可用且文件存在时加载. 返回是否真的加载了."""
    if not path.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    # override=False → 已经在 process env 里的值不被文件覆盖 (env 永远最高优先级)
    load_dotenv(dotenv_path=str(path), override=False, verbose=False, encoding="utf-8")
    logger.debug(f"[portable_config] 已加载: {path}")
    return True


# ── 懒加载: 首次访问时才 load (避免 import-time 副作用) ───────
_INITIALIZED = False


def initialize_if_needed() -> None:
    """按优先级顺序尝试加载配置文件. 只运行一次, 重复调用安全."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True
    root = _project_root()
    # 顺序不能乱 (先加载低优先级, 再加载高优先级 — 后者写的是已存在同名 key 时保持 env 值不变)
    _load_env_file(root / ".env", _FROM_DOTENV_NOT_LOCAL)
    _load_env_file(root / ".env.local", _FROM_ENV_LOCAL)
    _load_env_file(root / "workspace" / ".env.local", _FROM_ENV_LOCAL)


# ── 公共 API ────────────────────────────────────────────────────

def get(key: str, default: Any = None) -> Any:
    """读取任意配置值.  env > .env.local > .env > default"""
    initialize_if_needed()
    return os.environ.get(key, default)


def get_int(key: str, default: int = 0) -> int:
    v = get(key)
    if v is None or v == "":
        return default
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        logger.warning(f"[portable_config] {key}={v!r} 无法解析为 int, 使用 default={default}")
        return default


def get_bool(key: str, default: bool = False) -> bool:
    v = get(key)
    if v is None or v == "":
        return default
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off", ""):
        return False if s == "" else False  # 空字符串也算 default
    logger.warning(f"[portable_config] {key}={v!r} 无法解析为 bool, 使用 default={default}")
    return default


# 记录哪些 key/value 是被 .env (而不是 .env.local 或 进程env) 注入的.
# get_secret 会跳过这些值 → 防止真密钥误写到仓库级 .env 后被当成 secret 读走.
_FROM_DOTENV_NOT_LOCAL: Dict[str, str] = {}
_FROM_ENV_LOCAL: Dict[str, str] = {}


def _snapshot_env_before() -> Dict[str, str]:
    return dict(os.environ)


def _diff_env(before: Dict[str, str]) -> Dict[str, str]:
    """返回加载完一个文件后, os.environ 新增/变化的部分."""
    return {k: v for k, v in os.environ.items() if before.get(k) != v}


def _load_env_file(path: Path, tracking_dict: Dict[str, str]) -> bool:
    """加载单个 env 文件, 并把新增值记入 tracking_dict (供 get_secret 鉴别来源)."""
    if not path.is_file():
        return False
    try:
        from dotenv import dotenv_values
    except ImportError:
        return False
    before = _snapshot_env_before()
    # 读文件但不直接 set env — 这样我们能选择来源
    values = dotenv_values(dotenv_path=str(path), encoding="utf-8")
    for k, v in values.items():
        if v is None:
            continue
        if k not in os.environ:  # 只有 env 里还没值的才允许文件里的占位值覆盖
            os.environ[k] = v
            tracking_dict[k] = v
    logger.debug(f"[portable_config] 已加载 {path} ({len(values)} 项, 新增 {len(_diff_env(before))} 项)")
    return True


def get_secret(key: str) -> Optional[str]:
    """读取敏感配置 (API token). 找不到时返回 None, 不抛异常.

    安全规则 (严格):
      1. 进程环境变量中显式设置的值 → OK (CI/云端/个人系统环境变量)
      2. 来自 .env.local 的值 → OK (本机私有, 已加入 .gitignore)
      3. 来自仓库级 .env 的值 → ❌ 返回 None
         (避免有人把真密钥误提交到仓库 .env 后被读到)
    """
    initialize_if_needed()
    v = os.environ.get(key)
    if not v:
        return None
    # 来自 .env (非私有) 的一律视为非信任占位
    if key in _FROM_DOTENV_NOT_LOCAL and _FROM_DOTENV_NOT_LOCAL[key] == v and key not in _FROM_ENV_LOCAL:
        return None
    return v


def state_store_backend() -> str:
    return get("STATE_STORE_BACKEND", "local").strip().lower()


def dump_safe_snapshot() -> Dict[str, str]:
    """导出不含密钥的配置快照 (用于日志/调试)."""
    initialize_if_needed()
    snapshot: Dict[str, str] = {}
    secret_keywords = (
        "KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "PASSWD",
        "REFRESH", "PRIVATE", "CLIENT_ID", "CLIENT_SECRET",
    )
    for k, v in os.environ.items():
        if k.startswith("MARKET_OPS_") or k.startswith("STATE_STORE_") or k in (
            "AI_PROVIDER", "OPENAI_MODEL", "OPENAI_BASE_URL", "META_API_VERSION",
            "GOOGLE_ADS_API_VERSION", "THINKINGDATA_BASE_URL",
            "CLOUD_RUNNER_LOGLEVEL",
        ):
            if any(sk in k.upper() for sk in secret_keywords):
                snapshot[k] = "<REDACTED>" if v else ""
            else:
                snapshot[k] = v
    return snapshot
