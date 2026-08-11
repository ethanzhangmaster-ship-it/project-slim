"""Asset Coverage Analyzer V1

分析素材库的覆盖度，找出缺失的素材类型。

输入：Ranking DB (v36_1_ranking_db.json)
输出：Coverage Report + Missing Assets List
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AssetGap:
    asset_type: str
    need: str
    priority: str
    current_count: int = 0
    target_count: int = 0
    avg_quality: float = 0.0


@dataclass
class CoverageReport:
    total_assets: int = 0
    coverage_score: dict[str, float] = field(default_factory=dict)
    role_distribution: dict[str, int] = field(default_factory=dict)
    role_quality: dict[str, float] = field(default_factory=dict)
    missing_assets: list[AssetGap] = field(default_factory=list)
    top_20_gaps: list[AssetGap] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class AssetCoverageAnalyzer:
    """分析素材库覆盖度，输出缺失报告。"""

    # 目标素材数量（基于 V3.6.2 需求）
    TARGET_COUNTS = {
        "hook": 100,
        "gameplay": 200,
        "reward": 250,
        "problem": 100,
        "cta": 50,
        "character": 150,
        "scene": 100,
    }

    # 最低质量阈值
    MIN_QUALITY_THRESHOLD = 40.0

    def __init__(self, ranking_db_path: Path | str) -> None:
        self.db_path = Path(ranking_db_path)
        self._data: list[dict] = []

    def analyze(self) -> CoverageReport:
        """执行全量覆盖度分析。"""
        self._load_db()
        report = CoverageReport(total_assets=len(self._data))

        # 1. 角色分布统计
        report.role_distribution = self._calc_role_distribution()
        report.role_quality = self._calc_role_quality()

        # 2. 覆盖度分数 (0-1)
        report.coverage_score = self._calc_coverage_scores(report.role_distribution)

        # 3. 缺失素材分析
        report.missing_assets = self._find_gaps(
            report.role_distribution, report.role_quality
        )
        report.top_20_gaps = sorted(
            report.missing_assets,
            key=lambda g: (g.target_count - g.current_count) * (1.5 if g.priority == "high" else 1.0),
            reverse=True,
        )[:20]

        # 4. 生成建议
        report.recommendations = self._generate_recommendations(report)

        return report

    def save_report(self, report: CoverageReport, output_path: Path | str) -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "total_assets": report.total_assets,
            "coverage_score": report.coverage_score,
            "role_distribution": report.role_distribution,
            "role_quality": {k: round(v, 2) for k, v in report.role_quality.items()},
            "missing_assets": [
                {
                    "type": g.asset_type,
                    "need": g.need,
                    "priority": g.priority,
                    "current_count": g.current_count,
                    "target_count": g.target_count,
                    "gap": g.target_count - g.current_count,
                    "avg_quality": round(g.avg_quality, 2),
                }
                for g in report.missing_assets
            ],
            "top_20_gaps": [
                {
                    "type": g.asset_type,
                    "need": g.need,
                    "priority": g.priority,
                    "gap": g.target_count - g.current_count,
                }
                for g in report.top_20_gaps
            ],
            "recommendations": report.recommendations,
        }
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out

    def _load_db(self) -> None:
        raw = json.loads(self.db_path.read_text(encoding="utf-8"))
        self._data = raw.get("shots", raw if isinstance(raw, list) else [])

    def _calc_role_distribution(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self._data:
            role_scores = item.get("role_scores", {})
            for role, score in role_scores.items():
                if score >= self.MIN_QUALITY_THRESHOLD:
                    counts[role] = counts.get(role, 0) + 1
        return counts

    def _calc_role_quality(self) -> dict[str, float]:
        quality: dict[str, list[float]] = {}
        for item in self._data:
            role_scores = item.get("role_scores", {})
            for role, score in role_scores.items():
                if role not in quality:
                    quality[role] = []
                quality[role].append(score)
        return {role: sum(scores) / len(scores) for role, scores in quality.items() if scores}

    def _calc_coverage_scores(self, distribution: dict[str, int]) -> dict[str, float]:
        scores = {}
        for role, target in self.TARGET_COUNTS.items():
            actual = distribution.get(role, 0)
            scores[role] = round(min(actual / target, 1.0), 2)
        return scores

    def _find_gaps(
        self, distribution: dict[str, int], quality: dict[str, float]
    ) -> list[AssetGap]:
        gaps = []

        # Hook 子类型分析
        hook_types = self._analyze_hook_subtypes()
        for ht, count in hook_types.items():
            target = max(25, self.TARGET_COUNTS["hook"] // 4)
            if count < target:
                gaps.append(AssetGap(
                    asset_type="hook",
                    need=ht,
                    priority="high" if count < 10 else "medium",
                    current_count=count,
                    target_count=target,
                    avg_quality=0,
                ))

        # Gameplay 子类型分析
        gameplay_types = self._analyze_gameplay_subtypes()
        for gt, count in gameplay_types.items():
            target = max(40, self.TARGET_COUNTS["gameplay"] // 4)
            if count < target:
                gaps.append(AssetGap(
                    asset_type="gameplay",
                    need=gt,
                    priority="high" if count < 15 else "medium",
                    current_count=count,
                    target_count=target,
                    avg_quality=0,
                ))

        # 整体角色覆盖度
        for role, target in self.TARGET_COUNTS.items():
            actual = distribution.get(role, 0)
            if actual < target:
                gaps.append(AssetGap(
                    asset_type=role,
                    need=f"{role}_coverage",
                    priority="high" if actual < target * 0.3 else "medium",
                    current_count=actual,
                    target_count=target,
                    avg_quality=quality.get(role, 0),
                ))

        return gaps

    def _analyze_hook_subtypes(self) -> dict[str, int]:
        """基于文件名和 hook_breakdown 分析 Hook 子类型。"""
        counts: dict[str, int] = {
            "curiosity_hook": 0,
            "fail_hook": 0,
            "evolution_hook": 0,
            "challenge_hook": 0,
            "action_hook": 0,
        }
        for item in self._data:
            name = item.get("video_name", "").lower()
            hook_score = item.get("hook_score_v2", 0)
            if hook_score < 30:
                continue

            # 基于文件名推断
            if any(k in name for k in ["evol", "egg", "dragon", "升级"]):
                counts["evolution_hook"] += 1
            elif any(k in name for k in ["fail", "wrong", "lose", "失败"]):
                counts["fail_hook"] += 1
            elif any(k in name for k in ["challenge", "only", "1%", "can you"]):
                counts["challenge_hook"] += 1
            elif any(k in name for k in ["curious", "what", "secret", "?"]):
                counts["curiosity_hook"] += 1
            else:
                counts["action_hook"] += 1

        return counts

    def _analyze_gameplay_subtypes(self) -> dict[str, int]:
        """基于 gameplay_clarity_breakdown 分析 Gameplay 子类型。"""
        counts: dict[str, int] = {
            "merge_action": 0,
            "progression": 0,
            "decision_moment": 0,
            "fail_retry": 0,
        }
        for item in self._data:
            gb = item.get("gameplay_clarity_breakdown", {})
            gc = item.get("gameplay_clarity", 0)
            if gc < 30:
                continue

            merge = gb.get("merge_score", 0)
            drag = gb.get("drag_score", 0)
            upgrade = gb.get("upgrade_score", 0)
            before_after = gb.get("before_after_score", 0)

            if merge > 40 or drag > 40:
                counts["merge_action"] += 1
            if upgrade > 40 or before_after > 40:
                counts["progression"] += 1
            if any(k in item.get("video_name", "").lower() for k in ["choose", "select", "a/b"]):
                counts["decision_moment"] += 1
            if any(k in item.get("video_name", "").lower() for k in ["fail", "retry", "wrong", "almost"]):
                counts["fail_retry"] += 1

        return counts

    def _generate_recommendations(self, report: CoverageReport) -> list[str]:
        recs = []
        cs = report.coverage_score

        if cs.get("hook", 0) < 0.5:
            recs.append(
                f"🔴 CRITICAL: Hook素材严重不足 (覆盖率 {cs.get('hook', 0):.0%})。"
                f"需要新增 {self.TARGET_COUNTS['hook'] - report.role_distribution.get('hook', 0)} 个高质量开场视频。"
                "建议：制作 curiosity hook、fail hook、evolution hook 三类。"
            )
        if cs.get("gameplay", 0) < 0.5:
            recs.append(
                f"🔴 CRITICAL: Gameplay素材不足 (覆盖率 {cs.get('gameplay', 0):.0%})。"
                f"需要新增 {self.TARGET_COUNTS['gameplay'] - report.role_distribution.get('gameplay', 0)} 个玩法视频。"
                "建议：录制 merge action、progression、decision moment。"
            )
        if cs.get("reward", 0) < 0.8:
            recs.append(
                f"🟡 Reward素材需要扩充 (覆盖率 {cs.get('reward', 0):.0%})。"
                "建议：增加 dragon evolution、legendary unlock 类视频。"
            )

        # 质量建议
        hq = report.role_quality.get("hook", 0)
        if hq > 0 and hq < 50:
            recs.append(
                f"🟡 现有 Hook 素材平均质量较低 ({hq:.1f})。建议淘汰低分素材，集中制作高冲击力的前3秒。"
            )

        gq = report.role_quality.get("gameplay", 0)
        if gq > 0 and gq < 50:
            recs.append(
                f"🟡 现有 Gameplay 素材平均质量较低 ({gq:.1f})。建议录制更清晰的 merge grid 和 before-after 对比。"
            )

        return recs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    import sys

    root = Path(__file__).resolve().parent.parent.parent
    db_path = root / "creative_remix_engine" / "storage" / "outputs" / "v36_1_ranking_db.json"
    output_path = root / "creative_remix_engine" / "storage" / "asset_coverage_report.json"

    if not db_path.exists():
        print(f"[ERROR] Ranking DB not found: {db_path}")
        return 1

    analyzer = AssetCoverageAnalyzer(db_path)
    report = analyzer.analyze()
    analyzer.save_report(report, output_path)

    print("=" * 60)
    print("  Asset Coverage Analyzer V1 — Report")
    print("=" * 60)
    print(f"\n  Total Assets : {report.total_assets}")
    print(f"\n  📊 Coverage Scores:")
    for role, score in sorted(report.coverage_score.items(), key=lambda x: -x[1]):
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        status = "✅" if score >= 0.8 else "🟡" if score >= 0.5 else "🔴"
        print(f"     {status} {role:12s}: {bar} {score:.0%}")

    print(f"\n  📈 Role Distribution (quality ≥ {analyzer.MIN_QUALITY_THRESHOLD}):")
    for role, count in sorted(report.role_distribution.items(), key=lambda x: -x[1]):
        avg_q = report.role_quality.get(role, 0)
        print(f"     • {role:12s}: {count:4d}  (avg quality: {avg_q:.1f})")

    print(f"\n  🔴 Top 10 Missing Assets:")
    for i, gap in enumerate(report.top_20_gaps[:10], 1):
        print(f"     {i}. [{gap.priority.upper()}] {gap.asset_type}/{gap.need}: "
              f"current={gap.current_count}, target={gap.target_count}, "
              f"gap={gap.target_count - gap.current_count}")

    if report.recommendations:
        print(f"\n  💡 Recommendations:")
        for rec in report.recommendations:
            print(f"     • {rec}")

    print(f"\n  Output: {output_path}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
