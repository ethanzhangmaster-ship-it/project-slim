"""Bitable HTML 图表报告生成器

生成自包含 HTML 文件，包含 Chart.js 交互图表和 KPI 汇总卡片。
输出到 output/active/bitable_report_YYYYMMDD.html。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.bitable_report import BitableReportPayload
from market_ops.config import Settings


class BitableHtmlReportBuilder:
    """生成带 Chart.js 图表的 HTML 周报。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date, payload: BitableReportPayload) -> Path:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        html = self._render_html(report_date, payload.chart_data)
        path = output_dir / f"bitable_report_{suffix}.html"
        path.write_text(html, encoding="utf-8")
        return path

    def _render_html(self, report_date: date, chart_data: dict[str, Any]) -> str:
        date_str = report_date.isoformat()
        kpi = chart_data.get("kpi_summary", {})
        prj = chart_data.get("project_spend_revenue", {})
        roi = chart_data.get("project_roi_comparison", {})
        dec = chart_data.get("decision_distribution", {})
        ch = chart_data.get("channel_spend_breakdown", {})
        cre = chart_data.get("creative_roas_top10", {})
        fat = chart_data.get("fatigue_distribution", {})
        radar = chart_data.get("decision_radar", {})
        fat_ctr = chart_data.get("fatigue_ctr_drop_top10", {})
        payback = chart_data.get("dynamic_payback_comparison", {})
        funnel = chart_data.get("action_funnel", {})

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Ops 可视化周报 — {date_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --text: #e0e0e0;
    --text2: #a0a0b0;
    --accent: #6c8cff;
    --green: #4caf50;
    --red: #ef5350;
    --gold: #ffc107;
    --purple: #ab47bc;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.6;
  }}
  h1 {{
    font-size: 1.5rem;
    margin-bottom: 8px;
    color: var(--accent);
  }}
  .subtitle {{
    color: var(--text2);
    font-size: 0.9rem;
    margin-bottom: 24px;
  }}
  .kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .kpi-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
  }}
  .kpi-label {{
    font-size: 0.8rem;
    color: var(--text2);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .kpi-value {{
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--accent);
  }}
  .chart-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
    gap: 24px;
    margin-bottom: 32px;
  }}
  .chart-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
  }}
  .chart-title {{
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--text);
  }}
  canvas {{
    max-height: 320px;
  }}
  .footer {{
    text-align: center;
    color: var(--text2);
    font-size: 0.75rem;
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
  }}
</style>
</head>
<body>

<h1>Market Ops 可视化周报</h1>
<p class="subtitle">报告周期: {date_str} &nbsp;|&nbsp; 自动生成 by Market Ops System</p>

<!-- KPI Summary Cards -->
<div class="kpi-row">
  {self._render_kpi_cards(kpi)}
</div>

<!-- Charts -->
<div class="chart-grid">
  <div class="chart-card">
    <div class="chart-title">项目花费与收入对比</div>
    <canvas id="chartSpendRevenue"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">项目 ROI 对比</div>
    <canvas id="chartProjectROI"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">决策分布</div>
    <canvas id="chartDecision"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">渠道花费分布</div>
    <canvas id="chartChannel"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">素材 ROAS Top 10</div>
    <canvas id="chartCreative"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">素材疲劳分布</div>
    <canvas id="chartFatigue"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">决策 13 维权重雷达</div>
    <canvas id="chartRadar"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">疲劳素材 CTR 降幅 Top 10</div>
    <canvas id="chartFatigueCTR"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">项目动态保底线对比 (D7)</div>
    <canvas id="chartPayback"></canvas>
  </div>
  <div class="chart-card">
    <div class="chart-title">行动追踪闭环漏斗</div>
    <canvas id="chartFunnel"></canvas>
  </div>
</div>

<div class="footer">
  Market Ops System &mdash; Bitable Visual Report &mdash; Generated {date_str}
</div>

<script>
Chart.defaults.color = '#a0a0b0';
Chart.defaults.borderColor = '#2a2d3a';
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

