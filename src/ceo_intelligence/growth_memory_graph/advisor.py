"""
P3.5.1 — Growth Knowledge Advisor（知识增强决策顾问，只读）。

把 Growth Knowledge Graph 接进两个既有决策入口，让 AI CEO「用记忆改变行为」：

  - ``advise_portfolio(game)``   -> ``KnowledgeSignal``   （喂 P3.4 Portfolio Ranker）
  - ``advise_strategy(proposal)`` -> ``KnowledgeSignal``   （喂 P3.3 Strategy Loop）

纪律（与 P3.5 一致，且更严——只读）：

- 不写回任何源、不调 ``consolidate``、不调 Provider / SafeExecutor / DecisionEngine；
- ``real_api_called`` 恒 ``False``；
- **fail-open**：图不可用 / 查询异常 → 返回空信号（confidence=0），绝不中断主链。

P3.5.2（防自我强化契约）：消费 CEO_DECISION 时按来源带权，杜绝「AI 自己相信自己」：

- 外部事实（Execution / Strategy 结果）      weight = 1.0
- CEO 决策实际结果（自生成，半信）            weight = 0.5
- CEO 决策模拟结果（最弱）                    weight = 0.2

``historical_success_rate`` 用加权平均，``confidence`` 用加权有效样本数——
10 条外部失败 + 10 条 CEO 自报成功 ≠ 100% 成功率。
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from .knowledge import GrowthKnowledgeGraph
from .signals import (
    KnowledgeSignal,
    knowledge_adjusted_confidence,
    knowledge_requires_approval,
)


# 风险阈值（确定性，可解释）
_LOW_SUCCESS_RATE = 0.4
_HIGH_ROLLBACK_RATE = 0.3
_MIN_SAMPLES_FOR_RISK = 3
_CONFIDENCE_K = 3  # Laplace 式置信：case_count / (case_count + K)

# P3.5.2 经验来源权重（防自我强化）
_WEIGHT_EXTERNAL = 1.0       # 外部事实（Execution/Strategy 结果）
_WEIGHT_CEO_REALIZED = 0.5   # CEO 决策实际结果（自生成，半信）
_WEIGHT_CEO_SIMULATED = 0.2  # CEO 决策模拟结果（最弱）

# 组合决策里视为「负面历史」的 verdict
_NEGATIVE_PORTFOLIO = {"reduce", "sunset"}


def _game_id(game: Any) -> str:
    if game is None:
        return ""
    gid = getattr(game, "game_id", None)
    if gid:
        return str(gid)
    return str(game)


def _keyword_overlap(text: str, hay: str) -> bool:
    """取 text 中 >=4 字符的有意义 token 做子串匹配（不依赖分词库）。"""
    tokens = [t for t in text.replace("_", " ").split() if len(t) >= 4]
    return any(tok in hay for tok in tokens)


class GrowthKnowledgeAdvisor:
    """经验顾问（只读，包一层 GrowthKnowledgeGraph）。

    ``quality``（可选）：P3.5.3 ``MemoryQualityGovernor``——注入后在折叠
    CEO_DECISION 经验前先做质量过滤（低质/未验证/过期经验不参与建议）。
    None → 不启用质量门（零回归，与 P3.5.2 行为一致）。
    """

    def __init__(
        self,
        graph: Optional[GrowthKnowledgeGraph] = None,
        quality: Optional[Any] = None,
    ) -> None:
        self.graph = graph
        self.quality = quality

    @property
    def real_api_called(self) -> bool:
        return False

    # ------------------------------------------------------------------ #
    # 第一接入点：P3.4 Portfolio Ranker
    # ------------------------------------------------------------------ #
    def advise_portfolio(self, game: Any) -> KnowledgeSignal:
        gid = _game_id(game)
        if self.graph is None or not gid:
            return KnowledgeSignal()  # fail-open：空信号
        try:
            return self._advise_portfolio(gid)
        except Exception:
            # 任何图异常都不应中断主链
            return KnowledgeSignal()

    def _advise_portfolio(self, game_id: str) -> KnowledgeSignal:
        similar = self.graph.similar_games(game_id)
        if not similar:
            return KnowledgeSignal()  # 无相似经验 → 空信号（confidence 0）

        # 收集相似游戏的全部经验证据（P3.5.2 按来源带权，防自我强化）
        weighted: List[Tuple[float, float]] = []   # (success_rate, weight)
        rb_list: List[float] = []
        rec_neg: List[str] = []
        rec_total = 0
        for s in similar:
            info = self.graph.why_game_succeeded(s["game_id"])
            for st in info.get("strategy_results", []):
                weighted += [(float(st.get("success_rate", 0.0)), _WEIGHT_EXTERNAL)]
            for ex in info.get("execution_outcomes", []):
                weighted += [(float(ex.get("success_rate", 0.0)), _WEIGHT_EXTERNAL)]
                rb_list += [ex.get("rolled_back_rate", 0.0)]
            for pd in info.get("portfolio_decisions", []):
                rec_total += 1
                if (pd.get("recommendation") or "") in _NEGATIVE_PORTFOLIO:
                    rec_neg += [s["game_id"]]
            # P3.5.2 闭环：相似游戏历史 CEO 决策（决策+知识+结果）带权并入
            # P3.5.3：注入质量门时先过滤（低质/未验证/过期经验不参与）
            ceo_recs = info.get("ceo_decisions", [])
            if self.quality is not None:
                ceo_recs = self.quality.filter_records(ceo_recs)
            for cd in ceo_recs:
                oc = cd.get("outcome") or {}
                sr = oc.get("success_rate")
                w = (
                    _WEIGHT_CEO_SIMULATED
                    if oc.get("simulated") else _WEIGHT_CEO_REALIZED
                )
                if sr is not None:
                    weighted += [(float(sr), w)]
                ks = cd.get("knowledge_signal") or {}
                rflags = ks.get("risk_flags") or []
                failed = (oc.get("success") is False) or (
                    sr is not None and float(sr) < _LOW_SUCCESS_RATE
                )
                if rflags and failed:
                    rec_neg += [s["game_id"]]

        total_w = sum(w for _, w in weighted)
        hist_sr = (
            (sum(sr * w for sr, w in weighted) / total_w) if total_w else 0.0
        )
        # 加权有效样本（排除 rb 重复计数；自生成经验只算一半/两成，防自嗨）
        eff_samples = total_w + rec_total
        case_count = len(weighted) + len(rb_list) + rec_total

        # risk flags
        risk_flags: List[str] = []
        if hist_sr < _LOW_SUCCESS_RATE and case_count >= _MIN_SAMPLES_FOR_RISK:
            risk_flags += ["low_historical_success"]
        if rb_list and (sum(rb_list) / len(rb_list)) > _HIGH_ROLLBACK_RATE:
            risk_flags += ["high_rollback_rate"]
        if rec_neg:
            risk_flags += ["historical_scale_failure"]

        # confidence：加权有效样本（自生成经验只算一半/两成，防自嗨）
        confidence = eff_samples / (eff_samples + _CONFIDENCE_K)

        # evidence
        ev_lines: List[str] = []
        if similar:
            top = similar[0]
            ev_lines += [
                f"{len(similar)} 个相似游戏（最强重叠 {top['game_id']} "
                f"共享 {top['shared_count']} 信号）"
            ]
        ev_lines += [f"历史成功率 {hist_sr:.0%}（{case_count} 条经验）"]
        if risk_flags:
            ev_lines += ["风险标记：" + ", ".join(risk_flags)]

        return KnowledgeSignal(
            confidence=confidence,
            historical_success_rate=hist_sr,
            similar_case_count=case_count,
            risk_flags=risk_flags,
            evidence=ev_lines,
        )

    # ------------------------------------------------------------------ #
    # 第二接入点：P3.3 Strategy Loop
    # ------------------------------------------------------------------ #
    def advise_strategy(
        self, proposal: Any, game_id: Optional[str] = None
    ) -> KnowledgeSignal:
        if self.graph is None:
            return KnowledgeSignal()
        try:
            return self._advise_strategy(proposal, game_id)
        except Exception:
            return KnowledgeSignal()

    def _advise_strategy(
        self, proposal: Any, game_id: Optional[str]
    ) -> KnowledgeSignal:
        text = " ".join(
            [
                getattr(proposal, "current_strategy", ""),
                getattr(proposal, "proposed_change", ""),
                getattr(proposal, "expected_impact", ""),
            ]
        ).lower()

        # 1) 匹配 graph 里的历史策略结果（strategy_id / dimension / rationale）
        matched_sr: List[float] = []
        matched_samples = 0
        matched_ids: List[str] = []
        for r in self.graph.strategy_results_by_success(descending=True):
            hay = " ".join(
                [r.strategy_id, r.dimension, r.rationale, r.recommendation]
            ).lower()
            if _keyword_overlap(text, hay):
                matched_sr += [r.success_rate]
                matched_samples += max(1, r.samples)
                matched_ids += [r.strategy_id]

        # 2) 若给了 game_id，叠加相似游戏经验 + 本游戏历史 CEO 决策（P3.5.2 带权）
        sr_extra: List[float] = []
        ceo_extra_w: List[Tuple[float, float]] = []
        ceo_extra_count = 0
        ceo_eff = 0.0
        ceo_advice_failed = False
        if game_id:
            game_info = self.graph.why_game_succeeded(game_id)
            for s in self.graph.similar_games(game_id):
                info = self.graph.why_game_succeeded(s["game_id"])
                for st in info.get("strategy_results", []):
                    sr_extra += [st.get("success_rate", 0.0)]
            # P3.5.2 闭环：本游戏历史 CEO 决策（知识+结果）带权并入
            # P3.5.3：注入质量门时先过滤（低质/未验证/过期经验不参与）
            ceo_recs = game_info.get("ceo_decisions", [])
            if self.quality is not None:
                ceo_recs = self.quality.filter_records(ceo_recs)
            for cd in ceo_recs:
                oc = cd.get("outcome") or {}
                sr = oc.get("success_rate")
                w = (
                    _WEIGHT_CEO_SIMULATED
                    if oc.get("simulated") else _WEIGHT_CEO_REALIZED
                )
                if sr is not None:
                    ceo_extra_w += [(float(sr), w)]
                ceo_extra_count += 1
                ceo_eff += w
                ks = cd.get("knowledge_signal") or {}
                rflags = ks.get("risk_flags") or []
                failed = (oc.get("success") is False) or (
                    sr is not None and float(sr) < _LOW_SUCCESS_RATE
                )
                if rflags and failed:
                    ceo_advice_failed = True

        base_w = [(float(sr), _WEIGHT_EXTERNAL) for sr in matched_sr + sr_extra]
        all_w = base_w + ceo_extra_w
        if not all_w and matched_samples == 0:
            return KnowledgeSignal()
        total_w = sum(w for _, w in all_w)
        hist_sr = (sum(sr * w for sr, w in all_w) / total_w) if total_w else 0.0
        case_count = matched_samples + len(sr_extra) + ceo_extra_count
        eff_samples = (
            sum(w for _, w in base_w)
            + (matched_samples - len(matched_sr))
            + ceo_eff
        )

        risk_flags: List[str] = []
        if hist_sr < _LOW_SUCCESS_RATE and case_count >= _MIN_SAMPLES_FOR_RISK:
            risk_flags += ["historical_failure_pattern"]
            if "retention" in text:
                risk_flags += ["retention_drop_risk"]
        if ceo_advice_failed:
            risk_flags += ["knowledge_advice_failed"]

        confidence = eff_samples / (eff_samples + _CONFIDENCE_K)

        ev_lines = []
        if matched_ids:
            ev_lines += [f"匹配历史策略：{', '.join(matched_ids[:3])}"]
        ev_lines += [f"历史成功率 {hist_sr:.0%}（{case_count} 样本）"]
        if risk_flags:
            ev_lines += ["风险标记：" + ", ".join(risk_flags)]

        return KnowledgeSignal(
            confidence=confidence,
            historical_success_rate=hist_sr,
            similar_case_count=case_count,
            risk_flags=risk_flags,
            evidence=ev_lines,
        )


__all__ = ["GrowthKnowledgeAdvisor", "knowledge_adjusted_confidence",
           "knowledge_requires_approval"]
