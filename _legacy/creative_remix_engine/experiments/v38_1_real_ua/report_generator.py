"""V3.8.1 Report Generator — UA Performance Report

生成：
- ua_performance_report.html
- winner_dna_evolution.html
- creative_roi_ranking.json
- performance_archetypes.json
- model_metrics.json
"""
import json
from pathlib import Path
from typing import Dict, List

from creative_remix_engine.config import OUTPUT_DIR


REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>V3.8.1 Real UA Validation Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f7fa; color: #1a1a2e; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%); color: white; padding: 40px; border-radius: 16px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header .subtitle {{ opacity: 0.9; font-size: 16px; }}
        .header .timestamp {{ opacity: 0.7; font-size: 14px; margin-top: 10px; }}

        .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
        .card h2 {{ font-size: 20px; margin-bottom: 16px; color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
        .card h3 {{ font-size: 16px; margin: 16px 0 12px; color: #4a5568; }}

        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }}
        .metric-box {{ background: #f7fafc; border-radius: 10px; padding: 18px; text-align: center; }}
        .metric-box .label {{ font-size: 13px; color: #718096; margin-bottom: 6px; }}
        .metric-box .value {{ font-size: 28px; font-weight: 700; color: #2d3748; }}
        .metric-box .change {{ font-size: 13px; margin-top: 4px; }}
        .change.up {{ color: #48bb78; }}
        .change.down {{ color: #f56565; }}

        .ab-comparison {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
        .ab-group {{ padding: 20px; border-radius: 10px; background: #f7fafc; }}
        .ab-group.baseline {{ border-left: 4px solid #a0aec0; }}
        .ab-group.variant {{ border-left: 4px solid #48bb78; }}
        .ab-group .group-title {{ font-weight: 600; margin-bottom: 12px; font-size: 16px; }}

        .verdict {{ text-align: center; padding: 30px; border-radius: 12px; margin: 20px 0; }}
        .verdict.pass {{ background: linear-gradient(135deg, #c6f6d5 0%, #9ae6b4 100%); color: #22543d; }}
        .verdict.fail {{ background: linear-gradient(135deg, #fed7d7 0%, #feb2b2 100%); color: #742a2a; }}
        .verdict h2 {{ font-size: 28px; margin-bottom: 8px; }}
        .verdict p {{ font-size: 16px; opacity: 0.9; }}

        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f7fafc; font-weight: 600; color: #4a5568; }}
        tr:hover {{ background: #f7fafc; }}

        .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
        .badge-splus {{ background: #fefcbf; color: #975a16; }}
        .badge-s {{ background: #c6f6d5; color: #276749; }}
        .badge-a {{ background: #bee3f8; color: #2a4365; }}
        .badge-b {{ background: #e9d8fd; color: #553c9a; }}
        .badge-reject {{ background: #fed7d7; color: #c53030; }}

        .archetype-card {{ background: #f7fafc; border-radius: 10px; padding: 16px; margin: 10px 0; }}
        .archetype-name {{ font-weight: 600; font-size: 15px; color: #2d3748; margin-bottom: 6px; }}
        .archetype-metrics {{ display: flex; gap: 16px; font-size: 13px; color: #4a5568; }}
        .archetype-features {{ margin-top: 8px; font-size: 12px; color: #718096; }}

        .target-list {{ list-style: none; padding: 0; }}
        .target-list li {{ padding: 10px; margin: 5px 0; border-radius: 8px; background: #f7fafc; display: flex; justify-content: space-between; align-items: center; }}
        .target-pass {{ color: #48bb78; font-weight: 600; }}
        .target-fail {{ color: #f56565; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>V3.8.1 Real UA Validation Layer</h1>
            <div class="subtitle">真实买量数据驱动的创意学习闭环</div>
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
                    <div class="label">V3.8 Ad Value</div>
                    <div class="value">{v38_ad_value}</div>
                    <div class="change">Buying Score</div>
                </div>
                <div class="metric-box">
                    <div class="label">V3.8.1 Ad Value</div>
                    <div class="value">{v381_ad_value}</div>
                    <div class="change up">Real Performance Score</div>
                </div>
                <div class="metric-box">
                    <div class="label">提升幅度</div>
                    <div class="value">{ad_value_improvement}%</div>
                    <div class="change up">综合 Ad Value</div>
                </div>
                <div class="metric-box">
                    <div class="label">样本数</div>
                    <div class="value">{n_per_group} × 2</div>
                    <div class="change">每组样本</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📈 真实指标对比</h2>
            <div class="ab-comparison">
                <div class="ab-group baseline">
                    <div class="group-title">V3.8 (Baseline)</div>
                    <div style="font-size: 24px; font-weight: 700; margin-bottom: 10px;">{v38_ctr}% CTR</div>
                    <div style="margin-bottom: 5px;">CPI: ${v38_cpi}</div>
                    <div style="margin-bottom: 5px;">D7 ROI: {v38_d7_roi}</div>
                    <div>D30 ROI: {v38_d30_roi}</div>
                </div>
                <div class="ab-group variant">
                    <div class="group-title">V3.8.1 (Variant)</div>
                    <div style="font-size: 24px; font-weight: 700; margin-bottom: 10px;">{v381_ctr}% CTR</div>
                    <div style="margin-bottom: 5px;">CPI: ${v381_cpi}</div>
                    <div style="margin-bottom: 5px;">D7 ROI: {v381_d7_roi}</div>
                    <div>D30 ROI: {v381_d30_roi}</div>
                </div>
            </div>

            <h3>指标提升</h3>
            <ul class="target-list">
                <li>CTR +15% <span class="{ctr_class}">{ctr_improvement:+.1f}%</span></li>
                <li>CPI -15% <span class="{cpi_class}">{cpi_improvement:+.1f}%</span></li>
                <li>D7 ROI +20% <span class="{roi_class}">{roi_improvement:+.1f}%</span></li>
                <li>D30 ROI <span class="{d30_class}">{d30_improvement:+.1f}%</span></li>
            </ul>
        </div>

        <div class="card">
            <h2>🧬 Performance Archetypes (真实ROI驱动)</h2>
            {archetypes_html}
        </div>

        <div class="card">
            <h2>🏆 Top 10 Creative DNA</h2>
            <table>
                <thead>
                    <tr><th>#</th><th>Creative ID</th><th>Score</th><th>CTR</th><th>CPI</th><th>D7 ROI</th><th>Hook</th><th>Subject</th></tr>
                </thead>
                <tbody>{top_creatives_html}</tbody>
            </table>
        </div>

        <div class="card">
            <h2>📊 模型指标</h2>
            <table>
                <thead>
                    <tr><th>模型</th><th>MAE</th><th>RMSE</th><th>R²</th><th>状态</th></tr>
                </thead>
                <tbody>
                    <tr><td>CTR Predictor</td><td>{ctr_mae}</td><td>{ctr_rmse}</td><td>{ctr_r2}</td><td>{ctr_status}</td></tr>
                    <tr><td>CPI Predictor</td><td>{cpi_mae}</td><td>{cpi_rmse}</td><td>{cpi_r2}</td><td>{cpi_status}</td></tr>
                    <tr><td>D7 ROI Predictor</td><td>{roi_d7_mae}</td><td>{roi_d7_rmse}</td><td>{roi_d7_r2}</td><td>{roi_status}</td></tr>
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>📋 数据汇总</h2>
            <table>
                <tr><th>项目</th><th>数值</th></tr>
                <tr><td>总创意数</td><td>{total_creatives}</td></tr>
                <tr><td>Winner 数量</td><td>{winner_count}</td></tr>
                <tr><td>平均 CTR</td><td>{avg_ctr}%</td></tr>
                <tr><td>平均 CPI</td><td>${avg_cpi}</td></tr>
                <tr><td>平均 D7 ROI</td><td>{avg_d7_roi}</td></tr>
                <tr><td>Performance Score 权重</td><td>CTR 30% + CPI 25% + ROI 35% + Retention 10%</td></tr>
            </table>
        </div>

        <div class="card">
            <h2>🎯 V3.8.1 核心升级</h2>
            <ul style="padding-left: 20px; line-height: 2;">
                <li><strong>真实数据驱动</strong>：从 AI 预测转向真实 UA 数据反馈</li>
                <li><strong>三平台数据连接</strong>：Facebook / TikTok / Google Ads</li>
                <li><strong>ML 预测模型</strong>：XGBoost/LightGBM/RandomForest 预测 CTR/CPI/ROI</li>
                <li><strong>DNA-Performance Mapping</strong>：视频 DNA 与真实买量结果关联</li>
                <li><strong>Winner DNA 自动更新</strong>：根据表现自动调整权重</li>
                <li><strong>Real Performance Score</strong>：真实 CTR/CPI/ROI/Retention 加权评分</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""


class V381ReportGenerator:
    """V3.8.1 报告生成器"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, ab_result: dict) -> dict:
        """生成报告"""
        improvement = ab_result["improvement"]
        v38 = ab_result["v38"]
        v381 = ab_result["v381"]

        # Verdict
        all_pass = (
            improvement["targets"]["ctr_15pct"] and
            improvement["targets"]["cpi_15pct"] and
            improvement["targets"]["roi_20pct"]
        )
        if all_pass:
            verdict_class = "pass"
            verdict_title = "✅ 全部目标达成"
            verdict_text = f"V3.8.1 真实数据驱动学习相比 V3.8 提升显著"
        else:
            verdict_class = "fail"
            verdict_title = "⚠️ 部分目标未达成"
            verdict_text = "需要继续优化模型和数据质量"

        # 指标数据
        v38_m = v38["metrics"]
        v381_m = v381["metrics"]

        # 等级样式
        ctr_class = "target-pass" if improvement["targets"]["ctr_15pct"] else "target-fail"
        cpi_class = "target-pass" if improvement["targets"]["cpi_15pct"] else "target-fail"
        roi_class = "target-pass" if improvement["targets"]["roi_20pct"] else "target-fail"
        d30_class = "target-pass" if improvement["d30_roi_improvement"] > 0 else "target-fail"

        # Archetypes
        archetypes_html = self._render_archetypes(ab_result.get("winner_update", {}).get("top_patterns", []))

        # Top Creatives
        top_creatives_html = self._render_top_creatives(v381["top_n"])

        # 模型指标
        ctr_metrics = ab_result.get("ctr_model_metrics", {})
        cpi_metrics = ab_result.get("cpi_model_metrics", {})
        roi_metrics = ab_result.get("roi_model_metrics", {})

        html = REPORT_TEMPLATE.format(
            timestamp=ab_result.get("timestamp", ""),
            verdict_class=verdict_class,
            verdict_title=verdict_title,
            verdict_text=verdict_text,
            v38_ad_value=f"{v38_m['avg_ad_value']:.1f}",
            v381_ad_value=f"{v381_m['avg_ad_value']:.1f}",
            ad_value_improvement=f"{improvement['ad_value_improvement']:+.1f}",
            n_per_group=ab_result.get("n_per_group", 20),
            v38_ctr=f"{v38_m['avg_ctr']:.2f}",
            v38_cpi=f"{v38_m['avg_cpi']:.2f}",
            v38_d7_roi=f"{v38_m['avg_d7_roi']:.3f}",
            v38_d30_roi=f"{v38_m['avg_d30_roi']:.3f}",
            v381_ctr=f"{v381_m['avg_ctr']:.2f}",
            v381_cpi=f"{v381_m['avg_cpi']:.2f}",
            v381_d7_roi=f"{v381_m['avg_d7_roi']:.3f}",
            v381_d30_roi=f"{v381_m['avg_d30_roi']:.3f}",
            ctr_improvement=improvement["ctr_improvement"],
            cpi_improvement=improvement["cpi_improvement"],
            roi_improvement=improvement["d7_roi_improvement"],
            d30_improvement=improvement["d30_roi_improvement"],
            ctr_class=ctr_class,
            cpi_class=cpi_class,
            roi_class=roi_class,
            d30_class=d30_class,
            archetypes_html=archetypes_html,
            top_creatives_html=top_creatives_html,
            ctr_mae=ctr_metrics.get("mae", "-"),
            ctr_rmse=ctr_metrics.get("rmse", "-"),
            ctr_r2=ctr_metrics.get("r2", "-"),
            ctr_status="Trained" if ctr_metrics else "Baseline",
            cpi_mae=cpi_metrics.get("mae", "-"),
            cpi_rmse=cpi_metrics.get("rmse", "-"),
            cpi_r2=cpi_metrics.get("r2", "-"),
            cpi_status="Trained" if cpi_metrics else "Baseline",
            roi_d7_mae=roi_metrics.get("d7", {}).get("mae", "-"),
            roi_d7_rmse=roi_metrics.get("d7", {}).get("rmse", "-"),
            roi_d7_r2=roi_metrics.get("d7", {}).get("r2", "-"),
            roi_status="Trained" if roi_metrics else "Baseline",
            total_creatives=ab_result.get("performance_db_summary", {}).get("total_creatives", 0),
            winner_count=ab_result.get("performance_db_summary", {}).get("winners_count", 0),
            avg_ctr=ab_result.get("performance_db_summary", {}).get("avg_ctr", 0),
            avg_cpi=ab_result.get("performance_db_summary", {}).get("avg_cpi", 0),
            avg_d7_roi=ab_result.get("performance_db_summary", {}).get("avg_d7_roi", 0),
        )

        html_path = self.output_dir / "ua_performance_report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # 保存其他 JSON 文件
        self._save_json_reports(ab_result)

        return {
            "html_path": str(html_path),
            "json_path": str(self.output_dir / "v38_1_ab_test_result.json"),
        }

    def _render_archetypes(self, top_patterns: List[dict]) -> str:
        """渲染 Archetypes"""
        if not top_patterns:
            return "<p>暂无数据</p>"

        html = ""
        for i, pattern in enumerate(top_patterns[:5], 1):
            dna = pattern["dna_pattern"]
            perf = pattern["performance"]
            features = f"Hook: {dna['hook']}, Gameplay: {dna['gameplay']}, Reward: {dna['reward']}"
            html += f'''
            <div class="archetype-card">
                <div class="archetype-name">#{i} {dna['subject']}_{dna['hook']}_{dna['gameplay']}</div>
                <div class="archetype-metrics">
                    <span>CTR: {perf["avg_ctr"]:.2f}%</span>
                    <span>CPI: ${perf["avg_cpi"]:.2f}</span>
                    <span>D7 ROI: {perf["avg_d7_roi"]:.3f}</span>
                    <span>Samples: {pattern["sample_count"]}</span>
                </div>
                <div class="archetype-features">{features}</div>
            </div>'''
        return html

    def _render_top_creatives(self, top_list: List[dict]) -> str:
        """渲染 Top 创意"""
        html = ""
        for i, item in enumerate(top_list[:10], 1):
            perf = item.get("real_performance", {})
            dna = perf.get("dna", {})
            html += f'''
            <tr>
                <td>{i}</td>
                <td>{item.get("creative_id", "")}</td>
                <td>{item.get("performance_score", 0):.1f}</td>
                <td>{perf.get("ctr", 0):.2f}</td>
                <td>{perf.get("cpi", 0):.2f}</td>
                <td>{perf.get("d7_roi", 0):.3f}</td>
                <td>{dna.get("hook", "")}</td>
                <td>{dna.get("subject", "")}</td>
            </tr>'''
        return html

    def _save_json_reports(self, ab_result: dict):
        """保存 JSON 报告"""
        # Creative ROI Ranking
        roi_ranking = sorted(
            ab_result.get("v381", {}).get("top_n", []),
            key=lambda x: -x.get("real_performance", {}).get("d7_roi", 0)
        )
        with open(self.output_dir / "creative_roi_ranking.json", "w", encoding="utf-8") as f:
            json.dump(roi_ranking, f, ensure_ascii=False, indent=2)

        # Performance Archetypes
        archetypes = ab_result.get("winner_update", {}).get("top_patterns", [])
        with open(self.output_dir / "performance_archetypes.json", "w", encoding="utf-8") as f:
            json.dump(archetypes, f, ensure_ascii=False, indent=2)

        # Model Metrics
        model_metrics = {
            "ctr_predictor": {},
            "cpi_predictor": {},
            "roi_predictor": {},
        }
        with open(self.output_dir / "model_metrics.json", "w", encoding="utf-8") as f:
            json.dump(model_metrics, f, ensure_ascii=False, indent=2)


def generate_v381_report(result_json_path: Path, output_dir: Path):
    """从 JSON 生成报告"""
    with open(result_json_path, "r", encoding="utf-8") as f:
        ab_result = json.load(f)

    generator = V381ReportGenerator(output_dir)
    return generator.generate(ab_result)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    from creative_remix_engine.experiments.v38_1_real_ua import run_v381_ab_test

    result = run_v381_ab_test(n=20)

    output_dir = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v38_1")
    generator = V381ReportGenerator(output_dir)
    report = generator.generate(result)
    print(f"\nReport generated: {report['html_path']}")
