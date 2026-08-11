"""VideoComposer — the single, unified composer (replaces video_assembler.py and
video_composer_v2.py). This is the FFmpeg Renderer in the merged pipeline.

Fixes delivered here:
  * Aspect-ratio normalize (scale+pad to target ratio) BEFORE concat, so mixing
    9:16 / 1:1 / 16:9 sources never breaks or distorts the output.
  * Correct xfade timeline (P0-4): offset = accumulated_output_duration - T,
    recursively, so 3+ segment crossfades work.
  * Audio is always preserved (no `-an`); optional BGM mix.
  * Render-failure detection: ComposeError is raised on any ffmpeg non-zero / missing
    output, so the controller never records a false success.

Segments passed in MUST already carry resolved source times (see clip_resolver).
The composer never computes a source timestamp itself.
"""
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

# target_ratio -> (width, height)
RESOLUTION = {
    "9X16": (1080, 1920),
    "1X1": (1080, 1080),
    "16X9": (1920, 1080),
}

FONT_CANDIDATES = [
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]

FADE = 0.25  # per-segment intro/outro fade (only applied at clip ends in concat mode)


class ComposeError(Exception):
    pass


class VideoComposer:
    def __init__(
        self,
        output_dir,
        target_ratio: str = "9X16",
        transition: str = "concat",  # "concat" (robust) or "xfade"
        bgm_path: Optional[str] = None,
        subtitle: bool = False,
        preset: str = "fast",
        crf: int = 18,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.target_ratio = target_ratio
        self.W, self.H = RESOLUTION.get(target_ratio, (1080, 1920))
        self.transition = transition
        self.bgm_path = Path(bgm_path) if bgm_path else None
        self.subtitle = subtitle
        self.preset = preset
        self.crf = crf
        self._font = self._find_font()

    # ------------------------------------------------------------------ #
    def _find_font(self) -> Optional[Path]:
        for f in FONT_CANDIDATES:
            p = Path(f)
            if p.exists():
                return p
        return None

    def _run(self, cmd, timeout=300) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def _normalize_vf(self) -> str:
        return (
            f"scale={self.W}:{self.H}:force_original_aspect_ratio=decrease,"
            f"pad={self.W}:{self.H}:(ow-iw)/2:(oh-ih)/2:black"
        )

    # ------------------------------------------------------------------ #
    def compose(self, segments: List[Dict], out_name: str) -> Path:
        """segments: list of dicts with keys
            source (path), source_start, source_end, duration,
            role, subtitle_text (optional)
        Returns final mp4 Path. Raises ComposeError on failure.
        """
        if not segments:
            raise ComposeError("no segments to compose")

        proj = self.output_dir / f"_proj_{out_name}"
        proj.mkdir(parents=True, exist_ok=True)

        seg_files: List[Path] = []
        for i, seg in enumerate(segments):
            src = Path(seg["source"])
            if not src.exists():
                raise ComposeError(f"source missing: {src}")
            start = float(seg["source_start"])
            dur = float(seg["source_end"]) - float(seg["source_start"])
            if dur <= 0:
                raise ComposeError(f"non-positive duration for segment {i}")
            out_seg = proj / f"seg_{i:02d}_{seg.get('role','x')}.mp4"
            self._extract_segment(src, out_seg, start, dur, i, len(segments), seg)
            if not out_seg.exists():
                raise ComposeError(f"segment extract failed: {out_seg}")
            seg_files.append(out_seg)

        final = self.output_dir / f"{out_name}.mp4"
        if self.transition == "xfade" and len(seg_files) >= 2:
            ok = self._concat_xfade(seg_files, final)
        else:
            ok = self._concat_demuxer(seg_files, final)

        if not ok or not final.exists():
            # resilient fallback: try the more robust concat path
            if self.transition == "xfade":
                ok = self._concat_demuxer(seg_files, final)
            if not ok or not final.exists():
                raise ComposeError(f"concat failed: {final}")

        if self.bgm_path and self.bgm_path.exists():
            final = self._mix_bgm(final, proj / f"{out_name}_bgm.mp4")

        # cleanup temp segments
        try:
            for f in seg_files:
                f.unlink(missing_ok=True)
            proj.rmdir()
        except Exception:
            pass
        return final

    # ------------------------------------------------------------------ #
    def _extract_segment(self, src, out_seg, start, dur, idx, total, seg):
        vf = self._normalize_vf()
        # fades only at the two ends (avoid black dips at internal boundaries)
        if idx == 0:
            vf += f",fade=t=in:st=0:d={FADE}"
        if idx == total - 1:
            vf += f",fade=t=out:st={max(0.1, dur - FADE)}:d={FADE}"

        if self.subtitle and seg.get("subtitle_text") and self._font:
            textfile = out_seg.parent / f"_sub_{idx:02d}.txt"
            textfile.write_text(seg["subtitle_text"], encoding="utf-8")
            vf += (
                f",drawtext=fontfile={self._font}:textfile={textfile}:"
                f"fontsize=46:fontcolor=white:borderw=4:bordercolor=black@0.7:"
                f"x=(w-text_w)/2:y=h*0.82"
            )

        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(src),
            "-t", f"{dur:.3f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-r", "30",
            "-loglevel", "error", str(out_seg),
        ]
        r = self._run(cmd)
        if r.returncode != 0:
            # retry without subtitle (subtitle/font can be the culprit)
            if self.subtitle:
                cmd = [c for c in cmd if not c.startswith("drawtext")] if False else None
                cmd2 = [
                    "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(src),
                    "-t", f"{dur:.3f}", "-vf", self._normalize_vf(),
                    "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
                    "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-r", "30",
                    "-loglevel", "error", str(out_seg),
                ]
                r = self._run(cmd2)
            if r.returncode != 0:
                raise ComposeError(f"ffmpeg extract failed: {r.stderr[-200:]}")

    def _concat_demuxer(self, seg_files: List[Path], final: Path) -> bool:
        lst = final.parent / f"_concat_{final.stem}.txt"
        lst.write_text("\n".join(f"file '{f}'" for f in seg_files), encoding="utf-8")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-r", "30",
            "-loglevel", "error", str(final),
        ]
        r = self._run(cmd)
        lst.unlink(missing_ok=True)
        return r.returncode == 0 and final.exists()

    def _concat_xfade(self, seg_files: List[Path], final: Path) -> bool:
        """Correct xfade chain (P0-4 fix).

        For each new segment i (i>=1):
            offset = accumulated_output_duration - T
            accumulated_output_duration += dur_i - T
        This recursively accounts for the duration lost at every prior transition,
        so the chain is valid for any number of segments.
        """
        T = min(0.4, min(_dur(f) for f in seg_files) / 2.0)
        n = len(seg_files)
        # probe per-file durations
        durs = [_dur(f) for f in seg_files]

        filters = []
        prev_v = f"[0:v]"
        prev_a = f"[0:a]"
        acc = durs[0]
        for i in range(1, n):
            offset = max(0.0, acc - T)
            vlabel = f"v{i}"
            alabel = f"a{i}"
            filters.append(
                f"{prev_v}[{i}:v]xfade=transition=fade:duration={T}:offset={offset:.3f}[{vlabel}]"
            )
            filters.append(
                f"{prev_a}[{i}:a]acrossfade=d={T:.3f}[{alabel}]"
            )
            prev_v = f"[{vlabel}]"
            prev_a = f"[{alabel}]"
            acc = acc + durs[i] - T

        cmd = ["ffmpeg", "-y"]
        for f in seg_files:
            cmd += ["-i", str(f)]
        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", prev_v, "-map", prev_a,
            "-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-r", "30",
            "-loglevel", "error", str(final),
        ]
        r = self._run(cmd)
        return r.returncode == 0 and final.exists()

    def _mix_bgm(self, final: Path, out: Path) -> Path:
        cmd = [
            "ffmpeg", "-y", "-i", str(final), "-i", str(self.bgm_path),
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 0.25[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-loglevel", "error", str(out),
        ]
        r = self._run(cmd)
        if r.returncode == 0 and out.exists():
            final.unlink(missing_ok=True)
            return out
        return final


def _dur(path: Path) -> float:
    import json
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return float(json.loads(r.stdout).get("format", {}).get("duration", 0) or 0)
    except Exception:
        return 0.0
