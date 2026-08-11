"""Facebook Creative Decision Engine - V4.2.1 主入口

串联所有决策模块，完成最终决策。
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.market_ops.creative_decision.performance_predictor import (
    PerformancePredictor, PerformancePrediction,
)
from src.market_ops.creative_decision.audience_context import (
    AudienceContextEngine, AudienceScore,
)
from src.market_ops.creative_decision.diversity_optimizer import (
    CreativeDiversityOptimizer, ClusterResult,
)
from src.market_ops.creative_decision.fatigue_predictor import (
    CreativeFatiguePredictor, FatiguePrediction,
)
from src.market_ops.creative_decision.budget_recommender import (
    BudgetPlacementCampaignRecommender,
    BudgetRecommendation, PlacementRecommendation, CampaignRecommendation,
)
from src.market_ops.creative_decision.testing_strategy import (
    TestingStrategyGenerator, CampaignPlan,
)
from src.market_ops.creative_decision.learning_interface import (
    LearningInterface, LearningUpdate,
)


class DecisionEngine:
    """Facebook Creative Decision Engine
    
    输入: V4.2 Ranking 结果
    输出: 最终决策（Top20 + 预算 + 版位 + Campaign + 测试计划）
    """

    # Decision Score 权重（可配置）
    DECISION_WEIGHTS = {
        "ranking": 0.40,
        "performance": 0.30,
        "audience": 0.10,
        "fatigue": 0.10,
        "portfolio": 0.10,
    }

    def __init__(self):
        self.perf_predictor = PerformancePredictor()
        self.audience_engine = AudienceContextEngine()
        self.diversity_optimizer = CreativeDiversityOptimizer()
        self.fatigue_predictor = CreativeFatiguePredictor()
        self.bpc_recommender = BudgetPlacementCampaignRecommender()
        self.testing_generator = TestingStrategyGenerator()
        self.learning = LearningInterface()

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(
        self,
        ranking_dir: str | Path,
        context: dict | None = None,
        history: list[dict] | None = None,
        output_dir: str | Path = "",
    ) -> dict:
        """运行完整决策流程

        Args:
            ranking_dir: V4.2 creative_ranking/ 输出目录
            context: 受众上下文 {"country": "US", "age": "25-34", ...}
            history: 历史投放数据（可选）
            output_dir: 本 Agent 输出目录
        """
        t0 = datetime.now()
        ranking_dir = Path(ranking_dir)
        self.output_dir = Path(output_dir) if output_dir else (
            ROOT / "output" / "creative_decision"
        )
        context = context or {"country": "US", "placement": "IG_Reels", "os": "iOS"}

        print("=" * 100)
        print("🎯 Facebook Creative Decision Engine - V4.2.1")
        print("=" * 100)

        # Step 1: 加载 Ranking 结果
        print("\n[Step 1] 加载 Ranking 结果...")
        rankings = self._load_rankings(ranking_dir)
        if not rankings:
            print("  ❌ 无 Ranking 数据")
            return {}
        print(f"  ✅ 加载了 {len(rankings)} 个 Ranked Variants")

        # Step 2: 性能预测
        print("\n[Step 2] Performance Prediction...")
        perf_predictions = self.perf_predictor.predict_batch(rankings)
        perf_map = {p.variant_id: p for p in perf_predictions}
        print(f"  ✅ 预测完成: CTR/CVR/IPM/ROAS")

        # Step 3: 受众上下文
        print(f"\n[Step 3] Audience Context ({context})...")
        audience_scores = self.audience_engine.rerank_for_context(rankings, context)
        audience_map = {s.variant_id: s for s in audience_scores}
        print(f"  ✅ 上下文调整完成")

        # Step 4: 疲劳预测
        print("\n[Step 4] Creative Fatigue Prediction...")
        if history:
            self.learning.load_history(history)
        fatigue_predictions = self.fatigue_predictor.predict_batch(rankings, history)
        fatigue_map = {p.variant_id: p for p in fatigue_predictions}
        print(f"  ✅ 疲劳预测完成")

        # Step 5: 多样性优化（聚类 + 选 Top20）
        print("\n[Step 5] Diversity Optimization...")
        clusters = self.diversity_optimizer.cluster(rankings)
        diverse_top = self.diversity_optimizer.select_diverse_top(rankings, top_n=20, per_cluster=2)
        print(f"  ✅ 聚类: {len(clusters)} 个 Clusters")
        print(f"  ✅ 多样性 Top20: {[v['variant_id'] for v in diverse_top[:5]]}...")

        # Step 6: Budget / Placement / Campaign 推荐
        print("\n[Step 6] Budget / Placement / Campaign Recommendation...")
        bpc_results = {}
        for v in diverse_top:
            vid = v["variant_id"]
            bpc_results[vid] = self.bpc_recommender.recommend_all(v)
        print(f"  ✅ 推荐完成: {len(bpc_results)} 个 Variants")

        # Step 7: 计算 Decision Score
        print("\n[Step 7] 计算 Decision Score...")
        decisions = self._compute_decision_scores(
            rankings, perf_map, audience_map, fatigue_map, diverse_top
        )
        print(f"  ✅ Decision Score 计算完成")
        print(f"  🥇 TOP Decision: {decisions[0]['variant_id']} = {decisions[0]['decision_score']:.1f}")

        # Step 8: 生成测试计划
        print("\n[Step 8] 生成 A/B Test 计划...")
        test_plan = self.testing_generator.generate_test_plan(diverse_top)
        print(f"  ✅ 生成 {len(test_plan)} 个 Campaign 测试计划")

        # Step 9: 学习接口（预留）
        print("\n[Step 9] Learning Interface...")
        learning_update = self.learning.learn(rankings)
        print(f"  ✅ 学习接口调用完成（预留）")

        # Step 10: 输出文件
        print("\n[Step 10] 输出决策结果...")
        self._write_output(
            decisions=decisions,
            diverse_top=diverse_top,
            clusters=clusters,
            perf_map=perf_map,
            audience_map=audience_map,
            fatigue_map=fatigue_map,
            bpc_results=bpc_results,
            test_plan=test_plan,
            learning_update=learning_update,
            context=context,
        )

        elapsed = (datetime.now() - t0).total_seconds()
        print(f"\n{'=' * 100}")
        print(f"✅ Decision Engine 完成! 耗时 {elapsed:.1f}s")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"{'=' * 100}")

        return {
            "total_ranked": len(rankings),
            "final_top20": [d["variant_id"] for d in decisions[:20]],
            "clusters": len(clusters),
            "test_campaigns": len(test_plan),
            "output_dir": str(self.output_dir),
            "elapsed_sec": elapsed,
        }

    # ------------------------------------------------------------------
    # 加载数据
    # ------------------------------------------------------------------
    def _load_rankings(self, ranking_dir: Path) -> list[dict]:
        """加载 V4.2 ranking.json"""
        ranking_file = ranking_dir / "ranking.json"
        if not ranking_file.exists():
            print(f"  ❌ ranking.json 不存在: {ranking_file}")
            return []
        with open(ranking_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # 计算 Decision Score
    # ------------------------------------------------------------------
    def _compute_decision_scores(
        self,
        rankings: list[dict],
        perf_map: dict[str, PerformancePrediction],
        audience_map: dict[str, AudienceScore],
        fatigue_map: dict[str, FatiguePrediction],
        diverse_top: list[dict],
    ) -> list[dict]:
        """计算每个 Variant 的 Decision Score"""
        diverse_ids = {v["variant_id"] for v in diverse_top}
        decisions = []

        for r in rankings:
            vid = r["variant_id"]
            if vid not in diverse_ids:
                continue  # 只处理多样性筛选后的

            # 基础分数
            ranking_score = r.get("overall_score", 0)
            perf = perf_map.get(vid)
            perf_score = perf.overall_performance if perf else 50.0
            audience = audience_map.get(vid)
            audience_score = audience.adjusted_score if audience else ranking_score
            fatigue = fatigue_map.get(vid)
            # fatigue_risk 越高 = 越疲劳 = 分数越低
            fatigue_score = 100 - (fatigue.fatigue_risk if fatigue else 50.0)
            # portfolio: 在 diverse_top 中的排名越高 = portfolio 分数越高
            portfolio_rank = next((i for i, v in enumerate(diverse_top) if v["variant_id"] == vid), 99)
            portfolio_score = max(0, 100 - portfolio_rank * 5)

            # Decision Score 加权
            decision_score = (
                ranking_score * self.DECISION_WEIGHTS["ranking"]
                + perf_score * self.DECISION_WEIGHTS["performance"]
                + audience_score * self.DECISION_WEIGHTS["audience"]
                + fatigue_score * self.DECISION_WEIGHTS["fatigue"]
                + portfolio_score * self.DECISION_WEIGHTS["portfolio"]
            )

            decisions.append({
                "variant_id": vid,
                "decision_score": round(decision_score, 1),
                "ranking_score": round(ranking_score, 1),
                "performance_score": round(perf_score, 1),
                "audience_score": round(audience_score, 1),
                "fatigue_score": round(fatigue_score, 1),
                "portfolio_score": round(portfolio_score, 1),
                "changed_dimension": r.get("changed_dimension", ""),
                "old_value": r.get("old_value", ""),
                "new_value": r.get("new_value", ""),
                "risk_level": r.get("risk_level", ""),
                "dimensions": r.get("dimensions", {}),
            })

        # 按 Decision Score 降序排序
        decisions.sort(key=lambda x: x["decision_score"], reverse=True)
        return decisions

    # ------------------------------------------------------------------
    # 输出文件
    # ------------------------------------------------------------------
    def _write_output(
        self,
        decisions: list[dict],
        diverse_top: list[dict],
        clusters: list[ClusterResult],
        perf_map: dict,
        audience_map: dict,
        fatigue_map: dict,
        bpc_results: dict,
        test_plan: list[CampaignPlan],
        learning_update: LearningUpdate,
        context: dict,
    ):
        """按 PRD 输出所有文件"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. final_top20.json
        final_top20 = decisions[:20]
        with open(self.output_dir / "final_top20.json", "w", encoding="utf-8") as f:
            json.dump(final_top20, f, indent=2, ensure_ascii=False, default=str)
        print(f"  🏆 final_top20.json → {self.output_dir / 'final_top20.json'}")

        # 2. portfolio.json - 完整决策 Portfolio
        portfolio = []
        for d in decisions:
            vid = d["variant_id"]
            bpc = bpc_results.get(vid, {})
            portfolio.append({
                "variant_id": vid,
                "decision_score": d["decision_score"],
                "ranking_score": d["ranking_score"],
                "performance_score": d["performance_score"],
                "audience_score": d["audience_score"],
                "fatigue_score": d["fatigue_score"],
                "changed_dimension": d["changed_dimension"],
                "new_value": d["new_value"],
                "risk_level": d["risk_level"],
                "budget": asdict(bpc.get("budget", BudgetRecommendation(variant_id=vid, tier="C"))) if bpc else {},
                "placement": asdict(bpc.get("placement", PlacementRecommendation(variant_id=vid))) if bpc else {},
                "campaign": asdict(bpc.get("campaign", CampaignRecommendation(variant_id=vid))) if bpc else {},
            })
        with open(self.output_dir / "portfolio.json", "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False, default=str)
        print(f"  📊 portfolio.json → {self.output_dir / 'portfolio.json'}")

        # 3. cluster.json
        cluster_data = []
        for c in clusters:
            cluster_data.append({
                "cluster_id": c.cluster_id,
                "cluster_features": c.cluster_features,
                "members": c.members,
                "top_variant": c.top_variant,
                "top_score": c.top_score,
            })
        with open(self.output_dir / "cluster.json", "w", encoding="utf-8") as f:
            json.dump(cluster_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"  🔗 cluster.json → {self.output_dir / 'cluster.json'}")

        # 4. prediction.json
        predictions = []
        for vid, perf in perf_map.items():
            predictions.append(asdict(perf))
        with open(self.output_dir / "prediction.json", "w", encoding="utf-8") as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False, default=str)
        print(f"  🔮 prediction.json → {self.output_dir / 'prediction.json'}")

        # 5. budget.json
        budgets = {vid: asdict(bpc.get("budget", BudgetRecommendation(variant_id=vid, tier="C"))) for vid, bpc in bpc_results.items()}
        with open(self.output_dir / "budget.json", "w", encoding="utf-8") as f:
            json.dump(budgets, f, indent=2, ensure_ascii=False, default=str)
        print(f"  💰 budget.json → {self.output_dir / 'budget.json'}")

        # 6. placement.json
        placements = {vid: asdict(bpc.get("placement", PlacementRecommendation(variant_id=vid))) for vid, bpc in bpc_results.items()}
        with open(self.output_dir / "placement.json", "w", encoding="utf-8") as f:
            json.dump(placements, f, indent=2, ensure_ascii=False, default=str)
        print(f"  📍 placement.json → {self.output_dir / 'placement.json'}")

        # 7. campaign.json
        campaigns = {vid: asdict(bpc.get("campaign", CampaignRecommendation(variant_id=vid))) for vid, bpc in bpc_results.items()}
        with open(self.output_dir / "campaign.json", "w", encoding="utf-8") as f:
            json.dump(campaigns, f, indent=2, ensure_ascii=False, default=str)
        print(f"  📢 campaign.json → {self.output_dir / 'campaign.json'}")

        # 8. testing_plan.json
        test_data = []
        for cp in test_plan:
            test_data.append({
                "campaign_id": cp.campaign_id,
                "campaign_name": cp.campaign_name,
                "campaign_type": cp.campaign_type,
                "objective": cp.objective,
                "total_budget_usd": cp.total_budget_usd,
                "adsets": [
                    {
                        "adset_id": a.adset_id,
                        "adset_name": a.adset_name,
                        "budget_usd": a.budget_usd,
                        "cells": [
                            {"cell_id": c.cell_id, "variant_id": c.variant_id,
                             "changed_dimension": c.changed_dimension, "changed_value": c.changed_value}
                            for c in a.cells
                        ],
                    }
                    for a in cp.adsets
                ],
            })
        with open(self.output_dir / "testing_plan.json", "w", encoding="utf-8") as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"  🧪 testing_plan.json → {self.output_dir / 'testing_plan.json'}")

        # 9. decision_report.md
        report = self._build_report(
            decisions, clusters, test_plan, context, learning_update
        )
        with open(self.output_dir / "decision_report.md", "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  📄 decision_report.md → {self.output_dir / 'decision_report.md'}")

    def _build_report(
        self, decisions, clusters, test_plan, context, learning_update
    ) -> str:
        """生成 decision_report.md"""
        lines = [
            "# Facebook Creative Decision Report (V4.2.1)",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 项目: P04 Merge Witches",
            f"> 受众上下文: {context}",
            "",
            "---",
            "",
            "## 一、Decision Score 模型",
            "",
            "| 维度 | 权重 | 说明 |",
            "|------|------|------|",
        ]
        for key, w in self.DECISION_WEIGHTS.items():
            lines.append(f"| {key} | {w*100:.0f}% | {'核心评分' if w >= 0.3 else '辅助评分'} |")

        lines.extend(["", "---", "", "## 二、Final TOP 20 决策", ""])
        lines.append("| 排名 | Variant | Decision | Ranking | Performance | Audience | Fatigue | Portfolio | 变更 |")
        lines.append("|------|---------|----------|---------|-------------|----------|---------|-----------|------|")
        for rank, d in enumerate(decisions[:20], 1):
            lines.append(
                f"| {rank} | {d['variant_id']} | {d['decision_score']:.1f} | "
                f"{d['ranking_score']:.1f} | {d['performance_score']:.1f} | "
                f"{d['audience_score']:.1f} | {d['fatigue_score']:.1f} | "
                f"{d['portfolio_score']:.1f} | {d['changed_dimension']} |"
            )

        lines.extend(["", "---", "", "## 三、聚类分布", ""])
        lines.append("| Cluster | 特征 | 成员数 | Top Variant | Top Score |")
        lines.append("|---------|------|--------|-------------|-----------|")
        for c in clusters[:10]:
            features = ", ".join(f"{k}={v}" for k, v in c.cluster_features.items())
            lines.append(
                f"| {c.cluster_id} | {features[:40]} | {len(c.members)} | "
                f"{c.top_variant} | {c.top_score:.1f} |"
            )

        lines.extend(["", "---", "", "## 四、A/B Test 计划", ""])
        for cp in test_plan[:5]:
            lines.append(f"### {cp.campaign_name}")
            lines.append(f"- Campaign Type: {cp.campaign_type}")
            lines.append(f"- Objective: {cp.objective}")
            lines.append(f"- Total Budget: ${cp.total_budget_usd}")
            for a in cp.adsets:
                cells_desc = " vs ".join(f"{c.cell_id}({c.changed_value})" for c in a.cells)
                lines.append(f"  - {a.adset_name}: {cells_desc} | ${a.budget_usd}")
            lines.append("")

        lines.extend([
            "", "---", "", "## 五、决策建议", "",
            "### 立即生成（Decision Score >= 80）",
            "",
            "### 优先测试（Decision Score 70-79）",
            "",
            "### 谨慎测试（Decision Score 60-69）",
            "",
            "### 不建议（Decision Score < 60）",
        ])

        return "\n".join(lines)


# ======================================================================
# CLI 入口
# ======================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Facebook Creative Decision Engine V4.2.1")
    parser.add_argument("--ranking-dir", type=str,
                        default=str(ROOT / "output" / "creative_ranking"),
                        help="V4.2 Ranking 输出目录")
    parser.add_argument("--output-dir", type=str, default="",
                        help="本 Agent 输出目录")
    parser.add_argument("--country", type=str, default="US",
                        help="目标国家")
    parser.add_argument("--placement", type=str, default="IG_Reels",
                        help="目标版位")
    args = parser.parse_args()

    context = {
        "country": args.country,
        "placement": args.placement,
        "os": "iOS",
        "age": "25-34",
        "gender": "F",
    }

    engine = DecisionEngine()
    result = engine.run(
        ranking_dir=args.ranking_dir,
        context=context,
        output_dir=args.output_dir,
    )
    print(f"\n🎯 结果: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
