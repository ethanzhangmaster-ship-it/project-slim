"""P1.2 — MAX Reality Source（生产真实接入，复用 RealFleetBridge 真报表加载器）。

设计原则（与 P1.1 一致性，不新建重复层）：
- 不重写 MAX 报表解析；直接 wrap ``operation.factory_brain.fleet_bridge.RealFleetBridge``
  这个既有的真报表加载器（读 data/<ACCT>_report.json，零凭据/零写）。
- 不重写聚合数学；MAX 报表里 per-app 收入 = SUM(estimated_revenue)，
  直接在 source 内做"报表行 -> E17.1 revenue 域"的最小映射（这是 source 的职责，非重复 analyzer）。
- 复用 ``RealFleetBridge.load_user_metrics`` 拿 per-app DAU（outputs/user_metrics/<ACCT>.json），
  使 arpdau 也成为真实值（无 DAU 时回退 0，不误判）。
- 符合 E17.1 RealitySource Protocol：domain / source_id / collect(game_id, as_of) -> domain dict。
  返回单域 bundle {"revenue": {...}}，collector 按 domain 名归位。

SIM 纪律：
- mode="sim"（默认）→ 返回确定性样本，real_api_called 恒 False。
- mode="production" → 读真实 ACCT 报表文件；只要成功读到任意一行，
  就把 self.real_api_called 置 True，collector 层会透出（验收硬指标）。
- 任一 game_id 在报表中无对应 application → 返回 {}，该 domain 保持 None。
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

try:
    from operation.factory_brain.fleet_bridge import RealFleetBridge
    _HAS_BRIDGE = True
except Exception:  # pragma: no cover - 导入失败时 production 模式会明确报错
    RealFleetBridge = None  # type: ignore
    _HAS_BRIDGE = False


# 默认拉取的真实账号（与 CFO Report / Fleet Bridge 一致的 3 个 MAX 账号）
DEFAULT_ACCOUNTS = ["ACCT_1", "ACCT_2", "ACCT_3"]


def _all_max_apps(registry) -> List[str]:
    """P1.4：从注册表取出所有 MAX application 名（注册表主键即 application 名）。"""
    try:
        return list(registry.all_game_ids())
    except Exception:
        return []


class MaxRealitySource:
    """把真实 MAX 报表数据接入 E17.1 Growth Reality Hub 的 revenue 域。

    真实字段映射（来自 MAX Report API dump）：
        estimated_revenue -> revenue.daily_revenue（窗口日均 = 周期和 / 天数）
        DAU (user_metrics) -> revenue.arpdau = daily_revenue / dau（有则真值）
        impressions/attempts/responses -> 仅内部质量指标（eCPM/show_rate 计算用）
    """

    domain = "revenue"  # 占位；实际返回 {"revenue": {...}} 单域 bundle
    source_id = "max_live"

    def __init__(
        self,
        accounts: Optional[List[str]] = None,
        data_dir: str = "data",
        app_map: Optional[Dict[str, str]] = None,
        mode: str = "sim",
        window_days: int = 7,
        as_of: Optional[str] = None,
        registry=None,
    ):
        # 要加载的 MAX 账号报表
        self.accounts: List[str] = list(accounts or DEFAULT_ACCOUNTS)
        self.data_dir: str = data_dir
        # P1.4：优先用 GameRegistry 统一 app→game 映射；否则回退显式 app_map；
        # 默认 game_id == MAX application 名（注册表即以此为主键）。
        if app_map:
            self.app_map: Dict[str, str] = dict(app_map)
        elif registry is not None:
            self.app_map = {
                app: (registry.max_app_to_game_id(app) or app)
                for app in _all_max_apps(registry)
            }
        else:
            self.app_map = {}
        self.registry = registry
        self.mode: str = mode
        self.window_days: int = window_days
        self._as_of: Optional[str] = as_of
        self.real_api_called: bool = False

        # 内部缓存：application -> 聚合槽（首次生产 collect 时加载）
        self._cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._app_dau: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    def collect(self, game_id: str, as_of: Optional[str] = None) -> Dict[str, Any]:
        as_of = as_of or self._as_of or _today()
        if self.mode != "production":
            return self._sim(game_id, as_of)
        return self._production(game_id, as_of)

    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> None:
        """懒加载真实报表（每实例仅一次），成功读到数据即置 real_api_called。"""
        if self._cache is not None:
            return
        self._cache = {}
        if not _HAS_BRIDGE:
            raise RuntimeError(
                "RealFleetBridge 不可用，无法进入 MAX production 模式")
        bridge = RealFleetBridge(data_dir=self.data_dir)
        any_loaded = False
        for acct in self.accounts:
            rep = bridge.load_report(acct)
            if not rep:
                continue
            self._accumulate(rep.get("rows", []))
            any_loaded = True
            # 复用既有 per-app DAU 指标（arpdau 真值来源）
            metrics = bridge.load_user_metrics(acct) or {}
            app_dau = metrics.get("app_dau") or metrics.get("apps") or {}
            if isinstance(app_dau, dict):
                for k, v in app_dau.items():
                    try:
                        self._app_dau[str(k).strip()] = float(v)
                    except (TypeError, ValueError):
                        continue
        if any_loaded:
            self.real_api_called = True

    def _accumulate(self, rows: List[Dict[str, Any]]) -> None:
        for r in rows:
            app = str(r.get("application") or "?").strip()
            if app == "?":
                continue
            rev = _to_float(r.get("estimated_revenue"))
            imp = int(_to_float(r.get("impressions")))
            att = int(_to_float(r.get("attempts")))
            resp = int(_to_float(r.get("responses")))
            day = str(r.get("day") or "")
            net = str(r.get("network") or "?").strip()
            fmt = str(r.get("ad_format") or "?").strip()
            slot = self._cache.setdefault(  # type: ignore[union-attr]
                app,
                {
                    "rev": 0.0, "imp": 0, "att": 0, "resp": 0,
                    "days": set(), "net": {}, "fmt": {},
                },
            )
            slot["rev"] += rev
            slot["imp"] += imp
            slot["att"] += att
            slot["resp"] += resp
            slot["net"][net] = slot["net"].get(net, 0.0) + rev
            slot["fmt"][fmt] = slot["fmt"].get(fmt, 0.0) + rev
            if day:
                slot["days"].add(day)

    # ------------------------------------------------------------------ #
    def _production(self, game_id: str, as_of: str) -> Dict[str, Any]:
        self._ensure_loaded()
        app = self.app_map.get(game_id, game_id)
        slot = (self._cache or {}).get(app)
        if not slot:
            return {}  # 报表中无此 application → 无数据（domain 保持 None）

        ndays = max(len(slot["days"]), 1)
        daily_revenue = slot["rev"] / ndays
        imp = slot["imp"]
        att = slot["att"]
        ecpm = round(slot["rev"] / imp * 1000, 4) if imp else 0.0
        rewarded = slot["fmt"].get("REWARD", 0.0)
        total = slot["rev"] or 1.0
        net_dist = {k: round(v / total, 4) for k, v in slot["net"].items()}

        revenue = {
            "daily_revenue": round(daily_revenue, 2),
            "payer_count": 0,  # MAX 报表不含付费人数；保持 0（不误判）
            "arpdau": self._arpdau(app, daily_revenue),
            "ltv": 0.0,
            "impressions": imp,
            "requests": att,
            "ecpm": ecpm,
            "rewarded_video_revenue": round(rewarded / ndays, 2),
            "network_distribution": net_dist,
        }
        out: Dict[str, Any] = {"revenue": revenue}

        # 复用 RealFleetBridge.load_user_metrics 的 per-app DAU → product 域
        dau = self._app_dau.get(app)
        if dau:
            out["product"] = {"dau": int(dau), "retention": 0.0, "conversion": 0.0}
        return out

    def _arpdau(self, app: str, daily_revenue: float) -> float:
        dau = self._app_dau.get(app)
        return round(daily_revenue / dau, 4) if dau else 0.0

    # ------------------------------------------------------------------ #
    def _sim(self, game_id: str, as_of: str) -> Dict[str, Any]:
        """确定性 SIM 样本（跨进程一致），real_api_called 恒 False。"""
        h = int(hashlib.sha256(f"{game_id}:max_sim".encode()).hexdigest()[:8], 16)
        daily_rev = float((h % 3000) + 200)
        dau = (h % 8000) + 1000
        imp = (h % 200000) + 50000
        att = imp * 3
        ecpm = round(daily_rev / imp * 1000, 4) if imp else 0.0
        return {
            "revenue": {
                "daily_revenue": round(daily_rev, 2),
                "payer_count": (h % 300) + 20,
                "arpdau": round(daily_rev / dau, 4),
                "ltv": 0.0,
                "impressions": imp,
                "requests": att,
                "ecpm": ecpm,
                "rewarded_video_revenue": round(daily_rev * 0.6, 2),
                "network_distribution": {"MINTEGRAL_BIDDING": 0.5, "APPLOVIN": 0.5},
            }
        }


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _to_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


__all__ = ["MaxRealitySource", "DEFAULT_ACCOUNTS"]
