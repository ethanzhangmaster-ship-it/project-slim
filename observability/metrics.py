"""
EP0.6 — Observability: metrics collector for agent execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime, timezone


@dataclass
class AgentMetric:
    agent: str
    action: str
    game_id: str
    success: bool
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MetricsCollector:
    """Collects execution metrics across all agents."""

    def __init__(self):
        self._metrics: List[AgentMetric] = []
        self._counters: Dict[str, int] = {}

    def record(self, metric: AgentMetric) -> None:
        self._metrics.append(metric)
        self._counters[metric.agent] = self._counters.get(metric.agent, 0) + 1

    def success_rate(self, agent: str = "") -> float:
        subset = [m for m in self._metrics if not agent or m.agent == agent]
        if not subset:
            return 1.0
        return sum(1 for m in subset if m.success) / len(subset)

    def avg_duration_ms(self, agent: str = "") -> float:
        subset = [m for m in self._metrics if not agent or m.agent == agent]
        if not subset:
            return 0.0
        return sum(m.duration_ms for m in subset) / len(subset)

    def summary(self) -> Dict:
        return {
            "total_actions": len(self._metrics),
            "by_agent": dict(self._counters),
            "overall_success_rate": round(self.success_rate(), 3),
            "avg_duration_ms": round(self.avg_duration_ms(), 1),
        }

    def to_markdown(self) -> str:
        lines = ["# Agent Metrics", ""]
        s = self.summary()
        lines.append(f"- **Total actions**: {s['total_actions']}")
        lines.append(f"- **Success rate**: {s['overall_success_rate']}")
        lines.append(f"- **Avg duration**: {s['avg_duration_ms']}ms\n")
        lines.append("## By Agent\n")
        for agent, count in sorted(s['by_agent'].items()):
            sr = self.success_rate(agent)
            avg_d = self.avg_duration_ms(agent)
            lines.append(f"- **{agent}**: {count} actions, {sr:.1%} success, {avg_d:.0f}ms avg")
        return "\n".join(lines)
