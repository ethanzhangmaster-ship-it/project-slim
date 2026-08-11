"""E11.6.4 — IAP Fitness Calibration Test.

10 AC covering:
  1.  RevenueFitnessProfile Schema
  2.  LTV 计算
  3.  IAP + IAA 合并
  4.  ROAS 计算
  5.  Retention 评分
  6.  Fitness 权重
  7.  Cold Start 保护
  8.  Confidence Factor
  9.  Selection Integration
  10. Deterministic
"""

from __future__ import annotations

import copy
import pytest

from market_ops.e11.reality import (
    GenomeAttributionResult,
    RevenueFitnessProfile,
    CalibratedFitness,
    FitnessWeights,
    RevenueFitnessCalculator,
    FitnessCalibrator,
)
from market_ops.e11.reality.fitness.fitness_calibration_schema import (
    ROASProfile,
    RetentionProfile,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_attr_result(
    genome_id: str = "genome_001",
    total_users: int = 1000,
    total_revenue: float = 5000.0,
    iap_revenue: float = 4000.0,
    ad_revenue: float = 1000.0,
    d30_ltv: float = 5.0,
    payer_rate: float = 0.05,
    attribution_score: float = 0.80,
) -> GenomeAttributionResult:
    return GenomeAttributionResult(
        genome_id=genome_id,
        creatives=[f"creative_{genome_id}_1"],
        total_users=total_users,
        total_revenue=total_revenue,
        iap_revenue=iap_revenue,
        ad_revenue=ad_revenue,
        d30_ltv=d30_ltv,
        payer_rate=payer_rate,
        attribution_score=attribution_score,
    )


# ═══════════════════════════════════════════════════════════
# AC1 — RevenueFitnessProfile Schema
# ═══════════════════════════════════════════════════════════

def test_ac1a_revenue_fitness_profile_create():
    """AC1a: RevenueFitnessProfile 默认创建。"""
    p = RevenueFitnessProfile()
    assert p.genome_id == ""
    assert p.revenue_fitness == 0.0
    assert p.iap_ltv == 0.0
    assert p.ad_ltv == 0.0
    assert p.total_ltv == 0.0
    assert not p.is_valid


def test_ac1b_revenue_fitness_profile_with_data():
    """AC1b: RevenueFitnessProfile 完整创建。"""
    p = RevenueFitnessProfile(
        genome_id="genome_A",
        creative_score=85.0,
        iap_ltv=3.2,
        ad_ltv=1.5,
        total_ltv=4.7,
        payer_rate=0.08,
        revenue_fitness=0.91,
        sample_size=1000,
    )
    assert p.genome_id == "genome_A"
    assert p.revenue_fitness == 0.91
    assert p.is_valid
    assert p.is_elite
    assert not p.is_cold_start


def test_ac1c_roas_profile():
    """AC1c: ROASProfile 创建与属性。"""
    r = ROASProfile(d7_roas=0.3, d30_roas=0.5, d120_roas=1.2)
    assert r.is_valid
    assert r.is_positive
    assert r.d7_roas == 0.3
    assert r.d30_roas == 0.5
    assert r.d120_roas == 1.2


def test_ac1d_roas_profile_invalid():
    """AC1d: ROASProfile 无数据时无效。"""
    r = ROASProfile()
    assert not r.is_valid
    assert not r.is_positive


def test_ac1e_retention_profile():
    """AC1e: RetentionProfile 创建与属性。"""
    r = RetentionProfile(d1=0.45, d7=0.20, d30=0.08)
    assert r.is_valid
    assert r.d1 == 0.45
    assert r.d7 == 0.20
    assert r.d30 == 0.08
    expected_wr = round(0.45 * 0.3 + 0.20 * 0.4 + 0.08 * 0.3, 4)
    assert r.weighted_retention == expected_wr


def test_ac1f_retention_profile_invalid():
    """AC1f: RetentionProfile 无数据时无效。"""
    r = RetentionProfile()
    assert not r.is_valid


def test_ac1g_calibrated_fitness_create():
    """AC1g: CalibratedFitness 创建。"""
    c = CalibratedFitness(
        genome_id="genome_X",
        evolution_fitness=0.75,
        revenue_fitness=0.40,
        final_fitness=0.72,
    )
    assert c.genome_id == "genome_X"
    assert c.is_valid
    assert c.is_strong
    assert not c.cold_start_adjusted


# ═══════════════════════════════════════════════════════════
# AC2 — LTV 计算
# ═══════════════════════════════════════════════════════════

def test_ac2a_ltv_from_attribution():
    """AC2a: 从 GenomeAttributionResult 计算 LTV。"""
    result = _make_attr_result(
        genome_id="g1",
        total_users=1000,
        iap_revenue=3000.0,
        ad_revenue=1500.0,
        d30_ltv=4.5,
    )
    # iap_ltv = 3000/1000 = 3.0, ad_ltv = 1500/1000 = 1.5
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.iap_ltv == 3.0
    assert profile.ad_ltv == 1.5
    assert profile.total_ltv == 4.5


def test_ac2b_ltv_single_user():
    """AC2b: 单用户 LTV。"""
    result = _make_attr_result(
        total_users=1, total_revenue=10.0, iap_revenue=10.0, d30_ltv=10.0,
    )
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.iap_ltv == 10.0


def test_ac2c_ltv_zero_users():
    """AC2c: 零用户时 LTV=0（收入也为 0）。"""
    result = _make_attr_result(
        total_users=0, total_revenue=0.0, iap_revenue=0.0, ad_revenue=0.0, d30_ltv=0.0,
    )
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.iap_ltv == 0.0
    assert profile.ad_ltv == 0.0


# ═══════════════════════════════════════════════════════════
# AC3 — IAP + IAA 合并
# ═══════════════════════════════════════════════════════════

def test_ac3a_iap_iaa_separate():
    """AC3a: IAP 和 IAA 收入分开记录。"""
    result = _make_attr_result(
        iap_revenue=8000.0, ad_revenue=2000.0,
        total_users=1000, d30_ltv=10.0,
    )
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.iap_ltv == 8.0
    assert profile.ad_ltv == 2.0
    assert profile.total_ltv == 10.0  # d30_ltv defined in attr


def test_ac3b_iap_only():
    """AC3b: 纯 IAP 收入。"""
    result = _make_attr_result(
        iap_revenue=5000.0, ad_revenue=0.0,
        total_users=1000,
    )
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.iap_ltv == 5.0
    assert profile.ad_ltv == 0.0


def test_ac3c_ad_only():
    """AC3c: 纯广告收入。"""
    result = _make_attr_result(
        iap_revenue=0.0, ad_revenue=3000.0,
        total_users=1000,
    )
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.iap_ltv == 0.0
    assert profile.ad_ltv == 3.0


# ═══════════════════════════════════════════════════════════
# AC4 — ROAS 计算
# ═══════════════════════════════════════════════════════════

def test_ac4a_roas_score_calculation():
    """AC4a: ROAS 评分计算。"""
    result = _make_attr_result()
    roas = ROASProfile(d7_roas=0.3, d30_roas=0.5, d120_roas=1.2)
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result, roas=roas)
    assert profile.roas_score > 0.0
    assert profile.roas_score <= 1.0


