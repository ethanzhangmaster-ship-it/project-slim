"""Policy Network — Contextual Bandit Policy Model

从 Bandit(theta/sigma) 升级到 Policy Network(state → action distribution)。

Architecture:
    state_t → FeatureEncoder → Shared Representation
        → (CTR head, ROAS head, Risk head)
        → Policy Score → Softmax → Budget/Selection Prob

Training (Hybrid Loss):
    Loss = 0.6 * MSE(ROAS_pred, ROAS) + 0.3 * BCE(top_performing) + 0.1 * entropy_reg

输出:
    creative_id → p(serve), budget_weight, exploration_score

用法:
    # 训练
    model = PolicyNetwork(input_dim=18)
    model.fit(X, y_roas, y_top_flag)
    model.save("output/policy_model.pt")

    # 推理
    probs = model.predict(states)  # → softmax probabilities over creatives

    # 集成到 DistributionController
    plan = controller.allocate_from_policy(project, states, creative_ids, total_budget)
"""

from __future__ import annotations

import json
import math
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# PyTorch: 可选，优先使用；不可用时回退到 sklearn LinearRegression
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# ============================================================================
# Feature Schema — 从 rl_state_t / unified_state 提取的数值特征
# ============================================================================

FEATURE_COLUMNS = [
    # Creative Graph (Policy Input)
    "final_score",          # 164 评分系统综合分
    "ctr_score",            # 164 评分 CTR 分
    "ipm_score",            # 164 评分 IPM 分
    # Facebook Delivery
    "spend",
    "impressions",
    "clicks",
    "ctr",
    "cpm",
    # User Outcome
    "installs",
    "purchases",
    # Economics
    "revenue",
    "roas_d7",
    "cpi",
    # Derived RL State
    "cohort_age",
    "engagement_score",
    "conversion_rate",
    "retention_proxy",
    # Reward
    "reward",
]

FEATURE_DIM = len(FEATURE_COLUMNS)  # 18


# ============================================================================
# Feature Encoder
# ============================================================================

class FeatureEncoder:
    """将 rl_state_t 行编码为归一化数值特征向量。

    归一化策略:
      - 比例类 (ctr, roas, conversion_rate): 已在 [0,1] 或小范围, 直接使用
      - 计数类 (spend, impressions, clicks, installs, purchases, revenue): log1p + min-max
      - 成本类 (cpm, cpi): log1p + min-max
      - 评分类 (final_score, ctr_score, ipm_score): 已在 [0,1]
    """

    def __init__(self) -> None:
        self._fitted = False
        self._stats: dict[str, dict[str, float]] = {}

    def fit(self, rows: list[dict[str, Any]]) -> "FeatureEncoder":
        """计算归一化参数 (min, max, log1p_min, log1p_max)"""
        count_cols = ["spend", "impressions", "clicks", "installs", "purchases", "revenue", "cpm", "cpi"]
        for col in count_cols:
            vals = []
            for r in rows:
                v = float(r.get(col, 0) or 0)
                if v > 0:
                    vals.append(math.log1p(v))
            if vals:
                self._stats[col] = {
                    "log1p_min": min(vals),
                    "log1p_max": max(vals),
                }
            else:
                self._stats[col] = {"log1p_min": 0.0, "log1p_max": 1.0}

        self._fitted = True
        return self

    def encode(self, row: dict[str, Any]) -> np.ndarray:
        """单行编码 → [feature_dim] float32 array"""
        vec = np.zeros(FEATURE_DIM, dtype=np.float32)

        count_cols = {"spend": 3, "impressions": 4, "clicks": 5,
                       "installs": 8, "purchases": 9, "revenue": 10, "cpm": 6, "cpi": 12}

        for i, col in enumerate(FEATURE_COLUMNS):
            raw = float(row.get(col, 0) or 0)

            if col in count_cols and self._fitted:
                st = self._stats.get(col, {})
                log1p_min = st.get("log1p_min", 0.0)
                log1p_max = st.get("log1p_max", 1.0)
                if raw > 0 and log1p_max > log1p_min:
                    v = (math.log1p(raw) - log1p_min) / (log1p_max - log1p_min)
                else:
                    v = 0.0
                vec[i] = max(0.0, min(1.0, v))
            elif col in ("ctr", "conversion_rate", "retention_proxy"):
                # 比例类, 截断到 [0, 1]
                vec[i] = max(0.0, min(1.0, raw))
            elif col in ("roas_d7", "reward"):
                vec[i] = max(0.0, min(1.0, raw))
            elif col in ("cohort_age",):
                vec[i] = raw / max(30.0, 1.0)  # 30 天归一化
            elif col == "engagement_score":
                vec[i] = max(0.0, min(1.0, raw))
            else:
                # final_score, ctr_score, ipm_score: 已在 [0,1]
                vec[i] = max(0.0, min(1.0, raw))

        return vec

    def encode_batch(self, rows: list[dict[str, Any]]) -> np.ndarray:
        """批量编码 → [N, feature_dim]"""
        return np.stack([self.encode(r) for r in rows])

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"stats": self._stats}, f, indent=2)

    def load(self, path: str | Path) -> "FeatureEncoder":
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._stats = data.get("stats", {})
            self._fitted = bool(self._stats)
        return self


