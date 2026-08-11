"""Analysis Pipeline - 视频分析管线

完整流程：
Video -> Parser -> Frame Extract -> Visual Analyzer -> Hook Analyzer ->
Action Analyzer -> Gameplay Analyzer -> Consistency Check -> Score Predictor -> Report
"""
from __future__ import annotations

import os
from typing import Any

from .models import VideoAnalysisReport
from .video_parser import VideoParser
from .frame_extractor import FrameExtractor
from .visual_analyzer import VisualAnalyzer
from .hook_analyzer import HookAnalyzer
from .action_analyzer import ActionAnalyzer
from .gameplay_analyzer import GameplayAnalyzer
from .consistency_checker import ConsistencyChecker
from .ad_score_predictor import AdScorePredictor
from .report_generator import ReportGenerator


class AnalysisPipeline:
    """视频分析管线"""

    def __init__(self, output_dir: str = ""):
        self.parser = VideoParser()
        self.extractor = FrameExtractor(output_dir=os.path.join(output_dir or os.getcwd(), "analysis_frames"))
        self.visual_analyzer = VisualAnalyzer()
        self.hook_analyzer = HookAnalyzer()
        self.action_analyzer = ActionAnalyzer()
        self.gameplay_analyzer = GameplayAnalyzer()
        self.consistency_checker = ConsistencyChecker()
        self.score_predictor = AdScorePredictor()
        self.report_generator = ReportGenerator(output_dir=os.path.join(output_dir or os.getcwd(), "analysis_reports"))

    def analyze(
        self,
        video_path: str,
        prompt_text: str = "",
        game_type: str = "merge",
        winner_dna_id: str = "",
    ) -> VideoAnalysisReport:
        """分析单个视频

        Args:
            video_path: 视频文件路径
            prompt_text: 生成视频的 prompt（用于内容分析）
            game_type: 游戏类型
            winner_dna_id: 参考的 Winner DNA ID

        Returns:
            VideoAnalysisReport
        """
        video_id = os.path.splitext(os.path.basename(video_path))[0]
        report = VideoAnalysisReport(
            video_id=video_id,
            video_path=video_path,
            game_type=game_type,
            winner_dna_id=winner_dna_id,
        )

        # Step 1: 视频解析
        report.video_info = self.parser.parse(video_path)

        # Step 2: 帧提取
        report.frames = self.extractor.extract(video_path, video_id=video_id)

        # Step 3: 视觉分析（基于 prompt）
        if prompt_text:
            report.visual_features = self.visual_analyzer.analyze(prompt_text)
            report.visual_score = self.visual_analyzer.score_visual_richness(report.visual_features)

        # Step 4: Hook 分析
        if prompt_text:
            report.hook_analysis = self.hook_analyzer.analyze(prompt_text)
            report.hook_score = report.hook_analysis.score

        # Step 5: Action 分析
        if prompt_text:
            report.action_analysis = self.action_analyzer.analyze(prompt_text)
            report.action_score = report.action_analysis.score

        # Step 6: Gameplay 分析
        if prompt_text:
            report.gameplay_analysis = self.gameplay_analyzer.analyze(prompt_text, game_type)
            report.gameplay_score = report.gameplay_analysis.score

        # Step 7: 一致性检查
        if prompt_text:
            report.consistency = self.consistency_checker.check(prompt_text)
            report.consistency_score = (
                report.consistency.character_consistency +
                report.consistency.color_consistency +
                report.consistency.style_consistency
            ) / 3

        # Step 8: 广告潜力预测
        if prompt_text:
            prediction = self.score_predictor.predict(
                hook=report.hook_analysis,
                action=report.action_analysis,
                gameplay=report.gameplay_analysis,
                consistency=report.consistency,
                visual=report.visual_features,
                visual_score=report.visual_score,
            )
            report.total_score = prediction["total_score"]
            report.level = prediction["level"]
            report.prediction = prediction["prediction"]

        # Step 9: 生成报告
        self.report_generator.generate(report)

        return report

    def analyze_batch(
        self,
        video_configs: list[dict[str, Any]],
    ) -> list[VideoAnalysisReport]:
        """批量分析

        Args:
            video_configs: [{"video_path": ..., "prompt": ..., "game_type": ...}, ...]

        Returns:
            VideoAnalysisReport 列表（按总分排序）
        """
        reports: list[VideoAnalysisReport] = []

        for i, config in enumerate(video_configs):
            print(f"[Analysis] {i+1}/{len(video_configs)}: {config.get('video_path', '')}")
            report = self.analyze(
                video_path=config["video_path"],
                prompt_text=config.get("prompt", ""),
                game_type=config.get("game_type", "merge"),
                winner_dna_id=config.get("winner_dna_id", ""),
            )
            reports.append(report)
            print(f"[Analysis]   Score: {report.total_score:.1f} | Prediction: {report.prediction}")

        # 排序
        reports.sort(key=lambda r: r.total_score, reverse=True)

        # 生成批量报告
        self.report_generator.generate_batch_report(reports)

        return reports

    def rank_videos(self, reports: list[VideoAnalysisReport], top_n: int = 10) -> list[VideoAnalysisReport]:
        """排序视频，返回 TOP N"""
        sorted_reports = sorted(reports, key=lambda r: r.total_score, reverse=True)
        return sorted_reports[:top_n]
