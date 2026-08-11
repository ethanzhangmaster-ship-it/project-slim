#!/usr/bin/env python3
"""多信号素材评分系统 — Multi-Signal Creative Scoring

不是漏斗，是并行三维评分：
  Creative Score  = f(CTR, IPM)          → 会不会被点
  Intent Score    = f(P(Purchase|Event))  → 像不像会买
  Revenue Score   = f(ROAS)              → 是否真赚钱

最终评分 = w1 * Creative + w2 * Intent + w3 * Revenue
→ 自动选 winner → 自动喂给 Lovart → 自动生成下一批

数据源:
  - DuckDB creative_performance (CTR, IPM, CPI, ROAS)
  - DuckDB app_events (P(Purchase|Event))
  - Lovart describe_image (视觉DNA)

用法:
  python scripts/score_creatives.py                    # 全量评分
  python scripts/score_creatives.py --project P04      # 按项目
  python scripts/score_creatives.py --top 10           # 输出 TOP 10
  python scripts/score_creatives.py --auto-select      # 自动选 winner → 输出 Lovart prompt
"""
from __future__ import annotations

import argparse, json, os, sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ============================================================================
# 评分权重 (可调)
# ============================================================================
WEIGHTS = {
    "creative": 0.20,   # 注意力: CTR + IPM
    "intent":   0.30,   # 意图: P(Purchase|Event)
    "revenue":  0.50,   # 收益: ROAS
}


@dataclass
class CreativeScore:
    creative_id: str
    creative_name: str = ""
    # 原始指标
    spend: float = 0.0
    installs: int = 0
    ctr: float = 0.0
    ipm: float = 0.0
    cpi: float = 0.0
    roas_d7: float = 0.0
    p_purchase_event: float = 0.0  # P(Purchase|Event)
    # 三维评分
    creative_score: float = 0.0
    intent_score: float = 0.0
    revenue_score: float = 0.0
    # 最终
    final_score: float = 0.0
    # 视觉DNA
    visual_dna: dict = field(default_factory=dict)
    # 元数据
    image_path: str = ""

    def to_dict(self) -> dict:
        return {
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "spend": self.spend, "installs": self.installs,
            "ctr": round(self.ctr, 2), "ipm": round(self.ipm, 2),
            "cpi": round(self.cpi, 2), "roas_d7": round(self.roas_d7, 4),
            "p_purchase_event": round(self.p_purchase_event, 4),
            "creative_score": round(self.creative_score, 4),
            "intent_score": round(self.intent_score, 4),
            "revenue_score": round(self.revenue_score, 4),
            "final_score": round(self.final_score, 4),
        }


