"""E17.2 确定性规则引擎（无 LLM，auditable）。

每条规则消费 GameSignals，产出零或多个 GrowthOpportunity 候选。
阈值集中为常数，便于审计与调参。

规则与机会类型映射：
- R1 收入下降            → REVENUE_RECOVERY
- R2 UA 失血 (ROAS↓+花费↑) → UA_STOP_LOSS
- R3 Creative 疲劳        → CREATIVE_REFRESH
- R4 ASO 优化 (CVR↓+评分高) → ASO_OPTIMIZATION
- R5 UA 扩量 (ROAS高+预算小) → UA_SCALE
"""
from __future__ import annotations

from typing import List

from .models import GameSignals, GrowthOpportunity, OpportunityType

# --- 阈值 ---
REVENUE_DECLINE_TH = -0.20
UA_STOP_ROAS_TH = -0.15
UA_STOP_SPEND_TH = 0.20
CREATIVE_CTR_TH = -0.20
CREATIVE_FREQ_TH = 0.20
CREATIVE_FATIGUE_TH = 0.70
UA_SCALE_ROAS_TH = 1.5
UA_SCALE_BUDGET_TH = 0.33
ASO_CVR_TH = -0.15
ASO_RATING_TH = 4.0


def evaluate(
    sig: GameSignals, game_id: str, created_at: str = "", segment: str = "global"
) -> List[GrowthOpportunity]:
    out: List[GrowthOpportunity] = []
    if sig.revenue_growth <= REVENUE_DECLINE_TH:
        out.append(_revenue_recovery(sig, game_id, created_at, segment))
    if sig.roas_growth <= UA_STOP_ROAS_TH and sig.spend_growth >= UA_STOP_SPEND_TH:
        out.append(_ua_stop_loss(sig, game_id, created_at, segment))
    if sig.ctr_growth <= CREATIVE_CTR_TH and (
        sig.frequency_growth >= CREATIVE_FREQ_TH or sig.fatigue_score >= CREATIVE_FATIGUE_TH
    ):
        out.append(_creative_refresh(sig, game_id, created_at, segment))
    if sig.store_cvr_growth <= ASO_CVR_TH and sig.rating >= ASO_RATING_TH:
        out.append(_aso_optimization(sig, game_id, created_at, segment))
    if sig.roas >= UA_SCALE_ROAS_TH and sig.budget_level < UA_SCALE_BUDGET_TH:
        out.append(_ua_scale(sig, game_id, created_at, segment))
    return out


# --------------------------------------------------------------------------- #
# 各规则产出（确定性打分：impact / confidence / urgency / risk）
# --------------------------------------------------------------------------- #
def _base_confidence(sig: GameSignals) -> float:
    # 覆盖 domain 越多，基线置信越高
    return min(0.95, 0.55 + 0.08 * sig.coverage)


def _revenue_recovery(sig, gid, created_at, segment) -> GrowthOpportunity:
    drop = abs(sig.revenue_growth)
    impact = min(drop, 0.5)
    return GrowthOpportunity(
        game_id=gid,
        type=OpportunityType.REVENUE_RECOVERY,
        title="收入下滑修复",
        problem=f"日收入环比 {sig.revenue_growth:+.0%}，存在明显收入流失风险",
        evidence=[
            f"日收入环比 {sig.revenue_growth:+.1%}",
            f"当前日收入 ${sig.revenue:,.0f}",
        ],
        expected_impact=impact,
        confidence=min(0.95, 0.6 + min(drop, 0.3)),
        urgency=min(0.95, 0.6 + min(drop, 0.35)),
        risk=0.40,
        suggested_actions=[
            "定位收入下滑根因（留存 / 付费 / 买量质量）",
            "检查近期版本与活动变更",
            "针对付费点做 monetization 实验",
        ],
        segment=segment,
        created_at=created_at,
    )


def _ua_stop_loss(sig, gid, created_at, segment) -> GrowthOpportunity:
    roas_drop = abs(sig.roas_growth)
    return GrowthOpportunity(
        game_id=gid,
        type=OpportunityType.UA_STOP_LOSS,
        title="UA 止损",
        problem=f"ROAS 环比 {sig.roas_growth:+.0%} 同时花费环比 +{sig.spend_growth:.0%}，投放在失血",
        evidence=[
            f"ROAS 环比 {sig.roas_growth:+.1%}",
            f"花费环比 {sig.spend_growth:+.1%}",
            f"当前 ROAS {sig.roas:.2f}",
        ],
        expected_impact=min(roas_drop, 0.4),
        confidence=0.72,
        urgency=0.82,
        risk=0.55,
        suggested_actions=[
            "暂停低效投放计划",
            "下调预算上限",
            "排查渠道质量与归因异常",
        ],
        segment=segment,
        created_at=created_at,
    )


def _creative_refresh(sig, gid, created_at, segment) -> GrowthOpportunity:
    return GrowthOpportunity(
        game_id=gid,
        type=OpportunityType.CREATIVE_REFRESH,
        title="素材刷新",
        problem="CTR 下降叠加素材疲劳，创意效用衰减",
        evidence=[
            f"CTR 环比 {sig.ctr_growth:+.1%}",
            f"素材疲劳 {sig.fatigue_score:.0%}",
            f"曝光频次环比 {sig.frequency_growth:+.1%}",
        ],
        expected_impact=0.20,
        confidence=min(0.95, 0.68 + sig.fatigue_score * 0.2),
        urgency=0.62,
        risk=0.30,
        suggested_actions=[
            "生成新一轮素材（20 变体）",
            "CLIP / 视觉评估筛选 Top",
            "Meta 小流量 A/B 测试",
        ],
        segment=segment,
        created_at=created_at,
    )


def _aso_optimization(sig, gid, created_at, segment) -> GrowthOpportunity:
    cvr_drop = abs(sig.store_cvr_growth)
    return GrowthOpportunity(
        game_id=gid,
        type=OpportunityType.ASO_OPTIMIZATION,
        title="商店优化",
        problem=f"商店转化率环比 {sig.store_cvr_growth:+.0%}，但评分 {sig.rating:.1f} 健康，有优化空间",
        evidence=[
            f"商店 CVR 环比 {sig.store_cvr_growth:+.1%}",
            f"评分 {sig.rating:.1f}",
            f"排名 {sig.ranking:.0f}",
        ],
        expected_impact=min(0.15 + cvr_drop, 0.3),
        confidence=0.70,
        urgency=0.55,
        risk=0.25,
        suggested_actions=[
            "优化商店截图 / 视频",
            "A/B 标题与关键词",
            "提升 store CVR",
        ],
        segment=segment,
        created_at=created_at,
    )


def _ua_scale(sig, gid, created_at, segment) -> GrowthOpportunity:
    return GrowthOpportunity(
        game_id=gid,
        type=OpportunityType.UA_SCALE,
        title="UA 扩量",
        problem=f"ROAS {sig.roas:.2f} 健康且预算偏小，具备扩量空间",
        evidence=[
            f"ROAS {sig.roas:.2f}（≥{UA_SCALE_ROAS_TH}）",
            f"预算水平 {sig.budget_level:.0%}（<{UA_SCALE_BUDGET_TH:.0%}）",
        ],
        expected_impact=0.30,
        confidence=0.75,
        urgency=0.50,
        risk=0.45,
        suggested_actions=[
            "逐步 +20% 预算",
            "扩量至高 ROAS 渠道",
            "监控 CPI 漂移",
        ],
        segment=segment,
        created_at=created_at,
    )
