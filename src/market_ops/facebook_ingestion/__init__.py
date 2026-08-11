"""E11 Phase 1.5 — Facebook Ads Reality Ingestion Layer。

将 Facebook Ads 投放数据标准化接入 Creative Repository。

Phase 1.5 升级：
  - creative_asset_id 升级为 {产品}_{类型}_{日期}_{序号} 格式
  - FacebookCreativeEntity → CreativeEntity 自动转换
  - Storage 同时保存 entity.json + facebook.json
  - 新增 DataQualityValidator 数据质量检查

后续阶段：
  Phase 2: CreativeEntity + Adjust → ROAS/LTV
  Phase 3: CreativeEntity + Eagle → 真实视频文件
  Phase 4: CreativeEntity + Lovart → Creative DNA
  Phase 5: Winner DNA → New Creative Generation

Usage:
    from market_ops.facebook_ingestion import (
        FacebookClient,
        CreativeFetcher,
        AdParser,
        CreativeStorage,
        SyncEngine,
        DataQualityValidator,
        FacebookCreativeEntity,
        CreativeType,
    )

    client = FacebookClient(access_token="xxx", ad_account_id="123456")
    engine = SyncEngine(client)
    result = engine.sync(start_date, end_date)

    # 数据质量检查
    validator = DataQualityValidator(engine.storage)
    report = validator.validate()
    print(report.to_summary())
"""

from .models import FacebookCreativeEntity, CreativeType
from .facebook_client import FacebookClient
from .creative_fetcher import CreativeFetcher
from .ad_parser import AdParser
from .storage import CreativeStorage
from .sync_engine import SyncEngine, SyncResult
from .validator import DataQualityValidator

__all__ = [
    "FacebookCreativeEntity",
    "CreativeType",
    "FacebookClient",
    "CreativeFetcher",
    "AdParser",
    "CreativeStorage",
    "SyncEngine",
    "SyncResult",
    "DataQualityValidator",
]