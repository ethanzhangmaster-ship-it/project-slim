"""E11.2.3 — BindingWorker。

监听 EAGLE_ASSET_DISCOVERED 事件，执行 A-Number 匹配，
发布 ASSET_MATCHED 事件。

事件流：
  输入：  EAGLE_ASSET_DISCOVERED
  输出：  ASSET_MATCHED（匹配成功）
  完成：  BINDING_COMPLETED

匹配逻辑：
  1. 从新素材的 v-number 提取数字部分
  2. 在已同步的 Facebook 广告中搜索匹配的 A-number
  3. 生成 CreativeAssetReference 并保存到 Repository
  4. 发布 ASSET_MATCHED
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from market_ops.creative_asset_binding.a_number_matcher import ANumberMatcher
from market_ops.creative_repository.assets.asset_binding_repository import AssetBindingRepository

from ..events.asset_events import AssetEvent, AssetEventType

if TYPE_CHECKING:
    from ..events.event_bus_adapter import AssetEventBus


class BindingWorker:
    """资产绑定 Worker。

    监听新素材发现事件，执行 A-Number 匹配。

    Usage:
        worker = BindingWorker(
            creative_storage_root="data/creatives",
            event_bus=bus,
        )
        bus.subscribe("eagle_asset_discovered", worker.on_asset_discovered)
    """

    def __init__(
        self,
        creative_storage_root: str = "data/creatives",
        event_bus: AssetEventBus | None = None,
    ) -> None:
        self._matcher = ANumberMatcher()
        self._repository = AssetBindingRepository(creative_storage_root)
        self._bus = event_bus
        self._match_count = 0

    # ── Event Handler ────────────────────────────────────

    def on_asset_discovered(self, event: AssetEvent) -> None:
        """处理 EAGLE_ASSET_DISCOVERED 事件。

        尝试将新素材匹配到已存在的 Facebook 广告。
        """
        eagle_v = event.eagle_v_number
        payload = event.payload

        if not eagle_v:
            return

        # 提取 v-number 数字部分
        v_num = self._matcher.extract_numeric_v(payload.get("filename", ""))
        if not v_num:
            return

        # 在已同步的 creative 中搜索匹配
        existing_refs = self._repository.load_all()
        matched = False

        for ref in existing_refs:
            if ref.ad_name:
                a_num = self._matcher.extract_numeric_a(ref.ad_name)
                if a_num and a_num in v_num:
                    # 找到匹配！更新 ref 信息
                    ref.eagle_v_number = eagle_v
                    ref.eagle_filename = payload.get("filename", "")
                    ref.local_path = payload.get("path", "")
                    ref.match_method = ref.match_method  # keep existing
                    ref.confidence = 1.0

                    self._repository.save(ref)
                    self._match_count += 1

                    # 发布匹配成功事件
                    if self._bus:
                        self._bus.publish(AssetEvent(
                            event_type=AssetEventType.ASSET_MATCHED,
                            creative_id=ref.creative_id,
                            eagle_v_number=eagle_v,
                            payload={
                                "ad_name": ref.ad_name,
                                "a_number": ref.a_number,
                                "eagle_filename": ref.eagle_filename,
                                "local_path": ref.local_path,
                                "match_method": "a_number",
                                "confidence": 1.0,
                            },
                        ))
                    matched = True
                    break

        if not matched:
            # 新素材暂未匹配到广告，记录但不发布事件
            # 等待 Facebook Sync 后再匹配
            pass

    def on_facebook_synced(self, event: AssetEvent) -> None:
        """处理 FACEBOOK_CREATIVE_SYNCED 事件。

        反向匹配：新广告来了，尝试匹配已有 Eagle 素材。
        """
        creative_id = event.creative_id
        ad_name = event.payload.get("ad_name", "")

        if not creative_id or not ad_name:
            return

        a_num = self._matcher.extract_numeric_a(ad_name)
        if not a_num:
            return

        # 搜索已有 Eagle 素材
        eagle_refs = self._repository.load_all_by_source("eagle")
        for ref in eagle_refs:
            if ref.eagle_v_number:
                v_num = self._matcher.extract_numeric_v(ref.eagle_filename)
                if v_num and a_num in v_num:
                    # 匹配成功
                    ref.creative_id = creative_id
                    ref.ad_name = ad_name
                    ref.a_number = self._matcher.extract_a_number(ad_name) or ""
                    ref.confidence = 1.0
                    self._repository.save(ref)
                    self._match_count += 1

                    if self._bus:
                        self._bus.publish(AssetEvent(
                            event_type=AssetEventType.ASSET_MATCHED,
                            creative_id=creative_id,
                            eagle_v_number=ref.eagle_v_number,
                            payload={
                                "ad_name": ad_name,
                                "a_number": ref.a_number,
                                "eagle_filename": ref.eagle_filename,
                                "local_path": ref.local_path,
                                "match_method": "a_number",
                                "confidence": 1.0,
                            },
                        ))
                    return

    # ── Query ────────────────────────────────────────────

    @property
    def match_count(self) -> int:
        return self._match_count

    def __repr__(self) -> str:
        return f"BindingWorker(matches={self._match_count})"