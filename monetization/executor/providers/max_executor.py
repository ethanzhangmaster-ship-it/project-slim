"""
E13.3.3 — Module 4a: AppLovin MAX Provider (MOCK)
=================================================

MOCK adapter for AppLovin MAX (bid floors, waterfall priority, backup networks).
In v1 it records the intended change and returns a `simulated_success` response
with `real_api_called: false`. A `fail_next` flag drives the rollback test
(Case 3): the next apply() returns `simulated_failed` without persisting.

Real implementation (E13.4): wrap the AppLovin MAX REST/SDK client here; keep
the same apply/rollback/status surface so the orchestrator is unchanged.
"""
from __future__ import annotations

from typing import List

from monetization.executor.models import Change
from monetization.executor.providers.base import MonetizationProvider, _assert_mock


class MaxProvider(MonetizationProvider):
    name = "MAX"

    def __init__(self):
        self.applied: List[Change] = []
        self.rolled_back: List[Change] = []
        self._fail_next = False

    # ---- test hook (drives Case 3 rollback) ------------------------------ #
    def set_fail_next(self, value: bool = True) -> None:
        self._fail_next = value

    # ---- interface ------------------------------------------------------- #
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
