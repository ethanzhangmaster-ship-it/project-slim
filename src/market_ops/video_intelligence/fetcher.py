"""Phase 1: Pull all videos & ad metrics from Facebook API.

Workflow:
  1. Query all video creatives with campaign/adset/ad hierarchy
  2. Download each video to videos/ directory
  3. Fetch ad performance metrics per video
  4. Output video_metrics.json
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Any

import requests as _requests

from market_ops.config import Settings
from market_ops.video_intelligence.models import VideoRecord, VideoMetrics


class VideoFetcher:
    """Pull all videos + metrics from Facebook Ads API."""

    def __init__(
        self,
        access_token: str | None = None,
        ad_account_id: str | None = None,
        api_version: str = "v22.0",
        output_dir: str | Path | None = None,
        lookback_days: int = 365,
        download_videos: bool = True,
    ) -> None:
        settings = Settings.from_env()
        self._token = (access_token or settings.meta_access_token or os.getenv("META_ACCESS_TOKEN", "")).strip()
        self._account_id = (ad_account_id or settings.meta_ad_account_id or os.getenv("META_AD_ACCOUNT_ID", "")).strip().removeprefix("act_")
        self._api_version = api_version.strip()
        self._base_url = f"https://graph.facebook.com/{self._api_version}"

        root = Path(output_dir or Path(__file__).resolve().parents[3] / "output" / "video_intelligence")
        self._output_dir = Path(root)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._videos_dir = self._output_dir / "videos"
        self._videos_dir.mkdir(parents=True, exist_ok=True)

        self._lookback_days = lookback_days
        self._download_videos = download_videos
        self._video_records: list[VideoRecord] = []
        self._video_metrics: list[VideoMetrics] = []

    def run(self) -> dict[str, Any]:
        print("[Phase 1] VideoFetcher: Starting...")

        self._video_records = self._pull_all_video_creatives()
        print(f"[Phase 1] Found {len(self._video_records)} video creatives")

        if self._download_videos:
            self._download_all_videos()

        self._video_metrics = self._pull_ad_metrics()

        self._save_results()
        print(f"[Phase 1] Done. {len(self._video_records)} videos, {len(self._video_metrics)} with metrics")

        return {
            "video_count": len(self._video_records),
            "metrics_count": len(self._video_metrics),
            "output_dir": str(self._output_dir),
        }

    def _pull_all_video_creatives(self) -> list[VideoRecord]:
        ads = self._fetch_all_ads()
        creatives_cache: dict[str, dict] = {}
        records: list[VideoRecord] = []

        for ad in ads:
            ad_id = str(ad.get("id", ""))
            campaign = ad.get("campaign") or {}
            adset = ad.get("adset") or {}
            creative = ad.get("creative") or {}
            creative_id = str(creative.get("id", ""))

            if creative_id in creatives_cache:
                rec = creatives_cache[creative_id]
            else:
                if not self._is_video_creative(creative):
                    creative_detail = self._fetch_creative_detail(creative_id)
                    if not self._is_video_creative(creative_detail):
                        continue
                    creative = creative_detail

                rec = {
                    "creative_id": creative_id,
                    "video_url": self._extract_video_url(creative),
                    "thumbnail_url": str(creative.get("thumbnail_url", "")),
                    "creative_name": str(creative.get("name", "")),
                    "creative_type": "video",
                    "campaign_id": str(campaign.get("id", "")),
                    "adset_id": str(adset.get("id", "")),
                    "ad_id": ad_id,
                }
                creatives_cache[creative_id] = rec

            video_url = rec["video_url"]
            if not video_url:
                continue

            video_id = f"video_{creative_id}"
            records.append(VideoRecord(
                video_id=video_id,
                creative_id=creative_id,
                ad_id=ad_id,
                adset_id=rec["adset_id"],
                campaign_id=rec["campaign_id"],
                video_url=video_url,
                thumbnail_url=rec["thumbnail_url"],
                creative_name=rec["creative_name"],
            ))

        return records

    def _fetch_all_ads(self) -> list[dict]:
        params = {
            "access_token": self._token,
            "fields": "id,name,campaign{id,name},adset{id,name},creative{id,name,thumbnail_url,object_story_spec,asset_feed_spec}",
            "limit": 500,
        }
        return self._get_paginated(f"/act_{self._account_id}/ads", params)

    def _fetch_creative_detail(self, creative_id: str) -> dict:
        params = {
            "access_token": self._token,
            "fields": "id,name,thumbnail_url,image_url,object_story_spec,video_id,asset_feed_spec",
        }
        url = f"{self._base_url}/{creative_id}"
        try:
            resp = _requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return {}

    @staticmethod
    def _is_video_creative(creative: dict) -> bool:
        if not creative:
            return False
        if creative.get("video_id"):
            return True
        story_spec = creative.get("object_story_spec") or {}
        if story_spec.get("video_data"):
            return True
        asset_spec = creative.get("asset_feed_spec") or {}
        for asset in asset_spec.get("bodies", []):
            if asset.get("video_id"):
                return True
        return False

    @staticmethod
    def _extract_video_url(creative: dict) -> str:
        story_spec = creative.get("object_story_spec") or {}
        video_data = story_spec.get("video_data") or {}
        if video_data.get("video_id"):
            vid = video_data["video_id"]
            return f"https://graph.facebook.com/v22.0/{vid}?fields=source"

        asset_spec = creative.get("asset_feed_spec") or {}
        for body in asset_spec.get("bodies", []):
            if body.get("video_id"):
                vid = body["video_id"]
                return f"https://graph.facebook.com/v22.0/{vid}?fields=source"

        return ""

    def _download_all_videos(self) -> None:
        downloaded = 0
        for rec in self._video_records:
            local_path = self._videos_dir / f"{rec.video_id}.mp4"
            if local_path.exists():
                rec.local_path = str(local_path)
                downloaded += 1
                continue

            source_url = self._resolve_video_source(rec.video_url)
            if not source_url:
                continue

            try:
                print(f"  Downloading {rec.video_id}...")
                resp = _requests.get(source_url, stream=True, timeout=300)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
                rec.local_path = str(local_path)
                downloaded += 1
            except Exception as exc:
                print(f"  Failed to download {rec.video_id}: {exc}")

        print(f"[Phase 1] Downloaded {downloaded}/{len(self._video_records)} videos")

    def _resolve_video_source(self, url: str) -> str:
        if "fields=source" in url:
            try:
                resp = _requests.get(f"{url}&access_token={self._token}", timeout=30)
                resp.raise_for_status()
                data = resp.json()
                src = data.get("source", "")
                if src:
                    return src
            except Exception:
                pass
        if url.startswith("https://"):
            return url
        return ""

    def _pull_ad_metrics(self) -> list[VideoMetrics]:
        creative_metrics: dict[str, dict[str, float]] = {}
        for rec in self._video_records:
            creative_metrics[rec.creative_id] = {
                "spend": 0.0, "impression": 0.0, "click": 0.0,
                "install": 0.0, "purchase": 0.0, "revenue": 0.0,
            }

        end = date.today()
        start = end - timedelta(days=self._lookback_days)

        params = {
            "access_token": self._token,
            "level": "ad",
            "time_range": json.dumps({"since": start.isoformat(), "until": end.isoformat()}),
            "fields": "ad_id,spend,impressions,clicks,ctr,cpc,cpm,actions,action_values",
            "limit": 500,
            "date_preset": "lifetime",
        }

        try:
            insights = self._get_paginated(f"/act_{self._account_id}/insights", params)
        except Exception as exc:
            print(f"[Phase 1] Insights fetch error: {exc}")
            insights = []

        print(f"[Phase 1] Fetched {len(insights)} insight rows")

        ad_id_to_creative: dict[str, str] = {}
        for rec in self._video_records:
            ad_id_to_creative[rec.ad_id] = rec.creative_id

        video_id_map: dict[str, str] = {}
        for rec in self._video_records:
            video_id_map[rec.creative_id] = rec.video_id

        for row in insights:
            ad_id = str(row.get("ad_id", ""))
            creative_id = ad_id_to_creative.get(ad_id)
            if not creative_id or creative_id not in creative_metrics:
                continue

            cm = creative_metrics[creative_id]
            cm["spend"] += self._to_float(row.get("spend"))
            cm["impression"] += self._to_float(row.get("impressions"))
            cm["click"] += self._to_float(row.get("clicks"))
            cm["install"] += self._extract_action_value(row.get("actions"), "install")
            cm["purchase"] += self._extract_action_value(row.get("actions"), "purchase")
            cm["revenue"] += self._extract_action_value(row.get("action_values"), "purchase")

        metrics: list[VideoMetrics] = []
        for creative_id, cm in creative_metrics.items():
            spend = cm["spend"]
            impression = cm["impression"]
            click = cm["click"]
            purchase = cm["purchase"]
            revenue = cm["revenue"]
            install = cm["install"]

            ctr = (click / impression * 100) if impression > 0 else 0.0
            cpc = (spend / click) if click > 0 else 0.0
            cpm = (spend / impression * 1000) if impression > 0 else 0.0
            roas = (revenue / spend) if spend > 0 else 0.0
            ipm = (install / impression * 1000) if impression > 0 else 0.0
            cpa = (spend / purchase) if purchase > 0 else 0.0

            video_id = video_id_map.get(creative_id, f"video_{creative_id}")

            metrics.append(VideoMetrics(
                video_id=video_id,
                creative_id=creative_id,
                spend=spend,
                impression=impression,
                click=click,
                ctr=round(ctr, 4),
                cpc=round(cpc, 4),
                cpm=round(cpm, 4),
                install=install,
                purchase=purchase,
                revenue=revenue,
                roas=round(roas, 4),
                ipm=round(ipm, 4),
                cpa=round(cpa, 4),
            ))

        return metrics

    def _save_results(self) -> None:
        records_data = []
        for rec in self._video_records:
            records_data.append({
                "video_id": rec.video_id,
                "creative_id": rec.creative_id,
                "ad_id": rec.ad_id,
                "adset_id": rec.adset_id,
                "campaign_id": rec.campaign_id,
                "video_url": rec.video_url,
                "local_path": rec.local_path,
                "thumbnail_url": rec.thumbnail_url,
                "creative_name": rec.creative_name,
            })

        records_file = self._output_dir / "video_records.json"
        records_file.write_text(
            json.dumps(records_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        metrics_data = []
        for m in self._video_metrics:
            metrics_data.append({
                "video_id": m.video_id,
                "creative_id": m.creative_id,
                "spend": m.spend,
                "impression": m.impression,
                "click": m.click,
                "ctr": m.ctr,
                "cpc": m.cpc,
                "cpm": m.cpm,
                "install": m.install,
                "purchase": m.purchase,
                "revenue": m.revenue,
                "roas": m.roas,
                "retention": m.retention,
                "ipm": m.ipm,
                "ltv": m.ltv,
                "cpa": m.cpa,
            })

        metrics_file = self._output_dir / "video_metrics.json"
        metrics_file.write_text(
            json.dumps(metrics_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        print(f"[Phase 1] Saved records: {records_file}")
        print(f"[Phase 1] Saved metrics: {metrics_file}")

    def _get_paginated(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self._base_url}{path}"
        results: list[dict[str, Any]] = []
        next_params: dict[str, Any] | None = params
        page = 0
        while url and page < 200:
            try:
                response = _requests.get(url, params=next_params, timeout=120)
                response.raise_for_status()
                payload = response.json()
                if "error" in payload:
                    raise RuntimeError(f"Meta API error: {payload['error']}")
                results.extend(payload.get("data", []))
                paging = payload.get("paging") or {}
                url = paging.get("next", "") or ""
                next_params = None
                page += 1
                if page % 5 == 0:
                    time.sleep(1)
            except Exception as exc:
                print(f"[Phase 1] API error on page {page}: {exc}")
                break
        return results

    @staticmethod
    def _to_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _extract_action_value(actions: Any, key_pattern: str) -> float:
        if not isinstance(actions, list):
            return 0.0
        total = 0.0
        for item in actions:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type", "")).lower()
            if key_pattern in action_type or action_type == f"omni_{key_pattern}":
                total += VideoFetcher._to_float(item.get("value"))
        return total

    @property
    def video_records(self) -> list[VideoRecord]:
        return self._video_records

    @property
    def video_metrics(self) -> list[VideoMetrics]:
        return self._video_metrics

    @property
    def output_dir(self) -> Path:
        return self._output_dir