def ensure_schema(db_path: Path):
    """建评分表"""
    conn = duckdb.connect(str(db_path), read_only=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS creative_scores (
            creative_id VARCHAR PRIMARY KEY,
            creative_name VARCHAR,
            project VARCHAR,
            spend DOUBLE, installs INTEGER,
            ctr DOUBLE, ipm DOUBLE, cpi DOUBLE, roas_d7 DOUBLE,
            p_purchase_event DOUBLE,
            creative_score DOUBLE, intent_score DOUBLE, revenue_score DOUBLE,
            final_score DOUBLE,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.close()


def load_performance_data(db_path: Path, project: str | None = None):
    """从 DuckDB 加载投放数据"""
    conn = duckdb.connect(str(db_path), read_only=True)

    proj_filter = ""
    params = []
    if project:
        proj_filter = "AND cp.project LIKE ?"
        params.append(f"%{project}%")

    rows = conn.execute(f"""
        SELECT 
            cp.creative_id,
            SUM(cp.spend) as spend,
            SUM(cp.install) as installs,
            SUM(cp.impression) as imp,
            SUM(cp.click) as clicks,
            CASE WHEN SUM(cp.impression)>0 THEN SUM(cp.click)*100.0/SUM(cp.impression) ELSE 0 END as ctr,
            CASE WHEN SUM(cp.impression)>0 THEN SUM(cp.install)*1000.0/SUM(cp.impression) ELSE 0 END as ipm,
            CASE WHEN SUM(cp.spend)>0 THEN SUM(cp.install)/SUM(cp.spend) ELSE 0 END as cpi_rate,
            CASE WHEN SUM(cp.spend)>0 AND SUM(cp.roas_d7)>0 
                 THEN SUM(cp.roas_d7*cp.spend)/SUM(cp.spend) ELSE 0 END as roas_d7
        FROM creative_performance cp
        WHERE cp.creative_id != '' {proj_filter}
        GROUP BY cp.creative_id
        HAVING SUM(cp.spend) >= 50 AND SUM(cp.install) >= 5
        ORDER BY spend DESC
    """, params).fetchall()

    conn.close()
    return rows


def load_event_data(db_path: Path):
    """从 Adjust API 拉取付费率数据
    
    返回 (event_data, adjust_data, global_pay_rate)
    """
    adjust_token = os.environ.get("ADJUST_API_TOKEN", "")
    adjust_data = {}
    global_pay_rate = 0.02  # fallback
    
    # 先建 DuckDB 连接（后面 Adjust API 和 event_data 都需要）
    conn = duckdb.connect(str(db_path), read_only=True)
    
    if adjust_token:
        import requests as _req, urllib3
        urllib3.disable_warnings()
            
            # 加载 ID 映射表
            id_map = {}
            try:
                map_rows = conn.execute("""
                    SELECT adjust_creative_id, duckdb_creative_id 
                    FROM creative_id_mapping 
                    WHERE duckdb_creative_id IS NOT NULL
                """).fetchall()
                id_map = {str(r[0]): str(r[1]) for r in map_rows}
            except Exception:
                pass  # 表可能不存在
            
            r = _req.get(
                'https://automate.adjust.com/reports-service/report',
                params={
                    'date_period': '2026-06-01:2026-06-30',
                    'dimensions': 'app,creative_id_network',
                    'metrics': 'installs,first_paying_users_d0,revenue',
                    'ad_spend_mode': 'network',
                },
                headers={'Authorization': f'Bearer {adjust_token}', 'Accept': 'application/json'},
                verify=False, timeout=30,
            )
            total_inst = 0
            total_payers = 0
            for row in r.json().get('rows', []):
                app = row.get('app', '')
                if 'P04' not in app:
                    continue
                adj_cid = str(row.get('creative_id_network', ''))
                inst = int(row.get('installs', 0))
                payers = int(row.get('first_paying_users_d0', 0))
                total_inst += inst
                total_payers += payers
                if not adj_cid or adj_cid == 'unknown' or inst < 3:
                    continue
                # 通过映射表转为 DuckDB creative_id
                db_cid = id_map.get(adj_cid, adj_cid)
                pay_rate = payers / inst if inst > 0 else 0
                # 如果已存在，累加（多个 Adjust ID 映射到同一个 DuckDB ID）
                if db_cid in adjust_data:
                    existing = adjust_data[db_cid]
                    existing['installs'] += inst
                    existing['payers'] += payers
                    existing['pay_rate'] = existing['payers'] / existing['installs'] if existing['installs'] > 0 else 0
                    existing['revenue'] += float(row.get('revenue', 0))
                else:
                    adjust_data[db_cid] = {
                        'installs': inst, 'payers': payers,
                        'pay_rate': pay_rate,
                        'revenue': float(row.get('revenue', 0)),
                    }
            if total_inst > 0:
                global_pay_rate = total_payers / total_inst

    event_data = {}
    tables = [r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name='app_events'"
    ).fetchall()]
    if tables:
        rows = conn.execute("""
            SELECT event_name, SUM(event_count), SUM(paying_users),
                   CASE WHEN SUM(event_count) > 0 THEN SUM(paying_users)*100.0/SUM(event_count) ELSE 0 END
            FROM app_events GROUP BY event_name
        """).fetchall()
        event_data = {r[0]: r[2] for r in rows}
    conn.close()
    
    return event_data, adjust_data, global_pay_rate


def compute_scores(
    perf_data: list,
    event_data: dict,
    adjust_data: dict,
    global_pay_rate: float = 0.02,
    local_images: dict | None = None,
) -> list[CreativeScore]:
    """计算三维评分
    
    Creative Score = f(CTR, IPM)
    Intent Score   = f(Pay Rate from Adjust)  
    Revenue Score  = f(ROAS)
    """
    if not perf_data:
        return []

    # 归一化基准 (中位数)
    all_ctr = [r[5] for r in perf_data if r[5] > 0]
    all_ipm = [r[6] for r in perf_data if r[6] > 0]
    all_roas = [r[8] for r in perf_data if r[8] > 0]
    all_cpi = [r[7] for r in perf_data if r[7] > 0]

    def med(vals): 
        s = sorted(vals)
        return s[len(s)//2] if s else 0.1

    ctr_med, ipm_med, roas_med, cpi_med = med(all_ctr), med(all_ipm), med(all_roas) or 0.05, med(all_cpi)
    
    # 全局付费率基准
    all_pay_rates = [a['pay_rate'] for a in adjust_data.values() if a['pay_rate'] > 0]
    pay_rate_benchmark = med(all_pay_rates) if all_pay_rates else 0.02

    results = []
    for r in perf_data:
        cid, spend, installs, imp, clicks, ctr, ipm, cpi_rate, roas = r
        cid_str = str(cid)

        # Creative Score: CTR 50% + IPM 50%
        ctr_s = min(1.0, ctr / max(ctr_med, 1e-6)) if ctr_med > 0 else 0.5
        ipm_s = min(1.0, ipm / max(ipm_med, 1e-6)) if ipm_med > 0 else 0.5
        creative_s = ctr_s * 0.5 + ipm_s * 0.5

        # Intent Score: 用 Adjust 真实付费率
        # 18位 creative_id 可以跟 Adjust 直接匹配
        adj = adjust_data.get(cid_str, {})
        pay_rate = adj.get('pay_rate', 0)
        if pay_rate > 0:
            intent_s = min(1.0, pay_rate / max(pay_rate_benchmark, 0.005))
        elif len(cid_str) == 18:
            # 18位 ID 但在 Adjust 中没匹配到 → 该 creative 0 付费
            intent_s = 0.1
        elif event_data:
            p_purchase = max(event_data.values()) if event_data else 0.03
            intent_s = min(1.0, p_purchase / 0.15)
        else:
            # 16位 ID fallback: 用 P04 全局付费率
            intent_s = min(1.0, global_pay_rate / max(pay_rate_benchmark, 0.005))

        # Revenue Score: ROAS
        rev_s = min(1.0, roas / max(roas_med, 1e-6)) if roas > 0 and roas_med > 0 else 0.2

        # 最终 = 加权
        final = (
            creative_s * WEIGHTS["creative"] +
            intent_s * WEIGHTS["intent"] +
            rev_s * WEIGHTS["revenue"]
        )

        cs = CreativeScore(
            creative_id=cid_str,
            spend=spend, installs=installs,
            ctr=ctr, ipm=ipm, cpi=1/cpi_rate if cpi_rate > 0 else 0,
            roas_d7=roas, p_purchase_event=pay_rate,
            creative_score=creative_s, intent_score=intent_s, revenue_score=rev_s,
            final_score=final,
            image_path=local_images.get(cid_str, "") if local_images else "",
        )
        results.append(cs)

    results.sort(key=lambda x: x.final_score, reverse=True)
    return results


def save_scores(db_path: Path, scores: list[CreativeScore], project: str = "P04"):
    """保存评分到 DuckDB"""
    conn = duckdb.connect(str(db_path), read_only=False)
    for s in scores:
        conn.execute("""
            INSERT OR REPLACE INTO creative_scores 
            (creative_id, creative_name, project, spend, installs, ctr, ipm, cpi, roas_d7,
             p_purchase_event, creative_score, intent_score, revenue_score, final_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            s.creative_id, s.creative_name, project,
            s.spend, s.installs, s.ctr, s.ipm, s.cpi, s.roas_d7,
            s.p_purchase_event, s.creative_score, s.intent_score, s.revenue_score, s.final_score,
        ])
    conn.close()


def auto_select_winners(scores: list[CreativeScore], top_n: int = 5):
    """自动选出 winner, 生成 Lovart prompt 建议"""
    winners = [s for s in scores[:top_n] if s.final_score > 0.3]

    print(f"\n{'='*70}")
    print(f"  🏆 自动选出 TOP {len(winners)} Winner")
    print(f"{'='*70}")

    for i, w in enumerate(winners):
        print(f"\n  #{i+1} creative_id={w.creative_id}")
        print(f"    综合: {w.final_score:.4f} (C={w.creative_score:.4f} I={w.intent_score:.4f} R={w.revenue_score:.4f})")
        print(f"    数据: spend=${w.spend:,.0f} installs={w.installs:,} CPI=${w.cpi:.2f} CTR={w.ctr:.1f}% ROAS={w.roas_d7:.4f}")

    # 生成 Lovart prompt 建议
    if winners:
        best = winners[0]
        print(f"\n  📝 Lovart 出图建议 (基于 Winner #{1}):")
        print(f"    参考图: {best.image_path or '(需下载)'}")
        print(f"    策略: 保留赢家核心视觉 → 4 种变体策略")

    return winners


def main():
    parser = argparse.ArgumentParser(description="多信号素材评分系统")
    parser.add_argument("--project", type=str, default="P04", help="项目")
    parser.add_argument("--top", type=int, default=20, help="显示 TOP N")
    parser.add_argument("--auto-select", action="store_true", help="自动选 winner + 输出 Lovart prompt")
    parser.add_argument("--weights", type=str, default=None, help="自定义权重 (JSON: {\"creative\":0.2,\"intent\":0.3,\"revenue\":0.5})")
    args = parser.parse_args()

    if args.weights:
        global WEIGHTS
        WEIGHTS.update(json.loads(args.weights))

    db_path = ROOT / "db" / "facebook_performance.duckdb"
    ensure_schema(db_path)

    print("=" * 70)
    print(f"  多信号素材评分系统 — {args.project}")
    print(f"  权重: C={WEIGHTS['creative']} I={WEIGHTS['intent']} R={WEIGHTS['revenue']}")
    print("=" * 70)

    # 1. 加载数据
    perf = load_performance_data(db_path, args.project)
    event_data, adjust_data, global_pay_rate = load_event_data(db_path)

    # 2. 加载本地图片映射
    local_images = {}
    img_dir = Path(r"D:\ethan\Documents\市场会议\output\facebook_top_creatives\P04")
    if img_dir.exists():
        import re
        for f in img_dir.rglob("*.png"):
            match = re.search(r"_(\d{10,25})\.png$", f.name)
            if match:
                local_images[match.group(1)] = str(f)

    print(f"\n  投放数据: {len(perf)} 素材")
    print(f"  Adjust 付费数据: {len(adjust_data)} 素材 (P04 全局付费率: {global_pay_rate*100:.2f}%)")
    print(f"  本地图片: {len(local_images)} 张")

    # 3. 计算评分
    scores = compute_scores(perf, event_data, adjust_data, global_pay_rate, local_images)
    save_scores(db_path, scores, args.project)

    # 4. 输出
    print(f"\n  {'#':<3} {'creative_id':<20} {'Final':>7} {'C':>6} {'I':>6} {'R':>6} {'Spend':>8} {'CPI':>6} {'ROAS':>6}")
    print(f"  {'-'*3} {'-'*20} {'-'*7} {'-'*6} {'-'*6} {'-'*6} {'-'*8} {'-'*6} {'-'*6}")
    for i, s in enumerate(scores[:args.top]):
        print(f"  {i+1:<3} {s.creative_id[:19]:<20} {s.final_score:7.4f} {s.creative_score:6.4f} {s.intent_score:6.4f} {s.revenue_score:6.4f} ${s.spend:>7,.0f} ${s.cpi:>5.2f} {s.roas_d7:6.4f}")

    # 5. 自动选择
    if args.auto_select:
        auto_select_winners(scores)

    print(f"\n  ✅ 评分已保存到 DuckDB creative_scores 表")
    print(f"  📊 下次运行: python scripts/score_creatives.py --auto-select")


if __name__ == "__main__":
    main()
