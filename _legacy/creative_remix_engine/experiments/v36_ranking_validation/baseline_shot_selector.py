"""Baseline Shot Selector — 纯 V3.4 文件名启发式（无 Ranking Engine）

用于 A/B 对照组 Group A。
"""
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple


@dataclass
class BaselineShotCandidate:
    filepath: Path
    v_num: str
    width: int
    height: int
    duration: float
    content_type: str
    overall_score: float = 0
    recommended_start: float = 0
    recommended_duration: float = 3.0


class BaselineShotSelector:
    """V3.4 原始 Shot Selector — 无 Ranking Engine，纯文件名启发式"""

    def __init__(self):
        self.shot_pool: List[BaselineShotCandidate] = []
        self._ffprobe_cache: Dict[str, dict] = {}

    def _get_video_info(self, path: Path) -> dict:
        key = str(path)
        if key in self._ffprobe_cache:
            return self._ffprobe_cache[key]
        try:
            r = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,duration",
                "-of", "json", str(path)
            ], capture_output=True, text=True, timeout=10)
            import json
            s = json.loads(r.stdout).get("streams", [{}])[0]
            info = {
                "width": int(s.get("width", 0)),
                "height": int(s.get("height", 0)),
                "duration": float(s.get("duration", 0) or 0),
            }
        except Exception:
            info = {"width": 0, "height": 0, "duration": 0}
        self._ffprobe_cache[key] = info
        return info

    def _infer_content_type(self, stem: str) -> str:
        s = stem.lower()
        if any(k in s for k in ["kaitou", "开场", "hook", "start"]):
            return "hook"
        if any(k in s for k in ["wanfa", "玩法", "gameplay", "merge", "play", "hecheng"]):
            return "gameplay"
        if any(k in s for k in ["juese", "角色", "reward", "character", "evol", "zhanshi"]):
            return "reward"
        if any(k in s for k in ["wenti", "问题", "problem", "challenge", "level", "boss"]):
            return "problem"
        if any(k in s for k in ["cta", "download", "结尾", "end"]):
            return "cta"
        if any(k in s for k in ["bianzhong", "变种", "variation"]):
            return "gameplay"
        return "mixed"

    def build_pool(self, source_dir: Path, min_duration: float = 2.5) -> List[BaselineShotCandidate]:
        candidates = []
        for vp in source_dir.glob("*.mp4"):
            info = self._get_video_info(vp)
            if info["duration"] < min_duration or info["width"] == 0:
                continue
            stem = vp.stem
            ctype = self._infer_content_type(stem)

            # V3.4: 纯文件名启发式 + 随机性
            score = 50
            s = stem.lower()
            if ctype == "hook":
                if any(k in s for k in ["kaitou", "开场", "hook"]):
                    score = 65
                else:
                    score = 45
            elif ctype == "gameplay":
                if any(k in s for k in ["wanfa", "玩法", "gameplay", "merge"]):
                    score = 60
                else:
                    score = 40
            elif ctype == "reward":
                if any(k in s for k in ["juese", "角色", "reward", "evolution"]):
                    score = 55
                else:
                    score = 38
            else:
                score = 40

            # 加入随机抖动，模拟 V3.4 "随机组合" 的行为
            import random
            score += random.uniform(-15, 15)

            candidates.append(BaselineShotCandidate(
                filepath=vp,
                v_num=stem[:30],
                width=info["width"],
                height=info["height"],
                duration=info["duration"],
                content_type=ctype,
                overall_score=round(score, 1),
            ))
        self.shot_pool = candidates
        return candidates

    def select_for_beat(self, beat_role: str, target_duration: float,
                        exclude_paths: Optional[List[Path]] = None,
                        top_n: int = 1) -> List[Tuple[BaselineShotCandidate, float, float]]:
        exclude_paths = exclude_paths or []
        exclude_set = {str(p) for p in exclude_paths}

        scored = []
        for shot in self.shot_pool:
            if str(shot.filepath) in exclude_set:
                continue
            role_bonus = 15 if shot.content_type == beat_role else 0
            overall = shot.overall_score + role_bonus

            dur = min(target_duration, shot.duration * 0.9)
            if beat_role == "hook":
                start = min(1.0, max(0, shot.duration - dur - 1.0))
            elif beat_role == "reward":
                start = max(0, shot.duration - dur - 1.5)
            elif beat_role == "gameplay":
                start = shot.duration * 0.2
            else:
                start = shot.duration * 0.1
            start = max(0, min(start, shot.duration - dur - 0.1))
            dur = min(dur, shot.duration - start)

            shot.recommended_start = round(start, 2)
            shot.recommended_duration = round(dur, 2)
            scored.append((shot, overall))

        scored.sort(key=lambda x: -x[1])
        results = []
        for shot, _ in scored[:top_n]:
            results.append((shot, shot.recommended_start, shot.recommended_duration))
        return results

    def select_for_plan(self, beats: List,
                        avoid_duplicate_source: bool = True) -> Dict[str, List[Tuple[BaselineShotCandidate, float, float]]]:
        selected = {}
        used_paths = []
        for beat in beats:
            top = self.select_for_beat(
                beat.role, beat.duration,
                exclude_paths=used_paths if avoid_duplicate_source else None,
                top_n=3
            )
            selected[beat.beat_id] = top
            if top and avoid_duplicate_source:
                used_paths.append(top[0][0].filepath)
        return selected
