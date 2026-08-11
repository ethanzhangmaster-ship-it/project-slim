"""Winner Structure Intelligence — V3.9.1

核心功能：
- StructureMinerV2: 真实广告结构学习器

对比 V3.9：
❌ 固定模板套用
✅ 真实视频结构分析和学习
"""

from .structure_miner_v2 import StructureMinerV2, ShotStructure, VideoStructure, StructureTemplate

__all__ = [
    "StructureMinerV2",
    "ShotStructure",
    "VideoStructure",
    "StructureTemplate",
]