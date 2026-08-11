"""Policy Execution Bridge — 策略输出 → 真实资金执行的控制桥

这是整个系统从"决策层"到"执行层"的关键接口，负责:
  1. 将 Policy 输出的概率分布转换为 Facebook 预算
  2. 强制执行 3 个生产级安全保护 (Budget Clamp, Exploration Floor, Kill-Switch)
  3. 收敛信号: 基于 reward variance 自动调整温度 T

完整数据流:
    PolicyStabilizerCore.select(bandit, gene_type)
        → {gene_value: probability}
    PolicyExecutionBridge.step(policy_output, bandit)
        → {adset_id: daily_budget}  (受保护)
    FacebookExecutor.execute_budget_plan(budget_plan)
        → Meta Ads 实际投放

生产级保护:
    P1: Budget Clamp     — budget ∈ [0.2 × avg, 2.0 × avg]  防爆
    P2: Exploration Floor — p_i = max(p_i, 0.02)              永不归零
    P3: Kill-Switch       — ROAS < threshold → fallback to bandit
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from market_ops.creative_intelligence.final_bandit import FinalBandit
    from market_ops.creative_intelligence.policy_stabilizer_core import PolicyStabilizerCore
    from market_ops.creative_intelligence.distribution_controller import (
        DistributionController,
        BudgetPlan,
    )
    from market_ops.creative_intelligence.facebook_executor import (
        FacebookExecutor,
        ExecutionResult,
    )


# ============================================================================
# 数据类型
# ============================================================================

@dataclass
class BridgeConfig:
    """PolicyExecutionBridge 配置"""

    # P1: Budget Clamp
    budget_clamp_min_ratio: float = 0.2   # 最低预算 = avg × 0.2
    budget_clamp_max_ratio: float = 2.0   # 最高预算 = avg × 2.0

    # P2: Exploration Floor
    exploration_floor: float = 0.02       # 每个 arm 最低概率 2%

    # P3: Kill-Switch
    kill_switch_roas_threshold: float = 0.3    # ROAS < 0.3 触发熔断
    kill_switch_consecutive_failures: int = 3  # 连续失败次数触发熔断

    # 收敛: 温度自适应
    convergence_variance_low: float = 0.01     # reward variance 低于此值 → 降 T
    convergence_variance_high: float = 0.10    # reward variance 高于此值 → 升 T
    temperature_adjust_rate: float = 0.05      # 每次调整幅度

    # 总预算
    total_budget: float = 1000.0


@dataclass
class BridgeResult:
    """单次桥接执行结果"""

    run_id: str
    # 输入
    policy_output: dict[str, float]         # {gene_value: probability}
    # 保护后
    protected_output: dict[str, float]      # 保护后的概率分布
    # 预算
    budget_plan: dict[str, float]           # {adset_id: daily_budget}
    # 执行
    execution_result: dict[str, Any] | None = None
    # 保护状态
    protections: dict[str, Any] = field(default_factory=dict)
    # 收敛
    convergence: dict[str, Any] = field(default_factory=dict)
    # 时间
    executed_at: str = ""

    def __post_init__(self):
        if not self.executed_at:
            self.executed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "policy_output": self.policy_output,
            "protected_output": self.protected_output,
            "budget_plan": self.budget_plan,
            "execution_result": self.execution_result,
            "protections": self.protections,
            "convergence": self.convergence,
            "executed_at": self.executed_at,
        }


# ============================================================================
# PolicyExecutionBridge
# ============================================================================

class PolicyExecutionBridge:
    """策略执行桥 — 决策层 → 执行层的控制接口

    核心职责:
      1. 接收 Policy 概率输出 → 转预算
      2. 强制执行 3 个生产级保护
      3. 收敛信号反馈 (reward variance → T 调整)
      4. 写入 Facebook

    用法:
        bridge = PolicyExecutionBridge(
            policy_core=policy_core,
            facebook_executor=executor,
            adset_mapping={"game:P04": "adset_id_1"},
        )
        result = bridge.step(policy_output, bandit, reward_history)
    """

    def __init__(
        self,
        policy_core: PolicyStabilizerCore | None = None,
        distribution_controller: DistributionController | None = None,
        facebook_executor: FacebookExecutor | None = None,
        adset_mapping: dict[str, str] | None = None,
        config: BridgeConfig | None = None,
        memory_path: str | Path | None = None,
    ):
        """
        Args:
            policy_core: 策略核心 (T(t) 控制器)
            distribution_controller: 预算分配器
            facebook_executor: Facebook 执行器
            adset_mapping: {gene_type:gene_value → adset_id} 映射
            config: 桥配置
            memory_path: 持久化路径
        """
        self.policy_core = policy_core
        self.distribution_controller = distribution_controller
        self.executor = facebook_executor
        self.adset_mapping = adset_mapping or {}
        self.config = config or BridgeConfig()

        # 运行时状态
        self._reward_history: list[float] = []
        self._consecutive_failures: int = 0
        self._kill_switch_active: bool = False
        self._iteration: int = 0

        # 持久化
        self._memory_path = Path(memory_path) if memory_path else None
        if self._memory_path and self._memory_path.exists():
            self._load()

    # ========================================================================
    # 核心: step — 单次决策→执行
    # ========================================================================

    def step(
        self,
        policy_output: dict[str, float],
        bandit: FinalBandit | None = None,
        reward_history: list[float] | None = None,
        dry_run: bool = False,
    ) -> BridgeResult:
        """执行一次完整决策→执行循环。

        Args:
            policy_output: {gene_value: probability} 策略输出的概率分布
            bandit: Bandit 实例 (用于 kill-switch fallback)
            reward_history: 最近 N 轮的 reward 列表 (用于收敛判断)
            dry_run: 模拟模式, 不实际调用 Facebook API

        Returns:
            BridgeResult
        """
        self._iteration += 1
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        result = BridgeResult(
            run_id=run_id,
            policy_output=dict(policy_output),
            protected_output={},
            budget_plan={},
        )

        # 更新 reward 历史
        if reward_history:
            self._reward_history.extend(reward_history)
            # 只保留最近 100 个
            if len(self._reward_history) > 100:
                self._reward_history = self._reward_history[-100:]

        # ---- P3: Kill-Switch 检查 ----
        kill_switch_triggered = self._check_kill_switch(policy_output, bandit)
        result.protections["kill_switch"] = {
            "active": self._kill_switch_active,
            "triggered_this_round": kill_switch_triggered,
            "consecutive_failures": self._consecutive_failures,
        }

        if kill_switch_triggered and bandit:
            # 熔断: fallback 到 Bandit (均匀分配)
            print("  [Bridge] 🔴 KILL-SWITCH 触发! 回退到 Bandit 均匀分配")
            policy_output = self._bandit_fallback(bandit)
            result.protections["kill_switch"]["fallback_applied"] = True

        # ---- P2: Exploration Floor ----
        protected = self._apply_exploration_floor(policy_output)
        result.protected_output = protected
        result.protections["exploration_floor"] = {
            "applied": protected != policy_output,
            "floor": self.config.exploration_floor,
        }

        # ---- 转预算 ----
        budget_plan = self._probabilities_to_budget(protected)
        result.protections["budget_conversion"] = {
            "total_budget": self.config.total_budget,
            "n_adsets": len(budget_plan),
        }

        # ---- P1: Budget Clamp ----
        budget_plan = self._apply_budget_clamp(budget_plan)
        result.budget_plan = budget_plan
        result.protections["budget_clamp"] = {
            "min_ratio": self.config.budget_clamp_min_ratio,
            "max_ratio": self.config.budget_clamp_max_ratio,
        }

        # ---- 收敛信号 ----
        result.convergence = self._compute_convergence()

        # ---- 执行到 Facebook ----
        if dry_run:
            result.execution_result = {
                "mode": "dry_run",
                "budget_plan": budget_plan,
            }
            print(f"  [Bridge] DRY RUN: {len(budget_plan)} 个 adset 预算分配")
            for adset_id, budget in budget_plan.items():
                print(f"    {adset_id} → ${budget:,.0f}/day")
        elif self.executor:
            exec_result = self.executor.execute_budget_plan(budget_plan)
            result.execution_result = exec_result.to_dict() if hasattr(exec_result, 'to_dict') else {"success": getattr(exec_result, 'success', False)}
            print(f"  [Bridge] {'✅' if getattr(exec_result, 'success', False) else '❌'} "
                  f"预算更新: {getattr(exec_result, 'budget_updates', 0)} 个 adset")
        else:
            result.execution_result = {"error": "FacebookExecutor 未初始化"}

        # 持久化
        self._save()

        return result

    # ========================================================================
    # P1: Budget Clamp — 防爆
    # ========================================================================

    def _apply_budget_clamp(self, budget_plan: dict[str, float]) -> dict[str, float]:
        """budget = clip(budget, 0.2 * avg, 2.0 * avg)"""
        if not budget_plan:
            return budget_plan

        values = list(budget_plan.values())
        avg = sum(values) / len(values)
        min_budget = avg * self.config.budget_clamp_min_ratio
        max_budget = avg * self.config.budget_clamp_max_ratio

        clamped = {}
        for adset_id, budget in budget_plan.items():
            original = budget
            clamped_budget = max(min_budget, min(max_budget, budget))
            clamped[adset_id] = round(clamped_budget, 2)
            if clamped_budget != original:
                print(f"  [Bridge] Budget Clamp: {adset_id} ${original:.0f} → ${clamped_budget:.0f}")

        return clamped

    # ========================================================================
    # P2: Exploration Floor — 永不归零
    # ========================================================================

    def _apply_exploration_floor(self, probabilities: dict[str, float]) -> dict[str, float]:
        """p_i = max(p_i, floor), 然后重新归一化"""
        if not probabilities:
            return probabilities

        floor = self.config.exploration_floor
        n = len(probabilities)

        # 检查是否需要 floor
        need_floor = any(p < floor for p in probabilities.values())
        if not need_floor:
            return dict(probabilities)

        # 应用 floor
        floored = {k: max(v, floor) for k, v in probabilities.items()}

        # 重新归一化
        total = sum(floored.values())
        if total > 0:
            normalized = {k: v / total for k, v in floored.items()}
        else:
            normalized = {k: 1.0 / n for k in probabilities}

        return normalized

    # ========================================================================
    # P3: Kill-Switch — ROAS 熔断
    # ========================================================================

    def _check_kill_switch(
        self,
        policy_output: dict[str, float],
        bandit: FinalBandit | None = None,
    ) -> bool:
        """检查是否触发 kill-switch。

        触发条件:
          1. 连续 N 次 reward 低于阈值
          2. 最近的 ROAS < kill_switch_roas_threshold
        """
        if not self._reward_history:
            return False

        recent = self._reward_history[-self.config.kill_switch_consecutive_failures:]
        if len(recent) < self.config.kill_switch_consecutive_failures:
            return False

        # 检查连续低 reward
        all_low = all(r < self.config.kill_switch_roas_threshold for r in recent)
        if all_low:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = max(0, self._consecutive_failures - 1)

        if self._consecutive_failures >= self.config.kill_switch_consecutive_failures:
            self._kill_switch_active = True
            return True

        self._kill_switch_active = False
        return False

    def reset_kill_switch(self) -> None:
        """手动重置 kill-switch"""
        self._consecutive_failures = 0
        self._kill_switch_active = False

    def _bandit_fallback(self, bandit: FinalBandit) -> dict[str, float]:
        """Kill-switch 触发后回退到 Bandit 均匀分配"""
        fallback: dict[str, float] = {}
        for gene_type in self.adset_mapping:
            arms = [a for a in bandit.arms.values() if a.gene_type == gene_type]
            if arms:
                n = len(arms)
                for a in arms:
                    fallback[a.gene_value] = 1.0 / n
            else:
                # 无 arms, 均匀分配 adset_mapping
                n = len(self.adset_mapping)
                for gv in self.adset_mapping:
                    fallback[gv] = 1.0 / n
        return fallback

    # ========================================================================
    # 预算转换
    # ========================================================================

    def _probabilities_to_budget(self, probabilities: dict[str, float]) -> dict[str, float]:
        """概率分布 → {adset_id: daily_budget}

        映射: gene_value → adset_id (通过 adset_mapping)
        如果没有映射, 直接用 gene_value 作为 key
        """
        budget_plan: dict[str, float] = {}
        total = self.config.total_budget

        for gene_value, prob in probabilities.items():
            # 查找 adset_id
            adset_id = self.adset_mapping.get(gene_value, gene_value)
            budget_plan[adset_id] = total * prob

        return budget_plan

    def set_adset_mapping(self, mapping: dict[str, str]) -> None:
        """更新 adset 映射表"""
        self.adset_mapping = mapping

    # ========================================================================
    # 收敛信号
    # ========================================================================

    def _compute_convergence(self) -> dict[str, Any]:
        """计算收敛信号, 用于自适应调整 T。

        reward variance ↓ → decrease T → more exploitation
        reward unstable   → increase T → more exploration
        """
        if len(self._reward_history) < 5:
            return {"status": "insufficient_data", "n_samples": len(self._reward_history)}

        recent = self._reward_history[-20:]  # 最近 20 轮
        variance = float(np.var(recent))
        mean = float(np.mean(recent))

        signal = {
            "n_samples": len(recent),
            "mean_reward": round(mean, 4),
            "variance": round(variance, 4),
            "action": "hold",
        }

        if variance < self.config.convergence_variance_low:
            signal["action"] = "decrease_temperature"
            signal["reason"] = f"低 variance ({variance:.4f}), 系统趋于收敛 → 降 T 以利用"
        elif variance > self.config.convergence_variance_high:
            signal["action"] = "increase_temperature"
            signal["reason"] = f"高 variance ({variance:.4f}), 系统不稳定 → 升 T 以探索"
        else:
            signal["action"] = "hold"
            signal["reason"] = f"variance ({variance:.4f}) 在正常范围"

        # 如果 policy_core 可用, 自动调整 T
        if self.policy_core and signal["action"] != "hold":
            self._adjust_temperature(signal["action"])

        return signal

    def _adjust_temperature(self, action: str) -> None:
        """根据收敛信号调整 T(t)"""
        if not self.policy_core:
            return

        if action == "decrease_temperature":
            # 加速降温: 额外推进 step
            self.policy_core.advance()
            print(f"  [Bridge] 收敛信号: 降 T → {self.policy_core.temperature:.3f}")
        elif action == "increase_temperature":
            # 升温: 回退 step (模拟)
            # PolicyStabilizerCore 不支持回退, 改为重置到较高温度
            if self.policy_core._step > 0:
                self.policy_core._step = max(0, self.policy_core._step - 2)
            print(f"  [Bridge] 收敛信号: 升 T → {self.policy_core.temperature:.3f}")

    @property
    def convergence_state(self) -> str:
        """当前收敛状态: exploring / converging / converged"""
        if len(self._reward_history) < 5:
            return "exploring"
        recent = self._reward_history[-20:]
        variance = float(np.var(recent))
        if variance < self.config.convergence_variance_low:
            return "converged"
        elif variance < self.config.convergence_variance_high:
            return "converging"
        return "exploring"

    # ========================================================================
    # 辅助: 从 Bandit 获取 policy 输出
    # ========================================================================

    def get_policy_output(self, bandit: FinalBandit, gene_type: str) -> dict[str, float]:
        """从 Bandit 获取当前策略概率分布。

        如果 policy_core 可用, 使用 T(t)-modulated select;
        否则使用 Bandit 原始的 softmax(theta / tau)。
        """
        if self.policy_core:
            return self.policy_core.select(bandit, gene_type)
        return bandit.softmax(gene_type)

    def get_all_policy_outputs(self, bandit: FinalBandit) -> dict[str, dict[str, float]]:
        """获取所有 gene_type 的策略概率分布"""
        outputs: dict[str, dict[str, float]] = {}
        for gene_type in self.adset_mapping:
            probs = self.get_policy_output(bandit, gene_type)
            if probs:
                outputs[gene_type] = probs
        return outputs

    # ========================================================================
    # 便捷方法: 一步完成 policy→执行
    # ========================================================================

    def execute_from_bandit(
        self,
        bandit: FinalBandit,
        reward_history: list[float] | None = None,
        dry_run: bool = False,
    ) -> dict[str, BridgeResult]:
        """从 Bandit 一步完成: policy → 保护 → 预算 → 执行。

        Returns:
            {gene_type: BridgeResult}
        """
        results: dict[str, BridgeResult] = {}
        all_outputs = self.get_all_policy_outputs(bandit)

        for gene_type, policy_output in all_outputs.items():
            result = self.step(
                policy_output=policy_output,
                bandit=bandit,
                reward_history=reward_history,
                dry_run=dry_run,
            )
            results[gene_type] = result

        return results

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save(self) -> None:
        if not self._memory_path:
            return
        data = {
            "iteration": self._iteration,
            "consecutive_failures": self._consecutive_failures,
            "kill_switch_active": self._kill_switch_active,
            "reward_history": self._reward_history[-50:],
            "convergence_state": self.convergence_state,
            "config": {
                "budget_clamp_min_ratio": self.config.budget_clamp_min_ratio,
                "budget_clamp_max_ratio": self.config.budget_clamp_max_ratio,
                "exploration_floor": self.config.exploration_floor,
                "kill_switch_roas_threshold": self.config.kill_switch_roas_threshold,
                "total_budget": self.config.total_budget,
            },
        }
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
            self._iteration = data.get("iteration", 0)
            self._consecutive_failures = data.get("consecutive_failures", 0)
            self._kill_switch_active = data.get("kill_switch_active", False)
            self._reward_history = data.get("reward_history", [])

    def stats(self) -> dict[str, Any]:
        return {
            "iteration": self._iteration,
            "consecutive_failures": self._consecutive_failures,
            "kill_switch_active": self._kill_switch_active,
            "convergence_state": self.convergence_state,
            "n_reward_history": len(self._reward_history),
            "n_adset_mappings": len(self.adset_mapping),
            "config": {
                "budget_clamp": f"[{self.config.budget_clamp_min_ratio}, {self.config.budget_clamp_max_ratio}]",
                "exploration_floor": self.config.exploration_floor,
                "kill_switch_threshold": self.config.kill_switch_roas_threshold,
                "total_budget": self.config.total_budget,
            },
        }