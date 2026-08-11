"""Dashboard - V4.4 Blueprint 生产概览

汇总 Blueprint 生成结果，输出文本 Dashboard。
"""
from __future__ import annotations

from typing import Any


class BlueprintDashboard:
    """Blueprint 生产概览"""

    def __init__(self) -> None:
        self.outputs: list[dict[str, Any]] = []

    def add(self, output: Any) -> None:
        """添加一个 BlueprintOutput"""
        self.outputs.append(output)

    def generate(self) -> str:
        """生成文本 Dashboard"""
        if not self.outputs:
            return "暂无 Blueprint 数据"

        lines = [
            "=" * 80,
            "Video Creative Blueprint Intelligence (V4.4) - Dashboard",
            "=" * 80,
            f"总变体数: {len(self.outputs)}",
            "",
            "## 汇总统计",
        ]

        total_shots = sum(o.shotlist.total_shots for o in self.outputs)
        total_scenes = sum(len(o.storyboard.scenes) for o in self.outputs)
        avg_quality = sum(o.quality.score for o in self.outputs) / len(self.outputs)
        avg_review = sum(o.creative_review.overall_score for o in self.outputs) / len(self.outputs)
        avg_ctr = sum(o.creative_review.predicted_ctr for o in self.outputs) / len(self.outputs)
        avg_roas = sum(o.creative_review.predicted_roas for o in self.outputs) / len(self.outputs)

        lines.extend([
            f"- 总镜头数: {total_shots}",
            f"- 总分镜场景: {total_scenes}",
            f"- 平均质量分: {avg_quality:.1f}/100",
            f"- 平均创意评分: {avg_review:.1f}/100",
            f"- 平均预测 CTR: {avg_ctr:.4f}",
            f"- 平均预测 ROAS: {avg_roas:.2f}",
            "",
        ])

        # DNA 分布
        hooks: dict[str, int] = {}
        emotions: dict[str, int] = {}
        rhythms: dict[str, int] = {}
        gameplay_types: dict[str, int] = {}

        for o in self.outputs:
            hooks[o.dna.hook] = hooks.get(o.dna.hook, 0) + 1
            emotions[o.dna.emotion] = emotions.get(o.dna.emotion, 0) + 1
            rhythms[o.dna.rhythm] = rhythms.get(o.dna.rhythm, 0) + 1
            gameplay_types[o.story_pattern.gameplay_type] = gameplay_types.get(o.story_pattern.gameplay_type, 0) + 1

        lines.append("## Hook 分布")
        for k, v in sorted(hooks.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

        lines.append("")
        lines.append("## Emotion 分布")
        for k, v in sorted(emotions.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

        lines.append("")
        lines.append("## Rhythm 分布")
        for k, v in sorted(rhythms.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

        lines.append("")
        lines.append("## 玩法类型分布")
        for k, v in sorted(gameplay_types.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

        # Camera 使用统计
        camera_moves: dict[str, int] = {}
        lens_usage: dict[str, int] = {}
        for o in self.outputs:
            for spec in o.camera_spec.specs:
                camera_moves[spec.move] = camera_moves.get(spec.move, 0) + 1
                lens_usage[spec.lens] = lens_usage.get(spec.lens, 0) + 1

        lines.append("")
        lines.append("## Camera 运镜统计")
        for k, v in sorted(camera_moves.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

        lines.append("")
        lines.append("## Lens 使用统计")
        for k, v in sorted(lens_usage.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

        # Top / Bottom Blueprint
        sorted_by_review = sorted(self.outputs, key=lambda x: x.creative_review.overall_score, reverse=True)
        top = sorted_by_review[0]
        bottom = sorted_by_review[-1]

        lines.extend([
            "",
            "## Top Blueprint",
            f"- {top.variant_id} | Overall: {top.creative_review.overall_score}/100 | "
            f"Hook:{top.creative_review.hook_score} Story:{top.creative_review.story_score} "
            f"Camera:{top.creative_review.camera_score} Visual:{top.creative_review.visual_score} Editing:{top.creative_review.editing_score}",
            "",
            "## Bottom Blueprint",
            f"- {bottom.variant_id} | Overall: {bottom.creative_review.overall_score}/100 | "
            f"Hook:{bottom.creative_review.hook_score} Story:{bottom.creative_review.story_score} "
            f"Camera:{bottom.creative_review.camera_score} Visual:{bottom.creative_review.visual_score} Editing:{bottom.creative_review.editing_score}",
            "",
            "## 各变体详情",
            "-" * 80,
        ])

        for o in self.outputs:
            cr = o.creative_review
            lines.append(
                f"{o.variant_id} | {o.story_pattern.gameplay_type:12} | "
                f"{o.blueprint.video_length:.0f}s | 镜头:{o.shotlist.total_shots:2} | "
                f"质量:{o.quality.score:3}/100 | 创意:{cr.overall_score:3}/100 | {cr.verdict}"
            )

        lines.append("-" * 80)
        return "\n".join(lines)

    def save(self, path: str) -> None:
        """保存 Dashboard 到文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.generate())
