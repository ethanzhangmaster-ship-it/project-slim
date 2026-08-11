"""
E15.2.5 — User-metrics interface (ARPDAU guardrail, pre-embedded).

The MAX Report API tells us revenue and eCPM, but NOT whether an
optimization *hurt the user*. The core IAA success metric is ARPDAU and
its drivers (ads/user, rewarded/user, interstitial/user). Those require a
user-side source (Adjust / Firebase), which we may not have a key for yet.

This module is the guardrail seam: it defines the contract now so that
every future action can be judged on "did revenue go up WITHOUT raising
ad load per user?". When no provider key is configured it returns a
PENDING UserMetrics (available=False) instead of failing — the daily
report simply shows the guardrail as "pending data source".

No LLM. Providers are stubs that return None until real keys are wired.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from operation.providers.live.adjust.kpi_client import (  # noqa: E402
    fetch_avg_dau, fetch_avg_dau_by_app, load_adjust_config)


@dataclass
class UserMetrics:
    """Per-account user-side monetization metrics over a window."""
    account: str
    period_start: str
    period_end: str
    dau: int = 0                       # average daily active users
    iaa_revenue: float = 0.0           # in-app-ad revenue over the window
    rewarded_impressions: int = 0
    interstitial_impressions: int = 0
    banner_impressions: int = 0
    days: int = 1
    source: str = "none"
    available: bool = True
    note: str = ""
    app_dau: Dict[str, float] = field(default_factory=dict)  # app_id/token -> avg DAU

    # ---- derived IAA guardrail metrics ------------------------------- #
    @property
    def daily_dau(self) -> float:
        return float(self.dau)

    @property
    def arpdau(self) -> float:
        """Average revenue per daily active user (the north-star IAA KPI)."""
        denom = self.dau * max(self.days, 1)
        return (self.iaa_revenue / denom) if denom else 0.0

    @property
    def total_ad_impressions(self) -> int:
        return (self.rewarded_impressions + self.interstitial_impressions
                + self.banner_impressions)

    @property
    def ads_per_user(self) -> float:
        denom = self.dau * max(self.days, 1)
        return (self.total_ad_impressions / denom) if denom else 0.0

    @property
    def rewarded_per_user(self) -> float:
        denom = self.dau * max(self.days, 1)
        return (self.rewarded_impressions / denom) if denom else 0.0

    @property
    def interstitial_per_user(self) -> float:
        denom = self.dau * max(self.days, 1)
        return (self.interstitial_impressions / denom) if denom else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account": self.account,
            "period": {"start": self.period_start, "end": self.period_end},
            "available": self.available,
            "source": self.source,
            "note": self.note,
            "dau": self.dau,
            "arpdau": round(self.arpdau, 5),
            "ads_per_user": round(self.ads_per_user, 3),
            "rewarded_per_user": round(self.rewarded_per_user, 3),
            "interstitial_per_user": round(self.interstitial_per_user, 3),
            "app_dau": dict(self.app_dau),
        }

    @classmethod
    def pending(cls, account: str, start: str, end: str, note: str) -> "UserMetrics":
        return cls(account=account, period_start=start, period_end=end,
                   available=False, source="none", note=note)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserMetrics":
        """Reconstruct from a to_dict() payload. The derived guardrail
        metrics (ads_per_user / arpdau) are reproduced exactly by
        reverse-engineering the impression counts, so UserGuardrail can
        be reused unchanged on stored metrics."""
        dau = int(d.get("dau", 0) or 0)
        days = max(int(d.get("days", 1) or 1), 1)
        apu = float(d.get("ads_per_user", 0.0) or 0.0)
        arp = float(d.get("arpdau", 0.0) or 0.0)
        total_imp = int(round(apu * dau * days)) if dau else 0
        iaa = arp * dau * days if dau else 0.0
        app_dau = _parse_app_dau(d.get("app_dau") or d.get("apps"))
        return cls(account=d.get("account", ""), period_start="", period_end="",
                   dau=dau, iaa_revenue=iaa, rewarded_impressions=total_imp,
                   interstitial_impressions=0, banner_impressions=0, days=days,
                   source=d.get("source", "none"),
                   available=bool(d.get("available", True)),
                   note=d.get("note", ""), app_dau=app_dau)


def _parse_app_dau(raw: Any) -> Dict[str, float]:
    """Normalise either ``{"app": {"dau": N}}`` or ``{"app": N}`` into a
    clean ``{app_id: float}`` dict (invalid entries dropped)."""
    out: Dict[str, float] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        dv = v.get("dau") if isinstance(v, dict) else v
        if isinstance(dv, (int, float)) and dv > 0:
            out[str(k)] = float(dv)
    return out


# --------------------------------------------------------------------- #
class UserMetricsProvider:
    """Base contract. fetch() returns UserMetrics or None (no data/key)."""
    name = "base"

    def fetch(self, account: str, start: str, end: str) -> Optional[UserMetrics]:
        raise NotImplementedError


class AdjustProvider(UserMetricsProvider):
    """Adjust KPI Service live DAU source (E15.2.6.5).

    Requires `adjust.user_token` in credentials/live_accounts.json and an
    `adjust.account_apps` mapping of MAX-account -> [Adjust app tokens].
    Returns a UserMetrics with dau = sum(avg_dau) across the account's apps,
    or None when no token / no mapping is configured yet (so the service
    falls through to the manual drop-in cache). A `client` may be injected
    for offline tests; otherwise the live kpi_client is used lazily.

    Per-app DAU: when the provider can pull `dimensions=app`, `app_dau` is
    filled (keyed by Adjust app token, optionally remapped to the MAX
    `application` id via `adjust.app_token_to_application`). fleet_bridge
    joins these to per-game Rev/DAU. If per-app fails, it falls back to the
    account-summed number (with `app_dau` empty) — fully backward compatible.
    """
    name = "adjust"

    def __init__(self, api_token: Optional[str] = None,
                 account_apps: Optional[Dict[str, List[str]]] = None,
                 auto_discover_all: bool = False,
                 token_to_app: Optional[Dict[str, str]] = None,
                 client: Any = None) -> None:
        cfg = load_adjust_config()
        self.api_token = (api_token if api_token is not None
                          else cfg.get("user_token"))
        self.account_apps = (account_apps if account_apps is not None
                             else (cfg.get("account_apps") or {}))
        self.auto_discover_all = auto_discover_all or bool(
            cfg.get("auto_discover_all"))
        self.token_to_app = (token_to_app if token_to_app is not None
                             else (cfg.get("app_token_to_application") or {}))
        self._client = client

    def _resolve_app_tokens(self, account: str) -> List[str]:
        ats = self.account_apps.get(account)
        if ats:
            return ats
        if self.auto_discover_all and self._client is not None:
            try:
                apps = self._client.list_apps(self.api_token)
                return [a.get("token") for a in apps if a.get("token")]
            except Exception:
                return []
        return []

    def _per_app_dau(self, account: str, start: str, end: str
                     ) -> Dict[str, float]:
        app_tokens = self._resolve_app_tokens(account)
        if not app_tokens:
            return {}
        try:
            if self._client is not None and hasattr(
                    self._client, "fetch_avg_dau_by_app"):
                by_app = self._client.fetch_avg_dau_by_app(
                    self.api_token, app_tokens, start, end)
            else:
                by_app = fetch_avg_dau_by_app(
                    self.api_token, app_tokens, start, end)
        except Exception:
            return {}
        # remap Adjust token -> MAX application id when a mapping exists
        if self.token_to_app:
            by_app = {self.token_to_app.get(tok, tok): dau
                      for tok, dau in by_app.items()}
        return by_app

    def fetch(self, account: str, start: str, end: str) -> Optional[UserMetrics]:
        if not self.api_token:
            return None
        app_tokens = self._resolve_app_tokens(account)
        if not app_tokens:
            return None
        # per-app path first (richer: enables per-game Rev/DAU)
        by_app = self._per_app_dau(account, start, end)
        if by_app:
            total = sum(by_app.values())
            if total > 0:
                return UserMetrics(
                    account=account, period_start=start, period_end=end,
                    dau=int(round(total)), available=True, source="adjust",
                    app_dau=by_app,
                    note=f"Adjust avg_dau per-app over {len(by_app)} app(s)")
        # fallback: account-summed DAU
        try:
            if self._client is not None:
                dau = self._client.fetch_avg_dau(
                    self.api_token, app_tokens, start, end)
            else:
                dau = fetch_avg_dau(self.api_token, app_tokens, start, end)
        except Exception:
            return None
        if not dau or dau <= 0:
            return None
        return UserMetrics(
            account=account, period_start=start, period_end=end,
            dau=int(round(dau)), available=True, source="adjust",
            note=f"Adjust avg_dau summed over {len(app_tokens)} app(s)")


class FirebaseProvider(UserMetricsProvider):
    """Firebase / GA4 BigQuery export stub. Returns None until wired."""
    name = "firebase"

    def __init__(self, service_account: Optional[str] = None) -> None:
        self.service_account = service_account

    def fetch(self, account: str, start: str, end: str) -> Optional[UserMetrics]:
        if not self.service_account:
            return None
        raise NotImplementedError("Firebase live fetch not implemented yet")


class ManualDropInProvider(UserMetricsProvider):
    """Operator-supplied DAU seam. Reads outputs/user_metrics/<account>.json
    written by `cli.py dau` (or any daily export). Returns a UserMetrics with
    dau + available=True; ARPDAU is derived later from MAX revenue by the
    agent. This is the zero-credential path that makes Revenue/DAU and the
    ARPDAU guardrail live *today*, pending the Adjust/Firebase auto-fetch.

    Drop-in file schema:
        {"account": "ACCT_2", "dau": 123456, "source": "manual",
         "as_of": "2026-07-23", "arpdau_history": [...]}
    """
    name = "manual_dropin"
    DIR = os.path.join("outputs", "user_metrics")

    def fetch(self, account: str, start: str, end: str) -> Optional[UserMetrics]:
        p = os.path.join(self.DIR, f"{account}.json")
        if not os.path.exists(p):
            return None
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return None
        dau = int(d.get("dau", 0) or 0)
        if dau <= 0:
            return None
        app_dau = _parse_app_dau(d.get("apps") or d.get("app_dau"))
        return UserMetrics(
            account=account, period_start=start, period_end=end,
            dau=dau, available=True, source="manual_dropin",
            app_dau=app_dau,
            note=(f"operator drop-in DAU {dau:,} (as_of {d.get('as_of','?')})"
                  + (f"; per-app DAU for {len(app_dau)} game(s)"
                     if app_dau else "")))


class UserMetricsService:
    """Tries each provider in order; PENDING if none can serve data.

    Priority: manual drop-in (zero-credential, live today) first, then
    Adjust, then Firebase. The first provider that returns data wins.
    """

    def __init__(self, providers: Optional[List[UserMetricsProvider]] = None) -> None:
        # Real auto-source (Adjust) first; manual drop-in is the cache/fallback.
        self.providers = providers or [
            AdjustProvider(), ManualDropInProvider(), FirebaseProvider()]

    def fetch(self, account: str, start: str, end: str) -> UserMetrics:
        for p in self.providers:
            try:
                m = p.fetch(account, start, end)
            except NotImplementedError:
                m = None
            if m is not None:
                m.source = p.name
                m.available = True
                # Keep the drop-in file fresh as a cache so a later Adjust
                # API blip still has yesterday's real DAU as fallback.
                if p.name == "adjust":
                    try:
                        save_dropin_dau(account, m.dau, end)
                        # Per-app DAU too: fleet_bridge reads the drop-in
                        # file, so persisting app_dau here is what turns on
                        # per-game Rev/DAU in the daily verdict card.
                        if m.app_dau:
                            save_dropin_dau_apps(account, m.app_dau, end)
                    except Exception:
                        pass
                return m
        names = ", ".join(p.name for p in self.providers) or "none"
        return UserMetrics.pending(
            account, start, end,
            note=(f"no user-side key configured ({names}) — ARPDAU/ads-per-user "
                  f"guardrail pending; connect Adjust or Firebase to enable"))


# --------------------------------------------------------------------- #
def save_dropin_dau(account: str, dau: int, as_of: str,
                    dir: str = ManualDropInProvider.DIR) -> str:
    """Persist operator-supplied DAU. Returns the file path written."""
    os.makedirs(dir, exist_ok=True)
    p = os.path.join(dir, f"{account}.json")
    data: Dict[str, Any] = {}
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
    data["account"] = account
    data["dau"] = int(dau)
    data["as_of"] = as_of
    data["source"] = "manual"
    data.setdefault("arpdau_history", [])
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return p


def save_dropin_dau_apps(account: str, apps: Dict[str, float],
                         as_of: str,
                         dir: str = ManualDropInProvider.DIR) -> str:
    """Merge per-app DAU into the operator drop-in file. `apps` maps the
    same application id used in the MAX report (data/<ACCT>_report.json ->
    `application`) to its average daily active users. Preserves the existing
    account-level `dau` when present. Returns the file path written.

    This is the zero-credential seam that gives fleet_bridge per-game
    Rev/DAU for accounts without an Adjust per-app mapping (notably ACCT_1's
    34 manual apps).
    """
    os.makedirs(dir, exist_ok=True)
    p = os.path.join(dir, f"{account}.json")
    data: Dict[str, Any] = {}
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
    data["account"] = account
    if not data.get("dau"):
        total = sum(float(v) for v in apps.values() if isinstance(v, (int, float)))
        if total > 0:
            data["dau"] = int(round(total))
    data.setdefault("apps", {})
    for k, v in apps.items():
        if isinstance(v, (int, float)) and v > 0:
            data["apps"][str(k)] = {"dau": float(v)}
    data["source"] = "manual"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return p


def persist_arpdau(account: str, day: str, dau: int, arpdau: float,
                   revenue: float,
                   dir: Optional[str] = None) -> None:
    """Append/replace the day's derived ARPDAU into the drop-in history so
    tomorrow's run has a real baseline for the guardrail delta."""
    dir = dir or ManualDropInProvider.DIR
    p = os.path.join(dir, f"{account}.json")
    if not os.path.exists(p):
        return
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    hist = data.setdefault("arpdau_history", [])
    hist = [h for h in hist if h.get("date") != day]
    hist.append({"date": day, "dau": int(dau),
                 "arpdau": round(arpdau, 5), "revenue": round(revenue, 2)})
    data["arpdau_history"] = sorted(hist, key=lambda h: h["date"])[-60:]
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# --------------------------------------------------------------------- #
@dataclass
class GuardrailResult:
    ok: bool
    verdict: str                       # pass | regression | pending
    details: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "verdict": self.verdict, "details": self.details}


