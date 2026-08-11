"""E11.2.5 — Growth Connector Layer（E11 → V8.5 桥接层）。

将 E11 Runtime 的 Winner 事件转换为 V8.5 可消费的 LearningSignal。

模块：
  - winner_detector.py   — WinnerDetector: 构建 WinnerProfile
  - signal_builder.py    — LearningSignalBuilder: WinnerProfile → E10.1 LearningSignal
  - dna_trigger.py       — DNATrigger: 评估是否需要 DNA 分析
  - growth_connector.py  — GrowthConnector: 主适配器，编排完整流程
"""
from .winner_detector import WinnerDetector, WinnerProfile
from .signal_builder import LearningSignalBuilder
from .dna_trigger import DNATrigger, DNATriggerSignal
from .growth_connector import GrowthConnector

__all__ = [
    "WinnerDetector",
    "WinnerProfile",
    "LearningSignalBuilder",
    "DNATrigger",
    "DNATriggerSignal",
    "GrowthConnector",
]