def test_ac4b_roas_high_performance():
    """AC4b: 高 ROAS 产生高 ROAS Score。"""
    result = _make_attr_result()
    roas_high = ROASProfile(d7_roas=1.0, d30_roas=1.5, d120_roas=2.0)
    roas_low = ROASProfile(d7_roas=0.1, d30_roas=0.2, d120_roas=0.3)
    calc = RevenueFitnessCalculator()
    p_high = calc.calculate(result, roas=roas_high)
    p_low = calc.calculate(result, roas=roas_low)
    assert p_high.roas_score > p_low.roas_score


def test_ac4c_roas_zero():
    """AC4c: ROAS=0 时评分=0。"""
    result = _make_attr_result()
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result, roas=ROASProfile())
    assert profile.roas_score == 0.0


def test_ac4d_roas_default():
    """AC4d: 不提供 ROAS 时默认使用零值。"""
    result = _make_attr_result()
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.roas_score == 0.0


# ═══════════════════════════════════════════════════════════
# AC5 — Retention 评分
# ═══════════════════════════════════════════════════════════

def test_ac5a_retention_score_calculation():
    """AC5a: 留存评分计算。"""
    result = _make_attr_result()
    retention = RetentionProfile(d1=0.45, d7=0.20, d30=0.08)
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result, retention=retention)
    assert profile.retention_score > 0.0
    assert profile.retention_score <= 1.0


