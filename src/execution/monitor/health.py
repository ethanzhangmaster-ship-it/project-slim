"""P2.5.4 SLA Monitor + Provider Health + Execution Health Score。

SLA 阈值（规格）：
    MAX  : <5s GREEN / 5–30s YELLOW / >30s RED
    Meta : <10s GREEN / 10–60s YELLOW / >60s RED
    Play : 不进 API SLA（无外部 API 调用，latency 不计，恒 GREEN）

健康分公式（规格）：
    Score = SuccessRate×0.4 + ProviderHealth×0.3 + LatencyScore×0.2 + RollbackSafety×0.1
    → GREEN / YELLOW / RED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.execution.monitor.collector import _parse_iso
from src.execution.monitor.models import (
    HEALTH_GREEN,
    HEALTH_RED,
    HEALTH_YELLOW,
    ExecutionMetrics,
    ExecutionSummary,
)
from src.execution.safe_executor.models import SafeExecutionOutcome

# 各 Provider 的 SLA 阈值（秒）
_PROVIDER_SLA: Dict[str, Dict[str, float]] = {
    "max": {"green": 5.0, "yellow": 30.0},
    "meta": {"green": 10.0, "yellow": 60.0},
}
# latency 评分映射
_LATENCY_SCORE: Dict[str, float] = {
    HEALTH_GREEN: 1.0,
    HEALTH_YELLOW: 0.6,
    HEALTH_RED: 0.2,
}
# 健康分等级阈值
GREEN_THRESHOLD = 0.8
YELLOW_THRESHOLD = 0.6


def latency_level(provider: str, seconds: float) -> str:
    """返回某 Provider 某次执行的延迟等级（GREEN/YELLOW/RED）。"""
    cfg = _PROVIDER_SLA.get(provider)
    if cfg is None:
        # Play 或未知 Provider：不进 API SLA，恒 GREEN
        return HEALTH_GREEN
    if seconds < cfg["green"]:
        return HEALTH_GREEN
    if seconds <= cfg["yellow"]:
        return HEALTH_YELLOW
    return HEALTH_RED


def latency_score(level: str) -> float:
    return _LATENCY_SCORE.get(level, HEALTH_RED and 0.2)


@dataclass
class ProviderHealth:
    """单个 Provider 的聚合健康画像。"""

    provider: str
    executions: int = 0
    success_rate: float = 0.0
    avg_latency: float = 0.0
    latency_level: str = HEALTH_GREEN
    latency_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "executions": self.executions,
            "success_rate": self.success_rate,
            "avg_latency": round(self.avg_latency, 3),
            "latency_level": self.latency_level,
            "latency_score": self.latency_score,
        }


def compute_provider_health(
    summaries: List[ExecutionSummary],
) -> Dict[str, ProviderHealth]:
    """按 Provider 维度聚合健康画像。"""
    by_provider: Dict[str, List[ExecutionSummary]] = {}
    for s in summaries:
        by_provider.setdefault(s.provider or "unknown", []).append(s)

    out: Dict[str, ProviderHealth] = {}
    for provider, rows in by_provider.items():
        n = len(rows)
        successes = sum(1 for r in rows if r.verdict in ("EXECUTED", "RETURN_EXISTING"))
        avg_lat = sum(r.latency_seconds for r in rows) / n if n else 0.0
        level = latency_level(provider, avg_lat)
        out[provider] = ProviderHealth(
            provider=provider,
            executions=n,
            success_rate=round(successes / n, 6) if n else 0.0,
            avg_latency=avg_lat,
            latency_level=level,
            latency_score=latency_score(level),
        )
    return out


def compute_metrics(outcomes: List[SafeExecutionOutcome]) -> ExecutionMetrics:
    """从 P2.4 产出聚合整体执行指标。"""
    summaries = _digest(outcomes)
    return ExecutionMetrics.from_summaries([s.to_dict() for s in summaries])


def _digest(outcomes: List[SafeExecutionOutcome]) -> List[ExecutionSummary]:
    from src.execution.monitor.collector import ExecutionEventCollector

    collector = ExecutionEventCollector()
    return [collector.summarize(None, o) for o in outcomes]


@dataclass
class ExecutionHealthScore:
    """执行健康分（整体）。"""

    score: float
    level: str
    success_rate: float = 0.0
    provider_health: float = 0.0
    latency_score: float = 0.0
    rollback_safety: float = 0.0

    @classmethod
    def from_components(
        cls,
        success_rate: float,
        provider_health: float,
        latency_score: float,
        rollback_safety: float,
    ) -> "ExecutionHealthScore":
        score = (
            success_rate * 0.4
            + provider_health * 0.3
            + latency_score * 0.2
            + rollback_safety * 0.1
        )
        if score >= GREEN_THRESHOLD:
            level = HEALTH_GREEN
        elif score >= YELLOW_THRESHOLD:
            level = HEALTH_YELLOW
        else:
            level = HEALTH_RED
        return cls(
            score=round(score, 4),
            level=level,
            success_rate=round(success_rate, 4),
            provider_health=round(provider_health, 4),
            latency_score=round(latency_score, 4),
            rollback_safety=round(rollback_safety, 4),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "success_rate": self.success_rate,
            "provider_health": self.provider_health,
            "latency_score": self.latency_score,
            "rollback_safety": self.rollback_safety,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionHealthScore":
        return cls(
            score=float(d.get("score", 0.0)),
            level=str(d.get("level", HEALTH_RED)),
            success_rate=float(d.get("success_rate", 0.0)),
            provider_health=float(d.get("provider_health", 0.0)),
            latency_score=float(d.get("latency_score", 0.0)),
            rollback_safety=float(d.get("rollback_safety", 0.0)),
        )


def compute_health_score(outcomes: List[SafeExecutionOutcome]) -> ExecutionHealthScore:
    """从 P2.4 产出计算整体执行健康分。"""
    summaries = _digest(outcomes)
    metrics = ExecutionMetrics.from_summaries([s.to_dict() for s in summaries])

    # ProviderHealth：按执行数加权的各 Provider success_rate
    providers = compute_provider_health(summaries)
    total_exec = sum(p.executions for p in providers.values())
    if total_exec > 0:
        provider_health = (
            sum(p.success_rate * p.executions for p in providers.values()) / total_exec
        )
    else:
        provider_health = 0.0

    # LatencyScore：各执行 latency_score 均值
    if summaries:
        lat_score = sum(
            latency_score(latency_level(s.provider, s.latency_seconds))
            for s in summaries
        ) / len(summaries)
    else:
        lat_score = 0.0

    # RollbackSafety：1 - rollback_rate
    rollback_safety = 1.0 - metrics.rollback_rate

    return ExecutionHealthScore.from_components(
        success_rate=metrics.success_rate,
        provider_health=provider_health,
        latency_score=lat_score,
        rollback_safety=rollback_safety,
    )


__all__ = [
    "latency_level",
    "latency_score",
    "ProviderHealth",
    "compute_provider_health",
    "compute_metrics",
    "ExecutionHealthScore",
    "compute_health_score",
    "GREEN_THRESHOLD",
    "YELLOW_THRESHOLD",
]