// 1. 项目花费与收入对比
new Chart(document.getElementById('chartSpendRevenue'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(prj.get("labels", []), ensure_ascii=False)},
    datasets: [
      {{
        label: '花费',
        data: {json.dumps(prj.get("spend", []))},
        backgroundColor: 'rgba(108,140,255,0.7)',
        borderColor: '#6c8cff',
        borderWidth: 1,
      }},
      {{
        label: '收入',
        data: {json.dumps(prj.get("revenue", []))},
        backgroundColor: 'rgba(76,175,80,0.7)',
        borderColor: '#4caf50',
        borderWidth: 1,
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{ y: {{ beginAtZero: true }} }}
  }}
}});

// 2. 项目 ROI 对比
const roiValues = {json.dumps(roi.get("roi_values", []))};
const roiColors = roiValues.map(v => v >= 1.0 ? 'rgba(76,175,80,0.8)' : v >= 0.8 ? 'rgba(255,193,7,0.8)' : 'rgba(239,83,80,0.8)');
new Chart(document.getElementById('chartProjectROI'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(roi.get("labels", []), ensure_ascii=False)},
    datasets: [{{
      label: 'ROI',
      data: roiValues,
      backgroundColor: roiColors,
      borderWidth: 1,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true }} }}
  }}
}});

// 3. 决策分布
const decisionLabels = {json.dumps(dec.get("categories", []), ensure_ascii=False)};
const decisionColors = decisionLabels.map(c => {{
  const map = {{
    'small_scale_up': '#4caf50', 'hold': '#6c8cff', 'repair': '#ffc107',
    'downweight': '#ff9800', 'pause_or_review': '#ef5350', 'data_blocked': '#9e9e9e'
  }};
  return map[c] || '#6c8cff';
}});
new Chart(document.getElementById('chartDecision'), {{
  type: 'doughnut',
  data: {{
    labels: decisionLabels,
    datasets: [{{
      data: {json.dumps(dec.get("counts", []))},
      backgroundColor: decisionColors,
      borderWidth: 2,
      borderColor: '#1a1d27',
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ padding: 16 }} }} }}
  }}
}});

// 4. 渠道花费分布
new Chart(document.getElementById('chartChannel'), {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps(ch.get("labels", []), ensure_ascii=False)},
    datasets: [{{
      data: {json.dumps(ch.get("values", []))},
      backgroundColor: ['#6c8cff','#4caf50','#ffc107','#ab47bc','#ff9800','#ef5350','#26c6da','#8d6e63'],
      borderWidth: 2,
      borderColor: '#1a1d27',
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom', labels: {{ padding: 16 }} }} }}
  }}
}});

// 5. 素材 ROAS Top 10
new Chart(document.getElementById('chartCreative'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(cre.get("labels", []), ensure_ascii=False)},
    datasets: [{{
      label: 'ROAS',
      data: {json.dumps(cre.get("values", []))},
      backgroundColor: 'rgba(171,71,188,0.7)',
      borderColor: '#ab47bc',
      borderWidth: 1,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true }} }}
  }}
}});

// 6. 疲劳分布
new Chart(document.getElementById('chartFatigue'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(fat.get("labels", []), ensure_ascii=False)},
    datasets: [{{
      label: '素材数量',
      data: {json.dumps(fat.get("counts", []))},
      backgroundColor: ['rgba(239,83,80,0.7)', 'rgba(255,193,7,0.7)', 'rgba(158,158,158,0.7)'],
      borderWidth: 1,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true }} }}
  }}
}});

