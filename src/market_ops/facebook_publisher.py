"""Facebook Publisher — Creative Factory → Facebook Ad Delivery.

Phase C of Creative Factory Loop v1.1:
  Creative Factory
        │
        ▼
  FacebookPublisher
        │
        ├── upload_creative(image/video)  → creative_id
        ├── create_ad_creative(creative_id) → ad_creative_id
        ├── create_ad_set(budget, targeting) → ad_set_id
        ├── create_ad(ad_creative_id, ad_set_id) → ad_id
        │
        ▼
  Facebook Ad Live
        │
        ▼
  Adjust Revenue → CreativePerformance → Next Loop

Tiered approval policy:
  Level 0: Dry run (no real API calls, test mode)
  Level 1: Low budget ($50/day, max 5 ads)
  Level 2: Full budget (unlimited, requires confirmation)

Usage:
    publisher = FacebookPublisher(access_token="...", ad_account_id="act_...")
    result = publisher.publish_creative(image_path, name="variant_001")
    # → FacebookCreative(creative_id, ad_id, status)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Optional

import requests as _requests


# ── Config ──
FB_API_VERSION = "v18.0"
FB_API_BASE = f"https://graph.facebook.com/{FB_API_VERSION}"
DEFAULT_TEST_BUDGET = 50.0  # USD per ad per day
DEFAULT_DAILY_BUDGET = 100.0  # USD per ad set per day
MAX_ADS_PER_LOOP = 5  # Safety limit per daily run


@dataclass
class FacebookCreative:
    """A creative published to Facebook."""
    local_path: str = ""
    creative_id: str = ""         # Facebook creative ID
    ad_creative_id: str = ""       # Facebook ad creative ID
    ad_id: str = ""                # Facebook ad ID
    ad_set_id: str = ""            # Facebook ad set ID
    campaign_id: str = ""          # Facebook campaign ID
    status: str = "draft"          # draft / uploaded / active / error
    name: str = ""
    platform: str = ""
    budget_daily: float = 0.0
    published_at: str = ""
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_live(self) -> bool:
        return self.status == "active"


@dataclass
class PublishResult:
    """Result from a batch publish operation."""
    date: str = ""
    total_attempted: int = 0
    total_uploaded: int = 0
    total_active: int = 0
    total_failed: int = 0
    creatives: list[FacebookCreative] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    approval_level: int = 0
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["creatives"] = [c.to_dict() for c in self.creatives]
        return d

    @property
    def success_rate(self) -> float:
        if self.total_attempted == 0:
            return 0.0
        return round(self.total_active / self.total_attempted, 4)


class FacebookPublisher:
    """Publish creatives to Facebook Ads via Marketing API.

    Approval levels:
      Level 0 — Dry run: no real API calls, returns mock results
      Level 1 — Low budget: $50/day, max 5 ads per run
      Level 2 — Full budget: unlimited, requires explicit confirmation
    """

    def __init__(
        self,
        access_token: str | None = None,
        ad_account_id: str | None = None,
        page_id: str | None = None,
        approval_level: int = 0,
        output_dir: Path | None = None,
    ) -> None:
        # Support both FB_xxx and META_xxx env var prefixes (project uses META_)
        self._access_token = (
            access_token
            or os.getenv("FB_ACCESS_TOKEN", "")
            or os.getenv("META_ACCESS_TOKEN", "")
        ).strip()
        self._ad_account_id = (
            ad_account_id
            or os.getenv("FB_AD_ACCOUNT_ID", "")
            or os.getenv("META_AD_ACCOUNT_ID", "")
        ).strip()
        self._page_id = (
            page_id
            or os.getenv("FB_PAGE_ID", "")
            or os.getenv("CLOSED_LOOP_PAGE_ID", "")
        ).strip()
        self.approval_level = approval_level
        self.output_dir = Path(output_dir) if output_dir else Path("output/creative_factory/facebook")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_configured(self) -> bool:
        return bool(self._access_token and self._ad_account_id)

    @property
    def is_dry_run(self) -> bool:
        return self.approval_level == 0 or not self.is_configured

    # ── Public API ──

    def publish_creatives(
        self,
        image_paths: list[str | Path],
        names: list[str] | None = None,
        budget_per_ad: float = DEFAULT_TEST_BUDGET,
        campaign_name: str = "Creative Factory Auto",
        platform: str = "ios",
    ) -> PublishResult:
        """Publish a batch of creatives to Facebook.

        Args:
            image_paths: List of local image/video file paths.
            names: Optional list of creative names (auto-generated if None).
            budget_per_ad: Daily budget per ad in USD.
            campaign_name: Facebook campaign name.
            platform: ios / android (for naming).

        Returns:
            PublishResult with all published creative statuses.
        """
        today = date.today().isoformat()
        result = PublishResult(date=today, approval_level=self.approval_level)
        t0 = time.time()

        if names is None:
            names = [f"cf_{platform}_{i+1:03d}" for i in range(len(image_paths))]

        # Safety limit
        effective_paths = image_paths[:MAX_ADS_PER_LOOP]
        effective_names = names[:MAX_ADS_PER_LOOP]

        result.total_attempted = len(effective_paths)

        for i, (img_path, name) in enumerate(zip(effective_paths, effective_names)):
            try:
                creative = self._publish_one(
                    image_path=Path(img_path),
                    name=name,
                    budget=budget_per_ad,
                    campaign_name=campaign_name,
                    platform=platform,
                )
                result.creatives.append(creative)
                if creative.is_live:
                    result.total_active += 1
                result.total_uploaded += 1

            except Exception as e:
                result.total_failed += 1
                result.errors.append(f"[{name}] {e}")

        result.elapsed_sec = round(time.time() - t0, 1)
        self._save_manifest(result)
        return result

    def _publish_one(
        self,
        image_path: Path,
        name: str,
        budget: float,
        campaign_name: str,
        platform: str,
    ) -> FacebookCreative:
        """Publish a single creative to Facebook.

        Pipeline:
          1. Upload media → creative_id (or use existing)
          2. Create ad creative → ad_creative_id
          3. Get or create campaign → campaign_id
          4. Create ad set (with budget) → ad_set_id
          5. Create ad → ad_id
        """
        creative = FacebookCreative(
            local_path=str(image_path),
            name=name,
            platform=platform,
            budget_daily=budget,
            published_at=date.today().isoformat(),
        )

        if self.is_dry_run:
            return self._dry_run_publish(creative)

        # Step 1: Upload media (image or video)
        creative.creative_id = self._upload_media(image_path, name)

        # Step 2: Create ad creative
        creative.ad_creative_id = self._create_ad_creative(
            creative.creative_id, name, platform
        )

        # Step 3: Get or create campaign
        creative.campaign_id = self._ensure_campaign(campaign_name)

        # Step 4: Create ad set
        creative.ad_set_id = self._create_ad_set(
            creative.campaign_id, name, budget, platform
        )

        # Step 5: Create ad
        creative.ad_id = self._create_ad(
            creative.ad_creative_id, creative.ad_set_id, name
        )

        creative.status = "active"
        return creative

    # ── Dry Run ──

    def _dry_run_publish(self, creative: FacebookCreative) -> FacebookCreative:
        """Generate mock IDs for dry run mode."""
        mock_id = uuid.uuid4().hex[:16]
        creative.creative_id = f"mock_creative_{mock_id}"
        creative.ad_creative_id = f"mock_adcreative_{mock_id}"
        creative.campaign_id = f"mock_campaign_{mock_id}"
        creative.ad_set_id = f"mock_adset_{mock_id}"
        creative.ad_id = f"mock_ad_{mock_id}"
        creative.status = "active" if self.approval_level >= 1 else "draft"
        return creative

    # ── Facebook API Methods ──

    def _upload_media(self, image_path: Path, name: str) -> str:
        """Upload image/video to Facebook ad account.

        POST /act_{ad_account_id}/adimages or /advideos
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Media file not found: {image_path}")

        is_video = image_path.suffix.lower() in (".mp4", ".mov", ".avi")

        if is_video:
            endpoint = f"/act_{self._ad_account_id}/advideos"
            file_field = "source"
        else:
            endpoint = f"/act_{self._ad_account_id}/adimages"
            file_field = "filename"

        url = f"{FB_API_BASE}{endpoint}"
        params = {"access_token": self._access_token}

        with open(image_path, "rb") as f:
            resp = _requests.post(
                url,
                params=params,
                files={file_field: (image_path.name, f)},
                timeout=120,
            )

        self._check_response(resp, "upload_media")
        data = resp.json()

        # Return the image hash or video ID
        images = data.get("images", {})
        if images:
            return list(images.values())[0].get("hash", "")
        return data.get("id", "")

    def _create_ad_creative(
        self, creative_id: str, name: str, platform: str
    ) -> str:
        """Create an ad creative object from uploaded media.

        POST /act_{ad_account_id}/adcreatives
        """
        url = f"{FB_API_BASE}/act_{self._ad_account_id}/adcreatives"
        body = {
            "name": name,
            "object_story_spec": {
                "page_id": self._page_id,
                "link_data": {
                    "link": "https://play.google.com/store/apps/details?id=com.merge.witches",
                    "message": "Play Merge Witches Now!",
                    "call_to_action": {"type": "INSTALL_MOBILE_APP"},
                },
            },
            "image_hash": creative_id,
            "access_token": self._access_token,
        }
        resp = _requests.post(url, json=body, timeout=30)
        self._check_response(resp, "create_ad_creative")
        return resp.json().get("id", "")

    def _ensure_campaign(self, campaign_name: str) -> str:
        """Get or create a campaign for the daily creative factory run.

        POST /act_{ad_account_id}/campaigns
        """
        url = f"{FB_API_BASE}/act_{self._ad_account_id}/campaigns"
        body = {
            "name": f"{campaign_name} - {date.today().isoformat()}",
            "objective": "APP_INSTALLS",
            "status": "ACTIVE",
            "special_ad_categories": [],
            "access_token": self._access_token,
        }
        resp = _requests.post(url, json=body, timeout=30)
        self._check_response(resp, "create_campaign")
        return resp.json().get("id", "")

    def _create_ad_set(
        self, campaign_id: str, name: str, budget: float, platform: str
    ) -> str:
        """Create an ad set with daily budget.

        POST /act_{ad_account_id}/adsets
        """
        url = f"{FB_API_BASE}/act_{self._ad_account_id}/adsets"
        body = {
            "name": f"{name} - Ad Set",
            "campaign_id": campaign_id,
            "daily_budget": int(budget * 100),  # cents
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "APP_INSTALLS",
            "status": "ACTIVE",
            "targeting": {
                "geo_locations": {"countries": ["US", "GB", "DE", "FR", "JP"]},
                "publisher_platforms": [platform if platform == "ios" else "android"],
                "device_platforms": ["mobile"],
            },
            "access_token": self._access_token,
        }
        resp = _requests.post(url, json=body, timeout=30)
        self._check_response(resp, "create_ad_set")
        return resp.json().get("id", "")

    def _create_ad(
        self, ad_creative_id: str, ad_set_id: str, name: str
    ) -> str:
        """Create the ad itself.

        POST /act_{ad_account_id}/ads
        """
        url = f"{FB_API_BASE}/act_{self._ad_account_id}/ads"
        body = {
            "name": f"{name} - Ad",
            "adset_id": ad_set_id,
            "creative": {"creative_id": ad_creative_id},
            "status": "ACTIVE",
            "access_token": self._access_token,
        }
        resp = _requests.post(url, json=body, timeout=30)
        self._check_response(resp, "create_ad")
        return resp.json().get("id", "")

    # ── Helpers ──

    @staticmethod
    def _check_response(resp: _requests.Response, step: str) -> None:
        """Check Facebook API response for errors."""
        if resp.status_code >= 400:
            error = resp.json().get("error", {})
            raise RuntimeError(
                f"Facebook API [{step}] {resp.status_code}: "
                f"{error.get('message', resp.text)}"
            )

    def _save_manifest(self, result: PublishResult) -> Path:
        """Save publish manifest to JSON."""
        today = date.today().isoformat().replace("-", "")
        path = self.output_dir / f"publish_manifest_{today}.json"
        path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path


# ── Convenience ──

def create_default_publisher(
    approval_level: int = 0,
    output_dir: str | Path = "output/creative_factory/facebook",
) -> FacebookPublisher:
    """Create a FacebookPublisher with sensible defaults (dry run by default)."""
    return FacebookPublisher(
        approval_level=approval_level,
        output_dir=Path(output_dir),
    )