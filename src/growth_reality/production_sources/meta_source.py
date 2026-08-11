"""P1.3 — Meta Reality Source（生产真实接入，复用 meta_client 真传输层）。

设计原则（与 P1.1/P1.2 一致，不新建重复层）：
- 不重写 Meta 客户端；直接 wrap ``operation.providers.live.meta.meta_client``
  这个唯一真 urllib Graph API 传输层（Bearer 鉴权 + 代理感知，仅读不写）。
- 不沿用 ``monetization/reality/production/meta_reader.py`` 的 sample 假数据；
  那是 sample-backed（注释明说「replace _load with real API」），本源才是真打 API。
- 符合 E17.1 RealitySource Protocol：domain / source_id / collect(game_id, as_of)。
  返回 acquisition 域 bundle；roas 由 RealityNormalizer 用 revenue 派生（月化日收入/花费）。

SIM 纪律：
- mode="sim"（默认）→ 返回确定性样本，real_api_called 恒 False。
- mode="production" → 真打 Meta Graph API；只要成功读到任意 campaign 数据，
  就把 self.real_api_called 置 True，collector 层会透出（验收硬指标）。
- 任一 game_id 在 campaign 中无对应（经 app_map）→ 返回 {}，该域保持 None。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from operation.providers.live.meta.meta_client import (
        MetaAuthError,
        MetaError,
        fetch_campaign_insights,
        load_meta_config,
    )
    _HAS_CLIENT = True
except Exception:  # pragma: no cover - 导入失败时 production 模式会明确报错
    fetch_campaign_insights = None  # type: ignore
    load_meta_config = None  # type: ignore
    MetaError = Exception  # type: ignore
    MetaAuthError = Exception  # type: ignore
    _HAS_CLIENT = False


class MetaRealitySource:
    """把真实 Meta Ads 买量数据接入 E17.1 Growth Reality Hub 的 acquisition 域。

    真实字段映射（来自 Meta Graph API insights）：
        spend         -> acquisition.spend（窗口累计）
        impressions   -> acquisition（透传，供 normalizer 扩展；当前入 spend/installs 计算）
        installs      -> acquisition.installs（actions 中 action_type 含 install）
        cpi           = spend / installs（聚合后计算）
        roas          -> 由 RealityNormalizer 用 revenue.daily_revenue 派生，此处给 0
    """

    domain = "acquisition"  # 占位；实际返回 {"acquisition": {...}}
    source_id = "meta_live"

    def __init__(
        self,
        access_token: str = "",
        ad_account_id: str = "",
        app_map: Optional[Dict[str, str]] = None,
        mode: str = "sim",
        window_days: int = 7,
        as_of: Optional[str] = None,
        proxy: Optional[str] = None,
        registry=None,
    ):
        # P1.4：优先 GameRegistry 统一 campaign→game 映射；否则回退显式 app_map
        if app_map:
            self.app_map: Dict[str, str] = dict(app_map)
        elif registry is not None:
            self.app_map = {}
            try:
                for gid in registry.all_game_ids():
                    for cid in registry.game_id_to_meta_campaigns(gid):
                        self.app_map[cid] = gid
                    if registry.lookup(gid):
                        self.app_map[registry.lookup(gid).display_name] = gid
            except Exception:
                self.app_map = {}
        else:
            self.app_map = {}
        self.registry = registry
        self.mode: str = mode
        self.window_days: int = window_days
        self._as_of: Optional[str] = as_of
        self.proxy: Optional[str] = proxy
        self.real_api_called: bool = False

        # 未显式给凭证时尝试从 credentials/live_accounts.json 的 meta 段补
        self.access_token: str = access_token
        self.ad_account_id: str = ad_account_id
        if (not self.access_token or not self.ad_account_id) and load_meta_config:
            cfg = load_meta_config() or {}
            if not self.access_token:
                self.access_token = cfg.get("access_token", "")
            if not self.ad_account_id:
                self.ad_account_id = cfg.get("ad_account_id", "")

        self._cache: Optional[Dict[str, Dict[str, float]]] = None

    # ------------------------------------------------------------------ #
    def collect(self, game_id: str, as_of: Optional[str] = None) -> Dict[str, Any]:
        as_of = as_of or self._as_of or _today()
        if self.mode != "production":
            return self._sim(game_id, as_of)
        return self._production(game_id, as_of)

    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> None:
        if self._cache is not None:
            return
        self._cache = {}
        if not _HAS_CLIENT:
            raise RuntimeError(
                "meta_client 不可用，无法进入 Meta production 模式")
        if not self.access_token or not self.ad_account_id:
            return  # 无凭证 → 无真实调用，real_api_called 保持 False
        start = _start_date(self._as_of or _today(), self.window_days)
        end = self._as_of or _today()
        try:
            rows = fetch_campaign_insights(
                self.access_token, self.ad_account_id, start, end,
                proxy=self.proxy,
            )
        except (MetaError, MetaAuthError):
            return
        for r in rows:
            # 先按 campaign_id 精确映射，再按 campaign_name（app_map 已登记
            # display_name → game_id 条目），最后回退原始 campaign_name。
            gid = (
                self.app_map.get(r["campaign_id"])
                or self.app_map.get(r["campaign_name"])
                or r["campaign_name"]
            )
            slot = self._cache.setdefault(  # type: ignore[union-attr]
                gid, {"spend": 0.0, "imp": 0, "inst": 0})
            slot["spend"] += r["spend"]
            slot["imp"] += r["impressions"]
            slot["inst"] += r["installs"]
        if self._cache:
            self.real_api_called = True

    def _production(self, game_id: str, as_of: str) -> Dict[str, Any]:
        self._ensure_loaded()
        slot = (self._cache or {}).get(game_id)
        if not slot:
            return {}
        spend = slot["spend"]
        inst = int(slot["inst"])
        cpi = round(spend / inst, 2) if inst else 0.0
        return {
            "acquisition": {
                "spend": round(spend, 2),
                "installs": inst,
                "cpi": cpi,
                "roas": 0.0,  # 由 RealityNormalizer 用 revenue 派生
            }
        }

    # ------------------------------------------------------------------ #
    def _sim(self, game_id: str, as_of: str) -> Dict[str, Any]:
        """确定性 SIM 样本（跨进程一致），real_api_called 恒 False。"""
        h = int(hashlib.sha256(f"{game_id}:meta_sim".encode()).hexdigest()[:8], 16)
        spend = float((h % 5000) + 200)
        inst = (h % 4000) + 100
        cpi = round(spend / inst, 2) if inst else 0.0
        return {
            "acquisition": {
                "spend": round(spend, 2),
                "installs": inst,
                "cpi": cpi,
                "roas": 0.0,
            }
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


__all__ = ["MetaRealitySource"]
