"""Facebook Executor v2 — 写回现实世界 (生产级执行层)

在 FacebookPublisher (素材上传+创建) 之上扩展:
  - 预算更新 (adset daily_budget / lifetime_budget)
  - 广告/广告组 暂停/恢复
  - Insights 读取 (spend, purchase, ROAS per creative)
  - 批量执行 预算分配方案

v2 新增 — 生产级保护:
  - P1: Budget Clamp     — budget = clip(budget, 0.2 * avg, 2.0 * avg)  防爆
  - P2: Exploration Floor — p_i = max(p_i, 0.02)                         永不归零
  - P3: Kill-Switch       — ROAS < threshold → fallback_to_bandit()      熔断

这是闭环的"执行层" — 系统决策通过它写入 Facebook, 真实影响 spend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from market_ops.creative_growth_loop.publish.facebook_publisher import FacebookPublisher


@dataclass
class ExecutionResult:
    """单次执行结果"""
    run_id: str
    budget_updates: int = 0
    budget_errors: list[str] = None
    status_changes: int = 0
    status_errors: list[str] = None
    executed_at: str = ""

    def __post_init__(self):
        self.budget_errors = self.budget_errors or []
        self.status_errors = self.status_errors or []

    @property
    def success(self) -> bool:
        return self.budget_updates > 0 and len(self.budget_errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "budget_updates": self.budget_updates,
            "budget_errors": self.budget_errors,
            "status_changes": self.status_changes,
            "status_errors": self.status_errors,
            "executed_at": self.executed_at,
        }


@dataclass
class CreativeInsight:
    """单个创意的性能数据"""
    creative_id: str
    ad_id: str
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    installs: int = 0
    purchases: int = 0
    purchase_value: float = 0.0
    roas: float = 0.0
    date: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "ad_id": self.ad_id,
            "spend": self.spend,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": self.ctr,
            "installs": self.installs,
            "purchases": self.purchases,
            "purchase_value": self.purchase_value,
            "roas": self.roas,
            "date": self.date,
        }


class FacebookExecutor(FacebookPublisher):
    """Facebook 执行器 — 在发布器基础上扩展写回 + 读回能力

    写回:
      - update_adset_budget(adset_id, daily_budget)  → 修改预算
      - update_adset_status(adset_id, status)         → 暂停/恢复
      - update_ad_status(ad_id, status)               → 暂停/恢复单个广告

    读回:
      - get_ad_insights(ad_ids, date_preset)          → 拉取性能数据
      - get_creative_insights(creative_ids)           → 按创意拉取

    批量执行:
      - execute_budget_plan(plan)                     → 执行 BudgetPlan
    """

    # ------------------------------------------------------------------
    # 写回: 预算控制
    # ------------------------------------------------------------------

    def update_adset_budget(
        self, adset_id: str, daily_budget: int | None = None,
        lifetime_budget: int | None = None,
    ) -> bool:
        """更新 adset 预算 (单位: 分, 即 100 = $1.00)

        Facebook Ads API: POST /{adset_id}
        """
        url = f"{self._base_url}/{adset_id}"
        params: dict[str, Any] = {"access_token": self._access_token}

        if daily_budget is not None:
            params["daily_budget"] = str(daily_budget)
        if lifetime_budget is not None:
            params["lifetime_budget"] = str(lifetime_budget)

        try:
            response = requests.post(url, data=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                print(f"  [FacebookExecutor] Budget update failed: {data['error']}")
                return False
            return data.get("success", True)
        except Exception as e:
            print(f"  [FacebookExecutor] Budget update error: {e}")
            return False

    def update_adset_status(self, adset_id: str, status: str) -> bool:
        """更新 adset 状态: ACTIVE / PAUSED / DELETED / ARCHIVED"""
        url = f"{self._base_url}/{adset_id}"
        params = {
            "access_token": self._access_token,
            "status": status,
        }
        try:
            response = requests.post(url, data=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return "error" not in data
        except Exception as e:
            print(f"  [FacebookExecutor] Status update error: {e}")
            return False

    def update_ad_status(self, ad_id: str, status: str) -> bool:
        """更新单个广告状态"""
        url = f"{self._base_url}/{ad_id}"
        params = {
            "access_token": self._access_token,
            "status": status,
        }
        try:
            response = requests.post(url, data=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return "error" not in data
        except Exception as e:
            print(f"  [FacebookExecutor] Ad status update error: {e}")
            return False

    # ------------------------------------------------------------------
    # 读回: Insights
    # ------------------------------------------------------------------

    def get_ad_insights(
        self,
        ad_ids: list[str],
        date_preset: str = "today",
        fields: list[str] | None = None,
    ) -> list[CreativeInsight]:
        """批量拉取广告性能数据

        Facebook Ads API: GET /{ad_id}/insights

        Args:
            ad_ids: 广告 ID 列表
            date_preset: today / yesterday / last_3d / last_7d
            fields: 自定义字段列表
        """
        if fields is None:
            fields = [
                "spend", "impressions", "clicks", "ctr",
                "actions", "action_values",
            ]

        insights: list[CreativeInsight] = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for ad_id in ad_ids:
            try:
                url = f"{self._base_url}/{ad_id}/insights"
                params = {
                    "access_token": self._access_token,
                    "date_preset": date_preset,
                    "fields": ",".join(fields),
                    "action_attribution_windows": json.dumps(["7d_click", "1d_view"]),
                }
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                for row in data.get("data", []):
                    insight = self._parse_insight_row(row, ad_id, today)
                    insights.append(insight)

            except Exception as e:
                print(f"  [FacebookExecutor] Insights fetch error for {ad_id}: {e}")

        return insights

    def get_creative_insights(
        self,
        creative_ids: list[str],
        date_preset: str = "last_7d",
    ) -> list[CreativeInsight]:
        """按创意 ID 拉取性能数据 (通过 ad 间接查询)"""
        # 先通过 creative 找到对应的 ad
        all_insights: list[CreativeInsight] = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for creative_id in creative_ids:
            try:
                # 查找使用该 creative 的 ads
                url = f"{self._base_url}/{creative_id}/ads"
                params = {
                    "access_token": self._access_token,
                    "fields": "id,name",
                }
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                ad_data = response.json()

                ad_ids = [ad["id"] for ad in ad_data.get("data", [])]
                if ad_ids:
                    insights = self.get_ad_insights(ad_ids, date_preset=date_preset)
                    for ins in insights:
                        ins.creative_id = creative_id
                    all_insights.extend(insights)

            except Exception as e:
                print(f"  [FacebookExecutor] Creative insights error for {creative_id}: {e}")

        return all_insights

    # ------------------------------------------------------------------
    # 批量执行: 预算分配方案
    # ------------------------------------------------------------------

    def execute_budget_plan(
        self,
        adset_budget_map: dict[str, float],  # adset_id → daily_budget_dollars
        pause_adsets: list[str] | None = None,
        resume_adsets: list[str] | None = None,
    ) -> ExecutionResult:
        """执行一个完整的预算分配方案。

        Args:
            adset_budget_map: {adset_id: daily_budget_in_dollars}
            pause_adsets: 需要暂停的 adset ID 列表
            resume_adsets: 需要恢复的 adset ID 列表

        Returns:
            ExecutionResult
        """
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        result = ExecutionResult(
            run_id=run_id,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

        # 预算更新
        for adset_id, budget_dollars in adset_budget_map.items():
            budget_cents = max(100, int(budget_dollars * 100))  # 最低 $1.00
            ok = self.update_adset_budget(adset_id, daily_budget=budget_cents)
            if ok:
                result.budget_updates += 1
                print(f"  [Executor] Budget: {adset_id} → ${budget_cents / 100:.2f}")
            else:
                result.budget_errors.append(f"Failed to update {adset_id}")

        # 暂停
        for adset_id in (pause_adsets or []):
            ok = self.update_adset_status(adset_id, "PAUSED")
            if ok:
                result.status_changes += 1
                print(f"  [Executor] Paused: {adset_id}")
            else:
                result.status_errors.append(f"Failed to pause {adset_id}")

        # 恢复
        for adset_id in (resume_adsets or []):
            ok = self.update_adset_status(adset_id, "ACTIVE")
            if ok:
                result.status_changes += 1
                print(f"  [Executor] Resumed: {adset_id}")
            else:
                result.status_errors.append(f"Failed to resume {adset_id}")

        self._save_execution_result(result)
        return result

    # ------------------------------------------------------------------
    # v2: 生产级保护方法
    # ------------------------------------------------------------------

    def execute_budget_plan_v2(
        self,
        adset_budget_map: dict[str, float],
        pause_adsets: list[str] | None = None,
        resume_adsets: list[str] | None = None,
        budget_clamp: bool = True,
        budget_clamp_min_ratio: float = 0.2,
        budget_clamp_max_ratio: float = 2.0,
        exploration_floor: float = 0.02,
        kill_switch_roas_threshold: float = 0.3,
        current_roas: float | None = None,
        fallback_budget_map: dict[str, float] | None = None,
    ) -> ExecutionResult:
        """v2 执行预算分配方案 (含 3 个生产级保护)。

        P1: Budget Clamp — budget ∈ [min_ratio × avg, max_ratio × avg]
        P2: Exploration Floor — 每个 adset 最低预算 > 0
        P3: Kill-Switch — ROAS < threshold → 回退到 fallback 方案

        Args:
            adset_budget_map: {adset_id: daily_budget_in_dollars}
            pause_adsets: 需要暂停的 adset ID 列表
            resume_adsets: 需要恢复的 adset ID 列表
            budget_clamp: 是否启用预算钳制
            budget_clamp_min_ratio: 最低预算比例 (默认 0.2)
            budget_clamp_max_ratio: 最高预算比例 (默认 2.0)
            exploration_floor: 最低预算 (美元), 低于此值设为 floor
            kill_switch_roas_threshold: ROAS 熔断阈值
            current_roas: 当前 ROAS (用于 kill-switch 判断)
            fallback_budget_map: kill-switch 触发时的回退预算方案

        Returns:
            ExecutionResult
        """
        original_plan = dict(adset_budget_map)

        # ---- P3: Kill-Switch ----
        if current_roas is not None and current_roas < kill_switch_roas_threshold:
            print(f"  [FacebookExecutor] 🔴 KILL-SWITCH: ROAS={current_roas:.3f} < {kill_switch_roas_threshold}")
            if fallback_budget_map:
                print(f"  [FacebookExecutor] 回退到 fallback 方案 ({len(fallback_budget_map)} 个 adset)")
                adset_budget_map = fallback_budget_map
            else:
                print(f"  [FacebookExecutor] 无 fallback 方案, 均匀分配")
                n = len(adset_budget_map)
                if n > 0:
                    total = sum(adset_budget_map.values())
                    avg = total / n
                    adset_budget_map = {k: avg for k in adset_budget_map}

        # ---- P2: Exploration Floor ----
        if exploration_floor > 0:
            for adset_id, budget in adset_budget_map.items():
                if budget < exploration_floor:
                    adset_budget_map[adset_id] = exploration_floor
                    print(f"  [FacebookExecutor] Exploration Floor: {adset_id} ${budget:.2f} → ${exploration_floor:.2f}")

        # ---- P1: Budget Clamp ----
        if budget_clamp and len(adset_budget_map) > 1:
            values = list(adset_budget_map.values())
            avg = sum(values) / len(values)
            min_budget = avg * budget_clamp_min_ratio
            max_budget = avg * budget_clamp_max_ratio

            for adset_id, budget in list(adset_budget_map.items()):
                if budget < min_budget:
                    adset_budget_map[adset_id] = min_budget
                    print(f"  [FacebookExecutor] Budget Clamp (min): {adset_id} ${budget:.2f} → ${min_budget:.2f}")
                elif budget > max_budget:
                    adset_budget_map[adset_id] = max_budget
                    print(f"  [FacebookExecutor] Budget Clamp (max): {adset_id} ${budget:.2f} → ${max_budget:.2f}")

        # ---- 执行 ----
        result = self.execute_budget_plan(
            adset_budget_map=adset_budget_map,
            pause_adsets=pause_adsets,
            resume_adsets=resume_adsets,
        )

        # 记录保护信息
        result._v2_protections = {
            "budget_clamp": budget_clamp,
            "budget_clamp_range": [budget_clamp_min_ratio, budget_clamp_max_ratio],
            "exploration_floor": exploration_floor,
            "kill_switch_triggered": current_roas is not None and current_roas < kill_switch_roas_threshold,
            "original_plan": original_plan,
            "protected_plan": dict(adset_budget_map),
        }

        return result

    @staticmethod
    def budget_clamp(
        budget_plan: dict[str, float],
        min_ratio: float = 0.2,
        max_ratio: float = 2.0,
    ) -> dict[str, float]:
        """P1: Budget Clamp — budget = clip(budget, min_ratio * avg, max_ratio * avg)

        Args:
            budget_plan: {adset_id: budget}
            min_ratio: 最低比例 (默认 0.2)
            max_ratio: 最高比例 (默认 2.0)

        Returns:
            钳制后的预算方案
        """
        if len(budget_plan) <= 1:
            return budget_plan

        values = list(budget_plan.values())
        avg = sum(values) / len(values)
        min_budget = avg * min_ratio
        max_budget = avg * max_ratio

        return {
            k: max(min_budget, min(max_budget, v))
            for k, v in budget_plan.items()
        }

    @staticmethod
    def exploration_floor(
        probabilities: dict[str, float],
        floor: float = 0.02,
    ) -> dict[str, float]:
        """P2: Exploration Floor — p_i = max(p_i, floor), 重新归一化

        Args:
            probabilities: {arm: probability}
            floor: 最低概率 (默认 0.02)

        Returns:
            保护后并重新归一化的概率分布
        """
        n = len(probabilities)
        if n == 0:
            return probabilities

        floored = {k: max(v, floor) for k, v in probabilities.items()}
        total = sum(floored.values())

        if total > 0:
            return {k: v / total for k, v in floored.items()}
        return {k: 1.0 / n for k in probabilities}

    @staticmethod
    def kill_switch_check(
        roas: float,
        threshold: float = 0.3,
    ) -> bool:
        """P3: Kill-Switch — ROAS < threshold → 触发熔断

        Args:
            roas: 当前 ROAS
            threshold: 熔断阈值 (默认 0.3)

        Returns:
            True 表示需要触发熔断
        """
        return roas < threshold

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _parse_insight_row(
        self, row: dict[str, Any], ad_id: str, date: str,
    ) -> CreativeInsight:
        """解析 Facebook Insights 返回的单行数据"""
        # 提取 actions (install, purchase 等)
        actions = row.get("actions", [])
        action_values = row.get("action_values", [])

        def _get_action(action_type: str) -> float:
            for a in actions:
                if a.get("action_type") == action_type:
                    return float(a.get("value", 0))
            return 0.0

        def _get_action_value(action_type: str) -> float:
            for a in action_values:
                if a.get("action_type") == action_type:
                    return float(a.get("value", 0))
            return 0.0

        spend = float(row.get("spend", 0))
        purchase_value = _get_action_value("purchase")

        return CreativeInsight(
            creative_id="",
            ad_id=ad_id,
            spend=spend,
            impressions=int(row.get("impressions", 0)),
            clicks=int(row.get("clicks", 0)),
            ctr=float(row.get("ctr", 0)),
            installs=int(_get_action("mobile_app_install")),
            purchases=int(_get_action("purchase")),
            purchase_value=purchase_value,
            roas=purchase_value / spend if spend > 0 else 0.0,
            date=date,
        )

    def _save_execution_result(self, result: ExecutionResult) -> Path:
        output_dir = Path("output/closed_loop/executions")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"execution_{result.run_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        return path