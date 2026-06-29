"""Facebook Ads 自动发布器：上传素材 → 创建广告创意 → 发布广告 → 记录"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


@dataclass
class PublishResult:
    """单次发布的完整结果"""
    run_id: str
    ad_account_id: str
    uploaded_count: int
    creative_count: int
    ad_count: int
    image_hashes: list[str] = field(default_factory=list)
    creative_ids: list[str] = field(default_factory=list)
    ad_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    published_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ad_account_id": self.ad_account_id,
            "uploaded_count": self.uploaded_count,
            "creative_count": self.creative_count,
            "ad_count": self.ad_count,
            "image_hashes": self.image_hashes,
            "creative_ids": self.creative_ids,
            "ad_ids": self.ad_ids,
            "errors": self.errors,
            "published_at": self.published_at,
        }

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.ad_count > 0


class FacebookPublisher:
    """Facebook Ads 素材发布器

    完整链路：上传图片 → 创建广告创意 → 创建广告
    """

    def __init__(
        self,
        access_token: str,
        ad_account_id: str,
        api_version: str = "v22.0",
        page_id: str = "",
    ) -> None:
        self._access_token = access_token.strip()
        self._ad_account_id = ad_account_id.removeprefix("act_").strip()
        self._api_version = api_version.strip()
        self._page_id = page_id.strip()
        self._base_url = f"https://graph.facebook.com/{self._api_version}"

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def upload_images(self, image_paths: list[str]) -> list[str]:
        """批量上传图片到 Facebook，返回 image_hash 列表。

        Facebook Ads API: POST /act_{ad_account_id}/adimages
        参数：bytes 或 url；返回 images[].hash

        每个图片单独上传，因为 Facebook 不提供真正的批量上传端点。
        """
        hashes: list[str] = []
        url = f"{self._base_url}/act_{self._ad_account_id}/adimages"

        for idx, img_path in enumerate(image_paths):
            path = Path(img_path)
            if not path.exists():
                self._log_error(f"Image not found: {img_path}")
                continue

            try:
                with open(path, "rb") as f:
                    files = {"filename": (path.name, f, "image/png")}
                    params = {"access_token": self._access_token}
                    response = requests.post(url, params=params, files=files, timeout=120)
                    response.raise_for_status()
                    data = response.json()

                    if "error" in data:
                        raise RuntimeError(f"Facebook API error: {data['error']}")

                    images = data.get("images", {})
                    # Facebook returns dict of {filename: {"hash": "..."}}
                    for _filename, info in images.items():
                        h = info.get("hash", "")
                        if h:
                            hashes.append(h)
            except Exception as e:
                self._log_error(f"Upload failed [{idx}] {path.name}: {e}")

        return hashes

    def create_ad_creatives(
        self,
        image_hashes: list[str],
        headlines: list[str],
        primary_texts: list[str],
        call_to_action: str = "INSTALL_MOBILE_APP",
        app_link: str = "",
    ) -> list[str]:
        """创建广告创意，返回 creative_id 列表。

        Facebook Ads API: POST /act_{ad_account_id}/adcreatives

        为每个 image_hash 创建独立的广告创意。
        如果 headline/primary_text 不够，循环使用。
        """
        creative_ids: list[str] = []
        url = f"{self._base_url}/act_{self._ad_account_id}/adcreatives"

        n = len(image_hashes)
        if n == 0:
            return []

        # extend headlines and primary_texts if shorter than images
        while len(headlines) < n:
            headlines.append(headlines[0] if headlines else "Play Now!")
        while len(primary_texts) < n:
            primary_texts.append(primary_texts[0] if primary_texts else "")

        for i, image_hash in enumerate(image_hashes):
            try:
                object_story_spec = {
                    "page_id": self._page_id,
                    "link_data": {
                        "image_hash": image_hash,
                        "link": app_link or "https://apps.apple.com/app/id000000000",
                        "message": primary_texts[i],
                        "name": headlines[i],
                        "call_to_action": {
                            "type": call_to_action,
                        },
                    },
                }

                params = {
                    "access_token": self._access_token,
                    "object_story_spec": json.dumps(object_story_spec),
                }
                response = requests.post(url, data=params, timeout=60)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    raise RuntimeError(f"Facebook API error: {data['error']}")

                creative_id = data.get("id", "")
                if creative_id:
                    creative_ids.append(creative_id)

            except Exception as e:
                self._log_error(f"Create creative failed [{i}]: {e}")

        return creative_ids

    def create_ads(
        self,
        creative_ids: list[str],
        adset_id: str,
        names: list[str],
        status: str = "PAUSED",
    ) -> list[str]:
        """创建广告，返回 ad_id 列表。

        Facebook Ads API: POST /act_{ad_account_id}/ads

        每个 creative_id 创建一个广告，挂在同一个 adset 下。
        默认 PAUSED 状态，需要手动或通过 publish 步骤启用。
        """
        ad_ids: list[str] = []
        url = f"{self._base_url}/act_{self._ad_account_id}/ads"

        n = len(creative_ids)
        if n == 0:
            return []

        while len(names) < n:
            names.append(f"Ad_{len(names) + 1}")

        for i, creative_id in enumerate(creative_ids):
            try:
                params = {
                    "access_token": self._access_token,
                    "name": names[i],
                    "adset_id": adset_id,
                    "creative": json.dumps({"creative_id": creative_id}),
                    "status": status,
                }
                response = requests.post(url, data=params, timeout=60)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    raise RuntimeError(f"Facebook API error: {data['error']}")

                ad_id = data.get("id", "")
                if ad_id:
                    ad_ids.append(ad_id)

            except Exception as e:
                self._log_error(f"Create ad failed [{i}]: {e}")

        return ad_ids

    def publish_and_monitor(
        self,
        image_dir: str,
        campaign_config: dict[str, Any] | None = None,
    ) -> PublishResult:
        """端到端发布：扫描图片 → 上传 → 创建创意 → 创建广告。

        Args:
            image_dir: 生成图片的目录路径（递归扫描 .png）
            campaign_config: 可选广告系列配置
                {
                    "adset_id": "123456",          # 必填：广告组 ID
                    "headlines": ["Headline 1", ...],
                    "primary_texts": ["Text 1", ...],
                    "ad_names": ["Ad 1", ...],
                    "call_to_action": "INSTALL_MOBILE_APP",
                    "app_link": "https://...",
                    "page_id": "123456",
                    "auto_activate": false,
                }

        Returns:
            PublishResult 包含所有创建的实体 ID
        """
        cfg = campaign_config or {}
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        adset_id = cfg.get("adset_id", "")
        if not adset_id:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=0,
                creative_count=0,
                ad_count=0,
                errors=["Missing required 'adset_id' in campaign_config"],
                published_at=datetime.now().isoformat(),
            )

        # override page_id from config if provided
        if cfg.get("page_id"):
            self._page_id = cfg["page_id"]

        headlines = cfg.get("headlines", ["Play Now!"])
        primary_texts = cfg.get("primary_texts", [""])
        ad_names = cfg.get("ad_names", [f"AI_Creative_{run_id}_{i}" for i in range(20)])
        call_to_action = cfg.get("call_to_action", "INSTALL_MOBILE_APP")
        app_link = cfg.get("app_link", "")
        auto_activate = cfg.get("auto_activate", False)

        # Step 1: scan images
        image_paths = self._scan_images(image_dir)
        if not image_paths:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=0,
                creative_count=0,
                ad_count=0,
                errors=[f"No PNG images found in {image_dir}"],
                published_at=datetime.now().isoformat(),
            )

        # Step 2: upload images
        image_hashes = self.upload_images(image_paths)
        if not image_hashes:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=0,
                creative_count=0,
                ad_count=0,
                errors=["All image uploads failed"],
                published_at=datetime.now().isoformat(),
            )

        # Step 3: create ad creatives
        creative_ids = self.create_ad_creatives(
            image_hashes=image_hashes,
            headlines=headlines,
            primary_texts=primary_texts,
            call_to_action=call_to_action,
            app_link=app_link,
        )

        # Step 4: create ads
        ad_ids = self.create_ads(
            creative_ids=creative_ids,
            adset_id=adset_id,
            names=ad_names,
            status="ACTIVE" if auto_activate else "PAUSED",
        )

        result = PublishResult(
            run_id=run_id,
            ad_account_id=self._ad_account_id,
            uploaded_count=len(image_hashes),
            creative_count=len(creative_ids),
            ad_count=len(ad_ids),
            image_hashes=image_hashes,
            creative_ids=creative_ids,
            ad_ids=ad_ids,
            published_at=datetime.now().isoformat(),
        )

        self._save_result(result)
        return result

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _scan_images(image_dir: str) -> list[str]:
        """递归扫描目录中的 PNG 图片"""
        path = Path(image_dir)
        if not path.exists():
            return []
        return sorted(str(p) for p in path.rglob("*.png"))

    @staticmethod
    def _log_error(msg: str) -> None:
        print(f"  [FacebookPublisher ERROR] {msg}")

    def _save_result(self, result: PublishResult) -> Path:
        """保存发布结果到 output 目录"""
        output_dir = Path("output/creative_growth_loop/publish_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"publish_{result.run_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        return path
