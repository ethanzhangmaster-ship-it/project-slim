"""E11.5.2 — Opportunity Detector。

将原始信号（dict）转换为结构化 OpportunitySignal。

核心职责：
  1. 解析原始信号数据
  2. 验证信号完整性
  3. 批量并行检测
  4. 去重（相同 category + pattern 组合）
"""

from __future__ import annotations

import logging
from typing import Any

from .models import OpportunitySignal

logger = logging.getLogger(__name__)


class OpportunityDetector:
    """机会检测器。

    将原始信号（外部系统数据）转换为 OpportunitySignal。

    Attributes:
        min_confidence:  最低置信度阈值
        deduplicate:     是否去重
        detected_count:  已检测信号数
    """

    def __init__(
        self,
        min_confidence: float = 0.0,
        deduplicate: bool = True,
    ) -> None:
        self._min_confidence = min_confidence
        self._deduplicate = deduplicate
        self._detected_count: int = 0
        self._seen_keys: set[str] = set()

    # ── 核心接口 ──────────────────────────────────────

    def detect(
        self,
        signals: list[dict[str, Any]],
    ) -> list[OpportunitySignal]:
        """从原始信号中检测机会。

        Args:
            signals: 原始信号列表（dict）

        Returns:
            OpportunitySignal 列表
        """
        opportunities: list[OpportunitySignal] = []

        for raw in signals:
            signal = self._parse_signal(raw)
            if signal is None:
                continue

            # 置信度过滤
            if signal.confidence < self._min_confidence:
                logger.debug(
                    f"Skipping low-confidence signal: {signal.signal_id} "
                    f"(conf={signal.confidence:.2f})"
                )
                continue

            # 去重
            if self._deduplicate:
                key = self._make_key(signal)
                if key in self._seen_keys:
                    logger.debug(
                        f"Skipping duplicate signal: {signal.signal_id} "
                        f"(key={key})"
                    )
                    continue
                self._seen_keys.add(key)

            opportunities.append(signal)
            self._detected_count += 1

        return opportunities

    def detect_batch(
        self,
        signal_batches: list[list[dict[str, Any]]],
    ) -> list[list[OpportunitySignal]]:
        """批量检测多组信号。"""
        return [self.detect(batch) for batch in signal_batches]

    # ── 内部 ──────────────────────────────────────────

    def _parse_signal(
        self,
        raw: dict[str, Any],
    ) -> OpportunitySignal | None:
        """解析单个原始信号为 OpportunitySignal。"""
        try:
            signal = OpportunitySignal.from_dict(raw)
            # 验证：必须包含有效 category 和至少一个 pattern
            if not signal.category:
                logger.debug(f"Skipping signal with empty category: {raw}")
                return None
            if not signal.patterns:
                logger.debug(f"Skipping signal with empty patterns: {raw}")
                return None
            return signal
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse signal: {e}")
            return None

    @staticmethod
    def _make_key(signal: OpportunitySignal) -> str:
        """生成去重 key。"""
        patterns_sorted = sorted(signal.patterns)
        return f"{signal.source}|{signal.category}|{','.join(patterns_sorted)}"

    # ── Stats ──────────────────────────────────────────

    @property
    def detected_count(self) -> int:
        return self._detected_count

    def reset(self) -> None:
        """重置去重缓存和计数。"""
        self._seen_keys.clear()
        self._detected_count = 0

    def get_stats(self) -> dict[str, Any]:
        return {
            "detected_count": self._detected_count,
            "seen_keys_count": len(self._seen_keys),
            "min_confidence": self._min_confidence,
            "deduplicate": self._deduplicate,
        }

    def __repr__(self) -> str:
        return f"OpportunityDetector(detected={self._detected_count})"