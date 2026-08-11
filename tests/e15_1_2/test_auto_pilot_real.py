"""
P3-auto — Real closed-loop auto-pilot tests
===========================================
Proves the auto-pilot execution path actually reaches the REAL Google
Play client (Edits API: open edit -> PUT listing -> commit) with a fake
transport, since the sandbox cannot reach androidpublisher.googleapis.com.

Covers:
  * auto-pilot ON + verified package -> metadata WRITE reaches the client
  * empty / fake package_name -> skipped (no blind app creation)
  * package not owned by this service account -> skipped
  * dry-run -> ownership READ happens, WRITE does NOT
"""
from __future__ import annotations

import os
import tempfile

from monetization.providers.models import SandboxMode

from operation.publishing_factory.batch_orchestrator import (
    BatchGameResult, BatchOrchestrator, BatchReport,
)
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient,
)


# --------------------------------------------------------------------------- #
# fake Google Play real client (subclasses the real one so it inherits
# check_status/update_metadata, but overrides the transport to simulate
# the Edits API round-trip locally — no network needed)
# --------------------------------------------------------------------------- #
class FakeRealClient(GooglePlayRealClient):
    def __init__(self, cred=None, sink=None):
        super().__init__(cred)
        self._sink = sink if sink is not None else []

    def _call_api(self, method, path, body=None):
        self._sink.append((method, path, body))
        if method == "POST" and path.endswith("/edits"):
            return {"success": True, "status_code": 200, "data": {"id": "edit1"}}
        if method == "PUT" and "/listings/" in path:
            return {"success": True, "status_code": 200, "data": {}}
        if method == "POST" and path.endswith(":commit"):
            return {"success": True, "status_code": 200, "data": {}}
        if method == "DELETE" and "/edits/" in path:
            return {"success": True, "status_code": 200, "data": {}}
        # catch-all (e.g. GET tracks/production during check_status)
        return {"success": True, "status_code": 200, "data": {}}


def _fake_factory(sink, deny=False):
    class _F(FakeRealClient):
        def _call_api(self, method, path, body=None):
            self._sink.append((method, path, body))
            if deny and method == "POST" and path.endswith("/edits"):
                return {"success": False, "status_code": 403,
                        "error": 'HTTP 403: {"error": {"message": '
                                 '"The caller does not have permission"}}',
                        "data": None}
            return super()._call_api(method, path, body)
    return lambda cred=None: _F(cred=cred, sink=sink)


def _registry(tmp_path, games):
    path = os.path.join(tmp_path, "catalog.json")
    reg = GameRegistry(path=path)
    for g in games:
        reg.add(g)
    reg.save()
    return reg


def _game(game_id, package_name):
    return GameProduct(
        game_id=game_id, package_name=package_name,
        platforms=["google_play"], genre="merge", status="published")


def _report_with(plan_dict):
    rep = BatchReport(sandbox="production", scanned=1, auto_pilot=True)
    rep.plans.append(BatchGameResult(
        game_id="g1", task_type="ASO_OPPORTUNITY",
        plan=plan_dict, recommended=True, requires_approval=False))
    return rep


REAL_CLIENT_PATH = (
    "operation.publishing.providers.google_play.real_client."
    "GooglePlayRealClient")
GET_GP_PATH = "operation.providers.live.store_keys.get_googleplay"


# --------------------------------------------------------------------------- #
class TestAutoPilotRealWrite:
    def test_metadata_write_reaches_real_client(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "com.born2play.biblequiz")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        rep = _report_with({"aso": {"title": "T", "short_description": "S",
                                    "full_description": "F"}})
        executed = orch._auto_execute(rep, dry_run=False)
        assert executed == 1
        # open edit -> PUT listing -> commit must all have happened
        assert any(p.endswith("/edits") and m == "POST"
                   for (m, p, _b) in sink)
        assert any("listings/en-US" in p and m == "PUT" for (m, p, _b) in sink)
        assert any(p.endswith(":commit") and m == "POST"
                   for (m, p, _b) in sink)


