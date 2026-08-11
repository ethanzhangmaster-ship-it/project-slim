"""Blueprint API - V4.4 统一接口

统一入口:
api.generate_blueprint()
↓
Video DNA → Blueprint → Story Pattern → Storyboard → Shot List
→ Asset Mapping → Editing Guide → Prompt Package → Creative Review

同时生成:
Camera Language / Pacing / Transition / Subtitle / Music / Quality Check

输出保存到 DuckDB Blueprint Memory。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from .video_dna_engine import VideoDNA, VideoDNAEngine
from .blueprint_engine import BlueprintEngine, VideoBlueprint
from .story_pattern_engine import StoryPatternEngine, StoryPattern
from .storyboard_engine import StoryboardEngine, Storyboard
from .shotlist_engine import ShotlistEngine, Shotlist
from .asset_mapping_engine import AssetMappingEngine, AssetMap
from .camera_engine import CameraEngine, CameraProfile
from .pacing_engine import PacingEngine, PacingProfile
from .transition_engine import TransitionEngine, TransitionProfile
from .subtitle_engine import SubtitleEngine, SubtitleProfile
from .music_engine import MusicEngine, MusicProfile
from .editing_engine import EditingEngine, EditingGuide
from .prompt_package_engine import PromptPackageEngine, PromptPackageCollection
from .creative_review import CreativeReviewEngine, CreativeReview
from .quality_checker import QualityChecker, QualityReport
from .blueprint_memory import BlueprintMemory


@dataclass
class BlueprintOutput:
    """完整 Blueprint 输出 (V4.4)"""
    variant_id: str
    dna: VideoDNA
    blueprint: VideoBlueprint
    story_pattern: StoryPattern
    storyboard: Storyboard
    shotlist: Shotlist
    asset_mapping: AssetMap
    camera_spec: CameraProfile
    pacing: PacingProfile
    transition: TransitionProfile
    subtitle: SubtitleProfile
    music: MusicProfile
    editing: EditingGuide
    prompt_package: PromptPackageCollection
    creative_review: CreativeReview
    quality: QualityReport
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "dna": self.dna.to_dict(),
            "blueprint": self.blueprint.to_dict(),
            "story_pattern": self.story_pattern.to_dict(),
            "storyboard": self.storyboard.to_dict(),
            "shotlist": self.shotlist.to_dict(),
            "asset_mapping": self.asset_mapping.to_dict(),
            "camera_spec": self.camera_spec.to_dict(),
            "pacing": self.pacing.to_dict(),
            "transition": self.transition.to_dict(),
            "subtitle": self.subtitle.to_dict(),
            "music": self.music.to_dict(),
            "editing": self.editing.to_dict(),
            "prompt_package": self.prompt_package.to_dict(),
            "creative_review": self.creative_review.to_dict(),
            "quality": self.quality.to_dict(),
            "metadata": self.metadata,
        }


class BlueprintAPI:
    """V4.4 统一 Blueprint API"""

    def __init__(
        self,
        output_dir: str = "output/video_blueprint",
        db_path: str = "output/video_blueprint/database/blueprint_library.duckdb",
    ):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 初始化所有引擎
        self.dna_engine = VideoDNAEngine()
        self.blueprint_engine = BlueprintEngine()
        self.story_pattern_engine = StoryPatternEngine()
        self.storyboard_engine = StoryboardEngine()
        self.shotlist_engine = ShotlistEngine()
        self.asset_mapping_engine = AssetMappingEngine()
        self.camera_engine = CameraEngine()
        self.pacing_engine = PacingEngine()
        self.transition_engine = TransitionEngine()
        self.subtitle_engine = SubtitleEngine()
        self.music_engine = MusicEngine()
        self.editing_engine = EditingEngine()
        self.prompt_package_engine = PromptPackageEngine()
        self.creative_review_engine = CreativeReviewEngine()
        self.quality_checker = QualityChecker()
        self.memory = BlueprintMemory(db_path=db_path)

    def generate_blueprint(self, variant: dict[str, Any]) -> BlueprintOutput:
        """生成完整 Blueprint (V4.4 主入口)

        Args:
            variant: V4.2.2 Decision Variant

        Returns:
            BlueprintOutput - 包含所有产物
        """
        # 1. Video DNA
        dna = self.dna_engine.generate(variant)

        # 2. Story Pattern
        story_pattern = self.story_pattern_engine.generate(dna, variant)

        # 3. Blueprint
        blueprint = self.blueprint_engine.generate(dna, story_pattern)

        # 4. Storyboard
        storyboard = self.storyboard_engine.generate(dna, blueprint, story_pattern)

        # 5. Shotlist
        shotlist = self.shotlist_engine.generate(dna, storyboard)

        # 6. Asset Mapping
        asset_mapping = self.asset_mapping_engine.generate(dna, shotlist)

        # 7. Camera Spec
        camera_spec = self.camera_engine.generate(dna, storyboard)

        # 8. Pacing
        pacing = self.pacing_engine.generate(dna, blueprint, shotlist)

        # 9. Transition
        transition = self.transition_engine.generate(dna)

        # 10. Subtitle
        subtitle = self.subtitle_engine.generate(dna, blueprint)

        # 11. Music
        music = self.music_engine.generate(dna, blueprint)

        # 12. Editing Guide
        editing = self.editing_engine.generate(dna, storyboard)

        # 13. Prompt Package
        prompt_package = self.prompt_package_engine.generate(dna, storyboard)

        # 14. Creative Review
        creative_review = self.creative_review_engine.review(dna, blueprint, storyboard, shotlist)

        # 15. Quality Check
        quality = self.quality_checker.check(dna, blueprint, storyboard, shotlist, subtitle, music=music, editing=editing)

        output = BlueprintOutput(
            variant_id=dna.variant_id,
            dna=dna,
            blueprint=blueprint,
            story_pattern=story_pattern,
            storyboard=storyboard,
            shotlist=shotlist,
            asset_mapping=asset_mapping,
            camera_spec=camera_spec,
            pacing=pacing,
            transition=transition,
            subtitle=subtitle,
            music=music,
            editing=editing,
            prompt_package=prompt_package,
            creative_review=creative_review,
            quality=quality,
            metadata={
                "platform": dna.platform,
                "placement": dna.placement,
                "duration": blueprint.video_length,
                "hook_type": dna.hook,
                "emotion": dna.emotion,
                "story_pattern": dna.story_pattern,
                "gameplay_type": story_pattern.gameplay_type,
                "rhythm": dna.rhythm,
            },
        )

        # 16. 保存到 Blueprint Memory
        self.memory.save_blueprint(
            variant_id=dna.variant_id,
            dna=dna.to_dict(),
            blueprint=blueprint.to_dict(),
            storyboard=storyboard.to_dict(),
            shotlist=shotlist.to_dict(),
        )

        return output

    def export(self, output: BlueprintOutput, sub_dir: str | None = None) -> dict[str, str]:
        """导出所有产物到 JSON

        Returns:
            字典 {产物名: 文件路径}
        """
        base_dir = self.output_dir
        if sub_dir:
            base_dir = os.path.join(base_dir, sub_dir)
        os.makedirs(base_dir, exist_ok=True)

        paths: dict[str, str] = {}
        vid = output.variant_id

        files = {
            "blueprint.json": output.blueprint,
            "story_pattern.json": output.story_pattern,
            "storyboard.json": output.storyboard,
            "shot_list.json": output.shotlist,
            "asset_spec.json": output.asset_mapping,
            "camera_spec.json": output.camera_spec,
            "pacing.json": output.pacing,
            "transition.json": output.transition,
            "subtitle_spec.json": output.subtitle,
            "music_spec.json": output.music,
            "editing_spec.json": output.editing,
            "prompt_package.json": output.prompt_package,
            "creative_review.json": output.creative_review,
            "quality_report.json": output.quality,
        }

        for filename, obj in files.items():
            p = os.path.join(base_dir, filename)
            with open(p, "w", encoding="utf-8") as f:
                if hasattr(obj, "to_dict"):
                    json.dump(obj.to_dict(), f, ensure_ascii=False, indent=2)
                else:
                    json.dump(obj, f, ensure_ascii=False, indent=2)
            paths[filename.replace(".json", "")] = p

        # Markdown 报告
        md_path = os.path.join(base_dir, "creative_blueprint.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._generate_markdown(output))
        paths["blueprint_report_md"] = md_path

        return paths

    def _generate_markdown(self, output: BlueprintOutput) -> str:
        """生成 Markdown 报告"""
        bp = output.blueprint
        dna = output.dna
        cr = output.creative_review

        lines = [
            f"# Video Blueprint - {bp.variant_id}",
            "",
            "## 基本信息",
            f"- 视频时长: {bp.video_length}s",
            f"- 情绪: {dna.emotion}",
            f"- Hook: {dna.hook}",
            f"- Story Pattern: {dna.story_pattern}",
            f"- 受众: {dna.audience}",
            f"- 平台: {dna.platform} / {dna.placement}",
            f"- 玩法类型: {output.story_pattern.gameplay_type}",
            "",
            "## Video DNA",
            f"- Hook Style: {dna.hook}",
            f"- Emotion: {dna.emotion}",
            f"- Camera Style: {dna.camera_style}",
            f"- Editing Style: {dna.editing_style}",
            f"- Music Style: {dna.music_style}",
            f"- Transition Style: {dna.transition_style}",
            f"- Color Style: {dna.color_style}",
            f"- Lighting Style: {dna.lighting_style}",
            f"- CTA Style: {dna.cta_style}",
            f"- Rhythm: {dna.rhythm}",
            "",
            "## 时间结构",
        ]

        for seg in bp.segments:
            lines.append(f"- {seg['name']}: {seg['start']}-{seg['end']}s ({seg['duration']}s) - {seg['description']}")

        lines.extend([
            "",
            "## Camera 规范",
            f"- 推荐运镜: {output.camera_spec.recommended_move}",
            f"- 可用运镜: {', '.join(output.camera_spec.all_moves)}",
            "",
            "### 场景运镜参数",
        ])
        for spec in output.camera_spec.specs:
            lines.extend([
                f"- {spec.move}:",
                f"  - Lens: {spec.lens}",
                f"  - Move: {spec.move}",
                f"  - Move Speed: {spec.move_speed}",
                f"  - Zoom: {spec.zoom}",
                f"  - Focus: {spec.focus}",
                f"  - Depth: {spec.depth}",
                f"  - Shake: {spec.shake}",
                f"  - Frame Rate: {spec.frame_rate}",
                f"  - FOV: {spec.fov}",
            ])

        lines.extend([
            "",
            "## 分镜",
        ])
        for scene in output.storyboard.scenes:
            lines.append(f"### Scene {scene.scene_index} - {scene.name}")
            lines.append(f"- 时间: {scene.start_time}-{scene.end_time}s")
            lines.append(f"- 描述: {scene.description}")
            lines.append(f"- 运镜: {scene.camera}")
            lines.append(f"- 灯光: {scene.lighting}")
            lines.append(f"- 动作: {scene.motion}")
            lines.append(f"- 字幕: {scene.subtitle}")
            lines.append(f"- 转场: {scene.transition}")
            if scene.fx:
                lines.append(f"- FX: {', '.join(scene.fx)}")
            lines.append("")

        lines.extend([
            f"## 镜头列表",
            f"- 总镜头: {output.shotlist.total_shots}",
            f"- 平均时长: {output.shotlist.total_duration / max(1, output.shotlist.total_shots):.2f}s",
            "",
            "## 素材映射",
        ])
        for m in output.asset_mapping.mappings[:5]:
            lines.append(f"- {m.shot_id}: BG={m.background}, Char={m.character}, FX={m.fx}, LUT={m.lut}")
        if len(output.asset_mapping.mappings) > 5:
            lines.append(f"- ... 共 {len(output.asset_mapping.mappings)} 个镜头映射")

        lines.extend([
            "",
            f"## 节奏",
            f"- 每秒镜头: {output.pacing.shots_per_second}",
            f"- 平均镜头时长: {output.pacing.avg_shot_length}s",
            "",
        ])
        for seg in output.pacing.segments:
            lines.append(f"- {seg['start']}-{seg['end']}s: {seg['label']} (每秒{seg['shots_per_sec']}镜头)")

        lines.extend([
            "",
            f"## 转场",
            f"- 推荐: {', '.join(output.transition.recommended)}",
            "",
            f"## 字幕",
        ])
        for sspec in output.subtitle.scenes:
            lines.append(f"- {sspec.scene_name}: {sspec.caption} (voice={sspec.voice}, popup={sspec.popup}, anim={sspec.animation}, timing={sspec.timing})")

        lines.extend([
            "",
            f"## 音乐",
            f"- BPM: {output.music.bpm}",
            f"- Mood: {output.music.mood}",
            f"- Genre: {output.music.genre}",
            "",
        ])
        for seg in output.music.segments:
            lines.append(f"- {seg.name} {seg.start}-{seg.end}s | Energy={seg.energy} | BPM={seg.bpm}")

        lines.extend([
            "",
            f"## 剪辑规范",
        ])
        for espec in output.editing.scenes:
            lines.append(f"- {espec.scene_name}: LUT={espec.lut}, Exposure={espec.exposure}, Contrast={espec.contrast}, Temp={espec.temperature}, Tint={espec.tint}, Sharpness={espec.sharpness}, Grain={espec.film_grain}, Bloom={espec.bloom}, Particles={espec.particles}, MotionBlur={espec.motion_blur}")

        lines.extend([
            "",
            f"## Prompt Package",
        ])
        for pkg in output.prompt_package.packages[:3]:
            lines.append(f"### {pkg.scene_name}")
            lines.append(f"- Image Prompt: {pkg.image_prompt}")
            lines.append(f"- Video Prompt: {pkg.video_prompt}")
            lines.append(f"- Motion Prompt: {pkg.motion_prompt}")
            lines.append(f"- Character Prompt: {pkg.character_prompt}")
            lines.append(f"- Lighting Prompt: {pkg.lighting_prompt}")
            lines.append(f"- Negative Prompt: {pkg.negative_prompt}")
        if len(output.prompt_package.packages) > 3:
            lines.append(f"- ... 共 {len(output.prompt_package.packages)} 个场景")

        lines.extend([
            "",
            f"## Creative Review",
            f"- Overall: {cr.overall_score}/100",
            f"- Facebook Score: {cr.facebook_score}",
            f"- Hook Score: {cr.hook_score}",
            f"- Story Score: {cr.story_score}",
            f"- Emotion Score: {cr.emotion_score}",
            f"- Camera Score: {cr.camera_score}",
            f"- Editing Score: {cr.editing_score}",
            f"- Visual Score: {cr.visual_score}",
            f"- Retention Score: {cr.retention_score}",
            f"- Novelty Score: {cr.novelty_score}",
            f"- CTR Score: {cr.ctr_score}",
            f"- ROAS Confidence: {cr.roas_confidence}",
            f"- Predicted CTR: {cr.predicted_ctr}",
            f"- Predicted IPM: {cr.predicted_ipm}",
            f"- Predicted ROAS: {cr.predicted_roas}",
            f"- Verdict: {cr.verdict}",
            "",
            f"## 质量检查",
            f"- 分数: {output.quality.score}/100",
            f"- 通过检查: {len(output.quality.passed)}",
            f"- 问题数: {len(output.quality.issues)}",
        ])

        if output.quality.suggestions:
            lines.append("")
            lines.append("### 建议")
            for i, s in enumerate(output.quality.suggestions, 1):
                lines.append(f"{i}. {s}")

        return "\n".join(lines)


# 全局单例
_api_instance: BlueprintAPI | None = None


def get_blueprint_api() -> BlueprintAPI:
    """获取全局 API 实例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = BlueprintAPI()
    return _api_instance
