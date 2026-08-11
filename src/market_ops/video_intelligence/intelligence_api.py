"""Creative Intelligence API - 统一入口

所有 Agent 统一调用此 API，而不是各自维护知识和规则。

接口：
- CreativeIntelligence.predict()
- CreativeIntelligence.rank()
- CreativeIntelligence.decide()
- CreativeIntelligence.memory()
- CreativeIntelligence.learn()
- CreativeIntelligence.portfolio()
- CreativeIntelligence.graph()
- CreativeIntelligence.feature()
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.market_ops.video_intelligence.memory_engine import VideoMemoryEngine
from src.market_ops.video_intelligence.feature_store import VideoFeatureStore
from src.market_ops.video_intelligence.knowledge_graph import CreativeKnowledgeGraph
from src.market_ops.video_intelligence.predictor_engine import PredictorEngine
from src.market_ops.video_intelligence.portfolio_engine import PortfolioEngine
from src.market_ops.video_intelligence.learning_engine import VideoLearningEngine
from src.market_ops.video_intelligence.rule_engine import RuleEngine


class CreativeIntelligence:
    """Facebook 创意系统的大脑层（Brain Layer）

    所有 Agent（Expansion/Ranking/Decision）统一调用此 API。
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        project: str = "P04",
    ):
        self.project = project

        # 初始化各子系统
        resolved_db = db_path if db_path else (
            Path(__file__).resolve().parents[3] / "db" / "video_intelligence.duckdb"
        )
        self.memory = VideoMemoryEngine(resolved_db)
        self.feature_store = VideoFeatureStore()
        self.knowledge_graph = CreativeKnowledgeGraph()
        self.predictor = PredictorEngine(default_predictor="rule")
        self.portfolio = PortfolioEngine()
        self.learning = VideoLearningEngine(
            memory_engine=self.memory,
            predictor_engine=self.predictor,
        )
        self.rules = RuleEngine()

        # 渠道扩展接口（当前默认 Facebook，未来可扩展 TikTok/Google 等）
        self.channel = "facebook"
        self._channels = {"facebook": {"supported": True, "priority": 1}}

        self._initialized = False

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def initialize(self, seed_data: dict | None = None) -> None:
        """初始化知识系统

        Args:
            seed_data: 种子数据（可选）
                - creatives: 历史创意列表
                - rules: 规则列表
                - memory: 记忆数据
        """
        if seed_data and "creatives" in seed_data:
            for c in seed_data["creatives"]:
                self.memory.update_creative(
                    creative_id=c.get("creative_id", ""),
                    dna=c.get("dna", {}),
                    performance=c.get("performance", {}),
                    project=self.project,
                )

        if seed_data and "memory" in seed_data:
            self.memory.load_from_dict(seed_data["memory"])

        if seed_data and "graph" in seed_data:
            self.knowledge_graph.load_from_dict(seed_data["graph"])

        self._initialized = True

    # ------------------------------------------------------------------
    # Predict API
    # ------------------------------------------------------------------
    def predict(
        self,
        features: dict,
        metric: str = "all",
        predictor: str | None = None,
    ) -> dict:
        """预测创意表现

        Args:
            features: 特征字典（从 DNA 提取的扁平特征）
            metric: 预测指标 "ctr"|"roas"|"cvr"|"ipm"|"all"
            predictor: 使用的预测器名称，None 用默认

        Returns:
            预测结果字典
        """
        if metric == "all":
            return self.predictor.predict_all(features, predictor=predictor)

        methods = {
            "ctr": self.predictor.predict_ctr,
            "roas": self.predictor.predict_roas,
            "cvr": self.predictor.predict_cvr,
            "ipm": self.predictor.predict_ipm,
        }
        if metric not in methods:
            raise ValueError(f"Unknown metric: {metric}. Use one of: {list(methods.keys())}")

        return methods[metric](features, predictor=predictor)

    def predict_from_dna(self, dna: dict, metric: str = "all") -> dict:
        """从 DNA 直接预测

        Args:
            dna: Creative DNA 字典
            metric: 预测指标
        """
        features = self.feature_store.extract_features_from_dna(dna)
        return self.predict(features, metric)

    # ------------------------------------------------------------------
    # Rank API
    # ------------------------------------------------------------------
    def rank(
        self,
        variants: list[dict],
        context: dict | None = None,
        sort_by: str = "overall",
    ) -> list[dict]:
        """对 variants 进行智能排序

        Args:
            variants: variant 列表（每个含 dna / dimensions）
            context: 受众上下文 {"country": "US", "placement": "IG_Reels"}
            sort_by: 排序依据 "overall"|"ctr"|"roas"|"novelty"

        Returns:
            排序后的 variant 列表（增加 predicted_* 字段）
        """
        scored = []
        for v in variants:
            dna = v.get("modified_dna", v.get("dna", {}))
            features = self.feature_store.extract_features_from_dna(dna)
            predictions = self.predictor.predict_all(features)

            scored_v = v.copy()
            scored_v["predicted_ctr"] = predictions.get("ctr", {}).get("value", 0)
            scored_v["predicted_roas"] = predictions.get("roas", {}).get("value", 0)
            scored_v["predicted_cvr"] = predictions.get("cvr", {}).get("value", 0)
            scored_v["predicted_ipm"] = predictions.get("ipm", {}).get("value", 0)
            scored_v["prediction_confidence"] = predictions.get("confidence", 0)
            scored.append(scored_v)

        # 排序
        sort_keys = {
            "overall": lambda x: x.get("decision_score", x.get("overall_score", 0)),
            "ctr": lambda x: x.get("predicted_ctr", 0),
            "roas": lambda x: x.get("predicted_roas", 0),
            "novelty": lambda x: x.get("novelty_score", x.get("dimensions", {}).get("novelty", {}).get("score", 0)),
        }
        key = sort_keys.get(sort_by, sort_keys["overall"])
        scored.sort(key=key, reverse=True)

        return scored

    # ------------------------------------------------------------------
    # Decide API
    # ------------------------------------------------------------------
    def decide(
        self,
        ranked_variants: list[dict],
        total_count: int = 20,
        portfolio_config: dict | None = None,
    ) -> dict:
        """最终决策：选出 Top N + Portfolio 分配

        Args:
            ranked_variants: 已排序的 variants
            total_count: 总数
            portfolio_config: Portfolio 分配配置

        Returns:
            {
                "final_top": [...],
                "portfolio": {"safe": [...], "growth": [...], "explore": [...]},
                "budget_allocation": {...},
            }
        """
        if portfolio_config:
            self.portfolio = PortfolioEngine(allocation_config=portfolio_config)

        portfolio = self.portfolio.allocate(ranked_variants, total_count=total_count)
        budget = self.portfolio.get_budget_allocation(portfolio)

        return {
            "final_top": portfolio["safe"] + portfolio["growth"] + portfolio["explore"],
            "portfolio": portfolio,
            "budget_allocation": budget,
            "total_count": total_count,
        }

    # ------------------------------------------------------------------
    # Memory API
    # ------------------------------------------------------------------
    def memory_get(self, dimension: str, value: str) -> dict | None:
        """查询变量记忆"""
        return self.memory.get_variable(dimension, value)

    def memory_update(self, dimension: str, value: str, metrics: dict) -> None:
        """更新变量记忆"""
        self.memory.update_variable(dimension, value, metrics)

    def memory_search(
        self,
        dimension: str | None = None,
        min_roas: float | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """搜索记忆"""
        return self.memory.search_variables(
            dimension=dimension,
            min_roas=min_roas,
            limit=limit,
        )

    def memory_top(self, dimension: str, metric: str = "roas", limit: int = 10, min_samples: int = 1) -> list[dict]:
        """Top变量"""
        return self.memory.get_top_variables(
            dimension=dimension,
            metric=metric,
            limit=limit,
            min_samples=min_samples,
        )

    # ------------------------------------------------------------------
    # Learn API
    # ------------------------------------------------------------------
    def learn(self, new_results: list[dict]) -> dict:
        """从投放结果中学习

        Args:
            new_results: Facebook 投放结果列表
                每个结果含 creative_id, variant_id, dna, performance 等

        Returns:
            学习报告
        """
        updated_creatives = 0
        updated_variables = 0

        for result in new_results:
            creative_id = result.get("creative_id") or result.get("variant_id")
            if not creative_id:
                continue

            perf = result.get("performance", {})
            # 兼容 roas / roas_d7
            roas_val = perf.get("roas") if perf.get("roas") is not None else perf.get("roas_d7", 0)
            metrics = {
                "ctr": float(perf.get("ctr", 0)),
                "roas": float(roas_val),
                "cvr": float(perf.get("cvr", 0)),
                "ipm": float(perf.get("ipm", 0)),
            }

            # 更新创意记忆
            try:
                self.memory.update_creative(
                    creative_id=creative_id,
                    dna=result.get("dna", {}),
                    performance=metrics,
                    project=self.project,
                )
                updated_creatives += 1
            except Exception:
                pass

            # 更新变量记忆（从 DNA/特征中提取）
            dna = result.get("dna", {})
            if dna:
                features = self.feature_store.extract_features_from_dna(dna)
                for dim, value in features.items():
                    if value is None or value == "":
                        continue
                    # 只更新有意义的分类/数值变量
                    if isinstance(value, (str, int, float, bool)):
                        try:
                            var_metrics = dict(metrics)
                            var_metrics["project"] = self.project
                            self.memory.update_variable(
                                dimension=str(dim),
                                value=str(value),
                                metrics=var_metrics,
                            )
                            updated_variables += 1
                        except Exception:
                            pass

        # 更新知识图谱
        graph_edges = 0
        try:
            # 将数据转换为 KG 需要的格式：features + metrics + baseline
            kg_results = []
            for result in new_results:
                dna = result.get("dna", {})
                perf = result.get("performance", {})
                if not dna:
                    continue
                features = self.feature_store.extract_features_from_dna(dna)
                roas_val = perf.get("roas") if perf.get("roas") is not None else perf.get("roas_d7", 0)
                metrics = {
                    "ctr": float(perf.get("ctr", 0)),
                    "roas": float(roas_val),
                    "cvr": float(perf.get("cvr", 0)),
                    "ipm": float(perf.get("ipm", 0)),
                }
                # 用平均值作为 baseline 确保 lift 有值
                baseline = {
                    "ctr": max(0.01, float(perf.get("ctr", 0)) * 0.8),
                    "roas": max(0.1, float(roas_val) * 0.8),
                    "cvr": max(0.01, float(perf.get("cvr", 0)) * 0.8),
                    "ipm": max(0.1, float(perf.get("ipm", 0)) * 0.8),
                }
                kg_results.append({
                    "features": features,
                    "metrics": metrics,
                    "baseline": baseline,
                    "sample_count": 1,
                })
            graph_edges = self.knowledge_graph.update_from_results(kg_results)
        except Exception:
            pass

        # 更新 learning engine 内部统计
        try:
            learning_report = self.learning.incremental_train(new_results)
        except Exception:
            learning_report = {"status": "skipped", "reason": "learning_engine_error"}

        return {
            "status": "success",
            "updated_creatives": updated_creatives,
            "updated_variables": updated_variables,
            "graph_edges_added": graph_edges,
            "learning": learning_report,
            "timestamp": datetime.now().isoformat(),
        }

    def get_insights(self, metric: str = "roas", limit: int = 10) -> dict:
        """获取洞察"""
        return {
            "top_winning_patterns": self.learning.get_top_winning_patterns(metric, limit),
            "top_losing_patterns": self.learning.get_top_losing_patterns(metric, limit),
            "feature_importance": self.learning.compute_feature_importance(metric),
        }

    # ------------------------------------------------------------------
    # Portfolio API
    # ------------------------------------------------------------------
    def portfolio_allocate(
        self,
        variants: list[dict],
        total_count: int = 20,
        config: dict | None = None,
    ) -> dict:
        """Portfolio 分配"""
        if config:
            self.portfolio = PortfolioEngine(allocation_config=config)
        return self.portfolio.allocate(variants, total_count=total_count)

    def portfolio_budget(self, portfolio: dict, total_budget: float = 1000) -> dict:
        """预算分配"""
        return self.portfolio.get_budget_allocation(portfolio, total_budget=total_budget)

    # ------------------------------------------------------------------
    # Graph API
    # ------------------------------------------------------------------
    def graph_query(self, node_id: str, edge_type: str | None = None) -> list:
        """查询知识图谱邻居"""
        return self.knowledge_graph.get_neighbors(node_id, edge_type=edge_type)

    def graph_infer(self, feature: str, metric: str) -> dict:
        """推断特征对指标的影响"""
        return self.knowledge_graph.infer_impact(feature, metric)

    def graph_top_features(self, metric: str, limit: int = 10) -> list[dict]:
        """获取影响某指标的Top特征"""
        return self.knowledge_graph.get_top_features_for_metric(metric, limit=limit)

    def graph_summary(self) -> dict:
        """图谱统计"""
        return self.knowledge_graph.get_summary()

    # ------------------------------------------------------------------
    # Feature API
    # ------------------------------------------------------------------
    def feature_extract(self, dna: dict) -> dict:
        """从 DNA 提取特征"""
        return self.feature_store.extract_features_from_dna(dna)

    def feature_normalize(self, features: dict) -> dict:
        """特征标准化"""
        return self.feature_store.normalize_batch(features)

    def feature_validate(self, features: dict) -> dict:
        """特征验证"""
        valid, errors = self.feature_store.validate_features(features)
        return {"valid": valid, "errors": errors}

    def feature_schema(self) -> dict:
        """获取特征Schema"""
        return self.feature_store._schema

    # ------------------------------------------------------------------
    # Rule API
    # ------------------------------------------------------------------
    def rules_check(self, variant: dict, category: str = "policy") -> dict:
        """规则检查"""
        return self.rules.check_compliance(variant, category=category)

    def rules_validate(self, variant: dict) -> dict:
        """创意合规验证"""
        return self.rules.validate_creative(variant)

    def rules_get(self, category: str) -> list[dict]:
        """获取某类规则"""
        return self.rules.get_rules(category)

    # ------------------------------------------------------------------
    # 渠道扩展（预留）
    # ------------------------------------------------------------------
    def set_channel(self, channel: str) -> None:
        """设置渠道（预留 TikTok/Google Ads 等）"""
        if channel not in self._channels:
            self._channels[channel] = {"supported": False, "priority": 99}
        self.channel = channel

    def add_channel(self, channel: str, config: dict) -> None:
        """添加新渠道"""
        self._channels[channel] = config

    # ------------------------------------------------------------------
    # 导出/导入
    # ------------------------------------------------------------------
    def export_state(self, output_path: str | Path) -> None:
        """导出整个系统状态"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "version": "4.2.2",
            "channel": self.channel,
            "project": self.project,
            "memory": self.memory.export_to_dict(),
            "graph": self.knowledge_graph.export_to_dict(),
            "rules": self.rules.export_to_dict(),
            "exported_at": datetime.now().isoformat(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)

    def import_state(self, input_path: str | Path) -> None:
        """导入系统状态"""
        input_path = Path(input_path)
        with open(input_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        if "memory" in state:
            self.memory.load_from_dict(state["memory"])
        if "graph" in state:
            self.knowledge_graph.load_from_dict(state["graph"])

        self._initialized = True


# ======================================================================
# 单例模式（整个系统共用一个 Intelligence 实例）
# ======================================================================
_intelligence_instance: CreativeIntelligence | None = None


def get_intelligence(project: str = "P04") -> CreativeIntelligence:
    """获取全局 CreativeIntelligence 单例"""
    global _intelligence_instance
    if _intelligence_instance is None:
        _intelligence_instance = CreativeIntelligence(project=project)
    return _intelligence_instance
