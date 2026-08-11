"""
E15.2.6.5 — Adjust live DAU client (Lean: urllib only, no deps).

Brings true DAU into the monetization agent's ARPDAU guardrail so the
daily briefing no longer needs a manual `cli.py dau` drop-in.

Two Adjust API generations are involved:

1. App discovery  — `GET https://api.adjust.com/dashboard/api/apps`
   Auth: `Authorization: Token token=<USER_TOKEN>` (falls back to HTTP
   Basic on 401). Returns every app the token can see (token + name).

2. DAU pull (KPI Service is deprecated / HTTP 410) — the **Report Service**
   legacy CSV endpoint:
       GET https://automate.adjust.com/reports-service/csv_report
       ?app_token__in=<csv>&date_period=YYYY-MM-DD:YYYY-MM-DD
       &dimensions=day&metrics=daus&readable_names=true
   Auth: `Authorization: Bearer <USER_TOKEN>`.
   Returns CSV: header + one row per day: `date,平均 DAU`.
   `daus` = average daily active users per day; we average across the
   window to get the account's mean daily DAU (same semantic the operator
   enters via `cli.py dau`, so the ARPDAU guardrail is unchanged).
"""
from __future__ import annotations

import base64
import csv
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DASHBOARD_BASE = "https://api.adjust.com"
REPORT_BASE = "https://automate.adjust.com"


class AdjustError(Exception):
    pass


class AdjustAuthError(AdjustError):
    pass


def _store_path() -> str:
    # operation/providers/live/adjust/kpi_client.py
    # -> workspace/credentials/live_accounts.json
    here = os.path.dirname(os.path.abspath(__file__))
    lf_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(here)))))
    return os.path.join(lf_root, "credentials", "live_accounts.json")


def load_adjust_config() -> Dict[str, Any]:
    path = _store_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data.get("adjust", {}) or {}


def _proxy_from_env() -> Optional[str]:
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(k)
        if v:
            return v
    return None


def _open(url: str, headers: Dict[str, str], timeout: int,
          proxy: Optional[str]) -> Any:
    req = urllib.request.Request(url, headers=headers)
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _request_json(token: str, url: str, params: Optional[Dict] = None,
                  timeout: int = 30, proxy: Optional[str] = None
                  ) -> Tuple[Any, str]:
    """JSON endpoint (app discovery). Token/Basic auth fallback."""
    full = url if not params else f"{url}?{urllib.parse.urlencode(params)}"
    headers = [
        {"Authorization": f"Token token={token}"},
        {"Authorization": "Basic "
         + base64.b64encode(f"{token}:".encode()).decode()},
    ]
    last_err: Optional[Exception] = None
    for attempt, hdr in enumerate(headers):
        try:
            resp = _open(full, hdr, timeout, proxy)
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body), list(hdr.values())[0][:10]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (401, 403) and attempt == 0:
                continue
            err = e.read()[:400].decode("utf-8", errors="replace")
            if e.code in (401, 403):
                raise AdjustAuthError(f"HTTP {e.code}: {err}") from e
            raise AdjustError(f"HTTP {e.code}: {err}") from e
        except urllib.error.URLError as e:
            last_err = e
            if attempt == 0 and proxy is None:
                p = _proxy_from_env()
                if p:
                    try:
                        resp = _open(full, hdr, timeout, p)
                        body = resp.read().decode("utf-8", errors="replace")
                        return json.loads(body), list(hdr.values())[0][:10]
                    except Exception:
                        pass
            continue
    raise AdjustError(f"network: {last_err}")


def _request_text_bearer(token: str, url: str, timeout: int = 40,
                         proxy: Optional[str] = None) -> str:
    """Report Service CSV endpoint. Bearer auth."""
    hdr = {"Authorization": f"Bearer {token}"}
    try:
        resp = _open(url, hdr, timeout, proxy)
        return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err = e.read()[:400].decode("utf-8", errors="replace")
        if e.code in (401, 403):
            raise AdjustAuthError(f"HTTP {e.code}: {err}") from e
        raise AdjustError(f"HTTP {e.code}: {err}") from e
    except urllib.error.URLError as e:
        # one proxy retry
        p = proxy or _proxy_from_env()
        if p:
            try:
                resp = _open(url, hdr, timeout, p)
                return resp.read().decode("utf-8", errors="replace")
            except Exception as ex:
                raise AdjustError(f"network: {ex}") from ex
        raise AdjustError(f"network: {e}") from e


def list_apps(token: str, timeout: int = 30) -> List[Dict[str, Any]]:
    data, _ = _request_json(token, f"{DASHBOARD_BASE}/dashboard/api/apps",
                            timeout=timeout)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("apps", data.get("data", []))
    return []


def fetch_avg_dau(token: str, app_tokens: List[str], start: str, end: str,
                  timeout: int = 40) -> float:
    """Mean daily DAU across the given app tokens over [start, end].

    Uses the Report Service legacy CSV endpoint (the KPI Service /kpis/v1
    is deprecated, HTTP 410). Returns the average of the per-day `daus`
    values so it matches the manual `cli.py dau` semantic exactly.
    """
    if not app_tokens:
        raise AdjustError("no app_tokens supplied")
    at = ",".join(app_tokens)
    params = {
        "app_token__in": at,
        "date_period": f"{start}:{end}",
        "dimensions": "day",
        "metrics": "daus",
        "readable_names": "true",
    }
    url = (f"{REPORT_BASE}/reports-service/csv_report"
           f"?{urllib.parse.urlencode(params)}")
    csv_text = _request_text_bearer(token, url, timeout=timeout)
    return _parse_dau_csv(csv_text)


