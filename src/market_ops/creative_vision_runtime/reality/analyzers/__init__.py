"""E12.2 — Analyzers package。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from .performance_analyzer import PerformanceAnalyzer
from .fatigue_detector import FatigueDetector
from .anomaly_detector import AnomalyDetector

# ThinkingData 产品分析域
from .lifecycle_analyzer import LifecycleAnalyzer, LifecycleSnapshot
from .funnel_analyzer import FunnelAnalyzer, FunnelSnapshot, FunnelStep
from .retention_analyzer import RetentionAnalyzer, RetentionSnapshot, ChannelRetention
from .monetization_analyzer import (
    MonetizationAnalyzer,
    MonetizationSnapshot,
    OfferPerformance,
)
from .economy_analyzer import (
    EconomyAnalyzer,
    EconomySnapshot,
    ResourceFlow,
)
from .gameplay_analyzer import (
    GameplayAnalyzer,
    GameplaySnapshot,
    LevelPerformance,
    ModeEngagement,
)
from .user_value_analyzer import (
    UserValueAnalyzer,
    UserValueSnapshot,
    UserSegment,
    ValueContribution,
)

if TYPE_CHECKING:
    from ..thinkingdata_reality import ThinkingDataReality

# ── 七域并行执行 ────────────────────────────────────────────

_SEVEN_DOMAIN_ANALYZERS: dict[str, type] = {
    "Lifecycle": LifecycleAnalyzer,
    "Funnel": FunnelAnalyzer,
    "Retention": RetentionAnalyzer,
    "Monetization": MonetizationAnalyzer,
    "Economy": EconomyAnalyzer,
    "Gameplay": GameplayAnalyzer,
    "UserValue": UserValueAnalyzer,
}


def parallel_analyze(
    td: ThinkingDataReality,
    project_id: int = 102,
    lookback_days: int = 30,
    max_workers: int = 7,
) -> dict[str, Any]:
    """并行执行七域分析器，返回 {域名: 快照}。

    使用 ThreadPoolExecutor 并发执行七个分析域，单域失败不影响其他域。
    失败的域会在结果中以 ``{name}_error`` 键记录异常信息。

    Args:
        td: ThinkingDataReality 实例（共享给所有 analyzer）。
        project_id: 项目 ID。
        lookback_days: 回溯天数。
        max_workers: 最大线程数，默认 7。

    Returns:
        dict[str, Any]: 每个域的快照结果，失败域附加 ``{name}_error`` 键。
    """
    analyzers = {name: cls(td) for name, cls in _SEVEN_DOMAIN_ANALYZERS.items()}
    results: dict[str, Any] = {}

    with ThreadPoolExecutor(max_workers=min(max_workers, len(analyzers))) as executor:
        futures = {
            executor.submit(az.analyze, project_id, lookback_days): name
            for name, az in analyzers.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                results[name] = None
                results[f"{name}_error"] = str(exc)

    return results


__all__ = [
    # 现有
    "PerformanceAnalyzer",
    "FatigueDetector",
    "AnomalyDetector",
    # ThinkingData 产品分析域
    "LifecycleAnalyzer",
    "LifecycleSnapshot",
    "FunnelAnalyzer",
    "FunnelSnapshot",
    "FunnelStep",
    "RetentionAnalyzer",
    "RetentionSnapshot",
    "ChannelRetention",
    "MonetizationAnalyzer",
    "MonetizationSnapshot",
    "OfferPerformance",
    "EconomyAnalyzer",
    "EconomySnapshot",
    "ResourceFlow",
    "GameplayAnalyzer",
    "GameplaySnapshot",
    "LevelPerformance",
    "ModeEngagement",
    "UserValueAnalyzer",
    "UserValueSnapshot",
    "UserSegment",
    "ValueContribution",
    # 并行执行
    "parallel_analyze",
    "_SEVEN_DOMAIN_ANALYZERS",
]