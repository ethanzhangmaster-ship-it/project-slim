"""E11.2.2 — Binding Scheduler（持续资产绑定管线编排）。

将 E11.2 从一次性迁移工具升级为持续运行管线。

流程：
  1. Eagle Scanner → 检测新素材
  2. Facebook Sync → 获取新广告
  3. A-Number Matcher → 匹配新素材到新广告
  4. Asset Binding Repository → 保存匹配结果
  5. Asset Materializer → 写入 entity.json
  6. Asset Lifecycle → 更新状态

Usage:
    scheduler = BindingScheduler(
        eagle_root="Y:\\Eagle\\公司-市场部门库.library",
        creative_storage_root="data/creatives",
        facebook_accounts=[...],
    )
    report = scheduler.run_incremental()
    print(report["summary"])
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .eagle_scanner import EagleScanner
from .a_number_matcher import ANumberMatcher
from .asset_lifecycle import AssetLifecycleManager, AssetLifecycleStatus
from market_ops.creative_repository.assets.asset_reference import CreativeAssetReference
from market_ops.creative_repository.assets.asset_binding_repository import AssetBindingRepository
from market_ops.creative_repository.assets.asset_materializer import AssetBindingMaterializer
from market_ops.creative_repository.assets.identity_resolver import IdentityResolver


class BindingScheduler:
    """持续资产绑定管线编排器。

    负责周期性地执行完整的资产绑定流程：
    扫描 → 匹配 → 存储 → 实体化 → 生命周期管理

    Usage:
        scheduler = BindingScheduler(
            eagle_root="Y:\\Eagle\\公司-市场部门库.library",
            creative_storage_root="data/creatives",
        )
        report = scheduler.run_incremental()
        print(report["summary"])
    """

    def __init__(
        self,
        eagle_root: str = "",
        creative_storage_root: str = "data/creatives",
        eagle_index_path: str = "data/eagle_scan_index.json",
        lifecycle_path: str = "data/asset_lifecycle.json",
        report_dir: str = "data/binding_reports",
    ) -> None:
        self._eagle_root = eagle_root
        self._creative_storage_root = creative_storage_root
        self._report_dir = Path(report_dir)

        # 子模块
        self._scanner = EagleScanner(eagle_root, index_path=eagle_index_path)
        self._matcher = ANumberMatcher()
        self._repository = AssetBindingRepository(creative_storage_root)
        self._resolver = IdentityResolver(creative_storage_root)
        self._materializer = AssetBindingMaterializer(
            creative_storage_root, self._resolver
        )
        self._lifecycle = AssetLifecycleManager(lifecycle_path)

    # ── Public API ───────────────────────────────────────

    def run_incremental(self) -> dict[str, Any]:
        """执行增量资产绑定管线。

        完整流程：
          1. 扫描 Eagle → 检测新素材
          2. 匹配新素材 → 生成 CreativeAssetReference
          3. 保存到 Repository
          4. 实体化到 entity.json
          5. 更新生命周期状态

        Returns:
            {
                "summary": str,
                "eagle_scan": {...},
                "bindings": {...},
                "lifecycle": {...},
                "elapsed_seconds": float,
            }
        """
        started = datetime.now()
        report: dict[str, Any] = {}

        # ── Phase 1: Eagle Scan ──────────────────────────
        report["eagle_scan"] = self._scanner.scan_incremental()
        new_assets = report["eagle_scan"]["new_assets"]

        # ── Phase 2: Match new assets ────────────────────
        # 注意：此阶段需要 Facebook 广告数据。
        # 如果 SyncEngine 尚未运行，新素材无法匹配，会进入待匹配队列。
        new_bindings = self._match_new_assets(new_assets)
        report["bindings"] = {
            "new_assets_scanned": len(new_assets),
            "new_matches": len(new_bindings),
            "unmatched": len(new_assets) - len(new_bindings),
        }

        # ── Phase 3: Save & Materialize ──────────────────
        materialized = 0
        for ref in new_bindings:
            if not self._repository.exists(ref.creative_id):
                self._repository.save(ref)
                self._materializer.materialize(ref.creative_id)
                materialized += 1

        report["bindings"]["materialized"] = materialized

        # ── Phase 4: Update Lifecycle ────────────────────
        lifecycle_count = self._lifecycle.import_from_mapping(new_bindings)
        report["lifecycle"] = {
            "imported": lifecycle_count,
            "counts": self._lifecycle.count_by_status(),
        }

        # ── Finalize ─────────────────────────────────────
        elapsed = (datetime.now() - started).total_seconds()
        report["elapsed_seconds"] = round(elapsed, 1)
        report["summary"] = self._build_summary(report)

        self._save_report(report)
        return report

    def run_full_historical(self, mapping_path: str) -> dict[str, Any]:
        """执行历史数据全量导入（首次运行）。

        Args:
            mapping_path: creative_mapping_v2.json 路径

        Returns:
            {
                "summary": str,
                "eagle_scan": {...},
                "migration": {...},
                "lifecycle": {...},
                "elapsed_seconds": float,
            }
        """
        from market_ops.creative_repository.assets.creative_mapping_loader import CreativeMappingLoader

        started = datetime.now()

        # Phase 1: Full Eagle scan
        eagle_report = self._scanner.scan_full()

        # Phase 2: Load historical mapping
        loader = CreativeMappingLoader()
        refs = loader.load(mapping_path)

        # Phase 3: Save to repository
        written = 0
        for ref in refs:
            if not self._repository.exists(ref.creative_id):
                self._repository.save(ref)
                written += 1

        # Phase 4: Materialize
        materialize_report = self._materializer.materialize_all()

        # Phase 5: Import lifecycle
        lifecycle_count = self._lifecycle.import_from_mapping(refs)

        elapsed = (datetime.now() - started).total_seconds()

        report = {
            "eagle_scan": {
                "total": eagle_report["total"],
                "video_count": eagle_report["video_count"],
                "image_count": eagle_report["image_count"],
            },
            "migration": {
                "total": len(refs),
                "written": written,
                "materialized": materialize_report["materialized"],
            },
            "lifecycle": {
                "imported": lifecycle_count,
                "counts": self._lifecycle.count_by_status(),
            },
            "elapsed_seconds": round(elapsed, 1),
        }
        report["summary"] = self._build_summary(report)
        self._save_report(report)
        return report

    def get_pipeline_status(self) -> dict[str, Any]:
        """获取管线当前状态。"""
        return {
            "eagle_available": self._scanner.is_available,
            "repository_count": self._repository.count(),
            "resolver_mappings": self._resolver.mapping_count,
            "lifecycle": self._lifecycle.count_by_status(),
            "lifecycle_summary": self._lifecycle.to_summary(),
        }

    # ── Internal ────────────────────────────────────────

    def _match_new_assets(
        self, new_assets: list[Any]
    ) -> list[CreativeAssetReference]:
        """匹配新素材到 Facebook 广告。

        注意：这需要 Facebook SyncEngine 已经运行过，creative_id 和 ad_name
        已经存在于 CreativeStorage 中。如果 SyncEngine 未运行，返回空列表。
        """
        # 从 CreativeStorage 获取所有已同步的 creative
        refs = self._repository.load_all()
        if not refs:
            return []

        # 构建 ad_name → creative_id 映射
        ad_name_to_id: dict[str, str] = {}
        for ref in refs:
            if ref.ad_name:
                ad_name_to_id[ref.ad_name] = ref.creative_id

        results: list[CreativeAssetReference] = []

        for new_asset in new_assets:
            # 搜索匹配的 Facebook 广告
            v_num = self._matcher.extract_numeric_v(new_asset.filename)
            if not v_num:
                continue

            # 在已知 ad_name 中搜索匹配的 A-number
            for ad_name, creative_id in ad_name_to_id.items():
                a_num = self._matcher.extract_numeric_a(ad_name)
                if a_num and a_num in v_num:
                    ref = self._matcher.match_to_asset(
                        creative_id=creative_id,
                        ad_name=ad_name,
                        scanner=self._scanner,
                    )
                    if ref:
                        results.append(ref)
                    break

        return results

    def _save_report(self, report: dict[str, Any]) -> None:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        filename = f"binding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = self._report_dir / filename

        # 过滤不可序列化的对象（EagleAsset, EagleIndex 等）
        safe = self._make_serializable(report)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(safe, f, indent=2, ensure_ascii=False)

    def _make_serializable(self, obj: Any) -> Any:
        """递归转换不可序列化对象为 dict。"""
        if isinstance(obj, dict):
            return {
                k: self._make_serializable(v)
                for k, v in obj.items()
                if k not in ("new_assets", "changed_assets", "index", "removed_paths")
            }
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, "to_dict"):
            return self._make_serializable(obj.to_dict())
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)

    def _build_summary(self, report: dict[str, Any]) -> str:
        lines = [
            "=" * 60,
            "  E11.2 Binding Pipeline Report",
            "=" * 60,
            "",
        ]

        if "eagle_scan" in report:
            es = report["eagle_scan"]
            lines.append(f"  Eagle Scan: {es.get('total', 0)} total, "
                         f"+{es.get('new_count', 0)} new, "
                         f"{es.get('changed_count', 0)} changed")

        if "bindings" in report:
            b = report["bindings"]
            lines.append(f"  Bindings:   {b.get('new_matches', 0)} matched, "
                         f"{b.get('materialized', 0)} materialized")

        if "migration" in report:
            m = report["migration"]
            lines.append(f"  Migration:  {m.get('total', 0)} records, "
                         f"{m.get('written', 0)} new, "
                         f"{m.get('materialized', 0)} materialized")

        if "lifecycle" in report:
            lc = report["lifecycle"]
            lines.append(f"  Lifecycle:  {lc.get('imported', 0)} imported")

        lines.append(f"  Elapsed:    {report['elapsed_seconds']}s")
        lines.append("=" * 60)

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"BindingScheduler(eagle={self._eagle_root!r}, "
            f"storage={self._creative_storage_root!r})"
        )