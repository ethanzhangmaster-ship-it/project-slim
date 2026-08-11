"""E11.2 Step 3 — Mutation Strategy Layer Test.

7 AC covering:
  1. StrategyContext 创建 (from_genome / 强弱基因自动分类)
  2. WeakGeneEnhancement (弱基因 → ENHANCE)
  3. StrongGenePreserve (强基因 + 弱基因 → REPLACE)
  4. Exploration (无强弱 → REPLACE)
  5. StrategySelector (优先级选择)
  6. Rule Priority (优先级正确)
  7. Deterministic (相同 context → 相同结果)
"""

from __future__ import annotations

from market_ops.e11.mutation import (
    MutationType,
    MutationRule,
    StrategyContext,
    MutationStrategy,
    WeakGeneEnhancementStrategy,
    StrongGenePreserveStrategy,
    ExplorationMutationStrategy,
    StrategySelector,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_context(
    genome_id: str = "genome_001",
    fitness: dict | None = None,
    weak_genes: list | None = None,
    strong_genes: list | None = None,
    gene_details: dict | None = None,
) -> StrategyContext:
    return StrategyContext(
        genome_id=genome_id,
        fitness=fitness or {"ctr": 0.12, "roas_d7": 0.35},
        weak_genes=weak_genes or [],
        strong_genes=strong_genes or [],
        gene_details=gene_details or {},
    )


# ═══════════════════════════════════════════════════════════
# AC1 — StrategyContext 创建
# ═══════════════════════════════════════════════════════════

def test_ac1_context_create():
    """AC1a: StrategyContext creates with all fields."""
    ctx = StrategyContext(
        genome_id="genome_001",
        fitness={"ctr": 0.12, "roas_d7": 0.35},
        weak_genes=["reward"],
        strong_genes=["hook"],
    )

    assert ctx.genome_id == "genome_001"
    assert ctx.fitness["ctr"] == 0.12
    assert ctx.weak_genes == ["reward"]
    assert ctx.strong_genes == ["hook"]


def test_ac1b_context_from_genome_weak():
    """AC1b: from_genome detects weak genes (strength < 0.5)."""
    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {"style": "fantasy", "composition": "center"},
        "reward": {"type": "unlock", "intensity": 0.30},  # weak
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }

    ctx = StrategyContext.from_genome(
        genome_id="genome_001",
        fitness={"ctr": 0.12},
        genes=genes,
        weak_threshold=0.5,
        strong_threshold=0.8,
    )

    assert "reward" in ctx.weak_genes
    assert "hook" in ctx.strong_genes  # 0.82 >= 0.8


def test_ac1c_context_from_genome_strong():
    """AC1c: from_genome detects strong genes (strength >= 0.8)."""
    genes = {
        "hook": {"type": "rescue", "strength": 0.91},
        "visual": {"style": "fantasy", "composition": "center"},
        "reward": {"type": "unlock", "intensity": 0.85},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }

    ctx = StrategyContext.from_genome(
        genome_id="genome_001",
        fitness={"ctr": 0.15},
        genes=genes,
        weak_threshold=0.5,
        strong_threshold=0.8,
    )

    assert "hook" in ctx.strong_genes
    assert "reward" in ctx.strong_genes
    assert len(ctx.weak_genes) == 0


def test_ac1d_context_empty_gene_is_weak():
    """AC1d: Empty gene slot is classified as weak."""
    genes = {
        "hook": {"type": "rescue", "strength": 0.82},
        "visual": {},  # empty
        "reward": {"type": "unlock", "intensity": 0.75},
        "emotion": {"primary": "curiosity"},
        "gameplay": {"mechanic": "merge"},
    }

    ctx = StrategyContext.from_genome(
        genome_id="genome_001",
        fitness={"ctr": 0.12},
        genes=genes,
    )

    assert "visual" in ctx.weak_genes


def test_ac1e_context_serialization():
    """AC1e: StrategyContext to_dict / from_dict roundtrip."""
    ctx = StrategyContext(
        genome_id="genome_001",
        fitness={"ctr": 0.12, "roas_d7": 0.35},
        weak_genes=["reward"],
        strong_genes=["hook"],
        gene_details={"hook": {"type": "rescue", "strength": 0.82}},
    )

    d = ctx.to_dict()
    assert d["genome_id"] == "genome_001"
    assert d["weak_genes"] == ["reward"]

    restored = StrategyContext.from_dict(d)
    assert restored.genome_id == ctx.genome_id
    assert restored.weak_genes == ctx.weak_genes
    assert restored.strong_genes == ctx.strong_genes


# ═══════════════════════════════════════════════════════════
# AC2 — Weak Gene Enhancement Strategy
# ═══════════════════════════════════════════════════════════

