"""Player Agent Integration — 20 (SDK → profile → segment → config → AB)."""
from tests.e15_2_8.e15_2_8_helpers import synthetic_events, write_jsonl, default_cfg
from operation.player_monetization.events.collector import EventCollector, FileEventReceiver
from operation.player_monetization.user_profile.player_segment import PlayerSegmenter
from operation.player_monetization.user_profile.value_predictor import ValuePredictor
from operation.player_monetization.ad_opportunity.opportunity_detector import OpportunityDetector
from operation.player_monetization.frequency.frequency_optimizer import FrequencyOptimizer
from operation.remote_config.variant_generator import VariantGenerator
from operation.remote_config.experiment_binding import ExperimentBinder
import tempfile, os

def _pipeline(n_users=3):
    """Run full pipeline on synthetic events via FileEventReceiver."""
    d = tempfile.mkdtemp(); p = os.path.join(d, "events.jsonl")
    write_jsonl(p, synthetic_events(n_users))
    profiles = EventCollector(FileEventReceiver(p)).collect()
    segmenter = PlayerSegmenter()
    segs = [segmenter.classify(prof) for prof in profiles]
    predictor = ValuePredictor()
    values = [predictor.predict(prof, seg) for prof, seg in zip(profiles, segs)]
    return profiles, segs, values

def test_pipeline_profiles_count():
    profiles, _, _ = _pipeline(3)
    assert len(profiles) == 3

def test_pipeline_segments_nonempty():
    _, segs, _ = _pipeline(2)
    assert all(s.segment for s in segs)

def test_pipeline_values_predicted():
    _, _, values = _pipeline(2)
    assert all(v.predicted_30d_iaa > 0 for v in values)

def test_pipeline_ad_opp_from_profile():
    profiles, segs, _ = _pipeline(1)
    opps = OpportunityDetector().detect(profiles[0], segs[0], fail_streak=1)
    assert len(opps) > 0

def test_pipeline_frequency_from_profile():
    _, segs, _ = _pipeline(1)
    r = FrequencyOptimizer().optimize("u0", segs[0])
    assert r.max_per_session > 0

def test_pipeline_config_bind():
    cfg = default_cfg()
    pair = ExperimentBinder().bind(cfg, "reward_cooldown", "revive", "e_pipe")
    assert pair is not None

def test_pipeline_flat_config_differs():
    cfg = default_cfg()
    a, b = ExperimentBinder().bind(cfg, "frequency_cap", "", "e_freq")
    assert a.to_flat_dict()["interstitial.max_daily"] < b.to_flat_dict()["interstitial.max_daily"]

def test_pipeline_variant_generator_pair():
    cfg = default_cfg()
    a, b = VariantGenerator().pair(cfg, "e1", {"interstitial": {"max_daily": 25}})
    assert b.interstitial.max_daily == 25

def test_pipeline_profiles_active():
    profiles, _, _ = _pipeline(2)
    assert all(p.active for p in profiles)

def test_pipeline_profiles_country():
    profiles, _, _ = _pipeline(1)
    assert profiles[0].country == "US"

def test_pipeline_segment_to_frequency_rule():
    _, segs, _ = _pipeline(1)
    r = FrequencyOptimizer().optimize("u0", segs[0])
    assert isinstance(r.cooldown_sec, int)

def test_pipeline_config_validate():
    from operation.remote_config.config_manager import ConfigManager
    assert ConfigManager().validate(default_cfg())["ok"]

def test_pipeline_ad_opp_reward_accept():
    profiles, segs, _ = _pipeline(1)
    p = profiles[0]
    opps = OpportunityDetector().detect(p, segs[0], fail_streak=2)
    rew = [o for o in opps if o.opportunity_type == "reward"]
    assert rew[0].ad_probability > 0

def test_pipeline_config_to_flat_all_keys():
    d = default_cfg().to_flat_dict()
    assert "reward.revive.cooldown" in d
    assert "interstitial.max_daily" in d

def test_pipeline_full_flat_variant_keys():
    cfg = default_cfg()
    _, b = VariantGenerator().pair(cfg, "e_full", {"reward": {"revive": {"cooldown": 150}}})
    d = b.to_flat_dict()
    assert d["_experiment_id"] == "e_full"

def test_pipeline_collector_profiles_consistent():
    profiles1, _, _ = _pipeline(2)
    profiles2, _, _ = _pipeline(2)
    assert len(profiles1) == 2 and len(profiles2) == 2

def test_pipeline_high_value_has_multiplier():
    cfg = default_cfg()
    assert cfg.segments["high_value"].reward_multiplier > 1.0

def test_pipeline_at_risk_reduced():
    cfg = default_cfg()
    assert cfg.segments["at_risk"].cooldown_multiplier > 1.0

def test_pipeline_all_actions_have_binding():
    from operation.remote_config.experiment_binding import _BINDING
    assert len(_BINDING) >= 4

def test_pipeline_defaults_safe():
    cfg = default_cfg()
    for r in cfg.reward.values():
        assert r.cooldown_sec >= 30
        assert 0.1 <= r.multiplier <= 5.0
