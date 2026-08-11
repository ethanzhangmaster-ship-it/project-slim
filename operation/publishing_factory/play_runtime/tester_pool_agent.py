"""E13.5 — Tester Pool Agent.

Solves the repeated closed-testing recruitment wall. Google Play requires
>= 12 opted-in testers on the closed track before an app can move to open /
production. The Android Publisher API can only *invite* testers (it cannot
create Google accounts), but the real manual friction is re-entering 12
emails for every new app. This agent keeps ONE persistent pool and
auto-invites it to every app, so the operator enters 12 emails once, not
per-app.

Lean: persistent pool in a JSON file (small, mutable set state), per-event
audit in JSONL (history trail for the briefing). No database.
Gated: reads are READ radius, invites are TESTERS radius (3-gate).
Idempotent: invites the UNION of (existing track testers + pool) so re-runs
never clobber manually-added testers nor duplicate pool members.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Google Play closed-track minimum opted-in testers before promotion.
MIN_POOL = 12


def _root() -> Path:
    env = os.environ.get("LAUNCHFORGE_ROOT")
    if env:
        return Path(env)
    # tester_pool_agent.py -> play_runtime/ -> publishing_factory/ -> launchforge/
    return Path(__file__).resolve().parents[3]


def pool_path() -> Path:
    """Canonical active pool file (env-overridable for tests)."""
    env = os.environ.get("LAUNCHFORGE_PLAY_TESTER_POOL")
    if env:
        return Path(env)
    return _root() / "data" / "play_runtime" / "tester_pool.json"


def audit_path() -> Path:
    """Event-log audit file (env-overridable for tests)."""
    env = os.environ.get("LAUNCHFORGE_PLAY_TESTER_AUDIT")
    if env:
        return Path(env)
    return _root() / "data" / "play_runtime" / "tester_pool_audit.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TesterPoolAgent:
    """Persistent tester pool + per-app closed-track invite automation."""

    __test__ = False  # not a pytest test class

    def __init__(self, connector=None):
        # connector must expose read_testers(pkg, track=) -> PlayResult-like
        # and invite_testers(pkg, tester_emails=, apply=) -> PlayResult-like.
        # Injected so tests can use a fake; production wires the real
        # PlayConnector (gated facade).
        self.connector = connector

    # ------------------------------------------------------------------ #
    # Pool management — local only, NO API calls
    # ------------------------------------------------------------------ #
    def _load_pool(self) -> dict:
        p = pool_path()
        if not p.exists():
            return {"testers": []}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"testers": []}

    def _save_pool(self, data: dict) -> None:
        p = pool_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = _now()
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    def add_tester(self, email: str,
                   groups: Optional[List[str]] = None,
                   name: str = "", note: str = "") -> dict:
        email = (email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            return {"ok": False, "error": f"invalid email: {email!r}"}
        pool = self._load_pool()
        testers = pool.setdefault("testers", [])
        existing = {t["email"] for t in testers}
        if email in existing:
            return {"ok": True, "already": True, "email": email}
        testers.append({
            "email": email,
            "groups": [g for g in (groups or []) if g],
            "name": name or "",
            "note": note or "",
            "added_at": _now(),
        })
        self._save_pool(pool)
        self._audit("pool_add", {"email": email,
                                 "groups": groups or [], "name": name})
        return {"ok": True, "email": email}

    def remove_tester(self, email: str) -> dict:
        email = (email or "").strip().lower()
        pool = self._load_pool()
        before = len(pool.get("testers", []))
        pool["testers"] = [t for t in pool.get("testers", [])
                           if t["email"] != email]
        after = len(pool["testers"])
        if after == before:
            return {"ok": False, "error": "not in pool"}
        self._save_pool(pool)
        self._audit("pool_remove", {"email": email})
        return {"ok": True, "email": email}

    def list_pool(self) -> List[dict]:
        return self._load_pool().get("testers", [])

    def pool_size(self) -> int:
        return len(self.list_pool())

    def meets_minimum(self) -> bool:
        return self.pool_size() >= MIN_POOL

    # ------------------------------------------------------------------ #
    # Invite planning / execution
    # ------------------------------------------------------------------ #
    def propose_invite(self, package_name: str) -> dict:
        """Diff the pool against the app's current track testers.

        Returns the missing set (pool members not yet on the track) and the
        UNION to PUT (current + pool) so existing manually-added testers are
        preserved. Does NOT mutate the console.
        """
        pool = self.list_pool()
        pool_emails = {t["email"] for t in pool}
        current: set = set()
        if self.connector is not None:
            res = self.connector.read_testers(package_name, track="closed")
            data = getattr(res, "data", None) or {}
            current = set(data.get("tester_emails", []))
        missing = sorted(pool_emails - current)
        already = sorted(pool_emails & current)
        union = sorted(current | pool_emails)
        return {
            "package_name": package_name,
            "pool_size": len(pool_emails),
            "current_on_track": sorted(current),
            "missing": missing,
            "already": already,
            "union_to_put": union,
            "would_invite": missing,
            "short_by": max(0, MIN_POOL - len(current | pool_emails)),
        }

    def run_daily(self, packages: List[str],
                  apply: bool = False) -> dict:
        """For each package, invite the pool (as a UNION with whatever is
        already on the track) so nothing is clobbered or duplicated.

        Idempotent: re-running only fills gaps; already-present pool members
        are skipped because the UNION already contains them.
        """
        per_pkg: Dict[str, dict] = {}
        total_missing = 0
        total_invited = 0
        for pkg in packages:
            proposal = self.propose_invite(pkg)
            missing = proposal["missing"]
            union = proposal["union_to_put"]
            per: dict = {"missing": missing, "invited": [],
                         "skipped": 0, "error": None}
            if missing and self.connector is not None:
                # PUT the UNION: existing + pool. Preserves manual testers.
                res = self.connector.invite_testers(
                    pkg, tester_emails=union, apply=apply)
                ok = bool(getattr(res, "ok", False))
                if ok:
                    per["invited"] = missing
                    total_invited += len(missing)
                    # Closed loop: once >= MIN_POOL testers are on the track
                    # (the UNION), start/refresh the 14-day clock in the
                    # pre-existing tester_community eligibility tracker (the
                    # section-5 production-readiness board) so it ticks
                    # automatically — no separate `tester_community invite`.
                    if len(union) >= MIN_POOL:
                        per["clock_started"] = self._record_clock(
                            pkg, len(union))
                else:
                    per["error"] = (getattr(res, "detail", "")
                                    or getattr(res, "error", ""))
                self._audit("invite", {
                    "package_name": pkg, "apply": apply,
                    "missing": missing, "union_size": len(union),
                    "ok": ok,
                    "clock_started": per.get("clock_started"),
                    "stage": str(getattr(res, "stage", "")),
                })
            elif not missing:
                per["skipped"] = len(proposal["already"])
            else:
                # no connector (dry planning) — just record the gap
                self._audit("invite_skip", {
                    "package_name": pkg, "apply": apply,
                    "reason": "no connector", "missing": missing})
            total_missing += len(missing)
            per_pkg[pkg] = per
        return {
            "applied": apply,
            "pool_size": self.pool_size(),
            "meets_minimum": self.meets_minimum(),
            "packages": len(packages),
            "total_missing": total_missing,
            "total_invited": total_invited,
            "per_package": per_pkg,
        }

    def _record_clock(self, package_name: str, tester_count: int) -> bool:
        """Start/refresh the 14-day closed-testing clock in the pre-existing
        ``tester_community.eligibility`` tracker (the section-5 board).

        Returns True if the clock was advanced. Lazy import avoids a
        cross-module import cycle at load time. Best-effort: a failure here
        never blocks the invite itself.
        """
        try:
            from operation.publishing_factory.tester_community import (
                eligibility as tc_eligibility)
            tc_eligibility.record_invitation(package_name, tester_count)
            return True
        except Exception:  # noqa: BLE001 — best-effort, never block invites
            return False

    # ------------------------------------------------------------------ #
    # Audit
    # ------------------------------------------------------------------ #
    def _audit(self, action: str, payload: dict) -> None:
        path = audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"action": action, "at": _now(), **payload}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------- #
# Module-level helpers (used by the briefing + CLI)
# ---------------------------------------------------------------------- #
def load_pool() -> List[dict]:
    return TesterPoolAgent().list_pool()


def summary() -> dict:
    """Aggregate pool + last invite status for the morning briefing.

    Reads ONLY the local pool file + audit JSONL — ZERO network, ZERO writes.
    """
    agent = TesterPoolAgent()
    pool = agent.list_pool()
    pool_size = len(pool)
    # last invite outcome per package from the audit trail
    per_package: Dict[str, dict] = {}
    last_run = None
    if audit_path().exists():
        with audit_path().open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    r = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                last_run = r.get("at", last_run)
                if r.get("action") == "invite" and r.get("package_name"):
                    pkg = r["package_name"]
                    prev = per_package.get(pkg, {})
                    prev["last_ok"] = r.get("ok", prev.get("last_ok", False))
                    prev["last_apply"] = r.get("apply",
                                               prev.get("last_apply", False))
                    prev["last_missing"] = r.get(
                        "missing", prev.get("last_missing", []))
                    per_package[pkg] = prev
    return {
        "pool_size": pool_size,
        "meets_minimum": pool_size >= MIN_POOL,
        "min_required": MIN_POOL,
        "last_run": last_run,
        "per_package": per_package,
        "short_by": max(0, MIN_POOL - pool_size),
    }


def promotion_readiness(package_names: Optional[List[str]] = None,
                        today_iso: Optional[str] = None) -> dict:
    """Combine the persistent tester pool with each app's 14-day
    closed-testing clock to decide which apps can be promoted to
    open / production RIGHT NOW.

    ``can_promote`` requires BOTH:
      - global pool >= MIN_POOL (12)  — tester SUPPLY exists
      - app's 14-day clock is done   — ``production_ready`` from eligibility

    Reads ONLY local state (pool json + tester_progress.json) — ZERO network.
    """
    from operation.publishing_factory.tester_community import (
        eligibility as tc_eligibility)
    agent = TesterPoolAgent()
    pool_size = agent.pool_size()
    pool_ok = pool_size >= MIN_POOL
    pkgs = (list(package_names) if package_names is not None
            else list(tc_eligibility.load_all().keys()))
    apps: List[dict] = []
    promote_list: List[str] = []
    for pkg in pkgs:
        elig = tc_eligibility.get(pkg, today_iso=today_iso)
        can = bool(pool_ok and elig.get("production_ready"))
        rec = {
            "package_name": pkg,
            "pool_size": pool_size,
            "pool_ok": pool_ok,
            "tester_count": elig.get("tester_count", 0),
            "days_running": elig.get("days_running", 0),
            "days_remaining": elig.get("days_remaining", 0),
            "clock_ready": elig.get("production_ready", False),
            "can_promote": can,
            "released_at": elig.get("released_at"),
        }
        apps.append(rec)
        if can:
            promote_list.append(pkg)
    apps.sort(key=lambda r: (not r["can_promote"],
                             r["days_remaining"], r["package_name"]))
    return {
        "pool_size": pool_size,
        "pool_ok": pool_ok,
        "min_required": MIN_POOL,
        "apps": apps,
        "promote_ready": promote_list,
        "promote_count": len(promote_list),
    }


def render_promotion_markdown(report: Optional[dict] = None,
                              today_iso: Optional[str] = None) -> str:
    """Render the promotion-readiness highlight for the section-5 board.

    Does NOT re-render the per-app 14-day table (eligibility already does
    that); it adds the global tester-pool supply + the 🚀 promote-ready list.
    """
    report = report if report is not None else promotion_readiness(
        today_iso=today_iso)
    supply = f"{report['pool_size']}/{report['min_required']}"
    ok = "✅" if report["pool_ok"] else "⚠️ 不足"
    lines = ["", f"**测试员供给池 (Tester Pool): {supply} {ok}**"]
    if report["promote_ready"]:
        lines.append("")
        lines.append(f"🚀 **可晋升生产/open（池≥{report['min_required']} "
                     f"且 14 天封闭测试钟满）：**")
        for pkg in report["promote_ready"]:
            lines.append(f"  - `{pkg}`")
    else:
        lines.append("")
        lines.append(f"⏳ 暂无满足「池≥{report['min_required']} "
                     f"且 14 天封闭测试钟满」的 App")
    return "\n".join(lines)


__all__ = ["TesterPoolAgent", "load_pool", "summary", "MIN_POOL",
           "pool_path", "audit_path", "promotion_readiness",
           "render_promotion_markdown"]
