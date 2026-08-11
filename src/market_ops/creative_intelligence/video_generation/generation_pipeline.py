"""Generation Pipeline - 视频生成管线

完整流程：
Winner DNA -> Video Director -> ComfyUI Workflow -> 生成 -> 验证 -> 评分 -> 保存
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

from ..video_director import VideoDirector, WinnerDNA, GameInfo, AdGoal
from .comfyui_client import ComfyUIClient
from .workflow_executor import WorkflowExecutor
from .generation_queue import GenerationQueue
from .video_validator import VideoValidator
from .quality_scorer import QualityScorer
from .output_manager import OutputManager
from .models import GenerationResult, GenerationStatus, BatchConfig


class GenerationPipeline:
    """视频生成管线"""

    def __init__(
        self,
        comfyui_host: str = "192.168.124.13",
        comfyui_port: int = 8188,
        output_dir: str = "",
    ):
        self.director = VideoDirector()
        self.client = ComfyUIClient(host=comfyui_host, port=comfyui_port)
        self.executor = WorkflowExecutor()
        self.queue = GenerationQueue()
        self.validator = VideoValidator()
        self.scorer = QualityScorer()
        self.output = OutputManager(base_dir=output_dir)

    def run(
        self,
        winner_dna: WinnerDNA,
        game_info: GameInfo,
        ad_goal: AdGoal,
        model_preset: str = "wan2.1_i2v_480p",
        seed: int = -1,
        image_ref: str = "",
    ) -> GenerationResult:
        """执行完整生成管线（单条）

        Args:
            winner_dna: Winner DNA
            game_info: 游戏信息
            ad_goal: 广告目标
            model_preset: 模型预设
            seed: 随机种子
            image_ref: 首帧参考图路径

        Returns:
            GenerationResult
        """
        video_id = f"VG-{datetime.now().strftime('%Y%m%d')}-{winner_dna.source_video_id}"
        result = GenerationResult(
            video_id=video_id,
            status=GenerationStatus.PENDING,
            winner_dna_id=winner_dna.source_video_id,
            prompt="",
            negative_prompt="",
            seed=seed,
            model_preset=model_preset,
        )

        try:
            # Step 1: Video Director 生成方案
            print(f"[Pipeline] Step 1: Video Director 生成方案...")
            plan = self.director.direct(winner_dna, game_info, ad_goal)
            result.prompt = plan.comfyui_workflow.positive
            result.negative_prompt = plan.comfyui_workflow.negative
            result.metadata = {
                "creative_concept": plan.creative_concept,
                "hook": plan.hook,
                "content_type": plan.metadata.get("content_type", ""),
                "format": plan.metadata.get("format", ""),
            }

            # Step 2: 质量评分（生成前预评）
            print(f"[Pipeline] Step 2: 质量评分...")
            result.score = self.scorer.score(plan)
            print(f"[Pipeline]   Pre-generation score: {result.score.total_score:.1f}")

            # Step 3: 生成 Flux 首帧图（如果需要 I2V）
            flux_image = ""
            if "i2v" in model_preset and not image_ref:
                print(f"[Pipeline] Step 3: 生成 Flux 首帧图...")
                flux_workflow = self.executor.build_flux_workflow(plan, seed=seed)
                flux_result = self.client.generate(flux_workflow, timeout=120)
                if flux_result["success"]:
                    flux_filename = flux_result["filename"]
                    flux_image = os.path.join(self.output.base_dir, f"{video_id}_flux.png")
                    self.client.download_file(flux_filename, flux_image)
                    print(f"[Pipeline]   Flux image: {flux_image}")
                    image_ref = flux_filename  # 上传到 ComfyUI 后的文件名
                else:
                    print(f"[Pipeline]   Flux 生成失败: {flux_result['error']}")

            # Step 4: 生成 ComfyUI Workflow
            print(f"[Pipeline] Step 4: 构建 ComfyUI Workflow...")
            video_workflow = self.executor.build_video_workflow(
                plan, model_preset=model_preset, image_ref=image_ref, seed=seed
            )

            # 保存 workflow
            workflow_path = os.path.join(self.output.base_dir, f"{video_id}_workflow.json")
            with open(workflow_path, "w", encoding="utf-8") as f:
                json.dump(video_workflow, f, indent=2, ensure_ascii=False)
            result.workflow_path = workflow_path

            # Step 5: 提交 ComfyUI 生成
            print(f"[Pipeline] Step 5: 提交 ComfyUI 生成...")
            result.status = GenerationStatus.RUNNING
            gen_result = self.client.generate(video_workflow, timeout=600)
            result.comfyui_prompt_id = gen_result.get("prompt_id", "")

            if not gen_result["success"]:
                result.status = GenerationStatus.FAILED
                result.error = gen_result.get("error", "生成失败")
                print(f"[Pipeline]   生成失败: {result.error}")
                self.output.save_result(result)
                return result

            # Step 6: 下载视频
            print(f"[Pipeline] Step 6: 下载视频...")
            video_filename = gen_result["filename"]
            video_path = os.path.join(self.output.base_dir, f"{video_id}.mp4")
            self.client.download_file(video_filename, video_path)
            result.video_path = video_path
            print(f"[Pipeline]   视频下载完成: {video_path}")

            # Step 7: 验证视频
            print(f"[Pipeline] Step 7: 验证视频...")
            result.validation = self.validator.validate(video_path)
            if not result.validation.valid:
                result.status = GenerationStatus.FAILED
                result.error = "; ".join(result.validation.issues)
                print(f"[Pipeline]   验证失败: {result.error}")
            else:
                result.status = GenerationStatus.VALIDATED
                print(f"[Pipeline]   验证通过: {result.validation.resolution}, "
                      f"{result.validation.duration:.1f}s, {result.validation.fps:.1f}fps")

            # Step 8: 保存结果
            print(f"[Pipeline] Step 8: 保存结果...")
            result.completed_at = datetime.now().isoformat()
            out_dir = self.output.save_result(result)
            print(f"[Pipeline]   结果保存到: {out_dir}")

        except Exception as e:
            result.status = GenerationStatus.FAILED
            result.error = str(e)
            print(f"[Pipeline]   异常: {e}")

        return result

    def run_batch(
        self,
        winner_dnas: list[WinnerDNA],
        game_info: GameInfo,
        ad_goal: AdGoal,
        batch_config: BatchConfig | None = None,
        model_preset: str = "wan2.1_i2v_480p",
    ) -> list[GenerationResult]:
        """批量生成

        Returns:
            GenerationResult 列表
        """
        results: list[GenerationResult] = []

        for i, dna in enumerate(winner_dnas):
            print(f"\n{'='*60}")
            print(f"[Batch] 生成 {i+1}/{len(winner_dnas)}: {dna.source_video_id} (ROAS: {dna.roas:.2f})")
            print(f"{'='*60}")

            result = self.run(dna, game_info, ad_goal, model_preset=model_preset)
            results.append(result)

            if result.status == GenerationStatus.VALIDATED:
                print(f"[Batch]   SUCCESS - Score: {result.score.total_score:.1f}")
            else:
                print(f"[Batch]   FAILED - Error: {result.error}")

        # 生成报告
        report_path = self.output.save_generation_report(results)
        print(f"\n[Batch] 报告已保存: {report_path}")

        return results

    def health_check(self) -> dict[str, Any]:
        """检查管线健康状态"""
        comfyui_status = self.client.health_check()
        return {
            "comfyui_connected": comfyui_status.get("ok", False),
            "comfyui_info": comfyui_status,
            "pipeline_ready": comfyui_status.get("ok", False),
        }
