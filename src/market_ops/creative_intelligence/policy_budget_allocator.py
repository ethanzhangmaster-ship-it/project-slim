"""Policy Budget Allocator — 可替换 FinalBandit 决策层的 Policy 驱动预算分配器

从 "rule-based media buying system" → "policy-driven allocator" 的最后一层。

核心替换:
  state_t → FinalBandit(theta) → softmax → budget allocation
  ↓
  state_t → PolicyNetwork → probability distribution → budget allocation

架构:
  - PolicyBudgetAllocator: 顶层控制器, 统一 allocate() 接口
  - XGBoostRanker: MVP 版本, 基于 ML 的 ranking → softmax 分配
  - HybridPolicyController: 混合控制器, 融合 policy + bandit + exploration

保留的现有模块:
  - Reward Stabilizer: EMA 平滑 + cohort 归一化
  - T(t) Annealing: PolicyStabilizerCore 温度控制
  - Exploration Logic: sigma-based exploration
  - Creative Graph: 创意特征 pipeline

替换的:
  - theta ranking → learned policy distribution
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from market_ops.creative_intelligence.final_bandit import FinalBandit

# ============================================================================
# 配置: 默认输入特征 (基于现有 unified_state 表)
# ============================================================================

DEFAULT_FEATURE_COLUMNS = [
    "ctr",           # 点击率
    "cpm",           # 千次展示成本
    "spend",         # 花费
    "installs",      # 安装数
    "roas_d7",       # 7日 ROAS
    "cpi",           # 单次安装成本
    "ipm",           # 千次展示安装数
    "engagement_score",  # 参与度
    "conversion_rate",   # 转化率
    "retention_proxy",   # 留存代理
    "cohort_age",        # 素材年龄
    "impressions",       # 展示量
    "clicks",            # 点击数
]

# 数值特征 (直接使用)
NUMERIC_FEATURES = [
    "ctr", "cpm", "spend", "installs", "roas_d7", "cpi", "ipm",
    "engagement_score", "conversion_rate", "retention_proxy",
    "cohort_age", "impressions", "clicks",
]

# 类别特征 (需要 one-hot)
CATEGORICAL_FEATURES = [
    "creative_type", "hook_type", "visual_style", "emotion_tag",
    "warm_cool", "game_mechanic_tag", "spend_bucket", "cpm_bucket",
    "mutation_type", "primary_color",
]


# ============================================================================
# 输出结构
# ============================================================================

@dataclass
class AllocationResult:
    """单个 creative 的预算分配结果"""
    creative_id: str
    probability: float       # 策略概率 p_i
    budget: float            # 预算金额
    expected_roas: float     # 预期 ROAS
    exploration_score: float  # 探索得分 (sigma/uncertainty)
    gene_type: str = ""
    gene_value: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "probability": round(self.probability, 4),
            "budget": round(self.budget, 2),
            "expected_roas": round(self.expected_roas, 4),
            "exploration_score": round(self.exploration_score, 4),
            "gene_type": self.gene_type,
            "gene_value": self.gene_value,
        }


@dataclass
class BudgetPlan:
    """完整的预算分配方案"""
    allocations: list[AllocationResult]
    total_budget: float
    temperature: float
    mode: str  # "policy" | "hybrid" | "softmax"
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def total_allocated(self) -> float:
        return sum(a.budget for a in self.allocations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allocations": [a.to_dict() for a in self.allocations],
            "total_budget": self.total_budget,
            "temperature": self.temperature,
            "mode": self.mode,
            "meta": self.meta,
        }


# ============================================================================
# Policy Model 基类 (可替换实现)
# ============================================================================

class PolicyModel:
    """Policy Model 基类 — 定义 predict() 接口

    子类实现:
      - XGBoostRanker: 基于 XGBoost 的 ranking 模型
      - LightGBMRanker: 基于 LightGBM 的 ranking 模型
      - NeuralPolicyNetwork: 未来 deep RL 版本
    """

    def predict(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        """对一批 state_t 进行推理, 返回 logits/scores

        Args:
            state_batch: list of state_t dicts, 每个 dict 包含特征列

        Returns:
            np.ndarray shape (N,), 每个 creative 的 score (越高越好)
        """
        raise NotImplementedError

    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> None:
        """训练模型

        Args:
            X: feature matrix (N, F)
            y: target labels (N,)
        """
        raise NotImplementedError

    def save(self, path: str | Path) -> None:
        raise NotImplementedError

    def load(self, path: str | Path) -> None:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.__class__.__name__


# ============================================================================
# XGBoost Ranker (MVP 版本)
# ============================================================================

class XGBoostRanker(PolicyModel):
    """XGBoost 排序器 — MVP 最小落地版本

    XGBoost → predict scores → softmax → budget allocation

    用法:
        ranker = XGBoostRanker()
        ranker.fit(X_train, y_train)  # X: features, y: reward
        logits = ranker.predict(state_batch)
    """

    def __init__(self, params: dict[str, Any] | None = None):
        self._model = None
        self._params = params or {
            "max_depth": 4,
            "learning_rate": 0.1,
            "n_estimators": 100,
            "objective": "reg:squarederror",
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }
        self._fitted = False

    def predict(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        if not self._fitted:
            # 未训练: 返回随机 scores + 基于简单启发式的排序
            return self._heuristic_predict(state_batch)

        X = self._extract_features(state_batch)
        return self._model.predict(X)

    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> None:
        try:
            import xgboost as xgb
            self._model = xgb.XGBRegressor(**self._params)
            self._model.fit(X, y, **kwargs)
            self._fitted = True
        except ImportError:
            # XGBoost 未安装: 回退到启发式
            self._fitted = False

    def save(self, path: str | Path) -> None:
        if self._model and self._fitted:
            self._model.save_model(str(path))

    def load(self, path: str | Path) -> None:
        try:
            import xgboost as xgb
            self._model = xgb.XGBRegressor()
            self._model.load_model(str(path))
            self._fitted = True
        except (ImportError, Exception):
            self._fitted = False

    @property
    def name(self) -> str:
        return "XGBoostRanker"

    # ========================================================================
    # 内部: 特征提取
    # ========================================================================

    def _extract_features(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        """从 state_t dicts 提取数值特征矩阵"""
        rows = []
        for state in state_batch:
            row = []
            for col in NUMERIC_FEATURES:
                val = state.get(col, 0)
                # 安全转换
                try:
                    row.append(float(val) if val is not None else 0.0)
                except (ValueError, TypeError):
                    row.append(0.0)
            rows.append(row)
        return np.array(rows, dtype=np.float64)

    def _heuristic_predict(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        """未训练时的启发式排序: 基于 ROAS + CTR 加权

        这是回退策略, 确保系统在 cold start 时不会崩溃。
        """
        scores = []
        for state in state_batch:
            roas = float(state.get("roas_d7", 0) or 0)
            ctr = float(state.get("ctr", 0) or 0)
            inst = float(state.get("installs", 0) or 0)
            spend = float(state.get("spend", 0) or 0)

            # 综合评分: ROAS 主导 + CTR 辅助 + 安装量信号
            roas_score = min(roas / 0.4, 1.0) if roas > 0 else 0
            ctr_score = min(ctr / 10.0, 1.0) if ctr > 0 else 0
            vol_score = min(inst / 100.0, 1.0) if inst > 0 else 0

            score = 0.5 * roas_score + 0.3 * ctr_score + 0.2 * vol_score
            scores.append(score)

        return np.array(scores, dtype=np.float64)


# ============================================================================
# LightGBM Ranker (备选 MVP)
# ============================================================================

class LightGBMRanker(PolicyModel):
    """LightGBM 排序器 — 备选 MVP 版本"""

    def __init__(self, params: dict[str, Any] | None = None):
        self._model = None
        self._params = params or {
            "max_depth": 5,
            "learning_rate": 0.05,
            "n_estimators": 100,
            "objective": "regression",
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "verbose": -1,
        }
        self._fitted = False

    def predict(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        if not self._fitted:
            return self._heuristic_predict(state_batch)
        X = self._extract_features(state_batch)
        return self._model.predict(X)

    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> None:
        try:
            import lightgbm as lgb
            self._model = lgb.LGBMRegressor(**self._params)
            self._model.fit(X, y, **kwargs)
            self._fitted = True
        except ImportError:
            self._fitted = False

    def save(self, path: str | Path) -> None:
        import joblib
        if self._model and self._fitted:
            joblib.dump(self._model, str(path))

    def load(self, path: str | Path) -> None:
        try:
            import joblib
            self._model = joblib.load(str(path))
            self._fitted = True
        except (ImportError, Exception):
            self._fitted = False

    @property
    def name(self) -> str:
        return "LightGBMRanker"

    def _extract_features(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        rows = []
        for state in state_batch:
            row = []
            for col in NUMERIC_FEATURES:
                val = state.get(col, 0)
                try:
                    row.append(float(val) if val is not None else 0.0)
                except (ValueError, TypeError):
                    row.append(0.0)
            rows.append(row)
        return np.array(rows, dtype=np.float64)

    def _heuristic_predict(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        scores = []
        for state in state_batch:
            roas = float(state.get("roas_d7", 0) or 0)
            ctr = float(state.get("ctr", 0) or 0)
            inst = float(state.get("installs", 0) or 0)
            roas_score = min(roas / 0.4, 1.0) if roas > 0 else 0
            ctr_score = min(ctr / 10.0, 1.0) if ctr > 0 else 0
            vol_score = min(inst / 100.0, 1.0) if inst > 0 else 0
            score = 0.5 * roas_score + 0.3 * ctr_score + 0.2 * vol_score
            scores.append(score)
        return np.array(scores, dtype=np.float64)


# ============================================================================
# PolicyBudgetAllocator — 核心控制器
# ============================================================================

class PolicyBudgetAllocator:
    """策略预算分配器 — 替换 FinalBandit 决策层

    核心流程:
      1. state_t → PolicyModel.predict() → logits
      2. logits → temperature scaling → softmax → probabilities
      3. probabilities → budget normalization → budget amounts

    安全机制:
      - temperature scaling: 保留 FinalBandit 的 annealing 思想
      - alpha 压缩: budget_i = total_budget * (p_i^alpha) / Σ(p^alpha)
      - 最低预算保护: 防止 creative 完全归零

    用法:
        allocator = PolicyBudgetAllocator(model=XGBoostRanker(), temperature=1.0)
        plan = allocator.allocate(state_batch, total_budget=1000.0)
    """

    # 默认参数
    DEFAULT_ALPHA = 0.8       # 预算压缩因子 (α<1: 平滑, α>1: 集中)
    MIN_BUDGET = 5.0          # 单 creative 最低预算
    TAU_MIN = 0.05            # 最低温度
    TAU_MAX = 2.0             # 最高温度

    def __init__(
        self,
        policy_model: PolicyModel,
        temperature: float = 1.0,
        alpha: float | None = None,
        memory_path: str | Path | None = None,
    ):
        """
        Args:
            policy_model: PolicyModel 实例 (XGBoostRanker / LightGBMRanker)
            temperature: 初始温度 (控制 explore/exploit, 可被 PolicyStabilizerCore 驱动)
            alpha: 预算压缩因子 (None = 使用 DEFAULT_ALPHA)
            memory_path: 持久化路径
        """
        self.model = policy_model
        self.T = temperature
        self.alpha = alpha if alpha is not None else self.DEFAULT_ALPHA

        self._step = 0
        self._memory_path = Path(memory_path) if memory_path else None
        if self._memory_path and self._memory_path.exists():
            self._load()

    # ========================================================================
    # 核心: allocate — 唯一的对外接口
    # ========================================================================

    def allocate(
        self,
        state_batch: list[dict[str, Any]],
        total_budget: float = 1000.0,
        temperature: float | None = None,
    ) -> BudgetPlan:
        """从 state_t → 预算分配

        Args:
            state_batch: list[state_t], 每个 dict 包含 creative 特征 + 身份信息
            total_budget: 总预算
            temperature: 覆盖 self.T (None = 使用 self.T)

        Returns:
            BudgetPlan: 完整的预算分配方案
        """
        T = temperature if temperature is not None else self.T
        n = len(state_batch)
        if n == 0:
            return BudgetPlan(
                allocations=[], total_budget=total_budget,
                temperature=T, mode="policy",
            )

        # 1. Policy Model 推理 → logits
        logits = self.model.predict(state_batch)

        # 2. Temperature scaling
        T_clamped = max(self.TAU_MIN, min(self.TAU_MAX, T))
        scaled = logits / T_clamped

        # 3. Softmax → probability distribution
        # 数值稳定: subtract max
        scaled_max = np.max(scaled)
        exp_scores = np.exp(scaled - scaled_max)
        total_exp = np.sum(exp_scores)
        if total_exp == 0:
            probs = np.ones(n) / n
        else:
            probs = exp_scores / total_exp

        # 4. Budget normalization with alpha compression
        budget_shares = self._normalize_budget(probs)

        # 5. 构建 AllocationResult
        allocations = []
        for i, state in enumerate(state_batch):
            cid = state.get("creative_id", f"unknown_{i}")
            roas = float(state.get("roas_d7", 0) or 0)
            sigma = float(state.get("sigma", 0) or 0)
            gene_type = str(state.get("gene_type", ""))
            gene_value = str(state.get("gene_value", ""))

            budget_amount = budget_shares[i] * total_budget
            # 最低预算保护
            budget_amount = max(self.MIN_BUDGET, budget_amount)

            allocations.append(AllocationResult(
                creative_id=cid,
                probability=float(probs[i]),
                budget=budget_amount,
                expected_roas=roas,
                exploration_score=sigma,
                gene_type=gene_type,
                gene_value=gene_value,
            ))

        self._step += 1
        self._save()

        return BudgetPlan(
            allocations=allocations,
            total_budget=total_budget,
            temperature=T,
            mode="policy",
            meta={
                "n_creatives": n,
                "alpha": self.alpha,
                "model": self.model.name,
                "step": self._step,
            },
        )

    # ========================================================================
    # Hybrid Policy Controller — 融合 policy + bandit + exploration
    # ========================================================================

    def allocate_hybrid(
        self,
        state_batch: list[dict[str, Any]],
        bandit: FinalBandit,
        total_budget: float = 1000.0,
        temperature: float | None = None,
        w_policy: float = 0.6,
        w_bandit: float = 0.3,
        w_explore: float = 0.1,
    ) -> BudgetPlan:
        """Hybrid Policy Controller: 融合三种信号

        final_score = w_policy * policy_model(state) + w_bandit * bandit_theta + w_explore * exploration_noise

        Args:
            state_batch: state_t 列表
            bandit: FinalBandit 实例 (提供 theta 作为稳定锚点)
            w_policy: policy model 权重
            w_bandit: bandit theta 权重
            w_explore: exploration noise 权重
        """
        T = temperature if temperature is not None else self.T
        n = len(state_batch)
        if n == 0:
            return BudgetPlan(
                allocations=[], total_budget=total_budget,
                temperature=T, mode="hybrid",
            )

        # 1. Policy 信号
        policy_logits = self.model.predict(state_batch)
        policy_norm = self._minmax_norm(policy_logits)

        # 2. Bandit 信号 (theta)
        bandit_scores = np.zeros(n)
        for i, state in enumerate(state_batch):
            gt = state.get("gene_type", "")
            gv = state.get("gene_value", "")
            key = f"{gt}_{gv}"
            arm = bandit.arms.get(key)
            if arm:
                bandit_scores[i] = arm.theta

        bandit_norm = self._minmax_norm(bandit_scores)

        # 3. Exploration 信号 (sigma-based noise)
        explore_scores = np.zeros(n)
        for i, state in enumerate(state_batch):
            gt = state.get("gene_type", "")
            gv = state.get("gene_value", "")
            key = f"{gt}_{gv}"
            arm = bandit.arms.get(key)
            if arm:
                # 高 sigma → 高探索得分
                explore_scores[i] = arm.sigma * random.uniform(0.5, 1.5)
            else:
                explore_scores[i] = random.uniform(0, 0.5)

        explore_norm = self._minmax_norm(explore_scores)

        # 4. 加权融合
        final_scores = (
            w_policy * policy_norm
            + w_bandit * bandit_norm
            + w_explore * explore_norm
        )

        # 5. Temperature scaling + softmax
        T_clamped = max(self.TAU_MIN, min(self.TAU_MAX, T))
        scaled = final_scores / T_clamped
        scaled_max = np.max(scaled)
        exp_scores = np.exp(scaled - scaled_max)
        total_exp = np.sum(exp_scores)
        probs = (exp_scores / total_exp) if total_exp > 0 else np.ones(n) / n

        budget_shares = self._normalize_budget(probs)

        allocations = []
        for i, state in enumerate(state_batch):
            cid = state.get("creative_id", f"unknown_{i}")
            roas = float(state.get("roas_d7", 0) or 0)
            sigma = float(state.get("sigma", 0) or 0)
            gt = str(state.get("gene_type", ""))
            gv = str(state.get("gene_value", ""))

            budget_amount = max(self.MIN_BUDGET, budget_shares[i] * total_budget)

            allocations.append(AllocationResult(
                creative_id=cid,
                probability=float(probs[i]),
                budget=budget_amount,
                expected_roas=roas,
                exploration_score=sigma,
                gene_type=gt,
                gene_value=gv,
            ))

        self._step += 1
        self._save()

        return BudgetPlan(
            allocations=allocations,
            total_budget=total_budget,
            temperature=T,
            mode="hybrid",
            meta={
                "n_creatives": n,
                "alpha": self.alpha,
                "model": self.model.name,
                "step": self._step,
                "weights": {
                    "policy": w_policy,
                    "bandit": w_bandit,
                    "explore": w_explore,
                },
            },
        )

    # ========================================================================
    # 内部: 预算归一化
    # ========================================================================

    def _normalize_budget(self, probs: np.ndarray) -> np.ndarray:
        """预算归一化: budget_i = (p_i^alpha) / Σ(p^alpha)

        alpha 控制探索 vs 收敛:
          alpha < 1 → 平滑分布 (多探索)
          alpha = 1 → 原始概率
          alpha > 1 → 集中赢家 (强收敛)
        """
        if self.alpha == 1.0:
            return probs

        # 安全压缩: p_i^alpha
        compressed = np.power(np.maximum(probs, 1e-10), self.alpha)
        total = np.sum(compressed)
        if total == 0:
            return np.ones_like(probs) / len(probs)
        return compressed / total

    @staticmethod
    def _minmax_norm(scores: np.ndarray) -> np.ndarray:
        """Min-max 归一化到 [0, 1]"""
        s_min = np.min(scores)
        s_max = np.max(scores)
        if s_max - s_min < 1e-10:
            return np.ones_like(scores) * 0.5
        return (scores - s_min) / (s_max - s_min)

    # ========================================================================
    # 温度控制 (对接 PolicyStabilizerCore)
    # ========================================================================

    def set_temperature(self, T: float) -> None:
        """由 PolicyStabilizerCore.temperature 驱动"""
        self.T = T

    @property
    def temperature(self) -> float:
        return self.T

    # ========================================================================
    # 持久化
    # ========================================================================

    def _save(self) -> None:
        if not self._memory_path:
            return
        data = {
            "temperature": self.T,
            "alpha": self.alpha,
            "step": self._step,
            "model": self.model.name,
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
            self.T = data.get("temperature", self.T)
            self.alpha = data.get("alpha", self.alpha)
            self._step = data.get("step", 0)

    def stats(self) -> dict[str, Any]:
        return {
            "model": self.model.name,
            "temperature": self.T,
            "alpha": self.alpha,
            "step": self._step,
        }


# ============================================================================
# 工具函数: 从 unified_state 表构建 state_batch
# ============================================================================

def build_state_batch_from_db(
    db_path: str | Path,
    project: str | None = None,
    date: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """从 unified_state 表提取 state_batch, 用于 PolicyBudgetAllocator.allocate()

    Args:
        db_path: DuckDB 路径
        project: 过滤项目 (如 'P04')
        date: 过滤日期
        limit: 最大行数

    Returns:
        list of state_t dicts
    """
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)

    # 检查表是否存在
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name = 'unified_state'"
    ).fetchall()
    if not tables:
        conn.close()
        return []

    conditions = []
    params: list = []
    if project:
        conditions.append("project = ?")
        params.append(project)
    if date:
        conditions.append("date = ?")
        params.append(date)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # 构建查询列
    columns = NUMERIC_FEATURES + ["creative_id", "project", "gene_type", "gene_value"]
    # 添加 sigma 相关: 用 conversion_rate 的变体作为 proxy
    # 实际 sigma 需要从 bandit 获取, 这里用 retention_proxy 作为 uncertainty proxy
    col_str = ", ".join(f'COALESCE({c}, 0) as {c}' for c in NUMERIC_FEATURES)
    col_str += ", creative_id, project, 'creative' as gene_type, creative_id as gene_value"

    sql = f"""
        SELECT {col_str}
        FROM unified_state
        {where}
        ORDER BY date DESC, spend DESC
        LIMIT ?
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    col_names = [d[0] for d in conn.description]
    conn.close()

    state_batch = []
    for row in rows:
        state = dict(zip(col_names, row))
        # 添加 sigma (从 bandit 获取, 这里给默认值)
        state.setdefault("sigma", 0.3)
        state_batch.append(state)

    return state_batch


