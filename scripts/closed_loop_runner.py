"""Closed Loop Runner — 在线策略执行引擎

完整闭环:
  1. 拉取 Facebook 数据     (RewardCollector)
  2. 计算 reward             (RewardStabilizer + QualityScoreBuilder)
  3. 更新 Bandit             (PolicyStabilizerCore)
  4. 分配预算                (PolicyExecutionBridge — NEW)
  5. 执行到 Facebook         (FacebookExecutor — 含 3 个生产保护)
  6. 等待 + 循环

v2 升级: 集成 PolicyExecutionBridge — 策略→执行控制桥
  - P1: Budget Clamp     — budget = clip(budget, 0.2 * avg, 2.0 * avg)
  - P2: Exploration Floor — p_i = max(p_i, 0.02)
  - P3: Kill-Switch       — ROAS < threshold → fallback to Bandit

模式:
  --dry-run: 模拟模式, Facebook API 调用被截获, 输出到日志
  --live:    真实模式, 实际调用 Facebook API (需要 ACCESS_TOKEN)

配置:
  closed_loop_config.json:
    {
      "ad_account_id": "act_123456",
      "adset_mapping": {
        "game:P04": "adset_id_1",
        "game:P07": "adset_id_2"
      },
      "access_token": "EAA...",
      "interval_hours": 6,
      "total_budget": 1000
    }

用法:
  python scripts/closed_loop_runner.py --dry-run
  python scripts/closed_loop_runner.py --live --config closed_loop_config.json
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from market_ops.creative_intelligence.final_bandit import FinalBandit
from market_ops.creative_intelligence.policy_stabilizer_core import PolicyStabilizerCore
from market_ops.creative_intelligence.reward_stabilizer import RewardStabilizer, unified_reward
from market_ops.creative_intelligence.distribution_controller import DistributionController
from market_ops.creative_intelligence.iap_observation import CreativeObservation, QualityScoreBuilder
from market_ops.creative_intelligence.policy_execution_bridge import (
    PolicyExecutionBridge,
    BridgeConfig,
    BridgeResult,
)


# ============================================================================
# 闭环状态
# ============================================================================

class LoopState:
    """闭环运行状态, 持久化到 JSON"""

    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "iterations": 0,
            "total_executions": 0,
            "total_budget_spent": 0.0,
            "convergence_log": [],
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def record_iteration(self, temperature: float, phase: str, budget_distribution: dict[str, float]) -> None:
        self.data["iterations"] += 1
        self.data["convergence_log"].append({
            "iteration": self.data["iterations"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "T": round(temperature, 4),
            "phase": phase,
            "budget_distribution": budget_distribution,
        })
        # 只保留最近 200 条
        if len(self.data["convergence_log"]) > 200:
            self.data["convergence_log"] = self.data["convergence_log"][-200:]
        self.save()


# ============================================================================
# 闭环运行器
# ============================================================================

class ClosedLoopRunner:
    """在线策略执行引擎

    核心循环:
      while True:
          execute_one_cycle()
          sleep(interval_hours)
    """

    def __init__(
        self,
        config: dict[str, Any],
        dry_run: bool = True,
    ):
        self.config = config
        self.dry_run = dry_run

        # 初始化核心组件
        output_dir = ROOT / "output" / "closed_loop"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.bandit = FinalBandit()
        self.policy_core = PolicyStabilizerCore(
            T0=config.get("T0", 1.0),
            T_min=config.get("T_min", 0.1),
            k=config.get("k", 0.03),
            memory_path=output_dir / "policy_stabilizer_core.json",
        )
        self.reward_stabilizer = RewardStabilizer(
            ema_alpha=config.get("ema_alpha", 0.3),
            memory_path=output_dir / "reward_stabilizer.json",
        )
        self.distribution_controller = DistributionController(
            memory_path=output_dir / "distribution_controller.json",
        )
        self.quality_builder = QualityScoreBuilder()

        # PolicyExecutionBridge (v2) — 策略→执行控制桥
        self.bridge = PolicyExecutionBridge(
            policy_core=self.policy_core,
            distribution_controller=self.distribution_controller,
            facebook_executor=None,  # lazy init below
            adset_mapping=self._adset_mapping,
            config=BridgeConfig(
                total_budget=self.total_budget,
                budget_clamp_min_ratio=config.get("budget_clamp_min_ratio", 0.2),
                budget_clamp_max_ratio=config.get("budget_clamp_max_ratio", 2.0),
                exploration_floor=config.get("exploration_floor", 0.02),
                kill_switch_roas_threshold=config.get("kill_switch_roas_threshold", 0.3),
            ),
            memory_path=output_dir / "policy_execution_bridge.json",
        )

        # Facebook Executor (lazy init, 只在 live 模式创建)
        self._executor = None
        self._adset_mapping: dict[str, str] = config.get("adset_mapping", {})

        # 状态
        self.state = LoopState(output_dir / "loop_state.json")

        # 配置
        self.interval_hours = config.get("interval_hours", 6)
        self.total_budget = config.get("total_budget", 1000.0)
        self.max_iterations = config.get("max_iterations", 0)  # 0 = 无限

    # ========================================================================
    # 核心循环
    # ========================================================================

    def run(self) -> None:
        """启动闭环 (阻塞)"""
        print("=" * 70)
        mode = "DRY RUN (模拟)" if self.dry_run else "LIVE (真实)"
        print(f"  Closed Loop Runner — {mode}")
        print(f"  T={self.policy_core.temperature:.3f}, phase={self.policy_core.phase}")
        print(f"  Interval: {self.interval_hours}h, Budget: ${self.total_budget:,.0f}")
        print(f"  Adsets: {len(self._adset_mapping)}")
        print("=" * 70)

        if not self.dry_run and not self._adset_mapping:
            print("\n  ⚠️  LIVE 模式但无 adset_mapping 配置, 无法执行预算分配")
            print("  请在 closed_loop_config.json 中配置 adset_mapping")
            return

        iteration = self.state.data["iterations"]

        while True:
            iteration += 1
            print(f"\n{'─' * 70}")
            print(f"  Iteration {iteration} | T={self.policy_core.temperature:.3f} | "
                  f"{datetime.now(timezone.utc).strftime('%H:%M UTC')}")
            print(f"{'─' * 70}")

            try:
                self._execute_one_cycle()
            except Exception as e:
                print(f"  ❌ Cycle failed: {e}")
                import traceback
                traceback.print_exc()

            # 终止条件
            if self.max_iterations > 0 and iteration >= self.max_iterations:
                print(f"\n  ✅ 达到最大迭代次数 {self.max_iterations}, 停止")
                break

            if self.policy_core.temperature <= self.policy_core.config.T_min:
                print(f"\n  ✅ 温度已降至 T_min={self.policy_core.config.T_min}, 系统已收敛")
                break

            # 等待
            print(f"\n  ⏳ 等待 {self.interval_hours}h 后进入下一轮...")
            if self.dry_run:
                print("  [DRY RUN] 跳过实际等待, 3 秒后继续")
                time.sleep(3)
            else:
                time.sleep(self.interval_hours * 3600)

    # ========================================================================
    # 单次循环
    # ========================================================================

    def _execute_one_cycle(self) -> None:
        """执行一次完整闭环"""

        # Step 1: 拉取数据
        print("  [1/5] 拉取性能数据...")
        insights = self._fetch_insights()

        # Step 2: 计算 reward
        print("  [2/5] 计算 reward...")
        rewards = self._compute_rewards(insights)

        # Step 3: 更新 Bandit
        print("  [3/5] 更新 Bandit...")
        self._update_bandit(rewards)

        # Step 4: 分配预算
        print("  [4/5] 分配预算...")
        budget_plan = self._allocate_budget()

        # Step 5: 执行到 Facebook
        print("  [5/5] 执行预算...")
        self._execute_budget(budget_plan)

        # 记录状态
        self.state.record_iteration(
            temperature=self.policy_core.temperature,
            phase=self.policy_core.phase,
            budget_distribution=budget_plan,
        )

        print(f"  ✅ 迭代完成 | T={self.policy_core.temperature:.3f} | "
              f"phase={self.policy_core.phase}")

    # ========================================================================
    # Step 1: 拉取数据
    # ========================================================================

    def _fetch_insights(self) -> list[dict[str, Any]]:
        """拉取 Facebook Insights 数据。

        LIVE 模式: 调用 FacebookExecutor.get_ad_insights()
        DRY RUN: 使用 DuckDB 中的历史数据
        """
        if self.dry_run:
            return self._fetch_dry_run()

        # LIVE 模式
        executor = self._get_executor()
        if not executor:
            return []

        # 收集所有已知的 ad_ids
        all_ad_ids = []
        for adset_id in self._adset_mapping.values():
            # 通过 adset 查找 ads
            try:
                url = f"{executor._base_url}/{adset_id}/ads"
                params = {
                    "access_token": executor._access_token,
                    "fields": "id",
                    "limit": "50",
                }
                response = __import__("requests").get(url, params=params, timeout=30)
                data = response.json()
                for ad in data.get("data", []):
                    all_ad_ids.append(ad["id"])
            except Exception as e:
                print(f"    [WARN] 无法获取 adset {adset_id} 的 ads: {e}")

        if not all_ad_ids:
            return []

        insights = executor.get_ad_insights(all_ad_ids, date_preset="last_3d")
        return [i.to_dict() for i in insights]

    def _fetch_dry_run(self) -> list[dict[str, Any]]:
        """DRY RUN: 从 DuckDB 读取历史数据"""
        import duckdb
        db_path = ROOT / "db" / "facebook_performance.duckdb"
        if not db_path.exists():
            print("    [DRY RUN] 无历史数据")
            return []

        conn = duckdb.connect(str(db_path))
        try:
            rows = conn.execute("""
                SELECT creative_id, date, spend, impression, click, ctr,
                       install, roas_d7
                FROM creative_performance
                ORDER BY date DESC
                LIMIT 50
            """).fetchall()

            results = []
            for row in rows:
                results.append({
                    "creative_id": row[0],
                    "date": str(row[1]),
                    "spend": float(row[2] or 0),
                    "impressions": int(row[3] or 0),
                    "clicks": int(row[4] or 0),
                    "ctr": float(row[5] or 0),
                    "installs": int(row[6] or 0),
                    "purchases": 0,
                    "purchase_value": 0.0,
                    "roas": float(row[7] or 0),
                })
            print(f"    [DRY RUN] 读取 {len(results)} 条历史数据")
            return results
        finally:
            conn.close()

    # ========================================================================
    # Step 2: 计算 reward
    # ========================================================================

    def _compute_rewards(self, insights: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """计算每个 creative 的 reward"""
        rewards: dict[str, dict[str, Any]] = {}

        for ins in insights:
            cid = ins.get("creative_id", "unknown")
            if cid == "unknown" or not cid:
                continue

            # 构造 CreativeObservation
            obs = CreativeObservation(
                creative_id=cid,
                date=ins.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                impression=ins.get("impressions", 0),
                click=ins.get("clicks", 0),
                ctr=ins.get("ctr", 0),
                install=ins.get("installs", 0),
                spend=ins.get("spend", 0),
                roas_d7=ins.get("roas", 0),
            )

            # 用 QualityScoreBuilder 计算基础 reward
            qs = self.quality_builder.build(obs)
            raw_reward = qs.score

            # 统一 reward 公式 (当有 purchase 数据时使用)
            if ins.get("purchases", 0) > 0:
                purchase_rate = ins["purchases"] / max(ins.get("clicks", 1), 1)
                raw_reward = unified_reward(
                    roas=ins.get("roas", 0),
                    purchase_rate=purchase_rate,
                    ctr=ins.get("ctr", 0),
                )

            # Reward Stabilizer: EMA + cohort
            smoothed = self.reward_stabilizer.smooth(cid, raw_reward)
            self.reward_stabilizer.update_cohort("live", smoothed)
            normalized = self.reward_stabilizer.normalize(cid, smoothed, cohort_key="live")

            rewards[cid] = {
                "raw": raw_reward,
                "smoothed": smoothed,
                "normalized": normalized,
                "metrics": ins,
            }

        print(f"    计算了 {len(rewards)} 个 creative 的 reward")
        return rewards

    # ========================================================================
    # Step 3: 更新 Bandit
    # ========================================================================

    def _update_bandit(self, rewards: dict[str, dict[str, Any]]) -> None:
        """用 T(t) 调制更新 Bandit"""
        updated = 0

        for cid, r in rewards.items():
            # 从 creative_id 提取 gene_type 和 gene_value
            # 简化: 假设 creative_id 格式为 "gene_type:gene_value"
            try:
                parts = cid.split(":", 1)
                if len(parts) == 2:
                    gt, gv = parts
                else:
                    gt = "unknown"
                    gv = cid
            except Exception:
                gt = "unknown"
                gv = cid

            normalized = r["normalized"]
            self.policy_core.update_bandit(self.bandit, gt, gv, normalized)
            updated += 1

        # 推进退火
        self.policy_core.advance()

        print(f"    更新了 {updated} 个 arm, T → {self.policy_core.temperature:.3f}")

    # ========================================================================
    # Step 4: 分配预算
    # ========================================================================

    def _allocate_budget(self) -> dict[str, float]:
        """用 PolicyExecutionBridge 分配预算 (含 3 个保护)"""
        budget_plan: dict[str, float] = {}

        for gene_type, adset_id in self._adset_mapping.items():
            # 使用 bridge 的 T(t)-modulated policy 输出
            policy_output = self.bridge.get_policy_output(self.bandit, gene_type)
            if not policy_output:
                continue

            # 通过 bridge 执行完整保护链
            br = self.bridge.step(
                policy_output=policy_output,
                bandit=self.bandit,
                dry_run=True,  # step 内部 dry_run, 预算在 _execute_budget 中执行
            )

            # 合并 budget_plan
            budget_plan.update(br.budget_plan)

            print(f"    {gene_type} → {adset_id}: "
                  f"policy={ {k: f'{v:.1%}' for k, v in br.policy_output.items()} } → "
                  f"budget={ {k: f'${v:,.0f}' for k, v in br.budget_plan.items()} } "
                  f"(T={self.policy_core.temperature:.3f}, "
                  f"protections: ks={br.protections.get('kill_switch', {}).get('active', False)}, "
                  f"conv={br.convergence.get('action', 'hold')})")

        return budget_plan

    # ========================================================================
    # Step 5: 执行预算
    # ========================================================================

    def _execute_budget(self, budget_plan: dict[str, float]) -> None:
        """执行预算分配到 Facebook (v2: 含 3 个生产保护)"""
        if self.dry_run:
            print(f"    [DRY RUN] 模拟执行: {len(budget_plan)} 个 adset")
            for adset_id, budget in budget_plan.items():
                print(f"      {adset_id} → ${budget:,.0f}/day")
            return

        # LIVE 模式
        executor = self._get_executor()
        if not executor:
            print("    [ERROR] FacebookExecutor 未初始化, 跳过执行")
            return

        # 使用 v2 执行 (含 3 个保护)
        result = executor.execute_budget_plan_v2(
            adset_budget_map=budget_plan,
            budget_clamp=True,
            budget_clamp_min_ratio=self.bridge.config.budget_clamp_min_ratio,
            budget_clamp_max_ratio=self.bridge.config.budget_clamp_max_ratio,
            exploration_floor=self.bridge.config.exploration_floor,
            kill_switch_roas_threshold=self.bridge.config.kill_switch_roas_threshold,
            current_roas=self._get_current_roas(),
        )
        print(f"    {'✅' if result.success else '❌'} "
              f"预算更新: {result.budget_updates}, 状态变更: {result.status_changes}")

        if result.budget_errors:
            for err in result.budget_errors:
                print(f"      ⚠️ {err}")

        # 更新 bridge 的 reward 历史 (用于收敛判断)
        if hasattr(result, '_v2_protections'):
            self._update_bridge_reward_from_protections(result._v2_protections)

    def _get_current_roas(self) -> float | None:
        """获取当前总体 ROAS (用于 kill-switch 判断)"""
        # 从最近的 reward 历史计算
        if self.bridge._reward_history:
            recent = self.bridge._reward_history[-10:]
            return sum(recent) / len(recent)
        return None

    def _update_bridge_reward_from_protections(self, protections: dict) -> None:
        """从保护信息更新 bridge 的 reward 历史"""
        # 简化: 如果执行成功, 记录一个正向 reward
        # 实际应由数据回流步骤更新
        pass

    # ========================================================================
    # 辅助
    # ========================================================================

    def _get_executor(self):
        """懒初始化 FacebookExecutor"""
        if self._executor is not None:
            return self._executor

        token = self.config.get("access_token")
        ad_account_id = self.config.get("ad_account_id")
        if not token or not ad_account_id:
            print("    [ERROR] 缺少 access_token 或 ad_account_id")
            return None

        try:
            from market_ops.creative_intelligence.facebook_executor import FacebookExecutor
            self._executor = FacebookExecutor(
                access_token=token,
                ad_account_id=ad_account_id,
            )
            # 同步到 bridge
            self.bridge.executor = self._executor
            return self._executor
        except Exception as e:
            print(f"    [ERROR] FacebookExecutor 初始化失败: {e}")
            return None


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Closed Loop Runner — 在线策略执行引擎")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="模拟模式 (默认)")
    parser.add_argument("--live", action="store_true",
                        help="真实模式 (调用 Facebook API)")
    parser.add_argument("--config", type=str, default="closed_loop_config.json",
                        help="配置文件路径")
    parser.add_argument("--interval", type=float, default=6,
                        help="循环间隔 (小时)")
    parser.add_argument("--max-iterations", type=int, default=0,
                        help="最大迭代次数 (0=无限)")
    parser.add_argument("--total-budget", type=float, default=1000,
                        help="总日预算")
    args = parser.parse_args()

    # 加载配置
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {}

    # CLI 参数覆盖
    if args.interval:
        config["interval_hours"] = args.interval
    if args.max_iterations:
        config["max_iterations"] = args.max_iterations
    if args.total_budget:
        config["total_budget"] = args.total_budget

    dry_run = not args.live

    runner = ClosedLoopRunner(config=config, dry_run=dry_run)
    runner.run()
    return 0


if __name__ == "__main__":
    main()