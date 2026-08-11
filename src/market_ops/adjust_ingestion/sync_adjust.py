"""E11 Phase 2 — Adjust Sync CLI Entry Point。

Usage:
    python sync_adjust.py --start 2026-07-01 --end 2026-07-21
    python sync_adjust.py --start 2026-07-01 --end 2026-07-21 --api-token xxx --app-token yyy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from market_ops.adjust_ingestion import (
    AdjustClient,
    AdjustSyncEngine,
    AdjustDataQualityValidator,
    AdjustStorage,
)
from market_ops.facebook_ingestion import CreativeStorage


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Adjust Revenue Sync — 将 Adjust 收入数据匹配到 CreativeEntity",
    )
    parser.add_argument(
        "--start", required=True,
        help="起始日期 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end", required=True,
        help="结束日期 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--api-token", default="",
        help="Adjust API Token",
    )
    parser.add_argument(
        "--app-token", default="",
        help="Adjust App Token",
    )
    parser.add_argument(
        "--data-dir", default="data/creatives",
        help="Creative 数据目录 (默认: data/creatives)",
    )

    args = parser.parse_args()

    # 1. 初始化
    client = AdjustClient(api_token=args.api_token, app_token=args.app_token)
    creative_storage = CreativeStorage(root_dir=args.data_dir)

    # 2. 同步
    engine = AdjustSyncEngine(client, creative_storage)
    result = engine.sync(start_date=args.start, end_date=args.end)

    # 3. 输出
    print(result.to_summary())

    if result.errors:
        print(f"  Errors: {len(result.errors)}")
        for err in result.errors:
            print(f"    - {err}")

    # 4. 质量检查
    adjust_storage = AdjustStorage(root_dir=args.data_dir)
    validator = AdjustDataQualityValidator(adjust_storage)
    quality_report = validator.validate()
    print(quality_report.to_summary())


if __name__ == "__main__":
    main()