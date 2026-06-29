"""IAP Observation Layer — CreativeObservation + QualityScoreBuilder

FinalBandit 不变。Observation 层独立, 只输出 quality_score 给 Bandit。

数据流:
    Facebook/Adjust → CreativeObservation → QualityScoreBuilder → quality_score → FinalBandit

核心约束:
- FinalBandit 只接收 quality_score (0~1)
- 所有原始指标 (CTR/ROAS/Purchase/Revenue) 进入 Observation, 不进入 Bandit
- 4 阶段 IAP 评分: 随时间推移, 从 CTR 权重逐步转向 ROAS/Revenue 权重
- 支持 delayed reward 回流 + replay 幂等
- 支持最低样本过滤 (anti-noise)
- 每个 quality_score 可解释来源
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ============================================================================
# CreativeObservation — 所有原始指标 (不进 Bandit)
# ============================================================================

@dataclass
class CreativeObservation:
    """单个 creative 的完整 observation 快照

    Facebook 指标 + Adjust 收入指标。所有字段进入 Observation, 禁止直接进入 Bandit。
    """

    creative_id: str
    campaign_id: str = ""
    adset_id: str = ""
    date: str = ""  # YYYY-MM-DD

    # Facebook 投放指标
    impression: int = 0
    click: int = 0
    ctr: float = 0.0  # %
    install: int = 0
    cvr: float = 0.0  # install/click
    cpi: float = 0.0
    ipm: float = 0.0  # install per mille
    spend: float = 0.0

    # Adjust 内购指标 (分天)
    purchase_d0: int = 0
    purchase_d1: int = 0
    purchase_d3: int = 0
    purchase_d7: int = 0

    revenue_d0: float = 0.0
    revenue_d1: float = 0.0
    revenue_d3: float = 0.0
    revenue_d7: float = 0.0

    roas_d0: float = 0.0
    roas_d1: float = 0.0
    roas_d3: float = 0.0
    roas_d7: float = 0.0

    pay_rate_d0: float = 0.0  # purchase/install
    pay_rate_d1: float = 0.0

    # 元数据
    collected_at: str = ""  # ISO timestamp
    data_source: str = "facebook"  # facebook | adjust | merged

    def __post_init__(self):
        if not self.collected_at:
            self.collected_at = datetime.now(timezone.utc).isoformat()

    def hours_since_install(self) -> float:
        """估算安装后经过的小时数 (基于 collected_at)"""
        try:
            ct = datetime.fromisoformat(self.collected_at.replace("Z", "+00:00"))
            install_date = datetime.strptime(self.date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            return (ct - install_date).total_seconds() / 3600
        except Exception:
            return 0

    @property
    def total_purchase(self) -> int:
        return self.purchase_d0 + self.purchase_d1 + self.purchase_d3 + self.purchase_d7

    @property
    def total_revenue(self) -> float:
        return self.revenue_d0 + self.revenue_d1 + self.revenue_d3 + self.revenue_d7

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "date": self.date,
            "impression": self.impression,
            "click": self.click,
            "ctr": self.ctr,
            "install": self.install,
            "cvr": self.cvr,
            "cpi": self.cpi,
            "ipm": self.ipm,
            "spend": self.spend,
            "purchase_d0": self.purchase_d0,
            "purchase_d1": self.purchase_d1,
            "purchase_d3": self.purchase_d3,
            "purchase_d7": self.purchase_d7,
            "revenue_d0": self.revenue_d0,
            "revenue_d1": self.revenue_d1,
            "revenue_d3": self.revenue_d3,
            "revenue_d7": self.revenue_d7,
            "roas_d0": self.roas_d0,
            "roas_d1": self.roas_d1,
            "roas_d3": self.roas_d3,
            "roas_d7": self.roas_d7,
            "pay_rate_d0": self.pay_rate_d0,
            "pay_rate_d1": self.pay_rate_d1,
            "collected_at": self.collected_at,
            "data_source": self.data_source,
        }

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "CreativeObservation":
        """从 DuckDB creative_performance 行构建"""
        return cls(
            creative_id=str(row.get("creative_id", "")),
            campaign_id=str(row.get("campaign_id", "")),
            adset_id=str(row.get("adset_id", "")),
            date=str(row.get("date", "")),
            impression=int(row.get("impression", 0) or 0),
            click=int(row.get("click", 0) or 0),
            ctr=float(row.get("ctr", 0) or 0),
            install=int(row.get("install", 0) or 0),
            cvr=float(row.get("install", 0) or 0) / max(float(row.get("click", 1) or 1), 1),
            cpi=float(row.get("cpi", 0) or 0),
            ipm=float(row.get("ipm", 0) or 0),
            spend=float(row.get("spend", 0) or 0),
            roas_d7=float(row.get("roas_d7", 0) or 0),
        )


# ============================================================================
# QualityScoreBuilder — 4 阶段 IAP 评分
# ============================================================================

@dataclass
class QualityScore:
    """quality_score + 可解释性"""

    score: float  # 0~1
    stage: int  # 1~4
    maturity: float  # 0~1
    sufficient_data: bool  # 是否满足最低样本门槛

    # 各维度得分和权重 (explainability)
    components: dict[str, dict] = field(default_factory=dict)
    # {"ctr": {"value": 0.02, "weight": 0.10, "score": 0.002}, ...}

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "stage": self.stage,
            "maturity": round(self.maturity, 4),
            "sufficient_data": self.sufficient_data,
            "components": {
                k: {kk: round(vv, 4) if isinstance(vv, float) else vv
                    for kk, vv in v.items()}
                for k, v in self.components.items()
            },
        }

    def explain(self) -> str:
        """人类可读的解释"""
        if not self.sufficient_data:
            return f"Insufficient Data (maturity={self.maturity:.2f})"
        parts = [f"Stage {self.stage} | Quality={self.score:.3f}"]
        for name, comp in self.components.items():
            parts.append(f"{name}: {comp['score']:.3f} (w={comp['weight']:.0%})")
        return " | ".join(parts)


class QualityScoreBuilder:
    """IAP 4 阶段评分构建器

    输入: CreativeObservation
    输出: QualityScore (0~1)
    """

    # 最低样本门槛
    MIN_IMPRESSIONS = 100
    MIN_CLICKS = 5
    MIN_INSTALLS = 1

    # Stage 分界 (小时)
    STAGE1_HOURS = 24
    STAGE2_HOURS = 72
    STAGE3_HOURS = 168  # 7 days

    def __init__(self) -> None:
        pass

    # ========================================================================
    # 主入口
    # ========================================================================

    def build(self, obs: CreativeObservation) -> QualityScore:
        """从 CreativeObservation 构建 QualityScore"""
        # Anti-noise: 最低样本过滤
        if not self._has_sufficient_data(obs):
            return QualityScore(
                score=0.0, stage=0, maturity=0.0, sufficient_data=False,
            )

        # 确定 stage + maturity
        hours = obs.hours_since_install()
        stage = self._determine_stage(hours)
        maturity = self._compute_maturity(hours)

        # 按 stage 计算
        if stage == 1:
            score, components = self._score_stage1(obs)
        elif stage == 2:
            score, components = self._score_stage2(obs)
        elif stage == 3:
            score, components = self._score_stage3(obs)
        else:
            score, components = self._score_stage4(obs)

        return QualityScore(
            score=max(0.0, min(1.0, score)),
            stage=stage,
            maturity=maturity,
            sufficient_data=True,
            components=components,
        )

    # ========================================================================
    # Anti-noise
    # ========================================================================

    def _has_sufficient_data(self, obs: CreativeObservation) -> bool:
        return (
            obs.impression >= self.MIN_IMPRESSIONS
            and obs.click >= self.MIN_CLICKS
            and obs.install >= self.MIN_INSTALLS
        )

    # ========================================================================
    # Stage + Maturity
    # ========================================================================

    def _determine_stage(self, hours: float) -> int:
        if hours < self.STAGE1_HOURS:
            return 1
        elif hours < self.STAGE2_HOURS:
            return 2
        elif hours < self.STAGE3_HOURS:
            return 3
        else:
            return 4

    def _compute_maturity(self, hours: float) -> float:
        """maturity 0~1: 安装后时间 / 7天"""
        return max(0.0, min(1.0, hours / self.STAGE3_HOURS))

    # ========================================================================
    # 4 阶段评分
    # ========================================================================

    @staticmethod
    def _sigmoid(x: float) -> float:
        """稳定 sigmoid: x/(1+|x|), 输出 [-1,1] → 映射到 [0,1]"""
        return (x / (1.0 + abs(x)) + 1.0) / 2.0

    @staticmethod
    def _norm_score(value: float, baseline: float) -> float:
        """标准化 + sigmoid → [0,1]"""
        if baseline <= 0:
            return 0.5
        return QualityScoreBuilder._sigmoid((value - baseline) / baseline)

    def _score_stage1(self, obs: CreativeObservation) -> tuple[float, dict]:
        """Stage 1 (<24h): CTR 20% + CVR 30% + IPM 30% + Install 20%

        禁止: ROAS D7
        """
        # baseline (经验值, 后续可用历史数据替换)
        b_ctr, b_cvr, b_ipm = 1.5, 0.05, 5.0

        ctr_s = self._norm_score(obs.ctr, b_ctr)
        cvr_s = self._norm_score(obs.cvr * 100, b_cvr * 100) if obs.cvr > 0 else 0.5
        ipm_s = self._norm_score(obs.ipm, b_ipm) if obs.ipm > 0 else 0.3
        inst_s = min(1.0, obs.install / 50.0)  # 安装量线性缩放, 50 封顶

        weights = {"ctr": 0.20, "cvr": 0.30, "ipm": 0.30, "install": 0.20}
        components = {
            "ctr": {"value": round(obs.ctr, 2), "weight": 0.20, "score": round(ctr_s, 4)},
            "cvr": {"value": round(obs.cvr, 4), "weight": 0.30, "score": round(cvr_s, 4)},
            "ipm": {"value": round(obs.ipm, 2), "weight": 0.30, "score": round(ipm_s, 4)},
            "install": {"value": obs.install, "weight": 0.20, "score": round(inst_s, 4)},
        }

        score = ctr_s * 0.20 + cvr_s * 0.30 + ipm_s * 0.30 + inst_s * 0.20
        return score, components

    def _score_stage2(self, obs: CreativeObservation) -> tuple[float, dict]:
        """Stage 2 (24h~72h): CTR 10% + CVR 20% + PurchaseRate 30% + RevenueD0 20% + ROAS D1 20%"""
        b_ctr, b_cvr, b_payrate, b_roas = 1.5, 0.05, 0.03, 0.15

        ctr_s = self._norm_score(obs.ctr, b_ctr)
        cvr_s = self._norm_score(obs.cvr * 100, b_cvr * 100) if obs.cvr > 0 else 0.5

        pay_rate = obs.pay_rate_d0 if obs.pay_rate_d0 > 0 else (
            obs.purchase_d0 / max(obs.install, 1)
        )
        pay_s = self._norm_score(pay_rate, b_payrate)

        rev_d0 = obs.revenue_d0 / max(obs.spend, 1) if obs.spend > 0 else 0
        rev_s = self._norm_score(rev_d0, b_roas)

        roas_s = self._norm_score(obs.roas_d1 if obs.roas_d1 > 0 else rev_d0, b_roas)

        components = {
            "ctr": {"value": round(obs.ctr, 2), "weight": 0.10, "score": round(ctr_s, 4)},
            "cvr": {"value": round(obs.cvr, 4), "weight": 0.20, "score": round(cvr_s, 4)},
            "purchase_rate": {"value": round(pay_rate, 4), "weight": 0.30, "score": round(pay_s, 4)},
            "revenue_d0": {"value": round(rev_d0, 4), "weight": 0.20, "score": round(rev_s, 4)},
            "roas_d1": {"value": round(obs.roas_d1, 4), "weight": 0.20, "score": round(roas_s, 4)},
        }

        score = ctr_s * 0.10 + cvr_s * 0.20 + pay_s * 0.30 + rev_s * 0.20 + roas_s * 0.20
        return score, components

    def _score_stage3(self, obs: CreativeObservation) -> tuple[float, dict]:
        """Stage 3 (3~7天): CTR 5% + CVR 15% + PurchaseRate 25% + RevenueD3 25% + ROAS D3 30%"""
        b_ctr, b_cvr, b_payrate, b_roas = 1.5, 0.05, 0.03, 0.15

        ctr_s = self._norm_score(obs.ctr, b_ctr)
        cvr_s = self._norm_score(obs.cvr * 100, b_cvr * 100) if obs.cvr > 0 else 0.5

        pay_rate = obs.pay_rate_d1 if obs.pay_rate_d1 > 0 else obs.pay_rate_d0
        if pay_rate <= 0:
            pay_rate = (obs.purchase_d1 + obs.purchase_d3) / max(obs.install, 1)
        pay_s = self._norm_score(pay_rate, b_payrate)

        rev_d3 = obs.revenue_d3 / max(obs.spend, 1) if obs.spend > 0 else 0
        rev_s = self._norm_score(rev_d3, b_roas)

        roas = obs.roas_d3 if obs.roas_d3 > 0 else (obs.roas_d1 if obs.roas_d1 > 0 else rev_d3)
        roas_s = self._norm_score(roas, b_roas)

        components = {
            "ctr": {"value": round(obs.ctr, 2), "weight": 0.05, "score": round(ctr_s, 4)},
            "cvr": {"value": round(obs.cvr, 4), "weight": 0.15, "score": round(cvr_s, 4)},
            "purchase_rate": {"value": round(pay_rate, 4), "weight": 0.25, "score": round(pay_s, 4)},
            "revenue_d3": {"value": round(rev_d3, 4), "weight": 0.25, "score": round(rev_s, 4)},
            "roas_d3": {"value": round(roas, 4), "weight": 0.30, "score": round(roas_s, 4)},
        }

        score = ctr_s * 0.05 + cvr_s * 0.15 + pay_s * 0.25 + rev_s * 0.25 + roas_s * 0.30
        return score, components

    def _score_stage4(self, obs: CreativeObservation) -> tuple[float, dict]:
        """Stage 4 (7天+): ROAS D7 40% + Revenue D7 30% + PayRate 20% + CVR 5% + CTR 5%

        CTR 只保留极低权重。
        """
        b_roas, b_payrate, b_cvr = 0.15, 0.03, 0.05

        roas = obs.roas_d7 if obs.roas_d7 > 0 else (
            obs.roas_d3 if obs.roas_d3 > 0 else obs.revenue_d7 / max(obs.spend, 1)
        )
        roas_s = self._norm_score(roas, b_roas)

        rev_d7 = obs.revenue_d7 / max(obs.spend, 1) if obs.spend > 0 else 0
        rev_s = self._norm_score(rev_d7, b_roas)

        pay_rate = obs.pay_rate_d1 if obs.pay_rate_d1 > 0 else (
            obs.total_purchase / max(obs.install, 1)
        )
        pay_s = self._norm_score(pay_rate, b_payrate)

        cvr_s = self._norm_score(obs.cvr * 100, b_cvr * 100) if obs.cvr > 0 else 0.5
        ctr_s = self._norm_score(obs.ctr, 1.5)

        components = {
            "roas_d7": {"value": round(roas, 4), "weight": 0.40, "score": round(roas_s, 4)},
            "revenue_d7": {"value": round(rev_d7, 4), "weight": 0.30, "score": round(rev_s, 4)},
            "pay_rate": {"value": round(pay_rate, 4), "weight": 0.20, "score": round(pay_s, 4)},
            "cvr": {"value": round(obs.cvr, 4), "weight": 0.05, "score": round(cvr_s, 4)},
            "ctr": {"value": round(obs.ctr, 2), "weight": 0.05, "score": round(ctr_s, 4)},
        }

        score = roas_s * 0.40 + rev_s * 0.30 + pay_s * 0.20 + cvr_s * 0.05 + ctr_s * 0.05
        return score, components


# ============================================================================
# ObservationStore — 管理 observation 生命周期, 支持 delayed reward + 幂等
# ============================================================================

class ObservationStore:
    """Observation 存储 + 去重 + delayed reward 回流

    保证:
    - 同一 (creative_id, date) 只生成一次 QualityScore
    - delayed reward 回流时更新 observation → 重新计算 quality_score
    - 但 FinalBandit.update() 只针对 delta (新增部分)
    """

    def __init__(self) -> None:
        # key = creative_id:date → CreativeObservation
        self._observations: dict[str, CreativeObservation] = {}
        # key = creative_id:date → quality_score (已发给 Bandit 的)
        self._submitted_scores: dict[str, float] = {}

    def ingest(self, obs: CreativeObservation) -> bool:
        """摄入 observation。返回 True 表示是新数据/有更新。"""
        key = f"{obs.creative_id}:{obs.date}"
        existing = self._observations.get(key)

        if existing is None:
            self._observations[key] = obs
            return True

        # 已存在, 检查是否有新的 revenue 回流 (delayed reward)
        if self._has_new_revenue(existing, obs):
            # 合并: 更新 revenue/purchase 字段
            existing.revenue_d1 = max(existing.revenue_d1, obs.revenue_d1)
            existing.revenue_d3 = max(existing.revenue_d3, obs.revenue_d3)
            existing.revenue_d7 = max(existing.revenue_d7, obs.revenue_d7)
            existing.purchase_d1 = max(existing.purchase_d1, obs.purchase_d1)
            existing.purchase_d3 = max(existing.purchase_d3, obs.purchase_d3)
            existing.purchase_d7 = max(existing.purchase_d7, obs.purchase_d7)
            existing.roas_d1 = max(existing.roas_d1, obs.roas_d1)
            existing.roas_d3 = max(existing.roas_d3, obs.roas_d3)
            existing.roas_d7 = max(existing.roas_d7, obs.roas_d7)
            existing.collected_at = obs.collected_at
            self._observations[key] = existing
            return True

        return False

    @staticmethod
    def _has_new_revenue(old: CreativeObservation, new: CreativeObservation) -> bool:
        return (
            new.revenue_d1 > old.revenue_d1
            or new.revenue_d3 > old.revenue_d3
            or new.revenue_d7 > old.revenue_d7
            or new.purchase_d1 > old.purchase_d1
            or new.purchase_d3 > old.purchase_d3
            or new.purchase_d7 > old.purchase_d7
        )

    def get_observation(self, creative_id: str, date: str) -> CreativeObservation | None:
        return self._observations.get(f"{creative_id}:{date}")

    def mark_submitted(self, creative_id: str, date: str, score: float) -> None:
        """标记该 observation 的 quality_score 已发给 Bandit"""
        self._submitted_scores[f"{creative_id}:{date}"] = score

    def get_submitted_score(self, creative_id: str, date: str) -> float | None:
        return self._submitted_scores.get(f"{creative_id}:{date}")

    def get_all_observations(self) -> list[CreativeObservation]:
        return list(self._observations.values())

    def stats(self) -> dict[str, Any]:
        return {
            "total_observations": len(self._observations),
            "total_submitted": len(self._submitted_scores),
        }
