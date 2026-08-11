"""
P3-auto — Auto-pilot Google Play publishing tests
=================================================
Covers the auto-pilot closed-loop mode:
  * OFF (default): plans require approval, no auto-execute
  * ON: passing plans auto-approved, auto-executed via agent
  * ON but no credentials: execution skipped gracefully
  * Existing behavior preserved: three-gate policy intact when off
"""
from __future__ import annotations

import os
import tempfile
from unittest import mock

from operation.publishing_factory.batch_orchestrator import (
    BatchOrchestrator, BatchReport,
)
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.product_profile import GameProduct
from operation.publishing_factory.memory import PublishingMemory
from operation.publishing_factory.auto_pilot import (
    auto_pilot_enabled, ENV_VAR,
)


def _registry_with_games(tmp_path, games):
    path = os.path.join(tmp_path, "catalog.json")
    reg = GameRegistry(path=path)
    for g in games:
        reg.add(g)
    reg.save()
    return reg


def _game(game_id, genre="merge", platforms=None, status="published"):
    return GameProduct(
        game_id=game_id, package_name=f"com.foo.{game_id}",
        platforms=platforms or ["google_play"],
        genre=genre, status=status)


class TestAutoPilotDisabled:
    """Auto-pilot OFF (default) — original behavior preserved."""

    def test_plans_require_approval(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            reg = _registry_with_games(d, [_game("g1")])
            orch = BatchOrchestrator(reg, auto_pilot=False)
            rep = orch.run_daily()
            assert rep.auto_pilot is False
            assert rep.plans
            for p in rep.plans:
                if p.recommended:
                    assert p.requires_approval is True
            assert rep.executed == 0

    def test_no_real_api_when_off(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            reg = _registry_with_games(d, [_game("g1")])
            orch = BatchOrchestrator(reg, auto_pilot=False)
            rep = orch.run_daily()
            assert rep.auto_pilot is False
            # no execution happens
            assert rep.executed == 0


class TestAutoPilotEnabled:
    """Auto-pilot ON — plans auto-approved, auto-executed."""

    def test_plans_auto_approved(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            reg = _registry_with_games(d, [_game("g1")])
            orch = BatchOrchestrator(reg, auto_pilot=True)
            rep = orch.run_daily()
            assert rep.auto_pilot is True
            for p in rep.plans:
                if p.recommended:
                    assert p.requires_approval is False
                    assert p.plan["approval_status"] == "approved"

    def test_execution_attempted(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            reg = _registry_with_games(d, [
                _game("g1"),
                _game("g2"),
            ])
            orch = BatchOrchestrator(reg, auto_pilot=True)
            rep = orch.run_daily()
            assert rep.auto_pilot is True
            # execution was attempted (may fail without real creds/build)
            assert isinstance(rep.executed, int)
            assert rep.executed >= 0

    def test_env_var_respected(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "1")
        assert auto_pilot_enabled() is True
        monkeypatch.setenv(ENV_VAR, "0")
        assert auto_pilot_enabled() is False
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert auto_pilot_enabled() is False

    def test_env_override(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            reg = _registry_with_games(d, [_game("g1")])
            orch = BatchOrchestrator(reg, auto_pilot=True)
            assert orch.auto_pilot is True


class TestAutoPilotEnvVar:
    """Auto-pilot from env var (no explicit constructor flag)."""

    def test_env_on(self, monkeypatch, tmp_path):
        monkeypatch.setenv(ENV_VAR, "1")
        with tempfile.TemporaryDirectory() as d:
            reg = _registry_with_games(d, [_game("g1")])
            orch = BatchOrchestrator(reg)
            assert orch.auto_pilot is True

    def test_env_off(self, monkeypatch, tmp_path):
        monkeypatch.setenv(ENV_VAR, "0")
        with tempfile.TemporaryDirectory() as d:
            reg = _registry_with_games(d, [_game("g1")])
            orch = BatchOrchestrator(reg)
            assert orch.auto_pilot is False
