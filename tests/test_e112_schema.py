"""E11.2 Step 1 — Mutation Schema Test.

6 AC covering:
  1. MutationType 完整枚举
  2. MutationRule 创建
  3. MutationTarget 创建
  4. MutationResult 创建
  5. MutationHistory 创建
  6. Schema 序列化兼容 (to_dict / from_dict roundtrip)
"""

from __future__ import annotations

from datetime import datetime

from market_ops.e11.mutation import (
    MutationType,
    MutationTarget,
    MutationRule,
    MutationResult,
    MutationHistory,
)


# ═══════════════════════════════════════════════════════════
# AC1 — MutationType 完整枚举
# ═══════════════════════════════════════════════════════════

def test_ac1_mutation_type_enum():
    """AC1: MutationType has 4 values — REPLACE, COMBINE, ENHANCE, REMOVE."""
    assert MutationType.REPLACE.value == "replace"
    assert MutationType.COMBINE.value == "combine"
    assert MutationType.ENHANCE.value == "enhance"
    assert MutationType.REMOVE.value == "remove"

    # 从字符串构造
    assert MutationType("replace") == MutationType.REPLACE
    assert MutationType("combine") == MutationType.COMBINE
    assert MutationType("enhance") == MutationType.ENHANCE
    assert MutationType("remove") == MutationType.REMOVE

    # 枚举完整性
    assert len(MutationType) == 4


# ═══════════════════════════════════════════════════════════
# AC2 — MutationRule 创建
# ═══════════════════════════════════════════════════════════

def test_ac2_mutation_rule_create():
    """AC2a: MutationRule creates with default rule_id."""
    rule = MutationRule(
        target_gene="hook",
        mutation_type=MutationType.REPLACE,
        strategy="winner_pattern",
        priority=0.8,
    )

    assert rule.target_gene == "hook"
    assert rule.mutation_type == MutationType.REPLACE
    assert rule.strategy == "winner_pattern"
    assert rule.priority == 0.8
    assert rule.rule_id.startswith("rule_")
    assert len(rule.rule_id) == 13  # "rule_" + 8 hex chars


def test_ac2b_mutation_rule_custom_id():
    """AC2b: MutationRule accepts custom rule_id."""
    rule = MutationRule(
        rule_id="rule_001",
        target_gene="reward",
        mutation_type=MutationType.ENHANCE,
        strategy="targeted",
        priority=0.9,
    )

    assert rule.rule_id == "rule_001"
    assert rule.target_gene == "reward"
    assert rule.mutation_type == MutationType.ENHANCE


def test_ac2c_mutation_rule_default_priority():
    """AC2c: MutationRule defaults priority to 0.5."""
    rule = MutationRule(
        target_gene="emotion",
        mutation_type=MutationType.COMBINE,
        strategy="random",
    )
    assert rule.priority == 0.5


# ═══════════════════════════════════════════════════════════
# AC3 — MutationTarget 创建
# ═══════════════════════════════════════════════════════════

def test_ac3_mutation_target_create():
    """AC3a: MutationTarget creates with all fields."""
    target = MutationTarget(
        gene_name="hook",
        old_value="rescue",
        new_value="discovery",
        confidence=0.85,
    )

    assert target.gene_name == "hook"
    assert target.old_value == "rescue"
    assert target.new_value == "discovery"
    assert target.confidence == 0.85


def test_ac3b_mutation_target_defaults():
    """AC3b: MutationTarget with default values."""
    target = MutationTarget(gene_name="visual")
    assert target.gene_name == "visual"
    assert target.old_value is None
    assert target.new_value is None
    assert target.confidence == 0.0


