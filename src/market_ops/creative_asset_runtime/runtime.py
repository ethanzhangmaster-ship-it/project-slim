"""E11.2.3 — AssetRuntime（事件驱动的持续资产绑定运行时）。

编排 4 个 Worker + EventBus，将 E11.2 从定时脚本升级为
事件驱动的持续运行服务。

事件链：
  EagleScannerWorker
    → EAGLE_ASSET_DISCOVERED
    → BindingWorker
    → ASSET_MATCHED
    → MaterializerWorker
    → ASSET_MATERIALIZED
    → LifecycleWorker
    → WINNER_DETECTED

Usage:
    runtime = AssetRuntime(
        eagle_root="Y:\\Eagle\\公司-市场部门库.library",
        creative_storage_root="data/creatives",
    )
    runtime.start()           # 订阅事件 + 首次扫描
    report = runtime.run_once()  # 执行一次完整管线
    print(runtime.get_status())
    runtime.shutdown()
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .events.asset_events import AssetEvent, AssetEventType
from .events.event_bus_adapter import AssetEventBus
from .workers.eagle_worker import EagleScannerWorker
from .workers.binding_worker import BindingWorker
from .workers.materializer_worker import MaterializerWorker
from .workers.lifecycle_worker import LifecycleWorker


class AssetRuntime:
    """Creative Asset Runtime — 持续资产绑定运行时。

    管理 4 个 Worker 的生命周期 + 事件总线。

    运行模式：
      - start() + run_once(): 手动触发一次完整管线
      - start() + 外部定时调用 eagle_worker.run(): 定时扫描

    Usage:
        runtime = AssetRuntime(
            eagle_root="Y:\\Eagle\\公司-市场部门库.library",
            creative_storage_root="data/creatives",
        )
        runtime.start()
        report = runtime.run_once()
        print(report["summary"])
        runtime.shutdown()
    """

    # 运行时状态文件
    RUNTIME_STATE_KEY = "runtime_state.json"

    def __init__(
        self,
        eagle_root: str = "",
        creative_storage_root: str = "data/creatives",
        eagle_index_path: str = "data/eagle_scan_index.json",
        lifecycle_path: str = "data/asset_lifecycle.json",
        runtime_dir: str = "data/runtime",
    ) -> None:
        self._eagle_root = eagle_root
        self._creative_storage_root = creative_storage_root
        self._runtime_dir = Path(runtime_dir)
        self._runtime_dir.mkdir(parents=True, exist_ok=True)

        # 事件总线
        replay_log = self._runtime_dir / "asset_events.jsonl"
        failed_log = self._runtime_dir / "failed_events.json"
        self._bus = AssetEventBus(
            replay_log=str(replay_log),
            failed_log=str(failed_log),
        )

        # Workers
        self._eagle_worker = EagleScannerWorker(
            eagle_root=eagle_root,
            event_bus=self._bus,
            eagle_index_path=eagle_index_path,
        )
        self._binding_worker = BindingWorker(
            creative_storage_root=creative_storage_root,
            event_bus=self._bus,
        )
        self._materializer_worker = MaterializerWorker(
            creative_storage_root=creative_storage_root,
            event_bus=self._bus,
        )
        self._lifecycle_worker = LifecycleWorker(
            lifecycle_path=lifecycle_path,
            event_bus=self._bus,
        )

        self._started = False
        self._run_count = 0

    # ── Public API ───────────────────────────────────────

    def start(self) -> None:
        """启动 Runtime：订阅事件。

        订阅关系：
          EAGLE_ASSET_DISCOVERED → BindingWorker.on_asset_discovered
          FACEBOOK_CREATIVE_SYNCED → BindingWorker.on_facebook_synced
          ASSET_MATCHED → MaterializerWorker.on_asset_matched
          ASSET_MATERIALIZED → LifecycleWorker.on_asset_materialized
          PERFORMANCE_UPDATED → LifecycleWorker.on_performance_updated
        """
        self._bus.subscribe(
            AssetEventType.EAGLE_ASSET_DISCOVERED,
            self._binding_worker.on_asset_discovered,
        )
        self._bus.subscribe(
            AssetEventType.FACEBOOK_CREATIVE_SYNCED,
            self._binding_worker.on_facebook_synced,
        )
        self._bus.subscribe(
            AssetEventType.ASSET_MATCHED,
            self._materializer_worker.on_asset_matched,
        )
        self._bus.subscribe(
            AssetEventType.ASSET_MATERIALIZED,
            self._lifecycle_worker.on_asset_materialized,
        )
        self._bus.subscribe(
            AssetEventType.PERFORMANCE_UPDATED,
            self._lifecycle_worker.on_performance_updated,
        )

        self._started = True
        self._save_state()

    def run_once(self) -> dict[str, Any]:
        """执行一次完整管线：扫描 → 匹配 → 实体化 → 生命周期。

        Returns:
            {
                "summary": str,
                "eagle_scan": {...},
                "bindings": {...},
                "materialized": {...},
                "lifecycle": {...},
                "event_bus": {...},
                "elapsed_seconds": float,
            }
        """
        if not self._started:
            self.start()

        self._run_count += 1
        started = datetime.now()

        # Phase 1: Eagle Scan
        scan_result = self._eagle_worker.run()
        # 事件已在 worker 中发布，无需手动处理

        # Phase 2-4: 事件链自动触发
        # EAGLE_ASSET_DISCOVERED → BindingWorker → ASSET_MATCHED
        # → MaterializerWorker → ASSET_MATERIALIZED → LifecycleWorker

        # 重试失败事件
        retried = self._bus.retry_failed()

        elapsed = (datetime.now() - started).total_seconds()

        report = {
            "eagle_scan": {
                "discovered": scan_result["discovered"],
                "total": scan_result["total"],
            },
            "bindings": {
                "matched": self._binding_worker.match_count,
            },
            "materialized": {
                "count": self._materializer_worker.materialized_count,
                "failed": self._materializer_worker.failed_count,
            },
            "lifecycle": {
                "winners": self._lifecycle_worker.winner_count,
                "failed": self._lifecycle_worker.failed_count,
                "summary": self._lifecycle_worker.to_summary(),
            },
            "event_bus": self._bus.get_stats(),
            "retried_failed": retried,
            "elapsed_seconds": round(elapsed, 1),
        }
        report["summary"] = self._build_summary(report)

        self._save_state()
        return report

    def run_eagle_scan_only(self) -> dict[str, Any]:
        """仅执行 Eagle 扫描（不触发后续绑定）。"""
        if not self._started:
            self.start()
        return self._eagle_worker.run_scan_only()

    def inject_performance(
        self,
        creative_id: str,
        spend: float = 0,
        revenue: float = 0,
        roas: float = 0,
        impressions: float = 0,
        installs: int = 0,
        eagle_v_number: str = "",
    ) -> None:
        """注入性能数据，触发生命周期更新。

        用于测试或外部系统注入性能数据。

        Args:
            creative_id: Facebook creative_id
            spend:       花费
            revenue:     收入
            roas:        ROAS
            impressions: 展示量
            installs:    安装数
            eagle_v_number: Eagle v 号
        """
        self._bus.publish(AssetEvent(
            event_type=AssetEventType.PERFORMANCE_UPDATED,
            creative_id=creative_id,
            eagle_v_number=eagle_v_number,
            payload={
                "spend": spend,
                "revenue": revenue,
                "roas": roas,
                "impressions": impressions,
                "installs": installs,
            },
        ))

    def inject_facebook_sync(
        self,
        creative_id: str,
        ad_name: str,
    ) -> None:
        """注入 Facebook 广告同步事件。

        用于测试或外部 Facebook Sync 触发。
        """
        self._bus.publish(AssetEvent(
            event_type=AssetEventType.FACEBOOK_CREATIVE_SYNCED,
            creative_id=creative_id,
            payload={
                "ad_name": ad_name,
            },
        ))

    def get_status(self) -> dict[str, Any]:
        """获取 Runtime 运行状态。"""
        return {
            "started": self._started,
            "run_count": self._run_count,
            "eagle_available": self._eagle_worker.is_available,
            "eagle_first_run": self._eagle_worker._is_first_run if hasattr(self._eagle_worker, '_is_first_run') else False,
            "bindings_matched": self._binding_worker.match_count,
            "materialized": self._materializer_worker.materialized_count,
            "materialize_failed": self._materializer_worker.failed_count,
            "lifecycle_winners": self._lifecycle_worker.winner_count,
            "lifecycle_failed": self._lifecycle_worker.failed_count,
            "event_bus": self._bus.get_stats(),
            "lifecycle_summary": self._lifecycle_worker.to_summary(),
        }

    def get_winners(self) -> list[str]:
        """获取所有 WINNER 素材。"""
        return self._lifecycle_worker.get_winners()

    def get_dna_ready(self) -> list[str]:
        """获取所有待 DNA 分析的 WINNER 素材。"""
        return self._lifecycle_worker.get_dna_ready()

    def shutdown(self) -> None:
        """关闭 Runtime，释放资源。"""
        self._save_state()
        self._bus.shutdown()
        self._started = False

    @property
    def event_bus(self) -> AssetEventBus:
        return self._bus

    # ── Internal ────────────────────────────────────────

    def _save_state(self) -> None:
        state_path = self._runtime_dir / self.RUNTIME_STATE_KEY
        state = {
            "started": self._started,
            "run_count": self._run_count,
            "updated_at": datetime.now().isoformat(),
            "eagle_available": self._eagle_worker.is_available,
            "bindings_matched": self._binding_worker.match_count,
            "materialized": self._materializer_worker.materialized_count,
            "materialize_failed": self._materializer_worker.failed_count,
            "lifecycle_winners": self._lifecycle_worker.winner_count,
            "lifecycle_failed": self._lifecycle_worker.failed_count,
            "event_bus_stats": self._bus.get_stats(),
        }
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def _build_summary(self, report: dict[str, Any]) -> str:
        lines = [
            "=" * 60,
            "  E11.2.3 Asset Runtime Report",
            "=" * 60,
            "",
            f"  Eagle Scan:     {report['eagle_scan']['discovered']} discovered "
            f"of {report['eagle_scan']['total']} total",
            f"  Bindings:       {report['bindings']['matched']} matched",
            f"  Materialized:   {report['materialized']['count']} "
            f"({report['materialized']['failed']} failed)",
            f"  Lifecycle:      {report['lifecycle']['winners']} winners, "
            f"{report['lifecycle']['failed']} failed",
            f"  Events:         {report['event_bus']['total_events']} total, "
            f"{report['retried_failed']} retried",
            f"  Elapsed:        {report['elapsed_seconds']}s",
            "=" * 60,
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"AssetRuntime(eagle={self._eagle_root!r}, "
            f"started={self._started}, runs={self._run_count})"
        )