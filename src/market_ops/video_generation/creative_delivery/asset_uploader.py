from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class UploadResult:
    asset_id: str
    creative_id: str
    platform: str
    status: str
    url: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class AssetUploader:
    def __init__(self):
        self.platform_uploaders = {
            "meta": self._upload_to_meta,
            "google": self._upload_to_google,
            "asa": self._upload_to_asa,
            "tiktok": self._upload_to_tiktok,
        }

    def upload(self, creative_id: str, platform: str, asset_path: str, asset_type: str = "video") -> UploadResult:
        uploader = self.platform_uploaders.get(platform, self._upload_to_meta)
        return uploader(creative_id, asset_path, asset_type)

    def _upload_to_meta(self, creative_id: str, asset_path: str, asset_type: str) -> UploadResult:
        return UploadResult(
            asset_id=f"meta_asset_{hash(creative_id) % 10000:04d}",
            creative_id=creative_id,
            platform="meta",
            status="uploaded",
            url=f"https://meta.com/assets/{hash(creative_id) % 10000:04d}",
            details={"asset_type": asset_type, "path": asset_path},
        )

    def _upload_to_google(self, creative_id: str, asset_path: str, asset_type: str) -> UploadResult:
        return UploadResult(
            asset_id=f"google_asset_{hash(creative_id) % 10000:04d}",
            creative_id=creative_id,
            platform="google",
            status="uploaded",
            url=f"https://google.com/assets/{hash(creative_id) % 10000:04d}",
            details={"asset_type": asset_type, "path": asset_path},
        )

    def _upload_to_asa(self, creative_id: str, asset_path: str, asset_type: str) -> UploadResult:
        return UploadResult(
            asset_id=f"asa_asset_{hash(creative_id) % 10000:04d}",
            creative_id=creative_id,
            platform="asa",
            status="uploaded",
            url=f"https://apple.com/assets/{hash(creative_id) % 10000:04d}",
            details={"asset_type": asset_type, "path": asset_path},
        )

    def _upload_to_tiktok(self, creative_id: str, asset_path: str, asset_type: str) -> UploadResult:
        return UploadResult(
            asset_id=f"tiktok_asset_{hash(creative_id) % 10000:04d}",
            creative_id=creative_id,
            platform="tiktok",
            status="uploaded",
            url=f"https://tiktok.com/assets/{hash(creative_id) % 10000:04d}",
            details={"asset_type": asset_type, "path": asset_path},
        )

    def upload_demo(self) -> UploadResult:
        return self.upload("creative_001", "meta", "/path/to/video.mp4", "video")
