"""P3.3 — Strategy Memory Adapter（策略经验适配器）。

连接 E17.7，但**不重造 Memory 层**：
- READ：直接 CALL `extract_patterns(graph)` 拿到 action-level 模式（strategy_type ×
  domain × action_type 的成功率 / 收入变化 / 置信度加成）。
- 维护：在 E17.7 之上的「strategy-level 经验」——`StrategyState` 持久化于
  `strategy_memory.jsonl`（与图谱存储解耦）。

学习规则（确定性）：
- 成功 → confidence 上浮、连续失败计数清零；
- 失败 → confidence 下浮、连续失败计数 +1；连续 5 次失败 → status=DISABLED。
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ceo_intelligence.growth_memory_graph.patterns import extract_patterns

from .models import (
    StrategyInsight,
    StrategyState,
    StrategyStatus,
    StrategyFeedback,
)

# 内置默认策略集（若 store 为空则以此播种；仅作冷启动，不覆盖学习结果）
DEFAULT_STRATEGIES: List[StrategyState] = [
    StrategyState(
        strategy_id="network_cleanup",
        dimension="monetization",
        parameters={"target": "low_ecpm"},
        confidence=0.6,
    ),
    StrategyState(
        strategy_id="aggressive_scale",
        dimension="ua",
        parameters={"budget_growth": 0.30},
        confidence=0.6,
    ),
    StrategyState(
        strategy_id="conservative_scale",
        dimension="ua",
        parameters={"budget_growth": 0.10},
        confidence=0.7,
    ),
    StrategyState(
        strategy_id="creative_fatigue_guard",
        dimension="creative",
        parameters={"refresh_days": 14},
        confidence=0.6,
    ),
]

# 学习超参
_CONF_UP = 0.05        # 单次成功对 confidence 的加成系数（乘以 reward）
_CONF_DOWN = 0.10      # 单次失败对 confidence 的固定下浮
_DISABLE_AFTER = 5     # 连续失败达到此数 → DISABLED


class StrategyMemoryAdapter:
    """E17.7 只读适配 + strategy-level 经验读写。"""

    def __init__(
        self,
        store_path: Optional[str] = None,
        default_states: Optional[List[StrategyState]] = None,
    ) -> None:
        self.store_path = store_path
        self._defaults = default_states or DEFAULT_STRATEGIES
        self._states: Dict[str, StrategyState] = self.load()

    # -- 加载 / 落盘 ---------------------------------------------------- #
    def load(self) -> Dict[str, StrategyState]:
        """从 store 读策略状态；无 store 或空则用默认集冷启动。"""
        states: Dict[str, StrategyState] = {}
        for s in self._defaults:
            # 深拷贝：避免把模块级默认对象原地改掉（会泄漏到其它实例/运行）
            states[s.strategy_id] = copy.deepcopy(s)
        if self.store_path and os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        st = StrategyState.from_dict(json.loads(line))
                        # 学习结果优先于冷启动默认值
                        states[st.strategy_id] = st
            except (json.JSONDecodeError, OSError):
                pass
        return states

    def save(self) -> None:
        if not self.store_path:
            return
        Path(self.store_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as fh:
            for st in self._states.values():
                fh.write(json.dumps(st.to_dict(), ensure_ascii=False) + "\n")

    # -- 状态访问 -------------------------------------------------------- #
    def all_states(self) -> Dict[str, StrategyState]:
        return dict(self._states)

    def ensure(self, strategy_id: str, dimension: str = "") -> StrategyState:
        st = self._states.get(strategy_id)
        if st is None:
            st = StrategyState(
                strategy_id=strategy_id,
                dimension=dimension or "unknown",
            )
            self._states[strategy_id] = st
        elif dimension and not st.dimension:
            st.dimension = dimension
        return st

    # -- 学习：应用反馈 -------------------------------------------------- #
    def apply_feedback(self, fb: StrategyFeedback) -> StrategyState:
        """把一条反馈折进对应策略状态（成功增信 / 失败降权）。"""
        st = self.ensure(fb.strategy_id)
        perf = st.performance
        if fb.outcome == "SUCCESS":
            perf["wins"] = int(perf.get("wins", 0)) + 1
            perf["consecutive_failures"] = 0
            st.confidence = min(1.0, st.confidence + _CONF_UP * max(0.0, fb.reward))
        elif fb.outcome == "FAILURE":
            perf["losses"] = int(perf.get("losses", 0)) + 1
            perf["consecutive_failures"] = int(perf.get("consecutive_failures", 0)) + 1
            st.confidence = max(0.0, st.confidence - _CONF_DOWN)
            if int(perf["consecutive_failures"]) >= _DISABLE_AFTER:
                st.status = StrategyStatus.DISABLED
        # NEUTRAL：记录但不动 confidence
        perf["samples"] = int(perf.get("wins", 0)) + int(perf.get("losses", 0))
        perf["reward_sum"] = float(perf.get("reward_sum", 0.0)) + fb.reward
        perf["last_outcome"] = fb.outcome
        return st

    # -- 读 E17.7：构建洞察 --------------------------------------------- #
    def build_insights(self, graph: Any = None) -> List[StrategyInsight]:
        """READ E17.7 patterns + 本地策略状态 → StrategyInsight 列表。

        优先采用 E17.7 的 action-level 历史（样本≥2），否则回退本地策略经验。
        零重算。
        """
        patterns = extract_patterns(graph) if graph is not None else []
        by_st: Dict[str, Any] = {p.strategy_type: p for p in patterns}

        insights: List[StrategyInsight] = []
        for sid, st in self._states.items():
            pat = by_st.get(sid)
            if pat and pat.samples >= 2:
                rate = pat.success_rate
                samples = pat.samples
                avg_reward = pat.avg_revenue_delta
            else:
                wins = int(st.performance.get("wins", 0))
                losses = int(st.performance.get("losses", 0))
                samples = wins + losses
                rate = (wins / samples) if samples else 0.0
                avg_reward = (
                    float(st.performance.get("reward_sum", 0.0)) / samples
                    if samples else 0.0
                )
            rec, rationale = self._recommend(st, rate, samples)
            insights.append(StrategyInsight(
                strategy_id=sid,
                dimension=st.dimension,
                historical_success_rate=rate,
                samples=samples,
                avg_reward=avg_reward,
                recommendation=rec,
                rationale=rationale,
            ))
        return insights

    @staticmethod
    def _recommend(st: StrategyState, rate: float, samples: int):
        if st.status == StrategyStatus.DISABLED:
            return ("disable",
                    "连续失败过多已停用；恢复须经 Simulation 闸门审批")
        if rate >= 0.7 and samples >= 3:
            return ("boost", f"历史成功率 {rate:.0%}，建议提高其优先级")
        if rate <= 0.4 and samples >= 5:
            return ("reduce", f"历史成功率低（{rate:.0%}），建议降低其权重")
        if samples > 0:
            return ("hold", "样本不足或表现波动，暂维持现状观察")
        return ("hold", "暂无执行样本，维持默认权重")


__all__ = ["StrategyMemoryAdapter", "DEFAULT_STRATEGIES"]
