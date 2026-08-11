"""Shot Intelligence Layer — V3.9.1 Real Video Understanding

核心功能：
- Shot Extractor: 从视频中提取 shots
- Shot Detector: 检测 shot 边界（镜头切换）
- Real Shot Detector: 真实帧分析的边界检测（Sprint 1.1）
- Visual DNA Extractor: 视觉模型提取真实 DNA（Sprint 1.2）
- Shot Analyzer: 分析 shot 内容
- Shot Database: shot 素材库管理
- Shot Embedding: shot 向量嵌入
- Shot Role Classifier: shot 角色分类
"""

from .shot_extractor import ShotExtractor
from .shot_detector import ShotDetector
from .real_shot_detector import RealShotDetector, RealShotBoundary
from .visual_dna_extractor import VisualDNAExtractor, VisualDNA
from .shot_analyzer import ShotAnalyzer, ShotDNA
from .shot_database import ShotDatabase
from .shot_embedding import ShotEmbedding
from .shot_role_classifier import ShotRoleClassifier

__all__ = [
    "ShotExtractor",
    "ShotDetector",
    "RealShotDetector",
    "RealShotBoundary",
    "VisualDNAExtractor",
    "VisualDNA",
    "ShotAnalyzer",
    "ShotDNA",
    "ShotDatabase",
    "ShotEmbedding",
    "ShotRoleClassifier",
]