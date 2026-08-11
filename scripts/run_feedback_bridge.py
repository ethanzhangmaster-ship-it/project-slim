"""宇宙 A → 宇宙 B 桥接脚本：Facebook Ads 数据 → FeedbackController → ExperienceStore

打通第一条真实闭环（含 Memory → Decision 反馈）：
  1. 从 Facebook Ads API 拉取真实广告效果数据（宇宙 A）
  2. 从 ExperienceStore 加载历史经验，创建 MemoryEnricher
  3. 对比当前周期与上一周期，检测疲劳/衰减/放量/燃烧信号
     — MemoryEnricher 用历史经验调整概率、置信度、建议行动
  4. 送入 FeedbackController.evaluate() 生成反馈信号和行动建议（宇宙 B）
  5. 将结果写入 ExperienceStore 形成长期记忆（下一轮 Step 2 会读取）

用法:
    python scripts/run_feedback_bridge.py --days 7
    python scripts/run_feedback_bridge.py --days 7 --dry-run   # 不写入 ExperienceStore
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

from market_ops.clients.meta_ads import MetaAdsCreativeClient
from market_ops.creative_vision_runtime.reality.feedback import (
    FeedbackController,
    FeedbackResult,
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


# ── 阈值常量 ──────────────────────────────────────────────

# CTR 下降超过此比例 → 疲劳风险
FATIGUE_CTR_DROP_THRESHOLD = 0.15

# ROAS 下降超过此比例 → ROAS 衰减风险
ROAS_DROP_THRESHOLD = 0.20

# ROAS 低于此值 → 预算燃烧风险
BUDGET_BURN_ROAS_THRESHOLD = 0.30

# ROAS 高于此值且 CTR 稳定 → 放量机会
SCALE_ROAS_THRESHOLD = 0.60

# 最小花费（USD），低于此值的数据噪音太大不分析
MIN_SPEND = 10.0

# 连续失败几次后升级严重度
REPEATED_FAILURE_ESCALATION = 2

# 变异类型成功率低于此值时升级建议行动
LOW_SUCCESS_RATE_THRESHOLD = 0.30

# 变异类型成功率高于此值时保持建议行动
HIGH_SUCCESS_RATE_THRESHOLD = 0.60

# 需要多少条记录才启用置信度校准
MIN_RECORDS_FOR_CALIBRATION = 5


class MemoryEnricher:
    """从 ExperienceStore 提取历史经验，用于增强下一轮预测。

    三层经验注入：
      1. 创意历史 — 同一 creative_id 过去的成败记录
      2. 变异有效性 — 各 MutationType 的历史成功率
      3. 可靠模式 — 从大量经验中提取的可靠 pattern
    """

    def __init__(self, store: ExperienceStore) -> None:
        self._store = store
        self._patterns = store.extract_patterns(min_sample=3)
        self._stats = store.get_stats()

        # 按 creative_id 索引历史记录
        self._creative_history: dict[str, list[ExperienceRecord]] = defaultdict(list)
        for record in store.query_all():
            self._creative_history[record.creative_id].append(record)

        # 按 mutation_type 计算成功率
        self._mutation_success: dict[str, dict[str, float]] = {}
        for mt, count in self._stats.by_mutation_type.items():
            records = store.query_by_mutation_type(
                _parse_mutation_type(mt)
            ) if mt else []
            successes = sum(1 for r in records if r.result.success)
            rate = successes / len(records) if records else 0.0
            self._mutation_success[mt] = {
                "total": float(len(records)),
                "success": float(successes),
                "rate": rate,
            }

    def enrich_prediction(self, prediction: RealityPrediction) -> RealityPrediction:
        """用历史经验增强单条预测。

        调整维度：
          - probability: 连续失败 → 提升
          - confidence: 全局成功率 → 校准
          - recommended_action: 变异低效 → 升级
          - evidence: 追加历史经验条目
        """
        creative_id = prediction.target_id
        history = self._creative_history.get(creative_id, [])

        # ── 1. 创意历史：连续失败升级 ──
        failure_count = sum(
            1 for r in history if r.result.outcome == ExperienceOutcome.FAILURE
        )
        if failure_count >= REPEATED_FAILURE_ESCALATION:
            # 连续失败 → 提升概率
            old_prob = prediction.probability
            prediction.probability = min(1.0, old_prob + 0.10 * failure_count)
            prediction.evidence.append(
                f"历史经验: 该创意已触发 {failure_count} 次失败信号"
            )
            # 升级风险等级
            if prediction.risk_level == RiskLevel.LOW:
                prediction.risk_level = RiskLevel.MEDIUM
            elif prediction.risk_level == RiskLevel.MEDIUM:
                prediction.risk_level = RiskLevel.HIGH

        # ── 2. 变异有效性：低效行动升级 ──
        action_to_mutation = {
            "MUTATE_HOOK": "refresh_hook",
            "ANALYZE_DNA_AND_MUTATE": "offer_change",
            "PAUSE_AND_REPLACE": "full_rebuild",
            "INCREASE_BUDGET": "visual_variation",
        }
        mutation_key = action_to_mutation.get(prediction.recommended_action, "")
        mt_stats = self._mutation_success.get(mutation_key)
        if mt_stats and mt_stats["total"] >= 3:
            rate = mt_stats["rate"]
            if rate < LOW_SUCCESS_RATE_THRESHOLD:
                # 变异低效 → 升级建议
                if prediction.recommended_action == "MUTATE_HOOK":
                    prediction.recommended_action = "ANALYZE_DNA_AND_MUTATE"
                    prediction.evidence.append(
                        f"历史经验: REFRESH_HOOK 成功率仅 {rate:.0%}"
                        f"（{int(mt_stats['success'])}/{int(mt_stats['total'])}），升级为 DNA 分析"
                    )
                elif prediction.recommended_action == "ANALYZE_DNA_AND_MUTATE":
                    prediction.recommended_action = "PAUSE_AND_REPLACE"
                    prediction.evidence.append(
                        f"历史经验: OFFER_CHANGE 成功率仅 {rate:.0%}"
                        f"（{int(mt_stats['success'])}/{int(mt_stats['total'])}），升级为暂停替换"
                    )
            elif rate >= HIGH_SUCCESS_RATE_THRESHOLD:
                prediction.evidence.append(
                    f"历史经验: {mutation_key.upper()} 成功率 {rate:.0%}"
                    f"（{int(mt_stats['success'])}/{int(mt_stats['total'])}），建议维持"
                )

        # ── 3. 置信度校准 ──
        if self._stats.total_records >= MIN_RECORDS_FOR_CALIBRATION:
            base_conf = prediction.metadata.get("confidence", 0.5)
            global_success_rate = self._stats.success_rate
            if global_success_rate < 0.30:
                # 全局成功率低 → 降低置信度
                calibrated = max(0.3, base_conf - 0.10)
                prediction.metadata["confidence"] = calibrated
                prediction.metadata["confidence_adjusted_by"] = "memory_calibration"
                prediction.evidence.append(
                    f"置信度校准: 全局成功率 {global_success_rate:.0%}，"
                    f"置信度 {base_conf:.2f}→{calibrated:.2f}"
                )
            elif global_success_rate > 0.60:
                # 全局成功率高 → 提升置信度
                calibrated = min(0.95, base_conf + 0.05)
                prediction.metadata["confidence"] = calibrated
                prediction.metadata["confidence_adjusted_by"] = "memory_calibration"
                prediction.evidence.append(
                    f"置信度校准: 全局成功率 {global_success_rate:.0%}，"
                    f"置信度 {base_conf:.2f}→{calibrated:.2f}"
                )

        # ── 4. 可靠模式匹配 ──
        for pattern in self._patterns:
            if not pattern.is_reliable:
                continue
            # 如果模式涉及的基因和当前预测的变异基因有交集
            pred_genes = set(
                prediction.metadata.get("changed_genes", [])
            )
            if pred_genes and set(pattern.genes) & pred_genes:
                prediction.evidence.append(
                    f"可靠模式: {pattern.description}"
                    f"（成功率 {pattern.success_rate:.0%}，样本 {pattern.sample_size}）"
                )
                break  # 只追加一条最相关的

        return prediction

    def enrich_predictions(
        self, predictions: list[RealityPrediction]
    ) -> list[RealityPrediction]:
        """批量增强预测。"""
        return [self.enrich_prediction(p) for p in predictions]

    def get_summary(self) -> dict[str, Any]:
        """返回记忆摘要供报告使用。"""
        return {
            "total_records": self._stats.total_records,
            "success_rate": self._stats.success_rate,
            "reliable_patterns": len([p for p in self._patterns if p.is_reliable]),
            "tracked_creatives": len(self._creative_history),
            "mutation_stats": self._mutation_success,
        }


def _parse_mutation_type(value: str) -> MutationType | None:
    """安全解析 MutationType 枚举。"""
    try:
        return MutationType(value)
    except ValueError:
        return None


def fetch_facebook_data(
    access_token: str,
    ad_account_id: str,
    api_version: str,
    game_name: str,
    days: int,
) -> list[AdsPerformanceRow]:
    """从 Facebook Ads API 拉取真实广告效果数据。"""
    client = MetaAdsCreativeClient(
        access_token=access_token,
        ad_account_id=ad_account_id,
        api_version=api_version,
        default_game_name=game_name,
    )
    end = date.today()
    start = end - timedelta(days=days)
    rows = client.fetch_performance_rows(start, end)
    print(f"  拉取到 {len(rows)} 条广告效果记录（{start} ~ {end}）")
    return rows


def aggregate_by_creative(
    rows: list[AdsPerformanceRow],
) -> dict[str, dict[str, float]]:
    """按 creative_id 聚合效果数据，返回 {creative_id: metrics}。

    AdsPerformanceRow 不含 impressions/installs/revenue，
    从 spend/clicks/ctr/cpi/roas 反推:
      impressions = clicks / ctr
      installs = spend / cpi
      revenue = spend * roas
    """
    agg: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "spend": 0.0,
            "clicks": 0.0,
            "ctr_sum": 0.0,
            "ctr_count": 0,
            "cpi_sum": 0.0,
            "cpi_count": 0,
            "roas_sum": 0.0,
            "roas_count": 0,
        }
    )
    for row in rows:
        cid = row.creative_id or row.ad_id or "unknown"
        agg[cid]["spend"] += row.spend
        agg[cid]["clicks"] += row.clicks
        if row.ctr > 0:
            agg[cid]["ctr_sum"] += row.ctr
            agg[cid]["ctr_count"] += 1
        if row.cpi > 0:
            agg[cid]["cpi_sum"] += row.cpi
            agg[cid]["cpi_count"] += 1
        if row.roas > 0:
            agg[cid]["roas_sum"] += row.roas
            agg[cid]["roas_count"] += 1

    # 计算衍生指标
    result: dict[str, dict[str, float]] = {}
    for cid, m in agg.items():
        ctr = m["ctr_sum"] / m["ctr_count"] if m["ctr_count"] > 0 else 0.0
        cpi = m["cpi_sum"] / m["cpi_count"] if m["cpi_count"] > 0 else 0.0
        roas = m["roas_sum"] / m["roas_count"] if m["roas_count"] > 0 else 0.0
        impressions = m["clicks"] / ctr if ctr > 0 else 0.0
        installs = m["spend"] / cpi if cpi > 0 else 0.0
        revenue = m["spend"] * roas
        result[cid] = {
            "spend": m["spend"],
            "clicks": m["clicks"],
            "ctr": ctr,
            "cpi": cpi,
            "roas": roas,
            "impressions": impressions,
            "installs": installs,
            "revenue": revenue,
        }

    return result


def generate_predictions(
    current: dict[str, dict[str, float]],
    previous: dict[str, dict[str, float]],
    enricher: MemoryEnricher | None = None,
) -> list[RealityPrediction]:
    """对比当前周期和上一周期，生成 RealityPrediction 列表。

    检测四种信号：
      - CTR 下降 → CREATIVE_FATIGUE_RISK
      - ROAS 下降 → ROAS_DECAY_RISK
      - ROAS 极低 + 高花费 → BUDGET_BURN_RISK
      - ROAS 高 + CTR 稳定 → SCALE_OPPORTUNITY

    若提供 enricher，则用历史经验增强每条预测（概率/置信度/建议行动/evidence）。
    """
    predictions: list[RealityPrediction] = []

    for creative_id, curr in current.items():
        if curr["spend"] < MIN_SPEND:
            continue

        prev = previous.get(creative_id, {})
        evidence: list[str] = []

        # ── 疲劳检测：CTR 下降 ──
        prev_ctr = prev.get("ctr", 0.0)
        curr_ctr = curr["ctr"]
        if prev_ctr > 0:
            ctr_drop = (prev_ctr - curr_ctr) / prev_ctr
            if ctr_drop > FATIGUE_CTR_DROP_THRESHOLD:
                probability = min(1.0, ctr_drop * 2)
                risk = (
                    RiskLevel.CRITICAL
                    if probability >= 0.9
                    else RiskLevel.HIGH
                    if probability >= 0.75
                    else RiskLevel.MEDIUM
                )
                predictions.append(
                    RealityPrediction(
                        prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                        target_id=creative_id,
                        current_value=curr_ctr,
                        predicted_value=curr_ctr * (1 - ctr_drop),
                        probability=probability,
                        risk_level=risk,
                        evidence=[
                            f"CTR {prev_ctr:.4f}→{curr_ctr:.4f}（-{ctr_drop:.0%}）",
                            f"当前花费 ${curr['spend']:.0f}",
                        ],
                        recommended_action="MUTATE_HOOK",
                        metadata={
                            "confidence": 0.80,
                            "ctr_drop": round(ctr_drop, 4),
                            "metric": "ctr",
                        },
                    )
                )
                evidence.append(f"CTR 下降 {ctr_drop:.0%}")

        # ── ROAS 衰减检测 ──
        prev_roas = prev.get("roas", 0.0)
        curr_roas = curr["roas"]
        if prev_roas > 0:
            roas_drop = (prev_roas - curr_roas) / prev_roas
            if roas_drop > ROAS_DROP_THRESHOLD:
                probability = min(1.0, roas_drop * 1.5)
                risk = (
                    RiskLevel.CRITICAL
                    if probability >= 0.9
                    else RiskLevel.HIGH
                    if probability >= 0.75
                    else RiskLevel.MEDIUM
                )
                predictions.append(
                    RealityPrediction(
                        prediction_type=PredictionType.ROAS_DECAY_RISK,
                        target_id=creative_id,
                        current_value=curr_roas,
                        predicted_value=curr_roas * (1 - roas_drop),
                        probability=probability,
                        risk_level=risk,
                        evidence=[
                            f"ROAS {prev_roas:.2f}→{curr_roas:.2f}（-{roas_drop:.0%}）",
                            f"收入 ${curr['revenue']:.0f} / 花费 ${curr['spend']:.0f}",
                        ],
                        recommended_action="ANALYZE_DNA_AND_MUTATE",
                        metadata={
                            "confidence": 0.80,
                            "roas_drop": round(roas_drop, 4),
                            "metric": "roas",
                        },
                    )
                )
                evidence.append(f"ROAS 下降 {roas_drop:.0%}")

        # ── 预算燃烧检测：ROAS 极低 + 高花费 ──
        if curr_roas < BUDGET_BURN_ROAS_THRESHOLD and curr["spend"] > 50:
            burn_ratio = 1.0 - curr_roas
            probability = min(1.0, burn_ratio)
            predictions.append(
                RealityPrediction(
                    prediction_type=PredictionType.BUDGET_BURN_RISK,
                    target_id=creative_id,
                    current_value=curr_roas,
                    predicted_value=max(0.0, curr_roas - 0.05),
                    probability=probability,
                    risk_level=RiskLevel.HIGH if probability >= 0.7 else RiskLevel.MEDIUM,
                    evidence=[
                        f"ROAS 仅 {curr_roas:.2f}（阈值 {BUDGET_BURN_ROAS_THRESHOLD}）",
                        f"花费 ${curr['spend']:.0f}，收入 ${curr['revenue']:.0f}",
                    ],
                    recommended_action="PAUSE_AND_REPLACE",
                    metadata={
                        "confidence": 0.85,
                        "roas": round(curr_roas, 4),
                        "spend": round(curr["spend"], 2),
                    },
                )
            )
            evidence.append(f"预算燃烧（ROAS {curr_roas:.2f}）")

        # ── 放量机会检测：ROAS 高 + CTR 稳定 ──
        if curr_roas > SCALE_ROAS_THRESHOLD and (not prev_ctr or curr_ctr >= prev_ctr * 0.95):
            probability = min(1.0, curr_roas)
            predictions.append(
                RealityPrediction(
                    prediction_type=PredictionType.SCALE_OPPORTUNITY,
                    target_id=creative_id,
                    current_value=curr_roas,
                    predicted_value=curr_roas * 1.1,
                    probability=probability,
                    risk_level=RiskLevel.LOW,
                    evidence=[
                        f"ROAS {curr_roas:.2f}（> {SCALE_ROAS_THRESHOLD}）",
                        f"CTR {curr_ctr:.4f} 稳定" if prev_ctr else "新创意，数据充足",
                        f"安装 {curr['installs']:.0f}，CPI ${curr['cpi']:.2f}",
                    ],
                    recommended_action="INCREASE_BUDGET",
                    metadata={
                        "confidence": 0.80,
                        "roas": round(curr_roas, 4),
                        "ctr": round(curr_ctr, 4),
                    },
                )
            )
            evidence.append(f"放量机会（ROAS {curr_roas:.2f}）")

        if not evidence:
            # 数据收集型预测（无风险但记录在案）
            predictions.append(
                RealityPrediction(
                    prediction_type=PredictionType.CREATIVE_FATIGUE_RISK,
                    target_id=creative_id,
                    current_value=curr_ctr,
                    predicted_value=curr_ctr,
                    probability=0.1,
                    risk_level=RiskLevel.LOW,
                    evidence=[
                        f"指标平稳，CTR {curr_ctr:.4f}，ROAS {curr_roas:.2f}",
                        f"花费 ${curr['spend']:.0f}",
                    ],
                    recommended_action="CONTINUE_MONITORING",
                    metadata={"confidence": 0.3, "metric": "none"},
                )
            )

    # 用历史经验增强预测（Memory → Decision 连接点）
    if enricher is not None:
        predictions = enricher.enrich_predictions(predictions)

    return predictions


def store_feedback_as_experience(
    predictions: list[RealityPrediction],
    feedback_result: FeedbackResult,
    store: ExperienceStore,
    product_id: str = "",
    market: str = "global",
) -> int:
    """将 FeedbackController 输出转化为 ExperienceRecord 存入 ExperienceStore。

    Returns:
        写入的记录数。
    """
    records_added = 0

    # 按 creative_id 分组信号
    signal_map: dict[str, list] = defaultdict(list)
    for signal in feedback_result.triggered:
        signal_map[signal.creative_id].append(signal)

    for pred in predictions:
        creative_id = pred.target_id
        triggered = signal_map.get(creative_id, [])

        # 判断结果
        if not triggered:
            outcome = ExperienceOutcome.INCONCLUSIVE
            insight = "无触发信号，继续观察"
            improvement = 0.0
        elif any(s.signal_type.value == "scale_opportunity" for s in triggered):
            outcome = ExperienceOutcome.SUCCESS
            insight = f"放量机会: ROAS {pred.current_value:.2f}"
            improvement = pred.current_value
        elif any(s.signal_type.value in ("fatigue_warning", "roas_decline") for s in triggered):
            outcome = ExperienceOutcome.FAILURE
            insight = f"创意衰减: {' '.join(pred.evidence[:2])}"
            improvement = -abs(pred.delta)
        elif any(s.signal_type.value == "creative_replacement" for s in triggered):
            outcome = ExperienceOutcome.FAILURE
            insight = f"预算燃烧，需替换: ROAS {pred.current_value:.2f}"
            improvement = -0.1
        else:
            outcome = ExperienceOutcome.INCONCLUSIVE
            insight = "数据收集阶段"
            improvement = 0.0

        # 构建 mutation detail
        mutation_type = MutationType.REFRESH_HOOK
        changed_genes: list[str] = []
        if pred.recommended_action == "MUTATE_HOOK":
            mutation_type = MutationType.REFRESH_HOOK
            changed_genes = ["hook", "visual_style"]
        elif pred.recommended_action == "ANALYZE_DNA_AND_MUTATE":
            mutation_type = MutationType.OFFER_CHANGE
            changed_genes = ["monetization", "context"]
        elif pred.recommended_action == "PAUSE_AND_REPLACE":
            mutation_type = MutationType.FULL_REBUILD
            changed_genes = ["hook", "visual_style", "gameplay", "monetization"]
        elif pred.recommended_action == "INCREASE_BUDGET":
            mutation_type = MutationType.VISUAL_VARIATION
            changed_genes = ["visual_style"]

        record = ExperienceRecord(
            creative_id=creative_id,
            mutation=MutationDetail(
                mutation_type=mutation_type,
                changed_genes=changed_genes,
            ),
            experiment=ExperimentDetail(
                baseline_metrics={
                    "ctr": pred.current_value if pred.metadata.get("metric") == "ctr" else 0.0,
                    "roas": pred.current_value if pred.metadata.get("metric") == "roas" else 0.0,
                },
                improvement=improvement,
                confidence=pred.metadata.get("confidence", 0.5),
            ),
            context=ContextDetail(
                product_id=product_id,
                market=market,
                platform="facebook",
            ),
            result=ExperienceResult(
                outcome=outcome,
                success=(outcome == ExperienceOutcome.SUCCESS),
                insight=insight,
                key_finding=pred.recommended_action,
            ),
            related_ids={
                "prediction_id": pred.prediction_id,
            },
            metadata={
                "prediction_type": pred.prediction_type.value,
                "risk_level": pred.risk_level.value,
                "probability": pred.probability,
                "triggered_count": len(triggered),
                "evidence": pred.evidence,
            },
        )
        store.add(record)
        records_added += 1

    return records_added


def print_report(
    predictions: list[RealityPrediction],
    feedback: FeedbackResult,
    store: ExperienceStore,
    records_added: int,
    enricher: MemoryEnricher | None = None,
) -> None:
    """打印闭环运行报告。"""
    print("\n" + "=" * 60)
    print("  闭环运行报告 — Facebook → Prediction → Feedback → Memory")
    print("=" * 60)

    # 预测统计
    type_counts: dict[str, int] = defaultdict(int)
    for p in predictions:
        type_counts[p.prediction_type.value] += 1
    print(f"\n📊 生成预测: {len(predictions)} 条")
    for ptype, count in sorted(type_counts.items()):
        print(f"   {ptype}: {count}")

    # 经验增强统计
    if enricher is not None:
        mem = enricher.get_summary()
        enriched_count = sum(
            1 for p in predictions
            if any("历史经验" in e or "置信度校准" in e or "可靠模式" in e
                   for e in p.evidence)
        )
        print(f"\n🧠 经验增强 (Memory → Decision):")
        print(f"   被增强的预测: {enriched_count}/{len(predictions)}")
        print(f"   历史记录: {mem['total_records']}")
        print(f"   追踪创意: {mem['tracked_creatives']}")
        print(f"   可靠模式: {mem['reliable_patterns']}")

    # 反馈统计
    print(f"\n⚡ FeedbackController 评估结果:")
    print(f"   信号总数: {len(feedback.signals)}")
    print(f"   触发信号: {len(feedback.triggered)}")
    print(f"   行动建议: {len(feedback.actions)}")
    print(f"   进化机会: {len(feedback.evolution_opportunities)}")
    print(f"   摘要: {feedback.summary or '（无）'}")

    # 触发的信号详情
    if feedback.triggered:
        print(f"\n🎯 触发信号详情 (Top 5):")
        sorted_signals = sorted(
            feedback.triggered,
            key=lambda s: s.priority,
            reverse=True,
        )
        for s in sorted_signals[:5]:
            print(
                f"   [{s.signal_type.value}] creative={s.creative_id} "
                f"priority={s.priority:.2f} action={s.recommended_action}"
            )

    # Memory 统计
    stats = store.get_stats()
    print(f"\n📦 ExperienceStore 记忆:")
    print(f"   总记录: {stats.total_records}")
    print(f"   成功: {stats.success_count} ({stats.success_rate:.0%})")
    print(f"   平均提升: {stats.mean_improvement:.4f}")
    print(f"   最佳提升: {stats.best_improvement:.4f}")
    print(f"   本次写入: {records_added}")

    print("\n" + "=" * 60)
    print("  ✅ 闭环完成: Facebook → Prediction → Feedback → Memory")
    print("     Memory → Decision 反馈: ✅ 经验已增强本轮预测")
    print("=" * 60 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Facebook Ads → FeedbackController → ExperienceStore 闭环桥接"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="当前周期天数（默认 7，会自动取前一个同等长度周期做对比）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只分析不写入 ExperienceStore",
    )
    parser.add_argument(
        "--product-id",
        default="",
        help="产品 ID（写入 ExperienceRecord.context.product_id）",
    )
    args = parser.parse_args()

    load_dotenv()

    access_token = os.getenv("META_ACCESS_TOKEN", "")
    ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
    api_version = os.getenv("META_API_VERSION", "v22.0")
    game_name = os.getenv("DEFAULT_GAME_NAME", "P04")

    if not access_token or not ad_account_id:
        print("❌ 缺少 META_ACCESS_TOKEN 或 META_AD_ACCOUNT_ID，请检查 .env 文件")
        return 1

    print("步骤 1/5: 从 Facebook Ads API 拉取当前周期数据...")
    end = date.today()
    start = end - timedelta(days=args.days)
    current_rows = fetch_facebook_data(
        access_token, ad_account_id, api_version, game_name, args.days
    )

    print("步骤 2/5: 拉取上一周期数据用于趋势对比...")
    prev_end = start
    prev_start = prev_end - timedelta(days=args.days)
    client = MetaAdsCreativeClient(
        access_token=access_token,
        ad_account_id=ad_account_id,
        api_version=api_version,
        default_game_name=game_name,
    )
    prev_rows = client.fetch_performance_rows(prev_start, prev_end)
    print(f"  拉取到 {len(prev_rows)} 条上一周期记录（{prev_start} ~ {prev_end}）")

    print("步骤 3/5: 加载历史经验 (Memory → Decision)...")
    store = ExperienceStore()
    enricher = MemoryEnricher(store)
    mem_summary = enricher.get_summary()
    print(f"  历史记录: {mem_summary['total_records']} 条")
    print(f"  追踪创意: {mem_summary['tracked_creatives']} 个")
    print(f"  可靠模式: {mem_summary['reliable_patterns']} 个")
    if mem_summary["mutation_stats"]:
        for mt, ms in mem_summary["mutation_stats"].items():
            if ms["total"] >= 3:
                print(f"  变异 {mt}: 成功率 {ms['rate']:.0%}（{int(ms['success'])}/{int(ms['total'])}）")

    print("步骤 4/5: 生成预测（含经验增强）并送入 FeedbackController...")
    current_agg = aggregate_by_creative(current_rows)
    previous_agg = aggregate_by_creative(prev_rows)
    predictions = generate_predictions(current_agg, previous_agg, enricher=enricher)
    print(f"  生成 {len(predictions)} 条预测")

    controller = FeedbackController()
    feedback = controller.evaluate(predictions)

    print("步骤 5/5: 写入 ExperienceStore...")
    if args.dry_run:
        print("  [--dry-run] 跳过写入")
        records_added = 0
    else:
        records_added = store_feedback_as_experience(
            predictions,
            feedback,
            store,
            product_id=args.product_id,
        )
        print(f"  写入 {records_added} 条经验记录")

    print_report(predictions, feedback, store, records_added, enricher)
    return 0


if __name__ == "__main__":
    sys.exit(main())
