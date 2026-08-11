"""Creative Intelligence Dashboard - 可视化报告生成

生成各类 Dashboard 数据：
- Creative Memory Dashboard
- Knowledge Graph Dashboard
- Feature Dashboard
- Learning Dashboard
- Portfolio Dashboard
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class IntelligenceDashboard:
    """Intelligence 可视化报告生成器"""

    def __init__(self, intelligence):
        self.intel = intelligence

    def generate_all(self, output_dir: str | Path) -> dict:
        """生成所有 Dashboard 数据"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        reports = {}

        # Memory Dashboard
        mem = self.generate_memory_dashboard()
        with open(output_dir / "memory_dashboard.json", "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2, ensure_ascii=False, default=str)
        reports["memory"] = mem

        # Feature Dashboard
        feat = self.generate_feature_dashboard()
        with open(output_dir / "feature_dashboard.json", "w", encoding="utf-8") as f:
            json.dump(feat, f, indent=2, ensure_ascii=False, default=str)
        reports["feature"] = feat

        # Knowledge Graph Dashboard
        kg = self.generate_graph_dashboard()
        with open(output_dir / "graph_dashboard.json", "w", encoding="utf-8") as f:
            json.dump(kg, f, indent=2, ensure_ascii=False, default=str)
        reports["graph"] = kg

        # Learning Dashboard
        learn = self.generate_learning_dashboard()
        with open(output_dir / "learning_dashboard.json", "w", encoding="utf-8") as f:
            json.dump(learn, f, indent=2, ensure_ascii=False, default=str)
        reports["learning"] = learn

        # Portfolio Dashboard
        port = self.generate_portfolio_dashboard()
        with open(output_dir / "portfolio_dashboard.json", "w", encoding="utf-8") as f:
            json.dump(port, f, indent=2, ensure_ascii=False, default=str)
        reports["portfolio"] = port

        # Markdown 报告
        md = self.generate_markdown_report(reports)
        with open(output_dir / "intelligence_report.md", "w", encoding="utf-8") as f:
            f.write(md)

        return reports

    def generate_memory_dashboard(self) -> dict:
        """Memory Dashboard - 最强变量排行"""
        intel = self.intel

        # Top 生物
        top_creatures = intel.memory_top("creature_0_type", "roas", 10)
        # Top 颜色
        top_colors = intel.memory_top("creature_0_color", "roas", 10)
        # Top 环境
        top_environments = intel.memory_top("environment_type", "roas", 10)
        # Top Hook
        top_hooks = intel.memory_top("hook_type", "roas", 10)

        # 国家差异
        countries = []
        for c in ["US", "UK", "DE", "JP", "KR", "BR"]:
            perf = intel.memory.get_country_performance(c)
            if perf:
                countries.append(perf)

        # 版位差异
        placements = []
        for p in ["FB_Feed", "IG_Feed", "IG_Reels", "FB_Reels", "Audience_Network"]:
            perf = intel.memory.get_placement_performance(p)
            if perf:
                placements.append(perf)

        return {
            "generated_at": datetime.now().isoformat(),
            "top_creatures_by_roas": top_creatures,
            "top_colors_by_roas": top_colors,
            "top_environments_by_roas": top_environments,
            "top_hooks_by_roas": top_hooks,
            "country_comparison": countries,
            "placement_comparison": placements,
        }

    def generate_feature_dashboard(self) -> dict:
        """Feature Dashboard - 特征统计"""
        intel = self.intel
        schema = intel.feature_schema()

        # 按类型统计
        types = {}
        for name, spec in schema.items():
            t = spec.get("type", "unknown")
            types[t] = types.get(t, 0) + 1

        # 数值特征统计
        numeric_features = [n for n, s in schema.items() if s.get("type") == "numeric"]
        categorical_features = [n for n, s in schema.items() if s.get("type") == "categorical"]
        target_features = [n for n, s in schema.items() if s.get("type") == "target"]

        return {
            "generated_at": datetime.now().isoformat(),
            "total_features": len(schema),
            "feature_types": types,
            "numeric_features": numeric_features,
            "categorical_features": categorical_features,
            "target_features": target_features,
            "schema_summary": {
                "character_features": [f for f in schema if f.startswith("character_")],
                "creature_features": [f for f in schema if f.startswith("creature_")],
                "environment_features": [f for f in schema if f.startswith("environment_")],
                "lighting_features": [f for f in schema if f.startswith("lighting_")],
                "audience_features": [f for f in schema if f in ["country", "age_range", "gender", "placement", "os"]],
            },
        }

    def generate_graph_dashboard(self) -> dict:
        """Knowledge Graph Dashboard"""
        intel = self.intel
        summary = intel.graph_summary()

        # Top特征-指标关联
        top_ctr_features = intel.graph_top_features("ctr", 10)
        top_roas_features = intel.graph_top_features("roas", 10)

        return {
            "generated_at": datetime.now().isoformat(),
            "graph_summary": summary,
            "top_ctr_drivers": top_ctr_features,
            "top_roas_drivers": top_roas_features,
        }

    def generate_learning_dashboard(self) -> dict:
        """Learning Dashboard"""
        intel = self.intel

        progress = intel.learning.get_learning_progress()

        # 特征重要性
        feature_importance = {
            "ctr": intel.learning.compute_feature_importance("ctr")[:15],
            "roas": intel.learning.compute_feature_importance("roas")[:15],
            "cvr": intel.learning.compute_feature_importance("cvr")[:15],
            "ipm": intel.learning.compute_feature_importance("ipm")[:15],
        }

        # 赢家/输家模式
        winning_patterns = intel.learning.get_top_winning_patterns("roas", 10)
        losing_patterns = intel.learning.get_top_losing_patterns("roas", 10)

        return {
            "generated_at": datetime.now().isoformat(),
            "learning_progress": progress,
            "feature_importance": feature_importance,
            "top_winning_patterns": winning_patterns,
            "top_losing_patterns": losing_patterns,
        }

    def generate_portfolio_dashboard(self) -> dict:
        """Portfolio Dashboard - 组合分布"""
        # 这个需要实际 portfolio 数据，这里生成结构
        return {
            "generated_at": datetime.now().isoformat(),
            "portfolio_structure": {
                "safe": {"count": 0, "budget_pct": 0.6},
                "growth": {"count": 0, "budget_pct": 0.3},
                "explore": {"count": 0, "budget_pct": 0.1},
            },
            "distribution_by": {
                "creature_type": {},
                "environment_type": {},
                "hook_type": {},
                "lighting_type": {},
                "risk_level": {},
            },
        }

    def generate_markdown_report(self, reports: dict) -> str:
        """生成 Markdown 总报告"""
        lines = [
            "# Creative Intelligence Dashboard (V4.2.2)",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 项目: {self.intel.project}",
            f"> 渠道: {self.intel.channel}",
            "",
            "---",
            "",
            "## 一、系统概览",
            "",
            f"- **总特征数**: {reports['feature']['total_features']}",
            f"- **特征类型**: {json.dumps(reports['feature']['feature_types'], ensure_ascii=False)}",
            f"- **预测目标**: {', '.join(reports['feature']['target_features'])}",
            "",
            "---",
            "",
            "## 二、最强变量排行",
            "",
            "### 生物类型（按ROAS）",
            "",
        ]

        for i, c in enumerate(reports["memory"].get("top_creatures_by_roas", [])[:5], 1):
            lines.append(f"{i}. {c.get('value', 'N/A')} - ROAS: {c.get('roas_mean', 'N/A')}")

        lines.extend([
            "",
            "### 环境类型（按ROAS）",
            "",
        ])
        for i, e in enumerate(reports["memory"].get("top_environments_by_roas", [])[:5], 1):
            lines.append(f"{i}. {e.get('value', 'N/A')} - ROAS: {e.get('roas_mean', 'N/A')}")

        lines.extend([
            "",
            "---",
            "",
            "## 三、知识图谱",
            "",
            f"**图谱统计**: {json.dumps(reports['graph'].get('graph_summary', {}), ensure_ascii=False)}",
            "",
            "### Top ROAS 驱动因素",
            "",
        ])
        for i, f in enumerate(reports["graph"].get("top_roas_drivers", [])[:5], 1):
            lines.append(f"{i}. {f.get('feature', 'N/A')} - 影响: {f.get('impact', 'N/A')}")

        lines.extend([
            "",
            "---",
            "",
            "## 四、学习进度",
            "",
            f"```json\n{json.dumps(reports['learning'].get('learning_progress', {}), ensure_ascii=False, indent=2)}\n```",
            "",
            "---",
            "",
            "## 五、规则引擎",
            "",
            f"- **规则总数**: {len(self.intel.rules._rules)}",
            f"- **规则分类**: {len(self.intel.rules._rules)} 类",
            "",
        ])

        return "\n".join(lines)
