"""Creative Intelligence Dashboard

可视化展示Feature排名/Winner Gallery/Knowledge Graph/Prediction Accuracy。

输出HTML Dashboard,支持按项目/平台/时间过滤。

Usage:
    from market_ops.creative_intelligence.dashboard import CreativeDashboard

    dash = CreativeDashboard()
    dash.generate(project="P04")
    # → 打开 output/creative_intelligence/dashboard.html
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.creative_intelligence.feature_db import FeatureDatabase
from market_ops.creative_intelligence.knowledge_base import CreativeKnowledgeBase

_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = _ROOT / "output" / "creative_intelligence"


class CreativeDashboard:
    """Creative Intelligence 可视化Dashboard"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db = FeatureDatabase(db_path)
        self._kb = CreativeKnowledgeBase()

    def generate(self, project: str | None = None) -> Path:
        """生成Dashboard HTML"""
        print(f"[Dashboard] 生成中... project={project}")

        # 收集数据
        stats = self._db.get_project_stats()
        kb_summary = self._kb.get_summary()
        top_rules = self._kb.get_top_rules(project=project, effect="positive", limit=10)
        avoid_rules = self._kb.get_avoid_rules(project=project, limit=5)

        # Top/Loser performers
        top_performers = self._db.query_features_with_performance(
            project=project, min_spend=100, limit=10,
        )
        loser_performers = sorted(
            self._db.query_features_with_performance(
                project=project, min_spend=50, limit=100,
            ),
            key=lambda x: x.get("ctr", 0),
        )[:10]

        html = self._build_html(
            project=project,
            stats=stats,
            kb_summary=kb_summary,
            top_rules=top_rules,
            avoid_rules=avoid_rules,
            top_performers=top_performers,
            loser_performers=loser_performers,
        )

        out_file = OUTPUT_DIR / f"dashboard_{project or 'all'}.html"
        out_file.write_text(html, encoding="utf-8")
        print(f"[Dashboard] 已生成: {out_file}")
        return out_file

    def _build_html(self, **data) -> str:
        project = data["project"] or "All"
        stats = data["stats"]
        kb = data["kb_summary"]
        top_rules = data["top_rules"]
        avoid_rules = data["avoid_rules"]
        top_performers = data["top_performers"]
        loser_performers = data["loser_performers"]

        # Feature排名表
        top_rules_html = ""
        for r in top_rules:
            top_rules_html += f"""
            <tr>
                <td>{r['pattern']}</td>
                <td>{r['metric']}</td>
                <td class="positive">+{r['lift_pct']}%</td>
                <td>{r['confidence']:.0%}</td>
                <td>{r['sample_count']}</td>
                <td>{r['source']}</td>
            </tr>"""

        avoid_html = ""
        for r in avoid_rules:
            avoid_html += f"""
            <tr>
                <td>{r['pattern']}</td>
                <td class="negative">{r['lift_pct']}%</td>
                <td>{r['confidence']:.0%}</td>
                <td>{r['sample_count']}</td>
            </tr>"""

        # Winner Gallery
        winner_html = ""
        for p in top_performers[:6]:
            img_path = p.get("image_path", "")
            if img_path:
                rel_path = img_path.replace("\\", "/").replace("output/", "../")
                winner_html += f"""
                <div class="gallery-card">
                    <img src="{rel_path}" loading="lazy" onerror="this.style.display='none'">
                    <div class="gallery-info">
                        <div class="gallery-name">{p.get('creative_id','')}</div>
                        <div>CTR {p.get('ctr',0)}% | CPI ${p.get('cpi',0)} | ${p.get('spend',0):.0f}</div>
                    </div>
                </div>"""

        # Loser Gallery
        loser_html = ""
        for p in loser_performers[:6]:
            img_path = p.get("image_path", "")
            if img_path:
                rel_path = img_path.replace("\\", "/").replace("output/", "../")
                loser_html += f"""
                <div class="gallery-card loser">
                    <img src="{rel_path}" loading="lazy" onerror="this.style.display='none'">
                    <div class="gallery-info">
                        <div class="gallery-name">{p.get('creative_id','')}</div>
                        <div>CTR {p.get('ctr',0)}% | ${p.get('spend',0):.0f}</div>
                    </div>
                </div>"""

        # 项目统计
        stats_html = ""
        for s in stats:
            stats_html += f"""
            <div class="stat-card">
                <h3>{s['project']}</h3>
                <div class="stat-num">{s['count']}</div>
                <div>Features</div>
                <div class="stat-sub">{s['hook_types']} hooks | {s['colors']} colors</div>
            </div>"""

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Creative Intelligence Dashboard - {project}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; padding: 20px; }}
header {{ background: linear-gradient(135deg, #1a1f3a, #0f1117); padding: 20px; border-radius: 12px; margin-bottom: 20px; }}
h1 {{ color: #FFD700; font-size: 24px; }}
.subtitle {{ color: #888; margin-top: 5px; }}
.section {{ background: #1a1d27; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
.section h2 {{ color: #00CED1; margin-bottom: 15px; font-size: 18px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
.stats-row {{ display: flex; gap: 15px; flex-wrap: wrap; }}
.stat-card {{ background: #222632; padding: 15px; border-radius: 8px; text-align: center; min-width: 120px; }}
.stat-card h3 {{ color: #FFD700; font-size: 14px; }}
.stat-num {{ font-size: 28px; color: #00CED1; margin: 5px 0; }}
.stat-sub {{ font-size: 11px; color: #666; margin-top: 5px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; padding: 8px; background: #222632; color: #00CED1; font-size: 12px; }}
td {{ padding: 8px; border-bottom: 1px solid #2a2e3a; font-size: 13px; }}
.positive {{ color: #4CAF50; font-weight: bold; }}
.negative {{ color: #f44336; font-weight: bold; }}
.gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }}
.gallery-card {{ background: #222632; border-radius: 8px; overflow: hidden; }}
.gallery-card.loser {{ opacity: 0.6; }}
.gallery-card img {{ width: 100%; height: 250px; object-fit: cover; display: block; }}
.gallery-info {{ padding: 8px; }}
.gallery-name {{ color: #FFD700; font-size: 12px; margin-bottom: 3px; word-break: break-all; }}
.gallery-info div {{ font-size: 11px; color: #888; }}
.kb-summary {{ display: flex; gap: 20px; flex-wrap: wrap; }}
.kb-item {{ background: #222632; padding: 10px 15px; border-radius: 6px; }}
.kb-label {{ color: #888; font-size: 11px; }}
.kb-value {{ color: #00CED1; font-size: 18px; font-weight: bold; }}
footer {{ text-align: center; padding: 20px; color: #555; font-size: 12px; }}
</style>
</head>
<body>
<header>
    <h1>Creative Intelligence Dashboard</h1>
    <div class="subtitle">Project: {project} | Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</header>

<div class="section">
    <h2>Project Overview</h2>
    <div class="stats-row">{stats_html}</div>
</div>

<div class="section">
    <h2>Knowledge Base</h2>
    <div class="kb-summary">
        <div class="kb-item"><div class="kb-label">Total Rules</div><div class="kb-value">{kb['total_rules']}</div></div>
        <div class="kb-item"><div class="kb-label">Active Rules</div><div class="kb-value">{kb['active_rules']}</div></div>
        <div class="kb-item"><div class="kb-label">Positive</div><div class="kb-value">{kb['by_effect'].get('positive',0)}</div></div>
        <div class="kb-item"><div class="kb-label">Negative</div><div class="kb-value">{kb['by_effect'].get('negative',0)}</div></div>
    </div>
</div>

<div class="section">
    <h2>Top Feature Rules (CTR)</h2>
    <table>
        <tr><th>Pattern</th><th>Metric</th><th>Lift</th><th>Confidence</th><th>Samples</th><th>Source</th></tr>
        {top_rules_html}
    </table>
</div>

<div class="section">
    <h2>Avoid Features</h2>
    <table>
        <tr><th>Pattern</th><th>Lift</th><th>Confidence</th><th>Samples</th></tr>
        {avoid_html}
    </table>
</div>

<div class="section">
    <h2>Winner Gallery (Top by Spend)</h2>
    <div class="gallery">{winner_html}</div>
</div>

<div class="section">
    <h2>Loser Gallery (Lowest CTR)</h2>
    <div class="gallery">{loser_html}</div>
</div>

<footer>
    Creative Intelligence Layer V1 | Generated by Market Ops System
</footer>
</body>
</html>"""

    def close(self) -> None:
        self._db.close()
