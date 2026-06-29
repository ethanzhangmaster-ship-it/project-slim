from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_ops.causal_learning import (
    CausalLearningBuilder,
    _causal_state,
    _missing_evidence,
    _confidence,
    _target_key,
    _canonical_pattern_family,
    _best_learning_match,
    _learning_pattern,
    _pattern_family,
    _structure_context_from_learning,
    _structure_signature_from_learning,
    _index_decisions,
    _index_learning_records,
    _next_validation_action,
)


class TestCausalState:
    def test_validated(self):
        assert _causal_state({"success": True}) == "validated"

    def test_invalidated(self):
        assert _causal_state({"success": False}) == "invalidated"

    def test_needs_execution_confirmation(self):
        assert _causal_state({"learning_state": "needs_execution_confirmation"}) == "needs_execution_confirmation"

    def test_pending_outcome(self):
        assert _causal_state({}) == "pending_outcome"


class TestMissingEvidence:
    def test_all_missing(self):
        experiment = {}
        decision = {}
        learning = {}
        missing = _missing_evidence(experiment, decision, learning, "pending_outcome")
        assert "success_metrics" in missing
        assert "rollback_metrics" in missing

    def test_execution_confirmation(self):
        missing = _missing_evidence({}, {}, {}, "needs_execution_confirmation")
        assert "execution_confirmation" in missing

    def test_validated_no_missing(self):
        experiment = {"success_metrics": ["roi"], "rollback_metrics": ["roi"]}
        learning = {"actual_signal": "good"}
        missing = _missing_evidence(experiment, {}, learning, "validated")
        # With source not in local_winner_prior/discovery_backlog and no decision,
        # linked_decision_evidence might appear
        # But success_metrics and rollback_metrics are present
        assert "success_metrics" not in missing
        assert "rollback_metrics" not in missing


class TestConfidence:
    def test_validated_high(self):
        result = _confidence("validated", {}, {"actual_signal": "good"}, {})
        assert result == "high"

    def test_medium_decision_confidence(self):
        result = _confidence("pending_outcome", {"confidence": 0.8}, {}, {"success_metrics": ["r"], "rollback_metrics": ["r"]})
        assert result == "medium"

    def test_low(self):
        result = _confidence("pending_outcome", {}, {}, {})
        assert result == "low"


class TestTargetKey:
    def test_basic(self):
        assert _target_key("P04 / iOS / Facebook") == "P04 / iOS / Facebook"

    def test_whitespace(self):
        assert _target_key(" P04  /  iOS ") == "P04 / iOS"

    def test_empty(self):
        assert _target_key("") == ""


class TestCanonicalPatternFamily:
    def test_winner_hook_clone(self):
        assert _canonical_pattern_family("winner_hook_clone_test") == "winner_hook_clone"

    def test_image_to_motion(self):
        assert _canonical_pattern_family("winner_image_to_motion_test") == "winner_image_to_motion"

    def test_unknown(self):
        assert _canonical_pattern_family("something_else") == "something_else"

    def test_empty(self):
        assert _canonical_pattern_family("") == ""


class TestBestLearningMatch:
    def test_direct_match(self):
        index = {"p04 / ios / facebook": {"data": "match"}}
        result = _best_learning_match("P04 / iOS / Facebook", index)
        assert result == {"data": "match"}

    def test_partial_match(self):
        index = {"some_p04_facebook_key": {"data": "partial"}}
        result = _best_learning_match("P04 / iOS / Facebook", index)
        assert result == {"data": "partial"}

    def test_no_match(self):
        result = _best_learning_match("P04 / iOS / Facebook", {})
        assert result == {}


class TestLearningPattern:
    def test_from_learning(self):
        learning = {
            "test_type": "winner_hook_clone_test",
            "post_metrics": {
                "winner_variant_type": "cta",
                "baseline_asset_type": "video",
                "winner_baseline_asset": "asset_001",
                "learning_note": "good",
                "post_action_ctr": "0.05",
                "post_action_cpi": "2.0",
                "created_variant_count": "5",
            },
        }
        experiment = {"creative_name": "fallback"}
        result = _learning_pattern(experiment, learning)
        assert result["pattern_family"] == "winner_hook_clone"
        assert result["variant_type"] == "cta"
        assert result["baseline_asset"] == "asset_001"

    def test_fallback_from_experiment(self):
        learning = {}
        experiment = {"hypothesis": "test", "creative_name": "cr_001"}
        result = _learning_pattern(experiment, learning)
        assert result["baseline_asset"] == "cr_001"