def test_ac5b_retention_high_vs_low():
    """AC5b: 高留存产生更高评分。"""
    result = _make_attr_result()
    ret_high = RetentionProfile(d1=0.60, d7=0.30, d30=0.15)
    ret_low = RetentionProfile(d1=0.20, d7=0.05, d30=0.01)
    calc = RevenueFitnessCalculator()
    p_high = calc.calculate(result, retention=ret_high)
    p_low = calc.calculate(result, retention=ret_low)
    assert p_high.retention_score > p_low.retention_score


def test_ac5c_retention_zero():
    """AC5c: 留存=0 时评分=0。"""
    result = _make_attr_result()
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result, retention=RetentionProfile())
    assert profile.retention_score == 0.0


# ═══════════════════════════════════════════════════════════
# AC6 — Fitness 权重
# ═══════════════════════════════════════════════════════════

def test_ac6a_default_weights():
    """AC6a: 默认权重配置。"""
    w = FitnessWeights()
    assert w.revenue == 0.35
    assert w.roas == 0.25
    assert w.retention == 0.20
    assert w.payer_rate == 0.10
    assert w.creative_quality == 0.10


def test_ac6b_custom_weights():
    """AC6b: 自定义权重。"""
    w = FitnessWeights(revenue=0.40, roas=0.20, retention=0.15, payer_rate=0.15, creative_quality=0.10)
    assert w.revenue == 0.40
    assert w.roas == 0.20


def test_ac6c_weights_auto_normalize():
    """AC6c: 权重自动归一化。"""
    w = FitnessWeights(revenue=0.7, roas=0.5, retention=0.4, payer_rate=0.2, creative_quality=0.2)
    total = w.revenue + w.roas + w.retention + w.payer_rate + w.creative_quality
    assert abs(total - 1.0) < 0.01


def test_ac6d_weighted_fitness_formula():
    """AC6d: 加权公式正确。"""
    result = _make_attr_result(
        d30_ltv=10.0, payer_rate=0.10, total_users=1000,
    )
    roas = ROASProfile(d7_roas=1.0, d30_roas=1.5, d120_roas=2.0)
    retention = RetentionProfile(d1=0.60, d7=0.30, d30=0.15)
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result, roas=roas, retention=retention, creative_score=90.0)

    w = calc.weights
    expected = (
        profile.revenue_score * w.revenue
        + profile.roas_score * w.roas
        + profile.retention_score * w.retention
        + profile.payer_rate_score * w.payer_rate
        + 0.0  # creative_quality_score * w.creative_quality — but creative_score is 90, so 0.9
    )
    # recalculate with creative_quality
    expected = round(
        profile.revenue_score * w.revenue
        + profile.roas_score * w.roas
        + profile.retention_score * w.retention
        + profile.payer_rate_score * w.payer_rate
        + (90.0 / 100.0) * w.creative_quality,
        4,
    )
    assert profile.revenue_fitness == expected


def test_ac6e_custom_weights_affect_fitness():
    """AC6e: 自定义权重影响 fitness 结果。"""
    result = _make_attr_result(d30_ltv=10.0, payer_rate=0.10)
    calc_default = RevenueFitnessCalculator()
    calc_custom = RevenueFitnessCalculator(
        weights=FitnessWeights(revenue=0.50, roas=0.10, retention=0.10, payer_rate=0.20, creative_quality=0.10),
    )
    p_default = calc_default.calculate(result)
    p_custom = calc_custom.calculate(result)
    # 不同权重产生不同结果
    assert p_default.revenue_fitness != p_custom.revenue_fitness


# ═══════════════════════════════════════════════════════════
# AC7 — Cold Start 保护
# ═══════════════════════════════════════════════════════════

def test_ac7a_cold_start_detection():
    """AC7a: 冷启动检测（样本量 < 100）。"""
    p = RevenueFitnessProfile(sample_size=50)
    assert p.is_cold_start
    p2 = RevenueFitnessProfile(sample_size=100)
    assert not p2.is_cold_start


