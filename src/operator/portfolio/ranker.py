"""P3.4.2 — Portfolio Ranking Engine.

多游戏排序（6 因子加权 → PortfolioScore）。
**不计算新业务指标**，全部字段只读消费 GamePortfolioSnapshot 既有值。

纪律：
- ✅ 排序是 ranker 的唯一职责（不分配预算、不 guard、不推荐 ActionKind）
- ✅ 全部因子来自 snapshot（不触碰 E17.3 / Provider / SafeExecutor）
- ❌ 不在本模块内「重算 ROAS / spend / revenue」
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.operator.portfolio.models import GamePortfolioSnapshot
from src.operator.portfolio.ranking_models import (
    AllocationCandidate,
    PortfolioScore,
    PortfolioVerdict,
)
from src.ceo_intelligence.growth_memory_graph.signals import (
    KnowledgeSignal,
    experience_adjustment,
)


class PortfolioRanker:
    """多游戏排序引擎。

    输入：List[GamePortfolioSnapshot]
    输出：List[AllocationCandidate]（含 portfolio_score、rank、recommended_action 初判，
          action_state 留待 PortFolioGuard 填充）
    """

    def rank(
        self,
        snapshots: List[GamePortfolioSnapshot],
        knowledge_signals: Optional[Dict[str, "KnowledgeSignal"]] = None,
    ) -> List[AllocationCandidate]:
        """排序入口。空列表 → 空列表。

        ``knowledge_signals``（可选，key=game_id）：P3.5.1 经验信号。
        仅做经验修正（base + 经验分 - 风险惩罚），**不重算 ROAS**；
        缺省为 None → 行为与 P3.4.2 完全一致（零回归）。
        """
        if not snapshots:
            return []

        # 1. 算分 + 经验修正（augmented score 仅用于排序/优先级）
        scored = []
        for snap in snapshots:
            score = PortfolioScore.compute(snap)
            sig = knowledge_signals.get(snap.game_id) if knowledge_signals else None
            aug = score.score
            if sig is not None:
                exp, pen = experience_adjustment(sig)
                aug = score.score + exp - pen
            scored.append((snap, score, aug, sig))

        # 2. 降序排序：augmented score → revenue → game_id
        scored.sort(
            key=lambda x: (
                -x[2],
                -(x[0].revenue if x[0].revenue is not None else float("-inf")),
                x[0].game_id,
            )
        )

        # 3. 构建候选（初判 action，action_state 留空待 guard 填）
        candidates: List[AllocationCandidate] = []
        for rank_idx, (snap, score, aug, sig) in enumerate(scored, start=1):
            verdict = self._initial_verdict(score, snap.lifecycle_stage)
            rev = snap.revenue if snap.revenue is not None else 0.0
            reason = self._build_initial_reason(verdict, score, snap)
            kn_sig = None
            kn_adj = 0.0
            if sig is not None:
                exp, pen = experience_adjustment(sig)
                kn_adj = (score.score + exp - pen) - score.score
                kn_sig = sig.to_dict()
                reason = (
                    f"{reason} | [experience] sr={sig.historical_success_rate:.0%} "
                    f"cases={sig.similar_case_count} adj={kn_adj:+.2f}"
                )
                if sig.risk_flags:
                    reason = f"{reason} risk={','.join(sig.risk_flags)}"
            candidates.append(
                AllocationCandidate(
                    game_id=snap.game_id,
                    rank=rank_idx,
                    portfolio_score=score.score,
                    recommended_action=verdict,
                    recommended_budget_delta=0.0,  # allocator 填
                    priority=round(aug * 100, 2),
                    confidence=snap.confidence if snap.confidence is not None else 0.0,
                    action_state="",   # guard 填
                    reason=reason,
                    strategy_score=snap.strategy_score if snap.strategy_score is not None else 0.0,
                    knowledge_signal=kn_sig,
                    knowledge_adjustment=kn_adj,
                )
            )
        return candidates

    # ------------------------------------------------------------------ #
    # 初判规则（确定性）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _initial_verdict(
        score: PortfolioScore,
        lifecycle_stage: Optional[str],
    ) -> PortfolioVerdict:
        """根据评分与生命周期初判组合动作（未经 Guard，且不触碰执行动作）。"""
        stage_lower = lifecycle_stage.lower() if lifecycle_stage else ""

        # SCALE：高评分 + 扩量阶段
        if score.score >= 0.6 and stage_lower in ("scale", "ua_test"):
            return PortfolioVerdict.SCALE

        # SUNSET：无论评分，生命末期
        if stage_lower == "kill":
            return PortfolioVerdict.SUNSET

        # REDUCE：低评分
        if score.score < 0.25:
            return PortfolioVerdict.REDUCE

        # MAINTAIN：中等评分
        if score.score >= 0.4:
            return PortfolioVerdict.MAINTAIN

        # 其余 → MAINTAIN（保守兜底）
        return PortfolioVerdict.MAINTAIN

    @staticmethod
    def _build_initial_reason(
        verdict: PortfolioVerdict,
        score: PortfolioScore,
        snap: GamePortfolioSnapshot,
    ) -> str:
        """生成初判理由（引用证据值，不触发额外计算）。"""
        parts = [f"score={score.score:.4f}"]

        if score.revenue_quality < 0.3:
            parts.append(f"roas_quality={score.revenue_quality:.2f}")
        if score.confidence < 0.5:
            parts.append(f"confidence={score.confidence:.2f}")
        if score.growth_potential < 0.3:
            parts.append(f"lifecycle={snap.lifecycle_stage}")
        if score.execution_health < 0.3:
            parts.append(f"exec_health={score.execution_health:.2f}")
        if verdict == PortfolioVerdict.SCALE:
            parts.append("high_potential")
        elif verdict == PortfolioVerdict.SUNSET:
            parts.append("lifecycle_end")
        elif verdict == PortfolioVerdict.REDUCE:
            parts.append("low_score")
        else:
            parts.append("maintain")

        return " | ".join(parts)


def build_portfolio_ranker() -> PortfolioRanker:
    """构建 ranker（纯函数，无外部依赖）。"""
    return PortfolioRanker()
