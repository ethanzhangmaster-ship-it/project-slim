"""
P3 — Minimal stdlib JSON HTTP client.

Used by the store real clients (App Store Connect / Google Play) so the
project stays Lean (no requests/urllib3 dependency). Returns a normalized
dict that every real client method understands:

    {"success": True,  "status_code": 200, "data": <parsed json or {}>}
    {"success": False, "status_code": <code|0>, "error": <msg>, "data": None}
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def http_json(method: str,
              url: str,
              *,
              body: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None,
              timeout: int = 20) -> Dict[str, Any]:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method.upper())
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if data is not None and "Content-Type" not in (headers or {}):
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return {
                "success": True,
                "status_code": resp.status,
                "data": json.loads(raw),
            }
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")[:2000]
        return {
            "success": False,
            "status_code": e.code,
            "error": f"HTTP {e.code}: {raw}",
            "data": None,
        }
    except Exception as e:  # noqa: BLE001 — surface as structured error
        return {
            "success": False,
            "status_code": 0,
            "error": f"{type(e).__name__}: {e}",
            "data": None,
        }


__all__ = ["http_json"]