# ============================================================================
# Policy Network (PyTorch) — 完整架构
# ============================================================================

if HAS_TORCH:

    class PolicyNetwork(nn.Module):
        """Contextual Bandit Policy Network

        Architecture:
            Input (state_t vector)
              → FeatureEncoder (external)
              → Shared Dense(128) + ReLU + Dropout(0.1)
              → Shared Dense(64) + ReLU
              → ┬ CTR head: Dense(32) → Dense(1)
                ├ ROAS head: Dense(32) → Dense(1)
                └ Risk head: Dense(32) → Dense(1)
              → Policy Score = w_roas*ROAS_pred + w_ctr*CTR_pred - w_risk*Risk_pred
              → Softmax over creatives
        """

        def __init__(
            self,
            input_dim: int = FEATURE_DIM,
            hidden_dim: int = 128,
            shared_dim: int = 64,
            head_dim: int = 32,
            dropout: float = 0.1,
            # Head weights for policy score
            w_roas: float = 0.6,
            w_ctr: float = 0.3,
            w_risk: float = 0.1,
        ) -> None:
            super().__init__()
            self.input_dim = input_dim
            self.w_roas = w_roas
            self.w_ctr = w_ctr
            self.w_risk = w_risk

            # Shared layers
            self.shared = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, shared_dim),
                nn.ReLU(),
            )

            # Task-specific heads
            self.ctr_head = nn.Sequential(
                nn.Linear(shared_dim, head_dim),
                nn.ReLU(),
                nn.Linear(head_dim, 1),
                nn.Sigmoid(),  # CTR ∈ [0, 1]
            )

            self.roas_head = nn.Sequential(
                nn.Linear(shared_dim, head_dim),
                nn.ReLU(),
                nn.Linear(head_dim, 1),
                nn.Softplus(),  # ROAS ≥ 0
            )

            self.risk_head = nn.Sequential(
                nn.Linear(shared_dim, head_dim),
                nn.ReLU(),
                nn.Linear(head_dim, 1),
                nn.Sigmoid(),  # Risk ∈ [0, 1]
            )

        def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
            """Forward pass, returns all head outputs"""
            shared = self.shared(x)
            return {
                "ctr": self.ctr_head(shared).squeeze(-1),
                "roas": self.roas_head(shared).squeeze(-1),
                "risk": self.risk_head(shared).squeeze(-1),
            }

        def policy_score(self, x: torch.Tensor) -> torch.Tensor:
            """Compute policy score = w_roas*ROAS + w_ctr*CTR - w_risk*Risk"""
            outputs = self.forward(x)
            return (
                self.w_roas * outputs["roas"]
                + self.w_ctr * outputs["ctr"]
                - self.w_risk * outputs["risk"]
            )

        def predict(self, x: np.ndarray) -> np.ndarray:
            """Predict softmax probabilities over creatives

            Args:
                x: [N, input_dim] feature matrix

            Returns:
                [N] probability distribution (sums to 1)
            """
            self.eval()
            with torch.no_grad():
                t = torch.from_numpy(x).float()
                scores = self.policy_score(t)
                # Softmax with temperature
                probs = F.softmax(scores, dim=0)
                return probs.numpy()

        def predict_with_details(
            self, x: np.ndarray,
        ) -> dict[str, np.ndarray]:
            """Predict with all intermediate outputs"""
            self.eval()
            with torch.no_grad():
                t = torch.from_numpy(x).float()
                outputs = self.forward(t)
                scores = self.policy_score(t)
                probs = F.softmax(scores, dim=0)
                return {
                    "probabilities": probs.numpy(),
                    "policy_score": scores.numpy(),
                    "ctr_pred": outputs["ctr"].numpy(),
                    "roas_pred": outputs["roas"].numpy(),
                    "risk_pred": outputs["risk"].numpy(),
                }

        def compute_loss(
            self,
            x: torch.Tensor,
            y_roas: torch.Tensor,
            y_top_flag: torch.Tensor,
        ) -> tuple[torch.Tensor, dict[str, float]]:
            """Hybrid loss computation

            Loss = 0.6 * MSE(ROAS_pred, ROAS)
                 + 0.3 * BCE(top_performing_flag)
                 + 0.1 * entropy_regularization
            """
            outputs = self.forward(x)

            # MSE for ROAS prediction
            loss_roas = F.mse_loss(outputs["roas"], y_roas)

            # BCE for top-performing classification
            # Use policy_score as logit for classification
            scores = (
                self.w_roas * outputs["roas"]
                + self.w_ctr * outputs["ctr"]
                - self.w_risk * outputs["risk"]
            )
            loss_top = F.binary_cross_entropy_with_logits(scores, y_top_flag)

            # Entropy regularization (encourage exploration)
            probs = torch.softmax(scores, dim=0)
            eps = 1e-8
            entropy = -torch.sum(probs * torch.log(probs + eps))
            # Normalize entropy: max entropy = log(N), so entropy_ratio ∈ [0, 1]
            n = max(len(probs), 1)
            max_entropy = math.log(n)
            entropy_norm = entropy / max_entropy if max_entropy > 0 else 0.0
            # We want moderate entropy, so penalize extremes
            target_entropy = 0.3  # target entropy ratio
            loss_entropy = (entropy_norm - target_entropy) ** 2

            total_loss = 0.6 * loss_roas + 0.3 * loss_top + 0.1 * loss_entropy

            return total_loss, {
                "loss_roas": loss_roas.item(),
                "loss_top": loss_top.item(),
                "loss_entropy": loss_entropy.item(),
                "entropy": entropy_norm.item() if isinstance(entropy_norm, torch.Tensor) else entropy_norm,
                "total": total_loss.item(),
            }

        def save_model(self, path: str | Path) -> None:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state_dict": self.state_dict(),
                "input_dim": self.input_dim,
                "w_roas": self.w_roas,
                "w_ctr": self.w_ctr,
                "w_risk": self.w_risk,
            }, p)

        @classmethod
        def load_model(cls, path: str | Path) -> "PolicyNetwork":
            checkpoint = torch.load(path, map_location="cpu", weights_only=False)
            model = cls(
                input_dim=checkpoint["input_dim"],
                w_roas=checkpoint.get("w_roas", 0.6),
                w_ctr=checkpoint.get("w_ctr", 0.3),
                w_risk=checkpoint.get("w_risk", 0.1),
            )
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            return model


