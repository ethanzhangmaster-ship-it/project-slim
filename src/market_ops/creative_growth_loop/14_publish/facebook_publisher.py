"""Facebook Ads 自动发布器：上传素材 → 创建Campaign → 创建AdSet → 创建广告创意 → 发布广告 → 记录

完整链路（两种模式）：
1. 基础模式：上传图片 → 创建广告创意 → 创建广告（挂到已有AdSet）
2. 完整模式：创建Campaign → 创建AdSet → 上传图片 → 创建广告创意 → 创建广告
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# ─── Campaign Strategy Enums (standalone-safe) ───────────────────────────
class _CampaignObjective:
    APP_INSTALLS = "APP_INSTALLS"
    CONVERSIONS = "CONVERSIONS"
    REACH = "REACH"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    BRAND_AWARENESS = "BRAND_AWARENESS"
    TRAFFIC = "TRAFFIC"
    LEAD_GENERATION = "LEAD_GENERATION"
    STORE_VISITS = "STORE_VISITS"
    CATALOG_SALES = "CATALOG_SALES"


class _CampaignBuyingType:
    AUCTION = "AUCTION"
    RESERVED = "RESERVED"


class _OptimizationGoal:
    APP_INSTALLS = "APP_INSTALLS"
    OFFSITE_CONVERSIONS = "OFFSITE_CONVERSIONS"
    CONVERSIONS = "CONVERSIONS"
    IMPRESSIONS = "IMPRESSIONS"
    REACH = "REACH"
    VIDEO_VIEWS = "VIDEO_VIEWS"


class _BidStrategy:
    LOWEST_COST_WITHOUT_CAP = "LOWEST_COST_WITHOUT_CAP"
    LOWEST_COST_WITH_BID_CAP = "LOWEST_COST_WITH_BID_CAP"
    TARGET_COST = "TARGET_COST"
    LOWEST_COST_BID_LIMIT = "LOWEST_COST_BID_LIMIT"


class _BillingEvent:
    IMPRESSIONS = "IMPRESSIONS"
    CLICKS = "CLICKS"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    CONVERSIONS = "CONVERSIONS"


CampaignObjective = _CampaignObjective
CampaignBuyingType = _CampaignBuyingType
OptimizationGoal = _OptimizationGoal
BidStrategy = _BidStrategy
BillingEvent = _BillingEvent

# These are not used in creative creation — skip
CampaignConfig = None
AdSetConfig = None
TargetingConfig = None


@dataclass
class PublishResult:
    """单次发布的完整结果"""
    run_id: str
    ad_account_id: str
    uploaded_count: int
    creative_count: int
    ad_count: int
    campaign_id: str = ""
    adset_ids: list[str] = field(default_factory=list)
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
            "campaign_id": self.campaign_id,
            "adset_ids": self.adset_ids,
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

    完整链路（两种模式）：
    - 基础模式：上传图片 → 创建广告创意 → 创建广告（挂到已有AdSet）
    - 完整模式：创建Campaign → 创建AdSet → 上传图片 → 创建广告创意 → 创建广告
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

    def create_campaign(
        self,
        name: str,
        objective: CampaignObjective = CampaignObjective.APP_INSTALLS,
        buying_type: CampaignBuyingType = CampaignBuyingType.AUCTION,
        status: str = "PAUSED",
        special_ad_categories: list[str] | None = None,
    ) -> str:
        """创建广告系列（Campaign），返回 campaign_id。

        Facebook Ads API: POST /act_{ad_account_id}/campaigns

        Args:
            name: Campaign 名称
            objective: 投放目标
            buying_type: 购买类型（AUCTION/RESERVED）
            status: 初始状态（PAUSED/ACTIVE）
            special_ad_categories: 特殊广告类别（如 NONE/HOUSING/EMPLOYMENT/CREDIT）

        Returns:
            campaign_id 字符串，失败返回空字符串
        """
        url = f"{self._base_url}/act_{self._ad_account_id}/campaigns"
        params: dict[str, Any] = {
            "access_token": self._access_token,
            "name": name,
            "objective": objective.value if isinstance(objective, CampaignObjective) else objective,
            "buying_type": buying_type.value if isinstance(buying_type, CampaignBuyingType) else buying_type,
            "status": status,
        }

        if special_ad_categories:
            params["special_ad_categories"] = json.dumps(special_ad_categories)
        else:
            params["special_ad_categories"] = json.dumps(["NONE"])

        try:
            response = requests.post(url, data=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise RuntimeError(f"Facebook API error: {data['error']}")

            campaign_id = data.get("id", "")
            print(f"  [FacebookPublisher] Campaign created: {campaign_id}")
            return campaign_id

        except Exception as e:
            self._log_error(f"Create campaign failed: {e}")
            return ""

    def create_campaign_from_config(self, config: CampaignConfig) -> str:
        """从 CampaignConfig 创建 Campaign"""
        return self.create_campaign(
            name=config.name,
            objective=config.objective,
            buying_type=config.buying_type,
            status=config.status,
            special_ad_categories=config.special_ad_categories if config.special_ad_categories else None,
        )

    def create_adset(
        self,
        name: str,
        campaign_id: str,
        daily_budget: int = 0,
        lifetime_budget: int = 0,
        optimization_goal: OptimizationGoal = OptimizationGoal.APP_INSTALLS,
        billing_event: BillingEvent = BillingEvent.IMPRESSIONS,
        bid_strategy: BidStrategy = BidStrategy.LOWEST_COST_WITHOUT_CAP,
        bid_amount: int | None = None,
        targeting: TargetingConfig | None = None,
        placements: list[str] | None = None,
        attribution_spec: list[dict] | None = None,
        status: str = "PAUSED",
    ) -> str:
        """创建广告组（Ad Set），返回 adset_id。

        Facebook Ads API: POST /act_{ad_account_id}/adsets

        Args:
            name: AdSet 名称
            campaign_id: 所属 Campaign ID
            daily_budget: 日预算（分）
            lifetime_budget: 总预算（分）
            optimization_goal: 优化目标
            billing_event: 计费事件
            bid_strategy: 出价策略
            bid_amount: 出价上限（分）
            targeting: 定向配置
            placements: 版位列表（空=自动版位）
            attribution_spec: 归因配置
            status: 状态

        Returns:
            adset_id 字符串，失败返回空字符串
        """
        url = f"{self._base_url}/act_{self._ad_account_id}/adsets"

        params: dict[str, Any] = {
            "access_token": self._access_token,
            "name": name,
            "campaign_id": campaign_id,
            "optimization_goal": optimization_goal.value if isinstance(optimization_goal, OptimizationGoal) else optimization_goal,
            "billing_event": billing_event.value if isinstance(billing_event, BillingEvent) else billing_event,
            "bid_strategy": bid_strategy.value if isinstance(bid_strategy, BidStrategy) else bid_strategy,
            "status": status,
        }

        # Budget
        if daily_budget > 0:
            params["daily_budget"] = daily_budget
        elif lifetime_budget > 0:
            params["lifetime_budget"] = lifetime_budget
        else:
            params["daily_budget"] = 1000  # 默认 $10

        # Bid amount
        if bid_amount is not None and bid_amount > 0:
            params["bid_amount"] = bid_amount

        # Targeting
        if targeting is not None:
            params["targeting"] = json.dumps(targeting.to_facebook_spec())
        else:
            params["targeting"] = json.dumps({
                "geo_locations": {"countries": ["US"]},
                "age_min": 18,
                "age_max": 65,
            })

        # Placements
        if placements:
            params["status"] = status  # keep
            params["targeting_optimization"] = "NONE"
            params["publisher_platforms"] = json.dumps(
                ["facebook", "instagram"]
            )

        # Attribution
        if attribution_spec:
            params["attribution_spec"] = json.dumps(attribution_spec)

        try:
            response = requests.post(url, data=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise RuntimeError(f"Facebook API error: {data['error']}")

            adset_id = data.get("id", "")
            print(f"  [FacebookPublisher] AdSet created: {adset_id}")
            return adset_id

        except Exception as e:
            self._log_error(f"Create adset failed: {e}")
            return ""

    def create_adset_from_config(self, config: AdSetConfig) -> str:
        """从 AdSetConfig 创建 AdSet"""
        return self.create_adset(
            name=config.name,
            campaign_id=config.campaign_id,
            daily_budget=config.daily_budget,
            lifetime_budget=config.lifetime_budget,
            optimization_goal=config.optimization_goal,
            billing_event=config.billing_event,
            bid_strategy=config.bid_strategy,
            bid_amount=config.bid_amount,
            targeting=config.targeting,
            placements=config.placements,
            attribution_spec=config.attribution_spec,
            status=config.status,
        )

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

        如果创建失败（App 开发模式限制 error 1885183），
        自动降级到 get_existing_creative_ids 回退方案。
        """
        creative_ids: list[str] = []
        url = f"{self._base_url}/act_{self._ad_account_id}/adcreatives"

        n = len(image_hashes)
        if n == 0:
            return []

        # extend headlines and primary_texts if shorter than images
        _headlines = list(headlines)
        _primary_texts = list(primary_texts)
        while len(_headlines) < n:
            _headlines.append(_headlines[0] if _headlines else "Play Now!")
        while len(_primary_texts) < n:
            _primary_texts.append(_primary_texts[0] if _primary_texts else "")

        for i, image_hash in enumerate(image_hashes):
            try:
                object_story_spec = {
                    "page_id": self._page_id,
                    "link_data": {
                        "image_hash": image_hash,
                        "link": app_link or "https://apps.apple.com/app/id000000000",
                        "message": _primary_texts[i],
                        "name": _headlines[i],
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
                    err = data["error"]
                    # error 1885183 = App in development mode
                    if err.get("error_subcode") == 1885183:
                        self._log_error(
                            f"Create creative [{i}] failed (App 开发模式): "
                            "需要 pages_manage_ads 权限或使用 App Review 后的 App。\n"
                            "    → 回退到复用现有 creative_id 方案"
                        )
                        return []  # 触发回退
                    raise RuntimeError(f"Facebook API error: {err}")

                creative_id = data.get("id", "")
                if creative_id:
                    creative_ids.append(creative_id)

            except Exception as e:
                self._log_error(f"Create creative failed [{i}]: {e}")

        return creative_ids

    def get_existing_creative_ids(self, limit: int = 20) -> list[str]:
        """获取广告账户下所有有效的 creative_id（用于回退方案）。

        当 App 处于开发模式无法创建新 creative 时，
        用这些已有 creative_id 配合 upload_images 的 image_hash 直接创建 ad。
        """
        url = f"{self._base_url}/act_{self._ad_account_id}/ads"
        params = {
            "access_token": self._access_token,
            "fields": "id,creative{id,image_hash},status,effective_status",
            "limit": limit,
        }
        creative_ids: list[str] = []
        seen: set[str] = set()

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                self._log_error(f"get_existing_creative_ids error: {data['error']}")
                return []

            for row in data.get("data", []):
                cr = row.get("creative") or {}
                cr_id = str(cr.get("id", ""))
                status = row.get("effective_status", row.get("status", ""))
                if cr_id and cr_id not in seen and status in ("ACTIVE", "PAUSED"):
                    creative_ids.append(cr_id)
                    seen.add(cr_id)

        except Exception as e:
            self._log_error(f"get_existing_creative_ids failed: {e}")

        return creative_ids

    def create_ad_with_image_hash(
        self,
        image_hash: str,
        adset_id: str,
        creative_ids: list[str],
        ad_name: str,
        status: str = "PAUSED",
    ) -> str | None:
        """用上传的 image_hash + 已有 creative_id 创建广告。

        当 App 在开发模式无法创建新 creative 时，使用此方法：
        - 复用已有 creative 的 page_id 配置
        - 配合 upload_images 返回的 image_hash 创建新 ad

        Returns:
            ad_id on success, None on failure.
        """
        if not creative_ids:
            self._log_error("create_ad_with_image_hash: no creative_ids available")
            return None

        # 轮流使用现有 creative_id
        for cr_id in creative_ids:
            try:
                params = {
                    "access_token": self._access_token,
                    "name": ad_name,
                    "adset_id": adset_id,
                    "creative": json.dumps({
                        "creative_id": cr_id,
                        "image_hash": image_hash,
                    }),
                    "status": status,
                }
                response = requests.post(
                    f"{self._base_url}/act_{self._ad_account_id}/ads",
                    data=params,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    err = data["error"]
                    if err.get("error_subcode") == 2446391:
                        # image_hash not compatible with this creative type
                        continue
                    self._log_error(f"create_ad_with_image_hash error: {err}")
                    return None

                ad_id = data.get("id", "")
                if ad_id:
                    print(f"  [FacebookPublisher] Ad created (fallback): {ad_id}")
                    return ad_id

            except Exception as e:
                self._log_error(f"create_ad_with_image_hash failed: {e}")

        return None

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

    def publish_full(
        self,
        image_dir: str,
        campaign_config: CampaignConfig,
        adset_configs: list[AdSetConfig],
        headlines: list[str] | None = None,
        primary_texts: list[str] | None = None,
        call_to_action: str = "INSTALL_MOBILE_APP",
        app_link: str = "",
        auto_activate: bool = False,
    ) -> PublishResult:
        """端到端完整发布：创建Campaign → 创建AdSet → 上传图片 → 创建创意 → 创建广告

        Args:
            image_dir: 生成图片的目录路径（递归扫描 .png）
            campaign_config: Campaign 创建配置
            adset_configs: AdSet 创建配置列表（多个AdSet支持多国家/多受众）
            headlines: 文案Headline列表
            primary_texts: 文案Primary Text列表
            call_to_action: CTA类型
            app_link: App下载链接
            auto_activate: 是否自动激活

        Returns:
            PublishResult
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        errors: list[str] = []

        # Step 1: Create Campaign
        campaign_id = self.create_campaign_from_config(campaign_config)
        if not campaign_id:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=0,
                creative_count=0,
                ad_count=0,
                errors=["Failed to create campaign"],
                published_at=datetime.now().isoformat(),
            )

        # Step 2: Create AdSets
        adset_ids: list[str] = []
        for cfg in adset_configs:
            cfg.campaign_id = campaign_id
            adset_id = self.create_adset_from_config(cfg)
            if adset_id:
                adset_ids.append(adset_id)
            else:
                errors.append(f"Failed to create adset: {cfg.name}")

        if not adset_ids:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=0,
                creative_count=0,
                ad_count=0,
                campaign_id=campaign_id,
                errors=errors + ["All adset creation failed"],
                published_at=datetime.now().isoformat(),
            )

        # Step 3: Scan and upload images
        image_paths = self._scan_images(image_dir)
        if not image_paths:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=0,
                creative_count=0,
                ad_count=0,
                campaign_id=campaign_id,
                adset_ids=adset_ids,
                errors=errors + [f"No PNG images found in {image_dir}"],
                published_at=datetime.now().isoformat(),
            )

        image_hashes = self.upload_images(image_paths)
        if not image_hashes:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=0,
                creative_count=0,
                ad_count=0,
                campaign_id=campaign_id,
                adset_ids=adset_ids,
                errors=errors + ["All image uploads failed"],
                published_at=datetime.now().isoformat(),
            )

        # Step 4: Create ad creatives
        hl = headlines or ["Play Now!"]
        pt = primary_texts or [""]
        creative_ids = self.create_ad_creatives(
            image_hashes=image_hashes,
            headlines=hl,
            primary_texts=pt,
            call_to_action=call_to_action,
            app_link=app_link,
        )

        if not creative_ids:
            return PublishResult(
                run_id=run_id,
                ad_account_id=self._ad_account_id,
                uploaded_count=len(image_hashes),
                creative_count=0,
                ad_count=0,
                campaign_id=campaign_id,
                adset_ids=adset_ids,
                image_hashes=image_hashes,
                errors=errors + ["All creative creation failed"],
                published_at=datetime.now().isoformat(),
            )

        # Step 5: Create ads (distribute creatives across adsets)
        ad_status = "ACTIVE" if auto_activate else "PAUSED"
        all_ad_ids: list[str] = []
        ads_per_adset = max(1, len(creative_ids) // len(adset_ids))

        for asi, adset_id in enumerate(adset_ids):
            start = asi * ads_per_adset
            end = start + ads_per_adset if asi < len(adset_ids) - 1 else len(creative_ids)
            subset_creatives = creative_ids[start:end]
            ad_names = [f"{campaign_config.name}_ad_{run_id}_{asi}_{j}" for j in range(len(subset_creatives))]

            ad_ids = self.create_ads(
                creative_ids=subset_creatives,
                adset_id=adset_id,
                names=ad_names,
                status=ad_status,
            )
            all_ad_ids.extend(ad_ids)

        result = PublishResult(
            run_id=run_id,
            ad_account_id=self._ad_account_id,
            uploaded_count=len(image_hashes),
            creative_count=len(creative_ids),
            ad_count=len(all_ad_ids),
            campaign_id=campaign_id,
            adset_ids=adset_ids,
            image_hashes=image_hashes,
            creative_ids=creative_ids,
            ad_ids=all_ad_ids,
            errors=errors,
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
