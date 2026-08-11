"""
Tests — E15.1.2 growth weekly briefing
=======================================
Covers build_markdown rendering, run() file output, dry-run semantics,
and the best-effort Feishu push (mocked so no real group is pinged).
"""
from __future__ import annotations

import os
from datetime import date
from unittest import mock

from operation.factory_brain.growth_sources import briefing
from operation.factory_brain.growth_sources.ingester import (
    MarketOpportunityIngester, build_default_sources)


def test_build_markdown_top_n_and_mock_tag():
    ing = MarketOpportunityIngester(build_default_sources())
    report = ing.run(dry_run=True)  # no drop-in write
    md = briefing.build_markdown(report, top_n=3, today=date(2026, 7, 27))
    assert "每周新游戏机会" in md
    # exactly 3 ranked rows rendered, each flagged [MOCK] in the 来源 column
    assert md.count("| [MOCK] |") == 3
    assert "2026-07-27" in md
    assert "本卡为只读发现" in md


def test_build_markdown_empty_is_safe():
    report = {"sources": [], "opportunities": [], "count": 0}
    md = briefing.build_markdown(report, top_n=5)
    assert "0" in md
    assert "| 1 |" not in md  # no data rows
    assert "每周新游戏机会" in md


def test_run_dry_run_writes_nothing():
    out = briefing.run(notify=False, dry_run=True, today=date(2099, 1, 1))
    assert out["real_api_called"] is False
    assert out["file"] is None
    assert out["notified"] is False
    assert not os.path.exists(os.path.join("outputs/growth", "2099-01-01.md"))


def test_run_writes_briefing_md(tmp_path):
    out_dir = str(tmp_path / "growth")
    out = briefing.run(notify=False, dry_run=False, top_n=5,
                       out_dir=out_dir, today=date(2099, 1, 3))
    assert out["real_api_called"] is False
    assert out["file"] is not None
    assert os.path.exists(out["file"])
    with open(out["file"], encoding="utf-8") as fh:
        content = fh.read()
    assert "[MOCK]" in content
    assert "每周新游戏机会" in content


def test_run_notifies_via_feishu_best_effort():
    with mock.patch(
            "operation.optimizer.notify.feishu.FeishuNotifier") as MockNot:
        inst = MockNot.return_value
        out = briefing.run(notify=True, dry_run=True, today=date(2099, 1, 2))
        assert out["notified"] is True
        assert out["notify_error"] is None
        inst.send_markdown_card.assert_called_once()
        args, _ = inst.send_markdown_card.call_args
        # (title, markdown, color=...)
        assert "每周新游机会" in args[0]
        assert "每周新游戏机会" in args[1]


def test_run_notify_error_is_caught_not_fatal():
    with mock.patch(
            "operation.optimizer.notify.feishu.FeishuNotifier") as MockNot:
        MockNot.return_value.send_markdown_card.side_effect = RuntimeError(
            "webhook 401")
        out = briefing.run(notify=True, dry_run=True, today=date(2099, 1, 4))
        assert out["notified"] is False
        assert out["notify_error"] is not None
        assert "webhook 401" in out["notify_error"]
        assert out["real_api_called"] is False
