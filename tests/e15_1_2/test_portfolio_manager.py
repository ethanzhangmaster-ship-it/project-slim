"""E15.1.2 — PortfolioManager tests (lifecycle + ROAS ladder)."""
import pytest

from operation.factory_brain.portfolio_manager import PortfolioManager

from tests.e15_1_2.brainhelpers import game, registry


def _pm(tmp_path, games=()):
    return PortfolioManager(registry(tmp_path, games),
                            state_path=str(tmp_path / "portfolio.json"))


# ---------------------------------------------------------------- stages
def test_default_stage_from_status(tmp_path):
    pm = _pm(tmp_path, [game("p1", status="published")])
    assert pm.stage_of("p1") == "soft_launch"


def test_default_stage_development(tmp_path):
    pm = _pm(tmp_path, [game("p1", status="development")])
    assert pm.stage_of("p1") == "prototype"


def test_set_and_persist_stage(tmp_path):
    pm = _pm(tmp_path, [game("p1")])
    pm.set_stage("p1", "ua_test")
    pm2 = PortfolioManager(pm.registry,
                           state_path=str(tmp_path / "portfolio.json"))
    assert pm2.stage_of("p1") == "ua_test"


def test_set_invalid_stage_raises(tmp_path):
    pm = _pm(tmp_path, [game("p1")])
    with pytest.raises(ValueError):
        pm.set_stage("p1", "warp_drive")


def test_advance_walks_order(tmp_path):
    pm = _pm(tmp_path, [game("p1")])
    pm.set_stage("p1", "idea")
    assert pm.advance("p1") == "prototype"
    assert pm.advance("p1") == "soft_launch"
    assert pm.advance("p1") == "ua_test"
    assert pm.advance("p1") == "scale"
    assert pm.advance("p1") == "scale"       # cap at scale


def test_kill_terminal(tmp_path):
    pm = _pm(tmp_path, [game("p1")])
    pm.kill("p1")
    assert pm.stage_of("p1") == "kill"
    assert pm.advance("p1") == "kill"        # dead stays dead


# ---------------------------------------------------------------- ROAS
def _roas_game(gid, roas, stage, pm_holder):
    g = game(gid, metrics={"roas": roas})
    return g


def test_roas_above_1_increase_budget(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"roas": 1.2})])
    pm.set_stage("p1", "ua_test")
    d = pm.daily_decisions()[0]
    assert d.action == "increase_budget"


def test_roas_mid_keep_optimizing(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"roas": 0.7})])
    pm.set_stage("p1", "ua_test")
    assert pm.daily_decisions()[0].action == "keep_optimizing"


def test_roas_low_stop_ua(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"roas": 0.2})])
    pm.set_stage("p1", "ua_test")
    assert pm.daily_decisions()[0].action == "stop_ua"


def test_roas_low_at_scale_kill(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"roas": 0.2})])
    pm.set_stage("p1", "scale")
    assert pm.daily_decisions()[0].action == "kill"


def test_roas_grey_zone_watch(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"roas": 0.4})])
    pm.set_stage("p1", "ua_test")
    d = pm.daily_decisions()[0]
    assert d.action == "keep_optimizing" and "grey" in d.reason


def test_roas_ignored_outside_ua_stages(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"roas": 1.5,
                                            "ad_revenue_share": 0.9})])
    pm.set_stage("p1", "soft_launch")
    assert pm.daily_decisions()[0].action == "boost_iaa"


# ---------------------------------------------------------------- mix
def test_iaa_heavy_boost_iaa(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"ad_revenue_share": 0.9})])
    assert pm.daily_decisions()[0].action == "boost_iaa"


def test_iap_heavy_boost_iap(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"iap_revenue_share": 0.6})])
    assert pm.daily_decisions()[0].action == "boost_iap"


# ---------------------------------------------------------------- misc
def test_killed_games_get_no_decisions(tmp_path):
    pm = _pm(tmp_path, [game("p1")])
    pm.kill("p1")
    assert pm.daily_decisions() == []


def test_prelaunch_ready_advances(tmp_path):
    pm = _pm(tmp_path, [game("p1", status="ready")])
    pm.set_stage("p1", "prototype")
    assert pm.daily_decisions()[0].action == "advance"


def test_all_decisions_require_manual_apply(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={"roas": 1.5}),
                        game("p2", metrics={"roas": 0.1})])
    pm.set_stage("p1", "ua_test")
    pm.set_stage("p2", "scale")
    assert all(d.requires_manual_apply for d in pm.daily_decisions())


def test_summary_counts_by_stage(tmp_path):
    pm = _pm(tmp_path, [game("p1"), game("p2"), game("p3")])
    pm.set_stage("p1", "scale")
    s = pm.portfolio_summary()
    assert s["total"] == 3 and s["by_stage"]["scale"] == 1


def test_hold_when_no_signal(tmp_path):
    pm = _pm(tmp_path, [game("p1", metrics={})])
    assert pm.daily_decisions()[0].action == "hold"


def test_corrupt_state_file_recovers(tmp_path):
    (tmp_path / "portfolio.json").write_text("{broken", encoding="utf-8")
    pm = _pm(tmp_path, [game("p1")])
    assert pm.stage_of("p1") == "soft_launch"    # falls back to default
