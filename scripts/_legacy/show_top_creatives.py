#!/usr/bin/env python3
"""Show P04 Witch top spending images and videos by platform (Android vs iOS)."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "db" / "facebook_performance.duckdb"

conn = duckdb.connect(str(DB), read_only=True)

# Get creative_type from unified_state
def get_creative_type(creative_id: str) -> str:
    try:
        r = conn.execute("""
            SELECT creative_type FROM unified_state 
            WHERE creative_id = ? AND creative_type IS NOT NULL AND creative_type != ''
            LIMIT 1
        """, [creative_id]).fetchone()
        return r[0] if r else "unknown"
    except:
        return "unknown"

def get_image_thumb(creative_id: str) -> str:
    try:
        r = conn.execute("""
            SELECT thumbnail_url FROM ad_graph 
            WHERE creative_id = ? AND thumbnail_url IS NOT NULL AND thumbnail_url != ''
            LIMIT 1
        """, [creative_id]).fetchone()
        return r[0] if r else ""
    except:
        return ""

def get_hook_type(creative_id: str) -> str:
    try:
        r = conn.execute("""
            SELECT hook_type FROM creative_features 
            WHERE creative_id = ? AND hook_type IS NOT NULL AND hook_type != ''
            LIMIT 1
        """, [creative_id]).fetchone()
        return r[0] if r else ""
    except:
        return ""

# Helper: query by platform
def top_creatives(platform_pattern: str, label: str):
    # Combined from creative_performance + unified_state for creative_type
    rows = conn.execute(f"""
        SELECT 
            cp.creative_id,
            SUM(cp.spend) as total_spend,
            SUM(cp.install) as total_installs,
            SUM(cp.impression) as total_imp,
            SUM(cp.click) as total_clicks,
            CASE WHEN SUM(cp.spend) > 0 THEN SUM(cp.roas_d7 * cp.spend)/SUM(cp.spend) ELSE 0 END as avg_roas,
            CASE WHEN SUM(cp.install) > 0 THEN SUM(cp.spend) / SUM(cp.install) ELSE 0 END as cpi,
            MAX(cp.campaign_id) as campaign_id
        FROM creative_performance cp
        WHERE cp.project = 'P04 Witch'
          AND cp.campaign_id LIKE '{platform_pattern}'
        GROUP BY cp.creative_id
        HAVING SUM(cp.spend) > 0
        ORDER BY total_spend DESC
        LIMIT 15
    """).fetchall()

    print(f"\n{'='*100}")
    print(f"  {label} — Top 15 Creatives by Spend")
    print(f"{'='*100}")
    print(f"{'Creative ID':<20s} {'Type':<8s} {'Hook':<15s} {'Spend':>10s} {'Installs':>8s} {'ROAS':>8s} {'CPI':>8s} {'Impr':>10s} {'CTR':>8s}")
    print(f"{'-'*20} {'-'*8} {'-'*15} {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*8}")

    total_spend = 0
    total_installs = 0
    
    for r in rows:
        cid, spend, installs, imp, clicks, roas, cpi, camp = r
        ctype = get_creative_type(cid)
        hook = get_hook_type(cid)
        ctr = (clicks / imp * 100) if imp > 0 else 0
        total_spend += spend
        total_installs += installs
        
        print(f"{cid:<20s} {ctype:<8s} {hook:<15s} ${spend:>9,.0f} {installs:>8,} {roas:>8.3f} ${cpi:>7.2f} {imp:>10,} {ctr:>7.2f}%")

    print(f"{'-'*100}")
    print(f"{'TOTAL':<20s} {'':8s} {'':15s} ${total_spend:>9,.0f} {total_installs:>8,}")

    return rows


# ── Android ────────────────────────────────────────────────────
android_rows = top_creatives("P4-AND-%", "P04 Witch - ANDROID")

# ── iOS ────────────────────────────────────────────────────────
ios_rows = top_creatives("P4-IOS-%", "P04 Witch - iOS")

# ── Summary ────────────────────────────────────────────────────
print(f"\n\n{'='*100}")
print(f"  Summary: P04 Witch by Platform")
print(f"{'='*100}")

totals = conn.execute("""
    SELECT 
        CASE WHEN campaign_id LIKE 'P4-AND-%' THEN 'Android' 
             WHEN campaign_id LIKE 'P4-IOS-%' THEN 'iOS' 
             ELSE 'Other' END as platform,
        SUM(spend) as total_spend,
        SUM(install) as total_installs,
        COUNT(DISTINCT creative_id) as unique_creatives,
        CASE WHEN SUM(spend) > 0 THEN SUM(roas_d7 * spend)/SUM(spend) ELSE 0 END as avg_roas,
        CASE WHEN SUM(install) > 0 THEN SUM(spend) / SUM(install) ELSE 0 END as cpi
    FROM creative_performance
    WHERE project = 'P04 Witch'
    GROUP BY platform
    ORDER BY total_spend DESC
""").fetchall()

for t in totals:
    print(f"  {t[0]:10s} | ${t[1]:>10,.0f} | {t[2]:>8,} installs | {t[3]:>4} creatives | ROAS={t[4]:.3f} | CPI=${t[5]:.2f}")

# Also show image vs video breakdown
print(f"\n\n{'='*100}")
print(f"  Creative Type Breakdown (Image vs Video)")
print(f"{'='*100}")

# Get creative types from unified_state
type_rows = conn.execute("""
    SELECT 
        us.creative_type,
        COUNT(DISTINCT us.creative_id) as unique_creatives,
        SUM(cp.spend) as total_spend
    FROM unified_state us
    JOIN creative_performance cp ON us.creative_id = cp.creative_id
    WHERE cp.project = 'P04 Witch'
      AND us.creative_type IS NOT NULL
      AND us.creative_type != ''
    GROUP BY us.creative_type
    ORDER BY total_spend DESC
""").fetchall()

for t in type_rows:
    print(f"  {t[0]:10s} | ${t[2]:>10,.0f} | {t[1]:>4} unique creatives")

conn.close()