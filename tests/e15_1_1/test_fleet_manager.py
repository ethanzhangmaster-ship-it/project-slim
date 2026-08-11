"""E15.1.1 — Fleet Manager tests (20)."""
from tests.e15_1_1.e15_1_1_helpers import game, fleet
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.catalog.fleet_manager import (
    FleetManager, TaskType,
)
from operation.publishing_factory.catalog.product_profile import GameStatus


def _reg(games):
    r = GameRegistry(path="data/_t_fleet.json")
    for g in games:
        r.add(g)
    return r


def test_registry_add_get():
    r = _reg([game()])
    assert r.get("merge_witch").game_id == "merge_witch"


def test_registry_count():
    r = _reg(fleet(5))
    assert r.count() == 5


def test_registry_list_by_status():
    r = _reg(fleet(5))
    assert len(r.list_by_status(GameStatus.PUBLISHED.value)) == 2


def test_registry_persist_roundtrip():
    r = _reg([game()])
    r.save()
    r2 = GameRegistry(path="data/_t_fleet.json").load()
    assert r2.get("merge_witch").genre == "merge"


def test_registry_remove():
    r = _reg([game()])
    assert r.remove("merge_witch") is True
    assert r.get("merge_witch") is None


def test_scan_version_ready():
    r = _reg([game(status="ready", version="1.0.0")])
    rep = FleetManager(r).scan()
    assert rep.tasks[0].task_type == TaskType.VERSION_READY.value


def test_scan_metadata_outdated():
    r = _reg([game(status="published", version="1.3.0", published_version="1.2.0")])
    rep = FleetManager(r).scan()
    assert rep.tasks[0].task_type == TaskType.METADATA_OUTDATED.value


def test_scan_rejected_is_resubmit():
    r = _reg([game(status="rejected")])
    rep = FleetManager(r).scan()
    assert rep.tasks[0].task_type == TaskType.RESUBMIT.value


def test_scan_aso_opportunity_published_stale():
    r = _reg([game(status="published", version="1.0.0", published_version="1.0.0",
                   keywords=[], locales=["en-US"])])
    rep = FleetManager(r).scan()
    assert TaskType.ASO_OPPORTUNITY.value in [t.task_type for t in rep.tasks]


def test_resubmit_has_highest_priority():
    r = _reg([game(game_id="bp", status="rejected"),
              game(game_id="mw", status="ready", version="1.0.0")])
    rep = FleetManager(r).scan()
    assert rep.tasks[0].task_type == TaskType.RESUBMIT.value
    assert rep.tasks[0].priority == 0


def test_version_ready_priority_over_aso():
    r = _reg([game(game_id="mw", status="ready", version="1.0.0"),
              game(game_id="wq", status="published", version="1.0.0",
                   published_version="1.0.0", keywords=[], locales=["en-US"])])
    rep = FleetManager(r).scan()
    types = [t.task_type for t in rep.tasks]
    assert types.index(TaskType.VERSION_READY.value) < types.index(TaskType.ASO_OPPORTUNITY.value)


def test_scan_reason_populated():
    r = _reg([game(status="ready", version="2.1.0")])
    rep = FleetManager(r).scan()
    assert "2.1.0" in rep.tasks[0].reason


def test_scan_by_type_counts():
    r = _reg(fleet(5))
    rep = FleetManager(r).scan()
    assert rep.by_type.get(TaskType.RESUBMIT.value) == 1
    # fleet(5) has one ready + one development game -> two first-publish tasks
    assert rep.by_type.get(TaskType.VERSION_READY.value) == 2
    assert rep.by_type.get(TaskType.ASO_OPPORTUNITY.value) == 1


def test_fleet_metrics_summary_total():
    r = _reg(fleet(5))
    s = FleetManager(r).metrics_summary()
    assert s["total"] == 5


def test_fleet_metrics_summary_published():
    r = _reg(fleet(5))
    s = FleetManager(r).metrics_summary()
    assert s["published"] == 2


def test_fleet_metrics_summary_genres():
    r = _reg(fleet(5))
    s = FleetManager(r).metrics_summary()
    assert "merge" in s["genres"]


def test_schedule_daily_alias():
    r = _reg([game(status="ready", version="1.0.0")])
    rep = FleetManager(r).schedule_daily()
    assert rep.scanned == 1


def test_scan_empty_fleet():
    r = _reg([])
    rep = FleetManager(r).scan()
    assert rep.scanned == 0
    assert rep.tasks == []


def test_scan_multiple_games_all_covered():
    r = _reg(fleet(5))
    rep = FleetManager(r).scan()
    assert len({t.game_id for t in rep.tasks}) == 5


def test_task_to_dict():
    r = _reg([game(status="ready", version="1.0.0")])
    rep = FleetManager(r).scan()
    assert rep.tasks[0].to_dict()["game_id"] == "merge_witch"


def test_product_needs_first_publish():
    assert game(status="ready").needs_first_publish() is True
    assert game(status="published").needs_first_publish() is False


def test_product_metadata_outdated_flag():
    assert game(status="published", version="1.1.0", published_version="1.0.0").metadata_outdated() is True
    assert game(status="published", version="1.0.0", published_version="1.0.0").metadata_outdated() is False
