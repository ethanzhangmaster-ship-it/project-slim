"""Prompt Compiler - 提示词编译器核心

将 Blueprint 输出编译为平台无关的 Master Prompt。

编译流程：
Blueprint → Parser → Normalize → Merge → Optimize → Validate → Master Prompt
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ..models.master_prompt import (
    CameraMetadata,
    CompilerContext,
    EditingMetadata,
    MasterPrompt,
    Metadata,
    MusicMetadata,
    PromptAST,
    PromptToken,
    ScenePrompt,
    SubtitleMetadata,
    ValidationResult,
)
from .prompt_optimizer import PromptOptimizer
from .prompt_renderer import PromptRenderer
from .prompt_statistics import PromptStatisticsGenerator
from .prompt_template import PromptTemplate


class BlueprintParser:
    """Blueprint 解析器"""

    def parse(self, blueprint_dir: str) -> CompilerContext:
        """解析 Blueprint 目录"""
        ctx = CompilerContext()
        bp_dir = Path(blueprint_dir)

        files = {
            "camera_spec": ("camera_spec.json", "specs"),
            "shot_list": ("shot_list.json", "shots"),
            "asset_spec": ("asset_spec.json", "mappings"),
            "editing_spec": ("editing_spec.json", "scenes"),
            "subtitle_spec": ("subtitle_spec.json", "scenes"),
            "music_spec": ("music_spec.json", "segments"),
            "prompt_package": ("prompt_package.json", "packages"),
        }

        for attr, (fname, key) in files.items():
            path = bp_dir / fname
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    setattr(ctx, f"{attr}s", data.get(key, []))

        return ctx


class PromptCompiler:
    """提示词编译器"""

    def __init__(self, blueprint_dir: str):
        self.blueprint_dir = Path(blueprint_dir)
        self.parser = BlueprintParser()
        self.optimizer = PromptOptimizer()
        self.renderer = PromptRenderer()
        self.statistics_generator = PromptStatisticsGenerator()
        self.template = PromptTemplate()

    def compile(self) -> MasterPrompt:
        """执行完整编译流程"""
        ctx = self.parser.parse(str(self.blueprint_dir))

        master = MasterPrompt()
        master.variant_id = self._extract_variant_id(ctx)

        for shot in ctx.shot_lists:
            scene_id = shot.get("shot_id", "")
            scene_name = shot.get("scene_name", "")

            ast = self._build_ast(ctx, shot, scene_name)

            optimized_ast = self.optimizer.optimize(ast)

            scene_prompt = self._ast_to_scene_prompt(optimized_ast, ctx, shot, scene_name)

            master.scenes.append(scene_prompt)

        return master

    def _extract_variant_id(self, ctx: CompilerContext) -> str:
        """提取 Variant ID"""
        if ctx.shot_lists:
            return ctx.shot_lists[0].get("shot_id", "").split("_")[0]
        return "V001"

    def _build_ast(self, ctx: CompilerContext, shot: Dict[str, Any], scene_name: str) -> PromptAST:
        """构建 Prompt AST"""
        ast = PromptAST(scene_id=shot.get("shot_id", ""))

        tokens = []

        tokens.extend(self._build_camera_tokens(shot.get("camera", {})))

        tokens.extend(self._build_editing_tokens(ctx, scene_name))

        tokens.extend(self._build_asset_tokens(ctx, shot.get("shot_id", "")))

        tokens.extend(self._build_prompt_tokens(ctx, scene_name))

        if shot.get("motion"):
            tokens.append(PromptToken(
                content=f"motion: {shot['motion']}",
                type="motion",
                weight=1.0,
                tags=["motion"],
            ))

        if shot.get("character"):
            tokens.append(PromptToken(
                content=f"character: {shot['character']}",
                type="character",
                weight=1.0,
                tags=["character"],
            ))

        if shot.get("environment"):
            tokens.append(PromptToken(
                content=f"environment: {shot['environment']}",
                type="scene",
                weight=1.0,
                tags=["scene"],
            ))

        if shot.get("fx"):
            fx_list = shot["fx"] if isinstance(shot["fx"], list) else [shot["fx"]]
            tokens.append(PromptToken(
                content=f"effects: {', '.join(fx_list)}",
                type="fx",
                weight=0.9,
                tags=["fx"],
            ))

        ast.tokens = tokens
        return ast

    def _build_camera_tokens(self, camera: Dict[str, Any]) -> List[PromptToken]:
        """构建相机参数 Token"""
        tokens = []
        if not camera:
            return tokens

        camera_prompts = self.template.generate_camera_prompt(camera)
        for prompt in camera_prompts:
            tokens.append(PromptToken(
                content=prompt,
                type="camera",
                weight=1.0,
                tags=["camera"],
            ))
        return tokens

    def _build_editing_tokens(self, ctx: CompilerContext, scene_name: str) -> List[PromptToken]:
        """构建编辑参数 Token"""
        tokens = []
        editing = next((e for e in ctx.editing_specs if e.get("scene_name") == scene_name), {})
        if not editing:
            return tokens

        editing_prompts = self.template.generate_editing_prompt(editing)
        for prompt in editing_prompts:
            tokens.append(PromptToken(
                content=prompt,
                type="lighting",
                weight=0.8,
                tags=["editing"],
            ))
        return tokens

    def _build_asset_tokens(self, ctx: CompilerContext, shot_id: str) -> List[PromptToken]:
        """构建资源参数 Token"""
        tokens = []
        asset = next((a for a in ctx.asset_specs if a.get("shot_id") == shot_id), {})
        if not asset:
            return tokens

        asset_prompts = self.template.generate_asset_prompt(asset)
        for prompt in asset_prompts:
            tokens.append(PromptToken(
                content=prompt,
                type="scene",
                weight=1.0,
                tags=["asset"],
            ))
        return tokens

    def _build_prompt_tokens(self, ctx: CompilerContext, scene_name: str) -> List[PromptToken]:
        """构建提示词 Token"""
        tokens = []
        prompt_pkg = next((p for p in ctx.prompt_packages if p.get("scene_name") == scene_name), {})
        if not prompt_pkg:
            return tokens

        mapping = {
            "image_prompt": ("scene", 1.2),
            "video_prompt": ("camera", 1.1),
            "motion_prompt": ("motion", 1.0),
            "character_prompt": ("character", 1.0),
            "lighting_prompt": ("lighting", 0.9),
            "negative_prompt": ("negative", 1.0),
        }

        for key, (ptype, weight) in mapping.items():
            value = prompt_pkg.get(key, "")
            if value and value.strip():
                tokens.append(PromptToken(
                    content=value,
                    type=ptype,
                    weight=weight,
                    tags=[key.replace("_prompt", "")],
                ))

        return tokens

    def _ast_to_scene_prompt(self, ast: PromptAST, ctx: CompilerContext,
                              shot: Dict[str, Any], scene_name: str) -> ScenePrompt:
        """将 AST 转换为 ScenePrompt"""
        scene_prompt = ScenePrompt(scene_id=ast.scene_id)

        prompt_pkg = next((p for p in ctx.prompt_packages if p.get("scene_name") == scene_name), {})

        scene_prompt.image_prompt = prompt_pkg.get("image_prompt", "")
        scene_prompt.video_prompt = prompt_pkg.get("video_prompt", "")
        scene_prompt.motion_prompt = prompt_pkg.get("motion_prompt", "")
        scene_prompt.lighting_prompt = prompt_pkg.get("lighting_prompt", "")
        scene_prompt.character_prompt = prompt_pkg.get("character_prompt", "")
        scene_prompt.negative_prompt = prompt_pkg.get("negative_prompt", "")

        scene_prompt.metadata = self._build_metadata(ctx, shot, scene_name)

        return scene_prompt

    def _build_metadata(self, ctx: CompilerContext, shot: Dict[str, Any], scene_name: str) -> Metadata:
        """构建元数据"""
        metadata = Metadata()

        camera = shot.get("camera", {})
        metadata.camera = CameraMetadata(
            lens=camera.get("lens", ""),
            move=camera.get("move", ""),
            move_speed=camera.get("move_speed", ""),
            zoom=camera.get("zoom", ""),
            focus=camera.get("focus", ""),
            depth=camera.get("depth", ""),
            shake=camera.get("shake", ""),
            frame_rate=camera.get("frame_rate", 60),
            fov=camera.get("fov", ""),
        )

        editing = next((e for e in ctx.editing_specs if e.get("scene_name") == scene_name), {})
        metadata.editing = EditingMetadata(
            exposure=editing.get("exposure", 0.0),
            contrast=editing.get("contrast", 1.0),
            highlight=editing.get("highlight", 0.0),
            shadow=editing.get("shadow", 0.0),
            temperature=editing.get("temperature", 5500),
            tint=editing.get("tint", 0),
            saturation=editing.get("saturation", 1.0),
            sharpness=editing.get("sharpness", 1.0),
            film_grain=editing.get("film_grain", 0.0),
            bloom=editing.get("bloom", 0.0),
            chromatic=editing.get("chromatic", 0.0),
            motion_blur=editing.get("motion_blur", 0.0),
            particles=editing.get("particles", ""),
            lut=editing.get("lut", ""),
        )

        subtitle = next((s for s in ctx.subtitle_specs if s.get("scene_name") == scene_name), {})
        metadata.subtitle = SubtitleMetadata(
            caption=subtitle.get("caption", ""),
            voice=subtitle.get("voice", ""),
            popup=subtitle.get("popup", ""),
            reward_text=subtitle.get("reward_text", ""),
            cta_overlay=subtitle.get("cta_overlay", ""),
            font=subtitle.get("font", ""),
            color=subtitle.get("color", ""),
            animation=subtitle.get("animation", ""),
            timing=subtitle.get("timing", ""),
        )

        music = next((m for m in ctx.music_specs if m.get("scene_name") == scene_name), {})
        metadata.music = MusicMetadata(
            genre=music.get("genre", ""),
            mood=music.get("mood", ""),
            energy=music.get("energy", ""),
            bpm=music.get("bpm", 0),
            timeline=music.get("timeline", []),
            beat_marker=music.get("beat_marker", []),
        )

        return metadata

    def validate(self, master: MasterPrompt) -> ValidationResult:
        """验证 Master Prompt"""
        result = ValidationResult()

        for scene in master.scenes:
            if not scene.scene_id:
                result.passed = False
                result.errors.append(f"Scene has empty scene_id")

            prompts = [
                scene.image_prompt,
                scene.video_prompt,
                scene.motion_prompt,
                scene.lighting_prompt,
                scene.character_prompt,
                scene.negative_prompt,
            ]

            for i, prompt in enumerate(prompts):
                if prompt and len(prompt.split()) > 2000:
                    result.warnings.append(f"{scene.scene_id}: Prompt {i} exceeds 2000 tokens")

                if prompt and any(char in prompt for char in ['\x00', '\x01']):
                    result.passed = False
                    result.errors.append(f"{scene.scene_id}: Prompt contains illegal characters")

        if not master.scenes:
            result.passed = False
            result.errors.append("Master Prompt has no scenes")

        return result

    def compile_and_save(self, output_dir: str) -> Dict[str, Any]:
        """编译并保存所有输出"""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        master = self.compile()

        validation = self.validate(master)

        stats = self.statistics_generator.generate(master)

        base_path = str(out_dir / "master_prompt")
        rendered_paths = self.renderer.render_all(master, base_path)

        with open(out_dir / "validation_report.json", "w", encoding="utf-8") as f:
            json.dump({
                "passed": validation.passed,
                "errors": validation.errors,
                "warnings": validation.warnings,
            }, f, indent=2, ensure_ascii=False)

        self.statistics_generator.save(stats, str(out_dir / "prompt_statistics.json"))

        return {
            "master_prompt": master.to_dict(),
            "validation": {
                "passed": validation.passed,
                "errors": len(validation.errors),
                "warnings": len(validation.warnings),
            },
            "statistics": {
                "total_tokens": stats.total_tokens,
                "total_prompts": stats.total_prompts,
                "avg_length": round(stats.avg_length, 2),
                "duplicate_rate": round(stats.duplicate_rate, 4),
                "compression_rate": round(stats.compression_rate, 4),
            },
            "output_files": rendered_paths + [
                str(out_dir / "validation_report.json"),
                str(out_dir / "prompt_statistics.json"),
            ],
        }