"""Report Generator - 报告生成器

生成 analysis_report.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from .models import VideoAnalysisReport


class ReportGenerator:
    """报告生成器"""

    def __init__(self, output_dir: str = ""):
        if not output_dir:
            output_dir = os.path.join(os.getcwd(), "analysis_reports")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, report: VideoAnalysisReport) -> str:
        """生成报告文件

        Returns:
            报告文件路径
        """
        report.analyzed_at = datetime.now().isoformat()

        # 生成建议
        self._generate_recommendations(report)

        # 保存 JSON
        filename = f"{report.video_id}_report.json"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        return filepath

    def generate_batch_report(
        self,
        reports: list[VideoAnalysisReport],
        report_name: str = "",
    ) -> str:
        """生成批量报告

        Returns:
            报告文件路径
        """
        if not report_name:
            report_name = f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # 排序
        reports_sorted = sorted(reports, key=lambda r: r.total_score, reverse=True)

        # TOP10
        top10 = [r.to_dict() for r in reports_sorted[:10]]

        # 统计
        scores = [r.total_score for r in reports]
        avg_score = sum(scores) / len(scores) if scores else 0
        high_potential = sum(1 for r in reports if r.prediction == "HIGH_POTENTIAL")
        medium_potential = sum(1 for r in reports if r.prediction == "MEDIUM_POTENTIAL")

        batch_report = {
            "generated_at": datetime.now().isoformat(),
            "total_videos": len(reports),
            "avg_score": round(avg_score, 1),
            "high_potential": high_potential,
            "medium_potential": medium_potential,
            "top10": top10,
            "all_videos": [r.to_dict() for r in reports_sorted],
        }

        filepath = os.path.join(self.output_dir, report_name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(batch_report, f, ensure_ascii=False, indent=2)

        return filepath

    def _generate_recommendations(self, report: VideoAnalysisReport) -> None:
        """生成优化建议"""
        strengths: list[str] = []
        weaknesses: list[str] = []
        recommendations: list[str] = []

        # Hook 分析
        if report.hook_score >= 80:
            strengths.append("Hook 强：前3秒吸引力足")
        elif report.hook_score < 50:
            weaknesses.append("Hook 弱：前3秒缺乏冲击")
            recommendations.append("增加前3秒的动作强度或冲突元素")

        # Action 分析
        if report.action_score >= 80:
            strengths.append("动作丰富：角色持续在做事情")
        elif report.action_score < 50:
            weaknesses.append("动作不足：角色缺乏有效动作")
            recommendations.append("避免 standing still，增加 merge/attack/transform 等动作")

        # Gameplay 分析
        if report.gameplay_score >= 80:
            strengths.append("玩法清晰：核心玩法展示到位")
        elif report.gameplay_score < 50:
            weaknesses.append("玩法模糊：未展示核心游戏机制")
            recommendations.append("增加 merge/upgrade/reward 等玩法元素")

        # Visual 分析
        if report.visual_score >= 80:
            strengths.append("视觉丰富：画面元素充足")
        elif report.visual_score < 50:
            weaknesses.append("视觉单调：画面缺乏吸引力")
            recommendations.append("增加 glowing particles / transformation flash 等特效")

        # Consistency
        if report.consistency_score < 60:
            weaknesses.append("一致性风险：可能出现角色漂移")
            recommendations.append("增加角色细节描述（face/hair/outfit）")

        report.strengths = strengths
        report.weaknesses = weaknesses
        report.recommendation = "; ".join(recommendations) if recommendations else "素材质量良好，可直接测试投放"
