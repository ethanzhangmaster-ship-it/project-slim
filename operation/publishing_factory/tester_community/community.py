"""12-person Closed Testing Tester Community — permanent one-time setup,
reused across every new app.

Google Play 2023-11 policy: each NEW app must satisfy a "closed test with
12+ opt-in testers for 14+ consecutive days" gate before production access
is granted. There is no way for this codebase to fabricate real humans —
the people must exist. What we DO automate is the operational side:

  * one-time config of the 12-person community (stored in
    ``credentials/tester_community.json`` — git-ignored, alongside
    ``live_accounts.json`` and ``store_keys.json``).
  * bulk invite them to a given app's closed testing track via the
    real Edits API (``testers/PUT``).
  * track per-app eligibility progress (testers invited, days running,
    days remaining) in ``data/tester_progress.json``.
  * render this for daily briefing.

The credentials JSON lives in the workspace-root ``credentials/`` folder
(not in launchforge/credentials/) so it sits with other live secrets.

SAFETY
======
This module only WRITES to the closed-testing testers list via the
existing ``GooglePlayRealClient`` (which itself goes through the same
Edits API as the listing writer). It never publishes to production.
Dry-run is the default for every write; ``--apply`` is explicit.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

# ----- workspace-root credentials/ ----------------------------------- #
# live_accounts.json / store_keys.json live in credentials/ at the
# WORKSPACE root (alongside launchforge/), not inside launchforge/.
# We search both candidates so this module works whether you launch it
# from launchforge/ or from the workspace root.

_REQUIRED_TESTERS = 12  # Google Play minimum for production access
_DEFAULT_NOTE = ("Closed-testing tester community (12+ members). "
                 "Canonical opt-in list is the E13.5 TesterPool "
                 "(data/play_runtime/tester_pool.json).")


def _cred_candidates() -> List[Path]:
    """Return the list of candidate paths to tester_community.json.

    Resolution order:
      1) ``$LAUNCHFORGE_TESTER_COMMUNITY`` env var (absolute path)
      2) CWD/credentials/tester_community.json
      3) CWD/../credentials/tester_community.json
      4) <module-parent>/launchforge/credentials/tester_community.json
      5) <module-parent>/credentials/tester_community.json
    """
    candidates: List[Path] = []
    env = os.environ.get("LAUNCHFORGE_TESTER_COMMUNITY", "").strip()
    if env:
        candidates.append(Path(env))
    cwd = Path.cwd()
    candidates.append(cwd / "credentials" / "tester_community.json")
    candidates.append(cwd.parent / "credentials" / "tester_community.json")
    here = Path(__file__).resolve()
    candidates.append(here.parents[2] / "credentials" / "tester_community.json")
    candidates.append(here.parents[3] / "credentials" / "tester_community.json")
    return candidates


def cred_path() -> Path:
    """Return the path where tester_community.json SHOULD live.

    The env var ``LAUNCHFORGE_TESTER_COMMUNITY`` (if set to an absolute
    path) ALWAYS wins — this lets tests and operators pin the location
    independently of CWD and the workspace layout. Otherwise we look
    for an existing credentials/ folder that already has
    ``live_accounts.json``, falling back to CWD/credentials.
    """
    env = os.environ.get("LAUNCHFORGE_TESTER_COMMUNITY", "").strip()
    if env:
        return Path(env)
    for p in _cred_candidates()[1:]:
        try:
            if (p.parent.exists()
                    and (p.parent / "live_accounts.json").exists()):
                return p
        except OSError:
            continue
    cwd = Path.cwd()
    cand = cwd / "credentials" / "tester_community.json"
    if cand.parent.exists():
        return cand
    return cwd.parent / "credentials" / "tester_community.json"


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s.strip()))


def _normalize_emails(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values:
        e = v.strip().lower()
        if not e:
            continue
        if not _is_email(e):
            raise ValueError(f"invalid tester email: {v!r}")
        if e in seen:
            continue
        seen.add(e)
        out.append(e)
    return out


def _normalize_groups(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values:
        g = v.strip()
        if not g:
            continue
        if "@" not in g:
            raise ValueError(
                f"invalid Google Group (need @googlegroups.com format): {v!r}")
        if g in seen:
            continue
        seen.add(g)
        out.append(g)
    return out


def empty_config() -> Dict:
    return {"emails": [], "groups": [],
            "note": ("12-person closed-testing tester community. "
                     "Initialized via operation.publishing_factory.tester_community"),
            "configured": False}


def _load_legacy(path: Path) -> Dict:
    """Read the legacy ``credentials/tester_community.json`` (groups + any
    pre-existing emails). Returns an empty config if absent/corrupt."""
    if not path.exists():
        return empty_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return empty_config()
        emails = data.get("emails") or []
        groups = data.get("groups") or []
        return {
            "emails": emails,
            "groups": groups,
            "note": data.get("note", "") or _DEFAULT_NOTE,
            "configured": bool(emails or groups),
        }
    except (OSError, json.JSONDecodeError):
        return empty_config()


def _pool_emails() -> List[str]:
    """Canonical TesterPool emails — the single authoring surface for
    opt-in testers (``tester_pool_cli add``). Merging this IN unifies the
    two email sources so the legacy ``tester_community invite`` flow and
    the E13.5 section-5 board share ONE truth. Returns [] on any failure
    so the legacy file remains a safe fallback."""
    try:
        from operation.publishing_factory.play_runtime.tester_pool_agent \
            import load_pool
        return [t.get("email") for t in load_pool() if t.get("email")]
    except Exception:  # noqa: BLE001 — never break load() on pool issues
        return []


def load() -> Dict:
    """Load tester community config, UNIFIED with the persistent
    TesterPool.

    The E13.5 TesterPoolAgent is the canonical one-time authoring surface
    for opt-in testers (its ``tester_pool_cli add`` is the single writer).
    This function merges the pool's emails IN so a single source of truth
    drives both the legacy ``tester_community invite`` flow and the new
    E13.5 section-5 board. The legacy ``credentials/tester_community.json``
    stays a valid seed/fallback (groups + any pre-existing emails)."""
    legacy = _load_legacy(cred_path())
    pool_emails = _pool_emails()
    if pool_emails:
        emails = sorted(set(pool_emails) | set(legacy.get("emails", [])))
        return {
            "emails": emails,
            "groups": legacy.get("groups", []),
            "note": legacy.get("note") or _DEFAULT_NOTE,
            "configured": bool(emails or legacy.get("groups")),
            "source": "tester_pool+community",
        }
    return legacy


def save(cfg: Dict) -> Path:
    """Persist the config. Validates shape and email/group format.
    Returns the path written."""
    cfg = cfg or {}
    emails = _normalize_emails(cfg.get("emails", []) or [])
    groups = _normalize_groups(cfg.get("groups", []) or [])
    out = {
        "emails": emails,
        "groups": groups,
        "note": cfg.get("note",
                        "Closed-testing tester community (12+ members)."),
        "configured": bool(emails or groups),
    }
    path = cred_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path


def add_emails(values: List[str]) -> Path:
    """Add opt-in tester emails to the CANONICAL TesterPool — the single
    authoring surface for testers. Delegates to ``TesterPoolAgent`` so there
    is exactly one writer; the legacy community file stays a seed/fallback
    only. ``community.load()`` then reflects the pool automatically."""
    from operation.publishing_factory.play_runtime.tester_pool_agent \
        import TesterPoolAgent, pool_path
    agent = TesterPoolAgent()
    for v in values:
        agent.add_tester(v)
    return pool_path()


def add_groups(values: List[str]) -> Path:
    cfg = load()
    cfg["groups"] = _normalize_groups(cfg.get("groups", []) + values)
    return save(cfg)


def status_text(cfg: Optional[Dict] = None) -> str:
    cfg = cfg if cfg is not None else load()
    emails = cfg.get("emails", []) or []
    groups = cfg.get("groups", []) or []
    ok = len(emails) >= _REQUIRED_TESTERS or bool(groups)
    icon = "OK" if ok else "INCOMPLETE"
    lines = [
        f"[{icon}] tester community @ {cred_path()}",
        f"  emails   = {len(emails)} (target: {_REQUIRED_TESTERS}+)"
    ]
    if emails:
        # Show first 3 emails (obfuscated local-part for privacy in CI logs).
        preview = []
        for e in emails[:3]:
            local, _, domain = e.partition("@")
            if len(local) <= 3:
                preview.append(f"{local}@{domain}")
            else:
                preview.append(f"{local[:2]}**@{domain}")
        lines.append(f"    preview = {preview}")
    lines.append(f"  groups   = {len(groups)}")
    if groups:
        lines.append(f"    list    = {groups}")
    if not ok:
        lines.append("")
        lines.append(
            f"  Run:  python -m operation.publishing_factory.tester_community "
            f"add --emails a@gmail.com,b@gmail.com,...  (need {_REQUIRED_TESTERS}+)")
    return "\n".join(lines)


__all__ = [
    "load",
    "save",
    "empty_config",
    "add_emails",
    "add_groups",
    "cred_path",
    "status_text",
    "_REQUIRED_TESTERS",
    "_normalize_emails",
    "_normalize_groups",
]