def test_ac7b_cold_start_calibration():
    """AC7b: 冷启动时 Evolution 权重增加。"""
    profile = RevenueFitnessProfile(
        genome_id="new_genome",
        revenue_fitness=0.90,
        sample_size=10,
        confidence=0.1,
    )
    calibrator = FitnessCalibrator()
    calibrated = calibrator.calibrate(evolution_fitness=0.80, revenue_profile=profile)
    assert calibrated.cold_start_adjusted
    # 冷启动下 evolution_weight 应该 > 0.6
    assert calibrated.evolution_weight > 0.6


def test_ac7c_cold_start_low_revenue_weight():
    """AC7c: 冷启动时 Revenue 权重降低。"""
    profile = RevenueFitnessProfile(
        genome_id="new_genome",
        revenue_fitness=0.90,
        sample_size=10,
    )
    calibrator = FitnessCalibrator()
    calibrated = calibrator.calibrate(evolution_fitness=0.80, revenue_profile=profile)
    assert calibrated.revenue_weight < 0.4


def test_ac7d_non_cold_start_normal():
    """AC7d: 非冷启动时使用正常权重。"""
    profile = RevenueFitnessProfile(
        genome_id="mature_genome",
        revenue_fitness=0.70,
        sample_size=1000,
    )
    calibrator = FitnessCalibrator()
    calibrated = calibrator.calibrate(evolution_fitness=0.75, revenue_profile=profile)
    assert not calibrated.cold_start_adjusted
    assert calibrated.evolution_weight == 0.6
    assert calibrated.revenue_weight == 0.4


def test_ac7e_cold_start_new_genome_not_eliminated():
    """AC7e: 冷启动新 Genome 不会被 Revenue 直接淘汰。"""
    # 新 Genome：高 Evolution 低 Revenue
    new_profile = RevenueFitnessProfile(
        genome_id="new_genome",
        revenue_fitness=0.20,
        sample_size=20,
    )
    # 老 Genome：高 Revenue
    old_profile = RevenueFitnessProfile(
        genome_id="old_genome",
        revenue_fitness=0.90,
        sample_size=5000,
    )
    calibrator = FitnessCalibrator()
    new_cal = calibrator.calibrate(evolution_fitness=0.85, revenue_profile=new_profile)
    old_cal = calibrator.calibrate(evolution_fitness=0.60, revenue_profile=old_profile)

    # 新 Genome 的 final_fitness 应该有被保护
    # Evolution 高（0.85）应该被保留
    assert new_cal.final_fitness > 0.5  # 不会被直接淘汰


# ═══════════════════════════════════════════════════════════
# AC8 — Confidence Factor
# ═══════════════════════════════════════════════════════════

def test_ac8a_confidence_increases_with_samples():
    """AC8a: 样本量越大，置信度越高。"""
    from market_ops.e11.reality.fitness.fitness_weights import calc_confidence_factor
    c10 = calc_confidence_factor(10)
    c100 = calc_confidence_factor(100)
    c1000 = calc_confidence_factor(1000)
    assert c10 < c100 < c1000


def test_ac8b_confidence_zero_samples():
    """AC8b: 零样本置信度为 0。"""
    from market_ops.e11.reality.fitness.fitness_weights import calc_confidence_factor
    assert calc_confidence_factor(0) == 0.0


def test_ac8c_confidence_approaches_one():
    """AC8c: 大样本量置信度趋近 1.0。"""
    from market_ops.e11.reality.fitness.fitness_weights import calc_confidence_factor
    c = calc_confidence_factor(10000)
    assert c > 0.99


def test_ac8d_confidence_in_profile():
    """AC8d: RevenueFitnessProfile 包含置信度。"""
    result = _make_attr_result(total_users=500)
    calc = RevenueFitnessCalculator()
    profile = calc.calculate(result)
    assert profile.confidence > 0.0
    assert profile.sample_size == 500


# ═══════════════════════════════════════════════════════════
# AC9 — Selection Integration
# ═══════════════════════════════════════════════════════════

