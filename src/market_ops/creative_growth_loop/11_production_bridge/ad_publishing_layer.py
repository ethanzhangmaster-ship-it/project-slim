"""Ad Upload / Publishing Layer - 广告上传发布层

P2.5-2: 将生成素材推送到广告平台。

支持：
- Meta Ads API（优先）
- 绑定 creative_id → ad_id → campaign_id
- 记录 ad_id / campaign_id / placement / budget
"""
from __future__ import annotations

import importlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

_PKG = "market_ops.creative_growth_loop"


@dataclass
class AdPublishRecord:
    """广告发布记录"""
    publish_id: str
    creative_id: str
    template_id: str
    layout_ast_id: str
    render_id: str
    
    ad_id: str = ""
    campaign_id: str = ""
    adset_id: str = ""
    
    ad_account_id: str = ""
    platform: str = "meta"
    
    creative_name: str = ""
    image_hash: str = ""
    
    status: str = "pending"
    error_message: str = ""
    
    budget_allocated: float = 0.0
    placement: str = ""
    
    compiler_version: int = 0
    published_at: int = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "publish_id": self.publish_id,
            "creative_id": self.creative_id,
            "template_id": self.template_id,
            "layout_ast_id": self.layout_ast_id,
            "render_id": self.render_id,
            "ad_id": self.ad_id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "ad_account_id": self.ad_account_id,
            "platform": self.platform,
            "creative_name": self.creative_name,
            "image_hash": self.image_hash,
            "status": self.status,
            "error_message": self.error_message,
            "budget_allocated": self.budget_allocated,
            "placement": self.placement,
            "compiler_version": self.compiler_version,
            "published_at": self.published_at,
            "metadata": self.metadata,
        }


