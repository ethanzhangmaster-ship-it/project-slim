"""DiscoveryValidator 单元测试。

覆盖场景：
- test_confirmed: 正向效果显著 → verdict = confirmed
- test_rejected: 负向效果显著 → verdict = rejected
- test_inconclusive_small_sample: 样本量不足 → verdict = inconclusive
- test_inconclusive_weak_effect: 效果不显著 → verdict = inconclusive
- test_batch_validation: 批量验证 + 反馈生成
"""
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# 确保项目根路径可导入
import sys

_PROJ_ROOT = Path(__file__).resolve().parent.parent / "src"
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from market_ops.discovery_validator import (
    DiscoveryValidator,
    ValidationResult,
    ValidationReport,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


class _MockSettings:
    """最小化 Settings mock，兼容 active_output_dir 属性方法。"""

    def __init__(self, tmp_path: Path):
        self.output_dir = tmp_path

    @property
    def active_output_dir(self) -> Path:
        return self.output_dir / "active"


def _make_mock_settings(tmp_path: Path):
    return _MockSettings(tmp_path)


@pytest.fixture
def settings(tmp_path: Path):
    return _make_mock_settings(tmp_path)


@pytest.fixture
def validator(settings) -> DiscoveryValidator:
    return DiscoveryValidator(
        settings=settings,
        min_sample_size=100,
        confidence_threshold=0.95,
    )


# ------------------------------------------------------------------
# 测试 validate_experiment
# ------------------------------------------------------------------


class TestValidateExperiment:
    """单条实验结果验证。"""

    def test_confirmed(self, validator):
        """正向效果超过阈值 → confirmed。"""
        result = validator.validate_experiment({
            "id": "exp_001",
            "hypothesis_id": "hyp_crisis_hook",
            "impressions": 5000,
            "conversion_rate": 0.15,   # +0.10 vs baseline 0.05 → effect/baseline = 2.0 > 0.95
            "baseline_rate": 0.05,
        })
        assert result.verdict == "confirmed"
        assert result.experiment_id == "exp_001"
        assert result.hypothesis_id == "hyp_crisis_hook"
        assert result.confidence > validator.confidence_threshold
        assert result.sample_size == 5000
        assert result.effect_size > 0
        assert len(result.learnings) > 0
        assert any("scale" in a or "winning" in a for a in result.next_actions)

    def test_rejected(self, validator):
        """负向效果超过阈值 → rejected。"""
        result = validator.validate_experiment({
            "id": "exp_002",
            "hypothesis_id": "hyp_mismatch_country",
            "impressions": 3000,
            "conversion_rate": 0.002,  # -0.058 vs baseline 0.06 → |effect|/baseline = 0.967 > 0.95
            "baseline_rate": 0.06,
        })
        assert result.verdict == "rejected"
        assert result.effect_size < 0
        assert any("losing" in a or "counter" in a for a in result.next_actions)

    def test_inconclusive_small_sample(self, validator):
        """样本量低于最小阈值 → inconclusive。"""
        validator.min_sample_size = 500
        result = validator.validate_experiment({
            "id": "exp_003",
            "hypothesis_id": "hyp_early",
            "impressions": 50,
            "conversion_rate": 0.10,
            "baseline_rate": 0.03,
        })
        assert result.verdict == "inconclusive"
        assert "样本量不足" in result.learnings[0]
        assert result.sample_size == 50

    def test_inconclusive_weak_effect(self, validator):
        """效果量不够 → inconclusive。"""
        result = validator.validate_experiment({
            "id": "exp_004",
            "hypothesis_id": "hyp_borderline",
            "impressions": 2000,
            "conversion_rate": 0.052,  # +0.002 vs baseline
            "baseline_rate": 0.050,    # 效果量 0.002 / 0.05 = 0.04, 远低于 0.95
        })
        assert result.verdict == "inconclusive"
        assert result.confidence < validator.confidence_threshold
        assert result.effect_size > 0  # 正向但不显著

    def test_alternative_field_names(self, validator):
        """支持 ctr / baseline_ctr 和 sample_size 备选字段。"""
        result = validator.validate_experiment({
            "experiment_id": "exp_alt",
            "hypothesis_id": "hyp_alt",
            "sample_size": 500,
            "ctr": 0.20,         # +0.10 vs baseline 0.10 → effect/baseline = 1.0 > 0.95
            "baseline_ctr": 0.10,
        })
        assert result.verdict == "confirmed"
        assert result.experiment_id == "exp_alt"
        assert result.sample_size == 500


# ------------------------------------------------------------------
# 测试批量验证 + 反馈
# ------------------------------------------------------------------


class TestBatchValidation:
    """批量验证与反馈生成。"""

    def test_batch_and_feedback(self, validator):
        experiments = [
            {
                "id": "exp_a",
                "hypothesis_id": "h_a",
                "impressions": 5000,
                "conversion_rate": 0.15,   # +0.10 vs 0.05 → conf=2.0 ✓
                "baseline_rate": 0.05,
            },
            {
                "id": "exp_b",
                "hypothesis_id": "h_b",
                "impressions": 3000,
                "conversion_rate": 0.002,  # -0.058 vs 0.06 → conf=0.967 ✓
                "baseline_rate": 0.06,
            },
            {
                "id": "exp_c",
                "hypothesis_id": "h_c",
                "impressions": 50,
                "conversion_rate": 0.10,
                "baseline_rate": 0.03,
            },
        ]
        results = validator.validate_batch(experiments)
        assert len(results) == 3

        feedback = validator.generate_feedback_for_hypothesis_generator()
        assert feedback["cycle"] == 3
        assert 0.0 <= feedback["win_rate"] <= 1.0
        assert feedback["pending"] >= 0
        assert isinstance(feedback["suggested_next_batch"], str)
        assert len(feedback["validated_results"]) == 3

        # 确认至少有 1 个 confirmed
        confirmed = [r for r in results if r.verdict == "confirmed"]
        assert len(confirmed) >= 1
        # 确认至少有 1 个 rejected
        rejected = [r for r in results if r.verdict == "rejected"]
        assert len(rejected) >= 1
        # 确认至少有 1 个 inconclusive（样本量不足）
        inconclusive = [r for r in results if r.verdict == "inconclusive"]
        assert len(inconclusive) >= 1


# ------------------------------------------------------------------
# 测试 build() 完整闭环
# ------------------------------------------------------------------


class TestBuildReport:
    """测试 build() 完整流程：加载 → 验证 → 写入报告。"""

    def test_build_with_experiments(self, settings):
        """有实验数据 → 生成完整报告。"""
        output_dir = settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = date.today().strftime("%Y%m%d")

        # 写入模拟实验数据
        ingestion_json = output_dir / f"experiment_result_ingestion_{suffix}.json"
        ingestion_json.write_text(json.dumps({
            "result_rows": [
                {
                    "id": "exp_build_1",
                    "hypothesis_id": "hyp_test",
                    "impressions": 5000,
                    "conversion_rate": 0.15,   # +0.10 vs 0.05 → conf=2.0 ✓
                    "baseline_rate": 0.05,
                },
            ]
        }), encoding="utf-8")

        validator = DiscoveryValidator(settings=settings)
        report = validator.build(report_date=date.today())

        assert isinstance(report, ValidationReport)
        assert report.markdown_path.exists()
        assert report.json_path.exists()
        assert len(report.results) == 1
        assert report.results[0].verdict == "confirmed"
        assert report.passed is True
        assert "win_rate" in report.feedback

        # 验证反馈 JSON 也写入
        suffix = date.today().strftime("%Y%m%d")
        feedback_path = output_dir / f"discovery_validation_feedback_{suffix}.json"
        assert feedback_path.exists()

    def test_build_without_experiments(self, settings):
        """无实验数据 → 仍生成报告但所有结果 inconclusive。"""
        output_dir = settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = date.today().strftime("%Y%m%d")

        # 写入模拟假设（无实验数据）
        hyp_json = output_dir / f"hypothesis_plan_{suffix}.json"
        hyp_json.write_text(json.dumps({
            "hypotheses": [
                {"id": "hyp_empty_1", "hypothesis": "测试假设"},
                {"id": "hyp_empty_2", "hypothesis": "另一假设"},
            ]
        }), encoding="utf-8")

        validator = DiscoveryValidator(settings=settings)
        report = validator.build(report_date=date.today())

        assert len(report.results) == 2
        assert all(r.verdict == "inconclusive" for r in report.results)
        assert report.passed is False
        assert report.feedback["cycle"] == 2
        assert report.feedback["win_rate"] == 0.0


# ------------------------------------------------------------------
# 数据类型测试
# ------------------------------------------------------------------


class TestValidationResultDataclass:
    """ValidationResult 数据类完整性。"""

    def test_serialize(self):
        result = ValidationResult(
            experiment_id="e1",
            hypothesis_id="h1",
            verdict="confirmed",
            confidence=0.97,
            statistical_significance=0.95,
            sample_size=1000,
            effect_size=0.03,
            learnings=["正向效果"],
            next_actions=["scale"],
        )
        d = {
            "experiment_id": result.experiment_id,
            "hypothesis_id": result.hypothesis_id,
            "verdict": result.verdict,
            "confidence": result.confidence,
            "statistical_significance": result.statistical_significance,
            "sample_size": result.sample_size,
            "effect_size": result.effect_size,
            "learnings": result.learnings,
            "next_actions": result.next_actions,
        }
        assert d["verdict"] == "confirmed"
        assert d["confidence"] == 0.97
        assert len(d["learnings"]) == 1
        assert len(d["next_actions"]) == 1