def test_ac3c_mutation_target_types():
    """AC3c: MutationTarget supports Any type for values."""
    # dict value
    target_dict = MutationTarget(
        gene_name="hook",
        old_value={"type": "rescue", "strength": 0.82},
        new_value={"type": "discovery", "strength": 0.90},
        confidence=0.88,
    )
    assert target_dict.old_value["type"] == "rescue"
    assert target_dict.new_value["strength"] == 0.90

    # int value
    target_int = MutationTarget(
        gene_name="reward",
        old_value=5,
        new_value=8,
        confidence=0.75,
    )
    assert target_int.old_value == 5
    assert target_int.new_value == 8


# ═══════════════════════════════════════════════════════════
# AC4 — MutationResult 创建
# ═══════════════════════════════════════════════════════════

def test_ac4_mutation_result_create():
    """AC4a: MutationResult creates with auto-generated mutation_id."""
    result = MutationResult(
        parent_genome_id="genome_001",
        child_genome_id="genome_002",
        changes=[
            MutationTarget(
                gene_name="hook",
                old_value="rescue",
                new_value="discovery",
                confidence=0.85,
            ),
        ],
        success=True,
    )

    assert result.parent_genome_id == "genome_001"
    assert result.child_genome_id == "genome_002"
    assert len(result.changes) == 1
    assert result.changes[0].gene_name == "hook"
    assert result.success is True
    assert result.mutation_id.startswith("mutation_")
    assert len(result.mutation_id) == 17  # "mutation_" + 8 hex chars


def test_ac4b_mutation_result_add_change():
    """AC4b: MutationResult.add_change appends MutationTarget."""
    result = MutationResult(
        parent_genome_id="genome_001",
        child_genome_id="genome_002",
    )

    assert len(result.changes) == 0

    result.add_change(MutationTarget(
        gene_name="hook",
        old_value="rescue",
        new_value="discovery",
        confidence=0.85,
    ))
    result.add_change(MutationTarget(
        gene_name="visual",
        old_value="fantasy",
        new_value="realistic",
        confidence=0.70,
    ))

    assert len(result.changes) == 2
    assert result.changes[0].gene_name == "hook"
    assert result.changes[1].gene_name == "visual"


def test_ac4c_mutation_result_failure():
    """AC4c: MutationResult can represent failure."""
    result = MutationResult(
        parent_genome_id="genome_001",
        child_genome_id="genome_001",  # same as parent = no change
        changes=[],
        success=False,
    )

    assert result.success is False
    assert result.parent_genome_id == result.child_genome_id
    assert len(result.changes) == 0


# ═══════════════════════════════════════════════════════════
# AC5 — MutationHistory 创建
# ═══════════════════════════════════════════════════════════

def test_ac5_mutation_history_create():
    """AC5a: MutationHistory records parent→child chain."""
    history = MutationHistory(
        mutation_id="mutation_001",
        parent_id="genome_001",
        child_id="genome_002",
        rule_id="rule_abc123",
    )

    assert history.mutation_id == "mutation_001"
    assert history.parent_id == "genome_001"
    assert history.child_id == "genome_002"
    assert history.rule_id == "rule_abc123"
    assert isinstance(history.created_at, datetime)


def test_ac5b_mutation_history_no_rule():
    """AC5b: MutationHistory without rule_id (defaults None)."""
    history = MutationHistory(
        mutation_id="mutation_002",
        parent_id="genome_002",
        child_id="genome_003",
    )

    assert history.mutation_id == "mutation_002"
    assert history.rule_id is None
    assert isinstance(history.created_at, datetime)


def test_ac5c_mutation_history_chain():
    """AC5c: Multiple histories form evolution chain."""
    h1 = MutationHistory(
        mutation_id="mutation_001",
        parent_id="genome_001",
        child_id="genome_002",
    )
    h2 = MutationHistory(
        mutation_id="mutation_002",
        parent_id="genome_002",
        child_id="genome_003",
    )
    h3 = MutationHistory(
        mutation_id="mutation_003",
        parent_id="genome_003",
        child_id="genome_004",
    )

    chain = [h1, h2, h3]
    assert len(chain) == 3

    # 验证链式: parent → child → parent → child
    assert chain[0].child_id == chain[1].parent_id
    assert chain[1].child_id == chain[2].parent_id


