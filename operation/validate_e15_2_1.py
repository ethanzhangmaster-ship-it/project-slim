"""
E15.2.1+E15.2.2 Acceptance Gate — Operation Memory + Safety Layer

Validates:
1. Memory: record → persist → recall → summarize (8 cases)
2. Safety: revenue protection, retention protection, frequency caps,
   rollback requirement, past evidence, combined scenarios (14 cases)
3. Integration: Memory + Safety together (3 cases)

Target: 25 cases, 0 failures.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from operation.memory.models import OperationRecord, record_factory
from operation.memory.store import OperationMemoryStore
from operation.memory.agent import MemoryAgent
from operation.safety.models import SafetyCheck, SafetyResult
from operation.safety.rules import (
    SafetyRuleEngine,
    RevenueProtectionRule,
    RevenueWarningRule,
    RetentionProtectionRule,
    RetentionWarningRule,
    FrequencyCapRule,
    RollbackRule,
    PastEvidenceRule,
)
from operation.safety.agent import SafetyAgent

PASS, FAIL = 0, 0
TOTAL = 0


def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  PASS  [{TOTAL:02d}] {label}")
    else:
        FAIL += 1
        print(f"  FAIL  [{TOTAL:02d}] {label}  — {detail}")


# =========================================================================== #
# Part 1: Memory Layer (9 cases)
# =========================================================================== #
print("\n=== E15.2.1 Operation Memory ===")

tmpdir = tempfile.mkdtemp(prefix="mem_test_")
store = OperationMemoryStore(base_dir=os.path.join(tmpdir, "memory"))
agent = MemoryAgent(store=store)

# 1.1 Record basic operation
rec1 = agent.record(
    game_id="game_01",
    operation="raise_bid_floor",
    provider="max",
    sandbox="SIMULATION",
    context={"country": "US", "platform": "android", "format": "reward"},
    before_state={"ecpm": 12.5, "revenue_daily": 340.0},
    after_state={"ecpm": 13.8, "revenue_daily": 375.0},
    result_metrics={"revenue_change_pct": 10.3, "ecpm_change_pct": 10.4},
    confidence=0.91,
    tags=["profitable", "low_risk"],
)
check("record creates OperationRecord", rec1.record_id.startswith("mem_"))
check("record has fingerprint", len(rec1.fingerprint) == 12)
check("record calculates revenue_impact", rec1.revenue_impact == 10.3)

# 1.2 Persist and reload
loaded = store.load("game_01")
check("persist + reload: 1 record", len(loaded) == 1)
check("reloaded record matches", loaded[0].record_id == rec1.record_id)

# 1.3 Multiple records
for i in range(5):
    agent.record(
        game_id="game_01",
        operation="add_waterfall_network",
        provider="max",
        context={"country": "US", "network": f"network_{i}"},
        before_state={"networks": i},
        after_state={"networks": i + 1},
        confidence=0.7 + i * 0.05,
    )
check("6 total records for game_01", len(store.load("game_01")) == 6)

# 1.4 Query by operation
results = store.query(game_id="game_01", operation="raise_bid_floor")
check("query by operation returns 1", len(results) == 1)

# 1.5 Query by provider
results = store.query(game_id="game_01", provider="max")
check("query by provider returns 6", len(results) == 6)

# 1.6 Find similar
similar = agent.recall_similar("game_01", "raise_bid_floor", {"country": "US", "platform": "android"})
check("find similar returns matches", len(similar) == 1)
check("similar record is the original", similar[0].record_id == rec1.record_id)

# 1.7 Summary
summary = agent.summary("game_01")
check("summary total_operations=6", summary["total_operations"] == 6)
check("summary has operation_counts", "raise_bid_floor" in summary["operation_counts"])
check("summary success_rate calculated", summary["success_rate"] == 1.0)

# 1.8 Operation effectiveness
eff = agent.get_operation_effectiveness("game_01", "raise_bid_floor")
check("effectiveness: times_used=1", eff["times_used"] == 1)
check("effectiveness: recommendation is highly_effective", eff["recommendation"] == "highly_effective")

# 1.9 Unknown operation effectiveness
eff2 = agent.get_operation_effectiveness("game_01", "unknown_op")
check("unknown operation: times_used=0", eff2["times_used"] == 0)
check("unknown operation: effectiveness=unknown", eff2["effectiveness"] == "unknown")

# 1.10 Multi-game isolation
agent.record(game_id="game_02", operation="raise_bid_floor", provider="max",
             context={"country": "JP"}, confidence=0.5)
check("game_02: 1 record", len(store.load("game_02")) == 1)
check("game_01 still has 6 records", len(store.load("game_01")) == 6)

# 1.11 Top profitable
summary = agent.summary("game_01")
check("top_profitable exists", len(summary.get("top_profitable", [])) > 0)

# 1.12 Failed records tracking
agent.record(game_id="game_03", operation="lower_bid_floor", provider="max",
             context={"country": "KR"}, before_state={"ecpm": 10}, after_state={"ecpm": 8},
             result_success=False, error="ECPM dropped below threshold", confidence=0.2)
check("failed record is stored", len(store.load("game_03")) == 1)
check("failed record has error", store.load("game_03")[0].error == "ECPM dropped below threshold")
summary3 = agent.summary("game_03")
check("failure_count tracked", summary3["failure_count"] == 1)
check("success_rate is 0 for all failures", summary3["success_rate"] == 0.0)


# =========================================================================== #
# Part 2: Safety Layer (16 cases)
# =========================================================================== #
print("\n=== E15.2.2 Action Safety ===")

engine = SafetyRuleEngine()

# 2.1 Safe operation passes
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="raise_bid_floor", provider="max",
    changes={"floor": 35, "old_floor": 30},
    current_metrics={"ecpm": 12.5},
    expected_impact={"revenue_change_pct": 5},
    has_rollback=True,
))
check("safe operation: allowed", r.is_allowed)
check("safe operation: no violations", len(r.violated_rules) == 0)

# 2.2 Revenue loss > 10% → blocked
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="lower_bid_floor", provider="max",
    expected_impact={"revenue_change_pct": -15.0},
))
check("revenue_loss_15pct: blocked", r.is_blocked)
check("revenue_loss_15pct: reason mentions loss",
     "15" in r.reason and "revenue" in r.reason.lower())

# 2.3 Revenue loss 5% → warning only
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="lower_bid_floor", provider="max",
    expected_impact={"revenue_change_pct": -5.0},
    has_rollback=True,
))
check("revenue_loss_5pct: needs confirmation", r.needs_confirmation)
check("revenue_loss_5pct: not blocked", not r.is_blocked)

# 2.4 Revenue loss 2% → allowed (below warning threshold)
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="lower_bid_floor", provider="max",
    expected_impact={"revenue_change_pct": -2.0},
    has_rollback=True,
))
check("revenue_loss_2pct: allowed", r.is_allowed)

# 2.5 Retention drop > 8% → blocked
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="increase_frequency", provider="max",
    expected_impact={"retention_change_pct": -10.0},
    current_metrics={"retention_d1": 0.38},
))
check("retention_drop_10pct: blocked", r.is_blocked)

# 2.6 Retention drop 5% → warning
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="increase_frequency", provider="max",
    expected_impact={"retention_change_pct": -5.0},
    current_metrics={"retention_d1": 0.38},
))
check("retention_drop_5pct: needs confirmation", r.needs_confirmation)
check("retention_drop_5pct: not blocked", not r.is_blocked)

# 2.7 Interstitial frequency below 90s → blocked
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="change_frequency_cap", provider="max",
    changes={"ad_format": "interstitial", "interval_seconds": 30},
))
check("interstitial_30s: blocked", r.is_blocked)
check("interstitial_30s: reason mentions minimum", "90" in r.reason.lower() or "90" in str(r.reason))

# 2.8 Rewarded video 30s is allowed (at cap)
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="change_frequency_cap", provider="max",
    changes={"ad_format": "rewarded", "interval_seconds": 30},
    has_rollback=True,
))
check("rewarded_30s: allowed (at cap)", r.is_allowed)

# 2.9 Rewarded video 15s → blocked
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="change_frequency_cap", provider="max",
    changes={"ad_format": "rewarded", "interval_seconds": 15},
))
check("rewarded_15s: blocked", r.is_blocked)

# 2.10 Rollback required for major op without snapshot
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="delete_product", provider="iap",
    has_rollback=False,
))
check("delete_product_no_rollback: blocked", r.is_blocked)
check("delete_product_no_rollback: rollback_required=True", r.rollback_required)

# 2.11 Rollback OK with snapshot
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="delete_product", provider="iap",
    has_rollback=True, rollback_snapshot_id="snap_001",
))
check("delete_product_with_rollback: allowed", r.is_allowed)

# 2.12 Past evidence blocks
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="add_waterfall_network", provider="max",
    past_evidence=[
        {"success": False, "revenue_impact": -8.0},
        {"success": False, "revenue_impact": -3.0},
    ],
    has_rollback=True,
))
check("past_failures: needs confirmation", r.needs_confirmation)
check("past_failures: warns about similar failures", "past" in " ".join(r.warnings).lower() or "fail" in " ".join(r.warnings).lower())

# 2.13 Past evidence all good → no warning
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="add_waterfall_network", provider="max",
    past_evidence=[
        {"success": True, "revenue_impact": 5.0},
        {"success": True, "revenue_impact": 3.0},
    ],
    has_rollback=True,
))
check("past_success: allowed", r.is_allowed)

# 2.14 Combined: revenue + retention both OK
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="optimize_waterfall", provider="max",
    expected_impact={"revenue_change_pct": 8.0, "retention_change_pct": 1.0},
    has_rollback=True,
))
check("combined_safe: allowed", r.is_allowed)

# 2.15 Combined: revenue OK but retention bad
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="increase_frequency", provider="max",
    expected_impact={"revenue_change_pct": 5.0, "retention_change_pct": -9.0},
))
check("combined_retention_bad: blocked", r.is_blocked)

# 2.16 No expected impact → safe by default
r = engine.evaluate(SafetyCheck(
    game_id="game_01", operation="check_status", provider="max",
))
check("no_impact: allowed", r.is_allowed)


# =========================================================================== #
# Part 3: Integration — Memory + Safety (4 cases)
# =========================================================================== #
print("\n=== E15.2.1+E15.2.2 Integration ===")

# Reuse memory from Part 1
safety = SafetyAgent(engine=engine, memory_agent=agent)

# 3.1 Safe operation with memory evidence
result = safety.check(
    game_id="game_01",
    operation="raise_bid_floor",
    provider="max",
    changes={"country": "US", "platform": "android", "format": "reward", "floor": 38, "old_floor": 35},
    current_metrics={"ecpm": 13.8, "retention_d1": 0.38},
    expected_impact={"revenue_change_pct": 5.0},
    has_rollback=True,
)
check("integration: safe with memory → allowed", result.is_allowed)

# 3.2 Risky operation with memory failure evidence
result = safety.check(
    game_id="game_03",
    operation="lower_bid_floor",
    provider="max",
    changes={"country": "KR"},
    expected_impact={"revenue_change_pct": -15.0},
)
check("integration: risky+failure_memory → blocked", result.is_blocked)

# 3.3 Memory agent records + safety agent checks roundtrip
mem_check = safety.check(
    game_id="game_01",
    operation="add_waterfall_network",
    provider="max",
    changes={"country": "US", "network": "test_net"},
    expected_impact={"revenue_change_pct": 2.0},
    has_rollback=True,
)
check("integration: roundtrip allowed", mem_check.is_allowed)

# 3.4 Operation record to_dict / from_dict roundtrip
d = rec1.to_dict()
rec_rt = OperationRecord.from_dict(d)
check("to_dict_from_dict roundtrip", rec_rt.record_id == rec1.record_id)
check("roundtrip preserves confidence", rec_rt.confidence == rec1.confidence)
check("roundtrip preserves tags", rec_rt.tags == rec1.tags)


# =========================================================================== #
# Results
# =========================================================================== #
print(f"\n{'='*50}")
print(f"  TOTAL: {TOTAL}  |  PASS: {PASS}  |  FAIL: {FAIL}")
if FAIL == 0:
    print("  MEMORY + SAFETY READY")
else:
    print(f"  {FAIL} FAILURES — review above")
print(f"{'='*50}")

# Clean up
import shutil
shutil.rmtree(tmpdir, ignore_errors=True)

sys.exit(0 if FAIL == 0 else 1)