// 7. 决策 13 维权重雷达
const radarLabels = {json.dumps(radar.get("labels", []), ensure_ascii=False)};
const radarDatasets = {json.dumps(radar.get("datasets", []), ensure_ascii=False)};
const radarColors = [
  {{ borderColor: 'rgba(108,140,255,0.8)', backgroundColor: 'rgba(108,140,255,0.15)' }},
  {{ borderColor: 'rgba(76,175,80,0.8)', backgroundColor: 'rgba(76,175,80,0.15)' }},
  {{ borderColor: 'rgba(255,193,7,0.8)', backgroundColor: 'rgba(255,193,7,0.15)' }},
  {{ borderColor: 'rgba(171,71,188,0.8)', backgroundColor: 'rgba(171,71,188,0.15)' }},
  {{ borderColor: 'rgba(255,152,0,0.8)', backgroundColor: 'rgba(255,152,0,0.15)' }},
];
const radarChartDatasets = radarDatasets.map((ds, i) => ({{
  ...radarColors[i % radarColors.length],
  label: ds.label || `Entity ${{i+1}}`,
  data: ds.values,
  fill: true,
  pointBackgroundColor: radarColors[i % radarColors.length].borderColor,
}}));
new Chart(document.getElementById('chartRadar'), {{
  type: 'radar',
  data: {{
    labels: radarLabels,
    datasets: radarChartDatasets,
  }},
  options: {{
    responsive: true,
    scales: {{
      r: {{
        beginAtZero: true,
        suggestedMin: -0.3,
        suggestedMax: 1.0,
        grid: {{ color: '#2a2d3a' }},
        angleLines: {{ color: '#2a2d3a' }},
        pointLabels: {{ color: '#a0a0b0', font: {{ size: 10 }} }},
      }}
    }},
    plugins: {{ legend: {{ position: 'bottom' }} }}
  }}
}});

// 8. 疲劳素材 CTR 降幅 Top 10
new Chart(document.getElementById('chartFatigueCTR'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(fat_ctr.get("labels", []), ensure_ascii=False)},
    datasets: [{{
      label: 'CTR 降幅',
      data: {json.dumps(fat_ctr.get("values", []))},
      backgroundColor: 'rgba(239,83,80,0.7)',
      borderColor: '#ef5350',
      borderWidth: 1,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ beginAtZero: true }} }}
  }}
}});

// 9. 项目动态保底线对比
new Chart(document.getElementById('chartPayback'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(payback.get("labels", []), ensure_ascii=False)},
    datasets: [
      {{
        label: '静态保本 D7',
        data: {json.dumps(payback.get("static_d7", []))},
        backgroundColor: 'rgba(158,158,158,0.7)',
        borderColor: '#9e9e9e',
        borderWidth: 1,
      }},
      {{
        label: '动态保本 D7',
        data: {json.dumps(payback.get("dynamic_d7", []))},
        backgroundColor: 'rgba(255,193,7,0.7)',
        borderColor: '#ffc107',
        borderWidth: 1,
      }},
      {{
        label: '当前 D7',
        data: {json.dumps(payback.get("current_d7", []))},
        backgroundColor: 'rgba(108,140,255,0.7)',
        borderColor: '#6c8cff',
        borderWidth: 1,
      }}
    ]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'top' }} }},
    scales: {{ y: {{ beginAtZero: true }} }}
  }}
}});

// 10. 行动追踪闭环漏斗
const funnelLabels = {json.dumps(funnel.get("labels", []), ensure_ascii=False)};
const funnelCounts = {json.dumps(funnel.get("counts", []))};
const funnelColors = funnelLabels.map(l => {{
  const map = {{
    '待确认': 'rgba(255,193,7,0.7)', '执行中': 'rgba(108,140,255,0.7)',
    '已完成': 'rgba(76,175,80,0.7)', '已验收': 'rgba(171,71,188,0.7)'
  }};
  return map[l] || 'rgba(108,140,255,0.7)';
}});
new Chart(document.getElementById('chartFunnel'), {{
  type: 'bar',
  data: {{
    labels: funnelLabels,
    datasets: [{{
      label: '行动数',
      data: funnelCounts,
      backgroundColor: funnelColors,
      borderWidth: 1,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }}
  }}
}});
</script>
</body>
</html>"""

    def _render_kpi_cards(self, kpi: dict[str, str]) -> str:
        if not kpi:
            return '<div class="kpi-card"><div class="kpi-label">暂无数据</div></div>'
        cards: list[str] = []
        for label, value in kpi.items():
            cards.append(
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div>'
                f'</div>'
            )
        return "\n  ".join(cards)
