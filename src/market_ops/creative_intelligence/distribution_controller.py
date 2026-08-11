"""Distribution Controller — 收敛约束 3/3

Distribution Control: 流量分配约束 + budget gating, 防止 Facebook 反向破坏分布。

核心约束:
- Top 20% → 70% budget (exploitation 主导)
- Middle 30% → 20% budget (维持 diversity)
- Bottom 50% → 10% budget (最小投入, 防止过早淘汰)
- 冷启动新品有独立预算保护

数据流:
    FinalBandit.rank() → DistributionController.allocate() → budget_plan
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import exp
from pathlib import Path
from typing import Any


@dataclass
class BudgetAllocation:
    """单个 creative 的预算分配"""
    creative_id: str
    theta: float
    sigma: float
    trials: int
    tier: str  # "top" | "middle" | "bottom" | "cold_start"
    budget_share: float   # 0~1, 占总预算比例
    reason: str


@dataclass
class BudgetPlan:
    """一次完整的预算分配方案"""
    project: str
    total_budget: float
    allocations: list[BudgetAllocation]
    tier_summary: dict[str, float]  # tier → budget%
    meta: dict[str, Any] = field(default_factory=dict)


class DistributionController:
    """流量分配控制器

    核心规则:
    - Top 20% → 70% budget
    - Middle 30% → 20% budget
    - Bottom 50% → 10% budget
    - 冷启动新品: 独立预算 (不受排名约束)

    用法:
        controller = DistributionController()
        bandit_ranking = bandit.rank()  # [{creative_id, theta, sigma, trials}, ...]
        plan = controller.allocate(project, bandit_ranking, total_budget=1000)
    """

    # 默认分配比例
    TOP_RATIO = 0.20    # 前 20%
    MID_RATIO = 0.30    # 中 30%
    BOT_RATIO = 0.50    # 后 50%

    TOP_BUDGET = 0.70   # 前 20% 拿 70% 预算
    MID_BUDGET = 0.20   # 中 30% 拿 20% 预算
    BOT_BUDGET = 0.10   # 后 50% 拿 10% 预算

    # 冷启动保护
    COLD_START_MIN_BUDGET = 15.0      # 新品最低日预算
    COLD_START_MAX_CREATIVES = 3      # 同时保护的新品数量上限
    COLD_START_MIN_TRIALS = 5         # 最少试验次数后解除保护

    # 单 creative 最低预算 (防止完全归零)
    MIN_CREATIVE_BUDGET = 5.0

    def __init__(self, memory_path: str | Path | None = None):
        self._cold_start_creatives: dict[str, int] = {}  # creative_id → trials
        self._memory_path = Path(memory_path) if memory_path else None
        if self._memory_path and self._memory_path.exists():
            self._load()

    # ========================================================================
    # 核心: allocate
    # ========================================================================

    def allocate(
        self,
        project: str,
        ranking: list[dict[str, Any]],
        total_budget: float = 1000.0,
        cold_start_ids: list[str] | None = None,
    ) -> BudgetPlan:
        """分配预算。

        Args:
            project: 项目名
            ranking: bandit.rank() 的输出, 按 theta DESC 排序
            total_budget: 总预算
            cold_start_ids: 冷启动新品 creative_id 列表

        Returns:
            BudgetPlan
        """
        n = len(ranking)
        if n == 0:
            return BudgetPlan(project=project, total_budget=total_budget, allocations=[], tier_summary={})

        # 1. 分离冷启动新品
        cold_ids = set(cold_start_ids or [])
        cold_creatives = [r for r in ranking if r["creative_id"] in cold_ids]
        warm_creatives = [r for r in ranking if r["creative_id"] not in cold_ids]

        # 冷启动预算: 取 min(TOP_BUDGET * 0.15, 冷启动数量 * COLD_START_MIN_BUDGET)
        n_cold = min(len(cold_creatives), self.COLD_START_MAX_CREATIVES)
        cold_budget = min(
            total_budget * 0.15,
            n_cold * self.COLD_START_MIN_BUDGET,
        )
        warm_budget = total_budget - cold_budget

        # 2. 对 warm creatives 分层
        n_warm = len(warm_creatives)
        if n_warm == 0:
            # 全冷启动
            allocations = self._allocate_flat(cold_creatives, cold_budget, "cold_start")
            plan = BudgetPlan(
                project=project, total_budget=total_budget,
                allocations=allocations,
                tier_summary={"cold_start": cold_budget / total_budget},
            )
            return plan

        top_n = max(1, int(n_warm * self.TOP_RATIO))
        mid_n = max(1, int(n_warm * self.MID_RATIO))
        bot_n = n_warm - top_n - mid_n

        top_creatives = warm_creatives[:top_n]
        mid_creatives = warm_creatives[top_n:top_n + mid_n]
        bot_creatives = warm_creatives[top_n + mid_n:]

        top_budget = warm_budget * self.TOP_BUDGET
        mid_budget = warm_budget * self.MID_BUDGET
        bot_budget = warm_budget * self.BOT_BUDGET

        # 3. 层内按 theta 比例分配
        top_alloc = self._allocate_proportional(top_creatives, top_budget, "top")
        mid_alloc = self._allocate_proportional(mid_creatives, mid_budget, "middle")
        bot_alloc = self._allocate_proportional(bot_creatives, bot_budget, "bottom")
        cold_alloc = self._allocate_flat(cold_creatives[:self.COLD_START_MAX_CREATIVES], cold_budget, "cold_start")

        all_allocations = top_alloc + mid_alloc + bot_alloc + cold_alloc

        tier_summary = {
            "top": round(top_budget / total_budget, 4),
            "middle": round(mid_budget / total_budget, 4),
            "bottom": round(bot_budget / total_budget, 4),
            "cold_start": round(cold_budget / total_budget, 4),
        }

        plan = BudgetPlan(
            project=project,
            total_budget=total_budget,
            allocations=all_allocations,
            tier_summary=tier_summary,
            meta={
                "n_total": n,
                "n_warm": n_warm,
                "n_cold": n_cold,
                "top_n": top_n,
                "mid_n": mid_n,
                "bot_n": bot_n,
            },
        )

        self._save()
        return plan

    def allocate_softmax(
        self,
        project: str,
        ranking: list[dict[str, Any]],
        total_budget: float,
        temperature: float,
        cold_start_ids: list[str] | None = None,
    ) -> BudgetPlan:
        """退火预算分配: budget_i ∝ softmax(theta_i / T)

        高温 (T 大) → 接近均匀分配 (广泛探索)
        低温 (T 小) → 极度集中赢家 (纯利用)

        Args:
            temperature: 来自 AnnealingController.temperature
        """
        n = len(ranking)
        if n == 0:
            return BudgetPlan(project=project, total_budget=total_budget, allocations=[], tier_summary={})

        # 分离冷启动
        cold_ids = set(cold_start_ids or [])
        cold_creatives = [r for r in ranking if r["creative_id"] in cold_ids]
        warm_creatives = [r for r in ranking if r["creative_id"] not in cold_ids]

        n_cold = min(len(cold_creatives), self.COLD_START_MAX_CREATIVES)
        cold_budget = min(total_budget * 0.15, n_cold * self.COLD_START_MIN_BUDGET)
        warm_budget = total_budget - cold_budget

        if not warm_creatives:
            allocations = self._allocate_flat(cold_creatives, cold_budget, "cold_start")
            return BudgetPlan(project=project, total_budget=total_budget,
                              allocations=allocations, tier_summary={"cold_start": 1.0})

        # softmax(theta_i / T)
        thetas = [c["theta"] for c in warm_creatives]
        T = max(temperature, 1e-6)
        scaled = [t / T for t in thetas]
        max_val = max(scaled)
        exps = [exp(s - max_val) for s in scaled]  # 数值稳定
        total_exp = sum(exps)
        weights = [e / total_exp for e in exps] if total_exp > 0 else [1.0 / len(warm_creatives)] * len(warm_creatives)

        # 分配 tier: 基于权重
        allocations = []
        for c, w in zip(warm_creatives, weights):
            amount = w * warm_budget
            # 根据权重判断 tier
            if w >= 0.3:
                tier = "top"
            elif w >= 0.1:
                tier = "middle"
            else:
                tier = "bottom"
            allocations.append(BudgetAllocation(
                creative_id=c["creative_id"],
                theta=c["theta"],
                sigma=c.get("sigma", 0),
                trials=c.get("trials", 0),
                tier=tier,
                budget_share=round(w, 4),
                reason=f"T={temperature:.3f}, softmax_weight={w:.3f}",
            ))

        # 冷启动
        cold_alloc = self._allocate_flat(cold_creatives[:self.COLD_START_MAX_CREATIVES], cold_budget, "cold_start")
        all_allocations = allocations + cold_alloc

        # tier summary
        tier_budgets: dict[str, float] = {}
        for a in all_allocations:
            tier_budgets[a.tier] = tier_budgets.get(a.tier, 0) + a.budget_share

        plan = BudgetPlan(
            project=project,
            total_budget=total_budget,
            allocations=all_allocations,
            tier_summary={k: round(v, 4) for k, v in tier_budgets.items()},
            meta={
                "n_total": n,
                "temperature": round(temperature, 4),
                "allocation_mode": "softmax",
            },
        )

        self._save()
        return plan

    # ========================================================================
    # Policy Network 分配 — 替代 allocate_softmax(theta/T)
    # ========================================================================

    def allocate_from_policy(
        self,
        project: str,
        policy_predictions: list[dict[str, Any]],
        total_budget: float,
        cold_start_ids: list[str] | None = None,
    ) -> BudgetPlan:
        """Policy Network 驱动的预算分配 — 替代 theta/T softmax

        输入是 PolicyModel.predict_for_creatives() 的输出:
          [{creative_id, serve_prob, budget_weight, exploration_score, ctr_pred, roas_pred, risk_pred}, ...]

        核心逻辑:
          budget_i = total_budget * serve_prob_i
          tier 基于 serve_prob 分桶

        Args:
            project: 项目名
            policy_predictions: PolicyModel 预测结果
            total_budget: 总预算
            cold_start_ids: 冷启动 creative_id 列表

        Returns:
            BudgetPlan
        """
        n = len(policy_predictions)
        if n == 0:
            return BudgetPlan(project=project, total_budget=total_budget, allocations=[], tier_summary={})

        # 1. 分离冷启动
        cold_ids = set(cold_start_ids or [])
        cold_preds = [p for p in policy_predictions if p["creative_id"] in cold_ids]
        warm_preds = [p for p in policy_predictions if p["creative_id"] not in cold_ids]

        n_cold = min(len(cold_preds), self.COLD_START_MAX_CREATIVES)
        cold_budget = min(total_budget * 0.15, n_cold * self.COLD_START_MIN_BUDGET)
        warm_budget = total_budget - cold_budget

        if not warm_preds:
            allocations = [
                BudgetAllocation(
                    creative_id=p["creative_id"],
                    theta=p.get("roas_pred", 0),
                    sigma=p.get("risk_pred", 0),
                    trials=0,
                    tier="cold_start",
                    budget_share=round(1.0 / max(n_cold, 1), 4),
                    reason="policy: cold_start only",
                )
                for p in cold_preds[:self.COLD_START_MAX_CREATIVES]
            ]
            return BudgetPlan(project=project, total_budget=total_budget,
                              allocations=allocations, tier_summary={"cold_start": 1.0})

        # 2. 按 serve_prob 归一化 (确保 sum=1)
        raw_probs = [p["serve_prob"] for p in warm_preds]
        total_prob = sum(raw_probs)
        if total_prob <= 0:
            norm_probs = [1.0 / len(warm_preds)] * len(warm_preds)
        else:
            norm_probs = [p / total_prob for p in raw_probs]

        # 3. 分配 budget
        allocations = []
        for pred, prob in zip(warm_preds, norm_probs):
            # 根据概率判断 tier
            if prob >= 0.3:
                tier = "top"
            elif prob >= 0.1:
                tier = "middle"
            else:
                tier = "bottom"

            allocations.append(BudgetAllocation(
                creative_id=pred["creative_id"],
                theta=pred.get("roas_pred", 0),
                sigma=pred.get("risk_pred", 0),
                trials=0,
                tier=tier,
                budget_share=round(prob, 4),
                reason=(f"policy: serve_prob={pred['serve_prob']:.4f}, "
                        f"roas_pred={pred.get('roas_pred', 0):.3f}, "
                        f"risk={pred.get('risk_pred', 0):.3f}"),
            ))

        # 4. 冷启动
        cold_alloc = [
            BudgetAllocation(
                creative_id=p["creative_id"],
                theta=0, sigma=0, trials=0,
                tier="cold_start",
                budget_share=round(1.0 / max(n_cold, 1), 4),
                reason="policy: cold_start",
            )
            for p in cold_preds[:self.COLD_START_MAX_CREATIVES]
        ]
        all_allocations = allocations + cold_alloc

        # 5. tier summary
        tier_budgets: dict[str, float] = {}
        for a in all_allocations:
            tier_budgets[a.tier] = tier_budgets.get(a.tier, 0) + a.budget_share

        plan = BudgetPlan(
            project=project,
            total_budget=total_budget,
            allocations=all_allocations,
            tier_summary={k: round(v, 4) for k, v in tier_budgets.items()},
            meta={
                "n_total": n,
                "n_warm": len(warm_preds),
                "n_cold": n_cold,
                "allocation_mode": "policy_network",
            },
        )

        self._save()
        return plan

    # ========================================================================
    # 内部: 分配算法
    # ========================================================================

    def _allocate_proportional(
        self, creatives: list[dict[str, Any]], budget: float, tier: str
    ) -> list[BudgetAllocation]:
        """层内按 theta 比例分配 (theta 可为负, shift 到正数后分配)"""
        if not creatives:
            return []

        thetas = [max(c["theta"], -0.5) + 0.5 for c in creatives]  # shift 到正数
        total_theta = sum(thetas)
        if total_theta <= 0:
            # 全平摊
            return self._allocate_flat(creatives, budget, tier)

        allocations = []
        for c, t in zip(creatives, thetas):
            share = t / total_theta
            amount = share * budget
            allocations.append(BudgetAllocation(
                creative_id=c["creative_id"],
                theta=c["theta"],
                sigma=c.get("sigma", 0),
                trials=c.get("trials", 0),
                tier=tier,
                budget_share=round(share, 4),
                reason=f"theta={c['theta']:.3f}, share={share:.1%}",
            ))
        return allocations

    def _allocate_flat(
        self, creatives: list[dict[str, Any]], budget: float, tier: str
    ) -> list[BudgetAllocation]:
        """平摊 (冷启动)"""
        if not creatives:
            return []
        n = len(creatives)
        share = 1.0 / n
        return [
            BudgetAllocation(
                creative_id=c["creative_id"],
                theta=c["theta"],
                sigma=c.get("sigma", 0),
                trials=c.get("trials", 0),
                tier=tier,
                budget_share=round(share, 4),
                reason=f"flat allocation, {n} creatives",
            )
            for c in creatives
        ]

    # ========================================================================
    # 冷启动管理
    # ========================================================================

    def register_cold_start(self, creative_id: str) -> None:
        self._cold_start_creatives[creative_id] = 0

    def update_cold_start_trials(self, creative_id: str, trials: int) -> bool:
        """更新冷启动 trial 数, 返回是否已解除保护"""
        if creative_id in self._cold_start_creatives:
            self._cold_start_creatives[creative_id] = trials
            if trials >= self.COLD_START_MIN_TRIALS:
                del self._cold_start_creatives[creative_id]
                return True
        return False

    @property
    def cold_start_count(self) -> int:
        return len(self._cold_start_creatives)

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save(self) -> None:
        if not self._memory_path:
            return
        data = {"cold_start_creatives": self._cold_start_creatives}
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._memory_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(self._memory_path)

    def _load(self) -> None:
        if not self._memory_path or not self._memory_path.exists():
            return
        with open(self._memory_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._cold_start_creatives = data.get("cold_start_creatives", {})

    def stats(self) -> dict[str, Any]:
        return {
            "cold_start_creatives": len(self._cold_start_creatives),
            "cold_start_details": self._cold_start_creatives,
        }