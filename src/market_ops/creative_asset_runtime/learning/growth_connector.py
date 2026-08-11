"""E11.2.5 — Growth Connector（E11 → V8.5 桥接器）。

核心适配器：将 E11 Runtime 的 AssetEvent 转换为 V8.5 可消费的 LearningSignal。

完整流程：
  AssetEvent (WINNER_DETECTED)
    → WinnerDetector.on_winner()
    → WinnerProfile
    → LearningSignalBuilder.build()
    → LearningSignal (E10.1 格式)
    → DNATrigger.evaluate()
    → DNATriggerSignal (V8.5 DNA Engine 入口)

职责分离：
  E11:   识别 Winner + 聚合并输出信号
  V8.5:  消费信号 + 分析 DNA + 驱动 Mutation

Usage:
    connector = GrowthConnector(event_bus)
    connector.start()  # 订阅事件
    # 当 WINNER_DETECTED 触发时，自动生成 LearningSignal
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..events.asset_events import AssetEvent, AssetEventType
from .winner_detector import WinnerDetector, WinnerProfile
from .signal_builder import LearningSignalBuilder
from .dna_trigger import DNATrigger, DNATriggerSignal

if TYPE_CHECKING:
    from ..events.event_bus_adapter import AssetEventBus

logger = logging.getLogger(__name__)


class GrowthConnector:
    """E11 Runtime → V8.5 Growth Loop 连接器。

    监听 WINNER_DETECTED 事件，自动生成 LearningSignal 和 DNATriggerSignal。

    Usage:
        connector = GrowthConnector(runtime.event_bus)
        connector.start()
        # 等待 WINNER_DETECTED → 自动生成信号
        signals = connector.learning_signals
        triggers = connector.dna_triggers
    """

    def __init__(
        self,
        event_bus: AssetEventBus,
        signal_output_dir: str = "data/runtime/learning_signals",
    ) -> None:
        self._bus = event_bus
        self._output_dir = Path(signal_output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # 子模块
        self._detector = WinnerDetector()
        self._builder = LearningSignalBuilder()
        self._trigger = DNATrigger()

        self._started = False
        self._signals_generated = 0

    # ── Public API ───────────────────────────────────────

    def start(self) -> None:
        """启动 GrowthConnector：订阅 WINNER_DETECTED 事件。"""
        self._bus.subscribe(
            AssetEventType.ASSET_WINNER_DETECTED,
            self._on_winner_detected,
        )
        self._bus.subscribe(
            AssetEventType.PERFORMANCE_UPDATED,
            self._on_performance_updated,
        )
        self._started = True
        logger.info("GrowthConnector: started, listening for WINNER_DETECTED")

    def stop(self) -> None:
        """停止监听。"""
        self._bus.unsubscribe(
            AssetEventType.ASSET_WINNER_DETECTED,
            self._on_winner_detected,
        )
        self._bus.unsubscribe(
            AssetEventType.PERFORMANCE_UPDATED,
            self._on_performance_updated,
        )
        self._started = False
        logger.info("GrowthConnector: stopped")

    # ── Event Handlers ───────────────────────────────────

    def _on_winner_detected(self, event: AssetEvent) -> None:
        """处理 WINNER_DETECTED → 生成 LearningSignal + DNATriggerSignal。"""
        # Step 1: 构建 WinnerProfile
        profile = self._detector.on_winner(event)
        if profile is None:
            return

        # Step 2: 转换为 LearningSignal
        signal = self._builder.build(profile)
        self._signals_generated += 1

        # Step 3: 评估是否需要 DNA 分析
        dna_signal = self._trigger.evaluate(signal)

        # Step 4: 持久化
        self._save_signal(signal, dna_signal)

        logger.info(
            f"GrowthConnector: winner={profile.eagle_v_number}, "
            f"roas={profile.roas:.1f}, "
            f"action={profile.recommended_action}, "
            f"dna={'triggered' if dna_signal else 'skipped'} "
            f"(priority={dna_signal.priority if dna_signal else 'N/A'})"
        )

    def _on_performance_updated(self, event: AssetEvent) -> None:
        """处理 PERFORMANCE_UPDATED → 更新已有 WinnerProfile。"""
        self._detector.on_performance_updated(event)

    # ── Query ────────────────────────────────────────────

    @property
    def learning_signals(self) -> list:
        return self._builder.get_signals()

    @property
    def dna_triggers(self) -> list[DNATriggerSignal]:
        return self._trigger.get_triggers()

    @property
    def winner_profiles(self) -> list[WinnerProfile]:
        return self._detector.get_all_winners()

    def get_scale_candidates(self) -> list[WinnerProfile]:
        return self._detector.get_scale_candidates()

    def get_analyze_candidates(self) -> list[WinnerProfile]:
        return self._detector.get_analyze_candidates()

    def get_high_priority_dna(self) -> list[DNATriggerSignal]:
        return self._trigger.get_high_priority()

    def get_status(self) -> dict[str, Any]:
        """获取 GrowthConnector 状态。"""
        return {
            "started": self._started,
            "signals_generated": self._signals_generated,
            "winners_detected": self._detector.winner_count,
            "dna_triggers": self._trigger.trigger_count,
            "scale_candidates": len(self.get_scale_candidates()),
            "analyze_candidates": len(self.get_analyze_candidates()),
            "high_priority_dna": len(self.get_high_priority_dna()),
        }

    # ── Internal ────────────────────────────────────────

    def _save_signal(
        self,
        signal,
        dna_signal: DNATriggerSignal | None,
    ) -> None:
        """持久化 LearningSignal + DNATriggerSignal。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"signal_{signal.signal_id}_{timestamp}.json"
        filepath = self._output_dir / filename

        data = {
            "learning_signal": signal.to_dict(),
            "dna_trigger": dna_signal.to_dict() if dna_signal else None,
            "generated_at": datetime.now().isoformat(),
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"GrowthConnector: failed to save signal: {e}")

    def __repr__(self) -> str:
        return (
            f"GrowthConnector(started={self._started}, "
            f"signals={self._signals_generated})"
        )