# ═══════════════════════════════════════════════════════════
# AC6 — Schema 序列化兼容
# ═══════════════════════════════════════════════════════════

def test_ac6_mutation_target_serialization():
    """AC6a: MutationTarget to_dict / from_dict roundtrip."""
    target = MutationTarget(
        gene_name="hook",
        old_value="rescue",
        new_value="discovery",
        confidence=0.85,
    )

    d = target.to_dict()
    assert d["gene_name"] == "hook"
    assert d["old_value"] == "rescue"
    assert d["new_value"] == "discovery"
    assert d["confidence"] == 0.85

    restored = MutationTarget.from_dict(d)
    assert restored.gene_name == target.gene_name
    assert restored.old_value == target.old_value
    assert restored.new_value == target.new_value
    assert restored.confidence == target.confidence


def test_ac6b_mutation_rule_serialization():
    """AC6b: MutationRule to_dict / from_dict roundtrip."""
    rule = MutationRule(
        rule_id="rule_001",
        target_gene="hook",
        mutation_type=MutationType.REPLACE,
        strategy="winner_pattern",
        priority=0.8,
    )

    d = rule.to_dict()
    assert d["rule_id"] == "rule_001"
    assert d["target_gene"] == "hook"
    assert d["mutation_type"] == "replace"
    assert d["strategy"] == "winner_pattern"
    assert d["priority"] == 0.8

    restored = MutationRule.from_dict(d)
    assert restored.rule_id == rule.rule_id
    assert restored.target_gene == rule.target_gene
    assert restored.mutation_type == rule.mutation_type
    assert restored.strategy == rule.strategy
    assert restored.priority == rule.priority


def test_ac6c_mutation_result_serialization():
    """AC6c: MutationResult to_dict / from_dict roundtrip."""
    result = MutationResult(
        mutation_id="mutation_001",
        parent_genome_id="genome_001",
        child_genome_id="genome_002",
        changes=[
            MutationTarget(
                gene_name="hook",
                old_value="rescue",
                new_value="discovery",
                confidence=0.85,
            ),
            MutationTarget(
                gene_name="visual",
                old_value="fantasy",
                new_value="realistic",
                confidence=0.70,
            ),
        ],
        success=True,
    )

    d = result.to_dict()
    assert d["mutation_id"] == "mutation_001"
    assert d["parent_genome_id"] == "genome_001"
    assert d["child_genome_id"] == "genome_002"
    assert len(d["changes"]) == 2
    assert d["changes"][0]["gene_name"] == "hook"
    assert d["changes"][1]["gene_name"] == "visual"
    assert d["success"] is True

    restored = MutationResult.from_dict(d)
    assert restored.mutation_id == result.mutation_id
    assert restored.parent_genome_id == result.parent_genome_id
    assert restored.child_genome_id == result.child_genome_id
    assert len(restored.changes) == 2
    assert restored.changes[0].gene_name == "hook"
    assert restored.changes[1].gene_name == "visual"
    assert restored.success is True


def test_ac6d_mutation_history_serialization():
    """AC6d: MutationHistory to_dict / from_dict roundtrip."""
    history = MutationHistory(
        mutation_id="mutation_001",
        parent_id="genome_001",
        child_id="genome_002",
        rule_id="rule_abc123",
    )

    d = history.to_dict()
    assert d["mutation_id"] == "mutation_001"
    assert d["parent_id"] == "genome_001"
    assert d["child_id"] == "genome_002"
    assert d["rule_id"] == "rule_abc123"
    assert "created_at" in d

    restored = MutationHistory.from_dict(d)
    assert restored.mutation_id == history.mutation_id
    assert restored.parent_id == history.parent_id
    assert restored.child_id == history.child_id
    assert restored.rule_id == history.rule_id
    assert isinstance(restored.created_at, datetime)