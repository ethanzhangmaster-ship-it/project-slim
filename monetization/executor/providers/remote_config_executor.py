"""
E13.3.3 — Module 4c: Remote Config Provider (MOCK)
===================================================

MOCK adapter for a Remote Config service (Firebase RemoteConfig / custom). This
is the *easiest to land first* in production because it is just a key/value
push (e.g. `reward_frequency`), so it has no mediation SDK coupling.

v1 still MOCKs it (no network call) but the response makes the RemoteConfig
target explicit so the real adapter (E13.4) is a drop-in.
"""
from __future__ import annotations

from typing import List

from monetization.executor.models import Change
from monetization.executor.providers.base import MonetizationProvider, _assert_mock


class RemoteConfigProvider(MonetizationProvider):
    name = "RemoteConfig"

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
        # RemoteConfig pushes the new value as a parameter
        return {
            "provider": self.name,
            "status": "simulated_success",
            "real_api_called": False,
            "parameter": change.target,
            "value": change.new,
            "change": change.to_dict(),
        }

    def rollback(self, change: Change) -> dict:
        _assert_mock()
        self.rolled_back.append(change)
        return {
            "provider": self.name,
            "status": "simulated_rolled_back",
            "real_api_called": False,
            "parameter": change.target,
            "value": change.old,
            "change": change.to_dict(),
        }

    def status(self) -> dict:
        return {
            "provider": self.name,
            "applied_count": len(self.applied),
            "rolled_back_count": len(self.rolled_back),
            "real_api_called": False,
        }
