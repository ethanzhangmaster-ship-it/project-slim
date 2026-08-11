from market_ops.product.evidence_adapter import from_decision_engine


def test_only_trusted_creative_actions_become_evidence():
    batch = from_decision_engine({"report_date": "2026-07-31", "items": [
        {"entity_type": "creative", "entity_id": "c-win", "decision": "small_scale_up", "confidence": 0.8, "spend": 100, "top_positive_signals": ["high roi"]},
        {"entity_type": "creative", "entity_id": "c-blocked", "decision": "data_blocked", "confidence": 0.9, "spend": 200},
        {"entity_type": "project", "entity_id": "p04", "decision": "small_scale_up", "confidence": 0.9, "spend": 300},
    ]})
    assert batch.total_budget == 100
    assert batch.results == [{"experiment_id": "decision-engine:2026-07-31:c-win", "creative_id": "c-win", "decision": "WINNER", "confidence": 0.8, "budget_before": 100.0, "reason": "high roi"}]
    assert {row["reason"] for row in batch.skipped} == {"decision_not_actionable:data_blocked", "not_a_creative"}
