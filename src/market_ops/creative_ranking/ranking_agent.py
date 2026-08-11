"""Facebook Creative Ranking Agent - V4.2 主入口

读取 V4.1 Expansion 输出，运行多维评分，输出排序结果。
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

from src.market_ops.creative_ranking.config import RankingConfig
from src.market_ops.creative_ranking.score_plugins import (
    SimilarityScorer,
    HookScorer,
    ReadabilityScorer,
    NoveltyScorer,
    FatigueScorer,
    BrandScorer,
    AIRiskScorer,
    GameplayScorer,
    PolicyScorer,
    ScoreResult,
)


class CreativeRankingAgent:
    """Creative Ranking Agent - 决定哪个 Variant 最值得生成"""

    def __init__(self, config: RankingConfig | None = None):
        self.config = config or RankingConfig()
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Config validation failed: {errors}")

        # 初始化所有 Scorer（Plugin 模式，未来可扩展）
        self.scorers = [
            SimilarityScorer(),
            HookScorer(),
            ReadabilityScorer(),
            NoveltyScorer(),
            FatigueScorer(),
            BrandScorer(),
            AIRiskScorer(),
            GameplayScorer(),
            PolicyScorer(),
        ]

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(
        self,
        expansion_dir: str | Path,
        output_dir: str | Path = "",
    ) -> dict:
        """运行完整 Ranking 流程

        Args:
            expansion_dir: V4.1 的 creative_expansion/ 输出目录
            output_dir: 本 Agent 的输出目录
        """
        t0 = datetime.now()
        expansion_dir = Path(expansion_dir)
        self.output_dir = Path(output_dir) if output_dir else (
            ROOT / "output" / "creative_ranking"
        )

        print("=" * 100)
        print("🎯 Facebook Creative Ranking Agent - V4.2")
        print("=" * 100)

        # Step 1: 加载 V4.1 输出
        print("\n[Step 1] 加载 Creative Expansion 输出...")
        variants = self._load_variants(expansion_dir)
        if not variants:
            print("  ❌ 无 Variants 可评分")
            return {}
        print(f"  ✅ 加载了 {len(variants)} 个 Variants")

        # Step 2: 加载 Winning DNA
        print("\n[Step 2] 加载 Winning Creative DNA...")
        base_dna = self._load_base_dna(expansion_dir)
        if not base_dna:
            print("  ❌ 无 Base DNA，尝试从第一个 Variant 推断")
            base_dna = variants[0].get("modified_dna", {})
        print(f"  ✅ Base DNA 加载完成")

        # Step 3: 运行多维评分
        print(f"\n[Step 3] 运行多维评分 ({len(self.scorers)} 个维度)...")
        scored = []
        for i, v in enumerate(variants):
            v_id = v.get("variant_id", f"V{i+1:03d}")
            v_dna = v.get("modified_dna", {})
            fb_meta = v.get("fb_meta", {})

            # 运行所有 scorer
            dimension_scores: dict[str, ScoreResult] = {}
            for scorer in self.scorers:
                try:
                    result = scorer.score(v_dna, base_dna, fb_meta)
                    dimension_scores[scorer.weight_key] = result
                except Exception as e:
                    print(f"    ⚠️ Scorer {scorer.name} 失败 ({v_id}): {e}")
                    dimension_scores[scorer.weight_key] = ScoreResult(score=50.0)

            # 计算 Overall Score（加权）
            overall = 0.0
            for key, weight in self.config.weights.items():
                dim_score = dimension_scores.get(key, ScoreResult(score=50.0))
                overall += dim_score.score * weight

            # 淘汰标记
            discarded = overall < self.config.discard_threshold
            discard_reason = ""
            if discarded:
                low_dims = [
                    key for key, res in dimension_scores.items()
                    if res.score < self.config.min_dimension_scores.get(key, 0)
                ]
                discard_reason = f"Overall={overall:.1f}<60" + (
                    f", 低分维度: {', '.join(low_dims)}" if low_dims else ""
                )

            scored.append({
                "variant_id": v_id,
                "overall_score": round(overall, 1),
                "discarded": discarded,
                "discard_reason": discard_reason,
                "dimension_scores": dimension_scores,
                "changed_dimension": v.get("changed_dimension", ""),
                "old_value": v.get("old_value", ""),
                "new_value": v.get("new_value", ""),
                "risk_level": v.get("risk_level", ""),
            })

            if (i + 1) % 10 == 0 or i == len(variants) - 1:
                print(f"    已评分: {i+1}/{len(variants)}")

        # Step 4: 排序
        print("\n[Step 4] 排序...")
        scored.sort(key=lambda x: x["overall_score"], reverse=True)
        passed = [s for s in scored if not s["discarded"]]
        discarded_list = [s for s in scored if s["discarded"]]
        print(f"  ✅ 通过: {len(passed)} | 淘汰: {len(discarded_list)}")
        if passed:
            print(f"  🥇 TOP1: {passed[0]['variant_id']} = {passed[0]['overall_score']:.1f}")

        # Step 5: 输出文件
        print("\n[Step 5] 输出结果...")
        self._write_output(scored, passed, discarded_list, base_dna)

        elapsed = (datetime.now() - t0).total_seconds()
        print(f"\n{'=' * 100}")
        print(f"✅ Ranking 完成! 耗时 {elapsed:.1f}s")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"{'=' * 100}")

        return {
            "total_variants": len(variants),
            "passed": len(passed),
            "discarded": len(discarded_list),
            "top20": [p["variant_id"] for p in passed[:20]],
            "output_dir": str(self.output_dir),
            "elapsed_sec": elapsed,
        }

    # ------------------------------------------------------------------
    # 加载数据
    # ------------------------------------------------------------------
    def _load_variants(self, expansion_dir: Path) -> list[dict]:
        """从 creative_expansion/ 加载所有 Variants

        合并 prompts.json + variables.json + quality.json 的信息
        """
        variants = []
        for v_dir in sorted(expansion_dir.iterdir()):
            if not v_dir.is_dir() or not v_dir.name.startswith("V"):
                continue

            variant_data = {}

            # 1. 加载 prompts.json（包含 prompts + modified_dna）
            prompts_file = v_dir / "prompts.json"
            if prompts_file.exists():
                with open(prompts_file, "r", encoding="utf-8") as f:
                    prompts_data = json.load(f)
                variant_data.update(prompts_data)

            # 2. 加载 variables.json（包含 changed_dimension, old_value, new_value 等）
            vars_file = v_dir / "variables.json"
            if vars_file.exists():
                with open(vars_file, "r", encoding="utf-8") as f:
                    vars_data = json.load(f)
                variant_data.update(vars_data)

            # 3. 加载 quality.json（包含 quality score）
            quality_file = v_dir / "quality.json"
            if quality_file.exists():
                with open(quality_file, "r", encoding="utf-8") as f:
                    quality_data = json.load(f)
                variant_data["fb_meta"] = quality_data

            # 如果没有 modified_dna，用 old_value 近似构建
            if "modified_dna" not in variant_data or not variant_data["modified_dna"]:
                variant_data["modified_dna"] = self._build_approx_dna(variant_data)

            variants.append(variant_data)
        return variants

    def _build_approx_dna(self, variant_data: dict) -> dict:
        """在没有完整 modified_dna 时，从已有信息近似构建"""
        changed_dim = variant_data.get("changed_dimension", "")
        new_val = variant_data.get("new_value", "")
        old_val = variant_data.get("old_value", "")

        # 基础 DNA（近似）
        dna = {
            "character": {"type": "witch", "pose": "standing centered"},
            "creatures": [{"type": "dragon", "color": "blue", "glow": "cyan"}],
            "environment": {"type": "magic_forest", "time": "night"},
            "lighting": {"color_temperature": "warm", "special_effects": ["particles"]},
            "colors": {"mood_palette": ["balanced"]},
            "hook": {"type": "collection"},
            "camera": {"shot_type": "medium", "movement": "static"},
            "composition": {"layout": "centered"},
        }

        # 根据 changed_dimension 应用变化
        if changed_dim == "creature_0_color" and new_val:
            dna["creatures"][0]["color"] = new_val
        elif changed_dim == "creature_0_type" and new_val:
            dna["creatures"][0]["type"] = new_val
        elif changed_dim == "creature_0_glow" and new_val:
            dna["creatures"][0]["glow"] = new_val
        elif changed_dim == "creature_0_action" and new_val:
            dna["creatures"][0]["action"] = new_val
        elif changed_dim == "lighting_temperature" and new_val:
            dna["lighting"]["color_temperature"] = new_val
        elif changed_dim == "lighting_effects_0" and new_val:
            dna["lighting"]["special_effects"] = [new_val]
        elif changed_dim == "colors_mood" and new_val:
            dna["colors"]["mood_palette"] = [new_val]
        elif changed_dim == "environment_type" and new_val:
            dna["environment"]["type"] = new_val
        elif changed_dim == "environment_time" and new_val:
            dna["environment"]["time"] = new_val
        elif changed_dim == "character_clothes" and new_val:
            dna["character"]["clothes"] = new_val
        elif changed_dim == "character_pose" and new_val:
            dna["character"]["pose"] = new_val
        elif changed_dim == "character_gesture" and new_val:
            dna["character"]["gesture"] = new_val
        elif changed_dim == "camera_shot" and new_val:
            dna["camera"]["shot_type"] = new_val
        elif changed_dim == "camera_movement" and new_val:
            dna["camera"]["movement"] = new_val
        elif changed_dim == "character_type" and new_val:
            dna["character"]["type"] = new_val
        elif changed_dim == "hook_type" and new_val:
            dna["hook"]["type"] = new_val
        elif changed_dim == "composition_layout" and new_val:
            dna["composition"]["layout"] = new_val

        return dna

    def _load_base_dna(self, expansion_dir: Path) -> dict:
        """从 variable_matrix.json 推断 Base DNA，或返回默认"""
        # 尝试从 variable_matrix.json 获取 base 值
        vm_file = expansion_dir / "summary" / "variable_matrix.json"
        if vm_file.exists():
            with open(vm_file, "r", encoding="utf-8") as f:
                vm = json.load(f)

            # 构建 base dna
            base_dna = {
                "character": {"type": "witch"},
                "creatures": [{"type": "dragon", "color": "blue", "glow": "cyan"}],
                "environment": {"type": "magic_forest", "time": "night"},
                "lighting": {"color_temperature": "warm", "special_effects": ["particles"]},
                "colors": {"mood_palette": ["balanced"]},
                "hook": {"type": "collection"},
                "camera": {"shot_type": "medium", "movement": "static"},
                "composition": {"layout": "centered"},
            }
            return base_dna

        # 默认 base DNA
        return {
            "character": {"type": "witch"},
            "creatures": [{"type": "dragon", "color": "blue", "glow": "cyan"}],
            "environment": {"type": "magic_forest", "time": "night"},
            "lighting": {"color_temperature": "warm", "special_effects": ["particles"]},
            "colors": {"mood_palette": ["balanced"]},
            "hook": {"type": "collection"},
            "camera": {"shot_type": "medium", "movement": "static"},
            "composition": {"layout": "centered"},
        }

    # ------------------------------------------------------------------
    # 输出文件
    # ------------------------------------------------------------------
    def _write_output(self, scored, passed, discarded, base_dna):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. ranking.csv
        csv_path = self.output_dir / "ranking.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            headers = [
                "rank", "variant_id", "overall_score", "status",
                "similarity", "hook", "readability",
                "novelty", "fatigue", "brand",
                "ai_risk", "gameplay", "policy",
                "changed_dimension", "old_value", "new_value", "risk_level",
                "recommendations", "risks", "discard_reason",
            ]
            writer.writerow(headers)
            for rank, s in enumerate(scored, 1):
                ds = s["dimension_scores"]
                recs = []
                risks = []
                for key, res in ds.items():
                    recs.extend(res.recommendations)
                    risks.extend(res.risks)
                writer.writerow([
                    rank, s["variant_id"], s["overall_score"],
                    "PASS" if not s["discarded"] else "DISCARD",
                    round(ds.get("winning_similarity", ScoreResult()).score, 1),
                    round(ds.get("facebook_hook", ScoreResult()).score, 1),
                    round(ds.get("visual_readability", ScoreResult()).score, 1),
                    round(ds.get("novelty", ScoreResult()).score, 1),
                    round(ds.get("creative_fatigue", ScoreResult()).score, 1),
                    round(ds.get("brand_consistency", ScoreResult()).score, 1),
                    round(ds.get("ai_generation_risk", ScoreResult()).score, 1),
                    round(ds.get("gameplay_consistency", ScoreResult()).score, 1),
                    round(ds.get("facebook_policy_risk", ScoreResult()).score, 1),
                    s["changed_dimension"], s["old_value"], s["new_value"], s["risk_level"],
                    "; ".join(recs[:3]), "; ".join(risks[:3]), s["discard_reason"],
                ])
        print(f"  📊 ranking.csv → {csv_path}")

        # 2. ranking.json
        json_path = self.output_dir / "ranking.json"
        scored_export = []
        for s in scored:
            ds = s["dimension_scores"]
            scored_export.append({
                "variant_id": s["variant_id"],
                "overall_score": s["overall_score"],
                "discarded": s["discarded"],
                "discard_reason": s["discard_reason"],
                "changed_dimension": s["changed_dimension"],
                "old_value": s["old_value"],
                "new_value": s["new_value"],
                "risk_level": s["risk_level"],
                "dimensions": {
                    k: {
                        "score": round(v.score, 1),
                        "breakdown": v.breakdown,
                        "recommendations": v.recommendations,
                        "risks": v.risks,
                    }
                    for k, v in ds.items()
                },
            })
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(scored_export, f, indent=2, ensure_ascii=False, default=str)
        print(f"  📋 ranking.json → {json_path}")

        # 3. top20.json
        top20 = scored_export[:20]
        with open(self.output_dir / "top20.json", "w", encoding="utf-8") as f:
            json.dump(top20, f, indent=2, ensure_ascii=False, default=str)
        print(f"  🏆 top20.json → {self.output_dir / 'top20.json'}")

        # 4. score_breakdown.json
        breakdown = {}
        for key in self.config.weights.keys():
            values = [s["dimension_scores"].get(key, ScoreResult(score=0)).score for s in scored]
            breakdown[key] = {
                "mean": round(sum(values) / len(values), 1) if values else 0,
                "max": round(max(values), 1) if values else 0,
                "min": round(min(values), 1) if values else 0,
            }
        with open(self.output_dir / "score_breakdown.json", "w", encoding="utf-8") as f:
            json.dump(breakdown, f, indent=2, ensure_ascii=False)
        print(f"  📈 score_breakdown.json → {self.output_dir / 'score_breakdown.json'}")

        # 5. report.md
        report = self._build_report(scored, passed, discarded)
        with open(self.output_dir / "report.md", "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  📄 report.md → {self.output_dir / 'report.md'}")

        # 6. heatmap.json
        heatmap = self._build_heatmap(scored)
        with open(self.output_dir / "heatmap.json", "w", encoding="utf-8") as f:
            json.dump(heatmap, f, indent=2, ensure_ascii=False)
        print(f"  🔥 heatmap.json → {self.output_dir / 'heatmap.json'}")

    def _build_report(self, scored, passed, discarded) -> str:
        lines = [
            "# Facebook Creative Ranking Report (V4.2)",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 项目: P04 Merge Witches",
            "",
            "---",
            "",
            "## 一、评分概览",
            "",
            f"- **总 Variants**: {len(scored)}",
            f"- **通过**: {len(passed)}",
            f"- **淘汰**: {len(discarded)}",
            f"- **淘汰阈值**: {self.config.discard_threshold}分",
            "",
            "### 评分权重",
            "",
            "| 维度 | 权重 |",
            "|------|------|",
        ]
        for key, w in self.config.weights.items():
            lines.append(f"| {key} | {w*100:.0f}% |")

        lines.extend(["", "---", "", "## 二、TOP 20 推荐", ""])
        lines.append("| 排名 | Variant | 总分 | 变更 | 风险 | 推荐理由 | 风险 |")
        lines.append("|------|---------|------|------|------|----------|------|")
        for rank, s in enumerate(passed[:20], 1):
            ds = s["dimension_scores"]
            recs = []
            risks = []
            for k, r in ds.items():
                recs.extend(r.recommendations)
                risks.extend(r.risks)
            rec_str = "; ".join(recs[:2]) if recs else "-"
            risk_str = "; ".join(risks[:2]) if risks else "-"
            lines.append(
                f"| {rank} | {s['variant_id']} | {s['overall_score']:.1f} | "
                f"{s['changed_dimension']} | {s['risk_level']} | {rec_str} | {risk_str} |"
            )

        if discarded:
            lines.extend(["", "---", "", "## 三、淘汰列表", ""])
            lines.append("| Variant | 总分 | 原因 |")
            lines.append("|---------|------|------|")
            for s in discarded[:10]:
                lines.append(f"| {s['variant_id']} | {s['overall_score']:.1f} | {s['discard_reason']} |")
            if len(discarded) > 10:
                lines.append(f"| ... | ... | 还有{len(discarded)-10}个 |")

        lines.extend([
            "", "---", "",
            "## 四、各维度分数分布", "",
        ])
        for key in self.config.weights.keys():
            values = [s["dimension_scores"].get(key, ScoreResult(score=0)).score for s in scored]
            if values:
                mean = sum(values) / len(values)
                lines.append(f"- **{key}**: 均值={mean:.1f}, 最高={max(values):.1f}, 最低={min(values):.1f}")

        lines.extend(["", "---", "", "## 五、决策建议", "",
            "### 立即生成（P0 + Overall > 75）",
            "",
            "### 谨慎测试（P1 + Overall 60-75）",
            "",
            "### 不建议生成（P2 或 Overall < 60）",
        ])

        return "\n".join(lines)

    def _build_heatmap(self, scored: list[dict]) -> dict:
        """生成 Heatmap 数据：各变量维度的平均分数"""
        # 按 changed_dimension 分组
        dim_groups: dict[str, list[dict]] = {}
        for s in scored:
            dim = s.get("changed_dimension", "unknown")
            dim_groups.setdefault(dim, []).append(s)

        heatmap = {
            "by_dimension": {},
            "by_risk_level": {},
        }
        for dim, group in dim_groups.items():
            if not group:
                continue
            avg_overall = sum(g["overall_score"] for g in group) / len(group)
            # 各维度平均分
            dim_scores = {}
            for key in self.config.weights.keys():
                vals = [g["dimension_scores"].get(key, ScoreResult(score=0)).score for g in group]
                dim_scores[key] = round(sum(vals) / len(vals), 1) if vals else 0
            heatmap["by_dimension"][dim] = {
                "count": len(group),
                "avg_overall": round(avg_overall, 1),
                "dimension_scores": dim_scores,
            }

        # 按风险等级分组
        for risk in ["P0", "P1", "P2"]:
            group = [s for s in scored if s.get("risk_level") == risk]
            if group:
                avg = sum(g["overall_score"] for g in group) / len(group)
                heatmap["by_risk_level"][risk] = {
                    "count": len(group),
                    "avg_overall": round(avg, 1),
                }

        return heatmap


# ======================================================================
# CLI 入口
# ======================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Facebook Creative Ranking Agent V4.2")
    parser.add_argument("--expansion-dir", type=str,
                        default=str(ROOT / "output" / "creative_expansion"),
                        help="V4.1 Expansion 输出目录")
    parser.add_argument("--output-dir", type=str, default="",
                        help="本 Agent 输出目录")
    parser.add_argument("--discard-threshold", type=float, default=60.0,
                        help="淘汰阈值")
    args = parser.parse_args()

    config = RankingConfig(discard_threshold=args.discard_threshold)
    agent = CreativeRankingAgent(config=config)
    result = agent.run(
        expansion_dir=args.expansion_dir,
        output_dir=args.output_dir,
    )
    print(f"\n🎯 结果: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    main()