# ============================================================================
# Policy Trainer (PyTorch)
# ============================================================================

if HAS_TORCH:

    class PolicyTrainer:
        """训练 PolicyNetwork 的封装"""

        def __init__(
            self,
            model: PolicyNetwork,
            lr: float = 1e-3,
            weight_decay: float = 1e-5,
            device: str = "cpu",
        ) -> None:
            self.model = model
            self.device = device
            self.model.to(device)
            self.optimizer = torch.optim.Adam(
                model.parameters(), lr=lr, weight_decay=weight_decay,
            )

        def train_step(
            self, x: np.ndarray, y_roas: np.ndarray, y_top_flag: np.ndarray,
        ) -> dict[str, float]:
            """单步训练"""
            self.model.train()
            self.optimizer.zero_grad()

            t_x = torch.from_numpy(x).float().to(self.device)
            t_roas = torch.from_numpy(y_roas).float().to(self.device)
            t_top = torch.from_numpy(y_top_flag).float().to(self.device)

            loss, metrics = self.model.compute_loss(t_x, t_roas, t_top)
            loss.backward()
            self.optimizer.step()

            return metrics

        def train(
            self,
            x: np.ndarray,
            y_roas: np.ndarray,
            y_top_flag: np.ndarray,
            epochs: int = 100,
            batch_size: int = 64,
            verbose: bool = True,
        ) -> list[dict[str, float]]:
            """完整训练循环"""
            history = []
            n = len(x)

            for epoch in range(epochs):
                # Shuffle
                idx = np.random.permutation(n)
                epoch_losses = []

                for start in range(0, n, batch_size):
                    batch_idx = idx[start:start + batch_size]
                    metrics = self.train_step(
                        x[batch_idx], y_roas[batch_idx], y_top_flag[batch_idx],
                    )
                    epoch_losses.append(metrics)

                # Average
                avg = {k: float(np.mean([m[k] for m in epoch_losses])) for k in epoch_losses[0]}
                history.append(avg)

                if verbose and (epoch % 20 == 0 or epoch == epochs - 1):
                    print(f"  Epoch {epoch:3d}/{epochs} | "
                          f"loss={avg['total']:.4f} | "
                          f"roas={avg['loss_roas']:.4f} | "
                          f"top={avg['loss_top']:.4f} | "
                          f"ent={avg['loss_entropy']:.4f} | "
                          f"H={avg['entropy']:.3f}")

            return history


