"""Report Generator — 生成 HTML 排名报告"""
import json
import base64
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class ReportGenerator:
    """HTML 报告生成器"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, ranking_data: Dict, db_data: List[dict]) -> Path:
        """生成 HTML 报告"""
        html = self._build_html(ranking_data)
        path = self.output_dir / "visual_ranking_report.html"
        path.write_text(html, encoding="utf-8")
        return path

    def _build_html(self, data: Dict) -> str:
        """构建 HTML 内容"""
        sections = []

        # Header
        sections.append(f"""
        <h1>Visual Intelligence Ranking Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        <p>Total Videos Analyzed: {data.get('total', 0)}</p>
        """)

        # Top Hook
        sections.append(self._build_table("TOP 20 Hook", data.get("top_hook", []),
                                          ["hook_score", "motion_score", "impact_score", "dna_score", "final_score"]))

        # Top Gameplay
        sections.append(self._build_table("TOP 20 Gameplay", data.get("top_gameplay", []),
                                          ["gameplay_score", "motion_score", "impact_score", "gameplay_type", "final_score"]))

        # Top Reward
        sections.append(self._build_table("TOP 20 Reward", data.get("top_reward", []),
                                          ["reward_score", "impact_score", "reward_types", "dna_score", "final_score"]))

        # Top CTA
        sections.append(self._build_table("TOP 20 CTA", data.get("top_cta", []),
                                          ["hook_score", "impact_score", "reward_score", "final_score"]))

        # Top Overall
        sections.append(self._build_table("TOP 50 Overall", data.get("top_overall", []),
                                          ["final_score", "motion_score", "impact_score", "gameplay_score", "hook_score", "reward_score", "dna_score"]))

        css = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }
            h1 { color: #1a1a2e; }
            h2 { color: #16213e; margin-top: 40px; border-bottom: 2px solid #e94560; padding-bottom: 8px; }
            table { width: 100%; border-collapse: collapse; background: white; margin: 16px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            th { background: #16213e; color: white; padding: 12px; text-align: left; font-size: 13px; }
            td { padding: 10px 12px; border-bottom: 1px solid #eee; font-size: 13px; }
            tr:hover { background: #f8f9fa; }
            .score { font-weight: bold; color: #e94560; }
            .tag { display: inline-block; background: #e94560; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 4px; }
            .tag-blue { background: #0f3460; }
            .tag-green { background: #16c79a; }
            .rank { font-weight: bold; color: #16213e; font-size: 16px; }
        </style>
        """

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Visual Intelligence Ranking Report V3.5</title>
{css}
</head>
<body>
{''.join(sections)}
</body>
</html>"""

    def _build_table(self, title: str, items: List[dict], cols: List[str]) -> str:
        rows = []
        for i, item in enumerate(items, 1):
            cells = [f'<td class="rank">#{i}</td>', f'<td>{item.get("video_name", "")[:50]}</td>']
            for c in cols:
                val = item.get(c, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                if "score" in c:
                    cells.append(f'<td class="score">{val}</td>')
                else:
                    cells.append(f'<td>{val}</td>')

            # Tags
            tags = item.get("tags", [])
            tag_html = "".join(f'<span class="tag">{t}</span>' for t in tags[:3])
            cells.append(f'<td>{tag_html}</td>')

            rows.append("<tr>" + "".join(cells) + "</tr>")

        header_cols = ["Rank", "Video Name"] + [c.replace("_", " ").title() for c in cols] + ["Tags"]
        header = "".join(f"<th>{c}</th>" for c in header_cols)

        return f"""
        <h2>{title}</h2>
        <table>
            <thead><tr>{header}</tr></thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
        """
