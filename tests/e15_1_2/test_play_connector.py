"""E13.5 — PlayConnector gate + audit tests (fake client, no network)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from monetization.providers.models import SandboxMode

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.models import (
    BlastRadius, GateStage,
)
from operation.publishing_factory.play_runtime.audit import (
    audit_path, recent,
)


class FakeClient:
    """In-memory stand-in for GooglePlayRealClient."""
    def __init__(self, owned: bool = True):
        self.owned = owned
        self.calls: list = []

    def check_status(self, package_name: str):
        self.calls.append(("check_status", package_name))
        if self.owned:
            return {"success": True, "status": "draft",
                    "play_status": "draft"}
        return {"success": False, "status_code": 404,
                "error": "package not found in account"}

    def update_metadata(self, package_name, metadata, locale="en-US"):
        self.calls.append(("update_metadata", package_name, locale))
        return {"success": True, "detail": f"listing {locale} updated",
                "edit_id": "e1", "locale": locale}

    def invite_testers_to_closed_track(self, package_name,
                                       tester_emails=None,
                                       tester_groups=None, track="closed",
                                       dry_run=True):
        self.calls.append(("invite", package_name, track))
        return {"success": True, "status_code": 200}

    def upload_bundle(self, package_name, build_path, version, build_number):
        self.calls.append(("upload_bundle", package_name))
        return {"success": True, "version_code": build_number}

    def set_rollout(self, package_name, track="production",
                    user_fraction=0.05, version_code=None,
                    release_notes=None):
        self.calls.append(("set_rollout", package_name, track, user_fraction))
        return {"success": True, "detail": f"rollout {user_fraction}"}

    def halt_rollout(self, package_name, track="production"):
        self.calls.append(("halt_rollout", package_name, track))
        return {"success": True, "detail": "halted"}


PKG = "com.ofwsalary.ofwcalculator"
META = {"title": "OFW Sahod Calculator",
        "short_description": "Net pay for OFWs",
        "full_description": "Compute take-home pay."}


def _connector(sandbox, auto_pilot=False, client=None, audit_file=None):
    if audit_file is not None:
        os.environ["LAUNCHFORGE_PLAY_AUDIT"] = str(audit_file)
    return PlayConnector(client=client or FakeClient(),
                         sandbox=sandbox, auto_pilot=auto_pilot)


# --------------------------------------------------------------------- #
# SIMULATION: never calls the API
def test_simulation_never_calls_api(tmp_path):
    c = _connector(SandboxMode.SIMULATION, audit_file=tmp_path / "a.jsonl")
    r = c.update_listing(PKG, META, apply=True)
    assert r.stage == GateStage.RECOMMEND
    assert r.real_api_called is False
    assert c.client.calls == []   # no API hit at all


# --------------------------------------------------------------------- #
# SHADOW: real READ for verify, writes previewed (no mutation)
def test_shadow_preview_no_mutation(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.SHADOW, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.update_listing(PKG, META, apply=True)
    assert r.stage == GateStage.SIMULATE
    # verify READ happened, but update_metadata (mutation) did NOT
    assert ("check_status", PKG) in fc.calls
    assert all(call[0] != "update_metadata" for call in fc.calls)
    assert r.real_api_called is True   # the verify read was real
    assert r.ok is True


# --------------------------------------------------------------------- #
# PRODUCTION + auto_pilot OFF: writes blocked
def test_production_auto_pilot_off_blocks_write(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=False, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.update_listing(PKG, META, apply=True)
    assert r.stage == GateStage.BLOCKED
    assert r.real_api_called is False
    assert fc.calls == []


# --------------------------------------------------------------------- #
# PRODUCTION + auto_pilot ON + apply=False: preview
def test_production_dry_run_preview(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.update_listing(PKG, META, apply=False)
    assert r.stage == GateStage.SIMULATE
    assert ("check_status", PKG) in fc.calls
    assert all(call[0] != "update_metadata" for call in fc.calls)


# --------------------------------------------------------------------- #
# PRODUCTION + auto_pilot ON + apply=True: real write
def test_production_apply_executes_write(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.update_listing(PKG, META, locale="fil", apply=True)
    assert r.stage == GateStage.EXECUTE
    assert r.real_api_called is True
    assert r.ok is True
    assert ("update_metadata", PKG, "fil") in fc.calls


# --------------------------------------------------------------------- #
# RELEASE gate: locked until unlock_release()
def test_release_locked_without_unlock(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.set_rollout(PKG, "production", 0.05, apply=True)
    assert r.stage == GateStage.APPROVE   # not BLOCKED, but locked
    assert r.real_api_called is False
    assert all(call[0] != "set_rollout" for call in fc.calls)


def test_release_unlocks_and_executes(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    c.unlock_release()
    assert c.release_unlocked is True
    r = c.set_rollout(PKG, "production", 0.20, apply=True)
    assert r.stage == GateStage.EXECUTE
    assert r.real_api_called is True
    assert ("set_rollout", PKG, "production", 0.20) in fc.calls


def test_halt_rollout_requires_unlock(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.halt_rollout(PKG, apply=True)
    assert r.stage == GateStage.APPROVE
    c.unlock_release()
    r2 = c.halt_rollout(PKG, apply=True)
    assert r2.stage == GateStage.EXECUTE
    assert ("halt_rollout", PKG, "production") in fc.calls


# --------------------------------------------------------------------- #
# RELEASE dual-factor: when LAUNCHFORGE_RELEASE_UNLOCK is set, the token
# must match exactly (second factor beyond auto-pilot).
def test_release_unlock_refuses_without_token_when_env_set(tmp_path, monkeypatch):
    monkeypatch.setenv("LAUNCHFORGE_RELEASE_UNLOCK", "s3cr3t")
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    # no token supplied -> refuse
    assert c.unlock_release(PKG) is False
    assert c.release_unlocked is False
    r = c.set_rollout(PKG, "production", 0.20, apply=True)
    assert r.stage == GateStage.APPROVE
    assert all(call[0] != "set_rollout" for call in fc.calls)


def test_release_unlock_dual_factor_token_match(tmp_path, monkeypatch):
    monkeypatch.setenv("LAUNCHFORGE_RELEASE_UNLOCK", "s3cr3t")
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    assert c.unlock_release(PKG, token="s3cr3t") is True
    r = c.set_rollout(PKG, "production", 0.20, apply=True)
    assert r.stage == GateStage.EXECUTE
    assert ("set_rollout", PKG, "production", 0.20) in fc.calls


# --------------------------------------------------------------------- #
# RELEASE unlock is package-scoped: unlocking A must not unlock B.
def test_release_unlock_is_package_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("LAUNCHFORGE_RELEASE_UNLOCK", "s3cr3t")
    A, B = "com.a.app", "com.b.app"
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    assert c.unlock_release(A, token="s3cr3t") is True
    # A is unlocked -> EXECUTE
    r_a = c.set_rollout(A, "production", 0.20, apply=True)
    assert r_a.stage == GateStage.EXECUTE
    # B is NOT unlocked -> still APPROVE
    r_b = c.set_rollout(B, "production", 0.20, apply=True)
    assert r_b.stage == GateStage.APPROVE
    assert all(call[1] != B for call in fc.calls if call[0] == "set_rollout")


# --------------------------------------------------------------------- #
# RELEASE unlock refuses when auto-pilot is OFF (first factor missing).
def test_release_unlock_refused_without_auto_pilot(tmp_path, monkeypatch):
    monkeypatch.setenv("LAUNCHFORGE_RELEASE_UNLOCK", "s3cr3t")
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=False, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    assert c.unlock_release(PKG, token="s3cr3t") is False
    r = c.set_rollout(PKG, "production", 0.20, apply=True)
    assert r.stage == GateStage.BLOCKED



# --------------------------------------------------------------------- #
# ownership: non-owned package refused for writes
def test_non_owned_package_refused(tmp_path):
    fc = FakeClient(owned=False)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    c.unlock_release()
    r = c.set_rollout(PKG, "production", 0.05, apply=True)
    assert r.ok is False
    # refused with a concrete ownership diagnosis (404 / not in account)
    assert r.diagnosis and ("404" in r.diagnosis or "账号" in r.diagnosis)
    assert all(call[0] != "set_rollout" for call in fc.calls)


# --------------------------------------------------------------------- #
# check_status is a real READ in every non-simulation mode
def test_check_status_real_read(tmp_path):
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.check_status(PKG)
    assert r.real_api_called is True
    assert r.ok is True
    assert r.data.get("play_status") == "draft"


# --------------------------------------------------------------------- #
# audit log: every routed op is persisted as JSONL
def test_audit_log_written(tmp_path):
    af = tmp_path / "audit.jsonl"
    fc = FakeClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=af)
    c.unlock_release()
    c.update_listing(PKG, META, locale="fil", apply=True)
    c.set_rollout(PKG, "production", 0.1, apply=True)
    c.check_status(PKG)

    assert af.exists()
    lines = [json.loads(l) for l in af.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    assert len(lines) == 3
    ops = {rec["op"] for rec in lines}
    assert "update_listing" in ops and "set_rollout" in ops \
        and "check_status" in ops
    # all persisted records carry the gate stage + blast radius
    for rec in lines:
        assert "stage" in rec and "radius" in rec
    # sanity: recent() reads back
    assert len(recent(limit=10)) == 3
