"""E12.7.6 Evolution Manager — 连接 E11 Evolution Engine，记忆模式 → 创意进化."""

from __future__ import annotations

from typing import Any

from ..memory.models import GrowthPattern


class EvolutionManager:
    """进化管理器 — 连接 Growth OS 记忆模式到 E11 Evolution Engine.

    流程:
      Memory Pattern → Creative Evolution → New Genome → New Experiment

    例如:
      发现 Winner Pattern: Character + Crisis + Rescue
      自动生成: Creative Mutation (change character, change scene, keep hook)
    """

    def __init__(self):
        self._evolution_count: int = 0
        self._mutations_generated: int = 0

    @property
    def evolution_count(self) -> int:
        return self._evolution_count

    @property
    def mutations_generated(self) -> int:
        return self._mutations_generated

    # ── Evolve ────────────────────────────────────────────────

    def evolve(self, patterns: list[GrowthPattern]) -> dict[str, Any]:
        """从记忆模式中生成进化建议."""
        self._evolution_count += 1

        mutations: list[dict[str, Any]] = []
        for pattern in patterns:
            if pattern.is_reliable:
                mutation = self._generate_mutation(pattern)
                if mutation:
                    mutations.append(mutation)
                    self._mutations_generated += 1

        return {
            "patterns_processed": len(patterns),
            "mutations_generated": len(mutations),
            "mutations": mutations,
        }

    def evolve_from_pattern(self, pattern: GrowthPattern) -> dict[str, Any] | None:
        """从单个模式生成进化建议."""
        if not pattern.is_reliable:
            return None

        mutation = self._generate_mutation(pattern)
        if mutation:
            self._evolution_count += 1
            self._mutations_generated += 1
        return mutation

    # ── Mutation Generation ───────────────────────────────────

    def _generate_mutation(self, pattern: GrowthPattern) -> dict[str, Any] | None:
        """生成创意突变建议."""
        if not pattern.conditions:
            return None

        mutation: dict[str, Any] = {
            "pattern_id": pattern.pattern_id,
            "source_confidence": pattern.confidence,
            "mutation_type": self._determine_mutation_type(pattern),
            "target_genes": self._extract_target_genes(pattern),
            "suggested_changes": self._suggest_changes(pattern),
            "expected_impact": self._predict_impact(pattern),
            "priority": self._compute_priority(pattern),
        }

        return mutation

    def _determine_mutation_type(self, pattern: GrowthPattern) -> str:
        """确定突变类型."""
        if pattern.confidence >= 0.85:
            return "amplify"
        if pattern.confidence >= 0.7:
            return "explore"
        return "experiment"

    def _extract_target_genes(self, pattern: GrowthPattern) -> list[str]:
        """提取目标基因."""
        genes: list[str] = []
        for action in pattern.actions:
            task_type = action.get("task_type", "")
            if "creative" in task_type or "mutation" in task_type:
                genes.append("visual")
                genes.append("hook")
            if "budget" in task_type:
                genes.append("strategy")
        if not genes:
            genes = ["hook", "visual", "gameplay"]
        return list(set(genes))

    def _suggest_changes(self, pattern: GrowthPattern) -> list[dict[str, Any]]:
        """建议具体变化."""
        changes: list[dict[str, Any]] = []
        for action in pattern.actions[:3]:
            task_type = action.get("task_type", "unknown")
            params = {k: v for k, v in action.items() if k not in ("task_type", "target_module", "priority")}
            changes.append({
                "action_type": task_type,
                "parameters": params,
                "reason": f"Pattern {pattern.pattern_id} shows {pattern.success_rate:.0%} success rate",
            })
        return changes

    def _predict_impact(self, pattern: GrowthPattern) -> dict[str, float]:
        """预测进化影响."""
        return {
            "expected_roas_improvement": round(pattern.success_rate * 0.3, 2),
            "expected_ctr_improvement": round(pattern.success_rate * 0.2, 2),
            "confidence": pattern.confidence,
        }

    def _compute_priority(self, pattern: GrowthPattern) -> int:
        """计算突变优先级."""
        score = int(pattern.confidence * 50 + pattern.success_rate * 30 + pattern.usage_count * 2)
        return min(100, max(10, score))

    # ── Reverse Evolution ─────────────────────────────────────

    def suppress_pattern(self, pattern: GrowthPattern) -> dict[str, Any]:
        """抑制低效模式."""
        return {
            "pattern_id": pattern.pattern_id,
            "action": "suppress",
            "reason": f"Low confidence ({pattern.confidence:.2f}) or low success rate ({pattern.success_rate:.0%})",
            "suggested_genes": self._extract_target_genes(pattern),
        }

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "evolution_count": self._evolution_count,
            "mutations_generated": self._mutations_generated,
        }