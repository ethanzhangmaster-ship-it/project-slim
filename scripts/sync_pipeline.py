#!/usr/bin/env python3
"""
P04 Data Sync Pipeline — E11.1 Entity Pipeline

架构:
  UnifiedSyncOrchestrator
      ├── Facebook SyncEngine → CreativeStorage
      └── Adjust SyncEngine   → CreativeStorage (match + merge)
              ↓
  FeatureStore (Entity → Feature Snapshot)
              ↓
  CSV Export (backward compatible artifact)

CSV 已降级为 export artifact，CreativeStorage 是唯一数据资产层。

用法:
  python scripts/sync_pipeline.py           # 增量同步 (昨天)
  python scripts/sync_pipeline.py --full    # 30天回溯
  python scripts/sync_pipeline.py --days 30 # 指定天数
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv()

from market_ops.e11.orchestrator import UnifiedSyncOrchestrator, SyncReport
from market_ops.feature_store import FeatureStore

# ── Config ──────────────────────────────────────────────────────────
FB_TOKEN = os.environ.get("FB_TOKEN", "") or os.environ.get("META_ACCESS_TOKEN", "")
FB_API_VERSION = os.environ.get("META_API_VERSION", "v19.0")
ADJUST_TOKEN = os.environ.get("ADJUST_TOKEN", "jzss-pBPTCF9fPcvYrbqNVsa2aay4aSsVK7KuAxpKPayWFecYg")
ADJUST_APP_TOKEN = os.environ.get("ADJUST_APP_TOKEN", "")

OUTPUT_DIR = ROOT / "output" / "p04_platform_analysis"
CREATIVE_STORAGE_DIR = ROOT / "data" / "creatives"
FEATURE_STORE_DIR = ROOT / "data" / "feature_store"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# P04 all 10 Facebook accounts
P04_ACCOUNTS = [
    {"id": "1959429141294402", "name": "P04 And 1", "platform": "Android"},
    {"id": "1455525822955003", "name": "P04 And 2", "platform": "Android"},
    {"id": "1379499207181514", "name": "P04 iOS 1", "platform": "iOS"},
    {"id": "1423660739468966", "name": "P04 iOS 2", "platform": "iOS"},
    {"id": "1628583695016910", "name": "P04 iOS 3", "platform": "iOS"},
    {"id": "2068461353924819", "name": "P04 iOS 6", "platform": "iOS"},
    {"id": "1868794510383229", "name": "P04 iOS 7", "platform": "iOS"},
    {"id": "2736817463332226", "name": "P04 Connect", "platform": "iOS"},
    {"id": "1784471669598847", "name": "P04 And 3", "platform": "Android"},
    {"id": "820201270652176", "name": "P04 And Adtiger", "platform": "Android"},
]

# Output files (backward compatible)
MERGED_FILE = OUTPUT_DIR / "p04_merged_fb_adjust.csv"
SYNC_LOG_FILE = OUTPUT_DIR / "sync_log.jsonl"
SYNC_REPORT_FILE = OUTPUT_DIR / "sync_report.json"

# ── Helpers ─────────────────────────────────────────────────────────


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")
    with open(SYNC_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "level": level, "msg": msg}, ensure_ascii=False) + "\n")


# ════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════


def run_sync(days_back: int = 1, full_backfill: bool = False, skip_adjust: bool = False):
    """Run the E11.1 Entity Pipeline.

    Args:
        days_back: Number of days to sync Facebook (default 1 = yesterday)
        full_backfill: If True, pull 30 days for both Facebook + Adjust
        skip_adjust: If True, skip Adjust sync (Facebook only)
    """
    today = date.today()

    if full_backfill:
        fb_date = today - timedelta(days=30)
        adjust_start = (today - timedelta(days=30)).isoformat()
    else:
        fb_date = today - timedelta(days=days_back)
        adjust_start = (today - timedelta(days=30)).isoformat()

    adjust_end = today.isoformat()

    log("=" * 60)
    log(f"P04 E11.1 Entity Pipeline: {fb_date.isoformat()} ~ {today.isoformat()}")
    log(f"  Facebook: {fb_date.isoformat()} ({days_back}d)")
    log(f"  Adjust:   {adjust_start} ~ {adjust_end} (30d backfill)")
    log(f"  Storage:  {CREATIVE_STORAGE_DIR}")
    log(f"  Features: {FEATURE_STORE_DIR}")
    log("=" * 60)

    # ── Phase 1: Unified Sync ────────────────────────────────────────
    log("\n[Phase 1] Unified Sync (Facebook + Adjust)...")

    if skip_adjust:
        adjust_config = {}
    else:
        adjust_config = {
            "api_token": ADJUST_TOKEN,
            "app_token": ADJUST_APP_TOKEN,
        }

    orchestrator = UnifiedSyncOrchestrator(
        creative_storage_root=str(CREATIVE_STORAGE_DIR),
        facebook_accounts=P04_ACCOUNTS,
        adjust_config=adjust_config,
        fb_token=FB_TOKEN,
        fb_api_version=FB_API_VERSION,
    )

    started = time.time()

    report = orchestrator.run_daily_sync(
        fb_date=fb_date,
        adjust_start=adjust_start,
        adjust_end=adjust_end,
    )

    elapsed = time.time() - started

    # ── Phase 2: Feature Extraction ─────────────────────────────────
    log("\n[Phase 2] Feature Extraction...")

    feature_store = FeatureStore(root_path=str(FEATURE_STORE_DIR))
    feature_count = feature_store.update_from_storage(orchestrator.creative_storage)

    log(f"  Feature snapshots: {feature_count}")

    # ── Phase 3: CSV Export (backward compatible) ────────────────────
    log("\n[Phase 3] CSV Export...")

    export_path = feature_store.export_to_csv(str(MERGED_FILE))
    log(f"  Exported: {export_path}")

    # ── Phase 4: Persist Sync Report ─────────────────────────────────
    report_dict = report.to_dict()
    report_dict["elapsed_seconds"] = round(elapsed, 1)
    report_dict["feature_store"] = {
        "root": str(FEATURE_STORE_DIR),
        "snapshots": feature_count,
    }
    report_dict["csv_export"] = str(MERGED_FILE)

    with open(SYNC_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    # ── Audit ────────────────────────────────────────────────────────
    log(f"\n{'=' * 60}")
    log(f"Sync Complete ({round(elapsed)}s)")
    log(f"  CreativeStorage: {report.creative_storage_count} entities")
    log(f"  FeatureStore:    {feature_count} snapshots")
    log(f"  CSV Export:      {MERGED_FILE}")
    log(f"  Report:          {SYNC_REPORT_FILE}")
    log(f"  Log:             {SYNC_LOG_FILE}")
    log(f"{'=' * 60}")
    print(report.to_summary())


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P04 E11.1 Entity Pipeline")
    parser.add_argument("--full", action="store_true", help="Full 30-day backfill")
    parser.add_argument("--days", type=int, default=1, help="Days to sync Facebook (default 1)")
    parser.add_argument("--skip-adjust", action="store_true", help="Skip Adjust pull")
    args = parser.parse_args()

    run_sync(days_back=args.days, full_backfill=args.full, skip_adjust=args.skip_adjust)