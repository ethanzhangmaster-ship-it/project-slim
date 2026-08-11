"""E13.5 — Play Runtime connector (the spine).

A single facade over ``GooglePlayRealClient`` that EVERY downstream Play
agent (Release / Health / ASO / Review / Economy) inherits. It owns the
three-tier execution gate so the policy is enforced in exactly one place:

    RECOMMEND  (SIMULATION)  -> propose only, NO API call
    SIMULATE   (SHADOW)      -> real READ for verification, writes previewed
    APPROVE    (PRODUCTION)  -> auto-pilot on, RELEASE needs explicit unlock
    EXECUTE    (PRODUCTION)  -> real write happened
    BLOCKED                    -> refused by a safety lock, no API call

Hard locks (non-bypassable):
  * SIMULATION never calls the API (real_api_called=False always).
  * SHADOW never mutates (writes are previewed, no PUT/POST that changes
    console state).
  * Anything above READ needs the auto-pilot gate (LAUNCHFORGE_AUTO_PUBLISH).
  * RELEASE (rollout / halt) additionally needs unlock_release().
  * Every write is preceded by an ownership READ; non-owned packages are
    refused (no blind app creation, no cross-account writes).

Lean rule: pure Python, JSONL audit log, deterministic, no LLM.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from monetization.providers.models import SandboxMode

from operation.publishing_factory.auto_pilot import auto_pilot_enabled
from operation.publishing_factory.play_runtime.audit import append as audit_append
from operation.publishing_factory.play_runtime.models import (
    BlastRadius, GateStage, PlayResult,
)
from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient, load_default_real_client,
)

# Localized ownership diagnosis (kept here so the connector is the single
# owner of the policy; batch_orchestrator imports this same helper).
from operation.publishing_factory.batch_orchestrator import _diagnose_ownership


def _as_sandbox(mode) -> SandboxMode:
    if isinstance(mode, SandboxMode):
        return mode
    try:
        return SandboxMode(mode)
    except ValueError:
        return SandboxMode.SIMULATION


class PlayConnector:
    """Unified, gated facade for all Google Play console operations."""

    def __init__(self,
                 client: Optional[GooglePlayRealClient] = None,
                 sandbox: Any = SandboxMode.SIMULATION,
                 auto_pilot: Optional[bool] = None):
        self.sandbox = _as_sandbox(sandbox)
        self.auto_pilot = (auto_pilot if auto_pilot is not None
                           else auto_pilot_enabled())
        # RELEASE operations stay locked until an explicit unlock call.
        # Two layers: a legacy global flag (used when no token is configured)
        # and a package-scoped set (the hardened, dual-factor path).
        self._release_unlocked = False
        self._release_unlocked_for: set = set()
        self._ownership_cache: Dict[str, bool] = {}
        if client is not None:
            self.client = client
        elif self.sandbox == SandboxMode.PRODUCTION:
            self.client = load_default_real_client()
        else:
            # SIM/SHADOW: a client is only needed if a real READ is made
            # (SHADOW). Tests inject a fake; production SHADOW loads real.
            self.client = load_default_real_client() if self.auto_pilot else None

    # ------------------------------------------------------------------ #
    # release unlock (the Approval door for RELEASE-radius ops)
    def unlock_release(self, package_name: Optional[str] = None,
                       *, token: Optional[str] = None) -> bool:
        """Dual-factor, package-scoped RELEASE unlock.

        Returns ``True`` (and records the unlock) only when BOTH factors hold:
          (1) auto-pilot is enabled (``LAUNCHFORGE_AUTO_PUBLISH=1``), AND
          (2) if ``LAUNCHFORGE_RELEASE_UNLOCK`` is set in the environment,
              the supplied ``token`` MUST match it exactly (second factor).

        If the env token is NOT configured, this falls back to the legacy
        behaviour (a global unlock triggered by an explicit ``--apply``), so
        existing automation and tests keep working without a shared secret.

        The unlock is package-scoped when ``package_name`` is supplied;
        otherwise it unlocks every package for this connector instance.
        NEVER call this automatically — only on an explicit human ``--apply``.
        """
        if not self.auto_pilot:
            return False
        expected = os.environ.get("LAUNCHFORGE_RELEASE_UNLOCK")
        if expected and token != expected:
            return False
        if package_name:
            self._release_unlocked_for.add(package_name)
        else:
            self._release_unlocked = True
        return True

    @property
    def release_unlocked(self) -> bool:
        return self._release_unlocked or bool(self._release_unlocked_for)

    # ------------------------------------------------------------------ #
    # gate decision
    def _decide(self, radius: BlastRadius, *, apply: bool = False,
                package_name: Optional[str] = None) -> GateStage:
        if self.sandbox == SandboxMode.SIMULATION:
            return GateStage.RECOMMEND
        if radius == BlastRadius.READ:
            # reads are always permitted (real in SHADOW/PROD)
            return (GateStage.SIMULATE if self.sandbox == SandboxMode.SHADOW
                    else GateStage.EXECUTE)
        if self.sandbox == SandboxMode.SHADOW:
            # real READ allowed, no mutation -> preview only
            return GateStage.SIMULATE
        # PRODUCTION writes
        if not self.auto_pilot:
            return GateStage.BLOCKED
        if radius == BlastRadius.RELEASE and not self._is_release_unlocked(package_name):
            return GateStage.APPROVE
        if not apply:
            return GateStage.SIMULATE
        return GateStage.EXECUTE

    def _is_release_unlocked(self, package_name: Optional[str]) -> bool:
        """True if RELEASE writes are permitted for ``package_name``."""
        if self._release_unlocked:
            return True  # legacy global unlock (env token not configured)
        if package_name is not None and package_name in self._release_unlocked_for:
            return True
        return False

    # ------------------------------------------------------------------ #
    # ownership verification (real READ, cached for the session)
    def _verify_ownership(self, package_name: str):
        if package_name in self._ownership_cache:
            owned = self._ownership_cache[package_name]
            return owned, None, None, ""
        res = self.client.check_status(package_name)
        owned = bool(res.get("success"))
        sc = res.get("status_code")
        err = res.get("error") or ""
        diag = _diagnose_ownership(sc, err) if not owned else ""
        self._ownership_cache[package_name] = owned
        return owned, sc, err, diag

    def _emit(self, result: PlayResult) -> PlayResult:
        audit_append(result)
        return result

    # ------------------------------------------------------------------ #
    # READ: status / ownership
    def check_status(self, package_name: str) -> PlayResult:
        stage = self._decide(BlastRadius.READ)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="check_status", package_name=package_name,
                radius=BlastRadius.READ, stage=GateStage.RECOMMEND,
                real_api_called=False, ok=True,
                detail="simulated: would read console status"))
        res = self.client.check_status(package_name)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="check_status", package_name=package_name,
            radius=BlastRadius.READ, stage=stage,
            real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("status", "unknown") if ok else (res.get("error") or ""),
            diagnosis="" if ok else _diagnose_ownership(
                res.get("status_code"), res.get("error") or ""),
            data={"play_status": res.get("status"),
                  "version": res.get("version")}))

    # ------------------------------------------------------------------ #
    # METADATA: listing text (title/short/full) for a locale
    def update_listing(self, package_name: str,
                       meta: Dict[str, str],
                       locale: str = "en-US",
                       *, apply: bool = False) -> PlayResult:
        radius = BlastRadius.METADATA
        stage = self._decide(radius, apply=apply)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="update_listing", package_name=package_name, radius=radius,
                stage=GateStage.RECOMMEND, real_api_called=False, ok=True,
                detail="proposed listing update (simulation)"))
        if stage == GateStage.BLOCKED:
            return self._emit(PlayResult(
                op="update_listing", package_name=package_name, radius=radius,
                stage=GateStage.BLOCKED, real_api_called=False, ok=False,
                detail="blocked: auto-pilot disabled or sim mode (no write)"))
        # SHADOW preview or PROD dry-run: verify ownership, preview write
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="update_listing", package_name=package_name, radius=radius,
                stage=GateStage.SIMULATE,
                real_api_called=owned,  # the verify READ was real
                ok=owned, http_status=sc,
                detail=("would update listing" if owned
                        else "ownership verify failed"),
                diagnosis=diag,
                data={"would_write": meta, "locale": locale}))
        # EXECUTE
        owned, sc, err, diag = self._verify_ownership(package_name)
        if not owned:
            return self._emit(PlayResult(
                op="update_listing", package_name=package_name, radius=radius,
                stage=GateStage.EXECUTE, real_api_called=True, ok=False,
                http_status=sc, error=err, diagnosis=diag,
                detail="ownership verify failed; refusing write"))
        upd = self.client.update_metadata(package_name, meta, locale)
        ok = bool(upd.get("success"))
        return self._emit(PlayResult(
            op="update_listing", package_name=package_name, radius=radius,
            stage=GateStage.EXECUTE, real_api_called=True, ok=ok,
            http_status=upd.get("status_code"),
            detail=upd.get("detail") or upd.get("error") or "",
            data={"locale": locale, "edit_id": upd.get("edit_id")}))

    # ------------------------------------------------------------------ #
    # TESTERS: invite to closed track
    def invite_testers(self, package_name: str,
                       tester_emails: Optional[List[str]] = None,
                       tester_groups: Optional[List[str]] = None,
                       *, apply: bool = False) -> PlayResult:
        radius = BlastRadius.TESTERS
        stage = self._decide(radius, apply=apply)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="invite_testers", package_name=package_name, radius=radius,
                stage=GateStage.RECOMMEND, real_api_called=False, ok=True,
                detail="proposed tester invite (simulation)"))
        if stage == GateStage.BLOCKED:
            return self._emit(PlayResult(
                op="invite_testers", package_name=package_name, radius=radius,
                stage=GateStage.BLOCKED, real_api_called=False, ok=False,
                detail="blocked: auto-pilot disabled or sim mode"))
        emails = [e for e in (tester_emails or []) if e]
        groups = [g for g in (tester_groups or []) if g]
        if not emails and not groups:
            return self._emit(PlayResult(
                op="invite_testers", package_name=package_name, radius=radius,
                stage=GateStage.BLOCKED, real_api_called=False, ok=False,
                detail="no testers supplied (emails/groups both empty)"))
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="invite_testers", package_name=package_name, radius=radius,
                stage=GateStage.SIMULATE, real_api_called=owned,
                ok=owned, http_status=sc, diagnosis=diag,
                detail=("would invite testers" if owned
                        else "ownership verify failed"),
                data={"would_invite_emails": emails,
                      "would_invite_groups": groups}))
        # EXECUTE
        owned, sc, err, diag = self._verify_ownership(package_name)
        if not owned:
            return self._emit(PlayResult(
                op="invite_testers", package_name=package_name, radius=radius,
                stage=GateStage.EXECUTE, real_api_called=True, ok=False,
                http_status=sc, error=err, diagnosis=diag,
                detail="ownership verify failed; refusing invite"))
        res = self.client.invite_testers_to_closed_track(
            package_name=package_name, tester_emails=emails,
            tester_groups=groups, track="closed", dry_run=False)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="invite_testers", package_name=package_name, radius=radius,
            stage=GateStage.EXECUTE, real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("detail") or res.get("error") or "",
            data={"tester_count": len(emails), "group_count": len(groups)}))

    # ------------------------------------------------------------------ #
    # TESTERS: read current testers (READ radius, never writes)
    def read_testers(self, package_name: str,
                     track: str = "closed") -> PlayResult:
        radius = BlastRadius.READ
        stage = self._decide(radius, apply=False)  # READ never writes
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="read_testers", package_name=package_name, radius=radius,
                stage=GateStage.RECOMMEND, real_api_called=False, ok=True,
                detail="proposed tester read (simulation)"))
        if stage == GateStage.BLOCKED:
            return self._emit(PlayResult(
                op="read_testers", package_name=package_name, radius=radius,
                stage=GateStage.BLOCKED, real_api_called=False, ok=False,
                detail="blocked: sim mode"))
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="read_testers", package_name=package_name, radius=radius,
                stage=GateStage.SIMULATE, real_api_called=False, ok=owned,
                http_status=sc, diagnosis=diag,
                detail=("would read testers" if owned
                        else "ownership verify failed"),
                data={}))
        # EXECUTE — actually read (READ radius still never writes).
        res = self.client.get_testers(package_name, track=track)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="read_testers", package_name=package_name, radius=radius,
            stage=GateStage.EXECUTE, real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("detail") or res.get("error") or "",
            data={"tester_emails": res.get("tester_emails", []),
                  "groups": res.get("groups", [])}))

    # ------------------------------------------------------------------ #
    # BINARY: upload AAB (needs a real build artifact on disk)
    def upload_bundle(self, package_name: str, build_path: str,
                      version: str, build_number: int,
                      *, apply: bool = False) -> PlayResult:
        radius = BlastRadius.BINARY
        stage = self._decide(radius, apply=apply)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="upload_bundle", package_name=package_name, radius=radius,
                stage=GateStage.RECOMMEND, real_api_called=False, ok=True,
                detail="proposed AAB upload (simulation)"))
        if stage == GateStage.BLOCKED:
            return self._emit(PlayResult(
                op="upload_bundle", package_name=package_name, radius=radius,
                stage=GateStage.BLOCKED, real_api_called=False, ok=False,
                detail="blocked: auto-pilot disabled or sim mode"))
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="upload_bundle", package_name=package_name, radius=radius,
                stage=GateStage.SIMULATE, real_api_called=owned,
                ok=owned, http_status=sc, diagnosis=diag,
                detail=("would upload AAB" if owned
                        else "ownership verify failed"),
                data={"build_path": build_path, "version": version}))
        owned, sc, err, diag = self._verify_ownership(package_name)
        if not owned:
            return self._emit(PlayResult(
                op="upload_bundle", package_name=package_name, radius=radius,
                stage=GateStage.EXECUTE, real_api_called=True, ok=False,
                http_status=sc, error=err, diagnosis=diag,
                detail="ownership verify failed; refusing upload"))
        res = self.client.upload_bundle(
            package_name, build_path, version, build_number)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="upload_bundle", package_name=package_name, radius=radius,
            stage=GateStage.EXECUTE, real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("detail") or res.get("error") or "",
            data={"version_code": res.get("version_code")}))

    # ------------------------------------------------------------------ #
    # RELEASE: rollout control (hard-gated, needs unlock_release)
    def set_rollout(self, package_name: str, track: str = "production",
                    user_fraction: float = 0.05, *,
                    version_code: Optional[int] = None,
                    release_notes: Optional[Dict[str, str]] = None,
                    apply: bool = False) -> PlayResult:
        radius = BlastRadius.RELEASE
        stage = self._decide(radius, apply=apply, package_name=package_name)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="set_rollout", package_name=package_name, radius=radius,
                stage=GateStage.RECOMMEND, real_api_called=False, ok=True,
                detail=f"proposed rollout {int(user_fraction*100)}% (simulation)"))
        if stage in (GateStage.BLOCKED, GateStage.APPROVE):
            reason = ("auto-pilot disabled or sim mode"
                      if stage == GateStage.BLOCKED
                      else "release locked: call unlock_release() first")
            return self._emit(PlayResult(
                op="set_rollout", package_name=package_name, radius=radius,
                stage=stage, real_api_called=False, ok=False,
                detail=reason))
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="set_rollout", package_name=package_name, radius=radius,
                stage=GateStage.SIMULATE, real_api_called=owned,
                ok=owned, http_status=sc, diagnosis=diag,
                detail=("would rollout %d%%" % int(user_fraction * 100)
                        if owned else "ownership verify failed"),
                data={"track": track, "user_fraction": user_fraction}))
        # EXECUTE (unlocked)
        owned, sc, err, diag = self._verify_ownership(package_name)
        if not owned:
            return self._emit(PlayResult(
                op="set_rollout", package_name=package_name, radius=radius,
                stage=GateStage.EXECUTE, real_api_called=True, ok=False,
                http_status=sc, error=err, diagnosis=diag,
                detail="ownership verify failed; refusing rollout"))
        res = self.client.set_rollout(
            package_name, track=track, user_fraction=user_fraction,
            version_code=version_code, release_notes=release_notes)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="set_rollout", package_name=package_name, radius=radius,
            stage=GateStage.EXECUTE, real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("detail") or res.get("error") or "",
            data={"track": track, "user_fraction": user_fraction}))

    # ------------------------------------------------------------------ #
    # READ: current rollout state of a track (no mutation)
    def get_track_status(self, package_name: str,
                         track: str = "production") -> PlayResult:
        stage = self._decide(BlastRadius.READ)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="get_track_status", package_name=package_name,
                radius=BlastRadius.READ, stage=GateStage.RECOMMEND,
                real_api_called=False, ok=True,
                detail="simulated: would read track status"))
        res = self.client.get_track_status(package_name, track=track)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="get_track_status", package_name=package_name,
            radius=BlastRadius.READ, stage=stage,
            real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("status") if ok else (res.get("error") or ""),
            data={"track": track,
                  "user_fraction": res.get("user_fraction"),
                  "version_code": res.get("version_code"),
                  "status": res.get("status")}))

    # ------------------------------------------------------------------ #
    # READ: Vitals (crash / ANR rates) — Play Developer Reporting API
    def read_vitals(self, package_name: str,
                    window_days: int = 7) -> PlayResult:
        """READ the app's Vitals (crash / ANR rates). READ radius, so it is
        permitted in SHADOW/PRODUCTION without any unlock, and never mutates
        console state. In SIMULATION it returns a simulated (None) payload."""
        stage = self._decide(BlastRadius.READ)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="read_vitals", package_name=package_name,
                radius=BlastRadius.READ, stage=GateStage.RECOMMEND,
                real_api_called=False, ok=True,
                detail="simulated: would read Vitals"))
        if self.client is None:
            return self._emit(PlayResult(
                op="read_vitals", package_name=package_name,
                radius=BlastRadius.READ, stage=stage,
                real_api_called=False, ok=False,
                detail="no client wired (sim/sandbox without credentials)"))
        res = self.client.get_vitals(package_name, window_days=window_days)
        ok = "crash_rate" in res or "anr_rate" in res
        return self._emit(PlayResult(
            op="read_vitals", package_name=package_name,
            radius=BlastRadius.READ, stage=stage,
            real_api_called=True, ok=ok,
            detail="vitals read",
            data={"crash_rate": res.get("crash_rate"),
                  "anr_rate": res.get("anr_rate"),
                  "d1_retention": res.get("d1_retention"),
                  "source": res.get("source")}))

    def halt_rollout(self, package_name: str, track: str = "production",
                     *, apply: bool = False) -> PlayResult:
        radius = BlastRadius.RELEASE
        stage = self._decide(radius, apply=apply, package_name=package_name)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="halt_rollout", package_name=package_name, radius=radius,
                stage=GateStage.RECOMMEND, real_api_called=False, ok=True,
                detail="proposed halt (simulation)"))
        if stage in (GateStage.BLOCKED, GateStage.APPROVE):
            reason = ("auto-pilot disabled or sim mode"
                      if stage == GateStage.BLOCKED
                      else "release locked: call unlock_release() first")
            return self._emit(PlayResult(
                op="halt_rollout", package_name=package_name, radius=radius,
                stage=stage, real_api_called=False, ok=False,
                detail=reason))
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="halt_rollout", package_name=package_name, radius=radius,
                stage=GateStage.SIMULATE, real_api_called=owned,
                ok=owned, http_status=sc, diagnosis=diag,
                detail=("would halt rollout" if owned
                        else "ownership verify failed"),
                data={"track": track}))
        owned, sc, err, diag = self._verify_ownership(package_name)
        if not owned:
            return self._emit(PlayResult(
                op="halt_rollout", package_name=package_name, radius=radius,
                stage=GateStage.EXECUTE, real_api_called=True, ok=False,
                http_status=sc, error=err, diagnosis=diag,
                detail="ownership verify failed; refusing halt"))
        res = self.client.halt_rollout(package_name, track=track)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="halt_rollout", package_name=package_name, radius=radius,
            stage=GateStage.EXECUTE, real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("detail") or res.get("error") or "",
            data={"track": track}))

    # ------------------------------------------------------------------ #
    # READ: user reviews (reviews.list) — READ radius, never mutates
    def read_reviews(self, package_name: str,
                     max_results: int = 100) -> PlayResult:
        """READ the latest user reviews for ``package_name``. READ radius, so
        it is permitted in SHADOW/PRODUCTION without any unlock and never
        mutates console state. In SIMULATION it returns a simulated payload.
        """
        stage = self._decide(BlastRadius.READ)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="read_reviews", package_name=package_name,
                radius=BlastRadius.READ, stage=GateStage.RECOMMEND,
                real_api_called=False, ok=True,
                detail="simulated: would read reviews"))
        if self.client is None:
            return self._emit(PlayResult(
                op="read_reviews", package_name=package_name,
                radius=BlastRadius.READ, stage=stage,
                real_api_called=False, ok=False,
                detail="no client wired (sim/sandbox without credentials)"))
        res = self.client.get_reviews(package_name, max_results=max_results)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="read_reviews", package_name=package_name,
            radius=BlastRadius.READ, stage=stage,
            real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("error") or "reviews read",
            data={"count": res.get("count", 0),
                  "reviews": res.get("reviews", []),
                  "token": res.get("token"),
                  "source": res.get("source")}))

    # ------------------------------------------------------------------ #
    # METADATA: reply to a single review (reviews.reply) — lowest write
    def reply_review(self, package_name: str, review_id: str,
                     reply_text: str, *, apply: bool = False) -> PlayResult:
        """Reply to one user review. METADATA radius (lowest-blast-radius
        write — only the developer reply text on a single review changes).

        Three-tier gate: SIMULATE proposes, SHADOW previews after verifying
        ownership, PRODUCTION writes only with auto-pilot + ``apply=True`` and
        only to a package this service account owns (no cross-account writes).
        """
        radius = BlastRadius.METADATA
        stage = self._decide(radius, apply=apply)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="reply_review", package_name=package_name,
                radius=radius, stage=GateStage.RECOMMEND,
                real_api_called=False, ok=True,
                detail="proposed review reply (simulation)",
                data={"review_id": review_id, "reply_text": reply_text}))
        if stage == GateStage.BLOCKED:
            return self._emit(PlayResult(
                op="reply_review", package_name=package_name,
                radius=radius, stage=GateStage.BLOCKED,
                real_api_called=False, ok=False,
                detail="blocked: auto-pilot disabled or sim mode (no write)"))
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="reply_review", package_name=package_name,
                radius=radius, stage=GateStage.SIMULATE,
                real_api_called=owned, ok=owned, http_status=sc,
                diagnosis=diag,
                detail=("would reply to review" if owned
                        else "ownership verify failed"),
                data={"review_id": review_id, "reply_text": reply_text}))
        # EXECUTE
        owned, sc, err, diag = self._verify_ownership(package_name)
        if not owned:
            return self._emit(PlayResult(
                op="reply_review", package_name=package_name,
                radius=radius, stage=GateStage.EXECUTE,
                real_api_called=True, ok=False, http_status=sc,
                error=err, diagnosis=diag,
                detail="ownership verify failed; refusing reply"))
        res = self.client.reply_to_review(package_name, review_id, reply_text)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="reply_review", package_name=package_name,
            radius=radius, stage=GateStage.EXECUTE,
            real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("detail") or res.get("error") or "",
            data={"review_id": review_id, "reply_text": reply_text,
                  "result": res.get("result")}))

    # ------------------------------------------------------------------ #
    # READ: listing experiments (edits.experiments) — READ radius
    def read_experiments(self, package_name: str) -> PlayResult:
        """READ the store-listing experiments for ``package_name``. READ
        radius, so it is permitted in SHADOW/PRODUCTION without any unlock
        and never mutates console state. In SIMULATION it returns a
        simulated (empty) payload.
        """
        stage = self._decide(BlastRadius.READ)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="read_experiments", package_name=package_name,
                radius=BlastRadius.READ, stage=GateStage.RECOMMEND,
                real_api_called=False, ok=True,
                detail="simulated: would list experiments"))
        if self.client is None:
            return self._emit(PlayResult(
                op="read_experiments", package_name=package_name,
                radius=BlastRadius.READ, stage=stage,
                real_api_called=False, ok=False,
                detail="no client wired (sim/sandbox without credentials)"))
        res = self.client.list_experiments(package_name)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="read_experiments", package_name=package_name,
            radius=BlastRadius.READ, stage=stage,
            real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("error") or "experiments read",
            data={"count": res.get("count", 0),
                  "experiments": res.get("experiments", []),
                  "source": res.get("source")}))

    # ------------------------------------------------------------------ #
    # METADATA: create a listing A/B experiment (edits.experiments)
    def create_experiment(self, package_name: str, *, name: str,
                          locale: str = "en-US",
                          variant_title: Optional[str] = None,
                          variant_short: Optional[str] = None,
                          variant_full: Optional[str] = None,
                          baseline_title: Optional[str] = None,
                          baseline_short: Optional[str] = None,
                          baseline_full: Optional[str] = None,
                          user_fraction: float = 0.1,
                          start_date: Optional[Dict[str, int]] = None,
                          end_date: Optional[Dict[str, int]] = None,
                          apply: bool = False) -> PlayResult:
        """Create a store-listing A/B experiment. METADATA radius (lowest-
        blast-radius write — it only schedules a test comparing two listings;
        the live listing is untouched until a winner is later promoted).

        Three-tier gate: SIMULATE proposes, SHADOW previews after verifying
        ownership, PRODUCTION writes only with auto-pilot + ``apply=True`` and
        only to a package this service account owns (no cross-account writes).
        """
        radius = BlastRadius.METADATA
        stage = self._decide(radius, apply=apply)
        if stage == GateStage.RECOMMEND:
            return self._emit(PlayResult(
                op="create_experiment", package_name=package_name,
                radius=radius, stage=GateStage.RECOMMEND,
                real_api_called=False, ok=True,
                detail="proposed listing experiment (simulation)",
                data={"name": name, "locale": locale,
                      "variant_title": variant_title,
                      "user_fraction": user_fraction}))
        if stage == GateStage.BLOCKED:
            return self._emit(PlayResult(
                op="create_experiment", package_name=package_name,
                radius=radius, stage=GateStage.BLOCKED,
                real_api_called=False, ok=False,
                detail="blocked: auto-pilot disabled or sim mode (no write)"))
        if stage == GateStage.SIMULATE:
            owned, sc, err, diag = self._verify_ownership(package_name)
            return self._emit(PlayResult(
                op="create_experiment", package_name=package_name,
                radius=radius, stage=GateStage.SIMULATE,
                real_api_called=owned, ok=owned, http_status=sc,
                diagnosis=diag,
                detail=("would create experiment" if owned
                        else "ownership verify failed"),
                data={"name": name, "locale": locale,
                      "variant_title": variant_title}))
        # EXECUTE
        owned, sc, err, diag = self._verify_ownership(package_name)
        if not owned:
            return self._emit(PlayResult(
                op="create_experiment", package_name=package_name,
                radius=radius, stage=GateStage.EXECUTE,
                real_api_called=True, ok=False, http_status=sc,
                error=err, diagnosis=diag,
                detail="ownership verify failed; refusing experiment"))
        res = self.client.create_listing_experiment(
            package_name, name=name, locale=locale,
            variant_title=variant_title, variant_short=variant_short,
            variant_full=variant_full, baseline_title=baseline_title,
            baseline_short=baseline_short, baseline_full=baseline_full,
            user_fraction=user_fraction, start_date=start_date,
            end_date=end_date)
        ok = bool(res.get("success"))
        return self._emit(PlayResult(
            op="create_experiment", package_name=package_name,
            radius=radius, stage=GateStage.EXECUTE,
            real_api_called=True, ok=ok,
            http_status=res.get("status_code"),
            detail=res.get("detail") or res.get("error") or "",
            data={"experiment_id": res.get("experiment_id"),
                  "name": res.get("name"),
                  "locale": res.get("locale")}))


__all__ = ["PlayConnector"]