def test_ac2_weak_gene_enhance():
    """AC2a: Weak gene detected → ENHANCE rule returned."""
    ctx = _make_context(
        weak_genes=["reward"],
        gene_details={"reward": {"type": "unlock", "intensity": 0.3}},
    )

    strategy = WeakGeneEnhancementStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.target_gene == "reward"
    assert rule.mutation_type == MutationType.ENHANCE
    assert rule.strategy == "weak_enhancement"


def test_ac2b_weak_gene_priority_scales():
    """AC2b: More weak genes → higher priority."""
    ctx1 = _make_context(weak_genes=["reward"])
    ctx2 = _make_context(weak_genes=["reward", "visual", "emotion"])

    strategy = WeakGeneEnhancementStrategy()
    rule1 = strategy.evaluate(ctx1)
    rule2 = strategy.evaluate(ctx2)

    assert rule1 is not None
    assert rule2 is not None
    assert rule2.priority > rule1.priority


def test_ac2c_weak_gene_no_weak_returns_none():
    """AC2c: No weak genes → returns None."""
    ctx = _make_context(weak_genes=[])

    strategy = WeakGeneEnhancementStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is None


def test_ac2d_weak_gene_selects_first():
    """AC2d: Multiple weak genes → selects first one."""
    ctx = _make_context(
        weak_genes=["reward", "visual", "gameplay"],
        gene_details={
            "reward": {"intensity": 0.3},
            "visual": {"style": ""},
            "gameplay": {"mechanic": ""},
        },
    )

    strategy = WeakGeneEnhancementStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.target_gene == "reward"  # 第一个弱基因


# ═══════════════════════════════════════════════════════════
# AC3 — Strong Gene Preserve Strategy
# ═══════════════════════════════════════════════════════════

def test_ac3_strong_gene_preserve():
    """AC3a: Strong + weak genes → REPLACE weak gene."""
    ctx = _make_context(
        strong_genes=["hook"],
        weak_genes=["reward"],
        gene_details={
            "hook": {"type": "rescue", "strength": 0.82},
            "reward": {"type": "unlock", "intensity": 0.3},
        },
    )

    strategy = StrongGenePreserveStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.target_gene == "reward"  # 替换弱基因
    assert rule.mutation_type == MutationType.REPLACE
    assert rule.strategy == "strong_preserve_replace_weak"
    assert rule.priority == 0.8


def test_ac3b_strong_gene_no_strong_returns_none():
    """AC3b: No strong genes → returns None."""
    ctx = _make_context(
        strong_genes=[],
        weak_genes=["reward"],
    )

    strategy = StrongGenePreserveStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is None


def test_ac3c_strong_gene_no_weak_returns_none():
    """AC3c: Strong genes but no weak genes → returns None."""
    ctx = _make_context(
        strong_genes=["hook"],
        weak_genes=[],  # 无弱基因
    )

    strategy = StrongGenePreserveStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is None


def test_ac3d_strong_gene_preserves_strong():
    """AC3d: Strong gene is NOT targeted for mutation."""
    ctx = _make_context(
        strong_genes=["hook"],
        weak_genes=["reward"],
    )

    strategy = StrongGenePreserveStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.target_gene != "hook"  # 强基因不被修改
    assert rule.target_gene == "reward"


# ═══════════════════════════════════════════════════════════
# AC4 — Exploration Mutation Strategy
# ═══════════════════════════════════════════════════════════

def test_ac4_exploration_middle_gene():
    """AC4a: No strong/weak → selects middle gene for REPLACE."""
    ctx = _make_context(
        weak_genes=[],
        strong_genes=[],
        gene_details={
            "hook": {"type": "rescue", "strength": 0.6},
            "visual": {"style": "fantasy", "composition": "center"},
            "reward": {"type": "unlock", "intensity": 0.6},
            "emotion": {"primary": "curiosity"},
            "gameplay": {"mechanic": "merge"},
        },
    )

    strategy = ExplorationMutationStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.mutation_type == MutationType.REPLACE
    assert rule.strategy == "exploration_replace"
    assert rule.priority == 0.5


def test_ac4b_exploration_with_weak():
    """AC4b: Only weak genes → selects weak gene for REPLACE."""
    ctx = _make_context(
        weak_genes=["reward", "visual"],
        strong_genes=[],
        gene_details={
            "hook": {"type": "rescue", "strength": 0.82},
            "visual": {"style": "fantasy", "composition": "center"},
            "reward": {"type": "unlock", "intensity": 0.3},
            "emotion": {"primary": "curiosity"},
            "gameplay": {"mechanic": "merge"},
        },
    )

    strategy = ExplorationMutationStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.mutation_type == MutationType.REPLACE


