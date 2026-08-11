"""Asset Mapper — ad_id → visual_asset_id 映射

综合 CLIP 聚类结果和 performance 数据,
生成 visual_assets.json: 每个 asset_id 对应一组 ad_ids 及其聚合性能指标。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from ..config import OUTPUT_DIR, ensure_dirs


class AssetMapper:
    """素材映射器: 将 cluster 结果与 performance 数据合并"""

    def __init__(self):
        self.assets: List[dict] = []

    def build_assets(self,
                     cluster_labels: Dict[str, int],
                     performance_records: List[dict]) -> List[dict]:
        """从聚类标签和性能数据构建 visual_assets

        Args:
            cluster_labels: {ad_id: cluster_id}
            performance_records: creative_performance_raw.json 的 records

        Returns:
            visual_assets 列表
        """
        # 建立 ad_id → performance 索引
        perf_index = {r["ad_id"]: r for r in performance_records}

        # 按 cluster 分组
        groups = defaultdict(list)
        for ad_id, cluster_id in cluster_labels.items():
            groups[cluster_id].append(ad_id)

        # 为每个 cluster 生成 asset 记录
        self.assets = []
        for cluster_id, ad_ids in sorted(groups.items()):
            # 聚合性能
            total_spend = 0
            total_iap_revenue = 0
            total_ad_revenue = 0
            total_all_revenue = 0
            total_installs = 0
            platforms = set()
            ad_names = set()
            thumbnail_urls = set()

            for ad_id in ad_ids:
                perf = perf_index.get(ad_id, {})
                total_spend += perf.get("spend", 0)
                total_iap_revenue += perf.get("iap_revenue", 0)
                total_ad_revenue += perf.get("ad_revenue", 0)
                total_all_revenue += perf.get("all_revenue", 0)
                total_installs += perf.get("installs", 0)
                platforms.add(perf.get("platform", "unknown"))
                ad_names.add(perf.get("ad_name", ""))
                thumb = perf.get("thumbnail_url", "")
                if thumb:
                    thumbnail_urls.add(thumb)

            # 计算聚合指标
            iap_roas = total_iap_revenue / total_spend if total_spend > 0 else 0
            total_roas = total_all_revenue / total_spend if total_spend > 0 else 0
            cpi = total_spend / total_installs if total_installs > 0 else 0

            asset = {
                "asset_id": f"asset_{cluster_id:04d}",
                "cluster_id": cluster_id,
                "source_ad_ids": ad_ids,
                "ad_count": len(ad_ids),
                "platforms": sorted(platforms),
                "sample_names": sorted(ad_names)[:5],
                "thumbnail_urls": sorted(thumbnail_urls)[:3],

                # 聚合性能
                "spend": round(total_spend, 2),
                "iap_revenue": round(total_iap_revenue, 2),
                "ad_revenue": round(total_ad_revenue, 2),
                "all_revenue": round(total_all_revenue, 2),
                "installs": total_installs,
                "iap_roas": round(iap_roas, 4),
                "total_roas": round(total_roas, 4),
                "cpi": round(cpi, 2),
            }

            self.assets.append(asset)

        # 按花费排序
        self.assets.sort(key=lambda x: x["spend"], reverse=True)

        print(f"[AssetMapper] 生成 {len(self.assets)} 个 visual assets")
        return self.assets

    def save(self, output_path: Optional[Path] = None) -> Path:
        """保存 visual_assets.json"""
        ensure_dirs()
        if output_path is None:
            output_path = OUTPUT_DIR / "visual_assets.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8",
                "total_assets": len(self.assets),
                "assets": self.assets,
            }, f, ensure_ascii=False, indent=2)

        print(f"[AssetMapper] 已保存: {output_path}")
        return output_path

    def build_from_thumbnail_url(self, performance_records: List[dict]) -> List[dict]:
        """降级方案: 用 thumbnail_url 直接分组 (不依赖 CLIP)

        当 CLIP 不可用时, 回退到 URL 精确匹配分组。
        """
        # 按 thumbnail_url 分组
        by_thumb = defaultdict(list)
        for r in performance_records:
            if r.get("is_image") and r.get("thumbnail_url"):
                by_thumb[r["thumbnail_url"]].append(r["ad_id"])
            elif r.get("is_image"):
                # 无 thumbnail 的图片广告, 各自成一组
                by_thumb[f"no_thumb_{r['ad_id']}"].append(r["ad_id"])

        # 转换为 cluster_labels 格式
        cluster_labels = {}
        for i, (thumb, ad_ids) in enumerate(by_thumb.items()):
            for ad_id in ad_ids:
                cluster_labels[ad_id] = i

        print(f"[AssetMapper] URL分组: {len(by_thumb)} 组 (从 {len(cluster_labels)} 条广告)")
        return self.build_assets(cluster_labels, performance_records)
