"""E12.5.1 — Experience Collector。

将 E12.4 的实验结果（ExperimentRun + ExperimentEvaluation +
EvolutionLearningRecord + MutationRequest）转换为长期经验记忆。

流程:
  ExperimentRun + ExperimentEvaluation
       │
       ▼
  ExperienceCollector.collect()
       │
       ▼
  ExperienceRecord（存入 ExperienceStore）

支持:
  - 单条收集
  - 批量收集
  - 从 EvolutionLearningRecord 直接收集
  - 自动推断结果类型和洞察
"""

from __future__ import annotations

from .models import (
    ContextDetail,
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceResult,
    ExperimentDetail,
    MutationDetail,
    MutationType,
)

# 延迟导入，避免循环引用
from ..feedback.models import (
    EvolutionLearningRecord,
    ExperimentEvaluation,
    ExperimentRun,
    MutationIntent,
    MutationRequest,
)


class ExperienceCollector:
    """经验收集器。

    将 E12.4 的实验闭环数据转换为长期经验记忆。

    Usage:
        >>> collector = ExperienceCollector()
        >>> record = collector.collect(
        ...     experiment=exp,
        ...     evaluation=eval,
        ...     learning_record=lr,
        ...     mutation_request=mr,
        ... )
    """

    # ── Main API ───────────────────────────────────────────

    def collect(
        self,
        experiment: ExperimentRun,
        evaluation: ExperimentEvaluation,
        learning_record: EvolutionLearningRecord | None = None,
        mutation_request: MutationRequest | None = None,
        product_id: str = "",
        product_name: str = "",
        market: str = "",
        country: str = "",
        audience: str = "",
        platform: str = "facebook",
        campaign_type: str = "",
        genome_id: str = "",
        gene_before: dict[str, str] | None = None,
        gene_after: dict[str, str] | None = None,
    ) -> ExperienceRecord:
        """收集一条实验经验。

        Args:
            experiment:       实验运行记录
            evaluation:       实验结果评估
            learning_record:  进化学习记录（可选）
            mutation_request: 突变请求（可选）
            product_id:       产品 ID
            product_name:     产品名称
            market:           市场
            country:          国家
            audience:         受众
            platform:         平台
            campaign_type:    投放类型
            genome_id:        基因组 ID
            gene_before:      突变前基因值
            gene_after:       突变后基因值

        Returns:
            ExperienceRecord
        """
        # 1. 构建 MutationDetail
        mutation_detail = self._build_mutation_detail(
            mutation_request, gene_before, gene_after
        )

        # 2. 构建 ExperimentDetail
        experiment_detail = self._build_experiment_detail(experiment, evaluation)

        # 3. 构建 ContextDetail
        context_detail = ContextDetail(
            product_id=product_id,
            product_name=product_name,
            market=market,
            country=country,
            audience=audience,
            platform=platform,
            campaign_type=campaign_type,
        )

        # 4. 构建 ExperienceResult
        result = self._build_result(evaluation, learning_record)

        # 5. 构建关联 ID
        related_ids = {
            "experiment_id": experiment.experiment_id,
            "evaluation_id": evaluation.evaluation_id,
        }
        if mutation_request:
            related_ids["mutation_request_id"] = mutation_request.request_id
        if learning_record:
            related_ids["learning_record_id"] = learning_record.record_id
            related_ids["prediction_id"] = learning_record.prediction_id

        # 6. 组装 ExperienceRecord
        record = ExperienceRecord(
            product_id=product_id,
            creative_id=experiment.creative_id,
            genome_id=genome_id,
            mutation=mutation_detail,
            experiment=experiment_detail,
            context=context_detail,
            result=result,
            related_ids=related_ids,
        )

        return record

    def collect_batch(
        self,
        experiments: list[ExperimentRun],
        evaluations: list[ExperimentEvaluation],
        learning_records: list[EvolutionLearningRecord] | None = None,
        mutation_requests: list[MutationRequest] | None = None,
        product_id: str = "",
        product_name: str = "",
        market: str = "",
        platform: str = "facebook",
    ) -> list[ExperienceRecord]:
        """批量收集。

        Args:
            experiments:      实验列表
            evaluations:      评估列表
            learning_records: 学习记录列表（可选）
            mutation_requests: 突变请求列表（可选）
            product_id:       产品 ID
            product_name:     产品名称
            market:           市场
            platform:         平台

        Returns:
            ExperienceRecord 列表
        """
        records: list[ExperienceRecord] = []
        for i, (exp, ev) in enumerate(zip(experiments, evaluations)):
            lr = learning_records[i] if learning_records and i < len(learning_records) else None
            mr = mutation_requests[i] if mutation_requests and i < len(mutation_requests) else None

            records.append(
                self.collect(
                    experiment=exp,
                    evaluation=ev,
                    learning_record=lr,
                    mutation_request=mr,
                    product_id=product_id,
                    product_name=product_name,
                    market=market,
                    platform=platform,
                )
            )
        return records

    def collect_from_learning_record(
        self,
        learning_record: EvolutionLearningRecord,
        experiment: ExperimentRun,
        evaluation: ExperimentEvaluation,
        mutation_request: MutationRequest | None = None,
        product_id: str = "",
        market: str = "",
        platform: str = "facebook",
    ) -> ExperienceRecord:
        """从 EvolutionLearningRecord 直接收集。

        Args:
            learning_record:  进化学习记录
            experiment:       实验运行记录
            evaluation:       实验结果评估
            mutation_request: 突变请求（可选）
            product_id:       产品 ID
            market:           市场
            platform:         平台

        Returns:
            ExperienceRecord
        """
        return self.collect(
            experiment=experiment,
            evaluation=evaluation,
            learning_record=learning_record,
            mutation_request=mutation_request,
            product_id=product_id,
            market=market,
            platform=platform,
        )

    # ── Private helpers ────────────────────────────────────

    @staticmethod
    def _build_mutation_detail(
        mutation_request: MutationRequest | None,
        gene_before: dict[str, str] | None,
        gene_after: dict[str, str] | None,
    ) -> MutationDetail:
        """从 MutationRequest 构建 MutationDetail。"""
        if mutation_request is None:
            return MutationDetail()

        # 映射 MutationIntent → MutationType
        intent_to_type: dict[MutationIntent, MutationType] = {
            MutationIntent.REFRESH_HOOK: MutationType.REFRESH_HOOK,
            MutationIntent.VISUAL_VARIATION: MutationType.VISUAL_VARIATION,
            MutationIntent.GAMEPLAY_CLARITY: MutationType.GAMEPLAY_CLARITY,
            MutationIntent.OFFER_CHANGE: MutationType.OFFER_CHANGE,
            MutationIntent.FULL_REBUILD: MutationType.FULL_REBUILD,
        }

        return MutationDetail(
            mutation_type=intent_to_type.get(
                mutation_request.intent, MutationType.REFRESH_HOOK
            ),
            changed_genes=mutation_request.change_genes,
            gene_before=gene_before or {},
            gene_after=gene_after or {},
            constraints=mutation_request.dna_constraints,
        )

    @staticmethod
    def _build_experiment_detail(
        experiment: ExperimentRun,
        evaluation: ExperimentEvaluation,
    ) -> ExperimentDetail:
        """从 ExperimentRun + ExperimentEvaluation 构建 ExperimentDetail。"""
        baseline = evaluation.raw_metrics.get("baseline", {})
        winner = evaluation.raw_metrics.get(evaluation.winner_id, {})

        return ExperimentDetail(
            baseline_metrics=dict(baseline),
            winner_metrics=dict(winner),
            improvement=evaluation.improvement_score,
            metrics_delta=evaluation.metrics_delta,
            winner_id=evaluation.winner_id,
            variant_count=experiment.variant_count,
            confidence=evaluation.confidence,
        )

    @staticmethod
    def _build_result(
        evaluation: ExperimentEvaluation,
        learning_record: EvolutionLearningRecord | None,
    ) -> ExperienceResult:
        """从评估结果构建 ExperienceResult。"""
        # 判断结果类型
        if evaluation.improvement_score > 0.15:
            outcome = ExperienceOutcome.SUCCESS
            success = True
        elif evaluation.improvement_score > 0:
            outcome = ExperienceOutcome.MARGINAL
            success = True
        elif evaluation.improvement_score <= 0 and evaluation.winner_id:
            outcome = ExperienceOutcome.FAILURE
            success = False
        else:
            outcome = ExperienceOutcome.INCONCLUSIVE
            success = False

        # 失败原因
        failure_reason = ""
        if outcome == ExperienceOutcome.FAILURE:
            failure_reason = "All variants underperformed baseline"
        elif outcome == ExperienceOutcome.INCONCLUSIVE:
            failure_reason = "No clear winner or insufficient data"

        # 洞察
        insight = evaluation.learning_signal
        if learning_record and learning_record.insight:
            insight = learning_record.insight

        # 关键发现
        key_finding = ""
        if outcome in (ExperienceOutcome.SUCCESS, ExperienceOutcome.MARGINAL):
            if evaluation.winner_id:
                key_finding = (
                    f"Winner {evaluation.winner_id}: "
                    f"improvement {evaluation.improvement_score:+.0%}"
                )
        elif outcome == ExperienceOutcome.FAILURE:
            key_finding = "Mutation ineffective — no improvement over baseline"

        return ExperienceResult(
            outcome=outcome,
            success=success,
            failure_reason=failure_reason,
            insight=insight,
            key_finding=key_finding,
        )

    def __repr__(self) -> str:
        return "ExperienceCollector()"