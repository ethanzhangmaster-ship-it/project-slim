"""Per-app closed-testing eligibility tracker.

Background
----------
Google Play requires each NEW app to satisfy
  "12+ closed-testing testers opted in for 14+ consecutive days"
before production access is granted. We track that locally so the
daily briefing can show progress per app.

Storage
-------
``data/tester_progress.json`` — flat dict ``{package_name: state}``.
State fields:
  - ``invited_at``   ISO date string when this app's closed testers were
                     first populated >= 12 strong (i.e. the 14-day
                     clock could start ticking).
  - ``tester_count`` Last recorded count of testers invited.
  - ``released_at`` ISO date string of the first attempt to release
                    to production (filled in when user clicks
                    "Apply for production release" successfully).
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REQUIRED_TESTERS = 12
REQUIRED_DAYS = 14

_PROGRESS_PATH = Path("data/tester_progress.json")


def _progress_path() -> Path:
    """Pick the right place to keep tester_progress.json.

    Resolution order:
      1) $LAUNCHFORGE_TESTER_PROGRESS env var
      2) CWD/data/tester_progress.json
      3) module-parent/../data/tester_progress.json
    """
    env = os.environ.get("LAUNCHFORGE_TESTER_PROGRESS", "").strip()
    if env:
        return Path(env)
    cwd = Path.cwd() / "data" / "tester_progress.json"
    if cwd.parent.exists():
        return cwd
    here = Path(__file__).resolve()
    return here.parents[2] / "data" / "tester_progress.json"


def _today() -> str:
    """ISO date string for today (UTC). Used as the 14-day clock anchor."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_iso(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except (TypeError, ValueError):
        return None


def load_all() -> Dict[str, Dict]:
    p = _progress_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_all(state: Dict[str, Dict]) -> None:
    p = _progress_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                 encoding="utf-8")


def get(package_name: str, today_iso: Optional[str] = None) -> Dict:
    """Return the eligibility state for one app. Default fields added if
    missing (so callers don't need to .get() everything). ``today_iso``
    can be injected for deterministic testing; defaults to real today
    (UTC)."""
    state = load_all().get(package_name) or {}
    today = date.fromisoformat(today_iso) if today_iso else date.fromisoformat(
        _today())
    invited_at = _parse_iso(state.get("invited_at"))
    days_running = 0
    days_remaining = REQUIRED_DAYS
    production_ready = False
    if invited_at:
        days_running = max(0, (today - invited_at).days)
        days_remaining = max(0, REQUIRED_DAYS - days_running)
        production_ready = days_remaining == 0
    return {
        "package_name": package_name,
        "invited_at": state.get("invited_at"),
        "tester_count": int(state.get("tester_count") or 0),
        "released_at": state.get("released_at"),
        "days_running": days_running,
        "days_remaining": days_remaining,
        "production_ready": production_ready,
    }


def record_invitation(package_name: str, tester_count: int,
                       today_iso: Optional[str] = None) -> Dict:
    """Update (or start) the 14-day clock for ``package_name`` once we
    have at least ``REQUIRED_TESTERS`` testers. The clock starts on
    ``today_iso`` (default: today UTC)."""
    state = load_all()
    cur = state.get(package_name, {})
    today_iso = today_iso or _today()
    invited_at = cur.get("invited_at")
    new_count = max(int(tester_count or 0), int(cur.get("tester_count") or 0))
    if not invited_at and new_count >= REQUIRED_TESTERS:
        invited_at = today_iso
    state[package_name] = {
        **cur,
        "tester_count": new_count,
        "invited_at": invited_at,
    }
    save_all(state)
    return get(package_name)


def record_release(package_name: str,
                   today_iso: Optional[str] = None) -> Dict:
    """Mark that production release was applied for/achieved."""
    state = load_all()
    cur = state.get(package_name, {})
    today_iso = today_iso or _today()
    state[package_name] = {
        **cur,
        "released_at": today_iso,
    }
    save_all(state)
    return get(package_name)


def all_apps() -> List[Dict]:
    """Return eligibility state for every package we've tracked, sorted
    by days_running desc (most-mature first)."""
    out = [get(p) for p in load_all().keys()]
    out.sort(key=lambda r: (-(r.get("days_running") or 0),
                            r.get("package_name") or ""))
    return out


def render_markdown(rows: Optional[List[Dict]] = None,
                    today_iso: Optional[str] = None) -> str:
    """Render the table for the daily briefing. ``today_iso`` is
    injectable for tests; defaults to real today (UTC)."""
    rows = rows if rows is not None else all_apps()
    if not rows:
        return ("5️⃣ Production Readiness — no apps tracked yet\n"
                "   Invite the closed-testing community to your first "
                "new app with:\n"
                "     python -m operation.publishing_factory."
                "tester_community invite <package>\n")
    lines = [
        "5️⃣ Production Readiness · 14-day closed-testing clock",
        "Per-app: testers invited / 12 required and days running / 14 "
        "required for production access.\n",
    ]
    header = ("| package | testers | days running | days left | status |")
    sep = "|---|---|---|---|---|"
    body = []
    for r in rows:
        pkg = r.get("package_name") or "?"
        cnt = r.get("tester_count") or 0
        dr = r.get("days_running") or 0
        dl = r.get("days_remaining") or 0
        prod_rdy = r.get("production_ready")
        rel = r.get("released_at")
        if rel:
            status = f"released {rel}"
        elif prod_rdy:
            status = "ready to apply"
        elif cnt < REQUIRED_TESTERS:
            status = f"{REQUIRED_TESTERS - cnt} more testers"
        elif dl > 0:
            status = f"{dl} more days"
        else:
            status = "-"
        body.append(f"| {pkg} | {cnt}/{REQUIRED_TESTERS} | "
                    f"{dr}/{REQUIRED_DAYS} | "
                    f"{dl if dl > 0 else '—'} | {status} |")
    return "\n".join(lines + [header, sep] + body) + "\n"


__all__ = [
    "REQUIRED_TESTERS",
    "REQUIRED_DAYS",
    "load_all",
    "save_all",
    "get",
    "record_invitation",
    "record_release",
    "all_apps",
    "render_markdown",
]
