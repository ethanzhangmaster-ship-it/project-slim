"""P1.6.3 — 缺失数据检测器（Missing Data Detector）。

确定性规则引擎：把「注册表已绑定真实源，但快照里却没有对应真实数据」的情况
自动标记为 DATA_GAP，防止 CEO 基于残缺数据做出错误经营决策（"被骗"）。

设计原则：
- 纯确定性规则，不接 LLM，不臆造数据。
- 仅对「注册表声明已绑定」的源做缺口检查（未绑定的源属于配置缺失，由
  Registry.binding_completeness 负责，不在此重复告警）。
- severity：high = 影响收入/ROAS 真相；medium = 影响归因/地理决策；low = 配置盲区。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..models import GrowthRealitySnapshot
from ..registry import GameRegistry


@dataclass
class DataGap:
    game_id: str
    gap_type: str
    severity: str  # "high" | "medium" | "low"
    detail: str
    expected_source: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "game_id": self.game_id,
            "gap_type": self.gap_type,
            "severity": self.severity,
            "detail": self.detail,
            "expected_source": self.expected_source,
        }


class MissingDataDetector:
    """检测每游戏的真实数据缺口（DATA_GAP）。"""

    @staticmethod
    def detect(
        per_game: Dict[str, GrowthRealitySnapshot],
        registry: GameRegistry,
        at_risk: Optional[List[str]] = None,
    ) -> List[DataGap]:
        at_risk = set(at_risk or [])
        gaps: List[DataGap] = []
        for gid, snap in per_game.items():
            bindings = registry.source_bindings(gid)
            sources = set(snap.sources)
            real_domains = set(snap.real_domains)

            has_revenue = "revenue" in real_domains
            has_acq = "acquisition" in real_domains

            # R1：已绑 MAX 账户，但无真实收入域 → 广告收入盲区
            if "max_account" in bindings and not has_revenue:
                gaps.append(DataGap(
                    gid, "max_revenue_missing", "high",
                    "已绑定 MAX 账户但无真实广告收入数据（收入域未进入真实域）",
                    "max_live",
                ))

            # R2：已绑 Adjust，但无真实获量/DAU 域 → 用户规模盲区
            if "adjust_app_token" in bindings and not has_acq:
                gaps.append(DataGap(
                    gid, "adjust_dau_missing", "high",
                    "已绑定 Adjust 但无真实获量/DAU 数据（获量域未进入真实域）",
                    "adjust_live",
                ))

            # R3：已绑 Meta，但 Meta 源未实际贡献 → 投放盲区
            if "meta_app_id" in bindings and "meta_live" not in sources:
                gaps.append(DataGap(
                    gid, "meta_data_missing", "medium",
                    "已绑定 Meta 但 Meta 广告数据未实际进入快照",
                    "meta_live",
                ))

            # R4：有真实收入但缺真实花费 → ROAS 不可计算（最易被高估的陷阱）
            if has_revenue and not has_acq:
                gaps.append(DataGap(
                    gid, "roas_spend_missing", "high",
                    "存在真实广告收入但缺真实获量/花费，ROAS 无法真实计算（会虚高）",
                    "adjust_live/meta_live",
                ))

            # R5：有 MAX 收入但缺 Adjust 付费/获量 → LTV/ROAS 失真
            if has_revenue and "adjust_app_token" in bindings and not has_acq:
                gaps.append(DataGap(
                    gid, "no_adjust_for_roas", "medium",
                    "有 MAX 广告收入但缺 Adjust 付费/获量，LTV/ROAS 失真（仅靠广告端）",
                    "adjust_live",
                ))

            # R6：在运营中（有真实收入或处于风险）但未配置目标国家 → 地理决策盲区
            if ("country" not in bindings) and (has_revenue or gid in at_risk):
                gaps.append(DataGap(
                    gid, "country_unbound", "low",
                    "游戏在运营/风险中但未配置目标国家，地理维度决策盲区",
                    "registry",
                ))

            # R7：处于风险名单但完全无真实数据覆盖 → 盲飞
            if gid in at_risk and not real_domains:
                gaps.append(DataGap(
                    gid, "no_real_coverage_at_risk", "high",
                    "游戏处于风险名单但无任何真实数据覆盖（纯 SIM/空）",
                    "any",
                ))

        return gaps

    @staticmethod
    def summarize(gaps: List[DataGap]) -> Dict[str, int]:
        out = {"high": 0, "medium": 0, "low": 0, "total": len(gaps)}
        for g in gaps:
            if g.severity in out:
                out[g.severity] += 1
        return out
