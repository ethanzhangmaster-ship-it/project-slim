"""P1.1 — Adjust Reality Source（生产真实接入，复用 kpi_client 真传输层）。

设计原则（与全局 Lean / 不新建重复层一致）：
- 不重写 Adjust 客户端；直接 wrap ``operation.providers.live.adjust.kpi_client``
  这个唯一真 urllib 客户端（Bearer 鉴权 + 代理感知）。
- 不引入 provider.py 的假 KPI（dau=5200 硬编码）——那是被禁用路径。
- 符合 E17.1 RealitySource Protocol：
    domain / source_id / collect(game_id, as_of) -> domain dict
  返回多域 bundle {revenue, product}，collector 按 domain 名自动摊开。

SIM 纪律：
- mode="sim"（默认）→ 返回确定性样本，real_api_called 恒 False。
- mode="production" → 真打 Adjust Report Service；只要成功取到数据，
  就把 self.real_api_called 置 True，collector 层会透出（验收硬指标）。
- 任一游戏无 app_token / 无 user_token / API 失败 → 返回 {}，
  该 domain 保持 None（避免被误判 revenue<=0 → at_risk）。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from operation.providers.live.adjust.kpi_client import (
        AdjustAuthError,
        AdjustError,
        fetch_metric_by_app,
        load_adjust_config,
    )
    _HAS_KPI = True
except Exception:  # pragma: no cover - 导入失败时生产模式会明确报错
    fetch_metric_by_app = None  # type: ignore
    load_adjust_config = None  # type: ignore
    AdjustError = Exception  # type: ignore
    AdjustAuthError = Exception  # type: ignore
    _HAS_KPI = False


class AdjustRealitySource:
    """把真实 Adjust 数据接入 E17.1 Growth Reality Hub 的 revenue/product 域。

    真实字段映射（来自 Adjust Report Service）：
        daus    -> product.dau（取窗口均值）
        revenue -> revenue.daily_revenue（取窗口日均 = 周期和 / 天数）
        payers  -> revenue.payer_count（取窗口均值）
    arpdau 由 normalizer 按 daily_revenue / dau 派生，无需此处算。
    """

    domain = "revenue"  # 占位；实际返回 {revenue, product} 多域 bundle
    source_id = "adjust_live"

    def __init__(
        self,
        app_tokens: Optional[Dict[str, str]] = None,
        user_token: str = "",
        mode: str = "sim",
        window_days: int = 7,
        as_of: Optional[str] = None,
        registry=None,
    ):
        # game_id -> Adjust app_token（P1.4 起可由 GameRegistry 统一提供；默认显式传入）
        self.app_tokens: Dict[str, str] = dict(app_tokens or {})
        self.user_token: str = user_token
        self.registry = registry
        self.mode: str = mode
        self.window_days: int = window_days
        self._as_of: Optional[str] = as_of
        self.real_api_called: bool = False

        # 若未显式给 token，尝试从 credentials/live_accounts.json 的 adjust 段补
        if (not self.user_token or not self.app_tokens) and load_adjust_config:
            cfg = load_adjust_config() or {}
            if not self.user_token:
                self.user_token = cfg.get("user_token", "")
            if not self.app_tokens:
                self.app_tokens = dict(cfg.get("app_tokens", {}) or {})

    # ------------------------------------------------------------------ #
    def collect(self, game_id: str, as_of: Optional[str] = None) -> Dict[str, Any]:
        as_of = as_of or self._as_of or _today()
        if self.mode != "production":
            return self._sim(game_id, as_of)
        return self._production(game_id, as_of)

    # ------------------------------------------------------------------ #
    def _production(self, game_id: str, as_of: str) -> Dict[str, Any]:
        if not _HAS_KPI:
            raise RuntimeError(
                "Adjust kpi_client 不可用，无法进入 production 模式")
        app_token = self.app_tokens.get(game_id)
        if not app_token or not self.user_token:
            return {}  # 无配置 → 无数据（domain 保持 None，避免误判 at_risk）
        start = _start_date(as_of, self.window_days)
        try:
            dau_series = fetch_metric_by_app(
                self.user_token, [app_token], "daus", start, as_of)
            rev_series = fetch_metric_by_app(
                self.user_token, [app_token], "revenue", start, as_of)
            payer_series = fetch_metric_by_app(
                self.user_token, [app_token], "payers", start, as_of)
        except (AdjustError, AdjustAuthError):
            return {}

        # 真打到 Adjust → 置 flag（验收硬指标）
        self.real_api_called = True

        dau_list = dau_series.get(app_token, [])
        rev_list = rev_series.get(app_token, [])
        payer_list = payer_series.get(app_token, [])
        if not dau_list and not rev_list:
            return {}

        mean_dau = _mean(dau_list)
        ndays = max(len(rev_list), 1)
        daily_revenue = sum(rev_list) / ndays  # 日均收入
        payer_count = int(round(_mean(payer_list))) if payer_list else 0

        return {
            "revenue": {
                "daily_revenue": round(daily_revenue, 2),
                "payer_count": payer_count,
                "arpdau": 0.0,
                "ltv": 0.0,
            },
            "product": {
                "dau": int(round(mean_dau)),
                "retention": 0.0,
                "conversion": 0.0,
            },
        }

    # ------------------------------------------------------------------ #
    def _sim(self, game_id: str, as_of: str) -> Dict[str, Any]:
        """确定性 SIM 样本（seed 无关，跨进程一致），real_api_called 恒 False。"""
        h = int(hashlib.sha256(f"{game_id}:adjust_sim".encode()).hexdigest()[:8], 16)
        dau = (h % 5000) + 500
        daily_rev = float((h % 2000) + 100)
        payers = (h % 200) + 10
        return {
            "revenue": {
                "daily_revenue": round(daily_rev, 2),
                "payer_count": payers,
                "arpdau": 0.0,
                "ltv": 0.0,
            },
            "product": {
                "dau": dau,
                "retention": 0.0,
                "conversion": 0.0,
            },
        }


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _start_date(as_of: str, window_days: int) -> str:
    try:
        d = datetime.strptime(as_of, "%Y-%m-%d")
    except ValueError:
        d = datetime.utcnow()
    return (d - timedelta(days=max(window_days - 1, 0))).strftime("%Y-%m-%d")


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


__all__ = ["AdjustRealitySource"]
