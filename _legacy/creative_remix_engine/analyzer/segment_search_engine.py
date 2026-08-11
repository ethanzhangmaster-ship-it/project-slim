"""Segment Search Engine — 基于Video Intelligence找最佳片段"""
import subprocess
from pathlib import Path
from typing import Dict, Optional, List

from ..models import SegmentScore


class SegmentSearchEngine:
    """自动搜索视频中的 Hook/Gameplay/Reward 峰值"""

    def __init__(self):
        pass

    def find_hook_peak(self, video_path: Path, duration: float) -> Optional[SegmentScore]:
        """找 Hook 峰值（前3秒内的最强画面）"""
        # Hook 通常在视频前部
        search_window = min(5, duration)
        return self._search_peak(video_path, 0, search_window, "hook")

    def find_gameplay_peak(self, video_path: Path, duration: float) -> Optional[SegmentScore]:
        """找 Gameplay 峰值（中段最强动作）"""
        start = min(3, duration * 0.2)
        end = min(duration * 0.7, duration - 2)
        return self._search_peak(video_path, start, end, "gameplay")

    def find_reward_peak(self, video_path: Path, duration: float) -> Optional[SegmentScore]:
        """找 Reward 峰值（结尾高潮）"""
        start = max(0, duration * 0.6)
        return self._search_peak(video_path, start, duration, "reward")

    def _search_peak(self, video_path: Path, start: float, end: float, role: str) -> Optional[SegmentScore]:
        """在指定时间窗口内搜索峰值"""
        window_dur = end - start
        if window_dur <= 0:
            return None

        # 将窗口分成3段，取中段（通常最精彩）
        segment_len = window_dur / 3
        best_start = start + segment_len
        best_dur = segment_len

        # 评分（简化版，基于位置）
        if role == "hook":
            score = 90 + min(best_start, 2) * 3  # 越早分越高
        elif role == "gameplay":
            score = 80 + 5  # 中段标准分
        else:
            score = 85 + min(duration - end, 3) * 2  # 越接近结尾越高

        return SegmentScore(
            start=round(best_start, 2),
            duration=round(min(best_dur, 5), 2),
            visual_impact=score,
            motion_score=score * 0.9,
            emotion_score=score * 0.85 if role == "hook" else score * 0.7,
            overall=score,
        )

    def analyze_video(self, video_path: Path) -> Dict[str, SegmentScore]:
        """完整分析一个视频，返回所有峰值"""
        # 获取时长
        try:
            result = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ], capture_output=True, text=True)
            duration = float(result.stdout.strip())
        except:
            duration = 16.0

        return {
            "hook": self.find_hook_peak(video_path, duration),
            "gameplay": self.find_gameplay_peak(video_path, duration),
            "reward": self.find_reward_peak(video_path, duration),
        }