# ============================================================================
# NeuralPolicyRanker — 对接 policy_network.py 的 PyTorch/Linear 模型
# ============================================================================

class NeuralPolicyRanker(PolicyModel):
    """Neural Network Policy Ranker — 适配 policy_network.py 的 PolicyModel

    将 policy_network.PolicyModel (PyTorch 或 Linear) 包装为
    policy_budget_allocator.PolicyModel 接口, 无缝接入 PolicyBudgetAllocator。

    用法:
        from market_ops.creative_intelligence.policy_network import PolicyModel as NNPolicyModel
        nn_model = NNPolicyModel.load("output/policy_model")
        ranker = NeuralPolicyRanker(nn_model)
        allocator = PolicyBudgetAllocator(policy_model=ranker, temperature=1.0)
        plan = allocator.allocate(state_batch, total_budget=1000)
    """

    def __init__(self, nn_policy_model=None):
        """
        Args:
            nn_policy_model: policy_network.PolicyModel 实例 (None = 延迟加载)
        """
        self._nn_model = nn_policy_model
        self._fitted = nn_policy_model is not None

    def predict(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        """对 state_batch 推理, 返回 policy scores (非 softmax)"""
        if not self._fitted or self._nn_model is None:
            return self._heuristic_predict(state_batch)

        # 用 nn_model 的 encoder 编码, 然后预测 scores
        try:
            X = self._nn_model.encoder.encode_batch(state_batch)
            if self._nn_model.backend == "torch":
                # PyTorch: 返回 policy_score (pre-softmax)
                import torch
                self._nn_model._model.eval()
                with torch.no_grad():
                    t = torch.from_numpy(X).float()
                    scores = self._nn_model._model.policy_score(t)
                    return scores.numpy()
            else:
                # Linear: 返回原始 scores
                return self._nn_model._model.predict_scores(X)
        except Exception:
            return self._heuristic_predict(state_batch)

    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> None:
        """训练 (通过 policy_network.PolicyModel)"""
        # NeuralPolicyRanker 的训练由 policy_trainer.py 管理
        # 这里只是接口占位
        pass

    def save(self, path: str | Path) -> None:
        if self._nn_model:
            self._nn_model.save(path)

    def load(self, path: str | Path) -> None:
        from market_ops.creative_intelligence.policy_network import PolicyModel as NNPolicyModel
        try:
            self._nn_model = NNPolicyModel.load(path)
            self._fitted = True
        except Exception:
            self._fitted = False

    @property
    def name(self) -> str:
        if self._nn_model:
            return f"NeuralPolicyRanker({self._nn_model.backend})"
        return "NeuralPolicyRanker(unfitted)"

    def _heuristic_predict(self, state_batch: list[dict[str, Any]]) -> np.ndarray:
        """未训练时的启发式排序"""
        scores = []
        for state in state_batch:
            roas = float(state.get("roas_d7", 0) or 0)
            ctr = float(state.get("ctr", 0) or 0)
            reward = float(state.get("reward", 0) or 0)
            score = 0.5 * min(roas, 1.0) + 0.3 * min(ctr / 10.0, 1.0) + 0.2 * reward
            scores.append(score)
        return np.array(scores, dtype=np.float64)


def build_state_batch_from_bandit(
    bandit: FinalBandit,
    state_batch: list[dict[str, Any]],
    gene_type: str = "creative",
) -> list[dict[str, Any]]:
    """将 FinalBandit 的 theta/sigma 注入 state_batch

    每个 state 的 gene_value 对应一个 bandit arm.
    """
    for state in state_batch:
        gv = state.get("gene_value", "")
        key = f"{gene_type}_{gv}"
        arm = bandit.arms.get(key)
        if arm:
            state["theta"] = arm.theta
            state["sigma"] = arm.sigma
            state["trials"] = arm.trials
        else:
            state.setdefault("theta", 0.0)
            state.setdefault("sigma", 0.5)
            state.setdefault("trials", 0)
    return state_batch