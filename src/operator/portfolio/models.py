"""P3.4.1 — Portfolio Model Layer（纯快照模型层）。

本模块**只定义数据结构与序列化**，不计算任何业务指标：

- ❌ 不重算 ROAS / spend / revenue / retention（源自 E17.1 Reality Snapshot）
- ❌ 不评分、不排序、不推荐、不产生 Action
- ❌ 不触碰 E17.3 Decision Engine，不调任何 Provider

对外契约（P3.4.1 只有这三个核心对象 + 四个解耦输入源）：

- ``GamePortfolioSnapshot``  单游戏组合视图（全部字段为 snapshot）
- ``PortfolioSnapshot``      组合级快照（P3.4.2 Ranking 输入）
- ``PortfolioSignal``        统一信号单元（解耦 assembler 输出与下游）
- ``StrategySource`` / ``ExecutionSource`` / ``RecoverySource`` / ``LifecycleSource``

评分 / 排序 / 分配 / 推荐类模型（``PortfolioScore`` / ``PortfolioVerdict`` /
``AllocationCandidate`` / ``PortfolioRecommendation``）**不属于本层**，
已迁至 :mod:`src.operator.portfolio.ranking_models`（P3.4.2+ 归属）。
本文件由 ``tests/p3_4_1/test_contract_boundary.py`` 静态锁定，越界即测试失败。

所有数值字段缺失时一律为 ``None``（语义 = UNKNOWN），下游据此判断「数据不足」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# 输入源（由 assembler 的适配器从既有上游填充；P3.4.1 只消费，不生产）
# --------------------------------------------------------------------------- #
@dataclass
class StrategySource:
    """单游戏策略效能快照（来自 E17.7 GrowthMemoryGraph）。

    - strategy_score / strategy_success_rate 均源自 ``graph.success_rate_by(game_id=)``
      （该游戏 RESULT 节点成功率；无样本为 0.0）。两者同源，P3.4.2 可分别加权。
    - active_strategy_count：该游戏在图谱中出现的不同 strategy_type 数量。
    """

    strategy_score: Optional[float] = None
    strategy_success_rate: Optional[float] = None
    active_strategy_count: int = 0


@dataclass
class ExecutionSource:
    """单游戏执行健康快照（来自 P2.5 ExecutionMonitor）。

    execution_health 取 ``compute_health_score().score``；
    failure_rate 取 ``1 - success_rate``（由健康分派生，非独立新指标）。
    """

    execution_health: Optional[float] = None
    failure_rate: Optional[float] = None


@dataclass
class RecoverySource:
    """单游戏恢复健康快照（来自 P2.6 Recovery）。

    注：P2.6 ``RecoveryExperienceRecord`` 以 failure 维度组织、不含 game_id，
    故 per-game recovery_rate 由更上层（P3.4.2 接 RecoveryIncident.target）预计算后注入；
    本层只持有结果值，不重算。
    """

    recovery_rate: Optional[float] = None


@dataclass
class LifecycleSource:
    """单游戏生命周期快照（来自 E15.1.2 PortfolioManager.stage_of）。

    - lifecycle_stage：``stage_of(game_id)`` 返回的字符串值
      （idea / prototype / soft_launch / ua_test / scale / kill）。
    - data_freshness：0-1，数据新鲜度；无来源时为 None。
    """

    lifecycle_stage: Optional[str] = None
    data_freshness: Optional[float] = None


# --------------------------------------------------------------------------- #
# 核心模型
# --------------------------------------------------------------------------- #
@dataclass
class GamePortfolioSnapshot:
    """单个游戏在 Portfolio 视角下的只读组合快照。

    全部字段为 **snapshot**（消费既有数据），**禁止**在本类内计算新指标。
    缺失字段为 ``None``（UNKNOWN）。
    """

    game_id: str

    # —— Reality（E17.1 / P1.7）——
    revenue: Optional[float] = None          # snapshot.revenue.daily_revenue
    spend: Optional[float] = None            # snapshot.acquisition.spend
    roas: Optional[float] = None             # snapshot.acquisition.roas（原样消费，不重算）
    confidence: Optional[float] = None       # snapshot.confidence（P1.7 置信，既有字段）
    coverage: Optional[float] = None         # domain_coverage()/5.0（0-1 覆盖比例）

    # —— Strategy（E17.7）——
    strategy_score: Optional[float] = None
    strategy_success_rate: Optional[float] = None
    active_strategy_count: int = 0

    # —— Execution（P2.5）——
    execution_health: Optional[float] = None
    failure_rate: Optional[float] = None

    # —— Recovery（P2.6）——
    recovery_rate: Optional[float] = None

    # —— Lifecycle（E15.1.2）——
    lifecycle_stage: Optional[str] = None
    data_freshness: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- 派生判断（只读，不计算新指标）--
    @property
    def has_reality(self) -> bool:
        return self.revenue is not None or self.spend is not None or self.roas is not None

    @property
    def has_strategy(self) -> bool:
        return self.strategy_success_rate is not None

    @property
    def has_execution(self) -> bool:
        return self.execution_health is not None

    @property
    def has_recovery(self) -> bool:
        return self.recovery_rate is not None

    @property
    def has_lifecycle(self) -> bool:
        return self.lifecycle_stage is not None

    @property
    def is_known(self) -> bool:
        """是否有任何有效经济信号（revenue/spend/roas/confidence 至少其一已知）。"""
        return self.has_reality or self.confidence is not None

    def to_signals(self, timestamp: Optional[str] = None) -> List["PortfolioSignal"]:
        """把既有字段统一打包为 PortfolioSignal 列表（仅重包装，不产生新值）。

        下游（P3.4.2/3/4）可据此解耦消费，不必感知 GamePortfolioSnapshot 结构。
        """
        out: List[PortfolioSignal] = []
        mapping = [
            ("revenue", self.revenue),
            ("spend", self.spend),
            ("roas", self.roas),
            ("confidence", self.confidence),
            ("coverage", self.coverage),
            ("strategy_score", self.strategy_score),
            ("strategy_success_rate", self.strategy_success_rate),
            ("execution_health", self.execution_health),
            ("failure_rate", self.failure_rate),
            ("recovery_rate", self.recovery_rate),
            ("data_freshness", self.data_freshness),
        ]
        for source, value in mapping:
            if value is None:
                continue
            out.append(
                PortfolioSignal(
                    source=source,
                    value=float(value),
                    confidence=1.0,
                    timestamp=timestamp,
                )
            )
        return out

    # -- 序列化 --
    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "revenue": _r(self.revenue),
            "spend": _r(self.spend),
            "roas": _r(self.roas),
            "confidence": _r(self.confidence),
            "coverage": _r(self.coverage),
            "strategy_score": _r(self.strategy_score),
            "strategy_success_rate": _r(self.strategy_success_rate),
            "active_strategy_count": self.active_strategy_count,
            "execution_health": _r(self.execution_health),
            "failure_rate": _r(self.failure_rate),
            "recovery_rate": _r(self.recovery_rate),
            "lifecycle_stage": self.lifecycle_stage,
            "data_freshness": _r(self.data_freshness),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GamePortfolioSnapshot":
        return cls(
            game_id=d["game_id"],
            revenue=d.get("revenue"),
            spend=d.get("spend"),
            roas=d.get("roas"),
            confidence=d.get("confidence"),
            coverage=d.get("coverage"),
            strategy_score=d.get("strategy_score"),
            strategy_success_rate=d.get("strategy_success_rate"),
            active_strategy_count=int(d.get("active_strategy_count", 0)),
            execution_health=d.get("execution_health"),
            failure_rate=d.get("failure_rate"),
            recovery_rate=d.get("recovery_rate"),
            lifecycle_stage=d.get("lifecycle_stage"),
            data_freshness=d.get("data_freshness"),
            metadata=dict(d.get("metadata", {})),
        )


@dataclass
class PortfolioSnapshot:
    """组合级快照（P3.4.2 Ranking 的输入）。

    total_revenue / total_spend 为既有值的**求和聚合**（非新指标）；
    coverage 为各游戏 coverage 的均值（0-1）。
    """

    generated_at: str
    games: List[GamePortfolioSnapshot] = field(default_factory=list)
    total_revenue: float = 0.0
    total_spend: float = 0.0
    coverage: float = 0.0

    @property
    def game_ids(self) -> List[str]:
        return [g.game_id for g in self.games]

    @property
    def count(self) -> int:
        return len(self.games)

    def get(self, game_id: str) -> Optional[GamePortfolioSnapshot]:
        for g in self.games:
            if g.game_id == game_id:
                return g
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "games": [g.to_dict() for g in self.games],
            "total_revenue": _r(self.total_revenue),
            "total_spend": _r(self.total_spend),
            "coverage": _r(self.coverage),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioSnapshot":
        return cls(
            generated_at=d.get("generated_at", ""),
            games=[GamePortfolioSnapshot.from_dict(g) for g in d.get("games", [])],
            total_revenue=float(d.get("total_revenue", 0.0)),
            total_spend=float(d.get("total_spend", 0.0)),
            coverage=float(d.get("coverage", 0.0)),
        )


@dataclass
class PortfolioSignal:
    """统一信号单元，用于解耦 assembler 输出与下游消费。

    仅承载「某来源 + 某数值 + 置信 + 时间戳」，不携带动作/决策语义。
    """

    source: str
    value: Optional[float] = None
    confidence: float = 1.0
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "value": _r(self.value),
            "confidence": _r(self.confidence),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioSignal":
        return cls(
            source=d["source"],
            value=d.get("value"),
            confidence=float(d.get("confidence", 1.0)),
            timestamp=d.get("timestamp"),
        )


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def _r(v: Optional[float]) -> Optional[float]:
    """序列化浮点：None 保持 None；否则 6 位精度（避免浮点噪声）。"""
    if v is None:
        return None
    return round(float(v), 6)
