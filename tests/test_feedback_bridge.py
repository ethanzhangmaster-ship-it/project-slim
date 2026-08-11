"""验证 run_feedback_bridge.py 桥接脚本的端到端逻辑。

使用 mock 的 AdsPerformanceRow 数据模拟 Facebook Ads 返回，
验证 生成预测 → FeedbackController 评估 → ExperienceStore 写入 → 经验增强下一轮预测 的完整链路。
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from market_ops.creative_vision_runtime.reality.feedback import (
    FeedbackController,
)
from market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ContextDetail,
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceResult,
    ExperimentDetail,
    MutationDetail,
    MutationType,
)
from market_ops.creative_vision_runtime.reality.prediction.models import (
    PredictionType,
    RealityPrediction,
    RiskLevel,
)
from market_ops.models import AdsPerformanceRow

# 导入被测函数
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))
from run_feedback_bridge import (
    MemoryEnricher,
    aggregate_by_creative,
    generate_predictions,
    store_feedback_as_experience,
)


# ── 工厂函数 ──────────────────────────────────────────────


def _make_row(
    creative_id: str,
    spend: float,
    clicks: int,
    ctr: float,
    cpi: float,
    roas: float,
    day: date | None = None,
) -> AdsPerformanceRow:
    return AdsPerformanceRow(
        date=day or date.today(),
        game="P04",
        country="All",
        channel="Facebook",
        ad_id=f"ad_{creative_id}",
        creative_id=creative_id,
        spend=spend,
        clicks=clicks,
        ctr=ctr,
        cpi=cpi,
        roas=roas,
        retention_d1=0.0,
        retention_d7=0.0,
        retention_d30=0.0,
    )


# ── aggregate_by_creative 测试 ────────────────────────────


class TestAggregateByCreative:
    def test_basic_aggregation(self):
        """多条同 creative 的行应聚合为一条。"""
        rows = [
            _make_row("c1", spend=100, clicks=50, ctr=0.02, cpi=2.0, roas=0.5),
            _make_row("c1", spend=200, clicks=70, ctr=0.025, cpi=3.0, roas=0.6),
            _make_row("c2", spend=50, clicks=20, ctr=0.01, cpi=5.0, roas=0.2),
        ]
        result = aggregate_by_creative(rows)

        assert "c1" in result
        assert "c2" in result
        assert result["c1"]["spend"] == 300.0
        assert result["c1"]["clicks"] == 120
        # ctr 应为均值
        assert result["c1"]["ctr"] == pytest.approx(0.0225, abs=0.001)
        assert result["c2"]["spend"] == 50.0

    def test_derived_metrics(self):
        """验证 impressions/installs/revenue 的反推逻辑。"""
        rows = [
            _make_row("c1", spend=100, clicks=50, ctr=0.02, cpi=2.0, roas=0.5),
        ]
        result = aggregate_by_creative(rows)

        m = result["c1"]
        assert m["impressions"] == pytest.approx(2500.0)  # clicks/ctr = 50/0.02
        assert m["installs"] == pytest.approx(50.0)  # spend/cpi = 100/2.0
        assert m["revenue"] == pytest.approx(50.0)  # spend*roas = 100*0.5

    def test_empty_input(self):
        """空输入应返回空 dict。"""
        assert aggregate_by_creative([]) == {}


# ── generate_predictions 测试 ─────────────────────────────


class TestGeneratePredictions:
    def test_fatigue_detection(self):
        """CTR 下降 > 15% 应生成 CREATIVE_FATIGUE_RISK 预测。"""
        current = {
            "c1": {
                "spend": 100,
                "ctr": 0.015,
                "roas": 0.5,
                "clicks": 50,
                "impressions": 3000,
                "installs": 30,
                "revenue": 50,
                "cpi": 3.0,
            }
        }
        previous = {
            "c1": {
                "spend": 100,
                "ctr": 0.025,  # 下降了 40%
                "roas": 0.5,
                "clicks": 60,
                "impressions": 2400,
                "installs": 30,
                "revenue": 50,
                "cpi": 3.0,
            }
        }
        preds = generate_predictions(current, previous)
        fatigue_preds = [
            p for p in preds
            if p.prediction_type == PredictionType.CREATIVE_FATIGUE_RISK
            and p.probability > 0.1
        ]
        assert len(fatigue_preds) == 1
        assert fatigue_preds[0].risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert "MUTATE_HOOK" in fatigue_preds[0].recommended_action

    def test_roas_decay_detection(self):
        """ROAS 下降 > 20% 应生成 ROAS_DECAY_RISK 预测。"""
        current = {
            "c1": {
                "spend": 200,
                "ctr": 0.02,
                "roas": 0.40,
                "clicks": 50,
                "impressions": 2500,
                "installs": 30,
                "revenue": 80,
                "cpi": 6.0,
            }
        }
        previous = {
            "c1": {
                "spend": 200,
                "ctr": 0.02,
                "roas": 0.60,  # 下降了 33%
                "clicks": 50,
                "impressions": 2500,
                "installs": 30,
                "revenue": 120,
                "cpi": 6.0,
            }
        }
        preds = generate_predictions(current, previous)
        roas_preds = [
            p for p in preds
            if p.prediction_type == PredictionType.ROAS_DECAY_RISK
        ]
        assert len(roas_preds) == 1
        assert roas_preds[0].probability > 0.3

    def test_budget_burn_detection(self):
        """ROAS 极低 + 高花费 应生成 BUDGET_BURN_RISK 预测。"""
        current = {
            "c1": {
                "spend": 100,
                "ctr": 0.02,
                "roas": 0.10,  # 极低
                "clicks": 50,
                "impressions": 2500,
                "installs": 30,
                "revenue": 10,
                "cpi": 3.0,
            }
        }
        preds = generate_predictions(current, {})
        burn_preds = [
            p for p in preds
            if p.prediction_type == PredictionType.BUDGET_BURN_RISK
        ]
        assert len(burn_preds) == 1
        assert burn_preds[0].risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM)

    def test_scale_opportunity_detection(self):
        """ROAS 高 + CTR 稳定 应生成 SCALE_OPPORTUNITY 预测。"""
        current = {
            "c1": {
                "spend": 200,
                "ctr": 0.03,
                "roas": 0.80,
                "clicks": 80,
                "impressions": 2600,
                "installs": 50,
                "revenue": 160,
                "cpi": 4.0,
            }
        }
        previous = {
            "c1": {
                "spend": 200,
                "ctr": 0.031,  # 基本稳定
                "roas": 0.70,
                "clicks": 80,
                "impressions": 2600,
                "installs": 50,
                "revenue": 140,
                "cpi": 4.0,
            }
        }
        preds = generate_predictions(current, previous)
        scale_preds = [
            p for p in preds
            if p.prediction_type == PredictionType.SCALE_OPPORTUNITY
        ]
        assert len(scale_preds) == 1
        assert scale_preds[0].recommended_action == "INCREASE_BUDGET"

    def test_low_spend_skipped(self):
        """花费低于 MIN_SPEND 的创意应被跳过。"""
        current = {
            "c1": {
                "spend": 5.0,  # 低于 10
                "ctr": 0.02,
                "roas": 0.5,
                "clicks": 10,
                "impressions": 500,
                "installs": 5,
                "revenue": 2.5,
                "cpi": 1.0,
            }
        }
        preds = generate_predictions(current, {})
        assert len(preds) == 0

    def test_stable_creative_gets_data_collection(self):
        """无异常的创意应生成一个低概率 DATA_COLLECTION 型预测。"""
        current = {
            "c1": {
                "spend": 100,
                "ctr": 0.02,
                "roas": 0.45,
                "clicks": 50,
                "impressions": 2500,
                "installs": 30,
                "revenue": 45,
                "cpi": 3.0,
            }
        }
        previous = {
            "c1": {
                "spend": 100,
                "ctr": 0.02,  # 无变化
                "roas": 0.45,
                "clicks": 50,
                "impressions": 2500,
                "installs": 30,
                "revenue": 45,
                "cpi": 3.0,
            }
        }
        preds = generate_predictions(current, previous)
        assert len(preds) == 1
        assert preds[0].probability <= 0.15
        assert preds[0].risk_level == RiskLevel.LOW


# ── store_feedback_as_experience 测试 ─────────────────────


class TestStoreFeedbackAsExperience:
    def test_end_to_end_bridge(self):
        """完整链路: 预测 → FeedbackController → ExperienceStore。"""
        # 构造混合预测
        from market_ops.creative_vision_runtime.reality.prediction.models import (
            RealityPrediction,
        )

        predictions = [
            # 疲劳
            RealityPrediction(
                prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                target_id="c_fatigue",
                current_value=0.015,
                predicted_value=0.010,
                probability=0.85,
                risk_level=RiskLevel.HIGH,
                evidence=["CTR 0.025→0.015（-40%）"],
                recommended_action="MUTATE_HOOK",
                metadata={"confidence": 0.80, "metric": "ctr"},
            ),
            # 放量
            RealityPrediction(
                prediction_type=PredictionType.SCALE_OPPORTUNITY,
                target_id="c_scale",
                current_value=0.80,
                predicted_value=0.88,
                probability=0.80,
                risk_level=RiskLevel.LOW,
                evidence=["ROAS 0.80"],
                recommended_action="INCREASE_BUDGET",
                metadata={"confidence": 0.80, "metric": "roas"},
            ),
            # 平稳
            RealityPrediction(
                prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                target_id="c_stable",
                current_value=0.02,
                predicted_value=0.02,
                probability=0.1,
                risk_level=RiskLevel.LOW,
                evidence=["指标平稳"],
                recommended_action="CONTINUE_MONITORING",
                metadata={"confidence": 0.3, "metric": "none"},
            ),
        ]

        # FeedbackController 评估
        controller = FeedbackController()
        feedback = controller.evaluate(predictions)

        # 验证 FeedbackController 产出了信号
        assert len(feedback.signals) == 3
        assert len(feedback.triggered) >= 1  # 至少疲劳和放量应该被触发

        # 写入 ExperienceStore
        store = ExperienceStore()
        records_added = store_feedback_as_experience(
            predictions, feedback, store, product_id="P04"
        )

        assert records_added == 3
        assert len(store) == 3

        # 验证记录内容
        all_records = store.query_all()
        outcomes = [r.result.outcome for r in all_records]
        assert ExperienceOutcome.SUCCESS in outcomes  # 放量 → SUCCESS
        assert ExperienceOutcome.FAILURE in outcomes  # 疲劳 → FAILURE

        # 验证统计
        stats = store.get_stats()
        assert stats.total_records == 3
        assert stats.success_count >= 1

    def test_dry_run_does_not_write(self):
        """空预测列表不应写入任何记录。"""
        store = ExperienceStore()
        controller = FeedbackController()
        feedback = controller.evaluate([])

        records_added = store_feedback_as_experience(
            [], feedback, store
        )
        assert records_added == 0
        assert len(store) == 0


# ── 完整闭环冒烟测试 ──────────────────────────────────────


class TestFullClosedLoopSmoke:
    def test_mock_fb_data_through_full_pipeline(self):
        """用 mock AdsPerformanceRow 模拟 FB 数据，跑完整管线。"""
        # 当前周期: 1 个疲劳创意 + 1 个放量创意
        current_rows = [
            _make_row("c_fatigue", spend=200, clicks=30, ctr=0.012, cpi=5.0, roas=0.3),
            _make_row("c_scale", spend=150, clicks=60, ctr=0.03, cpi=3.0, roas=0.85),
        ]
        # 上一周期: 疲劳创意之前 CTR 更高
        previous_rows = [
            _make_row("c_fatigue", spend=200, clicks=60, ctr=0.028, cpi=4.0, roas=0.5),
            _make_row("c_scale", spend=150, clicks=55, ctr=0.031, cpi=3.0, roas=0.75),
        ]

        current_agg = aggregate_by_creative(current_rows)
        previous_agg = aggregate_by_creative(previous_rows)

        # 生成预测
        predictions = generate_predictions(current_agg, previous_agg)
        assert len(predictions) >= 2  # 至少 2 个创意有预测

        # FeedbackController
        controller = FeedbackController()
        feedback = controller.evaluate(predictions)
        assert len(feedback.signals) >= 2

        # ExperienceStore
        store = ExperienceStore()
        added = store_feedback_as_experience(
            predictions, feedback, store, product_id="P04"
        )
        assert added == len(predictions)
        assert len(store) == len(predictions)

        # 验证记忆中有成功和失败
        stats = store.get_stats()
        assert stats.total_records == len(predictions)
        # c_fatigue 应该是 FAILURE
        fatigue_records = [
            r for r in store.query_all()
            if r.creative_id == "c_fatigue"
        ]
        assert any(r.result.outcome == ExperienceOutcome.FAILURE for r in fatigue_records)


# ── 辅助函数: 构造 ExperienceRecord ──────────────────────


def _make_experience(
    creative_id: str,
    outcome: ExperienceOutcome,
    mutation_type: MutationType = MutationType.REFRESH_HOOK,
    improvement: float = 0.0,
    changed_genes: list[str] | None = None,
    product_id: str = "P04",
) -> ExperienceRecord:
    """快速构造一条 ExperienceRecord 用于填充 ExperienceStore。"""
    return ExperienceRecord(
        creative_id=creative_id,
        mutation=MutationDetail(
            mutation_type=mutation_type,
            changed_genes=changed_genes or ["hook"],
        ),
        experiment=ExperimentDetail(
            improvement=improvement,
            confidence=0.7,
        ),
        context=ContextDetail(
            product_id=product_id,
            platform="facebook",
        ),
        result=ExperienceResult(
            outcome=outcome,
            success=(outcome == ExperienceOutcome.SUCCESS),
            insight=f"测试记录: {outcome.value}",
        ),
    )


# ── MemoryEnricher 测试 ──────────────────────────────────


class TestMemoryEnricherCreativeHistory:
    """测试创意历史 — 连续失败升级。"""

    def test_repeated_failures_escalate_probability(self):
        """同一创意 2+ 次失败 → 概率提升 + 风险升级。"""
        store = ExperienceStore()
        # 填入 2 条失败记录
        store.add(_make_experience("c1", ExperienceOutcome.FAILURE))
        store.add(_make_experience("c1", ExperienceOutcome.FAILURE))

        enricher = MemoryEnricher(store)

        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c1",
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            evidence=["CTR 下降"],
            recommended_action="MUTATE_HOOK",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)

        # 概率应提升 (0.50 + 0.10*2 = 0.70)
        assert enriched.probability > 0.50
        # 风险应升级
        assert enriched.risk_level == RiskLevel.HIGH
        # evidence 应包含历史经验
        assert any("历史经验" in e for e in enriched.evidence)

    def test_no_history_no_escalation(self):
        """无历史记录的创意不应被升级。"""
        store = ExperienceStore()
        enricher = MemoryEnricher(store)

        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c_new",
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            evidence=["CTR 下降"],
            recommended_action="MUTATE_HOOK",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)
        assert enriched.probability == 0.50  # 不变
        assert enriched.risk_level == RiskLevel.MEDIUM  # 不变

    def test_single_failure_no_escalation(self):
        """仅 1 次失败不应触发升级（阈值 >= 2）。"""
        store = ExperienceStore()
        store.add(_make_experience("c1", ExperienceOutcome.FAILURE))

        enricher = MemoryEnricher(store)
        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c1",
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.LOW,
            evidence=["CTR 下降"],
            recommended_action="MUTATE_HOOK",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)
        assert enriched.probability == 0.50  # 不变
        assert enriched.risk_level == RiskLevel.LOW  # 不变


class TestMemoryEnricherMutationEffectiveness:
    """测试变异有效性 — 低效行动升级。"""

    def test_low_success_rate_escalates_action(self):
        """REFRESH_HOOK 成功率 < 30% → 升级为 ANALYZE_DNA_AND_MUTATE。"""
        store = ExperienceStore()
        # 4 次失败 + 1 次成功 = 20% 成功率
        for _ in range(4):
            store.add(_make_experience(
                "c1", ExperienceOutcome.FAILURE,
                mutation_type=MutationType.REFRESH_HOOK,
            ))
        store.add(_make_experience(
            "c1", ExperienceOutcome.SUCCESS,
            mutation_type=MutationType.REFRESH_HOOK,
        ))

        enricher = MemoryEnricher(store)

        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c_new",  # 不同创意，排除创意历史干扰
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            evidence=["CTR 下降"],
            recommended_action="MUTATE_HOOK",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)
        assert enriched.recommended_action == "ANALYZE_DNA_AND_MUTATE"
        assert any("REFRESH_HOOK 成功率" in e for e in enriched.evidence)

    def test_high_success_rate_maintains_action(self):
        """REFRESH_HOOK 成功率 >= 60% → 维持建议并追加正面证据。"""
        store = ExperienceStore()
        # 4 次成功 + 2 次失败 = 67% 成功率
        for _ in range(4):
            store.add(_make_experience(
                "c1", ExperienceOutcome.SUCCESS,
                mutation_type=MutationType.REFRESH_HOOK,
            ))
        for _ in range(2):
            store.add(_make_experience(
                "c1", ExperienceOutcome.FAILURE,
                mutation_type=MutationType.REFRESH_HOOK,
            ))

        enricher = MemoryEnricher(store)

        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c_new",
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            evidence=["CTR 下降"],
            recommended_action="MUTATE_HOOK",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)
        assert enriched.recommended_action == "MUTATE_HOOK"  # 不变
        assert any("成功率" in e and "建议维持" in e for e in enriched.evidence)


class TestMemoryEnricherConfidenceCalibration:
    """测试置信度校准。"""

    def test_low_global_success_reduces_confidence(self):
        """全局成功率 < 30% 且记录 >= 5 → 降低置信度。"""
        store = ExperienceStore()
        # 7 次失败 + 1 次成功 = 12.5%
        for _ in range(7):
            store.add(_make_experience(
                "c_fail", ExperienceOutcome.FAILURE,
                mutation_type=MutationType.REFRESH_HOOK,
            ))
        store.add(_make_experience("c_ok", ExperienceOutcome.SUCCESS))

        enricher = MemoryEnricher(store)

        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c_new",
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            evidence=["CTR 下降"],
            recommended_action="CONTINUE_MONITORING",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)
        assert enriched.metadata["confidence"] < 0.80
        assert "confidence_adjusted_by" in enriched.metadata

    def test_high_global_success_increases_confidence(self):
        """全局成功率 > 60% 且记录 >= 5 → 提升置信度。"""
        store = ExperienceStore()
        # 7 次成功 + 1 次失败 = 87.5%
        for _ in range(7):
            store.add(_make_experience("c_ok", ExperienceOutcome.SUCCESS))
        store.add(_make_experience("c_fail", ExperienceOutcome.FAILURE))

        enricher = MemoryEnricher(store)

        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c_new",
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            evidence=["CTR 下降"],
            recommended_action="CONTINUE_MONITORING",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)
        assert enriched.metadata["confidence"] > 0.80

    def test_few_records_no_calibration(self):
        """记录 < 5 时不启用置信度校准。"""
        store = ExperienceStore()
        store.add(_make_experience("c1", ExperienceOutcome.FAILURE))

        enricher = MemoryEnricher(store)
        pred = RealityPrediction(
            prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
            target_id="c_new",
            current_value=0.015,
            predicted_value=0.010,
            probability=0.50,
            risk_level=RiskLevel.MEDIUM,
            evidence=["CTR 下降"],
            recommended_action="CONTINUE_MONITORING",
            metadata={"confidence": 0.80, "metric": "ctr"},
        )

        enriched = enricher.enrich_prediction(pred)
        assert enriched.metadata["confidence"] == 0.80  # 不变


class TestMemoryEnricherGetSummary:
    """测试 MemoryEnricher.get_summary()。"""

    def test_empty_store_summary(self):
        """空 store 的 summary 应返回零值。"""
        store = ExperienceStore()
        enricher = MemoryEnricher(store)
        summary = enricher.get_summary()

        assert summary["total_records"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["reliable_patterns"] == 0
        assert summary["tracked_creatives"] == 0

    def test_populated_store_summary(self):
        """有记录的 store 的 summary 应反映实际数据。"""
        store = ExperienceStore()
        store.add(_make_experience("c1", ExperienceOutcome.SUCCESS))
        store.add(_make_experience("c2", ExperienceOutcome.FAILURE))
        store.add(_make_experience("c3", ExperienceOutcome.SUCCESS))

        enricher = MemoryEnricher(store)
        summary = enricher.get_summary()

        assert summary["total_records"] == 3
        assert summary["success_rate"] == pytest.approx(2 / 3, abs=0.01)
        assert summary["tracked_creatives"] == 3


# ── Memory → Decision 端到端测试 ─────────────────────────


class TestMemoryToDecisionEndToEnd:
    """验证经验数据在第二轮预测中真正影响了决策。"""

    def test_second_round_predictions_are_enriched(self):
        """第一轮写入经验 → 第二轮预测被增强。"""
        # ── 第一轮: 正常跑一遍 ──
        current_rows = [
            _make_row("c_fatigue", spend=200, clicks=30, ctr=0.012, cpi=5.0, roas=0.3),
        ]
        previous_rows = [
            _make_row("c_fatigue", spend=200, clicks=60, ctr=0.028, cpi=4.0, roas=0.5),
        ]

        current_agg = aggregate_by_creative(current_rows)
        previous_agg = aggregate_by_creative(previous_rows)

        store = ExperienceStore()
        enricher_r1 = MemoryEnricher(store)  # 空 enricher
        predictions_r1 = generate_predictions(current_agg, previous_agg, enricher=enricher_r1)

        controller = FeedbackController()
        feedback_r1 = controller.evaluate(predictions_r1)
        store_feedback_as_experience(predictions_r1, feedback_r1, store, product_id="P04")

        # 第一轮预测不应有经验增强（store 初始为空）
        r1_evidence = []
        for p in predictions_r1:
            r1_evidence.extend(p.evidence)
        assert not any("历史经验" in e for e in r1_evidence)

        # ── 第二轮: 同样的数据，但现在 store 有历史 ──
        enricher_r2 = MemoryEnricher(store)
        predictions_r2 = generate_predictions(current_agg, previous_agg, enricher=enricher_r2)

        # 第二轮预测应有经验增强
        r2_evidence = []
        for p in predictions_r2:
            r2_evidence.extend(p.evidence)
        assert any("历史经验" in e for e in r2_evidence), \
            "第二轮预测应包含来自第一轮的经验增强"

    def test_repeated_failures_escalate_across_rounds(self):
        """连续多轮失败 → 概率逐轮提升。"""
        # CTR 下降 40%，probability = min(1.0, 0.40*2) = 0.80
        # 0.80 >= TriggerRules FATIGUE_PROBABILITY 阈值 0.75 → 信号触发 → FAILURE
        # 但 0.80 < 1.0，留出经验增强空间（2 次失败后 0.80 + 0.20 = 1.0）
        current = {
            "c1": {
                "spend": 200, "ctr": 0.015, "roas": 0.45,
                "clicks": 30, "impressions": 2000, "installs": 40,
                "revenue": 90, "cpi": 5.0,
            }
        }
        previous = {
            "c1": {
                "spend": 200, "ctr": 0.025, "roas": 0.50,
                "clicks": 50, "impressions": 2000, "installs": 40,
                "revenue": 100, "cpi": 4.0,
            }
        }

        store = ExperienceStore()

        # 第一轮: 无经验
        preds_r1 = generate_predictions(current, previous, enricher=MemoryEnricher(store))
        prob_r1 = preds_r1[0].probability

        # 写入第一轮经验
        controller = FeedbackController()
        feedback_r1 = controller.evaluate(preds_r1)
        store_feedback_as_experience(preds_r1, feedback_r1, store)

        # 第二轮: 有 1 条失败记录（不够升级阈值 2）
        preds_r2 = generate_predictions(current, previous, enricher=MemoryEnricher(store))
        store_feedback_as_experience(preds_r2, controller.evaluate(preds_r2), store)

        # 第三轮: 有 2 条失败记录（够升级阈值 2）
        preds_r3 = generate_predictions(current, previous, enricher=MemoryEnricher(store))
        prob_r3 = preds_r3[0].probability

        # 第三轮概率应高于第一轮
        assert prob_r3 > prob_r1, \
            f"第三轮概率 {prob_r3} 应高于第一轮 {prob_r1}（经验积累效果）"
