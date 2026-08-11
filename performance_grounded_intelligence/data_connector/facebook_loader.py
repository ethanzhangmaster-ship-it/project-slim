"""Facebook Data Loader — 加载 Facebook API JSON + Ads Manager Excel

数据源:
1. p04_full_ad_hierarchy.json (API 拉取, 含 creative_id / thumbnail_url / video_id)
2. 无标题报告.xlsx (后台导出, 含 广告编号 / 花费)

输出: List[dict] 每条广告的完整 Facebook 侧数据
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

import openpyxl

from ..config import FB_API_JSON, FB_EXCEL_PATH


class FacebookDataLoader:
    """Facebook 数据加载器"""

    def __init__(self,
                 api_path: Optional[Path] = None,
                 excel_path: Optional[Path] = None):
        self.api_path = api_path or FB_API_JSON
        self.excel_path = excel_path or FB_EXCEL_PATH

        self._api_records: List[dict] = []
        self._excel_records: Dict[str, dict] = {}

    def load(self) -> Dict[str, dict]:
        """加载并融合 API + Excel 数据, 返回 {ad_id: {...}}"""
        self._load_api()
        self._load_excel()
        return self._merge()

    def _load_api(self):
        """加载 Facebook API JSON"""
        if not self.api_path.exists():
            raise FileNotFoundError(f"Facebook API 文件不存在: {self.api_path}")

        with open(self.api_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._api_records = data.get("records", [])
        print(f"[FacebookLoader] API 记录数: {len(self._api_records)}")

    def _load_excel(self):
        """加载 Facebook Ads Manager Excel 导出"""
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Facebook Excel 文件不存在: {self.excel_path}")

        wb = openpyxl.load_workbook(self.excel_path, read_only=True)
        ws = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        wb.close()

        # 列: 广告名称(0), 广告(1), 广告编号(2), 覆盖人数(3), 展示次数(4),
        #      频次(5), 货币(6), 已花费金额USD(7), 归因设置(8), 开始(9), 结束(10)
        data_rows = all_rows[2:]  # skip header + summary row

        for row in data_rows:
            ad_id = str(row[2] or "").strip()
            if not ad_id:
                continue
            self._excel_records[ad_id] = {
                "ad_name": row[0] or "",
                "ad_id": ad_id,
                "spend": float(row[7] or 0),
                "impressions": int(float(row[4] or 0)),
                "reach": int(float(row[3] or 0)),
                "frequency": float(row[5] or 0),
                "date_start": str(row[9] or ""),
                "date_end": str(row[10] or ""),
            }

        print(f"[FacebookLoader] Excel 广告数: {len(self._excel_records)}")

    def _merge(self) -> Dict[str, dict]:
        """融合 API 和 Excel 数据, 以 Excel 为主 (花费最权威)"""
        # 从 API 建立 ad_id -> 附加信息 映射
        api_by_id: Dict[str, dict] = {}
        for r in self._api_records:
            aid = str(r.get("ad_id", "") or "").strip()
            if aid:
                api_by_id[aid] = {
                    "creative_id": r.get("creative_id", ""),
                    "thumbnail_url": r.get("thumbnail_url", ""),
                    "video_id": r.get("video_id", ""),
                    "creative_type": r.get("creative_type", ""),
                    "api_spend": float(r.get("spend", 0) or 0),
                    "api_impressions": int(float(r.get("impressions", 0) or 0)),
                    "api_installs": int(float(r.get("installs", 0) or 0)),
                }

        # 合并: Excel 为花费基准, API 补充 creative 元数据
        merged: Dict[str, dict] = {}
        for ad_id, excel_data in self._excel_records.items():
            record = {**excel_data}
            api_info = api_by_id.get(ad_id, {})
            record["creative_id"] = api_info.get("creative_id", "")
            record["thumbnail_url"] = api_info.get("thumbnail_url", "")
            record["video_id"] = api_info.get("video_id", "")
            record["creative_type"] = api_info.get("creative_type", "")
            record["has_api_data"] = ad_id in api_by_id
            merged[ad_id] = record

        api_match = sum(1 for v in merged.values() if v["has_api_data"])
        print(f"[FacebookLoader] 融合完成: {len(merged)} 广告, "
              f"API匹配 {api_match} ({api_match/len(merged)*100:.1f}%)")

        return merged
