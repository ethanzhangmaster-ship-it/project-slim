"""
E13.3.3 — Module 4b: ironSource LevelPlay Provider (MOCK)
=========================================================

MOCK adapter for ironSource LevelPlay (now part of AppLovin mediation). Same
surface as MaxProvider. Used when the segment network is mediated by LevelPlay
(e.g. ironsource / levelplay / supersonic) — see config_mutator routing.
"""
from __future__ import annotations

from typing import List

from monetization.executor.models import Change
from monetization.executor.providers.base import MonetizationProvider, _assert_mock


class LevelPlayProvider(MonetizationProvider):
    name = "LevelPlay"

    def __init__(self):
        self.applied: List[Change] = []
        self.rolled_back: List[Change] = []
        self._fail_next = False

    def set_fail_next(self, value: bool = True) -> None:
        self._fail_next = value

    def apply(self, change: Change) -> dict:
        _assert_mock()
        if self._fail_next:
            self._fail_next = False
            return {
                "provider": self.name,
                "status": "simulated_failed",
                "real_api_called": False,
                "change": change.to_dict(),
                "error": "mock injected failure (simulate_fail=True)",
            }
        self.applied.append(change)
        return {
            "provider": self.name,
            "status": "simulated_success",
            "real_api_called": False,
            "change": change.to_dict(),
        }

    def rollback(self, change: Change) -> dict:
        _assert_mock()
        self.rolled_back.append(change)
        return {
            "provider": self.name,
            "status": "simulated_rolled_back",
            "real_api_called": False,
            "change": change.to_dict(),
        }

    def status(self) -> dict:
        return {
            "provider": self.name,
            "applied_count": len(self.applied),
            "rolled_back_count": len(self.rolled_back),
            "real_api_called": False,
        }
