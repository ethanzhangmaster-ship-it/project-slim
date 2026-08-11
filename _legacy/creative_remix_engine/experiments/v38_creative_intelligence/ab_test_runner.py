"""V3.8 Creative Intelligence — A/B Test Report Generator

生成 v38_creative_intelligence_report.html 报告
包含：Winner Archetype、Top Creative DNA、A/B Result 等
"""
import json
from pathlib import Path
from typing import Dict, List


REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>V3.8 Creative Intelligence Calibration Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f7fa;
            color: #1a1a2e;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 30px;
        }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header .subtitle {{ opacity: 0.9; font-size: 16px; }}
        .header .timestamp {{ opacity: 0.7; font-size: 14px; margin-top: 10px; }}

        .card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        .card h2 {{
            font-size: 20px;
            margin-bottom: 16px;
            color: #2d3748;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
        }}
        .card h3 {{
            font-size: 16px;
            margin: 16px 0 12px;
            color: #4a5568;
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        .metric-box {{
            background: #f7fafc;
            border-radius: 10px;
            padding: 18px;
            text-align: center;
        }}
        .metric-box .label {{
            font-size: 13px;
            color: #718096;
            margin-bottom: 6px;
        }}
        .metric-box .value {{
            font-size: 28px;
            font-weight: 700;
            color: #2d3748;
        }}
        .metric-box .change {{
            font-size: 13px;
            margin-top: 4px;
        }}
        .change.up {{ color: #48bb78; }}
        .change.down {{ color: #f56565; }}

        .ab-comparison {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }}
        .ab-group {{
            padding: 20px;
            border-radius: 10px;
            background: #f7fafc;
        }}
        .ab-group.baseline {{ border-left: 4px solid #a0aec0; }}
        .ab-group.variant {{ border-left: 4px solid #667eea; }}
        .ab-group .group-title {{
            font-weight: 600;
            margin-bottom: 12px;
            font-size: 16px;
        }}

        .grade-bars {{ margin: 16px 0; }}
        .grade-bar {{
            display: flex;
            align-items: center;
            margin: 8px 0;
        }}
        .grade-label {{
            width: 60px;
            font-weight: 600;
            font-size: 14px;
        }}
        .grade-track {{
            flex: 1;
            height: 24px;
            background: #edf2f7;
            border-radius: 12px;
            overflow: hidden;
        }}
        .grade-fill {{
            height: 100%;
            border-radius: 12px;
            transition: width 0.3s;
        }}
        .grade-splus {{ background: linear-gradient(90deg, #f6e05e, #ecc94b); }}
        .grade-s {{ background: linear-gradient(90deg, #68d391, #48bb78); }}
        .grade-a {{ background: linear-gradient(90deg, #63b3ed, #4299e1); }}
        .grade-b {{ background: linear-gradient(90deg, #b794f4, #9f7aea); }}
        .grade-reject {{ background: linear-gradient(90deg, #fc8181, #f56565); }}
        .grade-count {{
            width: 40px;
            text-align: right;
            font-size: 14px;
            color: #4a5568;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
            font-size: 14px;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: #f7fafc;
            font-weight: 600;
            color: #4a5568;
        }}
        tr:hover {{ background: #f7fafc; }}

        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-splus {{ background: #fefcbf; color: #975a16; }}
        .badge-s {{ background: #c6f6d5; color: #276749; }}
        .badge-a {{ background: #bee3f8; color: #2a4365; }}
        .badge-b {{ background: #e9d8fd; color: #553c9a; }}
        .badge-reject {{ background: #fed7d7; color: #c53030; }}

        .archetype-card {{
            background: #f7fafc;
            border-radius: 10px;
            padding: 16px;
            margin: 10px 0;
        }}
        .archetype-name {{
            font-weight: 600;
            font-size: 15px;
            color: #2d3748;
            margin-bottom: 6px;
        }}
        .archetype-metrics {{
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: #4a5568;
        }}
        .archetype-features {{
            margin-top: 8px;
            font-size: 12px;
            color: #718096;
        }}

        .verdict {{
            text-align: center;
            padding: 30px;
            border-radius: 12px;
            margin: 20px 0;
        }}
        .verdict.pass {{
            background: linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%);
            color: #22543d;
        }}
        .verdict.fail {{
            background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%);
            color: #742a2a;
        }}
        .verdict h2 {{ font-size: 28px; margin-bottom: 8px; }}
        .verdict p {{ font-size: 16px; opacity: 0.9; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>V3.8 Creative Intelligence Calibration</h1>
            <div class="subtitle">从视觉质量 → 买量价值 — A/B Test 报告</div>
            <div class="timestamp">{timestamp}</div>
        </div>

        <div class="verdict {verdict_class}">
            <h2>{verdict_title}</h2>
            <p>{verdict_text}</p>
        </div>

        <div class="card">
            <h2>📊 A/B Test 核心指标</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="label">Baseline Ad Value</div>
                    <div class="value">{baseline_value}</div>
                    <div class="change">V3.4 Visual Quality</div>
                </div>
                <div class="metric-box">
                    <div class="label">Variant Ad Value</div>
                    <div class="value">{variant_value}</div>
                    <div class="change up">V3.8 Buying Score</div>
                </div>
                <div class="metric-box">
                    <div class="label">提升幅度</div>
                    <div class="value">{improvement_pct}%</div>
                    <div class="change up">绝对提升 {improvement_abs}</div>
                </div>
                <div class="metric-box">
                    <div class="label">目标 (≥20%)</div>
                    <div class="value">{target_status}</div>
                    <div class="change">{target_detail}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📈 Performance Grade 分布</h2>
            <div class="ab-comparison">
                <div class="ab-group baseline">
                    <div class="group-title">Baseline (V3.4)</div>
                    {baseline_grades_html}
                </div>
                <div class="ab-group variant">
                    <div class="group-title">Variant (V3.8)</div>
                    {variant_grades_html}
                </div>
            </div>
        </div>

        <div class="card">
            <h2>🏆 Top 10 Variant Creative DNA</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Video Name</th>
                        <th>Buying Score</th>
                        <th>Grade</th>
                        <th>Archetype</th>
                        <th>Pred. CTR</th>
                        <th>Pred. CPI</th>
                    </tr>
                </thead>
                <tbody>
                    {top_variant_rows}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>🧬 Performance Archetypes</h2>
            {archetypes_html}
        </div>

        <div class="card">
            <h2>💡 Winner DNA 模式洞察</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="label">Top Hook Type</div>
                    <div class="value">{top_hook}</div>
                    <div class="change">最常见开场类型</div>
                </div>
                <div class="metric-box">
                    <div class="label">Top Subject</div>
                    <div class="value">{top_subject}</div>
                    <div class="change">最常见主体</div>
                </div>
                <div class="metric-box">
                    <div class="label">Top Action</div>
                    <div class="value">{top_action}</div>
                    <div class="change">最常见玩法</div>
                </div>
                <div class="metric-box">
                    <div class="label">Avg Archetype Sim</div>
                    <div class="value">{avg_arch_sim}%</div>
                    <div class="change">原型相似度</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📋 实验配置</h2>
            <table>
                <tr><th>项目</th><th>详情</th></tr>
                <tr><td>实验名称</td><td>V3.8 Creative Intelligence Calibration</td></tr>
                <tr><td>素材池大小</td><td>{pool_size} videos</td></tr>
                <tr><td>每组样本数</td><td>{n_per_group}</td></tr>
                <tr><td>Baseline 方法</td><td>V3.4 Shot Selector (Visual Quality)</td></tr>
                <tr><td>Variant 方法</td><td>V3.8 Winner DNA Ranking (Buying Score + Performance Grade)</td></tr>
                <tr><td>评估维度</td><td>Hook×25% + Gameplay×25% + Reward×20% + Novelty×15% + Emotion×10% + CTA×5% + Winner Bonus</td></tr>
            </table>
        </div>

        <div class="card">
            <h2>🎯 V3.8 核心升级点</h2>
            <ul style="padding-left: 20px; line-height: 2;">
                <li><strong>Buying Score</strong>：从视觉质量评分转向买量价值评分，直接预测 CTR/CPI/ROI</li>
                <li><strong>Winner DNA Database</strong>：建立真实买量 Winner 数据库，持续学习高绩效模式</li>
                <li><strong>Performance Archetype</strong>：发现高绩效创意原型（Dragon Evolution, Rescue Story 等）</li>
                <li><strong>Performance Grade</strong>：S+/S/A/B/Reject 五级买量价值分级</li>
                <li><strong>Smart Mutation</strong>：基于 Winner DNA 指导的定向变异，提升成功率</li>
                <li><strong>UA Feedback Loop</strong>：买量数据自动反馈，模型持续优化</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""


class V38ReportGenerator:
    """V3.8 报告生成器"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, ab_result: dict) -> dict:
        """生成 HTML 报告"""
        improvement = ab_result["improvement"]
        baseline = ab_result["baseline"]
        variant = ab_result["variant"]

        # Verdict
        if improvement["target_20pct_met"]:
            verdict_class = "pass"
            verdict_title = "✅ A/B Test 通过"
            verdict_text = f"V3.8 Winner DNA Ranking 相比 V3.4 提升 {improvement['improvement_percentage']:.1f}%，达到 20% 目标"
        else:
            verdict_class = "fail"
            verdict_title = "⚠️ 未达目标"
            verdict_text = f"提升 {improvement['improvement_percentage']:.1f}%，距离 20% 目标还有差距"

        # Grade bars
        baseline_grades_html = self._render_grade_bars(baseline["grades"])
        variant_grades_html = self._render_grade_bars(variant["grades"])

        # Top variant rows
        top_variant_rows = self._render_top_table(variant["ad_value"]["top_list"])

        # Archetypes
        archetypes_html = self._render_archetypes(ab_result.get("archetype_ranking", []))

        # Winner patterns
        patterns = variant.get("winner_patterns", [])
        top_hook = self._most_common(patterns, "hook_type")
        top_subject = self._most_common(patterns, "subject")
        top_action = self._most_common(patterns, "action")
        avg_arch_sim = variant.get("archetypes", {}).get("avg_archetype_similarity", 0)

        html = REPORT_TEMPLATE.format(
            timestamp=ab_result.get("timestamp", ""),
            verdict_class=verdict_class,
            verdict_title=verdict_title,
            verdict_text=verdict_text,
            baseline_value=f"{improvement['baseline_ad_value']:.1f}",
            variant_value=f"{improvement['variant_ad_value']:.1f}",
            improvement_pct=f"{improvement['improvement_percentage']:+.1f}",
            improvement_abs=f"{improvement['absolute_improvement']:+.1f}",
            target_status="PASS" if improvement["target_20pct_met"] else "NOT MET",
            target_detail="目标 ≥ 20%",
            baseline_grades_html=baseline_grades_html,
            variant_grades_html=variant_grades_html,
            top_variant_rows=top_variant_rows,
            archetypes_html=archetypes_html,
            top_hook=top_hook or "-",
            top_subject=top_subject or "-",
            top_action=top_action or "-",
            avg_arch_sim=f"{avg_arch_sim:.0f}",
            pool_size=ab_result.get("pool_size", 0),
            n_per_group=ab_result.get("n_per_group", 10),
        )

        html_path = self.output_dir / "v38_creative_intelligence_report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        return {
            "html_path": str(html_path),
            "json_path": str(self.output_dir / "v38_ab_test_result.json"),
        }

    @staticmethod
    def _render_grade_bars(grades: Dict[str, int]) -> str:
        """渲染 Grade 分布条"""
        total = sum(grades.values()) or 1
        grade_order = ["S+", "S", "A", "B", "Reject"]
        class_map = {
            "S+": "grade-splus",
            "S": "grade-s",
            "A": "grade-a",
            "B": "grade-b",
            "Reject": "grade-reject",
        }

        html = '<div class="grade-bars">'
        for grade in grade_order:
            count = grades.get(grade, 0)
            pct = count / total * 100
            html += f'''
            <div class="grade-bar">
                <span class="grade-label">{grade}</span>
                <div class="grade-track">
                    <div class="grade-fill {class_map[grade]}" style="width: {pct}%"></div>
                </div>
                <span class="grade-count">{count}</span>
            </div>'''
        html += "</div>"
        return html

    @staticmethod
    def _render_top_table(top_list: List[dict]) -> str:
        """渲染 Top 表格"""
        badge_class = {
            "S+": "badge-splus",
            "S": "badge-s",
            "A": "badge-a",
            "B": "badge-b",
            "Reject": "badge-reject",
        }
        html = ""
        for i, item in enumerate(top_list, 1):
            grade = item.get("grade", "")
            badge = f'<span class="badge {badge_class.get(grade, "badge-b")}">{grade}</span>' if grade else "-"
            html += f'''
                    <tr>
                        <td>{i}</td>
                        <td>{item.get("video_name", "")}</td>
                        <td><strong>{item.get("score", 0):.1f}</strong></td>
                        <td>{badge}</td>
                        <td>{item.get("archetype", "")}</td>
                        <td>-</td>
                        <td>-</td>
                    </tr>'''
        return html

    @staticmethod
    def _render_archetypes(archetype_ranking: List[dict]) -> str:
        """渲染 Archetype 列表"""
        if not archetype_ranking:
            return "<p>暂无数据</p>"

        html = ""
        for i, arch in enumerate(archetype_ranking, 1):
            features = ", ".join(arch.get("key_features", [])[:3])
            html += f'''
            <div class="archetype-card">
                <div class="archetype-name">#{i} {arch["name"]}</div>
                <div class="archetype-metrics">
                    <span>CTR: {arch["avg_ctr"]:.2f}%</span>
                    <span>CPI: ${arch["avg_cpi"]:.2f}</span>
                    <span>D7 ROI: {arch["avg_d7_roi"]:.3f}</span>
                    <span>Winners: {arch["winner_count"]}</span>
                </div>
                <div class="archetype-features">特征: {features}</div>
            </div>'''
        return html

    @staticmethod
    def _most_common(patterns: List[dict], key: str) -> str:
        """获取最常见的值"""
        from collections import Counter
        vals = [p.get(key, "") for p in patterns if p.get(key)]
        if not vals:
            return ""
        return Counter(vals).most_common(1)[0][0]


def generate_v38_report(result_json_path: Path, output_dir: Path):
    """从 JSON 生成报告"""
    with open(result_json_path, "r", encoding="utf-8") as f:
        ab_result = json.load(f)

    generator = V38ReportGenerator(output_dir)
    return generator.generate(ab_result)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    from creative_remix_engine.experiments.v38_creative_intelligence import run_v38_ab_test

    result = run_v38_ab_test(n=10)

    output_dir = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v38_creative_intelligence")
    generator = V38ReportGenerator(output_dir)
    report = generator.generate(result)
    print(f"\nReport generated: {report['html_path']}")
