"""AgentRegistry JSONL 持久化 — 快照存储.

将 AgentRegistry 的内存状态持久化到 JSONL, 支持进程重启后恢复.
不侵入现有 AgentRegistry 类 (V1 兼容), 作为薄层持久化模块.

设计:
  - save: 全量覆盖写入 (快照模式, 非追加)
  - load: 读取快照恢复 AgentRecord 列表
  - 默认组织: 首次启动时从 create_default_organization() 生成

持久化路径: data/workspace/agents.jsonl
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENTS_SNAPSHOT_PATH = _PROJECT_ROOT / "data" / "workspace" / "agents.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: Path) -> None:
    """确保目录存在."""
    path.parent.mkdir(parents=True, exist_ok=True)


def save_agents_snapshot(records: list[dict[str, Any]], path: Path | None = None) -> None:
    """保存 Agent 快照到 JSONL (全量覆盖).

    Args:
        records: AgentRecord.to_dict() 列表
        path: 持久化路径, 默认 AGENTS_SNAPSHOT_PATH
    """
    target = path or AGENTS_SNAPSHOT_PATH
    _ensure_dir(target)
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    logger.info("Saved %d agents snapshot to %s", len(records), target)


def load_agents_snapshot(path: Path | None = None) -> list[dict[str, Any]]:
    """从 JSONL 读取 Agent 快照.

    Returns:
        AgentRecord dict 列表, 文件不存在返回空列表.
    """
    target = path or AGENTS_SNAPSHOT_PATH
    if not target.exists():
        logger.debug("Agents snapshot not found: %s", target)
        return []
    records: list[dict[str, Any]] = []
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to read agents snapshot: %s", exc)
        return []
    for line_num, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            logger.warning("Agents snapshot parse error at line %d: %s", line_num, exc)
    return records


def create_default_agents_snapshot(path: Path | None = None) -> list[dict[str, Any]]:
    """创建默认组织 Agent 快照并持久化.

    从 create_default_organization() 生成 5 个标准 Agent:
      - Growth Supervisor
      - UA Agent
      - Creative Agent
      - Monetization Agent
      - Product Agent

    Returns:
        AgentRecord dict 列表.
    """
    try:
        from src.market_ops.creative_vision_runtime.growth_runtime.agent.communication.agent_registry import (
            create_default_organization,
        )
    except ImportError as exc:
        logger.error("Failed to import AgentRegistry: %s", exc)
        return []

    registry = create_default_organization()
    records = [r.to_dict() for r in registry.get_all()]
    save_agents_snapshot(records, path)
    logger.info("Created default agents snapshot with %d agents", len(records))
    return records


def _has_all_required_roles(records: list[dict[str, Any]]) -> bool:
    """检查快照中是否包含所有必需角色 (含最新 DataAnalyst + PlayerSupport).

    用于检测旧快照并触发自动重新生成.
    """
    required_roles = {"liveops", "data_analyst", "player_support"}
    present_roles = {
        (r.get("identity", {}) or {}).get("role", "")
        for r in records
    }
    return required_roles.issubset(present_roles)


def get_agents_data(path: Path | None = None) -> list[dict[str, Any]]:
    """获取 Agent 数据 — 读取快照, 不存在或缺少必需角色则创建默认组织.

    这是 Workspace 读取 Agent 数据的统一入口. 当旧快照缺少新增角色
    (如 DataAnalyst/PlayerSupport 上线前的快照) 时, 自动重新生成默认组织以保持兼容.
    """
    records = load_agents_snapshot(path)
    if not records or not _has_all_required_roles(records):
        records = create_default_agents_snapshot(path)
    return records


def update_agent_status(
    agent_id: str,
    status: str,
    path: Path | None = None,
) -> bool:
    """更新单个 Agent 状态并持久化.

    Args:
        agent_id: Agent ID
        status: 新状态 (online, idle, busy, degraded, offline)
        path: 持久化路径

    Returns:
        True 如果更新成功.
    """
    records = load_agents_snapshot(path)
    updated = False
    for record in records:
        identity = record.get("identity", {}) or {}
        if identity.get("agent_id") == agent_id:
            record["status"] = status
            record["last_heartbeat"] = _now_iso()
            updated = True
            break
    if updated:
        save_agents_snapshot(records, path)
        logger.info("Updated agent %s status to %s", agent_id, status)
    return updated


def heartbeat_agent(agent_id: str, path: Path | None = None) -> bool:
    """更新 Agent 心跳时间戳并持久化."""
    records = load_agents_snapshot(path)
    updated = False
    for record in records:
        identity = record.get("identity", {}) or {}
        if identity.get("agent_id") == agent_id:
            record["last_heartbeat"] = _now_iso()
            # 如果之前是 offline, 恢复为 online
            if record.get("status") == "offline":
                record["status"] = "online"
            updated = True
            break
    if updated:
        save_agents_snapshot(records, path)
    return updated