def test_ac9a_rank_by_calibrated_fitness():
    """AC9a: 按 CalibratedFitness 排名。"""
    c1 = CalibratedFitness(genome_id="A", final_fitness=0.40)
    c2 = CalibratedFitness(genome_id="B", final_fitness=0.90)
    c3 = CalibratedFitness(genome_id="C", final_fitness=0.70)
    calibrator = FitnessCalibrator()
    ranked = calibrator.rank_by_calibrated_fitness([c1, c2, c3])
    assert ranked[0].genome_id == "B"
    assert ranked[1].genome_id == "C"
    assert ranked[2].genome_id == "A"


def test_ac9b_revenue_wins_over_creative():
    """AC9b: 商业价值优先于创意评分。"""
    # Genome A: 创意好但赚钱差
    # Genome B: 创意一般但赚钱好
    profile_a = RevenueFitnessProfile(
        genome_id="A", creative_score=90, revenue_fitness=0.40, sample_size=1000,
    )
    profile_b = RevenueFitnessProfile(
        genome_id="B", creative_score=75, revenue_fitness=0.90, sample_size=1000,
    )
    calibrator = FitnessCalibrator()
    cal_a = calibrator.calibrate(evolution_fitness=0.90, revenue_profile=profile_a)
    cal_b = calibrator.calibrate(evolution_fitness=0.75, revenue_profile=profile_b)
    # B 应该赢，因为商业价值更高
    assert cal_b.final_fitness > cal_a.final_fitness


def test_ac9c_select_candidates():
    """AC9c: 按 Elite/Threshold/Diversity 选择。"""
    profiles = [
        RevenueFitnessProfile(genome_id=f"g{i}", revenue_fitness=0.9 - i * 0.1, sample_size=1000)
        for i in range(10)
    ]
    calibrator = FitnessCalibrator()
    calibrated = [
        calibrator.calibrate(evolution_fitness=0.8 - i * 0.05, revenue_profile=p)
        for i, p in enumerate(profiles)
    ]
    result = calibrator.select_candidates(calibrated, elite_count=3, threshold_count=3)
    assert len(result["elite"]) == 3
    assert len(result["threshold"]) <= 3


def test_ac9d_get_elite():
    """AC9d: 获取精英校准。"""
    c1 = CalibratedFitness(genome_id="g1", final_fitness=0.90)
    c2 = CalibratedFitness(genome_id="g2", final_fitness=0.50)
    c3 = CalibratedFitness(genome_id="g3", final_fitness=0.86)
    calibrator = FitnessCalibrator()
    elite = calibrator.get_elite_calibrated([c1, c2, c3])
    assert len(elite) == 2


def test_ac9e_get_weak():
    """AC9e: 获取弱者校准。"""
    c1 = CalibratedFitness(genome_id="g1", final_fitness=0.30)
    c2 = CalibratedFitness(genome_id="g2", final_fitness=0.90)
    c3 = CalibratedFitness(genome_id="g3", final_fitness=0.20)
    calibrator = FitnessCalibrator()
    weak = calibrator.get_weak_calibrated([c1, c2, c3])
    assert len(weak) == 2


def test_ac9f_rank_by_revenue_fitness():
    """AC9f: 按 revenue_fitness 排名。"""
    p1 = RevenueFitnessProfile(genome_id="A", revenue_fitness=0.30)
    p2 = RevenueFitnessProfile(genome_id="B", revenue_fitness=0.90)
    p3 = RevenueFitnessProfile(genome_id="C", revenue_fitness=0.60)
    calc = RevenueFitnessCalculator()
    ranked = calc.rank_by_revenue_fitness([p1, p2, p3])
    assert ranked[0].genome_id == "B"
    assert ranked[-1].genome_id == "A"


def test_ac9g_batch_calibrate():
    """AC9g: 批量校准。"""
    profiles = [
        RevenueFitnessProfile(genome_id="g1", revenue_fitness=0.80, sample_size=1000),
        RevenueFitnessProfile(genome_id="g2", revenue_fitness=0.50, sample_size=1000),
    ]
    fitness_map = {"g1": 0.85, "g2": 0.70}
    calibrator = FitnessCalibrator()
    calibrated = calibrator.calibrate_batch(fitness_map, profiles)
    assert len(calibrated) == 2
    assert calibrated[0].genome_id == "g1"