# ============================================================================
# Linear Scorer (sklearn fallback) — MVP
# ============================================================================

class LinearPolicyScorer:
    """基于 sklearn 的线性策略评分器 (MVP, 无 PyTorch 依赖)

    使用 SGDRegressor 做 reward-weighted ranking:
        score = w · state_features
        P(serve) = softmax(score)
    """

    def __init__(self) -> None:
        self._coef: np.ndarray | None = None
        self._intercept: float = 0.0
        self._fitted = False

    def fit(
        self,
        x: np.ndarray,
        y_reward: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> "LinearPolicyScorer":
        """用 reward 作为 target 拟合线性模型

        Args:
            x: [N, feature_dim]
            y_reward: [N] reward values
            sample_weight: [N] optional, softmax(reward/temperature) weights
        """
        # 闭式解: w = (X^T W X)^{-1} X^T W y
        n, d = x.shape
        if sample_weight is None:
            sample_weight = np.ones(n)

        w_mat = np.diag(sample_weight)
        try:
            xt_w = x.T @ w_mat
            gram = xt_w @ x
            gram += 1e-4 * np.eye(d)  # 正则化
            xt_w_y = xt_w @ y_reward
            self._coef = np.linalg.solve(gram, xt_w_y)
            self._intercept = 0.0
        except np.linalg.LinAlgError:
            # Fallback: 伪逆
            self._coef = np.linalg.lstsq(x, y_reward, rcond=None)[0]
            self._intercept = 0.0

        self._fitted = True
        return self

    def predict_scores(self, x: np.ndarray) -> np.ndarray:
        """返回每个 creative 的原始 score"""
        if not self._fitted:
            raise RuntimeError("Model not fitted")
        return x @ self._coef + self._intercept

    def predict(self, x: np.ndarray, temperature: float = 0.1) -> np.ndarray:
        """返回 softmax 概率分布"""
        scores = self.predict_scores(x)
        # 数值稳定 softmax
        max_score = scores.max()
        exp_scores = np.exp((scores - max_score) / max(temperature, 1e-6))
        return exp_scores / exp_scores.sum()

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump({"coef": self._coef, "intercept": self._intercept}, f)

    def load(self, path: str | Path) -> "LinearPolicyScorer":
        p = Path(path)
        if p.exists():
            with open(p, "rb") as f:
                data = pickle.load(f)
            self._coef = data["coef"]
            self._intercept = data["intercept"]
            self._fitted = True
        return self


# ============================================================================
# 统一接口: PolicyModel
# ============================================================================

@dataclass
class PolicyPrediction:
    """单次推理输出"""
    creative_id: str
    serve_prob: float          # p(serve) — softmax 概率
    budget_weight: float        # budget 权重
    exploration_score: float    # 探索得分 (基于 uncertainty)
    ctr_pred: float = 0.0
    roas_pred: float = 0.0
    risk_pred: float = 0.0


class PolicyModel:
    """统一的 Policy Model 接口

    自动选择 PyTorch PolicyNetwork 或 LinearPolicyScorer。

    用法:
        # 训练
        model = PolicyModel(backend="torch" if HAS_TORCH else "linear")
        model.fit(X, y_roas, y_top_flag)
        model.save("output/policy_model")

        # 推理
        predictions = model.predict_for_creatives(states, creative_ids)
        → [PolicyPrediction, ...]
    """

    def __init__(self, backend: str = "auto", **kwargs) -> None:
        if backend == "auto":
            backend = "torch" if HAS_TORCH else "linear"

        self.backend = backend
        self.encoder = FeatureEncoder()

        if backend == "torch" and HAS_TORCH:
            input_dim = kwargs.pop("input_dim", FEATURE_DIM)
            self._model = PolicyNetwork(input_dim=input_dim, **kwargs)
            self._trainer: PolicyTrainer | None = PolicyTrainer(self._model)
        else:
            self._model = LinearPolicyScorer()
            self._trainer = None

    def fit(
        self,
        rows: list[dict[str, Any]],
        epochs: int = 100,
        batch_size: int = 64,
        verbose: bool = True,
    ) -> list[dict[str, float]]:
        """从 rl_state_t 行训练模型

        Args:
            rows: 每行包含 state features + reward + roas_d7
        """
        # 1. 特征编码
        self.encoder.fit(rows)
        X = self.encoder.encode_batch(rows)

        # 2. 构建 target
        y_roas = np.array([float(r.get("roas_d7", 0) or 0) for r in rows], dtype=np.float32)
        y_reward = np.array([float(r.get("reward", 0) or 0) for r in rows], dtype=np.float32)

        # Top-performing flag: top 30% by reward
        threshold = np.percentile(y_reward, 70) if len(y_reward) > 3 else y_reward.max()
        y_top_flag = (y_reward >= threshold).astype(np.float32)

        if self.backend == "torch" and HAS_TORCH and self._trainer:
            history = self._trainer.train(
                X, y_roas, y_top_flag,
                epochs=epochs, batch_size=batch_size, verbose=verbose,
            )
        else:
            # Linear scorer: reward-weighted training
            temperature = 0.1
            weights = np.exp((y_reward - y_reward.max()) / temperature)
            weights = weights / weights.sum()
            self._model.fit(X, y_reward, sample_weight=weights)
            history = [{"total": 0.0}]

        return history

    def predict(self, rows: list[dict[str, Any]]) -> np.ndarray:
        """预测 softmax 概率分布"""
        X = self.encoder.encode_batch(rows)
        if self.backend == "torch" and HAS_TORCH:
            return self._model.predict(X)
        else:
            return self._model.predict(X)

    def predict_for_creatives(
        self,
        rows: list[dict[str, Any]],
        creative_ids: list[str],
    ) -> list[PolicyPrediction]:
        """为每个 creative 生成完整预测"""
        probs = self.predict(rows)

        if self.backend == "torch" and HAS_TORCH:
            X = self.encoder.encode_batch(rows)
            details = self._model.predict_with_details(X)
            ctr_preds = details["ctr_pred"]
            roas_preds = details["roas_pred"]
            risk_preds = details["risk_pred"]
        else:
            ctr_preds = np.zeros(len(probs))
            roas_preds = np.zeros(len(probs))
            risk_preds = np.zeros(len(probs))

        return [
            PolicyPrediction(
                creative_id=cid,
                serve_prob=round(float(probs[i]), 4),
                budget_weight=round(float(probs[i]), 4),
                exploration_score=round(float(risk_preds[i]), 4),
                ctr_pred=round(float(ctr_preds[i]), 4),
                roas_pred=round(float(roas_preds[i]), 4),
                risk_pred=round(float(risk_preds[i]), 4),
            )
            for i, cid in enumerate(creative_ids)
        ]

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.encoder.save(p.with_suffix(".encoder.json"))
        if self.backend == "torch" and HAS_TORCH:
            self._model.save_model(p.with_suffix(".pt"))
        else:
            self._model.save(p.with_suffix(".pkl"))

    @classmethod
    def load(cls, path: str | Path) -> "PolicyModel":
        p = Path(path)
        model = cls(backend="torch" if HAS_TORCH else "linear")
        model.encoder.load(p.with_suffix(".encoder.json"))

        if HAS_TORCH:
            pt_path = p.with_suffix(".pt")
            if pt_path.exists():
                model._model = PolicyNetwork.load_model(pt_path)
                model._trainer = PolicyTrainer(model._model)
                model.backend = "torch"
                return model

        pkl_path = p.with_suffix(".pkl")
        if pkl_path.exists():
            model._model = LinearPolicyScorer().load(pkl_path)
            model.backend = "linear"
            return model

        raise FileNotFoundError(f"No model found at {path}")