@dataclass
class PublishBatchResult:
    """批量发布结果"""
    batch_id: str
    total_count: int
    success_count: int
    failed_count: int
    
    records: List[AdPublishRecord] = field(default_factory=list)
    
    started_at: int = 0
    completed_at: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "records": [r.to_dict() for r in self.records],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class AdPublishingLayer:
    """广告发布层 - 管理素材到广告平台的发布
    
    核心职责：
    1. 将渲染好的素材上传到广告平台
    2. 建立 creative_id ↔ ad_id ↔ campaign_id 映射
    3. 记录编译器版本，确保数据可回溯
    4. 支持多种广告平台
    """
    
    def __init__(self, output_dir: str = "memory/closed_loop"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.records_file = self.output_dir / "publish_records.json"
        self._records: Dict[str, AdPublishRecord] = {}
        self._ad_to_creative: Dict[str, str] = {}
        
        self._publisher_cache = {}
        
        self._load_records()
    
    def _load_records(self):
        if self.records_file.exists():
            with open(self.records_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for pid, rec_data in data.items():
                    self._records[pid] = AdPublishRecord(**rec_data)
                    if rec_data.get("ad_id"):
                        self._ad_to_creative[rec_data["ad_id"]] = pid
    
    def _save_records(self):
        data = {pid: rec.to_dict() for pid, rec in self._records.items()}
        with open(self.records_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _get_facebook_publisher(self, access_token: str, ad_account_id: str,
                                 page_id: str = "", api_version: str = "v19.0"):
        cache_key = f"{ad_account_id}_{access_token[-8:]}"
        if cache_key not in self._publisher_cache:
            fb_module = importlib.import_module(f"{_PKG}.14_publish.facebook_publisher")
            publisher = fb_module.FacebookPublisher(
                access_token=access_token,
                ad_account_id=ad_account_id,
                api_version=api_version,
                page_id=page_id,
            )
            self._publisher_cache[cache_key] = publisher
        return self._publisher_cache[cache_key]
    
    def register_creative_for_publish(self, creative_id: str, template_id: str,
                                      layout_ast_id: str, render_id: str,
                                      compiler_version: int = 1) -> str:
        """注册待发布的创意"""
        publish_id = f"pub_{uuid.uuid4().hex[:8]}"
        
        record = AdPublishRecord(
            publish_id=publish_id,
            creative_id=creative_id,
            template_id=template_id,
            layout_ast_id=layout_ast_id,
            render_id=render_id,
            compiler_version=compiler_version,
            status="registered",
        )
        
        self._records[publish_id] = record
        self._save_records()
        
        return publish_id
    
    def publish_to_meta(self, publish_id: str,
                        access_token: str, ad_account_id: str,
                        campaign_id: str, adset_id: str,
                        image_path: str, page_id: str = "",
                        creative_name: str = "",
                        api_version: str = "v19.0") -> AdPublishRecord:
        """发布到 Meta Ads 平台"""
        if publish_id not in self._records:
            raise ValueError(f"Publish record not found: {publish_id}")
        
        record = self._records[publish_id]
        record.status = "publishing"
        
        try:
            publisher = self._get_facebook_publisher(
                access_token, ad_account_id, page_id, api_version
            )
            
            creative_name = creative_name or f"IC_{record.template_id}_{record.creative_id}"
            
            image_hashes = publisher.upload_images([image_path])
            if image_hashes:
                record.image_hash = image_hashes[0]
            
            if campaign_id and adset_id:
                result = publisher.create_ads_with_images(
                    image_paths=[image_path],
                    image_hashes=image_hashes,
                    campaign_id=campaign_id,
                    adset_id=adset_id,
                    creative_base_name=creative_name,
                )
                
                if result.get("ad_ids"):
                    record.ad_id = result["ad_ids"][0]
                    record.status = "published"
                else:
                    record.status = "failed"
                    record.error_message = result.get("errors", ["Unknown error"])[0]
            else:
                record.status = "image_uploaded"
                record.error_message = "No campaign/adset provided"
            
            record.campaign_id = campaign_id
            record.adset_id = adset_id
            record.ad_account_id = ad_account_id
            record.platform = "meta"
            record.creative_name = creative_name
            record.published_at = int(time.time())
            
            if record.ad_id:
                self._ad_to_creative[record.ad_id] = publish_id
            
        except Exception as e:
            record.status = "failed"
            record.error_message = str(e)
        
        self._save_records()
        return record
    
    def publish_batch(self, publish_jobs: List[Dict[str, Any]],
                      access_token: str, ad_account_id: str,
                      campaign_id: str, adset_id: str,
                      page_id: str = "") -> PublishBatchResult:
        """批量发布"""
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        result = PublishBatchResult(
            batch_id=batch_id,
            total_count=len(publish_jobs),
            started_at=int(time.time()),
        )
        
        for job in publish_jobs:
            try:
                publish_id = self.register_creative_for_publish(
                    creative_id=job.get("creative_id", ""),
                    template_id=job.get("template_id", "merge_formula"),
                    layout_ast_id=job.get("layout_ast_id", ""),
                    render_id=job.get("render_id", ""),
                    compiler_version=job.get("compiler_version", 1),
                )
                
                record = self.publish_to_meta(
                    publish_id=publish_id,
                    access_token=access_token,
                    ad_account_id=ad_account_id,
                    campaign_id=campaign_id,
                    adset_id=adset_id,
                    image_path=job.get("image_path", ""),
                    page_id=page_id,
                    creative_name=job.get("creative_name", ""),
                )
                
                result.records.append(record)
                if record.status == "published":
                    result.success_count += 1
                else:
                    result.failed_count += 1
                    
            except Exception as e:
                result.failed_count += 1
                print(f"Publish job failed: {e}")
        
        result.completed_at = int(time.time())
        return result
    
    def get_creative_by_ad(self, ad_id: str) -> Optional[AdPublishRecord]:
        """通过 ad_id 回溯 creative"""
        publish_id = self._ad_to_creative.get(ad_id)
        if publish_id:
            return self._records.get(publish_id)
        return None
    
    def get_publish_record(self, publish_id: str) -> Optional[AdPublishRecord]:
        return self._records.get(publish_id)
    
    def get_records_by_template(self, template_id: str) -> List[AdPublishRecord]:
        return [r for r in self._records.values() if r.template_id == template_id]
    
    def get_published_ads(self) -> List[AdPublishRecord]:
        return [r for r in self._records.values() if r.status == "published"]
    
    def get_mapping_summary(self) -> Dict[str, Any]:
        total = len(self._records)
        published = sum(1 for r in self._records.values() if r.status == "published")
        failed = sum(1 for r in self._records.values() if r.status == "failed")
        
        by_template = {}
        for r in self._records.values():
            by_template[r.template_id] = by_template.get(r.template_id, 0) + 1
        
        return {
            "total": total,
            "published": published,
            "failed": failed,
            "by_template": by_template,
            "ad_to_creative_mappings": len(self._ad_to_creative),
        }
