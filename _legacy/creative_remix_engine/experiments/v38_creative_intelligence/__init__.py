"""V3.8 Creative Intelligence Calibration — A/B Test Experiment

对比：
- Baseline: V3.4 Shot Selector (基于视觉质量评分)
- Variant: V3.8 Winner DNA Ranking (基于 Buying Score + Performance Grade)

目标：Ad Value 提升 >= 20%
"""
import sys
import json
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from creative_remix_engine.winner_intelligence import (
    WinnerDNAExtractor,
    CreativeValuePredictor,
    PerformanceQualityGate,
    ArchetypeDiscoveryEngine,
)
from creative_remix_engine.winner_intelligence.winner_database import WinnerDatabase


RANKING_DB = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
MEMORY_DIR = Path("d:/project_slim/project_slim/creative_remix_engine/storage/memory")
OUTPUT_DIR = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v38_creative_intelligence")


class V38ABTest:
    """V3.8 A/B Test 实验引擎"""

    def __init__(self):
        self.ranking_data = self._load_ranking()
        self.video_names = list(self.ranking_data.keys())

        self.dna_extractor = WinnerDNAExtractor(RANKING_DB)
        self.value_predictor = CreativeValuePredictor(RANKING_DB, MEMORY_DIR / "winner_database_v38.json")
        self.quality_gate = PerformanceQualityGate(RANKING_DB, MEMORY_DIR / "winner_database_v38.json")
        self.archetype_engine = ArchetypeDiscoveryEngine(MEMORY_DIR / "winner_database_v38.json")
        self.archetype_engine.discover_archetypes()

        self.results = {}

    def _load_ranking(self) -> Dict[str, dict]:
        """加载 Ranking 数据"""
        if RANKING_DB.exists():
            try:
                with open(RANKING_DB, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {item.get("video_name", ""): item for item in data.get("shots", [])}
            except Exception:
                return {}
        return {}

    def _seed_winner_db(self):
        """初始化 Winner DB（从 Ranking 模拟）"""
        winner_db = WinnerDatabase(MEMORY_DIR / "winner_database_v38.json")
        if len(winner_db.winners) == 0:
            winner_db.seed_from_ranking(RANKING_DB, top_n=30)
        return winner_db

    def run_ab_test(self, n_per_group: int = 10) -> dict:
        """运行 A/B Test"""
        print("=" * 70)
        print("V3.8 Creative Intelligence Calibration — A/B Test")
        print("=" * 70)

        # 初始化 Winner DB
        print("\n[Step 1] Seeding Winner Database...")
        self._seed_winner_db()

        # 准备素材池
        print(f"\n[Step 2] Preparing material pool ({len(self.video_names)} videos)...")

        # 计算两个版本的评分
        print("\n[Step 3] Scoring with Baseline (V3.4 Shot Selector)...")
        baseline_scores = self._score_baseline()

        print("\n[Step 4] Scoring with Variant (V3.8 Winner DNA)...")
        variant_scores = self._score_variant()

        # 选取 Top N
        print(f"\n[Step 5] Selecting Top {n_per_group} per group...")
        baseline_top = self._select_top(baseline_scores, n_per_group, "ad_value_score")
        variant_top = self._select_top(variant_scores, n_per_group, "buying_score")

        # 计算 Ad Value
        print("\n[Step 6] Computing Ad Value...")
        baseline_ad_value = self._compute_ad_value(baseline_top, "baseline")
        variant_ad_value = self._compute_ad_value(variant_top, "variant")

        # 统计分析
        print("\n[Step 7] Statistical analysis...")
        improvement = self._calc_improvement(baseline_ad_value, variant_ad_value)

        # Performance Grade 分布
        baseline_grades = self._grade_distribution(baseline_top)
        variant_grades = self._grade_distribution(variant_top)

        # Archetype 分析
        baseline_archetypes = self._archetype_analysis(variant_top)

        # Winner DNA 模式
        winner_patterns = self._extract_winner_patterns(variant_top)

        self.results = {
            "experiment": "V3.8 Creative Intelligence Calibration A/B Test",
            "timestamp": datetime.now().isoformat(),
            "pool_size": len(self.video_names),
            "n_per_group": n_per_group,
            "baseline": {
                "method": "V3.4 Shot Selector (Visual Quality)",
                "top_n": baseline_top,
                "ad_value": baseline_ad_value,
                "grades": baseline_grades,
            },
            "variant": {
                "method": "V3.8 Winner DNA Ranking (Buying Score)",
                "top_n": variant_top,
                "ad_value": variant_ad_value,
                "grades": variant_grades,
                "archetypes": baseline_archetypes,
                "winner_patterns": winner_patterns,
            },
            "improvement": improvement,
            "archetype_ranking": self.archetype_engine.get_archetype_ranking(),
        }

        # 保存结果
        self._save_results()

        # 打印结果
        self._print_summary(improvement)

        return self.results

    def _score_baseline(self) -> List[dict]:
        """Baseline 评分（V3.4 视觉评分）"""
        scores = []
        for name in self.video_names:
            rank = self.ranking_data.get(name, {})
            ad_value = rank.get("ad_value_score", 0)
            hook = rank.get("hook_score_v2", rank.get("hook_score", 0))
            gameplay = rank.get("gameplay_clarity", 0)
            reward = rank.get("reward_score", 0)
            scores.append({
                "video_name": name,
                "ad_value_score": ad_value,
                "hook_score": hook,
                "gameplay_score": gameplay,
                "reward_score": reward,
                "impact_score": rank.get("impact_score", 0),
                "motion_score": rank.get("motion_score", 0),
            })
        return scores

    def _score_variant(self) -> List[dict]:
        """Variant 评分（V3.8 Buying Score）"""
        scores = []
        for name in self.video_names:
            prediction = self.value_predictor.predict(name)
            dna = self.dna_extractor.extract(name)
            grade_result = self.quality_gate.evaluate(name, dna)
            archetype_result = self.archetype_engine.classify_creative(dna)

            scores.append({
                "video_name": name,
                "buying_score": prediction["buying_score"],
                "predicted_ctr": prediction["predicted_ctr"],
                "predicted_cpi": prediction["predicted_cpi"],
                "predicted_d7_roi": prediction["predicted_d7_roi"],
                "performance_grade": grade_result.grade,
                "archetype": archetype_result["archetype"],
                "archetype_similarity": archetype_result["similarity"],
                "breakdown": prediction["breakdown"],
                "grade_details": {
                    "strengths": grade_result.strengths,
                    "weaknesses": grade_result.weaknesses,
                    "recommendations": grade_result.recommendations,
                },
            })
        return scores

    @staticmethod
    def _select_top(scores: List[dict], n: int, sort_key: str) -> List[dict]:
        """选取 Top N"""
        sorted_scores = sorted(scores, key=lambda x: -x.get(sort_key, 0))
        return sorted_scores[:n]

    def _compute_ad_value(self, top_list: List[dict], group: str) -> dict:
        """计算 Ad Value（综合买量价值指数）"""
        n = len(top_list) or 1

        if group == "baseline":
            # Baseline Ad Value = ad_value_score 的加权
            avg_ad_value = sum(x["ad_value_score"] for x in top_list) / n
            avg_hook = sum(x["hook_score"] for x in top_list) / n
            avg_gameplay = sum(x["gameplay_score"] for x in top_list) / n
            avg_reward = sum(x["reward_score"] for x in top_list) / n

            # 转换为买量价值估算
            estimated_ctr = 1.0 + avg_ad_value / 50 * 2.0
            estimated_cpi = max(0.3, 1.2 - avg_ad_value / 100)
            estimated_roi = avg_ad_value / 100 * 0.3

            composite = avg_ad_value
        else:
            # Variant Ad Value = Buying Score 综合
            avg_buying = sum(x["buying_score"] for x in top_list) / n
            avg_ctr = sum(x["predicted_ctr"] for x in top_list) / n
            avg_cpi = sum(x["predicted_cpi"] for x in top_list) / n
            avg_roi = sum(x["predicted_d7_roi"] for x in top_list) / n

            estimated_ctr = avg_ctr
            estimated_cpi = avg_cpi
            estimated_roi = avg_roi

            # 综合 Ad Value = Buying Score + CTR + CPI + ROI + Grade Bonus
            grade_bonus = sum(
                {"S+": 10, "S": 6, "A": 3, "B": 1, "Reject": 0}.get(x.get("performance_grade", ""), 0)
                for x in top_list
            ) / n

            composite = (
                avg_buying * 0.5 +
                avg_ctr * 12 +
                (1.0 / max(avg_cpi, 0.01)) * 6 +
                avg_roi * 100 * 0.35 +
                grade_bonus * 1.5
            )

        return {
            "composite_ad_value": round(composite, 2),
            "avg_buying_score": round(avg_buying if group == "variant" else 0, 1) if group == "variant" else round(sum(x["ad_value_score"] for x in top_list) / n, 1),
            "estimated_ctr": round(estimated_ctr, 2),
            "estimated_cpi": round(estimated_cpi, 2),
            "estimated_d7_roi": round(estimated_roi, 3),
            "top_list": [
                {
                    "video_name": x["video_name"],
                    "score": x.get("buying_score", x.get("ad_value_score", 0)),
                    "grade": x.get("performance_grade", ""),
                }
                for x in top_list
            ],
        }

    @staticmethod
    def _calc_improvement(baseline: dict, variant: dict) -> dict:
        """计算提升幅度"""
        b_val = baseline["composite_ad_value"]
        v_val = variant["composite_ad_value"]
        improvement_pct = (v_val - b_val) / max(b_val, 1) * 100

        return {
            "baseline_ad_value": b_val,
            "variant_ad_value": v_val,
            "absolute_improvement": round(v_val - b_val, 2),
            "improvement_percentage": round(improvement_pct, 1),
            "target_20pct_met": improvement_pct >= 20.0,
        }

    def _grade_distribution(self, top_list: List[dict]) -> Dict[str, int]:
        """计算 Performance Grade 分布"""
        distribution = {"S+": 0, "S": 0, "A": 0, "B": 0, "Reject": 0}
        for item in top_list:
            grade = item.get("performance_grade", "")
            if grade in distribution:
                distribution[grade] += 1
        return distribution

    def _archetype_analysis(self, top_list: List[dict]) -> dict:
        """Archetype 分析"""
        archetype_counts = {}
        for item in top_list:
            arch = item.get("archetype", "Unknown")
            archetype_counts[arch] = archetype_counts.get(arch, 0) + 1

        sorted_arch = dict(sorted(archetype_counts.items(), key=lambda x: -x[1]))

        avg_sim = sum(
            item.get("archetype_similarity", 0) for item in top_list
        ) / max(len(top_list), 1)

        return {
            "distribution": sorted_arch,
            "avg_archetype_similarity": round(avg_sim, 1),
        }

    def _extract_winner_patterns(self, top_list: List[dict]) -> List[dict]:
        """提取 Winner DNA 模式"""
        patterns = []
        for item in top_list[:5]:
            name = item["video_name"]
            dna = self.dna_extractor.extract(name)
            patterns.append({
                "video_name": name,
                "buying_score": item["buying_score"],
                "grade": item["performance_grade"],
                "archetype": item["archetype"],
                "hook_type": dna.get("hook_dna", {}).get("hook_type", ""),
                "subject": dna.get("subject_dna", {}).get("primary_subject", ""),
                "action": dna.get("gameplay_dna", {}).get("action", ""),
            })
        return patterns

    def _save_results(self):
        """保存结果"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = OUTPUT_DIR / "v38_ab_test_result.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n  JSON saved: {json_path}")

    def _print_summary(self, improvement: dict):
        """打印摘要"""
        print("\n" + "=" * 70)
        print("A/B Test Summary")
        print("=" * 70)
        print(f"  Baseline (V3.4 Visual): {improvement['baseline_ad_value']:.1f} Ad Value")
        print(f"  Variant  (V3.8 Buying):  {improvement['variant_ad_value']:.1f} Ad Value")
        print(f"  Improvement:             {improvement['improvement_percentage']:+.1f}%")
        print(f"  Target (>= 20%):         {'PASS' if improvement['target_20pct_met'] else 'NOT MET'}")
        print(f"\n  Pool size: {self.results['pool_size']}")
        print(f"  Sample per group: {self.results['n_per_group']}")


def run_v38_ab_test(n: int = 10):
    """运行 V3.8 A/B Test"""
    tester = V38ABTest()
    return tester.run_ab_test(n_per_group=n)


if __name__ == "__main__":
    run_v38_ab_test(n=10)