def test_ac4c_exploration_empty_genes_returns_none():
    """AC4c: Empty gene_details → returns None."""
    ctx = _make_context(gene_details={})

    strategy = ExplorationMutationStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is None


# ═══════════════════════════════════════════════════════════
# AC5 — Strategy Selector
# ═══════════════════════════════════════════════════════════

def test_ac5_selector_strong_weak():
    """AC5a: Strong + Weak → StrongGenePreserve."""
    ctx = _make_context(
        strong_genes=["hook"],
        weak_genes=["reward"],
    )

    selector = StrategySelector()
    strategy = selector.select(ctx)

    assert isinstance(strategy, StrongGenePreserveStrategy)


def test_ac5b_selector_weak_only():
    """AC5b: Weak only → WeakGeneEnhancement."""
    ctx = _make_context(
        strong_genes=[],
        weak_genes=["reward"],
    )

    selector = StrategySelector()
    strategy = selector.select(ctx)

    assert isinstance(strategy, WeakGeneEnhancementStrategy)


def test_ac5c_selector_no_strong_no_weak():
    """AC5c: No strong/weak → ExplorationMutation."""
    ctx = _make_context(
        strong_genes=[],
        weak_genes=[],
    )

    selector = StrategySelector()
    strategy = selector.select(ctx)

    assert isinstance(strategy, ExplorationMutationStrategy)


def test_ac5d_selector_with_rule():
    """AC5d: select_with_rule returns (strategy, rule)."""
    ctx = _make_context(
        strong_genes=["hook"],
        weak_genes=["reward"],
    )

    selector = StrategySelector()
    strategy, rule = selector.select_with_rule(ctx)

    assert isinstance(strategy, StrongGenePreserveStrategy)
    assert rule is not None
    assert rule.mutation_type == MutationType.REPLACE


def test_ac5e_selector_count():
    """AC5e: selection_count increments."""
    selector = StrategySelector()
    assert selector.selection_count == 0

    ctx = _make_context(weak_genes=["reward"])
    selector.select(ctx)
    assert selector.selection_count == 1

    selector.select(ctx)
    assert selector.selection_count == 2


# ═══════════════════════════════════════════════════════════
# AC6 — Rule Priority
# ═══════════════════════════════════════════════════════════

def test_ac6_priority_weak_enhancement():
    """AC6a: WeakGeneEnhancement priority is 0.7+."""
    ctx = _make_context(weak_genes=["reward"])
    strategy = WeakGeneEnhancementStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.priority >= 0.7


def test_ac6b_priority_strong_preserve():
    """AC6b: StrongGenePreserve priority is fixed 0.8."""
    ctx = _make_context(strong_genes=["hook"], weak_genes=["reward"])
    strategy = StrongGenePreserveStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.priority == 0.8


def test_ac6c_priority_exploration():
    """AC6c: Exploration priority is fixed 0.5."""
    ctx = _make_context(
        gene_details={"hook": {"type": "rescue", "strength": 0.6}},
    )
    strategy = ExplorationMutationStrategy()
    rule = strategy.evaluate(ctx)

    assert rule is not None
    assert rule.priority == 0.5


# ═══════════════════════════════════════════════════════════
# AC7 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac7_deterministic_weak():
    """AC7a: Same context → same rule from WeakGeneEnhancement."""
    ctx = _make_context(weak_genes=["reward"])
    strategy = WeakGeneEnhancementStrategy()

    rule1 = strategy.evaluate(ctx)
    rule2 = strategy.evaluate(ctx)

    assert rule1 is not None
    assert rule2 is not None
    assert rule1.target_gene == rule2.target_gene
    assert rule1.mutation_type == rule2.mutation_type
    assert rule1.priority == rule2.priority


def test_ac7b_deterministic_selector():
    """AC7b: Same context → same strategy from Selector."""
    ctx = _make_context(strong_genes=["hook"], weak_genes=["reward"])
    selector = StrategySelector()

    s1 = selector.select(ctx)
    s2 = selector.select(ctx)

    assert type(s1) == type(s2)


def test_ac7c_deterministic_rule_from_selector():
    """AC7c: Same context → same rule from select_with_rule."""
    ctx = _make_context(weak_genes=["reward"])
    selector = StrategySelector()

    _, r1 = selector.select_with_rule(ctx)
    _, r2 = selector.select_with_rule(ctx)

    assert r1 is not None
    assert r2 is not None
    assert r1.target_gene == r2.target_gene
    assert r1.mutation_type == r2.mutation_type