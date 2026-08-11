"""P1.6.2 — 真实数据健康监控（Reality Health Monitor）。

每天基于 E17.1 产出的 CompanySnapshot + GameRegistry，逐游戏输出：
- 四源（Adjust / Meta / MAX / Registry）状态 OK / MISSING / N/A / ORPHAN
- Data Freshness（live = 有真实域；sim = 纯 SIM/空）
- Confidence / Real Confidence
- 绑定完整度缺失项

并聚合成 Reality Coverage Report（每日经营覆盖日报）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..models import GrowthRealitySnapshot
from ..registry import GameRegistry
from .gaps import DataGap, MissingDataDetector

# 源 → (绑定键, 中文名)；绑定键为 None 表示始终期望（如 registry 本地源）
SOURCE_META = {
    "max_live": ("max_account", "MAX 收入"),
    "adjust_live": ("adjust_app_token", "Adjust 获量"),
    "meta_live": ("meta_app_id", "Meta 广告"),
    "registry": (None, "注册表产品"),
}


@dataclass
class SourceHealth:
    source: str
    label: str
    expected: bool
    present: bool
    status: str  # OK | MISSING | N/A | ORPHAN


@dataclass
class GameRealityHealth:
    game_id: str
    source_health: Dict[str, SourceHealth]
    confidence: float
    real_confidence: float
    real_domains: List[str]
    freshness: str
    binding_missing: List[str]
    fully_covered: bool

    def to_dict(self) -> Dict:
        return {
            "game_id": self.game_id,
            "sources": {k: v.status for k, v in self.source_health.items()},
            "confidence": self.confidence,
            "real_confidence": self.real_confidence,
            "real_domains": self.real_domains,
            "freshness": self.freshness,
            "binding_missing": self.binding_missing,
            "fully_covered": self.fully_covered,
        }


@dataclass
class RealityCoverageReport:
    as_of: str
    per_game: Dict[str, GameRealityHealth]
    gaps: List[DataGap]
    total_games: int
    covered_games: int
    games_with_gaps: int
    coverage_ratio: float

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# 真实数据覆盖日报（{self.as_of}）")
        lines.append("")
        lines.append("> P1.6.2 Reality Coverage — 防 CEO 被骗的真实数据健康体检")
        lines.append("")
        lines.append("## 一、总览")
        lines.append("")
        lines.append(f"- 游戏总数：**{self.total_games}**")
        lines.append(f"- 完全覆盖（期望源均 OK）：**{self.covered_games}** "
                     f"（覆盖率 {self.coverage_ratio:.0%}）")
        lines.append(f"- 存在数据缺口（DATA_GAP）的游戏：**{self.games_with_gaps}**")
        sev = MissingDataDetector.summarize(self.gaps)
        lines.append(f"- DATA_GAP 总计：**{sev['total']}** "
                     f"（high {sev['high']} / medium {sev['medium']} / low {sev['low']}）")
        lines.append("")

        lines.append("## 二、逐游戏源健康")
        lines.append("")
        lines.append("| 游戏 | MAX | Adjust | Meta | Registry | 新鲜度 | 真实置信 | 绑定缺失 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for gid, h in sorted(self.per_game.items()):
            def s(k: str) -> str:
                sh = h.source_health.get(k)
                return sh.status if sh else "-"
            miss = ", ".join(h.binding_missing) if h.binding_missing else "—"
            lines.append(
                f"| {gid} | {s('max_live')} | {s('adjust_live')} | {s('meta_live')} | "
                f"{s('registry')} | {h.freshness} | {h.real_confidence:.2f} | {miss} |"
            )
        lines.append("")

        if self.gaps:
            lines.append("## 三、DATA_GAP 缺口清单")
            lines.append("")
            order = {"high": 0, "medium": 1, "low": 2}
            for g in sorted(self.gaps, key=lambda x: (order.get(x.severity, 9), x.game_id)):
                lines.append(f"- **[{g.severity.upper()}]** `{g.game_id}` — "
                             f"{g.gap_type}：{g.detail}（期望源：{g.expected_source}）")
            lines.append("")

        lines.append("---")
        lines.append("状态说明：OK=已绑定且有真实数据 / MISSING=已绑定但无真实数据 / "
                     "N/A=未绑定 / ORPHAN=有数据但未绑定。")
        return "\n".join(lines)


class RealityHealthMonitor:
    """逐游戏真实数据健康监控器。"""

    def __init__(self, registry: GameRegistry):
        self.registry = registry

    def check(
        self,
        company,
        include_gaps: bool = True,
    ) -> RealityCoverageReport:
        per_game: Dict[str, GameRealityHealth] = {}
        at_risk = list(getattr(company, "at_risk", []) or [])
        for gid, snap in company.per_game.items():
            per_game[gid] = self._check_game(gid, snap, at_risk)

        gaps: List[DataGap] = []
        if include_gaps:
            gaps = MissingDataDetector.detect(company.per_game, self.registry, at_risk)

        covered = sum(1 for h in per_game.values() if h.fully_covered)
        with_gaps = len({g.game_id for g in gaps})
        ratio = (covered / len(per_game)) if per_game else 0.0

        return RealityCoverageReport(
            as_of=getattr(company, "as_of", ""),
            per_game=per_game,
            gaps=gaps,
            total_games=len(per_game),
            covered_games=covered,
            games_with_gaps=with_gaps,
            coverage_ratio=round(ratio, 3),
        )

    def _check_game(
        self, gid: str, snap: GrowthRealitySnapshot, at_risk: List[str]
    ) -> GameRealityHealth:
        bindings = self.registry.source_bindings(gid)
        sources = set(snap.sources)
        sh: Dict[str, SourceHealth] = {}
        expected_ok = True
        has_expected = False
        for src, (bind_key, label) in SOURCE_META.items():
            expected = True if bind_key is None else (bind_key in bindings)
            present = src in sources
            if src == "registry":
                # 注册表本地源恒视为 present（除非游戏不在注册表）
                present = present or (gid in self.registry.all_game_ids())
            if expected:
                has_expected = True
                if present:
                    status = "OK"
                else:
                    status = "MISSING"
                    expected_ok = False
            else:
                status = "N/A" if not present else "ORPHAN"
            sh[src] = SourceHealth(src, label, expected, present, status)

        freshness = "live" if snap.real_domains else "sim"
        missing = self.registry.binding_completeness(gid)
        # fully_covered：存在期望源且全部 OK
        fully_covered = has_expected and expected_ok

        return GameRealityHealth(
            game_id=gid,
            source_health=sh,
            confidence=snap.confidence,
            real_confidence=snap.real_confidence,
            real_domains=list(snap.real_domains),
            freshness=freshness,
            binding_missing=missing,
            fully_covered=fully_covered,
        )
