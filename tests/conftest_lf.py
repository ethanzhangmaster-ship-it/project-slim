"""EP0.11.3 Test Pyramid auto-marking.

Every collected test gets exactly one pyramid marker (unit / integration /
e2e) plus optional domain markers (security). Rules, in priority order:

1. Explicit markers on the test/class/module are respected and never
   overridden.
2. Directory-based:  tests/unit/**        -> unit
                     tests/integration/** -> integration
                     tests/e2e/**         -> e2e
                     tests/security/**    -> security (+ integration if the
                     file name says so, else unit)
3. Name-based heuristics: file or test names containing "integration",
   "e2e" / "end_to_end" map to the matching layer.
4. Default: unit.

Measure the pyramid with:
    pytest tests/ --collect-only -q -m unit         (etc.)
"""

from __future__ import annotations

import pytest

_PYRAMID = ("unit", "integration", "e2e")

_E2E_HINTS = ("e2e", "end_to_end")
_INTEGRATION_HINTS = ("integration", "full_pipeline", "full_cycle", "pipeline")


def _has_pyramid_marker(item: pytest.Item) -> bool:
    return any(item.get_closest_marker(m) is not None for m in _PYRAMID)


def _classify(item: pytest.Item) -> str:
    path = str(item.fspath).replace("\\", "/").lower()
    name = item.name.lower()
    fname = path.rsplit("/", 1)[-1]

    # 1) directory-based
    if "/tests/e2e/" in path:
        return "e2e"
    if "/tests/integration/" in path:
        return "integration"
    if "/tests/unit/" in path:
        return "unit"

    # 2) name-based
    if any(h in fname or h in name for h in _E2E_HINTS):
        return "e2e"
    if any(h in fname or h in name for h in _INTEGRATION_HINTS):
        return "integration"

    # 3) default
    return "unit"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        path = str(item.fspath).replace("\\", "/").lower()

        # domain marker: everything under tests/security/ is security
        if "/tests/security/" in path and item.get_closest_marker("security") is None:
            item.add_marker(pytest.mark.security)

        if not _has_pyramid_marker(item):
            item.add_marker(getattr(pytest.mark, _classify(item)))
