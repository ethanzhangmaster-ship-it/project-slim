"""Video Assembly Engine — 提取、标准化、拼接"""
import subprocess
from pathlib import Path
from typing import List

from ..models import RemixRecipe, RemixSegment
from ..config import FFMPEG_PRESET, FFMPEG_CRF, FADE_DURATION


class VideoAssembler:
    """视频组装引擎"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def assemble(self, recipe: RemixRecipe, recipe_dir: Path) -> Path:
        """根据配方组装最终视频"""
        proj_dir = recipe_dir / recipe.recipe_id
        proj_dir.mkdir(parents=True, exist_ok=True)

        clip_files = []

        for i, seg in enumerate(recipe.segments):
            out_clip = proj_dir / f"seg_{i:02d}_{seg.role}.mp4"
            clip_files.append(out_clip)

            if out_clip.exists():
                continue

            success = self._extract_segment(seg, out_clip)
            if not success:
                print(f"    ⚠️ 提取失败: {seg.v_num} @{seg.start}s")

        # concat
        final = self._concat_clips(clip_files, proj_dir / f"{recipe.recipe_id}.mp4")
        return final

    def _extract_segment(self, seg: RemixSegment, out_path: Path) -> bool:
        """提取单个片段（保留音频 + fade 转场）"""
        src = seg.filepath
        start = seg.start
        dur = seg.duration

        fade_in = f"fade=t=in:st=0:d={FADE_DURATION}"
        fade_out = f"fade=t=out:st={max(0.1,dur-FADE_DURATION)}:d={FADE_DURATION}"
        vf = f"{fade_in},{fade_out}"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", str(src),
            "-t", str(dur),
            "-vf", vf,
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF),
            "-c:a", "aac", "-b:a", "192k",
            str(out_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def _concat_clips(self, clip_files: List[Path], final_path: Path) -> Path:
        """拼接所有片段"""
        if not clip_files:
            return final_path

        # 过滤掉不存在的
        valid = [c for c in clip_files if c.exists()]
        if not valid:
            return final_path

        concat_list = final_path.parent / "concat_list.txt"
        concat_list.write_text("\n".join(f"file '{c}'" for c in valid), encoding="utf-8")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", str(FFMPEG_CRF),
            "-c:a", "aac", "-b:a", "192k",
            str(final_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and final_path.exists():
            return final_path
        return final_path
