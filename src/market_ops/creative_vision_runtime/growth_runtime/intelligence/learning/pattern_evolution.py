"""E15.3.5 Pattern Evolution Engine — 模式进化引擎.

管理 Pattern 的完整生命周期: DISCOVERED → VALIDATED → ACTIVE → DECAYING → RETIRED

状态转换规则:
  - DISCOVERED → VALIDATED: 验证通过 (evidence >= 10, confidence >= 0.5)
  - VALIDATED → ACTIVE:      活跃使用 (usage >= 5, success_rate >= 0.6)
  - ACTIVE → DECAYING:       效果衰减 (success_rate < 0.5 or decay_rate >= 0.2)
  - DECAYING → RETIRED:      确认失效 (success_rate < 0.3 or evidence declining)
  - DECAYING → ACTIVE:       恢复有效
  - Any → RETIRED:           手动退役

用法:
    engine = PatternEvolutionEngine()
    engine.register(pattern)
    engine.validate(pattern_id)
    engine.decay(pattern_id)
    engine.retire(pattern_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    LearnedPattern,
    PatternEvolution,
    PatternStatus,
)


# ═══════════════════════════════════════════════════════════════
# Evolution Rules
# ═══════════════════════════════════════════════════════════════

# 状态转换允许规则
VALID_TRANSITIONS: dict[PatternStatus, set[PatternStatus]] = {
    PatternStatus.DISCOVERED: {PatternStatus.VALIDATED, PatternStatus.RETIRED},
    PatternStatus.VALIDATED: {PatternStatus.ACTIVE, PatternStatus.RETIRED},
    PatternStatus.ACTIVE: {PatternStatus.DECAYING, PatternStatus.RETIRED},
    PatternStatus.DECAYING: {PatternStatus.ACTIVE, PatternStatus.RETIRED},
    PatternStatus.RETIRED: set(),  # 不可逆
}


# ═══════════════════════════════════════════════════════════════
# Pattern Evolution Engine
# ═══════════════════════════════════════════════════════════════


class PatternEvolutionEngine:
    """E15.3.5 模式进化引擎 — 管理模式生命周期.

    用法:
        engine = PatternEvolutionEngine()
        engine.register(pattern)
        engine.validate(pattern_id)
        engine.evolve_all()
    """

    def __init__(self):
        self._patterns: dict[str, LearnedPattern] = {}
        self._evolutions: list[PatternEvolution] = []
        self._evolution_count: int = 0

    @property
    def evolution_count(self) -> int:
        return self._evolution_count

    # ── Register ────────────────────────────────────────────────

    def register(self, pattern: LearnedPattern) -> LearnedPattern:
        """注册模式."""
        self._patterns[pattern.pattern_id] = pattern
        return pattern

    def register_batch(self, patterns: list[LearnedPattern]) -> list[LearnedPattern]:
        """批量注册."""
        for p in patterns:
            self.register(p)
        return patterns

    # ── Transitions ─────────────────────────────────────────────

    def validate(self, pattern_id: str) -> PatternEvolution | None:
        """验证模式 (DISCOVERED → VALIDATED)."""
        return self._transition(pattern_id, PatternStatus.VALIDATED, "validated")

    def activate(self, pattern_id: str) -> PatternEvolution | None:
        """激活模式 (VALIDATED → ACTIVE)."""
        return self._transition(pattern_id, PatternStatus.ACTIVE, "activated")

    def decay(self, pattern_id: str, reason: str = "") -> PatternEvolution | None:
        """衰减模式 (ACTIVE → DECAYING)."""
        return self._transition(pattern_id, PatternStatus.DECAYING, reason or "decaying_performance")

    def recover(self, pattern_id: str) -> PatternEvolution | None:
        """恢复模式 (DECAYING → ACTIVE)."""
        return self._transition(pattern_id, PatternStatus.ACTIVE, "recovered")

    def retire(self, pattern_id: str, reason: str = "") -> PatternEvolution | None:
        """退役模式 (Any → RETIRED)."""
        return self._transition(pattern_id, PatternStatus.RETIRED, reason or "retired")

    def _transition(
        self, pattern_id: str, to_status: PatternStatus, reason: str
    ) -> PatternEvolution | None:
        """执行状态转换."""
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return None

        from_status = pattern.status

        # 检查是否允许转换
        if to_status not in VALID_TRANSITIONS.get(from_status, set()):
            return None

        # 相同状态跳过
        if from_status == to_status:
            return None

        # 执行转换
        pattern.status = to_status
        if to_status == PatternStatus.VALIDATED:
            pattern.last_validated = datetime.now(timezone.utc).isoformat()

        evolution = PatternEvolution(
            pattern_id=pattern_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            evidence=[f"pattern: {pattern.name}"],
        )
        self._evolutions.append(evolution)
        self._evolution_count += 1
        return evolution

    # ── Auto Evolve ─────────────────────────────────────────────

    def evolve_all(self) -> list[PatternEvolution]:
        """自动进化所有模式.

        根据当前数据自动推进状态。

        Returns:
            list[PatternEvolution]: 本次进化记录
        """
        evolutions: list[PatternEvolution] = []

        for pattern_id, pattern in list(self._patterns.items()):
            evolution = self._auto_evolve(pattern)
            if evolution:
                evolutions.append(evolution)

        return evolutions

    def _auto_evolve(self, pattern: LearnedPattern) -> PatternEvolution | None:
        """根据规则自动进化单个模式."""
        status = pattern.status

        # DISCOVERED → VALIDATED
        if status == PatternStatus.DISCOVERED:
            if pattern.evidence_count >= 10 and pattern.confidence >= 0.50:
                return self.validate(pattern.pattern_id)

        # VALIDATED → ACTIVE
        elif status == PatternStatus.VALIDATED:
            if pattern.usage_count >= 5 and pattern.success_rate >= 0.60:
                return self.activate(pattern.pattern_id)

        # ACTIVE → DECAYING
        elif status == PatternStatus.ACTIVE:
            if pattern.success_rate < 0.50 or pattern.decay_rate >= 0.20:
                return self.decay(pattern.pattern_id, "auto_decay")

        # DECAYING → RETIRED or RECOVERED
        elif status == PatternStatus.DECAYING:
            if pattern.success_rate < 0.30:
                return self.retire(pattern.pattern_id, "auto_retire")
            elif pattern.success_rate >= 0.60:
                return self.recover(pattern.pattern_id)

        return None

    # ── Update Pattern Data ─────────────────────────────────────

    def update_pattern(
        self,
        pattern_id: str,
        success_rate: float | None = None,
        usage_count: int | None = None,
        decay_rate: float | None = None,
        evidence_count: int | None = None,
    ) -> LearnedPattern | None:
        """更新模式数据."""
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            return None

        if success_rate is not None:
            pattern.success_rate = success_rate
        if usage_count is not None:
            pattern.usage_count = usage_count
        if decay_rate is not None:
            pattern.decay_rate = decay_rate
        if evidence_count is not None:
            pattern.evidence_count = evidence_count

        pattern.last_validated = datetime.now(timezone.utc).isoformat()
        return pattern

    # ── Query ───────────────────────────────────────────────────

    def get_pattern(self, pattern_id: str) -> LearnedPattern | None:
        return self._patterns.get(pattern_id)

    def get_patterns(self) -> list[LearnedPattern]:
        return list(self._patterns.values())

    def get_active_patterns(self) -> list[LearnedPattern]:
        return [p for p in self._patterns.values() if p.is_active()]

    def get_valid_patterns(self) -> list[LearnedPattern]:
        return [p for p in self._patterns.values() if p.is_valid()]

    def get_by_status(self, status: PatternStatus) -> list[LearnedPattern]:
        return [p for p in self._patterns.values() if p.status == status]

    def get_evolutions(self) -> list[PatternEvolution]:
        return list(self._evolutions)

    def get_evolution_history(self, pattern_id: str) -> list[PatternEvolution]:
        return [e for e in self._evolutions if e.pattern_id == pattern_id]

    def get_summary(self) -> dict[str, Any]:
        patterns = self.get_patterns()
        status_counts = {}
        for status in PatternStatus:
            status_counts[status.value] = len(self.get_by_status(status))

        return {
            "total_patterns": len(patterns),
            "status_distribution": status_counts,
            "active_count": len(self.get_active_patterns()),
            "valid_count": len(self.get_valid_patterns()),
            "total_evolutions": len(self._evolutions),
            "patterns": [p.to_dict() for p in patterns],
        }

    def reset(self) -> None:
        self._patterns.clear()
        self._evolutions.clear()
        self._evolution_count = 0


__all__ = ["VALID_TRANSITIONS", "PatternEvolutionEngine"]