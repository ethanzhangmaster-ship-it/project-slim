"""Final Bandit (Spec §13 — 封版)

唯一算法真相。不再有 v7/v8/v9。

唯一 State:  theta, sigma, trials
唯一 Update: delta=reward-theta; theta+=alpha*delta; sigma=(1-beta)*sigma+beta*abs(delta); trials+=1
唯一 Decision: theta DESC
唯一 Sampling: Softmax(theta/tau + gamma*sigma)
Entropy: 系统级, 只调 tau, 不进 ranking
Auction: 仅 diagnostic, 不进 decision
Reward: 仅 observation, 不进 decision

数据流:
    Facebook API → Observation → Reward → Update(theta,sigma) → Policy(theta DESC) → Sampling → Facebook
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ============================================================================
# FinalArm (Spec §13.1) — 只允许 3 个字段
# ============================================================================

@dataclass
class FinalArm:
    """唯一 Arm state (Spec §13.1)

    只允许: theta, sigma, trials
    禁止: value/weight/score/reward_avg/ucb_score/uncertainty/information_gain 等
    """
    gene_type: str
    gene_value: str
    theta: float = 0.0      # quality estimate
    sigma: float = 0.5      # uncertainty
    trials: int = 0         # sample count

    def to_dict(self) -> dict[str, Any]:
        """序列化 — 只有 3 个状态字段"""
        return {
            "gene_type": self.gene_type,
            "gene_value": self.gene_value,
            "theta": self.theta,
            "sigma": self.sigma,
            "trials": self.trials,
        }


# ============================================================================
# FinalBandit (Spec §13 — 封版)
# ============================================================================

class FinalBandit:
    """Final Architecture Bandit (Spec §13)

    封版后不允许新增算法层。仅允许参数调优/工程实现/监控运维。
    """

    # 唯一可调参数 (Spec §13.10: 仅允许参数调优)
    # 2026-06-26 grid search 最优值 (320 组合, 真实数据)
    alpha: float = 0.25      # theta 学习率 (↑ 从 0.15, 更快收敛)
    beta: float = 0.20       # sigma 学习率 (↑ 从 0.10, 更快降低不确定性)
    tau: float = 0.10        # sampling temperature (↓ 从 0.20, 更集中 exploit)
    gamma: float = 0.15      # exploration weight (↓ 从 0.30, 减少随机探索)

    # Entropy 自动调温 (Spec §13.6)
    TAU_MIN: float = 0.05
    TAU_MAX: float = 0.50
    ENTROPY_TARGET: float = 0.15

    def __init__(
        self,
        memory_path: str | Path | None = None,
        db_backup_path: str | Path | None = None,
    ) -> None:
        self.arms: dict[str, FinalArm] = {}
        self._memory_path = Path(memory_path) if memory_path else None
        self._db_backup_path = Path(db_backup_path) if db_backup_path else None
        self._step = 0
        # 持久化去重: key = f"{gene_type}_{gene_value}:{date}"
        self._learned_dates: set[str] = set()
        # 优先从 DB 恢复, 其次从 JSON
        if self._db_backup_path:
            restored = self._restore_from_db()
            if not restored and self._memory_path and self._memory_path.exists():
                self._load_memory()
        elif self._memory_path and self._memory_path.exists():
            self._load_memory()

    # ========================================================================
    # 唯一 Update (Spec §13.2)
    # ========================================================================

    def update(self, gene_type: str, gene_value: str, reward: float) -> None:
        """Spec §13.2: 唯一更新公式

        delta = reward - theta
        theta += alpha * delta
        sigma = (1 - beta) * sigma + beta * abs(delta)
        trials += 1
        """
        self._step += 1
        key = f"{gene_type}_{gene_value}"
        if key not in self.arms:
            self.arms[key] = FinalArm(gene_type=gene_type, gene_value=gene_value)

        arm = self.arms[key]
        delta = reward - arm.theta
        arm.theta += self.alpha * delta
        arm.sigma = (1 - self.beta) * arm.sigma + self.beta * abs(delta)
        arm.trials += 1

        self._save_memory()

    # ========================================================================
    # Policy Stabilizer Core: T(t)-modulated update (Spec §14)
    # ========================================================================

    def update_with_temperature(
        self, gene_type: str, gene_value: str, reward: float, T: float,
    ) -> None:
        """T(t)-modulated Bandit update (Policy Stabilizer Core §14)

        T(t) 控制学习速度:
          T 高 → 学得快 (探索阶段)
          T 低 → 学得慢 (收敛阶段)

        delta = reward - theta
        theta += alpha * delta * T
        sigma = (1 - beta * T) * sigma + beta * abs(delta)
        trials += 1
        """
        self._step += 1
        key = f"{gene_type}_{gene_value}"
        if key not in self.arms:
            self.arms[key] = FinalArm(gene_type=gene_type, gene_value=gene_value)

        arm = self.arms[key]
        delta = reward - arm.theta
        arm.theta += self.alpha * delta * T
        arm.sigma = (1 - self.beta * T) * arm.sigma + self.beta * abs(delta)
        arm.trials += 1

        self._save_memory()

    # ========================================================================
    # 持久化去重 (工程层, 不进入算法状态)
    # ========================================================================

    def has_learned_on_date(self, gene_type: str, gene_value: str, date_str: str) -> bool:
        """检查 (gene_type, gene_value, date) 是否已学习过。

        这是工程层去重, 不进入 theta/sigma/trials 状态。
        """
        key = f"{gene_type}_{gene_value}:{date_str}"
        return key in self._learned_dates

    def mark_learned_on_date(self, gene_type: str, gene_value: str, date_str: str) -> None:
        """标记 (gene_type, gene_value, date) 已学习。

        去重信息持久化到 memory JSON 的 _learned_dates 字段。
        """
        key = f"{gene_type}_{gene_value}:{date_str}"
        if key not in self._learned_dates:
            self._learned_dates.add(key)
            self._save_memory()
    # ========================================================================

    def rank(self, gene_type: str) -> list[str]:
        """Spec §13.4: Ranking = theta DESC

        唯一 decision 依据。不允许 reward/UCB/auction/entropy 参与。
        """
        type_arms = [a for a in self.arms.values() if a.gene_type == gene_type]
        sorted_arms = sorted(type_arms, key=lambda a: a.theta, reverse=True)
        return [a.gene_value for a in sorted_arms]

    def best(self, gene_type: str) -> str:
        """theta 最高的 arm (greedy choice)"""
        ranked = self.rank(gene_type)
        return ranked[0] if ranked else "unknown"

    # ========================================================================
    # 唯一 Sampling (Spec §13.5) — Softmax(theta/tau + gamma*sigma)
    # ========================================================================

    def sample(self, gene_type: str) -> str:
        """Spec §13.5: Softmax(theta/tau + gamma*sigma)

        Exploration 只影响 Sampling, 不影响 Ranking。
        sigma 高 (uncertainty 大) → sampling 概率高 → 自然探索。
        """
        type_arms = [a for a in self.arms.values() if a.gene_type == gene_type]
        if not type_arms:
            return "unknown"

        # 全新 arm: 均匀随机
        if all(a.trials == 0 for a in type_arms):
            return random.choice(type_arms).gene_value

        # Spec §13.6: Entropy 自动调 tau (只调温度, 不进 ranking)
        tau = self._auto_tau(gene_type)

        # Softmax(theta/tau + gamma*sigma)
        scores = [a.theta / tau + self.gamma * a.sigma for a in type_arms]
        max_score = max(scores)
        exp_scores = [math.exp((s - max_score) / max(tau, 1e-6)) for s in scores]
        total = sum(exp_scores)
        probs = [e / total for e in exp_scores]

        # 按概率采样
        r = random.random()
        cum = 0.0
        for arm, prob in zip(type_arms, probs):
            cum += prob
            if r <= cum:
                return arm.gene_value
        return type_arms[-1].gene_value

    # ========================================================================
    # Policy Stabilizer Core: T(t)-modulated sampling (Spec §14)
    # ========================================================================

    def sample_with_temperature(self, gene_type: str, T: float) -> str:
        """T(t)-modulated action selection (Policy Stabilizer Core §14)

        score_i = theta_i + T * sigma_i
        P(select i) = softmax(score_i)

        T 高 → sigma (探索) 权重高 → 广泛探索
        T 低 → theta (收益) 权重高 → 集中 exploit
        """
        type_arms = [a for a in self.arms.values() if a.gene_type == gene_type]
        if not type_arms:
            return "unknown"

        if all(a.trials == 0 for a in type_arms):
            return random.choice(type_arms).gene_value

        # score = theta + T * sigma
        scores = [a.theta + T * a.sigma for a in type_arms]
        max_score = max(scores)
        # 数值稳定: softmax with temperature
        effective_tau = max(T, 0.05)  # 防止 T→0 时除零
        exp_scores = [math.exp((s - max_score) / effective_tau) for s in scores]
        total = sum(exp_scores)
        probs = [e / total for e in exp_scores]

        r = random.random()
        cum = 0.0
        for arm, prob in zip(type_arms, probs):
            cum += prob
            if r <= cum:
                return arm.gene_value
        return type_arms[-1].gene_value

    # ========================================================================
    # Entropy (Spec §13.6) — 系统状态, 只调 tau
    # ========================================================================

    def entropy(self, gene_type: str) -> float:
        """Spec §13.6: entropy = std([arm.theta for arm in arms])

        系统级状态, 不是 Arm 状态。只用于调 tau, 不进 ranking。
        """
        type_arms = [a for a in self.arms.values() if a.gene_type == gene_type]
        if len(type_arms) < 2:
            return 0.0
        thetas = [a.theta for a in type_arms]
        mean_t = sum(thetas) / len(thetas)
        var = sum((t - mean_t) ** 2 for t in thetas) / len(thetas)
        return var ** 0.5

    def _auto_tau(self, gene_type: str) -> float:
        """Spec §13.6: tau = auto_adjust(entropy)

        entropy 高 (系统混乱) → tau 降低 → 集中 exploit
        entropy 低 (系统确定) → tau 升高 → 鼓励 explore
        """
        e = self.entropy(gene_type)
        # entropy 低于 target → 提高 tau (鼓励探索)
        # entropy 高于 target → 降低 tau (集中 exploit)
        ratio = e / max(self.ENTROPY_TARGET, 1e-6)
        adjusted = self.tau * (1.0 + (1.0 - min(ratio, 2.0)) * 0.5)
        return max(self.TAU_MIN, min(self.TAU_MAX, adjusted))

    # ========================================================================
    # Diagnostic (Spec §13.7 — Auction 等仅用于 diagnostic)
    # ========================================================================

    def get_state(self, gene_type: str) -> dict[str, Any]:
        """返回系统状态快照 (仅 diagnostic, 不影响 decision)"""
        type_arms = [a for a in self.arms.values() if a.gene_type == gene_type]
        return {
            "n_arms": len(type_arms),
            "entropy": self.entropy(gene_type),
            "tau": self._auto_tau(gene_type),
            "step": self._step,
            "arms": {a.gene_value: {
                "theta": round(a.theta, 4),
                "sigma": round(a.sigma, 4),
                "trials": a.trials,
            } for a in type_arms},
            "ranking": self.rank(gene_type),
        }

    # ========================================================================
    # 持久化 (只存 theta/sigma/trials, 无隐藏状态)
    # ========================================================================

    def _load_memory(self) -> None:
        if not self._memory_path or not self._memory_path.exists():
            return
        with open(self._memory_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._step = data.get("_step", 0)
            self._learned_dates = set(data.get("_learned_dates", []))
            for key, arm_data in data.get("arms", {}).items():
                self.arms[key] = FinalArm(
                    gene_type=arm_data["gene_type"],
                    gene_value=arm_data["gene_value"],
                    theta=arm_data.get("theta", 0.0),
                    sigma=arm_data.get("sigma", 0.5),
                    trials=arm_data.get("trials", 0),
                )

    def _save_memory(self) -> None:
        if not self._memory_path:
            return
        data = {
            "_step": self._step,
            "_learned_dates": sorted(self._learned_dates),
            "arms": {k: v.to_dict() for k, v in self.arms.items()},
        }
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写入: 先写 tmp, 再 rename
        tmp_path = self._memory_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self._memory_path)

        # 同步备份到 DuckDB (如果配置了)
        if self._db_backup_path:
            try:
                self._backup_to_db()
            except Exception:
                pass  # DB 备份失败不影响主流程

    # ========================================================================
    # DB 备份 (工程层, 不进入算法状态)
    # ========================================================================

    def _ensure_db_backup_schema(self, conn) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bandit_state (
                arm_key VARCHAR PRIMARY KEY,
                gene_type VARCHAR,
                gene_value VARCHAR,
                theta DOUBLE,
                sigma DOUBLE,
                trials INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bandit_learned_dates (
                date_key VARCHAR PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _backup_to_db(self) -> None:
        """将当前状态同步写入 DuckDB"""
        import duckdb
        conn = duckdb.connect(str(self._db_backup_path), read_only=False)
        self._ensure_db_backup_schema(conn)

        # 写入 arm 状态
        for key, arm in self.arms.items():
            conn.execute("""
                INSERT OR REPLACE INTO bandit_state
                    (arm_key, gene_type, gene_value, theta, sigma, trials, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [key, arm.gene_type, arm.gene_value, arm.theta, arm.sigma, arm.trials])

        # 写入去重记录
        for dk in self._learned_dates:
            conn.execute("""
                INSERT OR IGNORE INTO bandit_learned_dates (date_key)
                VALUES (?)
            """, [dk])

        conn.close()

    def _restore_from_db(self) -> bool:
        """从 DuckDB 恢复状态。返回 True 表示成功恢复"""
        if not self._db_backup_path or not self._db_backup_path.exists():
            return False
        try:
            import duckdb
            conn = duckdb.connect(str(self._db_backup_path), read_only=True)

            # 检查表是否存在
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_name IN ('bandit_state', 'bandit_learned_dates')"
            ).fetchall()
            if len(tables) < 2:
                conn.close()
                return False

            # 恢复 arms
            rows = conn.execute(
                "SELECT arm_key, gene_type, gene_value, theta, sigma, trials FROM bandit_state"
            ).fetchall()
            if not rows:
                conn.close()
                return False

            for row in rows:
                key, gt, gv, theta, sigma, trials = row
                self.arms[key] = FinalArm(
                    gene_type=gt, gene_value=gv,
                    theta=float(theta), sigma=float(sigma), trials=int(trials),
                )

            # 恢复 learned_dates
            date_rows = conn.execute("SELECT date_key FROM bandit_learned_dates").fetchall()
            self._learned_dates = {str(r[0]) for r in date_rows}

            # 计算 _step
            self._step = sum(a.trials for a in self.arms.values())

            conn.close()
            return True
        except Exception:
            return False

    def backup_to_db(self) -> bool:
        """手动触发 DB 备份 (公开接口)"""
        if not self._db_backup_path:
            return False
        try:
            self._backup_to_db()
            return True
        except Exception:
            return False