class TestAutoPilotSkips:
    def test_empty_package_skipped(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        rep = _report_with({"aso": {"title": "T"}})
        executed = orch._auto_execute(rep, dry_run=False)
        assert executed == 0
        assert any("no verified package_name" in n for n in rep.notes)
        # no API call should have been made for an empty package
        assert sink == []

    def test_fake_package_skipped(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "com.fake.g1")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        rep = _report_with({"aso": {"title": "T"}})
        executed = orch._auto_execute(rep, dry_run=False)
        assert executed == 0
        assert any("no verified package_name" in n for n in rep.notes)
        assert sink == []

    def test_unowned_package_skipped(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink, deny=True))
        reg = _registry(tmp_path, [_game("g1", "com.other.someone")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        rep = _report_with({"aso": {"title": "T"}})
        executed = orch._auto_execute(rep, dry_run=False)
        assert executed == 0
        assert any("not accessible by this service account" in n
                   for n in rep.notes)
        # only the ownership READ (edit open, which was denied) attempted
        assert any(p.endswith("/edits") for (_m, p, _b) in sink)
        assert not any("listings/en-US" in p for (_m, p, _b) in sink)


class TestAutoPilotDryRun:
    def test_dry_run_reads_but_does_not_write(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "com.born2play.biblequiz")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        rep = _report_with({"aso": {"title": "T", "short_description": "S",
                                    "full_description": "F"}})
        executed = orch._auto_execute(rep, dry_run=True)
        assert executed == 0
        # ownership READ happened (edit open) but NO listing PUT / commit
        assert any(p.endswith("/edits") and m == "POST"
                   for (m, p, _b) in sink)
        assert not any("listings/en-US" in p for (_m, p, _b) in sink)
        assert not any(p.endswith(":commit") for (_m, p, _b) in sink)
        assert any("DRY-RUN" in n for n in rep.notes)


# --------------------------------------------------------------------------- #
# operator-directed single-app push (bypasses the fleet recommendation gate)
# --------------------------------------------------------------------------- #
class TestPushSingle:
    def test_verify_only_no_write(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "com.born2play.biblequiz")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        st = orch.push_single("g1", {}, dry_run=True)
        assert st["ok"] is True
        assert st["stage"] == "verify-only"
        assert st["owned"] is True
        # only the ownership READ (edit open) — no listing PUT / commit
        assert any(p.endswith("/edits") for (_m, p, _b) in sink)
        assert not any("listings/en-US" in p for (_m, p, _b) in sink)

    def test_dry_run_shows_payload_no_write(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "com.born2play.biblequiz")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        meta = {"title": "New Title", "short_description": "New short",
                "full_description": "New full"}
        st = orch.push_single("g1", meta, dry_run=True)
        assert st["ok"] is True
        assert st["stage"] == "dry-run"
        assert st["would_write"] == meta
        # ownership READ happened, but NO listing PUT / commit
        assert any(p.endswith("/edits") and m == "POST"
                   for (m, p, _b) in sink)
        assert not any("listings/en-US" in p for (_m, p, _b) in sink)
        assert not any(p.endswith(":commit") for (_m, p, _b) in sink)

    def test_apply_writes_listing(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "com.born2play.biblequiz")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        meta = {"title": "New Title", "short_description": "New short",
                "full_description": "New full"}
        st = orch.push_single("g1", meta, dry_run=False)
        assert st["ok"] is True
        assert st["stage"] == "written"
        assert st["written"] == meta
        # full Edits API round-trip: open -> PUT listing -> commit
        assert any(p.endswith("/edits") and m == "POST"
                   for (m, p, _b) in sink)
        assert any("listings/en-US" in p and m == "PUT" for (m, p, _b) in sink)
        assert any(p.endswith(":commit") and m == "POST"
                   for (m, p, _b) in sink)

    def test_unowned_refused(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink, deny=True))
        reg = _registry(tmp_path, [_game("g1", "com.other.someone")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        st = orch.push_single("g1", {"title": "T"}, dry_run=False)
        assert st["ok"] is False
        assert st["stage"] == "ownership"
        assert not any("listings/en-US" in p for (_m, p, _b) in sink)

    def test_ownership_failure_surfaces_http_status_and_diagnosis(
            self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink, deny=True))
        reg = _registry(tmp_path, [_game("g1", "com.other.someone")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        st = orch.push_single("g1", {"title": "T"}, dry_run=False)
        assert st["ok"] is False
        assert st["stage"] == "ownership"
        # the real HTTP status code must NOT be swallowed
        assert st.get("http_status") == 403
        # and a concrete next-action diagnosis must be attached
        assert "Users & permissions" in st["diagnosis"]
        assert "does not have permission" in (st.get("error") or "").lower()

    def test_no_package_refused(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        st = orch.push_single("g1", {"title": "T"}, dry_run=False)
        assert st["ok"] is False
        assert st["stage"] == "package"
        assert sink == []

    def test_apply_writes_localized_listing(self, tmp_path, monkeypatch):
        sink = []
        monkeypatch.setattr(GET_GP_PATH, lambda: {"service_account_json": {}})
        monkeypatch.setattr(REAL_CLIENT_PATH, _fake_factory(sink))
        reg = _registry(tmp_path, [_game("g1", "com.born2play.biblequiz")])
        orch = BatchOrchestrator(reg, auto_pilot=True)
        meta = {"title": "Taglish Title", "short_description": "S",
                "full_description": "F"}
        st = orch.push_single("g1", meta, dry_run=False, locale="fil")
        assert st["ok"] is True
        assert st["stage"] == "written"
        # the PUT must target the requested locale, not en-US
        assert any("/listings/fil" in p and m == "PUT"
                   for (m, p, _b) in sink)
        assert not any("/listings/en-US" in p for (_m, p, _b) in sink)
