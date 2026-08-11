"""E11.4.2 — Mutation Constraint Layer。

基因突变约束系统，防止 Mutation 失控。
"""

from __future__ import annotations

from .models import MutationConstraint


# ── Default Constraints ──────────────────────────────────

DEFAULT_CONSTRAINTS: dict[str, MutationConstraint] = {
    "hook_contrast": MutationConstraint(
        gene_name="hook_contrast",
        min_value=0.0,
        max_value=1.0,
        max_delta=0.25,
        min_delta=0.05,
        direction="both",
    ),
    "color_brightness": MutationConstraint(
        gene_name="color_brightness",
        min_value=0.0,
        max_value=1.0,
        max_delta=0.25,
        min_delta=0.05,
        direction="both",
    ),
    "color_saturation": MutationConstraint(
        gene_name="color_saturation",
        min_value=0.0,
        max_value=1.0,
        max_delta=0.25,
        min_delta=0.05,
        direction="both",
    ),
    "object_density": MutationConstraint(
        gene_name="object_density",
        min_value=0.0,
        max_value=1.0,
        max_delta=0.25,
        min_delta=0.05,
        direction="both",
    ),
    "transition_speed": MutationConstraint(
        gene_name="transition_speed",
        min_value=0.0,
        max_value=1.0,
        max_delta=0.25,
        min_delta=0.05,
        direction="increase",
    ),
    "reward_reveal_curve": MutationConstraint(
        gene_name="reward_reveal_curve",
        min_value=0.0,
        max_value=1.0,
        max_delta=0.25,
        min_delta=0.05,
        direction="increase",
    ),
}


class ConstraintEngine:
    """突变约束引擎。

    确保所有基因突变都在安全范围内。
    """

    # ── 全局默认 ─────────────────────────────────────────
    GLOBAL_MAX_DELTA = 0.25
    GLOBAL_MIN_DELTA = 0.05

    def __init__(
        self,
        constraints: dict[str, MutationConstraint] | None = None,
    ) -> None:
        self._constraints = dict(constraints) if constraints else dict(DEFAULT_CONSTRAINTS)

    def get(self, gene_name: str) -> MutationConstraint:
        """获取基因约束，不存在则返回默认约束。"""
        if gene_name in self._constraints:
            return self._constraints[gene_name]
        return MutationConstraint(
            gene_name=gene_name,
            max_delta=self.GLOBAL_MAX_DELTA,
            min_delta=self.GLOBAL_MIN_DELTA,
        )

    def apply(
        self,
        gene_name: str,
        old_value: float,
        target_value: float,
        operator: str = "increase",
    ) -> float:
        """应用约束，计算安全的 new_value。

        Args:
            gene_name:    基因名
            old_value:    当前值
            target_value: 目标值
            operator:     操作符

        Returns:
            约束后的安全值
        """
        constraint = self.get(gene_name)

        # 计算原始 delta
        raw_delta = target_value - old_value

        # 限制 delta
        clamped_delta = constraint.clamp_delta(raw_delta, operator)

        # 计算新值
        new_value = old_value + clamped_delta

        # 限制在值域内
        new_value = constraint.clamp(new_value)

        return round(new_value, 4)

    def validate(
        self,
        gene_name: str,
        old_value: float,
        new_value: float,
    ) -> bool:
        """验证突变是否合法。"""
        constraint = self.get(gene_name)
        return constraint.is_valid(old_value, new_value)

    def add_constraint(self, constraint: MutationConstraint) -> None:
        """添加自定义约束。"""
        self._constraints[constraint.gene_name] = constraint

    def remove_constraint(self, gene_name: str) -> bool:
        return self._constraints.pop(gene_name, None) is not None

    def list_genes(self) -> list[str]:
        return list(self._constraints.keys())

    def to_dict(self) -> dict[str, dict]:
        return {
            gene: constraint.to_dict()
            for gene, constraint in self._constraints.items()
        }

    def __repr__(self) -> str:
        return f"ConstraintEngine(genes={len(self._constraints)})"