# ═══════════════════════════════════════════════════════════
# AC10 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac10a_deterministic_calculation():
    """AC10a: 相同输入产生相同 RevenueFitnessProfile。"""
    result = _make_attr_result()
    calc = RevenueFitnessCalculator()
    p1 = calc.calculate(result)
    p2 = calc.calculate(result)
    assert p1.revenue_fitness == p2.revenue_fitness
    assert p1.revenue_score == p2.revenue_score
    assert p1.roas_score == p2.roas_score


def test_ac10b_deterministic_calibration():
    """AC10b: 相同输入产生相同 CalibratedFitness。"""
    profile = RevenueFitnessProfile(
        genome_id="g1", revenue_fitness=0.70, sample_size=1000,
    )
    calibrator = FitnessCalibrator()
    c1 = calibrator.calibrate(evolution_fitness=0.80, revenue_profile=profile)
    c2 = calibrator.calibrate(evolution_fitness=0.80, revenue_profile=profile)
    assert c1.final_fitness == c2.final_fitness


def test_ac10c_deterministic_weights():
    """AC10c: 相同权重产生相同结果。"""
    calc1 = RevenueFitnessCalculator()
    calc2 = RevenueFitnessCalculator()
    result = _make_attr_result()
    assert calc1.calculate(result).revenue_fitness == calc2.calculate(result).revenue_fitness


def test_ac10d_deterministic_confidence():
    """AC10d: 相同样本量产生相同置信度。"""
    from market_ops.e11.reality.fitness.fitness_weights import calc_confidence_factor
    c1 = calc_confidence_factor(500)
    c2 = calc_confidence_factor(500)
    assert c1 == c2


def test_ac10e_deterministic_batch():
    """AC10e: 相同输入批量计算产生相同结果。"""
    results = [
        _make_attr_result(genome_id="g1", d30_ltv=5.0),
        _make_attr_result(genome_id="g2", d30_ltv=3.0),
    ]
    calc = RevenueFitnessCalculator()
    batch1 = calc.calculate_batch(results)
    batch2 = calc.calculate_batch(copy.deepcopy(results))
    for p1, p2 in zip(batch1, batch2):
        assert p1.revenue_fitness == p2.revenue_fitness


# ═══════════════════════════════════════════════════════════
# 额外测试 — Serialization
# ═══════════════════════════════════════════════════════════

def test_serialization_revenue_fitness_profile_roundtrip():
    """RevenueFitnessProfile 序列化往返。"""
    original = RevenueFitnessProfile(
        genome_id="genome_test",
        creative_score=88.0,
        iap_ltv=3.5,
        ad_ltv=1.2,
        total_ltv=4.7,
        payer_rate=0.07,
        revenue_fitness=0.88,
        revenue_score=0.70,
        roas_score=0.65,
        retention_score=0.55,
        payer_rate_score=0.60,
        confidence=0.95,
        sample_size=2000,
        roas=ROASProfile(d7_roas=0.4, d30_roas=0.8, d120_roas=1.5),
        retention=RetentionProfile(d1=0.50, d7=0.25, d30=0.10),
    )
    restored = RevenueFitnessProfile.from_dict(original.to_dict())
    assert restored.genome_id == original.genome_id
    assert restored.revenue_fitness == original.revenue_fitness
    assert restored.total_ltv == original.total_ltv
    assert restored.roas.d30_roas == original.roas.d30_roas
    assert restored.retention.d7 == original.retention.d7


def test_serialization_calibrated_fitness_roundtrip():
    """CalibratedFitness 序列化往返。"""
    original = CalibratedFitness(
        genome_id="g_serial",
        evolution_fitness=0.82,
        revenue_fitness=0.65,
        final_fitness=0.75,
        cold_start_adjusted=True,
        evolution_weight=0.80,
        revenue_weight=0.20,
        confidence=0.30,
        sample_size=50,
    )
    restored = CalibratedFitness.from_dict(original.to_dict())
    assert restored.genome_id == original.genome_id
    assert restored.final_fitness == original.final_fitness
    assert restored.cold_start_adjusted == original.cold_start_adjusted
    assert restored.evolution_weight == original.evolution_weight


def test_serialization_fitness_weights_roundtrip():
    """FitnessWeights 序列化往返。"""
    original = FitnessWeights(revenue=0.40, roas=0.20, retention=0.15, payer_rate=0.15, creative_quality=0.10)
    restored = FitnessWeights.from_dict(original.to_dict())
    assert restored.revenue == original.revenue
    assert restored.roas == original.roas
    assert restored.retention == original.retention


