"""E11.2.3 — EagleScannerWorker。

持续运行扫描 Eagle 库，检测新素材并发布 EAGLE_ASSET_DISCOVERED 事件。

触发机制：
  - 首次运行：全量扫描（scan_full）
  - 后续运行：增量扫描（scan_incremental）
  - 新素材逐个发布事件

事件流：
  输入： 无（定时触发）
  输出： EAGLE_ASSET_DISCOVERED（每个新素材）
  完成： EAGLE_SCAN_COMPLETED
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from market_ops.creative_asset_binding.eagle_scanner import EagleScanner

from ..events.asset_events import AssetEvent, AssetEventType

if TYPE_CHECKING:
    from ..events.event_bus_adapter import AssetEventBus


class EagleScannerWorker:
    """Eagle 素材库扫描 Worker。

    将 EagleScanner 包装为事件驱动 Worker：
      - 扫描 Eagle 库
      - 发现新素材 → 发布 EAGLE_ASSET_DISCOVERED
      - 扫描完成 → 发布 EAGLE_SCAN_COMPLETED

    Usage:
        worker = EagleScannerWorker(
            eagle_root="Y:\\Eagle\\公司-市场部门库.library",
            event_bus=bus,
        )
        worker.run()
    """

    def __init__(
        self,
        eagle_root: str,
        event_bus: AssetEventBus,
        eagle_index_path: str = "data/eagle_scan_index.json",
    ) -> None:
        self._scanner = EagleScanner(eagle_root, index_path=eagle_index_path)
        self._bus = event_bus
        self._is_first_run = True

    # ── Public API ───────────────────────────────────────

    def run(self) -> dict[str, int]:
        """执行一次扫描。

        首次运行：全量扫描，所有素材视为新素材
        后续运行：增量扫描，仅检测变更

        Returns:
            {"discovered": int, "total": int}
        """
        if self._is_first_run:
            result = self._scanner.scan_full()
            self._is_first_run = False
            new_assets = result.get("index", None)
            if new_assets:
                new_assets = new_assets.assets
            else:
                new_assets = []
        else:
            result = self._scanner.scan_incremental()
            new_assets = result.get("new_assets", [])

        discovered = 0

        for asset in new_assets:
            v_number = self._extract_v_number(asset.filename)
            event = AssetEvent(
                event_type=AssetEventType.EAGLE_ASSET_DISCOVERED,
                eagle_v_number=v_number,
                payload={
                    "filename": asset.filename,
                    "path": asset.path,
                    "file_hash": asset.file_hash,
                    "file_size": asset.file_size,
                    "created_time": asset.created_at,
                },
            )
            self._bus.publish(event)
            discovered += 1

        # 扫描完成事件
        self._bus.publish(AssetEvent(
            event_type=AssetEventType.EAGLE_SCAN_COMPLETED,
            payload={
                "total": result.get("total", 0),
                "discovered": discovered,
                "new_count": result.get("new_count", discovered),
                "changed_count": result.get("changed_count", 0),
                "removed_count": result.get("removed_count", 0),
                "timestamp": datetime.now().isoformat(),
            },
        ))

        return {"discovered": discovered, "total": result.get("total", 0)}

    def run_scan_only(self) -> dict:
        """仅扫描，不发布事件（用于 dry-run）。"""
        if self._is_first_run:
            result = self._scanner.scan_full()
            self._is_first_run = False
        else:
            result = self._scanner.scan_incremental()
        return result

    @property
    def is_available(self) -> bool:
        return self._scanner.is_available

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _extract_v_number(filename: str) -> str:
        import re
        match = re.search(r"v(\d{4,8})", filename, re.IGNORECASE)
        if match:
            return f"v{match.group(1)}"
        return ""

    def __repr__(self) -> str:
        return f"EagleScannerWorker(first_run={self._is_first_run})"