"""V4.0 Creative Intelligence Platform — Creative Repository.

Unified storage for all creative assets:
  creative_repository/
    creative_000001/
      metadata.json
      facebook.json
      adjust.json
      dna.json
      image.png / video.mp4
      review.json
      report.html

Single source of truth for the entire creative intelligence pipeline.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .metadata import CreativeMetadata, CreativeType, CreativeStatus, MonetizationType, OptimizationGoal


class CreativeRepository:
    """Unified creative asset storage with metadata management.

    Usage:
        repo = CreativeRepository("output/creative_repository")
        creative = repo.register(
            creative_type="image",
            facebook_data={...},
            adjust_data={...},
        )
        repo.save_dna(creative.creative_id, dna_data)
        repo.save_image(creative.creative_id, image_path)
        repo.save_review(creative.creative_id, review_scores)
    """

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self._root = Path(root_dir or "output/creative_repository")
        self._root.mkdir(parents=True, exist_ok=True)

    # ── Registration ──

    def register(
        self,
        creative_type: str = "image",
        facebook_data: dict[str, Any] | None = None,
        adjust_data: dict[str, Any] | None = None,
        eagle_path: str = "",
        country: str = "",
        monetization: str = "iaa",
        optimization_goal: str = "install",
    ) -> CreativeMetadata:
        """Register a new creative in the repository.

        Creates a new creative directory with metadata.
        """
        creative_id = f"creative_{self._next_index():06d}"
        creative_dir = self._root / creative_id
        creative_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat()

        metadata = CreativeMetadata(
            creative_id=creative_id,
            creative_type=CreativeType(creative_type),
            monetization=MonetizationType(monetization),
            optimization_goal=OptimizationGoal(optimization_goal),
            source_eagle_path=eagle_path,
            country=country,
            status=CreativeStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            first_seen=now,
            last_seen=now,
        )

        # Save Facebook data
        if facebook_data:
            self._save_json(creative_dir / "facebook.json", facebook_data)
            metadata.source_facebook_id = facebook_data.get("creative_id", "")
            # Populate performance from Facebook
            metadata.spend = facebook_data.get("spend", 0)
            metadata.impressions = facebook_data.get("impressions", 0)
            metadata.clicks = facebook_data.get("clicks", 0)
            metadata.ctr = facebook_data.get("ctr", 0)
            metadata.cpm = facebook_data.get("cpm", 0)
            metadata.installs = facebook_data.get("installs", 0)
            metadata.roas_d7 = facebook_data.get("roas_d7", 0)

        # Save Adjust data
        if adjust_data:
            self._save_json(creative_dir / "adjust.json", adjust_data)
            metadata.source_adjust_id = adjust_data.get("creative_id", "")
            metadata.purchases = adjust_data.get("purchases", 0)
            metadata.purchase_value = adjust_data.get("purchase_value", 0)
            metadata.ltv_d30 = adjust_data.get("ltv_d30", 0)
            metadata.retention_d1 = adjust_data.get("retention_d1", 0)
            metadata.retention_d7 = adjust_data.get("retention_d7", 0)

        self._save_json(creative_dir / "metadata.json", metadata.to_dict())
        return metadata

    def update_metadata(self, creative_id: str, **kwargs) -> CreativeMetadata | None:
        """Update metadata fields for an existing creative."""
        meta = self.get_metadata(creative_id)
        if not meta:
            return None

        for key, value in kwargs.items():
            if hasattr(meta, key):
                setattr(meta, key, value)

        meta.updated_at = datetime.now().isoformat()
        creative_dir = self._root / creative_id
        self._save_json(creative_dir / "metadata.json", meta.to_dict())
        return meta

    # ── DNA ──

    def save_dna(self, creative_id: str, dna_data: dict[str, Any]) -> bool:
        """Save DNA data for a creative."""
        creative_dir = self._root / creative_id
        if not creative_dir.exists():
            return False

        self._save_json(creative_dir / "dna.json", dna_data)

        # Update metadata flags
        meta = self.get_metadata(creative_id)
        if meta:
            if dna_data.get("dna_type") == "image" or "character" in dna_data:
                meta.has_image_dna = True
            if dna_data.get("dna_type") == "video" or "opening_hook" in dna_data:
                meta.has_video_dna = True
            meta.updated_at = datetime.now().isoformat()
            self._save_json(creative_dir / "metadata.json", meta.to_dict())
        return True

    def get_dna(self, creative_id: str) -> dict[str, Any] | None:
        """Get DNA data for a creative."""
        return self._load_json(self._root / creative_id / "dna.json")

    # ── Assets ──

    def save_image(self, creative_id: str, image_path: str | Path) -> str:
        """Copy an image into the creative directory."""
        creative_dir = self._root / creative_id
        creative_dir.mkdir(parents=True, exist_ok=True)
        dest = creative_dir / "image.png"
        shutil.copy2(str(image_path), str(dest))
        return str(dest)

    def save_video(self, creative_id: str, video_path: str | Path) -> str:
        """Copy a video into the creative directory."""
        creative_dir = self._root / creative_id
        creative_dir.mkdir(parents=True, exist_ok=True)
        dest = creative_dir / "video.mp4"
        shutil.copy2(str(video_path), str(dest))
        return str(dest)

    def get_image_path(self, creative_id: str) -> str:
        """Get path to image asset."""
        return str(self._root / creative_id / "image.png")

    def get_video_path(self, creative_id: str) -> str:
        """Get path to video asset."""
        return str(self._root / creative_id / "video.mp4")

    # ── Review ──

    def save_review(self, creative_id: str, review_scores: dict[str, Any]) -> bool:
        """Save human review scores."""
        creative_dir = self._root / creative_id
        if not creative_dir.exists():
            return False

        numeric_scores = [v for v in review_scores.values() if isinstance(v, (int, float))]
        review_data = {
            "creative_id": creative_id,
            "scores": review_scores,
            "average": sum(numeric_scores) / max(len(numeric_scores), 1),
            "reviewed_at": datetime.now().isoformat(),
        }
        self._save_json(creative_dir / "review.json", review_data)

        # Update metadata
        meta = self.get_metadata(creative_id)
        if meta:
            meta.review_score = review_data["average"]
            meta.review_count = (meta.review_count or 0) + 1
            meta.updated_at = datetime.now().isoformat()
            self._save_json(creative_dir / "metadata.json", meta.to_dict())
        return True

    def get_review(self, creative_id: str) -> dict[str, Any] | None:
        """Get review data."""
        return self._load_json(self._root / creative_id / "review.json")

    # ── Query ──

    def get_metadata(self, creative_id: str) -> CreativeMetadata | None:
        """Get metadata for a creative."""
        data = self._load_json(self._root / creative_id / "metadata.json")
        if data:
            return CreativeMetadata.from_dict(data)
        return None

    def list_all(self) -> list[CreativeMetadata]:
        """List all creatives in the repository."""
        result = []
        for d in sorted(self._root.iterdir()):
            if d.is_dir():
                meta = self.get_metadata(d.name)
                if meta:
                    result.append(meta)
        return result

    def list_winners(self, min_roas: float = 0.5) -> list[CreativeMetadata]:
        """List winning creatives (ROAS >= threshold)."""
        return [m for m in self.list_all() if m.roas_d7 >= min_roas]

    def list_by_type(self, creative_type: str) -> list[CreativeMetadata]:
        ct = CreativeType(creative_type)
        return [m for m in self.list_all() if m.creative_type == ct]

    def list_by_status(self, status: str) -> list[CreativeMetadata]:
        st = CreativeStatus(status)
        return [m for m in self.list_all() if m.status == st]

    # ── Helpers ──

    def _next_index(self) -> int:
        existing = [d.name for d in self._root.iterdir() if d.is_dir()]
        indices = []
        for name in existing:
            try:
                indices.append(int(name.split("_")[1]))
            except (ValueError, IndexError):
                pass
        return max(indices) + 1 if indices else 1

    def _save_json(self, path: Path, data: dict[str, Any]) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None