def test_serialization_calibrator_roundtrip():
    """FitnessCalibrator 序列化往返。"""
    original = FitnessCalibrator(evolution_weight=0.55, revenue_weight=0.45, cold_start_threshold=150)
    restored = FitnessCalibrator.from_dict(original.to_dict())
    assert restored.evolution_weight == original.evolution_weight
    assert restored.revenue_weight == original.revenue_weight
    assert restored.cold_start_threshold == original.cold_start_threshold


# ═══════════════════════════════════════════════════════════
# 额外测试 — Dominant Dimension & Repr
# ═══════════════════════════════════════════════════════════

def test_dominant_dimension():
    """dominant_dimension 返回最高分维度。"""
    p = RevenueFitnessProfile(
        revenue_score=0.80, roas_score=0.50,
        retention_score=0.60, payer_rate_score=0.40,
    )
    assert p.dominant_dimension() == "revenue"


def test_repr():
    """所有核心类型的 repr 可正常输出。"""
    assert "RevenueFitnessProfile" in repr(RevenueFitnessProfile(genome_id="g1"))
    assert "CalibratedFitness" in repr(CalibratedFitness(genome_id="g1"))
    assert "RevenueFitnessCalculator" in repr(RevenueFitnessCalculator())
    assert "FitnessCalibrator" in repr(FitnessCalibrator())
    assert "FitnessWeights" in repr(FitnessWeights())
    assert "ROASProfile" in repr(ROASProfile())
    assert "RetentionProfile" in repr(RetentionProfile())


def test_cold_start_threshold_configurable():
    """冷启动阈值可配置。"""
    calibrator = FitnessCalibrator(cold_start_threshold=200)
    assert calibrator.is_cold_start(150)
    assert not calibrator.is_cold_start(200)


def test_revenue_contribution():
    """revenue_contribution 计算 Revenue 贡献占比。"""
    c = CalibratedFitness(
        genome_id="g1",
        evolution_fitness=0.70,
        revenue_fitness=0.80,
        final_fitness=0.74,
        revenue_weight=0.4,
    )
    # 0.80 * 0.4 / 0.74 ≈ 0.4324
    assert c.revenue_contribution > 0.0
    assert c.revenue_contribution <= 1.0


def test_calculate_batch_with_maps():
    """calculate_batch 支持 ROAS/Retention 映射。"""
    results = [
        _make_attr_result(genome_id="g1", d30_ltv=5.0),
        _make_attr_result(genome_id="g2", d30_ltv=3.0),
    ]
    roas_map = {"g1": ROASProfile(d30_roas=1.5), "g2": ROASProfile(d30_roas=0.5)}
    calc = RevenueFitnessCalculator()
    profiles = calc.calculate_batch(results, roas_map=roas_map)
    assert len(profiles) == 2
    # g1 has higher ROAS
    assert profiles[0].roas_score > 0.0


def test_get_top_profiles():
    """get_top_profiles 返回前 N 个。"""
    calc = RevenueFitnessCalculator()
    profiles = [
        RevenueFitnessProfile(genome_id="A", revenue_fitness=0.30),
        RevenueFitnessProfile(genome_id="B", revenue_fitness=0.90),
        RevenueFitnessProfile(genome_id="C", revenue_fitness=0.60),
    ]
    top = calc.get_top_profiles(profiles, top_n=2)
    assert len(top) == 2
    assert top[0].genome_id == "B"


def test_get_cold_start_profiles():
    """get_cold_start_profiles 返回冷启动 Profile。"""
    calc = RevenueFitnessCalculator()
    profiles = [
        RevenueFitnessProfile(genome_id="A", sample_size=1000),
        RevenueFitnessProfile(genome_id="B", sample_size=50),
        RevenueFitnessProfile(genome_id="C", sample_size=30),
    ]
    cold = calc.get_cold_start_profiles(profiles)
    assert len(cold) == 2
    assert cold[0].genome_id == "B"


def test_is_cold_start_false():
    """is_cold_start 检测阈值。"""
    calibrator = FitnessCalibrator()
    assert calibrator.is_cold_start(50)
    assert not calibrator.is_cold_start(100)