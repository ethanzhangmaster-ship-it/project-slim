"""E11.2.2 — Asset Lifecycle Manager。

管理素材从创建到进化完成的全生命周期状态。

状态机：
  NEW → MATCHED → TESTING → WINNER → DNA_ANALYZED → MUTATED
  任意状态可进入: ARCHIVED, FAILED

状态转换条件：
  NEW          → 初始状态，素材刚进入 Eagle
  MATCHED      → 已匹配到 Facebook 广告
  TESTING      → Facebook 广告有足够数据 (impressions >= 1000)
  WINNER       → ROAS D7 >= 阈值 或 人工标记
  DNA_ANALYZED → Vision DNA 已提取
  MUTATED      → 已产生变异后代
  ARCHIVED     → 不再使用
  FAILED       → ROAS 过低，标记失败

Usage:
    mgr = AssetLifecycleManager("data/asset_lifecycle.json")
    mgr.transition("v2601536", "TESTING")
    status = mgr.get_status("v2601536")
    winners = mgr.get_by_status("WINNER")
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class AssetLifecycleStatus(str, Enum):
    """素材生命周期状态。"""
    NEW = "NEW"
    MATCHED = "MATCHED"
    TESTING = "TESTING"
    WINNER = "WINNER"
    DNA_ANALYZED = "DNA_ANALYZED"
    MUTATED = "MUTATED"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


# 合法状态转换
VALID_TRANSITIONS: dict[AssetLifecycleStatus, set[AssetLifecycleStatus]] = {
    AssetLifecycleStatus.NEW: {
        AssetLifecycleStatus.MATCHED,
        AssetLifecycleStatus.ARCHIVED,
    },
    AssetLifecycleStatus.MATCHED: {
        AssetLifecycleStatus.TESTING,
        AssetLifecycleStatus.FAILED,
        AssetLifecycleStatus.ARCHIVED,
    },
    AssetLifecycleStatus.TESTING: {
        AssetLifecycleStatus.WINNER,
        AssetLifecycleStatus.FAILED,
        AssetLifecycleStatus.ARCHIVED,
    },
    AssetLifecycleStatus.WINNER: {
        AssetLifecycleStatus.DNA_ANALYZED,
        AssetLifecycleStatus.ARCHIVED,
    },
    AssetLifecycleStatus.DNA_ANALYZED: {
        AssetLifecycleStatus.MUTATED,
        AssetLifecycleStatus.ARCHIVED,
    },
    AssetLifecycleStatus.MUTATED: {
        AssetLifecycleStatus.ARCHIVED,
    },
    AssetLifecycleStatus.FAILED: {
        AssetLifecycleStatus.ARCHIVED,
    },
    AssetLifecycleStatus.ARCHIVED: set(),
}


class AssetLifecycleManager:
    """素材生命周期管理器。

    持久化状态到 JSON 文件，支持查询和批量转换。
    """

    def __init__(self, state_path: str = "data/asset_lifecycle.json") -> None:
        self._path = Path(state_path)
        self._states: dict[str, dict[str, Any]] = {}
        self._load()

    # ── Public API ───────────────────────────────────────

    def transition(
        self,
        asset_id: str,
        new_status: str | AssetLifecycleStatus,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """执行状态转换。

        Args:
            asset_id:  素材 ID (eagle_v_number, e.g., "v2601536")
            new_status: 目标状态
            metadata:   附加信息（spend, roas, 等）

        Returns:
            True if transition succeeded
        """
        if isinstance(new_status, str):
            new_status = AssetLifecycleStatus(new_status.upper())

        current = self._get_or_create(asset_id)
        current_status = AssetLifecycleStatus(
            current.get("status", AssetLifecycleStatus.NEW.value)
        )

        # 验证转换合法性
        if new_status not in VALID_TRANSITIONS.get(current_status, set()):
            return False

        # 执行转换
        now = datetime.now().isoformat()
        history = current.get("history", [])
        history.append({
            "from": current_status.value,
            "to": new_status.value,
            "at": now,
        })

        current["status"] = new_status.value
        current["updated_at"] = now
        current["history"] = history

        if metadata:
            current.update(metadata)

        self._save()
        return True

    def get_status(self, asset_id: str) -> AssetLifecycleStatus | None:
        """获取素材当前状态。"""
        entry = self._states.get(asset_id)
        if entry:
            return AssetLifecycleStatus(entry["status"])
        return None

    def get_details(self, asset_id: str) -> dict[str, Any] | None:
        """获取素材完整生命周期信息。"""
        return self._states.get(asset_id)

    def get_by_status(
        self, status: str | AssetLifecycleStatus
    ) -> list[str]:
        """获取指定状态的所有素材 ID。"""
        if isinstance(status, str):
            status = AssetLifecycleStatus(status.upper())
        return [
            aid for aid, entry in self._states.items()
            if entry.get("status") == status.value
        ]

    def get_winners(self) -> list[str]:
        """获取所有 WINNER 素材。"""
        return self.get_by_status(AssetLifecycleStatus.WINNER)

    def get_dna_ready(self) -> list[str]:
        """获取所有待分析 DNA 的 WINNER 素材。"""
        return self.get_by_status(AssetLifecycleStatus.WINNER)

    def get_dna_analyzed(self) -> list[str]:
        """获取所有已分析 DNA 的素材。"""
        return self.get_by_status(AssetLifecycleStatus.DNA_ANALYZED)

    def mark_failed(self, asset_id: str, reason: str = "") -> bool:
        """标记素材为失败（低 ROAS）。"""
        return self.transition(asset_id, AssetLifecycleStatus.FAILED, {
            "failure_reason": reason,
            "failed_at": datetime.now().isoformat(),
        })

    def mark_archived(self, asset_id: str) -> bool:
        """标记素材为归档。"""
        return self.transition(asset_id, AssetLifecycleStatus.ARCHIVED)

    def count_by_status(self) -> dict[str, int]:
        """按状态统计。"""
        counts: dict[str, int] = {}
        for entry in self._states.values():
            s = entry.get("status", AssetLifecycleStatus.NEW.value)
            counts[s] = counts.get(s, 0) + 1
        return counts

    def to_summary(self) -> str:
        """生成摘要。"""
        counts = self.count_by_status()
        lines = [
            "=" * 40,
            "  Asset Lifecycle Summary",
            "=" * 40,
            f"  Total tracked: {len(self._states)}",
        ]
        for status in AssetLifecycleStatus:
            count = counts.get(status.value, 0)
            if count > 0:
                lines.append(f"  {status.value:14s}: {count}")
        lines.append("=" * 40)
        return "\n".join(lines)

    def import_from_mapping(
        self,
        asset_references: list[Any],
        default_status: AssetLifecycleStatus = AssetLifecycleStatus.MATCHED,
    ) -> int:
        """从 CreativeAssetReference 列表批量导入。

        Args:
            asset_references: CreativeAssetReference 列表
            default_status:   默认状态

        Returns:
            导入数量
        """
        count = 0
        for ref in asset_references:
            asset_id = ref.eagle_v_number or ref.eagle_filename
            if not asset_id:
                continue
            if asset_id not in self._states:
                self._states[asset_id] = {
                    "status": default_status.value,
                    "created_at": datetime.now().isoformat(),
                    "history": [],
                    "creative_id": ref.creative_id,
                    "eagle_filename": ref.eagle_filename,
                    "local_path": ref.local_path,
                }
                count += 1
        self._save()
        return count

    # ── Internal ────────────────────────────────────────

    def _get_or_create(self, asset_id: str) -> dict[str, Any]:
        if asset_id not in self._states:
            self._states[asset_id] = {
                "status": AssetLifecycleStatus.NEW.value,
                "created_at": datetime.now().isoformat(),
                "history": [],
            }
        return self._states[asset_id]

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                self._states = json.load(f)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._states, f, indent=2, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"AssetLifecycleManager(assets={len(self._states)})"