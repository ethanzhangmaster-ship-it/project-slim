"""FFmpegValidator — post-render verification (Quality Gate mechanical checks, Gate 1).

Uses ffprobe + ffmpeg blackdetect/silencedetect. Pure stdlib + subprocess.
This is what makes "render failure detection" real: a video is only counted as
successful if it passes ALL checks below. No more silent success.
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Optional

# target_ratio string -> expected width/height ratio (w/h)
RATIO_TARGET = {
    "9X16": 9.0 / 16.0,
    "1X1": 1.0,
    "16X9": 16.0 / 9.0,
}


def _run(cmd) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _ffprobe(path: Path) -> Dict:
    # NOTE: do NOT restrict to v:0 — we must see audio streams for the
    # "silent anomaly" check.
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,width,height,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ]
    r = _run(cmd)
    try:
        return json.loads(r.stdout or "{}")
    except Exception:
        return {}


def validate(
    path,
    target_ratio: str = "9X16",
    min_duration: float = 10.0,
    black_min_duration: float = 1.0,
    silence_min_duration: float = 2.0,
) -> Dict:
    """Return a structured validation report. `passed` is True only if every
    Gate-1 check passes."""
    path = Path(path)
    rep = {
        "path": str(path),
        "playable": False,
        "ratio_ok": False,
        "duration_ok": False,
        "black_ok": True,
        "audio_ok": False,
        "passed": False,
        "width": 0,
        "height": 0,
        "duration": 0.0,
        "has_audio": False,
        "issues": [],
        "warnings": [],
    }
    if not path.exists() or path.stat().st_size == 0:
        rep["issues"].append("file missing or empty")
        return rep

    info = _ffprobe(path)
    streams = info.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        rep["issues"].append("no video stream (not playable)")
        return rep
    v = video_streams[0]
    w = int(v.get("width", 0) or 0)
    h = int(v.get("height", 0) or 0)
    dur = float(v.get("duration") or info.get("format", {}).get("duration") or 0)
    rep["width"], rep["height"], rep["duration"] = w, h, round(dur, 2)
    rep["playable"] = w > 0 and h > 0 and dur > 0

    # aspect ratio
    if w > 0 and h > 0:
        actual = w / h
        target = RATIO_TARGET.get(target_ratio, 9.0 / 16.0)
        rep["ratio_ok"] = abs(actual - target) < 0.03
        if not rep["ratio_ok"]:
            rep["issues"].append(
                f"ratio {actual:.3f} != target {target:.3f} ({target_ratio})"
            )

    # duration
    rep["duration_ok"] = dur >= min_duration
    if not rep["duration_ok"]:
        rep["issues"].append(f"duration {dur:.1f}s < {min_duration}s")

    # audio presence
    audio_streams = [
        s for s in streams if s.get("codec_type") == "audio"
    ]
    rep["has_audio"] = len(audio_streams) > 0
    if rep["has_audio"]:
        rep["audio_ok"] = _audio_not_silent(path, dur, silence_min_duration)
        if not rep["audio_ok"]:
            rep["issues"].append("audio track present but effectively silent")
    else:
        rep["audio_ok"] = False
        rep["issues"].append("no audio track (silent anomaly)")

    # black frames
    rep["black_ok"] = _no_long_black(path, black_min_duration)
    if not rep["black_ok"]:
        rep["issues"].append(f"black frames >= {black_min_duration}s detected")

    rep["passed"] = (
        rep["playable"]
        and rep["ratio_ok"]
        and rep["duration_ok"]
        and rep["black_ok"]
        and rep["audio_ok"]
    )
    return rep


def _audio_not_silent(path: Path, duration: float, silence_min: float) -> bool:
    """True if the audio is NOT effectively fully silent."""
    if duration <= 0:
        return False
    cmd = [
        "ffmpeg", "-v", "info", "-i", str(path),
        "-af", f"silencedetect=n=-50dB:d={silence_min}",
        "-f", "null", "-",
    ]
    r = _run(cmd)
    # sum up reported silence durations
    total_silence = 0.0
    for line in r.stderr.splitlines():
        if "silence_duration:" in line:
            try:
                val = float(line.split("silence_duration:")[1].split()[0])
                total_silence += val
            except Exception:
                pass
    # if silence covers ~entire clip -> treat as silent
    return total_silence < duration * 0.95


def _no_long_black(path: Path, black_min: float) -> bool:
    cmd = [
        "ffmpeg", "-v", "info", "-i", str(path),
        "-vf", f"blackdetect=d={black_min}:pix_th=0.10",
        "-f", "null", "-",
    ]
    r = _run(cmd)
    for line in r.stderr.splitlines():
        if "black_duration:" in line:
            try:
                val = float(line.split("black_duration:")[1].split()[0])
                if val >= black_min:
                    return False
            except Exception:
                pass
    return True
