"""Thumbnail Downloader — 从 Facebook CDN 下载缩略图

遍历 creative_performance_raw.json 的 thumbnail_url,
下载到 output/performance_grounded/thumbnails/{ad_id}.jpg
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

from ..config import OUTPUT_DIR, THUMBNAILS_DIR, ensure_dirs


class ThumbnailDownloader:
    """缩略图下载器"""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or THUMBNAILS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_all(self, records: List[dict],
                     skip_existing: bool = True) -> Dict[str, Path]:
        """批量下载缩略图

        Args:
            records: creative_performance_raw.json 的 records
            skip_existing: 是否跳过已下载的

        Returns:
            {ad_id: local_path}
        """
        if not HAS_HTTPX:
            print("[ThumbnailDownloader] WARNING: httpx 未安装, 使用 urllib 降级")

        # 筛选有 thumbnail_url 且 is_image 的记录
        to_download = []
        for r in records:
            if r.get("is_image") and r.get("thumbnail_url"):
                to_download.append(r)

        print(f"[ThumbnailDownloader] 待下载: {len(to_download)} 张缩略图")

        downloaded: Dict[str, Path] = {}
        skipped = 0
        failed = 0

        for i, record in enumerate(to_download):
            ad_id = record["ad_id"]
            url = record["thumbnail_url"]
            local_path = self.output_dir / f"{ad_id}.jpg"

            if skip_existing and local_path.exists():
                downloaded[ad_id] = local_path
                skipped += 1
                continue

            success = self._download_one(url, local_path)
            if success:
                downloaded[ad_id] = local_path
            else:
                failed += 1

            if (i + 1) % 100 == 0:
                print(f"  进度: {i+1}/{len(to_download)} "
                      f"(下载: {len(downloaded)-skipped}, 跳过: {skipped}, 失败: {failed})")

        print(f"[ThumbnailDownloader] 完成: 成功 {len(downloaded)}, "
              f"跳过 {skipped}, 失败 {failed}")

        return downloaded

    def _download_one(self, url: str, local_path: Path) -> bool:
        """下载单张图片"""
        try:
            if HAS_HTTPX:
                with httpx.Client(timeout=30, follow_redirects=True) as client:
                    response = client.get(url)
                    if response.status_code == 200:
                        local_path.write_bytes(response.content)
                        return True
            else:
                import urllib.request
                urllib.request.urlretrieve(url, str(local_path))
                return True
        except Exception as e:
            # 静默失败, 部分 CDN URL 可能过期
            return False

    def get_url_hash(self, url: str) -> str:
        """生成 URL 的 hash (用于去重)"""
        return hashlib.md5(url.encode()).hexdigest()[:12]
