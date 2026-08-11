"""E17.11.2 Experience Write Models — 经验写入路径模型.

Day 7.11 Step 2:
  定义 ExecutionResult → GrowthExperience 写入路径的模型:
    1. ExperienceBuildResult   — 构建结果
    2. ImportanceScore         — 重要性评分
    3. ExperienceWriteResult   — 单次写入结果
    4. WriteBatchResult        — 批量写入结果
    5. ConsolidationTrigger    — 整合触发配置
    6. ExperienceImportanceLevel — 重要性等级

设计原则:
  - 纯数据模型，不包含业务逻辑
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class ExperienceImportanceLevel(str, Enum):
    """经验重要性等级."""
    CRITICAL = "critical"     # 关键经验: 权重高，长期保留
    HIGH = "high"             # 高重要性: 参与长期记忆
    MEDIUM = "medium"         # 中等重要性: 短期记忆
    LOW = "low"               # 低重要性: 可丢弃
    NEGLIGIBLE = "negligible" # 可忽略: 不写入


class WriteStatus(str, Enum):
    """写入状态."""
    WRITTEN = "written"           # 成功写入
    SKIPPED_LOW_IMPORTANCE = "skipped_low_importance"  # 重要性不足跳过
    SKIPPED_DUPLICATE = "skipped_duplicate"            # 重复跳过
    FAILED = "failed"             # 写入失败


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class ImportanceScore:
    """经验重要性评分.

    Attributes:
        total_score: 综合重要性评分 [0, 1]
        impact: 影响因子 (metric delta) × 0.4
        confidence: 置信度因子 × 0.3
        novelty: 新颖性因子 × 0.2
        repeatability: 可重复性因子 × 0.1
        level: 重要性等级
        reasons: 评分原因
    """
    total_score: float = 0.0
    impact: float = 0.0
    confidence: float = 0.0
    novelty: float = 0.0
    repeatability: float = 0.0
    level: ExperienceImportanceLevel = ExperienceImportanceLevel.NEGLIGIBLE
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_score": self.total_score,
            "impact": self.impact,
            "confidence": self.confidence,
            "novelty": self.novelty,
            "repeatability": self.repeatability,
            "level": self.level.value,
            "reasons": self.reasons,
        }


@dataclass
class ExperienceBuildResult:
    """ExecutionResult → GrowthExperience 构建结果.

    Attributes:
        success: 构建是否成功
        experience: 构建的 GrowthExperience (成功时)
        error: 错误信息 (失败时)
        build_time_ms: 构建耗时 (ms)
    """
    success: bool = False
    experience: Any = None  # GrowthExperience
    error: str = ""
    build_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "experience_id": (
                self.experience.experience_id
                if self.experience and hasattr(self.experience, "experience_id")
                else ""
            ),
            "error": self.error,
            "build_time_ms": self.build_time_ms,
        }


@dataclass
class ExperienceWriteResult:
    """单次经验写入结果.

    Attributes:
        status: 写入状态
        experience_id: 经验ID
        importance: 重要性评分
        build_result: 构建结果
        stored: 是否已存储到 ExperienceStore
        consolidation_triggered: 是否触发了整合
        consolidation_report: 整合报告 (可选)
        error: 错误信息
        timestamp: 写入时间
    """
    status: WriteStatus = WriteStatus.FAILED
    experience_id: str = ""
    importance: ImportanceScore = field(default_factory=ImportanceScore)
    build_result: ExperienceBuildResult = field(default_factory=ExperienceBuildResult)
    stored: bool = False
    consolidation_triggered: bool = False
    consolidation_report: Any = None  # ConsolidationReport
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_written(self) -> bool:
        return self.status == WriteStatus.WRITTEN

    @property
    def is_skipped(self) -> bool:
        return self.status in (
            WriteStatus.SKIPPED_LOW_IMPORTANCE,
            WriteStatus.SKIPPED_DUPLICATE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "experience_id": self.experience_id,
            "importance": self.importance.to_dict(),
            "build_success": self.build_result.success,
            "stored": self.stored,
            "consolidation_triggered": self.consolidation_triggered,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class WriteBatchResult:
    """批量写入结果.

    Attributes:
        total: 总输入数
        written: 成功写入数
        skipped: 跳过数 (低重要性 + 重复)
        failed: 失败数
        consolidation_triggered: 是否触发了整合
        consolidation_report: 整合报告
        results: 每条经验的写入结果
        timestamp: 批次时间
    """
    total: int = 0
    written: int = 0
    skipped: int = 0
    failed: int = 0
    consolidation_triggered: bool = False
    consolidation_report: Any = None
    results: list[ExperienceWriteResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.written / self.total, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "written": self.written,
            "skipped": self.skipped,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "consolidation_triggered": self.consolidation_triggered,
            "timestamp": self.timestamp,
        }


@dataclass
class ConsolidationTrigger:
    """整合触发配置.

    Attributes:
        min_experience_count: 触发整合的最小经验数
        min_importance_threshold: 触发整合的最小重要性阈值
        cooldown_cycles: 整合冷却周期 (避免频繁整合)
        auto_trigger: 是否自动触发
        enabled: 是否启用
    """
    min_experience_count: int = 5
    min_importance_threshold: float = 0.30
    cooldown_cycles: int = 3
    auto_trigger: bool = True
    enabled: bool = True

    @classmethod
    def default(cls) -> ConsolidationTrigger:
        return cls()

    @classmethod
    def test_mode(cls) -> ConsolidationTrigger:
        """测试模式: 低阈值，快速触发."""
        return cls(
            min_experience_count=2,
            min_importance_threshold=0.10,
            cooldown_cycles=0,
            auto_trigger=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_experience_count": self.min_experience_count,
            "min_importance_threshold": self.min_importance_threshold,
            "cooldown_cycles": self.cooldown_cycles,
            "auto_trigger": self.auto_trigger,
            "enabled": self.enabled,
        }


__all__ = [
    "ExperienceImportanceLevel",
    "WriteStatus",
    "ImportanceScore",
    "ExperienceBuildResult",
    "ExperienceWriteResult",
    "WriteBatchResult",
    "ConsolidationTrigger",
]