"""Asset Upload Layer - 素材上传层（CDN/S3）

上传素材到可访问 URL：
- S3 (支持)
- CDN (支持)
- Local Mock (开发环境)

输出必须包含 asset_url
"""
from __future__ import annotations

import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class UploadedAsset:
    """上传后的素材"""
    asset_id: str
    asset_url: str
    upload_id: str = ""
    
    file_path: str = ""
    sha256: str = ""
    size_bytes: int = 0
    
    upload_status: str = "pending"
    uploaded_at: int = 0
    
    provider: str = "local"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_url": self.asset_url,
            "upload_id": self.upload_id,
            "file_path": self.file_path,
            "sha256": self.sha256,
            "size": self.size_bytes,
            "upload_status": self.upload_status,
            "uploaded_at": self.uploaded_at,
            "provider": self.provider,
        }


class AssetUploadEngine:
    """素材上传引擎 - 本地上传到可访问 URL
    
    支持：
    - local: 本地文件服务（开发/测试）
    - s3: AWS S3（生产）
    - cdn: CDN（生产）
    """
    
    def __init__(self, provider: str = "local",
                 local_base_url: str = "http://localhost:8080/assets",
                 local_upload_dir: str = "assets/public",
                 s3_bucket: str = "",
                 s3_region: str = "us-east-1",
                 cdn_base_url: str = ""):
        self.provider = provider
        self.local_base_url = local_base_url
        self.local_upload_dir = Path(local_upload_dir)
        self.local_upload_dir.mkdir(parents=True, exist_ok=True)
        self.s3_bucket = s3_bucket
        self.s3_region = s3_region
        self.cdn_base_url = cdn_base_url
        
        self._uploads: Dict[str, UploadedAsset] = {}
    
    def upload_file(self, file_path: str, asset_id: str = "",
                     sha256: str = "") -> UploadedAsset:
        """上传文件
        
        Args:
            file_path: 本地文件路径
            asset_id: 素材ID（可选，自动生成）
            sha256: 文件哈希（可选，自动计算）
        
        Returns:
            UploadedAsset: 包含可访问 URL
        """
        if not os.path.exists(file_path):
            return UploadedAsset(
                asset_id=asset_id or "unknown",
                asset_url="",
                upload_status="failed",
            )
        
        if not asset_id:
            asset_id = f"asset_{uuid.uuid4().hex[:12]}"
        
        upload_id = f"upload_{uuid.uuid4().hex[:12]}"
        
        if self.provider == "local":
            return self._upload_local(file_path, asset_id, upload_id, sha256)
        elif self.provider == "s3":
            return self._upload_s3(file_path, asset_id, upload_id, sha256)
        elif self.provider == "cdn":
            return self._upload_cdn(file_path, asset_id, upload_id, sha256)
        else:
            return self._upload_local(file_path, asset_id, upload_id, sha256)
    
    def _upload_local(self, file_path: str, asset_id: str,
                       upload_id: str, sha256: str) -> UploadedAsset:
        """本地上传（开发/测试环境）"""
        file_name = os.path.basename(file_path)
        dest_path = self.local_upload_dir / file_name
        
        shutil.copy2(file_path, dest_path)
        
        file_size = os.path.getsize(dest_path)
        
        if not sha256:
            import hashlib
            h = hashlib.sha256()
            with open(dest_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    h.update(chunk)
            sha256 = h.hexdigest()
        
        asset_url = f"{self.local_base_url}/{file_name}"
        
        result = UploadedAsset(
            asset_id=asset_id,
            asset_url=asset_url,
            upload_id=upload_id,
            file_path=str(dest_path),
            sha256=sha256,
            size_bytes=file_size,
            upload_status="success",
            uploaded_at=int(time.time()),
            provider="local",
        )
        
        self._uploads[upload_id] = result
        return result
    
    def _upload_s3(self, file_path: str, asset_id: str,
                    upload_id: str, sha256: str) -> UploadedAsset:
        """S3 上传（生产环境 - 预留接口）"""
        if not self.s3_bucket:
            return self._upload_local(file_path, asset_id, upload_id, sha256)
        
        try:
            import boto3
            s3 = boto3.client('s3', region_name=self.s3_region)
            
            file_name = os.path.basename(file_path)
            s3_key = f"creatives/{asset_id}/{file_name}"
            
            with open(file_path, 'rb') as f:
                s3.upload_fileobj(f, self.s3_bucket, s3_key)
            
            asset_url = f"https://{self.s3_bucket}.s3.{self.s3_region}.amazonaws.com/{s3_key}"
            
            result = UploadedAsset(
                asset_id=asset_id,
                asset_url=asset_url,
                upload_id=upload_id,
                file_path=file_path,
                sha256=sha256,
                size_bytes=os.path.getsize(file_path),
                upload_status="success",
                uploaded_at=int(time.time()),
                provider="s3",
            )
            
            self._uploads[upload_id] = result
            return result
        except ImportError:
            return self._upload_local(file_path, asset_id, upload_id, sha256)
        except Exception as e:
            return UploadedAsset(
                asset_id=asset_id,
                asset_url="",
                upload_id=upload_id,
                upload_status="failed",
                provider="s3",
            )
    
    def _upload_cdn(self, file_path: str, asset_id: str,
                     upload_id: str, sha256: str) -> UploadedAsset:
        """CDN 上传（生产环境 - 预留接口）"""
        if not self.cdn_base_url:
            return self._upload_local(file_path, asset_id, upload_id, sha256)
        
        s3_result = self._upload_s3(file_path, asset_id, upload_id, sha256)
        
        if s3_result.upload_status == "success":
            file_name = os.path.basename(file_path)
            cdn_url = f"{self.cdn_base_url}/creatives/{asset_id}/{file_name}"
            s3_result.asset_url = cdn_url
            s3_result.provider = "cdn"
        
        return s3_result
    
    def get_upload(self, upload_id: str) -> Optional[UploadedAsset]:
        return self._uploads.get(upload_id)
