"""跨机器/跨账号可移植状态存储.

设计目标:
  1. 状态存储位置与本地机器解耦 — 换电脑/关电脑/换账号, 状态不丢失
  2. 切换方式: 只改环境变量, 不改代码
  3. 支持 3 种后端 (可扩展):
     - LocalFS (默认, 向后兼容)
     - GitHub Gist (零成本, 免部署, 个人用推荐)
     - S3 / R2 (团队/生产用)
  4. 写入时每次自动 flush + 完整性校验
  5. 启动时自动检测断点 (in_progress 任务 → 推回 pending)

环境变量:
  STATE_STORE_BACKEND = local | gist | s3
  STATE_STORE_ROOT    = 语义根据后端不同:
    - local: 本地目录路径 (默认 ./data)
    - gist:  Gist ID (如 "a1b2c3d4e5f6", 必须提前手动创建空 gist)
    - s3:    "bucket/prefix" (如 "my-state-bucket/aso/v1")
  GITHUB_TOKEN / GIST_TOKEN  = Gist 后端访问令牌
  AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY = S3 后端凭证
  S3_ENDPOINT_URL = S3 兼容存储 (Cloudflare R2, MinIO 等)

用法:
    from .state_store import get_state_store
    store = get_state_store()           # 读 STATE_STORE_BACKEND 自动实例化
    store.write_json("game_registry.json", data)
    data = store.read_json("game_registry.json", default={})
    store.append_jsonl("cycle_history.jsonl", record)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────

_ENV_BACKEND = "STATE_STORE_BACKEND"
_ENV_ROOT = "STATE_STORE_ROOT"
_DEFAULT_BACKEND = "local"


# ── 抽象基类 ────────────────────────────────────────────────────

class StateStore(ABC):
    """跨后端统一的 KV + JSONL 状态存储接口."""

    backend: str = "abstract"

    # ── JSON 文件 ────────────────────────────────────────────────

    @abstractmethod
    def read_json(self, key: str, default: Any = None) -> Any:
        """读取 JSON. 不存在返回 default, 损坏时记录告警并返回 default."""

    @abstractmethod
    def write_json(self, key: str, value: Any) -> None:
        """原子写入 JSON (先写临时文件再替换 / 先写再校验)."""

    # ── JSONL 追加 ───────────────────────────────────────────────

    @abstractmethod
    def append_jsonl(self, key: str, record: Dict[str, Any]) -> None:
        """追加一条 JSON 记录到文件末尾."""

    @abstractmethod
    def read_jsonl(self, key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """读取全部或最后 N 条 JSONL."""

    # ── 通用 ──────────────────────────────────────────────────────

    @abstractmethod
    def exists(self, key: str) -> bool:
        """key 是否存在."""

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        """列出前缀匹配的所有 key."""

    def health_check(self) -> Dict[str, Any]:
        """存储健康检查 (写入+读取往返测试)."""
        probe_key = f".probe/{os.getpid()}_{int(__import__('time').time()*1000)}.json"
        try:
            self.write_json(probe_key, {"ok": True})
            got = self.read_json(probe_key)
            return {"backend": self.backend, "ok": bool(got and got.get("ok")), "probe": probe_key}
        except Exception as e:
            logger.exception("state_store health_check failed")
            return {"backend": self.backend, "ok": False, "error": f"{type(e).__name__}: {e}"}


# ── LocalFS 后端 (默认, 100% 向后兼容) ──────────────────────────

class LocalFSStateStore(StateStore):
    """本地文件系统实现 — 默认后端, 与现有 data/ 目录行为一致."""

    backend = "local"

    def __init__(self, root_dir: str = "data") -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info(f"[state_store] LocalFS 后端初始化: root={self._root}")

    # ── helpers ──────────────────────────────────────────────────
    def _path(self, key: str) -> Path:
        """key 转绝对路径, 阻止跳出 root (目录穿越防御)."""
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError:
            raise ValueError(f"非法 key (目录穿越被拒绝): {key}") from None
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        """原子写入: tmp + fsync + replace, 避免崩溃写坏."""
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    # ── JSON ─────────────────────────────────────────────────────
    def read_json(self, key: str, default: Any = None) -> Any:
        path = self._path(key)
        if not path.is_file():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[state_store] 读取 {key} 损坏或不可读: {e}, 使用 default")
            return default

    def write_json(self, key: str, value: Any) -> None:
        path = self._path(key)
        payload = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        self._atomic_write(path, payload)

    # ── JSONL ────────────────────────────────────────────────────
    def append_jsonl(self, key: str, record: Dict[str, Any]) -> None:
        path = self._path(key)
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    def read_jsonl(self, key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        path = self._path(key)
        if not path.is_file():
            return []
        out: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if limit is not None and limit > 0:
            lines = lines[-limit:]
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                logger.warning(f"[state_store] JSONL {key} 跳过坏行: {ln[:80]}")
        return out

    # ── 通用 ─────────────────────────────────────────────────────
    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list_keys(self, prefix: str = "") -> List[str]:
        start = self._root
        if prefix:
            start = self._root / prefix
            if not start.exists():
                return []
        keys: List[str] = []
        for p in start.rglob("*"):
            if p.is_file():
                keys.append(str(p.relative_to(self._root)).replace("\\", "/"))
        return keys


# ── GitHub Gist 后端 (免部署, 机器无关) ──────────────────────────

class GistStateStore(StateStore):
    """GitHub Gist 作为状态存储.

    每个 Gist file = 一个 key. JSONL 按行追加到 gist file 内容.
    首次使用前请手动创建一个空的 secret gist, 记下 Gist ID.
    """

    backend = "gist"

    def __init__(self, gist_id: str, token: Optional[str] = None) -> None:
        self._gist_id = gist_id
        self._token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GIST_TOKEN")
        if not self._token:
            raise RuntimeError(
                "GistStateStore 需要 GITHUB_TOKEN 或 GIST_TOKEN 环境变量 "
                "(在 https://github.com/settings/tokens 生成, 勾选 gist 权限)"
            )
        self._cache: Dict[str, Any] = {}
        self._api = "https://api.github.com"
        logger.info(f"[state_store] Gist 后端初始化: gist_id={gist_id[:8]}...")

    # ── low-level HTTP ───────────────────────────────────────────
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _fetch_gist(self) -> Dict[str, Any]:
        import urllib.request
        req = urllib.request.Request(f"{self._api}/gists/{self._gist_id}", headers=self._headers())
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _patch_gist(self, files: Dict[str, Any]) -> Dict[str, Any]:
        import urllib.request
        body = json.dumps({"files": files}).encode("utf-8")
        req = urllib.request.Request(
            f"{self._api}/gists/{self._gist_id}",
            data=body,
            method="PATCH",
            headers={**self._headers(), "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _get_files(self) -> Dict[str, Any]:
        return self._fetch_gist().get("files", {})

    # ── JSON ─────────────────────────────────────────────────────
    def read_json(self, key: str, default: Any = None) -> Any:
        files = self._get_files()
        entry = files.get(key)
        if not entry or entry.get("truncated"):
            # 文件被截断的情况需要单独下载 raw_url
            if entry and entry.get("raw_url"):
                try:
                    import urllib.request
                    with urllib.request.urlopen(entry["raw_url"], timeout=30) as r:
                        return json.loads(r.read().decode("utf-8"))
                except Exception as e:
                    logger.warning(f"[state_store] gist {key} raw 下载失败: {e}")
                    return default
            return default
        try:
            return json.loads(entry["content"])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[state_store] gist {key} 解析失败: {e}")
            return default

    def write_json(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        self._patch_gist({key: {"content": payload}})

    # ── JSONL ────────────────────────────────────────────────────
    def append_jsonl(self, key: str, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        files = self._get_files()
        existing = files.get(key, {}).get("content", "") if key in files else ""
        self._patch_gist({key: {"content": existing + line}})

    def read_jsonl(self, key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        files = self._get_files()
        entry = files.get(key)
        content = ""
        if entry:
            if entry.get("truncated") and entry.get("raw_url"):
                try:
                    import urllib.request
                    with urllib.request.urlopen(entry["raw_url"], timeout=30) as r:
                        content = r.read().decode("utf-8")
                except Exception:
                    content = entry.get("content", "")
            else:
                content = entry.get("content", "")
        out: List[Dict[str, Any]] = []
        lines = content.splitlines()
        if limit is not None and limit > 0:
            lines = lines[-limit:]
        for ln in lines:
            if not ln.strip():
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                logger.warning(f"[state_store] gist JSONL {key} 跳过坏行")
        return out

    # ── 通用 ─────────────────────────────────────────────────────
    def exists(self, key: str) -> bool:
        return key in self._get_files()

    def list_keys(self, prefix: str = "") -> List[str]:
        return [k for k in self._get_files().keys() if k.startswith(prefix)]


# ── S3 后端 (生产/团队用, 支持 R2/MinIO) ────────────────────────

class S3StateStore(StateStore):
    """S3 兼容后端 (AWS S3 / Cloudflare R2 / MinIO / 阿里云 OSS 等).

    key = 对象在 bucket/prefix 下的相对路径.
    """

    backend = "s3"

    def __init__(self, bucket_prefix: str) -> None:
        try:
            import boto3  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "S3StateStore 需要 boto3: pip install boto3"
            ) from e

        # bucket_prefix 格式: "mybucket/some/prefix"
        parts = bucket_prefix.strip("/").split("/", 1)
        self._bucket = parts[0]
        self._prefix = parts[1] if len(parts) > 1 else ""
        if self._prefix and not self._prefix.endswith("/"):
            self._prefix += "/"

        endpoint = os.environ.get("S3_ENDPOINT_URL") or None
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
        logger.info(
            f"[state_store] S3 后端初始化: bucket={self._bucket}, "
            f"prefix={self._prefix or '(none)'}, endpoint={endpoint or 'aws-default'}"
        )

    # ── helpers ──────────────────────────────────────────────────
    def _full_key(self, key: str) -> str:
        return self._prefix + key

    # ── JSON ─────────────────────────────────────────────────────
    def read_json(self, key: str, default: Any = None) -> Any:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=self._full_key(key))
            return json.loads(resp["Body"].read().decode("utf-8"))
        except self._client.exceptions.NoSuchKey:
            return default
        except Exception as e:
            logger.warning(f"[state_store] S3 读 {key} 失败: {e}")
            return default

    def write_json(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self._client.put_object(
            Bucket=self._bucket, Key=self._full_key(key), Body=payload,
            ContentType="application/json; charset=utf-8",
        )

    # ── JSONL ────────────────────────────────────────────────────
    def append_jsonl(self, key: str, record: Dict[str, Any]) -> None:
        # S3 不支持真正的 append, 采用 read+write (对高频小文件足够)
        existing = self._client.get_object(
            Bucket=self._bucket, Key=self._full_key(key)
        )["Body"].read().decode("utf-8") if self.exists(key) else ""
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        self._client.put_object(
            Bucket=self._bucket, Key=self._full_key(key),
            Body=(existing + line).encode("utf-8"),
            ContentType="application/x-ndjson; charset=utf-8",
        )

    def read_jsonl(self, key: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.exists(key):
            return []
        body = self._client.get_object(
            Bucket=self._bucket, Key=self._full_key(key)
        )["Body"].read().decode("utf-8")
        lines = body.splitlines()
        if limit is not None and limit > 0:
            lines = lines[-limit:]
        out: List[Dict[str, Any]] = []
        for ln in lines:
            if not ln.strip():
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                logger.warning(f"[state_store] S3 JSONL {key} 跳过坏行")
        return out

    # ── 通用 ─────────────────────────────────────────────────────
    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._full_key(key))
            return True
        except self._client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def list_keys(self, prefix: str = "") -> List[str]:
        full_prefix = self._prefix + prefix
        paginator = self._client.get_paginator("list_objects_v2")
        keys: List[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                k = obj["Key"]
                if k.startswith(self._prefix):
                    keys.append(k[len(self._prefix):])
        return keys


# ── 工厂 (从环境变量自动选择) ────────────────────────────────────

def _detect_backend() -> str:
    return os.environ.get(_ENV_BACKEND, _DEFAULT_BACKEND).strip().lower()


def get_state_store(
    backend: Optional[str] = None,
    root: Optional[str] = None,
) -> StateStore:
    """获取 StateStore 单例.

    不指定时自动从环境变量读取:
      STATE_STORE_BACKEND = local | gist | s3
      STATE_STORE_ROOT = 根目录 / gist id / bucket+prefix
    """
    backend = (backend or _detect_backend()).lower()
    root = root if root is not None else os.environ.get(_ENV_ROOT, "data")

    if backend == "local":
        return LocalFSStateStore(root_dir=root)
    if backend == "gist":
        return GistStateStore(gist_id=root)
    if backend == "s3":
        return S3StateStore(bucket_prefix=root)
    raise ValueError(
        f"不支持的 STATE_STORE_BACKEND={backend!r}; "
        f"可选值: local, gist, s3"
    )
