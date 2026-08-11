"""E17.2 Growth Opportunity Engine — 模型层。

把「公司现在发生了什么」(E17.1) 转成「哪里有机会、哪个最该做」(E17.2)。

约定（与 E17.1 / E16 一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- OpportunityType 为 str Enum，便于 JSON 序列化与 memory 键
- GameSignals 是规则引擎的「归一信号」契约（由 analyzer 从快照/历史派生）
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OpportunityType(str, Enum):
    REVENUE_RECOVERY = "revenue_recovery"
    UA_SCALE = "ua_scale"
    UA_STOP_LOSS = "ua_stop_loss"
    CREATIVE_REFRESH = "creative_refresh"
    ASO_OPTIMIZATION = "aso_optimization"
    MONETIZATION = "monetization"
    RETENTION = "retention"
    RELEASE_HEALTH = "release_health"


@dataclass
class GrowthOpportunity:
    game_id: str
    type: OpportunityType
    title: str
    problem: str
    evidence: List[str] = field(default_factory=list)
    expected_impact: float = 0.0
    confidence: float = 0.0
    urgency: float = 0.0
    risk: float = 0.0
    suggested_actions: List[str] = field(default_factory=list)
    priority: float = 0.0
    segment: str = "global"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrowthOpportunity":
        return cls(
            game_id=d["game_id"],
            type=OpportunityType(d["type"]),
            title=d["title"],
            problem=d["problem"],
            evidence=list(d.get("evidence", [])),
            expected_impact=float(d.get("expected_impact", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            urgency=float(d.get("urgency", 0.0)),
            risk=float(d.get("risk", 0.0)),
            suggested_actions=list(d.get("suggested_actions", [])),
            priority=float(d.get("priority", 0.0)),
            segment=d.get("segment", "global"),
            created_at=d.get("created_at", ""),
        )


@dataclass
class PortfolioOpportunity:
    game_id: str
    top_problem: str
    priority: float
    type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioOpportunity":
        return cls(
            game_id=d["game_id"],
            top_problem=d["top_problem"],
            priority=float(d["priority"]),
            type=d.get("type", ""),
        )


@dataclass
class OpportunityReport:
    total_opportunities: int
    top_priority: List[GrowthOpportunity] = field(default_factory=list)
    portfolio_ranking: List[PortfolioOpportunity] = field(default_factory=list)
    risk_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_opportunities": self.total_opportunities,
            "top_priority": [o.to_dict() for o in self.top_priority],
            "portfolio_ranking": [p.to_dict() for p in self.portfolio_ranking],
            "risk_summary": self.risk_summary,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OpportunityReport":
        return cls(
            total_opportunities=int(d["total_opportunities"]),
            top_priority=[GrowthOpportunity.from_dict(x) for x in d.get("top_priority", [])],
            portfolio_ranking=[PortfolioOpportunity.from_dict(x) for x in d.get("portfolio_ranking", [])],
            risk_summary=dict(d.get("risk_summary", {})),
        )

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append("# 增长机会报告（Growth Opportunity Engine）")
        lines.append("")
        lines.append(f"- 机会总数：**{self.total_opportunities}**")
        rs = self.risk_summary
        lines.append(f"- 高/中/低风险：{rs.get('high',0)} / {rs.get('medium',0)} / {rs.get('low',0)}")
        lines.append(f"- 组合预期收入影响（合计）：**{rs.get('total_expected_impact',0.0):+.1%}**")
        lines.append("")
        if self.top_priority:
            lines.append("## 优先级最高的机会")
            lines.append("")
            lines.append("| 游戏 | 类型 | 问题 | 优先级 | 预期影响 | 置信 | 风险 |")
            lines.append("|---|---|---|---|---|---|---|")
            for o in self.top_priority[:10]:
                lines.append(
                    f"| {o.game_id} | {o.type.value} | {o.problem} | "
                    f"{o.priority:.3f} | {o.expected_impact:+.1%} | {o.confidence:.0%} | {o.risk:.0%} |"
                )
            lines.append("")
        if self.portfolio_ranking:
            lines.append("## 组合机会排序（每游戏 Top 机会）")
            lines.append("")
            lines.append("| 游戏 | 首要问题 | 优先级 |")
            lines.append("|---|---|---|")
            for p in self.portfolio_ranking:
                lines.append(f"| {p.game_id} | {p.top_problem} | {p.priority:.3f} |")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 规则引擎的归一信号（analyzer 从 E17.1 快照 + 历史派生）
# --------------------------------------------------------------------------- #
@dataclass
class GameSignals:
    game_id: str = ""

    # revenue
    revenue: float = 0.0
    revenue_growth: float = 0.0

    # acquisition / ua
    spend: float = 0.0
    spend_growth: float = 0.0
    roas: float = 0.0
    roas_growth: float = 0.0
    installs: float = 0.0
    cpi: float = 0.0
    budget_level: float = 0.5  # 0..1，<0.33 视为「小预算」

    # creative
    ctr: float = 0.0
    ctr_growth: float = 0.0
    frequency: float = 1.0
    frequency_growth: float = 0.0
    fatigue_score: float = 0.0
    creative_score: float = 0.0
    creative_score_growth: float = 0.0

    # aso
    ranking: float = 0.0
    ranking_growth: float = 0.0
    rating: float = 0.0
    store_cvr: float = 0.0
    store_cvr_growth: float = 0.0

    # product
    dau: float = 0.0
    retention: float = 0.0
    conversion: float = 0.0

    # meta
    coverage: int = 0  # 覆盖的 domain 数（置信度基线依据）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GameSignals":
        return cls(**{k: d.get(k, 0.0) if k != "game_id" else d.get("game_id", "") for k in cls.__dataclass_fields__})
