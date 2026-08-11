"""P1.7 — 真实校验审计数据模型。

四类核心实体：
- RevenueReconciliation : 收入交叉对账结果（Adjust IAP + MAX Ad vs Total）
- FreshnessCheck        : 逐源数据新鲜度检查
- RealityScore          : 综合可信分（Coverage × Freshness × Consistency）
- AuditReport           : 每日审计报告（舰队级汇总）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Revenue Reconciliation
# --------------------------------------------------------------------------- #
@dataclass
class RevenueReconciliation:
    game_id: str
    adjust_iap: float = 0.0          # Adjust 口径 IAP 日收入
    max_ads: float = 0.0             # MAX 口径广告日收入
    expected_total: float = 0.0      # adjust_iap + max_ads
    reported_total: float = 0.0      # 来源：E17.1 snapshot daily_revenue
    variance: float = 0.0            # |expected - reported| / max(expected, 0.01)
    status: str = "INSUFFICIENT"     # GREEN / YELLOW / RED / INSUFFICIENT
    detail: str = ""                 # 人类可读的异常说明

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "adjust_iap": self.adjust_iap,
            "max_ads": self.max_ads,
            "expected_total": self.expected_total,
            "reported_total": self.reported_total,
            "variance": round(self.variance, 4),
            "status": self.status,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------- #
# Data Freshness
# --------------------------------------------------------------------------- #
@dataclass
class FreshnessCheck:
    source: str                     # "adjust" / "max" / "meta"
    last_sync: Optional[datetime] = None
    age_minutes: float = 0.0
    status: str = "UNKNOWN"         # GREEN / YELLOW / RED / UNKNOWN
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "age_minutes": round(self.age_minutes, 1),
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class GameFreshness:
    game_id: str
    sources: List[FreshnessCheck] = field(default_factory=list)
    overall: str = "UNKNOWN"        # 最差源的 status
    freshness_score: float = 1.0    # 0-1: GREEN=1.0, YELLOW=0.5, RED=0.0, UNKNOWN=0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "sources": [s.to_dict() for s in self.sources],
            "overall": self.overall,
            "freshness_score": self.freshness_score,
        }


# --------------------------------------------------------------------------- #
# Reality Confidence Score
# --------------------------------------------------------------------------- #
@dataclass
class RealityScore:
    game_id: str
    coverage: float = 0.0           # 来自 P1.6 real_confidence（0-1）
    freshness: float = 1.0          # 来自 freshness.freshness_score（0-1）
    consistency: float = 1.0        # 来自 reconciliation variance → 0-1
    composite: float = 0.0          # coverage × freshness × consistency
    decision_level: str = "BLOCKED" # BLOCKED / APPROVE / EXECUTE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "coverage": round(self.coverage, 3),
            "freshness": round(self.freshness, 3),
            "consistency": round(self.consistency, 3),
            "composite": round(self.composite, 3),
            "decision_level": self.decision_level,
        }

    @classmethod
    def compute(cls, game_id: str, coverage: float, freshness: float,
                consistency: float) -> "RealityScore":
        composite = coverage * freshness * consistency
        composite = max(0.0, min(1.0, composite))
        # decision_level 由 RealityGate 统一判定
        return cls(
            game_id=game_id,
            coverage=coverage, freshness=freshness,
            consistency=consistency, composite=round(composite, 3),
        )


# --------------------------------------------------------------------------- #
# Audit Report
# --------------------------------------------------------------------------- #
@dataclass
class GameAuditEntry:
    game_id: str
    recon: Optional[RevenueReconciliation] = None
    freshness: Optional[GameFreshness] = None
    score: Optional[RealityScore] = None

    @property
    def decision_ready(self) -> bool:
        if not self.score:
            return False
        return self.score.decision_level in ("APPROVE", "EXECUTE")


@dataclass
class AuditReport:
    as_of: str
    entries: List[GameAuditEntry] = field(default_factory=list)
    total_games: int = 0
    green: int = 0
    yellow: int = 0
    red: int = 0
    insufficient: int = 0
    decision_ready: int = 0
    revenue_integrity: float = 0.0   # % of games with GREEN reconciliation
    data_freshness: float = 0.0      # % of games with GREEN/YELLOW freshness

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of": self.as_of,
            "total_games": self.total_games,
            "green": self.green, "yellow": self.yellow, "red": self.red,
            "insufficient": self.insufficient,
            "decision_ready": self.decision_ready,
            "revenue_integrity": round(self.revenue_integrity, 3),
            "data_freshness": round(self.data_freshness, 3),
            "entries": [{
                "game_id": e.game_id,
                "recon": e.recon.to_dict() if e.recon else None,
                "freshness": e.freshness.to_dict() if e.freshness else None,
                "score": e.score.to_dict() if e.score else None,
            } for e in self.entries],
        }

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# Reality Audit Report ({self.as_of})")
        lines.append("")
        lines.append("> P1.7 Reality Validation — 数据可信审计日报")
        lines.append("")

        # 总览
        lines.append("## 一、总览")
        lines.append("")
        lines.append(f"- 游戏总数：**{self.total_games}**")
        lines.append(f"- 审计通过（GREEN）：**{self.green}**")
        lines.append(f"- 需要关注（YELLOW）：**{self.yellow}**")
        lines.append(f"- 禁止决策（RED）：**{self.red}**")
        lines.append(f"- 数据不足（INSUFFICIENT）：**{self.insufficient}**")
        lines.append(f"- 收入完整性：**{self.revenue_integrity:.0%}**")
        lines.append(f"- 数据新鲜度：**{self.data_freshness:.0%}**")
        lines.append(f"- 可自动决策游戏：**{self.decision_ready}**")
        lines.append("")

        # 逐游戏审计
        lines.append("## 二、逐游戏审计")
        lines.append("")
        lines.append("| 游戏 | 收入对账 | 对账状态 | 新鲜度 | 可信分 | 决策等级 |")
        lines.append("|---|---|---|---|---|---|")
        for e in sorted(self.entries, key=lambda x: (x.score and x.score.composite or 0), reverse=True):
            if e.recon:
                rec = f"¥{e.recon.expected_total:.0f} vs ¥{e.recon.reported_total:.0f} (Δ{e.recon.variance:.1%})"
                rstat = e.recon.status
            else:
                rec = "—"
                rstat = "N/A"
            fstat = e.freshness.overall if e.freshness else "N/A"
            comp = f"{e.score.composite:.2f}" if e.score else "—"
            dl = e.score.decision_level if e.score else "N/A"
            lines.append(f"| {e.game_id} | {rec} | {rstat} | {fstat} | {comp} | {dl} |")
        lines.append("")

        # RED 游戏详情
        reds = [e for e in self.entries if e.recon and e.recon.status == "RED"]
        if reds:
            lines.append("## 三、RED 告警详情")
            lines.append("")
            for e in reds:
                r = e.recon
                lines.append(f"- **{e.game_id}**：期望 ¥{r.expected_total:.0f}，"
                             f"实际报告 ¥{r.reported_total:.0f}，偏差 {r.variance:.1%}")
                if r.detail:
                    lines.append(f"  - {r.detail}")
            lines.append("")

        lines.append("---")
        lines.append("状态说明：GREEN = 可信可自动决策 / YELLOW = 需人工关注 "
                     "/ RED = 禁止自动决策（数据不可信） / INSUFFICIENT = 数据不足无法审计。")
        return "\n".join(lines)
