"""
P5 — Closed-testing tester community tests.

Verifies:
  * community.json round-trip: load/save/add/normalize
  * eligibility clock: days_running/days_remaining/production_ready
  * inviter reaches the real client (FakeRealClient subclass) and
    correctly distinguishes dry-run vs apply.
  * CLI subcommands surface a single ASCII-safe status line.
  * Missing-config and empty-list short-circuits are explicit.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient,
)
from operation.publishing_factory.tester_community import (
    community, eligibility, inviter,
)


# --------------------------------------------------------------------------- #
# fake Google Play real client for inviter dry/apply E2E
# --------------------------------------------------------------------------- #
class FakeRealClient(GooglePlayRealClient):
    def __init__(self, cred=None, sink=None):
        super().__init__(cred)
        self._sink = sink if sink is not None else []

    def _call_api(self, method, path, body=None):
        self._sink.append((method, path, body))
        if method == "POST" and path.endswith("/edits"):
            return {"success": True, "status_code": 200,
                    "data": {"id": "edit_test"}}
        if method == "PUT" and "/testers/" in path:
            return {"success": True, "status_code": 200, "data": {}}
        if method == "POST" and path.endswith(":commit"):
            return {"success": True, "status_code": 200, "data": {}}
        if method == "DELETE" and "/edits/" in path:
            return {"success": True, "status_code": 200, "data": {}}
        return {"success": True, "status_code": 200, "data": {}}


@pytest.fixture
def tmp_cred(monkeypatch, tmp_path):
    """Point LAUNCHFORGE_TESTER_COMMUNITY / _PROGRESS / _POOL at tmp files
    so the unified load() reads the pool from tmp, never the real repo."""
    cred_file = tmp_path / "tester_community.json"
    progress_file = tmp_path / "tester_progress.json"
    pool_file = tmp_path / "tester_pool.json"
    monkeypatch.setenv("LAUNCHFORGE_TESTER_COMMUNITY", str(cred_file))
    monkeypatch.setenv("LAUNCHFORGE_TESTER_PROGRESS", str(progress_file))
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_POOL", str(pool_file))
    yield cred_file, progress_file


class TestCommunityCRUD:
    def test_save_load_roundtrip(self, tmp_cred):
        cred_file, _ = tmp_cred
        cfg = community.empty_config()
        cfg["emails"] = [f"user{i}@gmail.com" for i in range(12)]
        cfg["groups"] = ["ofw-testers@googlegroups.com"]
        community.save(cfg)
        loaded = community.load()
        assert len(loaded["emails"]) == 12
        assert loaded["groups"] == ["ofw-testers@googlegroups.com"]
        assert loaded["configured"] is True

    def test_normalize_emails_lowercases_and_dedupes(self):
        out = community._normalize_emails([
            "Alice@Gmail.com", " alice@gmail.com ", "bob@gmail.com"])
        assert out == ["alice@gmail.com", "bob@gmail.com"]

    def test_normalize_emails_rejects_garbage(self):
        with pytest.raises(ValueError):
            community._normalize_emails(["not-an-email", "ok@gmail.com"])

    def test_normalize_groups_requires_at_sign(self):
        with pytest.raises(ValueError):
            community._normalize_groups(["no-at-sign"])

    def test_add_emails_appends(self, tmp_cred):
        cfg = community.empty_config()
        cfg["emails"] = [f"u{i}@gmail.com" for i in range(10)]
        community.save(cfg)
        community.add_emails(["v1@gmail.com", "v2@gmail.com"])
        loaded = community.load()
        assert len(loaded["emails"]) == 12
        assert loaded["configured"] is True

    def test_status_text_marks_incomplete_below_12(self, tmp_cred):
        cfg = community.empty_config()
        cfg["emails"] = [f"u{i}@gmail.com" for i in range(5)]
        community.save(cfg)
        text = community.status_text()
        assert "INCOMPLETE" in text
        assert "5" in text  # email count shown


class TestEligibility:
    def test_default_state(self, tmp_cred):
        st = eligibility.get("com.example.app")
        assert st["tester_count"] == 0
        assert st["days_running"] == 0
        assert st["days_remaining"] == eligibility.REQUIRED_DAYS
        assert st["production_ready"] is False
        assert st["invited_at"] is None

    def test_record_invitation_starts_clock_at_12(self, tmp_cred):
        eligibility.record_invitation("com.example.app", 10,
                                       today_iso="2026-07-01")
        st = eligibility.get("com.example.app", today_iso="2026-07-01")
        assert st["tester_count"] == 10
        assert st["invited_at"] is None  # under 12 -> no clock

        eligibility.record_invitation("com.example.app", 12,
                                       today_iso="2026-07-01")
        st = eligibility.get("com.example.app", today_iso="2026-07-01")
        assert st["invited_at"] == "2026-07-01"
        assert st["days_running"] == 0
        assert st["days_remaining"] == 14

    def test_clock_advances_after_14_days(self, tmp_cred):
        eligibility.record_invitation("com.example.app", 12,
                                       today_iso="2026-07-01")
        st = eligibility.get("com.example.app", today_iso="2026-07-01")
        # Override clock reading: we just verify days_running is computed
        # by subtracting today from invited_at; inject a fake "today" by
        # setting invited_at 14 days in the past:
        from operation.publishing_factory.tester_community import eligibility as el
        all_state = el.load_all()
        all_state["com.example.app"]["invited_at"] = "2025-01-01"
        el.save_all(all_state)
        st = el.get("com.example.app", today_iso="2026-07-15")
        assert st["days_running"] >= 365  # ~1.5 years
        assert st["days_remaining"] == 0
        assert st["production_ready"] is True

    def test_render_markdown_handles_empty(self, tmp_cred):
        md = eligibility.render_markdown([])
        assert "no apps tracked" in md
        assert "5️⃣" in md  # heading number


class TestInviter:
    def test_dry_run_does_not_call_api(self, tmp_cred):
        cred_file, _ = tmp_cred
        cfg = community.empty_config()
        cfg["emails"] = [f"u{i}@gmail.com" for i in range(12)]
        community.save(cfg)
        sink = []
        client = FakeRealClient(sink=sink)
        result = inviter.invite("com.example.app", apply=False,
                                 client=client)
        assert result["ok"] is True
        assert result["stage"] == "dry-run"
        assert sink == []  # zero API calls
        assert result["tester_count"] == 12

    def test_apply_calls_api_in_order_and_records_eligibility(self, tmp_cred):
        cred_file, progress_file = tmp_cred
        cfg = community.empty_config()
        cfg["emails"] = [f"u{i}@gmail.com" for i in range(12)]
        community.save(cfg)
        sink = []
        client = FakeRealClient(sink=sink)
        result = inviter.invite("com.example.app", apply=True,
                                 client=client)
        assert result["ok"] is True
        assert result["stage"] == "invite-sent"
        assert result["tester_count"] == 12
        # Edits API sequence: POST /edits (open) -> PUT /testers/closed ->
        # POST :commit. We should see exactly those three calls (plus
        # possibly a DELETE on failure-path, but no failure here).
        methods = [m for (m, _, _) in sink]
        assert "POST" in methods and "PUT" in methods
        # Check the closed track PUT was addressed
        testers_put = [p for (m, p, _) in sink
                        if m == "PUT" and "/testers/closed" in p]
        assert testers_put, "expected PUT .../testers/closed"
        # Eligibility state should now have tester_count=12 and invited_at
        st = eligibility.get("com.example.app")
        assert st["tester_count"] == 12
        assert st["invited_at"]  # not None

    def test_missing_config_short_circuits(self, tmp_cred):
        result = inviter.invite("com.example.app", apply=True)
        assert result["ok"] is False
        assert result["stage"] == "config-missing"

    def test_override_emails_bypass_community(self, tmp_cred):
        sink = []
        client = FakeRealClient(sink=sink)
        result = inviter.invite("com.example.app", apply=False,
                                 client=client,
                                 tester_emails=["x@gmail.com", "y@gmail.com"])
        assert result["ok"] is True
        assert result["tester_count"] == 2

    def test_api_error_surfaces_diagnosis(self, tmp_cred):
        cfg = community.empty_config()
        cfg["emails"] = [f"u{i}@gmail.com" for i in range(12)]
        community.save(cfg)

        class BrokenClient(FakeRealClient):
            def _call_api(self, method, path, body=None):
                return {"success": False, "status_code": 403,
                        "error": "HTTP 403: permission denied",
                        "data": None}

        result = inviter.invite("com.example.app", apply=True,
                                 client=BrokenClient())
        assert result["ok"] is False
        assert result["stage"] == "api-error"
        assert result["http_status"] == 403
        assert "permission" in result["detail"]


class TestCLI:
    def test_status_outputs_indicator(self, tmp_cred, capsys):
        from operation.publishing_factory.tester_community import cli
        cfg = community.empty_config()
        cfg["emails"] = [f"u{i}@gmail.com" for i in range(12)]
        community.save(cfg)
        code = cli.cmd_status(argparse_namespace_stub())
        out = capsys.readouterr().out
        assert "OK" in out
        assert code == 0

    def test_check_render_markdown(self, tmp_cred, capsys):
        from operation.publishing_factory.tester_community import cli
        eligibility.record_invitation("com.example.app", 12,
                                       today_iso="2025-01-01")
        code = cli.cmd_check(argparse_namespace_stub(
            package="com.example.app"))
        out = capsys.readouterr().out
        assert "5️⃣" in out
        assert "com.example.app" in out
        assert code == 0


def argparse_namespace_stub(**kw):
    """Make a tiny stub for subcommand handlers that need argparse.Namespace."""
    import argparse
    return argparse.Namespace(**kw)
