"""
P6 — Tester email source unification (E13.5).

Verifies that the legacy ``tester_community`` config and the new E13.5
``TesterPool`` are a SINGLE source of truth:

  * ``community.load()`` merges the pool's emails IN (pool is canonical).
  * ``community.add_emails()`` writes to the POOL, not the legacy file
    (one writer; the legacy file is only a seed/fallback).
  * legacy + pool union correctly, deduped.
"""
from __future__ import annotations

import json

import pytest

from operation.publishing_factory.tester_community import community
from operation.publishing_factory.play_runtime.tester_pool_agent import (
    TesterPoolAgent, pool_path,
)


@pytest.fixture
def iso(monkeypatch, tmp_path):
    cred = tmp_path / "tester_community.json"
    progress = tmp_path / "tester_progress.json"
    pool = tmp_path / "tester_pool.json"
    monkeypatch.setenv("LAUNCHFORGE_TESTER_COMMUNITY", str(cred))
    monkeypatch.setenv("LAUNCHFORGE_TESTER_PROGRESS", str(progress))
    monkeypatch.setenv("LAUNCHFORGE_PLAY_TESTER_POOL", str(pool))
    return {"cred": cred, "progress": progress, "pool": pool}


def _seed_legacy(cred, emails, groups=None):
    cred.write_text(json.dumps({
        "emails": emails,
        "groups": groups or [],
        "note": "seed",
        "configured": True,
    }, ensure_ascii=False), encoding="utf-8")


def _seed_pool(pool, emails):
    pool.write_text(json.dumps({
        "testers": [{"email": e, "groups": [], "name": "",
                     "note": "", "added_at": "2026-07-28T00:00:00+00:00"}
                    for e in emails],
        "updated_at": "2026-07-28T00:00:00+00:00",
    }, ensure_ascii=False), encoding="utf-8")


class TestPoolIsCanonical:
    def test_empty_pool_and_legacy_is_not_configured(self, iso):
        cfg = community.load()
        assert cfg["configured"] is False
        assert cfg["emails"] == []

    def test_pool_with_12_reflected_in_community(self, iso):
        pool = iso["pool"]
        _seed_pool(pool, [f"u{i}@gmail.com" for i in range(12)])
        cfg = community.load()
        assert cfg["configured"] is True
        assert len(cfg["emails"]) == 12
        assert cfg.get("source") == "tester_pool+community"

    def test_legacy_plus_pool_union_deduped(self, iso):
        _seed_legacy(iso["cred"], [f"leg{i}@gmail.com" for i in range(5)])
        _seed_pool(iso["pool"], [f"pool{i}@gmail.com" for i in range(7)])
        cfg = community.load()
        # 5 legacy + 7 pool = 12, no overlap, sorted+deduped
        assert len(cfg["emails"]) == 12
        assert all(e.startswith(("leg", "pool")) for e in cfg["emails"])

    def test_pool_wins_when_legacy_absent(self, iso):
        _seed_pool(iso["pool"], [f"p{i}@gmail.com" for i in range(3)])
        cfg = community.load()
        assert len(cfg["emails"]) == 3
        assert cfg["configured"] is True


class TestSingleWriter:
    def test_add_emails_writes_to_pool_not_legacy(self, iso):
        # legacy starts with 10 emails
        _seed_legacy(iso["cred"], [f"leg{i}@gmail.com" for i in range(10)])
        # add 2 via community.add_emails -> should go to the POOL
        p = community.add_emails(["new1@gmail.com", "new2@gmail.com"])
        # returns the pool path
        assert str(p) == str(pool_path())
        # legacy file must be unchanged (still 10)
        legacy = json.loads(iso["cred"].read_text(encoding="utf-8"))
        assert len(legacy["emails"]) == 10
        # pool now has the 2 new emails
        pool = json.loads(iso["pool"].read_text(encoding="utf-8"))
        assert len(pool["testers"]) == 2
        # community.load() sees the union: 10 legacy + 2 pool = 12
        cfg = community.load()
        assert len(cfg["emails"]) == 12

    def test_add_emails_via_agent_matches_community(self, iso):
        # Adding through TesterPoolAgent directly is what the new CLI uses;
        # community.load() must reflect it without a separate save().
        TesterPoolAgent().add_tester("alpha@gmail.com")
        TesterPoolAgent().add_tester("beta@gmail.com")
        cfg = community.load()
        assert set(cfg["emails"]) == {"alpha@gmail.com", "beta@gmail.com"}


class TestInviterSeesPool:
    def test_inviter_uses_unified_emails(self, iso):
        from operation.publishing.providers.google_play.real_client \
            import GooglePlayRealClient
        from operation.publishing_factory.tester_community import inviter

        _seed_pool(iso["pool"], [f"u{i}@gmail.com" for i in range(12)])

        sink = []

        class Fake(GooglePlayRealClient):
            def _call_api(self, method, path, body=None):
                sink.append((method, path, body))
                if method == "POST" and path.endswith("/edits"):
                    return {"success": True, "status_code": 200,
                            "data": {"id": "e1"}}
                if method == "PUT" and "/testers/" in path:
                    return {"success": True, "status_code": 200, "data": {}}
                if method == "POST" and path.endswith(":commit"):
                    return {"success": True, "status_code": 200, "data": {}}
                if method == "DELETE" and "/edits/" in path:
                    return {"success": True, "status_code": 200, "data": {}}
                return {"success": True, "status_code": 200, "data": {}}

        res = inviter.invite("com.example.app", apply=True, client=Fake())
        assert res["ok"] is True
        assert res["tester_count"] == 12  # from the pool, not legacy
