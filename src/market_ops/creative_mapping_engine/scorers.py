"""Creative Mapping Engine — 6 维度评分器。

每个维度独立评分 (0.0-1.0)，加权综合得出置信度。

v1.2: frame_similarity 维度已启用 CLIP embedding/pHash 计算。
"""

from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from .frame_similarity import FrameSimilarityComputer
from .models import MappingScores


# 6 位序列号提取 (文件名末尾的 _XXXXXX)
_SERIAL_PATTERN = re.compile(r"_(\d{6})(?:\.\w+)?$")


class MappingScorer:
    """6 维度评分器。

    维度:
      1. name_similarity — 序列号提取 + Levenshtein 编辑距离
      2. duration_match — 时长差值容差
      3. resolution_match — 完全匹配 / 宽高比匹配
      4. creation_time_match — 时间窗口
      5. frame_similarity — CLIP embedding cosine / pHash (v1.2 启用)
      6. file_hash_match — 文件哈希精确匹配
    """

    DEFAULT_WEIGHTS: dict[str, float] = {
        "name_similarity": 0.25,
        "duration_match": 0.15,
        "resolution_match": 0.10,
        "creation_time_match": 0.10,
        "frame_similarity": 0.25,
        "file_hash_match": 0.15,
    }

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        frame_computer: FrameSimilarityComputer | None = None,
    ):
        self._weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        self._frame_computer = frame_computer or FrameSimilarityComputer()

    @property
    def weights(self) -> dict[str, float]:
        return self._weights

    @property
    def frame_computer(self) -> FrameSimilarityComputer:
        """帧相似度计算器实例。"""
        return self._frame_computer

    # ── 维度 1: 名称相似度 ────────────────────────────────────

    def score_name_similarity(self, fb_name: str, eagle_filename: str) -> float:
        """名称相似度 — 序列号精确匹配优先，否则编辑距离归一化。"""
        if not fb_name or not eagle_filename:
            return 0.0

        # 尝试序列号提取
        fb_serial = self._extract_serial(fb_name)
        eagle_serial = self._extract_serial(eagle_filename)
        if fb_serial and eagle_serial:
            return 1.0 if fb_serial == eagle_serial else 0.0

        # 回退: 编辑距离归一化
        ratio = SequenceMatcher(None, fb_name.lower(), eagle_filename.lower()).ratio()
        return round(ratio, 4)

    @staticmethod
    def _extract_serial(name: str) -> str:
        """提取 6 位序列号。"""
        match = _SERIAL_PATTERN.search(name)
        return match.group(1) if match else ""

    # ── 维度 2: 时长匹配 ──────────────────────────────────────

    @staticmethod
    def score_duration_match(fb_duration: float, eagle_duration: float) -> float:
        """时长匹配 — 差值容差评分。"""
        if fb_duration <= 0 or eagle_duration <= 0:
            return 0.0
        diff = abs(fb_duration - eagle_duration)
        if diff <= 0.5:
            return 1.0
        elif diff <= 2.0:
            return 0.7
        else:
            return 0.0

    # ── 维度 3: 分辨率匹配 ────────────────────────────────────

    @staticmethod
    def score_resolution_match(fb_res: str, eagle_res: str) -> float:
        """分辨率匹配 — 完全匹配 / 宽高比匹配。"""
        if not fb_res or not eagle_res:
            return 0.0
        if fb_res == eagle_res:
            return 1.0
        # 宽高比匹配
        fb_ratio = MappingScorer._aspect_ratio(fb_res)
        eagle_ratio = MappingScorer._aspect_ratio(eagle_res)
        if fb_ratio > 0 and eagle_ratio > 0:
            return 0.7 if abs(fb_ratio - eagle_ratio) < 0.01 else 0.0
        return 0.0

    @staticmethod
    def _aspect_ratio(res: str) -> float:
        """解析分辨率字符串 "WxH" → 宽高比。"""
        try:
            parts = res.lower().split("x")
            if len(parts) == 2:
                w, h = int(parts[0]), int(parts[1])
                return w / h if h > 0 else 0.0
        except (ValueError, IndexError):
            pass
        return 0.0

    # ── 维度 4: 创建时间匹配 ──────────────────────────────────

    @staticmethod
    def score_creation_time_match(fb_time: str, eagle_time: str) -> float:
        """创建时间匹配 — 时间窗口评分。"""
        if not fb_time or not eagle_time:
            return 0.0
        fb_dt = MappingScorer._parse_date(fb_time)
        eagle_dt = MappingScorer._parse_date(eagle_time)
        if fb_dt is None or eagle_dt is None:
            return 0.0
        diff_days = abs((fb_dt - eagle_dt).days)
        if diff_days <= 1:
            return 1.0
        elif diff_days <= 7:
            return 0.7
        else:
            return 0.3

    @staticmethod
    def _parse_date(s: str) -> datetime | None:
        """解析日期字符串 (支持多种格式，包括 Facebook +0000 时区)。"""
        # 预处理：去掉时区后缀 (Z, +0000, +00:00)
        s = re.sub(r"(Z|[+-]\d{2}:?\d{2})$", "", s)
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    # ── 维度 5: 帧相似度 ──────────────────────────────────────

    def score_frame_similarity(self, fb_thumbnail: str, eagle_path: str) -> float:
        """帧相似度 — CLIP embedding cosine / pHash (v1.2 启用)。

        优先使用 CLIP embedding 计算 cosine similarity，
        CLIP 不可用时降级到 pHash 感知哈希，
        图像加载失败时返回 0.0。

        Args:
            fb_thumbnail: Facebook 缩略图 URL 或本地路径
            eagle_path: Eagle 视频文件路径

        Returns:
            0.0-1.0 归一化评分
        """
        if not fb_thumbnail or not eagle_path:
            return 0.0
        score, _method, _cached = self._frame_computer.compute(
            fb_thumbnail, eagle_path
        )
        return score

    # ── 维度 6: 文件哈希匹配 ──────────────────────────────────

    @staticmethod
    def score_file_hash_match(fb_hash: str, eagle_hash: str) -> float:
        """文件哈希匹配 — 精确匹配。"""
        if not fb_hash or not eagle_hash:
            return 0.0
        return 1.0 if fb_hash.lower() == eagle_hash.lower() else 0.0

    # ── 综合评分 ──────────────────────────────────────────────

    def score_all(
        self,
        fb_name: str,
        eagle_filename: str,
        fb_duration: float = 0.0,
        eagle_duration: float = 0.0,
        fb_resolution: str = "",
        eagle_resolution: str = "",
        fb_creation_time: str = "",
        eagle_creation_time: str = "",
        fb_thumbnail: str = "",
        eagle_path: str = "",
        fb_hash: str = "",
        eagle_hash: str = "",
    ) -> MappingScores:
        """计算全部 6 维度评分。"""
        return MappingScores(
            name_similarity=self.score_name_similarity(fb_name, eagle_filename),
            duration_match=self.score_duration_match(fb_duration, eagle_duration),
            resolution_match=self.score_resolution_match(fb_resolution, eagle_resolution),
            creation_time_match=self.score_creation_time_match(
                fb_creation_time, eagle_creation_time
            ),
            frame_similarity=self.score_frame_similarity(fb_thumbnail, eagle_path),
            file_hash_match=self.score_file_hash_match(fb_hash, eagle_hash),
        )

    def weighted_total(self, scores: MappingScores) -> float:
        """加权综合评分。"""
        return scores.weighted_total(self._weights)

    def dominant_dimension(self, scores: MappingScores) -> str:
        """找出贡献最大的维度 (用于 match_method)。"""
        values = scores.to_dict()
        weighted = {k: v * self._weights.get(k, 0.0) for k, v in values.items()}
        return max(weighted, key=weighted.get) if weighted else ""


__all__ = ["MappingScorer"]
