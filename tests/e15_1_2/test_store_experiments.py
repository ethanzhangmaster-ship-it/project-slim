"""E15.1.2 — StoreExperimentPlanner tests."""
from operation.factory_brain.store_experiment_planner import (
    StoreExperimentPlanner,
)

from tests.e15_1_2.brainhelpers import game


def _drop_game(gid="p1", cvr=0.08, baseline=0.15):
    return game(gid, metrics={"store_cvr": cvr, "baseline_cvr": baseline})


def test_trigger_on_relative_drop():
    g = _drop_game(cvr=0.11, baseline=0.15)     # -27% vs baseline
    assert StoreExperimentPlanner.needs_experiment(g) is True


def test_trigger_on_absolute_floor():
    g = _drop_game(cvr=0.08, baseline=0.0)
    assert StoreExperimentPlanner.needs_experiment(g) is True


def test_no_trigger_healthy():
    g = _drop_game(cvr=0.20, baseline=0.18)
    assert StoreExperimentPlanner.needs_experiment(g) is False


def test_no_trigger_without_cvr():
    assert StoreExperimentPlanner.needs_experiment(game("p1")) is False


def test_plan_variant_counts():
    p = StoreExperimentPlanner().plan(_drop_game())
    assert len(p.icon_variants) == 5
    assert len(p.screenshot_variants) == 3
    assert len(p.copy_variants) == 5


def test_plan_none_when_healthy():
    p = StoreExperimentPlanner().plan(_drop_game(cvr=0.5, baseline=0.4))
    assert p is None


def test_plan_requires_manual_apply():
    p = StoreExperimentPlanner().plan(_drop_game())
    assert p.requires_manual_apply is True


def test_plan_store_field():
    p = StoreExperimentPlanner().plan(_drop_game(), store="app_store")
    assert p.store == "app_store"
    assert p.experiment_id.endswith("app_store")


def test_plan_fleet_only_published_and_triggered():
    games = [
        _drop_game("bad"),
        game("dev", status="development",
             metrics={"store_cvr": 0.01}),
        game("ok", metrics={"store_cvr": 0.3, "baseline_cvr": 0.25}),
    ]
    plans = StoreExperimentPlanner().plan_fleet(games)
    assert {p.game_id for p in plans} == {"bad"}


def test_plan_fleet_per_platform():
    g = _drop_game("multi")
    g.platforms = ["google_play", "app_store"]
    plans = StoreExperimentPlanner().plan_fleet([g])
    assert {p.store for p in plans} == {"google_play", "app_store"}


def test_plan_serializable():
    import json
    p = StoreExperimentPlanner().plan(_drop_game())
    assert json.dumps(p.to_dict())
