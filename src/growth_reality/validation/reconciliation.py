"""P1.7.1 — 收入交叉对账引擎（Revenue Reconciliation Engine）。

把 Adjust IAP 收入 + MAX 广告收入 与 E17.1 快照 total 做交叉对账：
- expected_total = adjust_iap + max_ads
- reported_total = company snapshot daily_revenue
- variance = |expected - reported| / max(expected, 0.01)

阈值：
- GREEN  : variance < 5%   → 可信
- YELLOW : 5% ≤ var < 20%  → 需关注
- RED    : variance ≥ 20%  → 禁止自动决策
- INSUFFICIENT : 缺任一源数据 → 无法对账
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models import GrowthRealitySnapshot
from ..snapshot import CompanySnapshot
from .models import RevenueReconciliation

_VSMALL = 0.01  # 除零保护


def _variance(expected: float, reported: float) -> float:
    denom = max(abs(expected), _VSMALL)
    return abs(expected - reported) / denom


def _status(v: float) -> str:
    if v < 0.05:
        return "GREEN"
    if v < 0.20:
        return "YELLOW"
    return "RED"


class RevenueReconciler:
    """收入交叉对账器：逐游戏对比 Adjust IAP + MAX Ad vs 快照总收入的差异。"""

    @staticmethod
    def reconcile_game(
        game_id: str,
        snap: Optional[GrowthRealitySnapshot],
        adjust_iap: Optional[float],
        max_ads: Optional[float],
    ) -> RevenueReconciliation:
        """对单个游戏执行收入对账。

        Args:
            game_id: 游戏 ID
            snap: E17.1 快照（提供 reported_total = snap.revenue.daily_revenue）
            adjust_iap: Adjust 口径 IAP 日收入（无数据传 None）
            max_ads: MAX 口径广告日收入（无数据传 None）

        Returns:
            RevenueReconciliation with status
        """
        has_adj = adjust_iap is not None
        has_max = max_ads is not None

        # 至少需要一个源有数据
        if not has_adj and not has_max:
            return RevenueReconciliation(
                game_id=game_id, status="INSUFFICIENT",
                detail="无 Adjust 和 MAX 数据",
            )

        iap = adjust_iap or 0.0
        ads = max_ads or 0.0
        expected = iap + ads
        reported = snap.revenue.daily_revenue if (snap and snap.revenue) else 0.0

        if expected < _VSMALL and reported < _VSMALL:
            # 收入为零（可能新游戏），不算异常
            return RevenueReconciliation(
                game_id=game_id, adjust_iap=iap, max_ads=ads,
                expected_total=0.0, reported_total=0.0,
                variance=0.0, status="GREEN",
                detail="零收入游戏",
            )

        var = _variance(expected, reported)
        status = _status(var)

        detail = ""
        if status == "RED":
            detail = (f"期望收入 ¥{expected:.0f}（Adjust ¥{iap:.0f} + MAX ¥{ads:.0f}），"
                      f"快照报告 ¥{reported:.0f}，偏差 {var:.1%}")
        elif status == "YELLOW":
            detail = f"偏差 {var:.1%}，建议人工核对"
        elif not has_adj or not has_max:
            detail = "单源对账（仅一侧有数据）"

        return RevenueReconciliation(
            game_id=game_id,
            adjust_iap=iap, max_ads=ads,
            expected_total=expected, reported_total=reported,
            variance=round(var, 4), status=status, detail=detail,
        )

    @staticmethod
    def reconcile_fleet(
        company: CompanySnapshot,
        adjust_by_game: Optional[Dict[str, Optional[float]]] = None,
        max_by_game: Optional[Dict[str, Optional[float]]] = None,
        reported_by_game: Optional[Dict[str, Optional[float]]] = None,
    ) -> Dict[str, RevenueReconciliation]:
        """对全舰队执行收入对账。

        Args:
            company: E17.1 公司快照
            adjust_by_game: {game_id: IAP日收入}，键不存在 = 无数据
            max_by_game: {game_id: 广告日收入}，键不存在 = 无数据
            reported_by_game: {game_id: 显式报告收入}。若提供则覆盖 snap.revenue.daily_revenue。
                用于已知 pipeline 限制（如 Adjust 后写覆盖 MAX）时手动汇入总收入。

        Returns:
            {game_id: RevenueReconciliation}
        """
        adj_map = adjust_by_game or {}
        max_map = max_by_game or {}
        rep_map = reported_by_game or {}
        out: Dict[str, RevenueReconciliation] = {}
        for gid, snap in company.per_game.items():
            # 显式传入的 reported 优先于 snap.revenue.daily_revenue
            if gid in rep_map and rep_map[gid] is not None:
                # 构造一个临时 snapshot 用于 reconcile 消费
                class _FakeRev:
                    daily_revenue = float(rep_map[gid])
                snap_override = None
            else:
                snap_override = snap
            out[gid] = RevenueReconciler.reconcile_game(
                gid,
                snap if snap_override is not None else _SnapWithRevenue(
                    game_id=gid, reported=float(rep_map[gid])),
                adj_map.get(gid),
                max_map.get(gid),
            )
        return out

    @staticmethod
    def consistency_score(recon: RevenueReconciliation) -> float:
        """把对账结果转为一致性分（0-1），供 ConfidenceScorer 使用。

        GREEN → 1.0, YELLOW → 0.6, RED → 0.3, INSUFFICIENT → 1.0（中立）
        """
        if recon.status == "GREEN":
            return 1.0
        if recon.status == "YELLOW":
            return 0.6
        if recon.status == "RED":
            return 0.3
        return 1.0  # INSUFFICIENT: 无证据不等于不一致（不扣分）


class _SnapWithRevenue:
    """最小化 snapshot 替身：只提供 reconcile_game 所需的 revenue.daily_revenue。"""
    class _Rev:
        def __init__(self, v): self.daily_revenue = v
    def __init__(self, game_id, reported):
        self.game_id = game_id
        self.revenue = self._Rev(reported)
