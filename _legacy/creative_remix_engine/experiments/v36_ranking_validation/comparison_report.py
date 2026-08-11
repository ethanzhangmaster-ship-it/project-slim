"""Comparison Report — 生成 A/B 对比报告"""
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime


class ComparisonReport:
    """A/B 对比报告生成器"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, results: List[Dict]) -> Dict:
        """生成完整对比报告"""
        baseline_scores = []
        ranking_scores = []
        pair_details = []

        for r in results:
            b = r.get("baseline_analysis", {})
            rk = r.get("ranking_analysis", {})

            b_scores = {
                "hook": b.get("hook_score", 0),
                "retention": b.get("retention_score", 0),
                "gameplay": b.get("gameplay_clarity", 0),
                "reward": b.get("reward_density", 0),
                "overall": b.get("overall_score", 0),
            }
            r_scores = {
                "hook": rk.get("hook_score", 0),
                "retention": rk.get("retention_score", 0),
                "gameplay": rk.get("gameplay_clarity", 0),
                "reward": rk.get("reward_density", 0),
                "overall": rk.get("overall_score", 0),
            }

            baseline_scores.append(b_scores)
            ranking_scores.append(r_scores)

            pair_details.append({
                "pair_id": r["pair_id"],
                "story_type": r["story_type"],
                "baseline": b_scores,
                "ranking": r_scores,
                "improvement": {
                    "hook": round(r_scores["hook"] - b_scores["hook"], 1),
                    "retention": round(r_scores["retention"] - b_scores["retention"], 1),
                    "gameplay": round(r_scores["gameplay"] - b_scores["gameplay"], 1),
                    "reward": round(r_scores["reward"] - b_scores["reward"], 1),
                    "overall": round(r_scores["overall"] - b_scores["overall"], 1),
                },
            })

        # 统计
        def avg(scores, key):
            return round(sum(s[key] for s in scores) / len(scores), 1) if scores else 0

        summary = {
            "total_pairs": len(results),
            "baseline_avg": {
                "hook": avg(baseline_scores, "hook"),
                "retention": avg(baseline_scores, "retention"),
                "gameplay": avg(baseline_scores, "gameplay"),
                "reward": avg(baseline_scores, "reward"),
                "overall": avg(baseline_scores, "overall"),
            },
            "ranking_avg": {
                "hook": avg(ranking_scores, "hook"),
                "retention": avg(ranking_scores, "retention"),
                "gameplay": avg(ranking_scores, "gameplay"),
                "reward": avg(ranking_scores, "reward"),
                "overall": avg(ranking_scores, "overall"),
            },
        }

        # 提升百分比
        for key in ["hook", "retention", "gameplay", "reward", "overall"]:
            b = summary["baseline_avg"][key]
            r = summary["ranking_avg"][key]
            if b > 0:
                summary[f"{key}_improvement_pct"] = round((r - b) / b * 100, 1)
            else:
                summary[f"{key}_improvement_pct"] = 0

        # 选出 TOP 3 Winner（按 Improvement 排序）
        sorted_by_improvement = sorted(pair_details, key=lambda x: x["improvement"]["overall"], reverse=True)
        top3 = sorted_by_improvement[:3]

        report = {
            "experiment": "V3.6 Ranking Driven Video Generation Validation",
            "generated_at": datetime.now().isoformat(),
            "total_pairs": len(results),
            "summary": summary,
            "pair_details": pair_details,
            "top3_winners": [
                {
                    "rank": i + 1,
                    "pair_id": w["pair_id"],
                    "story_type": w["story_type"],
                    "overall_score": w["ranking"]["overall"],
                    "improvement_over_baseline": w["improvement"]["overall"],
                }
                for i, w in enumerate(top3)
            ],
        }

        # 保存 JSON
        json_path = self.output_dir / "v36_comparison_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 生成 HTML
        html_path = self._build_html(report)

        return {
            "json_path": str(json_path),
            "html_path": str(html_path),
            "report": report,
        }

    def _build_html(self, report: Dict) -> Path:
        """构建 HTML 报告"""
        s = report["summary"]

        css = """
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }
            h1 { color: #1a1a2e; }
            .summary { background: white; padding: 24px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 20px 0; }
            .metric { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #eee; }
            .metric:last-child { border-bottom: none; }
            .label { font-weight: 500; color: #555; }
            .baseline { color: #e94560; font-weight: bold; }
            .ranking { color: #16c79a; font-weight: bold; }
            .improvement { color: #0f3460; font-weight: bold; }
            .winner { background: #fff3cd; padding: 16px; border-radius: 8px; margin: 12px 0; }
            table { width: 100%; border-collapse: collapse; background: white; margin: 20px 0; }
            th { background: #16213e; color: white; padding: 12px; }
            td { padding: 10px 12px; border-bottom: 1px solid #eee; text-align: center; }
            .up { color: #16c79a; }
            .down { color: #e94560; }
        </style>
        """

        # Summary 表格
        rows = []
        for key in ["hook", "retention", "gameplay", "reward", "overall"]:
            b = s["baseline_avg"][key]
            r = s["ranking_avg"][key]
            pct = s.get(f"{key}_improvement_pct", 0)
            cls = "up" if pct > 0 else "down"
            rows.append(f"""
                <tr>
                    <td>{key.replace('_', ' ').title()}</td>
                    <td class="baseline">{b}</td>
                    <td class="ranking">{r}</td>
                    <td class="{cls}">{pct:+.1f}%</td>
                </tr>
            """)

        # Pair 详情
        pair_rows = []
        for p in report["pair_details"]:
            imp = p["improvement"]["overall"]
            cls = "up" if imp > 0 else "down"
            pair_rows.append(f"""
                <tr>
                    <td>#{p['pair_id']}</td>
                    <td>{p['story_type']}</td>
                    <td>{p['baseline']['overall']}</td>
                    <td>{p['ranking']['overall']}</td>
                    <td class="{cls}">{imp:+.1f}</td>
                </tr>
            """)

        # Winners
        winner_html = ""
        for w in report["top3_winners"]:
            winner_html += f"""
            <div class="winner">
                <strong>#{w['rank']} Winner</strong> — Pair {w['pair_id']} ({w['story_type']})<br>
                Overall Score: <span class="ranking">{w['overall_score']}</span> |
                Improvement: <span class="improvement">+{w['improvement_over_baseline']}</span>
            </div>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>V3.6 A/B Validation Report</title>
{css}
</head>
<body>
<h1>V3.6 Ranking Driven Video Generation — A/B Validation Report</h1>
<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<div class="summary">
    <h2>Summary</h2>
    <div class="metric">
        <span class="label">Total Pairs</span>
        <span>{report['total_pairs']}</span>
    </div>
    <table>
        <thead>
            <tr><th>Metric</th><th class="baseline">Baseline (V3.4)</th><th class="ranking">Ranking (V3.5)</th><th>Improvement</th></tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
</div>

<div class="summary">
    <h2>TOP 3 Winners</h2>
    {winner_html}
</div>

<div class="summary">
    <h2>Pair-by-Pair Comparison</h2>
    <table>
        <thead>
            <tr><th>Pair</th><th>Story</th><th class="baseline">Baseline</th><th class="ranking">Ranking</th><th>Delta</th></tr>
        </thead>
        <tbody>{''.join(pair_rows)}</tbody>
    </table>
</div>

</body>
</html>"""

        path = self.output_dir / "v36_comparison_report.html"
        path.write_text(html, encoding="utf-8")
        return path