class UserGuardrail:
    """
    Judges whether an optimization is safe from the USER's side:
    revenue may rise, but ad load per user must not blow past a tolerance.
    Used later to gate Experiment-layer actions before rollout.
    """
    MAX_ADS_PER_USER_INCREASE = 0.15    # +15% ad load tolerance
    MIN_ARPDAU_IMPROVEMENT = 0.0        # ARPDAU should not fall

    def evaluate(self, baseline: UserMetrics, current: UserMetrics) -> GuardrailResult:
        if not baseline.available or not current.available:
            return GuardrailResult(
                ok=True, verdict="pending",
                details=["user metrics unavailable — cannot verify ad-load impact; "
                         "treat action as unverified"])
        details: List[str] = []
        ok = True
        if baseline.ads_per_user > 0:
            delta = (current.ads_per_user / baseline.ads_per_user) - 1.0
            details.append(f"ads/user {baseline.ads_per_user:.2f} -> "
                           f"{current.ads_per_user:.2f} ({delta:+.0%})")
            if delta > self.MAX_ADS_PER_USER_INCREASE:
                ok = False
        arp_delta = current.arpdau - baseline.arpdau
        details.append(f"ARPDAU {baseline.arpdau:.4f} -> {current.arpdau:.4f} "
                       f"({arp_delta:+.4f})")
        if arp_delta < self.MIN_ARPDAU_IMPROVEMENT:
            ok = False
        return GuardrailResult(ok=ok,
                               verdict="pass" if ok else "regression",
                               details=details)
