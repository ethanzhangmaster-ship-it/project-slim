"""Experiment Binding tests — 20 (spec: Experiment Binding 20)."""
from tests.e15_2_8.e15_2_8_helpers import default_cfg
from operation.remote_config.experiment_binding import ExperimentBinder, _BINDING

def test_binding_known_actions():
    assert "reward_cooldown" in _BINDING
    assert "interstitial_interval" in _BINDING

def test_binding_unknown_action():
    assert ExperimentBinder().bind(default_cfg(), "nonexistent") is None

def test_binding_reward_cooldown_control():
    a, b = ExperimentBinder().bind(default_cfg(), "reward_cooldown", "revive", "e1")
    assert a.reward["revive"].cooldown_sec == _BINDING["reward_cooldown"]["control"]

def test_binding_reward_cooldown_variant():
    a, b = ExperimentBinder().bind(default_cfg(), "reward_cooldown", "revive", "e1")
    assert b.reward["revive"].cooldown_sec == _BINDING["reward_cooldown"]["variant"]

def test_binding_reward_multiplier_control():
    a, b = ExperimentBinder().bind(default_cfg(), "reward_multiplier", "revive", "e1")
    assert a.reward["revive"].multiplier == _BINDING["reward_multiplier"]["control"]

def test_binding_reward_multiplier_variant():
    a, b = ExperimentBinder().bind(default_cfg(), "reward_multiplier", "revive", "e1")
    assert b.reward["revive"].multiplier == _BINDING["reward_multiplier"]["variant"]

def test_binding_interstitial_interval_control():
    a, b = ExperimentBinder().bind(default_cfg(), "interstitial_interval", "", "e1")
    assert a.interstitial.min_interval_sec == _BINDING["interstitial_interval"]["control"]

def test_binding_interstitial_interval_variant():
    a, b = ExperimentBinder().bind(default_cfg(), "interstitial_interval", "", "e1")
    assert b.interstitial.min_interval_sec == _BINDING["interstitial_interval"]["variant"]

def test_binding_after_fail_control():
    a, b = ExperimentBinder().bind(default_cfg(), "interstitial_after_fail", "", "e1")
    assert a.interstitial.after_fail == False

def test_binding_after_fail_variant():
    a, b = ExperimentBinder().bind(default_cfg(), "interstitial_after_fail", "", "e1")
    assert b.interstitial.after_fail == True

def test_binding_frequency_cap_control():
    a, b = ExperimentBinder().bind(default_cfg(), "frequency_cap", "", "e1")
    assert a.interstitial.max_daily == _BINDING["frequency_cap"]["control"]

def test_binding_frequency_cap_variant():
    a, b = ExperimentBinder().bind(default_cfg(), "frequency_cap", "", "e1")
    assert b.interstitial.max_daily == _BINDING["frequency_cap"]["variant"]

def test_binding_experiment_id_set():
    a, b = ExperimentBinder().bind(default_cfg(), "reward_cooldown", "", "exp_42")
    assert a.experiment_id == "exp_42" and b.experiment_id == "exp_42"

def test_binding_variant_tag():
    a, b = ExperimentBinder().bind(default_cfg(), "reward_multiplier", "", "e1")
    assert a.variant == "control" and b.variant == "variant"

def test_binding_flat_jsons_differ():
    a, b = ExperimentBinder().bind(default_cfg(), "interstitial_interval", "", "e1")
    assert a.to_flat_dict() != b.to_flat_dict()

def test_binding_all_actions_bindable():
    for action in _BINDING:
        assert ExperimentBinder().bind(default_cfg(), action, "revive", "e") is not None

def test_binding_5_actions_defined():
    assert len(_BINDING) == 5

def test_binding_control_unchanged_from_base():
    base = default_cfg()
    a, _ = ExperimentBinder().bind(base, "reward_cooldown", "revive", "e")
    assert a.reward["revive"].cooldown_sec == base.reward["revive"].cooldown_sec

def test_binding_interstitial_enabled_unchanged():
    base = default_cfg()
    _, b = ExperimentBinder().bind(base, "reward_multiplier", "revive", "e")
    assert b.interstitial.enabled == base.interstitial.enabled

def test_binding_target_defaults_to_revive():
    a, _ = ExperimentBinder().bind(default_cfg(), "reward_cooldown", "", "e")
    assert "revive" in a.reward