class TestPatternFamily:
    def test_image_to_motion(self):
        assert _pattern_family({"hypothesis": "image to motion test"}) == "winner_image_to_motion"
        assert _pattern_family({"hypothesis": "动效测试"}) == "winner_image_to_motion"

    def test_default_hook_clone(self):
        assert _pattern_family({"hypothesis": ""}) == "winner_hook_clone"
        assert _pattern_family({"hypothesis": "something else"}) == "winner_hook_clone"


class TestStructureContext:
    def test_from_learning(self):
        learning = {
            "structure_context": {"asset_type": "video", "orientation": "vertical"}
        }
        result = _structure_context_from_learning(learning)
        assert result["asset_type"] == "video"
        assert result["orientation"] == "vertical"

    def test_from_post_metrics(self):
        learning = {
            "post_metrics": {
                "structure_context": {"asset_type": "image", "orientation": "horizontal"}
            },
        }
        result = _structure_context_from_learning(learning)
        assert result["asset_type"] == "image"
        assert result["orientation"] == "horizontal"

    def test_from_winner_bias(self):
        learning = {
            "baseline_asset_type": "image",
            "winner_structure_bias": [
                {"bias_type": "duration_bucket", "value": "15-30s"}
            ],
        }
        result = _structure_context_from_learning(learning)
        assert result["asset_type"] == "image"
        assert result["duration_bucket"] == "15-30s"

    def test_empty(self):
        result = _structure_context_from_learning({})
        assert result == {}


class TestStructureSignature:
    def test_direct(self):
        learning = {"structure_signature": "asset_type=video | orientation=horizontal"}
        result = _structure_signature_from_learning(learning)
        assert "asset_type=video" in result

    def test_from_context(self):
        learning = {
            "baseline_asset_type": "image",
            "winner_structure_bias": [
                {"bias_type": "orientation", "value": "vertical"},
                {"bias_type": "aspect_ratio", "value": "9:16"},
            ],
        }
        result = _structure_signature_from_learning(learning)
        assert "asset_type=image" in result
        assert "orientation=vertical" in result
        assert "aspect_ratio=9:16" in result

    def test_empty(self):
        result = _structure_signature_from_learning({})
        assert result == ""


class TestIndexDecisions:
    def test_basic(self):
        items = [
            {"entity_id": "p04", "project": "P04 Witch", "scope": "iOS / Facebook"},
        ]
        index = _index_decisions(items)
        assert "p04" in index
        assert index["p04"]["project"] == "P04 Witch"

    def test_combined_key(self):
        items = [
            {"entity_id": "cr_001", "project": "P04", "scope": "iOS / Facebook"},
        ]
        index = _index_decisions(items)
        assert "P04 / iOS / Facebook / cr_001" in index


class TestIndexLearningRecords:
    def test_by_target(self):
        items = [{"target": "P04 / iOS / Facebook"}]
        index = _index_learning_records(items)
        assert "P04 / iOS / Facebook" in index

    def test_by_action_id(self):
        items = [{"action_id": "act_001", "target": ""}]
        index = _index_learning_records(items)
        assert "act_001" in index


class TestNextValidationAction:
    def test_needs_execution(self):
        item = {
            "causal_state": "needs_execution_confirmation",
            "hypothesis_id": "cause_001",
            "experiment_id": "exp_001",
            "target": "P04",
            "missing_evidence": ["execution_confirmation"],
        }
        result = _next_validation_action(item)
        assert "Confirm whether" in result["required_update"]

    def test_pending(self):
        item = {
            "causal_state": "pending_outcome",
            "hypothesis_id": "cause_002",
            "experiment_id": "exp_002",
            "target": "P02",
            "missing_evidence": ["actual_result_note"],
        }
        result = _next_validation_action(item)
        assert "post-experiment outcome" in result["required_update"]
