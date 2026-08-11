"""Gameplay Intelligence Engine — V3.9.1

核心功能：
- GameplayDetector: 综合玩法检测器
- MergeDetector: 合并游戏检测
- DragDetector: 拖拽游戏检测
- UpgradeDetector: 升级游戏检测
- RewardDetector: 奖励事件检测

对比 V3.9：
❌ 无真实玩法检测
✅ 基于 OpenCV 的真实游戏玩法分析
"""

from .gameplay_detector import GameplayDetector, GameplayResult, GameplayEvent
from .merge_detector import MergeDetector, MergeDetection, MergeEvent
from .drag_detector import DragDetector, DragDetection, DragEvent
from .upgrade_detector import UpgradeDetector, UpgradeDetection, UpgradeEvent
from .reward_detector import RewardDetector, RewardDetection, RewardEvent

__all__ = [
    "GameplayDetector",
    "GameplayResult",
    "GameplayEvent",
    "MergeDetector",
    "MergeDetection",
    "MergeEvent",
    "DragDetector",
    "DragDetection",
    "DragEvent",
    "UpgradeDetector",
    "UpgradeDetection",
    "UpgradeEvent",
    "RewardDetector",
    "RewardDetection",
    "RewardEvent",
]