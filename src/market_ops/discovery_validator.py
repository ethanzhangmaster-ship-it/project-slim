"""Discovery 闭环验证器：实验结果 → 假设验证 → 知识沉淀

将 experiment_result_ingestion / experiment_manager 的实验数据
与 hypothesis_generator 的假设连接起来，形成完整的闭环：
hypothesis → experiment → data collection → validation → knowledge deposition
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_ops.config import Settings


@dataclass(slots=True)
class ValidationResult:
    experiment_id: str
    hypothesis_id: str
    verdict: str  # confirmed / rejected / inconclusive
    confidence: float  # 0-1
    statistical_significance: float  # p-value 或等效指标
    sample_size: int
    effect_size: float
    learnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidationReport:
    markdown_path: Path
    json_path: Path
    passed: bool
    results: list[ValidationResult] = field(default_factory=list)
    feedback: dict[str, Any] = field(default_factory=dict)


class DiscoveryValidator:
    """闭环验证：连接实验管理、结果摄入和假设生成。

    职责：
    1. 从 experiment_result_ingestion + experiment_manager 读取实验数据
    2. 对每个实验执行统计验证（最小样本量、效果量、置信度）
    3. 生成 confirmed / rejected / inconclusive 判定
    4. 产出 feedback 数据供 hypothesis_generator 下一轮使用
    """

    def __init__(
        self,
        settings: Settings,
        min_sample_size: int = 100,
        confidence_threshold: float = 0.95,
    ) -> None:
        self._settings = settings
        self.min_sample_size = min_sample_size
        self.confidence_threshold = confidence_threshold
        self.validated_hypotheses: list[ValidationResult] = []

    # ------------------------------------------------------------------
    # 核心验证逻辑
    # ------------------------------------------------------------------

    def validate_experiment(self, experiment_result: dict[str, Any]) -> ValidationResult:
        """验证单个实验结果。

        experiment_result 字段约定（与 experiment_result_ingestion 对齐）：
        - id / experiment_id: 实验标识
        - hypothesis_id: 关联假设 ID
        - impressions: 展示量（样本量）
        - conversion_rate / ctr: 核心转化指标
        - baseline_rate / baseline_ctr: 基线对照指标
        - sample_size: 备选样本量字段（优先使用 impressions）
        """
        experiment_id = experiment_result.get("id") or experiment_result.get("experiment_id", "unknown")
        hypothesis_id = experiment_result.get("hypothesis_id", "unknown")
        sample_size = experiment_result.get("impressions", 0) or experiment_result.get("sample_size", 0)
        conversion_rate = float(experiment_result.get("conversion_rate") or experiment_result.get("ctr", 0))
        baseline_rate = float(experiment_result.get("baseline_rate") or experiment_result.get("baseline_ctr", 0))

        # 1) 最小样本量检查
        if sample_size < self.min_sample_size:
            result = ValidationResult(
                experiment_id=experiment_id,
                hypothesis_id=hypothesis_id,
                verdict="inconclusive",
                confidence=0.0,
                statistical_significance=0.0,
                sample_size=sample_size,
                effect_size=0.0,
                learnings=[f"样本量不足: {sample_size} < {self.min_sample_size}"],
                next_actions=[
                    "增加预算扩大样本",
                    f"需要至少 {self.min_sample_size} 次展示",
                ],
            )
            self.validated_hypotheses.append(result)
            return result

        # 2) 效果量计算
        effect = conversion_rate - baseline_rate
        # 使用 Cohen's d 式归一化：effect / max(|baseline|, 0.001)
        confidence = min(abs(effect) / max(abs(baseline_rate), 0.001), 1.0)

        # 3) 判定
        if effect > 0 and confidence >= self.confidence_threshold:
            verdict = "confirmed"
            pct = effect * 100
            learnings = [f"正向效果: 转化率提升 {pct:.1f}%"]
            next_actions = ["scale to broader audience", "record as winning pattern"]
        elif effect < 0 and confidence >= self.confidence_threshold:
            verdict = "rejected"
            pct = abs(effect) * 100
            learnings = [f"负向效果: 转化率下降 {pct:.1f}%"]
            next_actions = ["record as losing pattern", "generate counter-hypothesis"]
        else:
            verdict = "inconclusive"
            learnings = ["效果不显著，需要更多数据"]
            next_actions = ["延长实验周期", "调整变量再试"]

        result = ValidationResult(
            experiment_id=experiment_id,
            hypothesis_id=hypothesis_id,
            verdict=verdict,
            confidence=confidence,
            statistical_significance=confidence,  # 简化：用归一化效果量代理显著性
            sample_size=sample_size,
            effect_size=effect,
            learnings=learnings,
            next_actions=next_actions,
        )
        self.validated_hypotheses.append(result)
        return result

    def validate_batch(self, experiment_results: list[dict[str, Any]]) -> list[ValidationResult]:
        """批量验证实验。"""
        return [self.validate_experiment(exp) for exp in experiment_results]

    # ------------------------------------------------------------------
    # 反馈生成
    # ------------------------------------------------------------------

    def generate_feedback_for_hypothesis_generator(self) -> dict[str, Any]:
        """生成反馈给 hypothesis_generator：哪些模式有效/无效。

        返回结构：
        - cycle: 已验证假设总数
        - win_rate: 确认率
        - winning_patterns: 已确认假设的 learnings
        - losing_patterns: 已拒绝假设的 learnings
        - pending: 未决数
        - suggested_next_batch: 下一轮方向建议
        - validated_results: 完整验证结果（序列化）
        """
        confirmed = [v for v in self.validated_hypotheses if v.verdict == "confirmed"]
        rejected = [v for v in self.validated_hypotheses if v.verdict == "rejected"]
        inconclusive = [v for v in self.validated_hypotheses if v.verdict == "inconclusive"]

        winning_patterns = [v.learnings for v in confirmed]
        losing_patterns = [v.learnings for v in rejected]
        total = len(self.validated_hypotheses)

        # 方向建议
        if confirmed:
            suggested = "focus on confirmed patterns"
        elif rejected:
            suggested = "generate counter-hypotheses against rejected patterns"
        else:
            suggested = "extend experiments to gather more data"

        return {
            "cycle": total,
            "win_rate": len(confirmed) / max(total, 1),
            "winning_patterns": winning_patterns,
            "losing_patterns": losing_patterns,
            "pending": len(inconclusive),
            "suggested_next_batch": suggested,
            "validated_results": [
                {
                    "experiment_id": v.experiment_id,
                    "hypothesis_id": v.hypothesis_id,
                    "verdict": v.verdict,
                    "confidence": v.confidence,
                    "effect_size": v.effect_size,
                    "learnings": v.learnings,
                    "next_actions": v.next_actions,
                }
                for v in self.validated_hypotheses
            ],
        }

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def load_experiment_results(self, report_date: date) -> list[dict[str, Any]]:
        """从 experiment_result_ingestion 的输出加载实验结果。"""
        active_dir = self._settings.active_output_dir
        suffix = report_date.strftime("%Y%m%d")
        ingestion_json = active_dir / f"experiment_result_ingestion_{suffix}.json"

        if not ingestion_json.exists():
            # 尝试从 experiment_plan 加载作为 fallback
            plan_json = active_dir / f"experiment_plan_{suffix}.json"
            if plan_json.exists():
                payload = json.loads(plan_json.read_text(encoding="utf-8"))
                return payload.get("experiments") or payload.get("experiment_rows") or []
            return []

        payload = json.loads(ingestion_json.read_text(encoding="utf-8"))
        return payload.get("result_rows") or payload.get("experiments") or []

    def load_hypotheses(self, report_date: date) -> list[dict[str, Any]]:
        """从 hypothesis_plan 加载假设列表。"""
        active_dir = self._settings.active_output_dir
        suffix = report_date.strftime("%Y%m%d")
        hyp_json = active_dir / f"hypothesis_plan_{suffix}.json"
        if not hyp_json.exists():
            return []
        payload = json.loads(hyp_json.read_text(encoding="utf-8"))
        return payload.get("hypotheses") or payload.get("hypothesis_list") or []

    # ------------------------------------------------------------------
    # 闭环入口：完整运行一次验证
    # ------------------------------------------------------------------

    def build(self, report_date: date) -> ValidationReport:
        """运行完整的闭环验证流程。

        1. 加载实验数据 + 假设列表
        2. 逐条验证
        3. 生成反馈
        4. 写入报告
        """
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")

        # 加载数据
        experiment_results = self.load_experiment_results(report_date)
        hypotheses = self.load_hypotheses(report_date)

        # 验证
        if experiment_results:
            results = self.validate_batch(experiment_results)
        else:
            # 无实验数据时，基于假设生成空验证报告
            results = [
                ValidationResult(
                    experiment_id="pending",
                    hypothesis_id=h.get("id", f"hyp_{i}"),
                    verdict="inconclusive",
                    confidence=0.0,
                    statistical_significance=0.0,
                    sample_size=0,
                    effect_size=0.0,
                    learnings=["等待实验结果输入"],
                    next_actions=["运行 experiment_result_ingestion 摄入数据"],
                )
                for i, h in enumerate(hypotheses)
            ]

        self.validated_hypotheses = results

        # 生成反馈
        feedback = self.generate_feedback_for_hypothesis_generator()

        # 写入文件
        markdown_path = output_dir / f"discovery_validation_{suffix}.md"
        json_path = output_dir / f"discovery_validation_{suffix}.json"
        feedback_json_path = output_dir / f"discovery_validation_feedback_{suffix}.json"

        markdown_path.write_text(self._render_markdown(results, feedback), encoding="utf-8")
        json_path.write_text(
            json.dumps(self._serialize_results(results), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        feedback_json_path.write_text(
            json.dumps(feedback, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        passed = sum(1 for r in results if r.verdict == "confirmed") > 0 if results else False
        return ValidationReport(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=passed,
            results=results,
            feedback=feedback,
        )

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def _render_markdown(self, results: list[ValidationResult], feedback: dict[str, Any]) -> str:
        lines: list[str] = [
            "# Discovery Validation Report",
            "",
            f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Total: {feedback['cycle']}",
            f"- Confirmed: {sum(1 for r in results if r.verdict == 'confirmed')} "
            f"({feedback['win_rate']:.0%})",
            f"- Rejected: {sum(1 for r in results if r.verdict == 'rejected')}",
            f"- Inconclusive: {feedback['pending']}",
            f"- Suggested next: {feedback['suggested_next_batch']}",
            "",
            "## Results",
            "",
        ]

        for r in results:
            verdict_icon = {"confirmed": "+", "rejected": "-", "inconclusive": "?"}
            lines.append(
                f"### {verdict_icon.get(r.verdict, '?')} {r.experiment_id}"
                f" | hypothesis: {r.hypothesis_id}"
            )
            lines.append(f"- Verdict: **{r.verdict.upper()}**")
            lines.append(f"- Confidence: {r.confidence:.3f} | Effect size: {r.effect_size:.4f}")
            lines.append(f"- Sample size: {r.sample_size}")
            if r.learnings:
                lines.append("- Learnings:")
                lines.extend(f"  - {l}" for l in r.learnings)
            if r.next_actions:
                lines.append("- Next actions:")
                lines.extend(f"  - {a}" for a in r.next_actions)
            lines.append("")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _serialize_results(results: list[ValidationResult]) -> list[dict[str, Any]]:
        return [
            {
                "experiment_id": r.experiment_id,
                "hypothesis_id": r.hypothesis_id,
                "verdict": r.verdict,
                "confidence": r.confidence,
                "statistical_significance": r.statistical_significance,
                "sample_size": r.sample_size,
                "effect_size": r.effect_size,
                "learnings": r.learnings,
                "next_actions": r.next_actions,
            }
            for r in results
        ]
