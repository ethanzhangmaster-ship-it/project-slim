#!/usr/bin/env python3
"""Facebook Ads 全量重抓 — 多账户 + 全窗口 + 真实图片下载（健壮版）

修复点（相比旧 fetch_facebook_data_local.py）：
  1. Token 从环境变量 FB_ACCESS_TOKEN 读取（不再写死）
  2. 自动发现 token 下【所有】广告账户
  3. 日期窗口参数化（默认 2025-11-01 → 2026-07-13）
  4. 真正下载图片二进制到 facebook_top_creatives/
  5. 断点续跑：已下载的 creative_id 跳过；分页 + 限流
  6. 健壮化：API 错误自动重试退避；大账户 "reduce data" 自动降 limit 重试

用法：
  set FB_ACCESS_TOKEN=EAAB...
  python scripts/fetch_facebook_full.py
可选：
  --start 2025-11-01 --end 2026-07-13
  --accounts-only        只列出账户
  --no-images           不下载图片
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "output" / "facebook_top_creatives"
OUT_FILE = ROOT / "output" / "facebook_fresh_data.json"
API_VERSION = "v19.0"

# 过期兜底（仅提示，不保证可用）
_FALLBACK_TOKEN = "EAAOu0s4qSmUBR...EXPIRED_2026-06-28"


def get_token() -> str:
    tok = os.environ.get("FB_ACCESS_TOKEN", "").strip()
    if tok:
        return tok
    print("⚠️  环境变量 FB_ACCESS_TOKEN 为空，使用仓库内过期兜底 token（大概率已失效）。")
    return _FALLBACK_TOKEN


def _backoff_sleep(attempt: int) -> None:
    time.sleep(min(2 ** attempt, 30))  # 1s, 2s, 4s, 8s ... 上限 30s


def fetch_paginated(url: str, params: dict, token: str, max_pages: int = 300,
                    retries: int = 3) -> tuple[list[dict], bool]:
    """返回 (results, hit_error)。遇 API/网络错误自动重试退避。"""
    results: list[dict] = []
    page = 0
    while url and page < max_pages:
        attempt = 0
        ok = False
        while attempt <= retries:
            try:
                r = requests.get(url, params=params, verify=False, timeout=90)
                data = r.json()
                if "error" in data:
                    code = data["error"].get("code")
                    msg = data["error"].get("message", "")
                    print(f"  ⚠️  API Error {code}: {msg[:120]}")
                    # reduce data / 限流 类错误稍后重试（降 limit 在外层处理）
                    if attempt < retries:
                        _backoff_sleep(attempt)
                        attempt += 1
                        continue
                    return results, True
                results.extend(data.get("data", []))
                url = data.get("paging", {}).get("next", "")
                params = None
                ok = True
                break
            except Exception as e:
                print(f"  ⚠️  网络错误: {e}")
                if attempt < retries:
                    _backoff_sleep(attempt)
                    attempt += 1
                    continue
                return results, True
        if not ok:
            return results, True
        page += 1
        if url:
            print(f"    分页 {page}: {len(results)} rows...")
    return results, False


def fetch_with_limit_fallback(getter, limits, label: str) -> list[dict]:
    """对 getter(limit) 依次尝试不同 limit，遇到 reduce-data 错误则降级。"""
    last_err = False
    for lim in limits:
        print(f"  {label} (limit={lim})...")
        rows, err = getter(lim)
        if not err:
            print(f"  {label}: {len(rows)} ✅")
            return rows
        last_err = err
        # 继续尝试更小的 limit
    print(f"  ⚠️  {label} 在各级 limit 下均失败，返回空。")
    return []


def download_image(url: str, dest: Path, token: str) -> bool:
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = requests.get(url, headers=headers, verify=False, timeout=90, stream=True)
        if r.status_code != 200:
            return False
        ct = r.headers.get("Content-Type", "")
        if not ct.startswith("image"):
            return False
        dest.write_bytes(r.content)
        return dest.stat().st_size > 1000
    except Exception:
        return False


def safe_name(s: str, limit: int = 40) -> str:
    bad = '<>:"/\\|?*'
    for c in bad:
        s = s.replace(c, "_")
    s = s.strip().replace(" ", "_")
    return s[:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-11-01")
    ap.add_argument("--end", default="2026-07-13")
    ap.add_argument("--accounts-only", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()

    token = get_token()
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("  Facebook Ads 全量重抓（健壮版）")
    print(f"  窗口: {args.start} → {args.end}")
    print(f"  图片目录: {IMG_DIR}")
    print("=" * 64)

    # 1) 校验 token
    print("\n  校验 token...")
    me = requests.get(f"https://graph.facebook.com/{API_VERSION}/me",
                      params={"access_token": token, "fields": "id,name"},
                      verify=False, timeout=20).json()
    if "error" in me:
        print(f"  ❌ Token 无效/过期: {me['error'].get('message')}")
        return 1
    print(f"  ✅ Token 有效: {me.get('name', me.get('id'))}")

    # 2) 发现所有账户
    print("\n  发现广告账户...")
    accounts = fetch_paginated(
        f"https://graph.facebook.com/{API_VERSION}/me/adaccounts",
        {"access_token": token, "fields": "id,name,account_id"}, token)[0]
    if not accounts:
        print("  ⚠️  未返回任何账户（token 可能无 ads_read 权限）")
        return 1
    print(f"  ✅ 可访问账户 {len(accounts)} 个:")
    for a in accounts:
        print(f"    {a['id']} | {a.get('name','?')}")

    if args.accounts_only:
        return 0

    time_range = json.dumps({"since": args.start, "until": args.end})
    all_ads: list[dict] = []
    all_insights: list[dict] = []
    ad_creative_map: dict[str, dict] = {}

    for acc in accounts:
        acc_id = acc["id"]
        print(f"\n── 账户 {acc_id} ({acc.get('name','?')}) ──")

        # 3) ads + creative（含图片 URL），大账户自动降 limit
        def get_ads(lim):
            p = {
                "access_token": token,
                "fields": ("id,name,effective_status,created_time,"
                           "campaign{name},adset{name},"
                           "creative{id,name,title,thumbnail_url,image_url}"),
                "limit": lim,
            }
            return fetch_paginated(
                f"https://graph.facebook.com/{API_VERSION}/{acc_id}/ads", p, token)

        ads = fetch_with_limit_fallback(get_ads, [500, 100, 25], "ads")
        print(f"  ads: {len(ads)}")
        for ad in ads:
            aid = ad.get("id", "")
            cr = ad.get("creative", {}) or {}
            cid = cr.get("id", "")
            if aid and cid:
                ad_creative_map[aid] = {
                    "creative_id": cid,
                    "creative_name": cr.get("name", ""),
                    "title": cr.get("title", ""),
                    "image_url": cr.get("image_url", ""),
                    "thumbnail_url": cr.get("thumbnail_url", ""),
                    "ad_name": ad.get("name", ""),
                    "campaign_name": (ad.get("campaign") or {}).get("name", ""),
                    "adset_name": (ad.get("adset") or {}).get("name", ""),
                    "status": ad.get("effective_status", ""),
                    "created_time": ad.get("created_time", ""),
                }
        all_ads.extend(ads)

        # 4) insights（全窗口聚合，ad 层级），大账户自动降 limit
        def get_ins(lim):
            p = {
                "access_token": token,
                "level": "ad",
                "time_range": time_range,
                "fields": ("ad_id,ad_name,campaign_name,adset_name,spend,impressions,"
                           "clicks,ctr,cpm,cpc,actions,action_values"),
                "limit": lim,
            }
            return fetch_paginated(
                f"https://graph.facebook.com/{API_VERSION}/{acc_id}/insights", p, token)

        ins = fetch_with_limit_fallback(get_ins, [500, 100, 25], "insights")
        print(f"  insights: {len(ins)}")
        all_insights.extend(ins)
        time.sleep(2)  # 账户间限流

    # 5) 合并
    print(f"\n  合并 ad({len(all_ads)}) + insight({len(all_insights)})...")
    merged = []
    for ins in all_insights:
        aid = ins.get("ad_id", "")
        info = ad_creative_map.get(aid, {})
        merged.append({
            "creative_id": info.get("creative_id", aid),
            "creative_name": info.get("creative_name", ""),
            "title": info.get("title", ""),
            "image_url": info.get("image_url", ""),
            "thumbnail_url": info.get("thumbnail_url", ""),
            "ad_id": aid,
            "ad_name": ins.get("ad_name", info.get("ad_name", "")),
            "campaign_name": ins.get("campaign_name", info.get("campaign_name", "")),
            "adset_name": ins.get("adset_name", info.get("adset_name", "")),
            "status": info.get("status", ""),
            "created_time": info.get("created_time", ""),
            "spend": float(ins.get("spend", 0)),
            "impressions": int(ins.get("impressions", 0)),
            "clicks": int(ins.get("clicks", 0)),
            "ctr": float(ins.get("ctr", 0)),
            "cpm": float(ins.get("cpm", 0)),
            "cpc": float(ins.get("cpc", 0)),
            "actions": ins.get("actions", []),
            "action_values": ins.get("action_values", []),
            "date_start": ins.get("date_start", ""),
            "date_stop": ins.get("date_stop", ""),
        })

    # 6) 下载图片（多线程并发 + 断点续跑）
    img_done = img_skip = img_fail = 0
    if not args.no_images:
        print(f"\n  下载图片到 {IMG_DIR}（并发 + 断点续跑）...")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        tasks = []  # (url, dest, fallback_url)
        seen = set()
        for m in merged:
            cid = m.get("creative_id", "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            name_tag = safe_name(m.get("creative_name", m.get("ad_name", "")))
            base = f"{name_tag}_{cid[-6:]}" if name_tag else cid
            if list(IMG_DIR.glob(f"{base}.*")):
                img_skip += 1
                continue
            url = m.get("image_url") or m.get("thumbnail_url")
            if not url:
                img_fail += 1
                continue
            ext = Path(urlparse(url).path).suffix or ".jpg"
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
            dest = IMG_DIR / f"{base}{ext}"
            fb = m.get("thumbnail_url") if (m.get("thumbnail_url") and m.get("thumbnail_url") != url) else None
            tasks.append((url, dest, fb))

        def worker(t):
            url, dest, fb = t
            if download_image(url, dest, token):
                return True
            if fb and download_image(fb, dest, token):
                return True
            if dest.exists() and dest.stat().st_size <= 1000:
                dest.unlink(missing_ok=True)
            return False

        done_lock = {"d": 0, "f": 0}
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(worker, t) for t in tasks]
            for fut in as_completed(futs):
                try:
                    ok = fut.result()
                except Exception:
                    ok = False
                if ok:
                    img_done += 1
                else:
                    img_fail += 1
                if (img_done + img_fail) % 50 == 0:
                    print(f"    已下载 {img_done}，失败 {img_fail}，跳过 {img_skip}")
        print(f"  图片: 新下载 {img_done} / 跳过已存在 {img_skip} / 失败 {img_fail}")

    # 7) 保存
    total_spend = sum(m["spend"] for m in merged)
    total_imp = sum(m["impressions"] for m in merged)
    total_clk = sum(m["clicks"] for m in merged)
    uniq = len(set(m["creative_id"] for m in merged if m["creative_id"]))
    dates = sorted(set(m["date_start"] for m in merged if m["date_start"]))
    out = {
        "pulled_at": date.today().isoformat(),
        "date_range": {"start": args.start, "end": args.end},
        "accounts": [{"id": a["id"], "name": a.get("name", "")} for a in accounts],
        "stats": {
            "total_rows": len(merged),
            "unique_creatives": uniq,
            "total_spend": round(total_spend, 2),
            "total_impressions": total_imp,
            "total_clicks": total_clk,
            "dates": dates,
            "images_downloaded": img_done,
            "images_skipped": img_skip,
            "images_failed": img_fail,
        },
        "data": merged,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  ✅ 保存: {OUT_FILE} ({OUT_FILE.stat().st_size/1024:.0f} KB)")
    print(f"  唯一 creative: {uniq} | 日期: {dates[0] if dates else '?'}→{dates[-1] if dates else '?'}")
    print(f"  Spend ${total_spend:,.0f} | Imp {total_imp:,} | Clk {total_clk:,}")
    print(f"\n  下一步: python scripts/import_facebook_fresh.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
