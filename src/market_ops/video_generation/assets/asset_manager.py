"""Asset Manager - 输出资产管理"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class VideoAsset:
    asset_id: str = ""
    task_id: str = ""
    blueprint_id: str = ""
    scene_id: str = ""
    platform: str = ""
    video_path: str = ""
    thumbnail_path: str = ""
    duration: float = 0.0
    resolution: str = ""
    fps: int = 0
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AssetManager:
    """资产管理 - 管理生成的视频资产"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent
        self.base_dir = Path(base_dir)
        self.videos_dir = self.base_dir / "videos"
        self.thumbnails_dir = self.base_dir / "thumbnails"
        self.metadata_dir = self.base_dir / "metadata"
        self.embeddings_dir = self.base_dir / "embeddings"
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in [self.videos_dir, self.thumbnails_dir, self.metadata_dir, self.embeddings_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def register_asset(
        self,
        task_id: str,
        video_path: str,
        blueprint_id: str = "",
        scene_id: str = "",
        platform: str = "",
        quality_score: float = 0.0,
        metadata: Dict[str, Any] = None,
    ) -> VideoAsset:
        asset_id = f"asset_{task_id}"
        asset = VideoAsset(
            asset_id=asset_id,
            task_id=task_id,
            blueprint_id=blueprint_id,
            scene_id=scene_id,
            platform=platform,
            video_path=video_path,
            quality_score=quality_score,
            metadata=metadata or {},
        )
        self._save_metadata(asset)
        return asset

    def _save_metadata(self, asset: VideoAsset):
        meta_path = self.metadata_dir / f"{asset.asset_id}.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(asset.to_dict(), f, indent=2, ensure_ascii=False)

    def get_asset(self, asset_id: str) -> Optional[VideoAsset]:
        meta_path = self.metadata_dir / f"{asset_id}.json"
        if not meta_path.exists():
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return VideoAsset(**data)

    def list_assets(self, platform: str = None, blueprint_id: str = None) -> List[VideoAsset]:
        assets = []
        for meta_file in self.metadata_dir.glob("*.json"):
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            asset = VideoAsset(**data)
            if platform and asset.platform != platform:
                continue
            if blueprint_id and asset.blueprint_id != blueprint_id:
                continue
            assets.append(asset)
        return assets

    def get_stats(self) -> Dict[str, Any]:
        assets = self.list_assets()
        platform_stats = {}
        for asset in assets:
            if asset.platform not in platform_stats:
                platform_stats[asset.platform] = {"count": 0, "total_duration": 0}
            platform_stats[asset.platform]["count"] += 1
            platform_stats[asset.platform]["total_duration"] += asset.duration

        return {
            "total_assets": len(assets),
            "total_duration": round(sum(a.duration for a in assets), 1),
            "avg_quality": round(sum(a.quality_score for a in assets) / len(assets), 1) if assets else 0,
            "platform_breakdown": platform_stats,
        }
