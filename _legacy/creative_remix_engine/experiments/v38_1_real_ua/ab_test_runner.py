"""V3.8.1 A/B Test Runner — Real UA Learning vs V3.8 Winner DNA

对比：
- Baseline: V3.8 Winner DNA Selector (AI预测 Buying Score)
- Variant: V3.8.1 Real UA Learning Selector (真实数据驱动)

目标：
- CTR +15%
- CPI -15%  
- ROI +20%
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from creative_remix_engine.config import OUTPUT_DIR
from creative_remix_engine.ua_feedback import CampaignImporter, MetricCalculator, DNAPerformanceMapper
from creative_remix_engine.performance_learning import (
    CreativePerformanceDB,
    PerformanceFeatureBuilder,
    CTRPredictor,
    CPIPredictor,
    ROIPredictor,
    WinnerUpdater,
    RealPerformanceScore,
)
from creative_remix_engine.winner_intelligence import CreativeValuePredictor


class V381ABTest:
    """V3.8.1 A/B Test 实验引擎"""

    def __init__(self):
        self.output_dir = OUTPUT_DIR / "v38_1"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # V3.8.1 组件
        self.importer = CampaignImporter()
        self.metric_calculator = MetricCalculator()
        self.dna_mapper = DNAPerformanceMapper()
        self.performance_db = CreativePerformanceDB(self.output_dir / "creative_performance_db.json")
        self.feature_builder = PerformanceFeatureBuilder()
        self.ctr_predictor = CTRPredictor()
        self.cpi_predictor = CPIPredictor()
        self.roi_predictor = ROIPredictor()
        self.winner_updater = WinnerUpdater()
        self.real_score = RealPerformanceScore(self.ctr_predictor, self.cpi_predictor, self.roi_predictor)

        # V3.8 组件（对比基准）
        self.v38_value_predictor = CreativeValuePredictor()

    def run_full_pipeline(self) -> dict:
        """运行完整的 V3.8.1 数据管道"""
        print("=" * 70)
        print("V3.8.1 Real UA Validation Layer — Full Pipeline")
        print("=" * 70)

        # Step 1: 导入数据
        print("\n[Step 1] Importing UA data...")
        import_result = self.importer.import_all_platforms(days=30)
        merged_data = import_result["merged"]
        print(f"  Total creatives: {len(merged_data)}")

        # Step 2: 计算指标
        print("\n[Step 2] Calculating metrics...")
        calculated = self.metric_calculator.calculate(merged_data)
        metrics_path = self.metric_calculator.save_calculated(calculated)
        print(f"  Metrics calculated: {len(calculated)}")
        print(f"  Saved to: {metrics_path}")

        # Step 3: DNA 与 Performance 关联
        print("\n[Step 3] Mapping DNA to Performance...")
        mapped = self.dna_mapper.map(merged_data, calculated)
        library_path = self.dna_mapper.save_library()
        print(f"  Mapped: {len(mapped)} creatives")
        print(f"  Library saved: {library_path}")

        # Step 4: 存入 Performance DB
        print("\n[Step 4] Saving to Performance DB...")
        for item in calculated:
            creative_id = item.get("creative_id", "")
            video_name = item.get("video_name", "")
            platform = item.get("platform", "")
            dna = item.get("raw", {}).get("dna", {})
            performance = item.get("performance", {})
            raw = item.get("raw", {})
            self.performance_db.add_performance(creative_id, video_name, platform, dna, performance, raw)
        print(f"  DB saved: {len(self.performance_db.data)} entries")

        # Step 5: 训练预测模型
        print("\n[Step 5] Training ML models...")
        self._train_models()

        # Step 6: 更新 Winner DNA
        print("\n[Step 6] Updating Winner DNA...")
        winner_update = self.winner_updater.update_from_performance_data(calculated)
        print(f"  Top patterns found: {len(winner_update['top_patterns'])}")

        # Step 7: 计算 Real Performance Score
        print("\n[Step 7] Calculating Real Performance Scores...")
        scores = self.real_score.batch_calculate(calculated)
        scores_path = self.real_score.save_scores(scores)
        print(f"  Scores calculated: {len(scores)}")
        print(f"  Saved to: {scores_path}")

        return {
            "import_result": import_result,
            "calculated_metrics": calculated,
            "mapped_data": mapped,
            "winner_update": winner_update,
            "performance_scores": scores,
        }

    def _train_models(self):
        """训练所有预测模型"""
        data = self.performance_db.data
        if len(data) < 20:
            print("  Not enough data for training, using baseline")
            return

        # 构建训练数据
        X = []
        y_ctr = []
        y_cpi = []
        y_d7_roi = []
        y_d30_roi = []

        for item in data:
            dna = item.get("dna", {})
            perf = item.get("performance", {})
            features = self.feature_builder.encode_dna(dna)

            X.append(features)
            y_ctr.append(perf.get("ctr", 0))
            y_cpi.append(perf.get("cpi", 0))
            y_d7_roi.append(perf.get("d7_roi", 0))
            y_d30_roi.append(perf.get("d30_roi", 0))

        X = self.feature_builder.normalize_features(np.array(X))
        y_ctr = np.array(y_ctr)
        y_cpi = np.array(y_cpi)
        y_d7_roi = np.array(y_d7_roi)
        y_d30_roi = np.array(y_d30_roi)

        # 过滤异常值
        mask = (y_cpi < 10) & (y_ctr > 0) & (y_d7_roi > -0.5)
        X = X[mask]
        y_ctr = y_ctr[mask]
        y_cpi = y_cpi[mask]
        y_d7_roi = y_d7_roi[mask]
        y_d30_roi = y_d30_roi[mask]

        print(f"  Training samples: {len(X)}")

        # 训练模型
        self.ctr_predictor.train(X, y_ctr)
        self.cpi_predictor.train(X, y_cpi)
        self.roi_predictor.train(X, y_d7_roi, y_d30_roi)

        # 保存模型
        self.ctr_predictor.save_model(self.output_dir / "ctr_model.json")
        self.cpi_predictor.save_model(self.output_dir / "cpi_model.json")
        self.roi_predictor.save_model(self.output_dir / "roi_model.json")

    def run_ab_test(self, n_per_group: int = 20) -> dict:
        """运行 A/B Test"""
        print("\n" + "=" * 70)
        print("V3.8.1 A/B Test — Real UA Learning vs V3.8")
        print("=" * 70)

        # 先运行完整管道获取数据
        pipeline_result = self.run_full_pipeline()
        mapped_data = pipeline_result["mapped_data"]
        scores = pipeline_result["performance_scores"]

        # Step 8: V3.8 评分（基准）
        print("\n[Step 8] Scoring with V3.8 Buying Score...")
        v38_scores = []
        for item in mapped_data:
            video_name = item.get("video_name", "")
            prediction = self.v38_value_predictor.predict(video_name)
            v38_scores.append({
                "creative_id": item.get("creative_id", ""),
                "video_name": video_name,
                "buying_score": prediction["buying_score"],
                "predicted_ctr": prediction["predicted_ctr"],
                "predicted_cpi": prediction["predicted_cpi"],
                "predicted_d7_roi": prediction["predicted_d7_roi"],
                "real_performance": item.get("performance", {}),
            })

        # Step 9: V3.8.1 评分（变体）
        print("\n[Step 9] Scoring with V3.8.1 Real Performance Score...")
        v381_scores = []
        for score in scores:
            creative_id = score.get("creative_id", "")
            # 找真实表现数据
            real_perf = {}
            for item in mapped_data:
                if item.get("creative_id") == creative_id:
                    real_perf = item.get("performance", {})
                    break
            v381_scores.append({
                "creative_id": creative_id,
                "video_name": score.get("video_name", ""),
                "performance_score": score.get("performance_score", 0),
                "ad_value": score.get("ad_value", 0),
                "grade": score.get("grade", ""),
                "real_performance": real_perf,
            })

        # Step 10: 选取 Top N
        print(f"\n[Step 10] Selecting Top {n_per_group} per group...")
        v38_top = sorted(v38_scores, key=lambda x: -x["buying_score"])[:n_per_group]
        v381_top = sorted(v381_scores, key=lambda x: -x["performance_score"])[:n_per_group]

        # Step 11: 计算真实指标对比
        print("\n[Step 11] Computing real metrics comparison...")
        v38_metrics = self._compute_group_metrics(v38_top)
        v381_metrics = self._compute_group_metrics(v381_top)

        # Step 12: 计算提升幅度
        print("\n[Step 12] Calculating improvement...")
        improvement = self._calc_improvement(v38_metrics, v381_metrics)

        # Step 13: 保存结果
        print("\n[Step 13] Saving results...")
        result = {
            "experiment": "V3.8.1 Real UA Learning A/B Test",
            "timestamp": datetime.now().isoformat(),
            "n_per_group": n_per_group,
            "v38": {
                "method": "V3.8 Winner DNA Selector (Buying Score)",
                "top_n": v38_top,
                "metrics": v38_metrics,
            },
            "v381": {
                "method": "V3.8.1 Real UA Learning Selector (Performance Score)",
                "top_n": v381_top,
                "metrics": v381_metrics,
            },
            "improvement": improvement,
            "winner_update": pipeline_result.get("winner_update", {}),
            "performance_db_summary": self.performance_db.get_summary(),
        }

        result_path = self.output_dir / "v38_1_ab_test_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"  Results saved: {result_path}")

        # 打印摘要
        self._print_summary(improvement)

        return result

    def _compute_group_metrics(self, top_list: List[dict]) -> dict:
        """计算组指标"""
        real_perfs = [item["real_performance"] for item in top_list if item["real_performance"]]

        if not real_perfs:
            return {
                "avg_ctr": 0,
                "avg_cpi": 0,
                "avg_d7_roi": 0,
                "avg_d30_roi": 0,
                "avg_ad_value": 0,
            }

        import numpy as np
        ctrs = [p["ctr"] for p in real_perfs]
        cpis = [p["cpi"] for p in real_perfs if p["cpi"] < 10]
        d7_rois = [p["d7_roi"] for p in real_perfs]
        d30_rois = [p["d30_roi"] for p in real_perfs]

        # 综合 Ad Value
        avg_ctr = np.mean(ctrs)
        avg_cpi = np.mean(cpis)
        avg_roi = np.mean(d7_rois)
        ad_value = avg_ctr * 15 + (1.0 / max(avg_cpi, 0.01)) * 10 + avg_roi * 100 * 3

        return {
            "avg_ctr": round(avg_ctr, 2),
            "avg_cpi": round(avg_cpi, 2),
            "avg_d7_roi": round(avg_roi, 3),
            "avg_d30_roi": round(np.mean(d30_rois), 3),
            "avg_ad_value": round(ad_value, 2),
            "sample_count": len(real_perfs),
        }

    @staticmethod
    def _calc_improvement(v38: dict, v381: dict) -> dict:
        """计算提升幅度"""
        return {
            "ctr_improvement": round((v381["avg_ctr"] - v38["avg_ctr"]) / max(v38["avg_ctr"], 0.1) * 100, 1),
            "cpi_improvement": round((v38["avg_cpi"] - v381["avg_cpi"]) / max(v38["avg_cpi"], 0.1) * 100, 1),
            "d7_roi_improvement": round((v381["avg_d7_roi"] - v38["avg_d7_roi"]) / max(v38["avg_d7_roi"], 0.01) * 100, 1),
            "d30_roi_improvement": round((v381["avg_d30_roi"] - v38["avg_d30_roi"]) / max(v38["avg_d30_roi"], 0.01) * 100, 1),
            "ad_value_improvement": round((v381["avg_ad_value"] - v38["avg_ad_value"]) / max(v38["avg_ad_value"], 1) * 100, 1),
            "targets": {
                "ctr_15pct": (v381["avg_ctr"] - v38["avg_ctr"]) / max(v38["avg_ctr"], 0.1) * 100 >= 15,
                "cpi_15pct": (v38["avg_cpi"] - v381["avg_cpi"]) / max(v38["avg_cpi"], 0.1) * 100 >= 15,
                "roi_20pct": (v381["avg_d7_roi"] - v38["avg_d7_roi"]) / max(v38["avg_d7_roi"], 0.01) * 100 >= 20,
            },
        }

    def _print_summary(self, improvement: dict):
        """打印摘要"""
        print("\n" + "=" * 70)
        print("A/B Test Summary")
        print("=" * 70)
        print(f"  CTR:     {improvement['ctr_improvement']:+.1f}% (target: +15%)")
        print(f"  CPI:     {improvement['cpi_improvement']:+.1f}% (target: -15%)")
        print(f"  D7 ROI:  {improvement['d7_roi_improvement']:+.1f}% (target: +20%)")
        print(f"  D30 ROI: {improvement['d30_roi_improvement']:+.1f}%")
        print(f"  Ad Value:{improvement['ad_value_improvement']:+.1f}%")
        print("\n  Targets:")
        print(f"    CTR +15%: {'PASS' if improvement['targets']['ctr_15pct'] else 'NOT MET'}")
        print(f"    CPI -15%: {'PASS' if improvement['targets']['cpi_15pct'] else 'NOT MET'}")
        print(f"    ROI +20%: {'PASS' if improvement['targets']['roi_20pct'] else 'NOT MET'}")


import numpy as np


def run_v381_ab_test(n: int = 20):
    """运行 V3.8.1 A/B Test"""
    tester = V381ABTest()
    return tester.run_ab_test(n_per_group=n)


if __name__ == "__main__":
    run_v381_ab_test(n=20)