def _parse_dau_csv(csv_text: str) -> float:
    """Parse the Report Service CSV. Column 0 = date, column 1 = avg DAU.
    Robust to the BOM + localized header (`日 (日期),平均 DAU`)."""
    if not csv_text or not csv_text.strip():
        return 0.0
    reader = csv.reader(io.StringIO(csv_text))
    vals: List[float] = []
    for i, row in enumerate(reader):
        if i == 0:
            continue  # header
        if len(row) < 2:
            continue
        try:
            vals.append(float(row[1].strip()))
        except (ValueError, IndexError):
            continue
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def fetch_avg_dau_by_app(token: str, app_tokens: List[str], start: str, end: str,
                         timeout: int = 40) -> Dict[str, float]:
    """Per-app mean daily DAU across the given app tokens over [start, end].

    Same Report Service endpoint as fetch_avg_dau but with
    ``dimensions=app`` and ``readable_names=false`` so column 0 is the raw
    app token (which is what ``account_apps`` / ``app_token_to_application``
    key on). Returns ``{app_token: avg_dau}``. Empty on error / no data so
    callers can fall back to the account-summed path without raising.
    """
    if not app_tokens:
        return {}
    at = ",".join(app_tokens)
    params = {
        "app_token__in": at,
        "date_period": f"{start}:{end}",
        "dimensions": "app",
        "metrics": "daus",
        "readable_names": "false",
    }
    url = (f"{REPORT_BASE}/reports-service/csv_report"
           f"?{urllib.parse.urlencode(params)}")
    try:
        csv_text = _request_text_bearer(token, url, timeout=timeout)
    except AdjustError:
        return {}
    return _parse_dau_csv_by_app(csv_text)


def _parse_dau_csv_by_app(csv_text: str) -> Dict[str, float]:
    """Parse the Report Service CSV with ``dimensions=app``.

    Column 0 = app token (readable_names=false), column 1 = avg DAU
    (already period-aggregated when no ``day`` dimension). Groups + averages
    across any repeated tokens defensively.
    """
    out: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    if not csv_text or not csv_text.strip():
        return out
    reader = csv.reader(io.StringIO(csv_text))
    for i, row in enumerate(reader):
        if i == 0:
            continue  # header
        if len(row) < 2:
            continue
        key = row[0].strip()
        if not key:
            continue
        try:
            val = float(row[1].strip())
        except (ValueError, IndexError):
            continue
        out[key] = out.get(key, 0.0) + val
        counts[key] = counts.get(key, 0) + 1
    return {k: v / counts[k] for k, v in out.items()}


def fetch_metric_by_app(token: str, app_tokens: List[str], metric: str,
                        start: str, end: str, timeout: int = 40,
                        proxy: Optional[str] = None
                        ) -> Dict[str, List[float]]:
    """Per-app **per-day** series for a single Adjust metric via Report Service.

    Uses ``dimensions=day,app`` so callers get one value per day and can
    decide mean (DAU) vs sum (revenue) themselves. Returns
    ``{app_token: [value_day1, value_day2, ...]}``. Empty on error / no data
    so callers can fall back without raising.

    Metric names follow Adjust Report Service: ``daus``, ``revenue``,
    ``payers``, ``installs``, ``sessions``, etc.
    """
    if not app_tokens or not metric:
        return {}
    at = ",".join(app_tokens)
    params = {
        "app_token__in": at,
        "date_period": f"{start}:{end}",
        "dimensions": "day,app",
        "metrics": metric,
        "readable_names": "false",
    }
    url = (f"{REPORT_BASE}/reports-service/csv_report"
           f"?{urllib.parse.urlencode(params)}")
    try:
        csv_text = _request_text_bearer(token, url, timeout=timeout, proxy=proxy)
    except AdjustError:
        return {}
    return _parse_metric_csv_by_app(csv_text)


def _parse_metric_csv_by_app(csv_text: str) -> Dict[str, List[float]]:
    """Parse Report Service CSV with ``dimensions=day,app``.

    Expected columns: ``date, <app_token>, <metric>``. Column 0 = date,
    column 1 = app token (readable_names=false), column 2 = metric value.
    Groups values per app token in day order.
    """
    out: Dict[str, List[float]] = {}
    if not csv_text or not csv_text.strip():
        return out
    reader = csv.reader(io.StringIO(csv_text))
    for i, row in enumerate(reader):
        if i == 0:
            continue  # header
        if len(row) < 3:
            continue
        key = row[1].strip()
        if not key:
            continue
        try:
            val = float(row[2].strip())
        except (ValueError, IndexError):
            continue
        out.setdefault(key, []).append(val)
    return out


__all__ = ["AdjustError", "AdjustAuthError", "load_adjust_config",
           "list_apps", "fetch_avg_dau", "fetch_avg_dau_by_app",
           "fetch_metric_by_app", "_parse_dau_csv_by_app",
           "_parse_metric_csv_by_app"]
