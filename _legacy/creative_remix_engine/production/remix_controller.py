"""RemixController — single orchestrator for the production pipeline (V3.9.1).

    DNA Selector -> Timeline Builder -> Clip Resolver -> Video Composer
    -> FFmpeg Renderer -> Quality Gate (FFmpeg validation) -> output.mp4

This is the ONLY production entry point. It never computes source timestamps
(ClipResolver does) and never reports success on a failed/unvalidated render.
Ad-analysis modules (engine/, src/market_ops/) are intentionally untouched.
"""
import csv
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from .timeline_planner import DNASelector, TimelineBuilder
from .video_composer import VideoComposer
from .ffmpeg_validator import validate


def _probe(path: Path) -> Dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-of", "json", str(path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        s = json.loads(r.stdout).get("streams", [{}])[0]
        return {
            "width": int(s.get("width", 0) or 0),
            "height": int(s.get("height", 0) or 0),
            "duration": float(s.get("duration", 0) or 0),
        }
    except Exception:
        return {"width": 0, "height": 0, "duration": 0.0}


def _classify_ratio(w: int, h: int) -> str:
    if w == 0 or h == 0:
        return "unknown"
    ratio = w / h
    if ratio < 0.7:
        return "9X16"
    elif ratio > 1.3:
        return "16X9"
    return "1X1"


def index_sources(source_dir) -> List[Dict]:
    source_dir = Path(source_dir)
    sources: List[Dict] = []
    if not source_dir.exists():
        return sources
    for f in source_dir.iterdir():
        if f.suffix.lower() != ".mp4":
            continue
        m = re.search(r"v(\d+)", f.stem)
        v_num = f"v{m.group(1)}" if m else f.stem
        info = _probe(f)
        sources.append({
            "v_num": v_num,
            "path": str(f),
            "duration": info["duration"],
            "width": info["width"],
            "height": info["height"],
            "ratio": _classify_ratio(info["width"], info["height"]),
            "roas": 0.0,
            "content": "",
        })
    return sources


class RemixController:
    def __init__(
        self,
        source_dir,
        adjust_csv: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(
            output_dir or str(self.source_dir.parent / "remix_output_v391")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sources = index_sources(self.source_dir)
        if adjust_csv:
            self._enrich(adjust_csv)
        self.selector = DNASelector(self.sources)

    def _enrich(self, adjust_csv: str):
        try:
            with open(adjust_csv, "r", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    v = row.get("v_num", "")
                    for s in self.sources:
                        if s["v_num"] == v:
                            s["roas"] = float(row.get("roas", 0) or 0)
                            s["content"] = row.get("content", "")
        except Exception:
            pass

    def generate(
        self,
        template: str = "bomb_15s",
        ratio: str = "9X16",
        count: int = 100,
        transition: str = "concat",
        subtitle: bool = False,
        bgm: Optional[str] = None,
        min_duration: float = 10.0,
    ) -> Dict:
        builder = TimelineBuilder(self.selector)
        recipes = builder.build(template, ratio, count)
        composer = VideoComposer(
            self.output_dir, ratio, transition, bgm, subtitle
        )
        reports: List[Dict] = []
        for recipe in recipes:
            entry = {
                "recipe_id": recipe["recipe_id"],
                "template": recipe["template"],
                "ratio": recipe["ratio"],
                "planned_duration": recipe["total_duration"],
                "segments": len(recipe["segments"]),
                "success": False,
                "error": None,
            }
            try:
                out = composer.compose(recipe["segments"], recipe["recipe_id"])
            except Exception as e:  # ComposeError or any render failure
                entry["error"] = str(e)[:200]
                reports.append(entry)
                continue
            v = validate(out, ratio, min_duration=min_duration)
            entry.update({
                "output": v["path"],
                "width": v["width"],
                "height": v["height"],
                "duration": v["duration"],
                "has_audio": v["has_audio"],
                "playable": v["playable"],
                "ratio_ok": v["ratio_ok"],
                "duration_ok": v["duration_ok"],
                "black_ok": v["black_ok"],
                "audio_ok": v["audio_ok"],
                "passed": v["passed"],
                "issues": v["issues"],
                "success": v["passed"],
            })
            if not v["passed"]:
                entry["error"] = "validation failed: " + "; ".join(v["issues"])
            reports.append(entry)

        passed = [r for r in reports if r.get("success")]
        summary = {
            "template": template,
            "ratio": ratio,
            "requested": count,
            "built": len(recipes),
            "rendered": len(reports),
            "passed_gate1": len(passed),
            "failed": len(reports) - len(passed),
            "pass_rate": round(len(passed) / len(reports), 3) if reports else 0.0,
            "transition": transition,
        }
        report_path = self.output_dir / "remix_report_v391.json"
        report_path.write_text(
            json.dumps(
                {"summary": summary, "details": reports},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        summary["report_path"] = str(report_path)
        return {"summary": summary, "details": reports}
