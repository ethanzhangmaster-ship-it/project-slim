"""Remote Config tests — 20 (spec: RemoteConfig 20)."""
import tempfile, os
from tests.e15_2_8.e15_2_8_helpers import default_cfg
from operation.remote_config.models import RemoteConfig, RewardConfig, InterstitialConfig, SegmentOverride
from operation.remote_config.config_manager import ConfigManager
from operation.remote_config.variant_generator import VariantGenerator

def test_default_cfg_game_id():
    assert default_cfg("com.x.y").game_id == "com.x.y"

def test_default_has_revive():
    assert "revive" in default_cfg().reward

def test_default_interstitial_enabled():
    assert default_cfg().interstitial.enabled

def test_default_segments():
    assert "high_value" in default_cfg().segments

def test_to_flat_dict():
    d = default_cfg().to_flat_dict()
    assert d["reward.revive.enabled"] == True
    assert isinstance(d["reward.revive.cooldown"], int)

def test_reward_config_to_dict():
    r = RewardConfig("test", True, 200, 1.2)
    d = r.to_dict()
    assert d["cooldown"] == 200 and d["multiplier"] == 1.2

def test_interstitial_config_to_dict():
    i = InterstitialConfig(True, 90, False, 8, True)
    d = i.to_dict()
    assert d["after_fail"] == True and d["max_daily"] == 8

def test_segment_override_to_dict():
    s = SegmentOverride("hv", 2.0, 0.5, 1.5)
    d = s.to_dict()
    assert d["reward_multiplier"] == 2.0

def test_config_manager_validate_ok():
    assert ConfigManager().validate(default_cfg())["ok"]

def test_config_manager_validate_missing_id():
    c = RemoteConfig()
    assert not ConfigManager().validate(c)["ok"]

def test_config_manager_validate_short_cooldown():
    c = default_cfg()
    c.reward["revive"].cooldown_sec = 10
    assert not ConfigManager().validate(c)["ok"]

def test_config_manager_save_load_yaml():
    d = tempfile.mkdtemp(); p = os.path.join(d, "cfg.yaml")
    cfg = default_cfg("com.test")
    ConfigManager().save(cfg, p)
    loaded = ConfigManager().load(p)
    assert loaded.game_id == "com.test"

def test_config_manager_save_flat_json():
    d = tempfile.mkdtemp(); p = os.path.join(d, "flat.json")
    cfg = default_cfg()
    ConfigManager().save_flat_json(cfg, p)
    assert os.path.exists(p)

def test_variant_generator_produces_pair():
    cfg = default_cfg()
    a, b = VariantGenerator().pair(cfg, "exp1", {"reward": {"revive": {"cooldown": 180}}})
    assert a.reward["revive"].cooldown_sec == 300
    assert b.reward["revive"].cooldown_sec == 180

def test_variant_generator_control_unchanged():
    cfg = default_cfg()
    a, _ = VariantGenerator().pair(cfg, "exp1", {"interstitial": {"max_daily": 20}})
    assert a.interstitial.max_daily == 10

def test_variant_generator_variant_changed():
    cfg = default_cfg()
    _, b = VariantGenerator().pair(cfg, "exp1", {"interstitial": {"max_daily": 20}})
    assert b.interstitial.max_daily == 20

def test_variant_generator_experiment_id():
    cfg = default_cfg()
    a, b = VariantGenerator().pair(cfg, "e99", {})
    assert a.experiment_id == "e99" and b.experiment_id == "e99"

def test_variant_generator_multiplier():
    cfg = default_cfg()
    _, b = VariantGenerator().pair(cfg, "e1", {"reward": {"revive": {"multiplier": 2.5}}})
    assert b.reward["revive"].multiplier == 2.5

def test_variant_generator_interstitial_after_fail():
    cfg = default_cfg()
    _, b = VariantGenerator().pair(cfg, "e1", {"interstitial": {"after_fail": True}})
    assert b.interstitial.after_fail == True

def test_flat_dict_includes_experiment():
    cfg = default_cfg()
    cfg.experiment_id = "exp_x"; cfg.variant = "treatment"
    d = cfg.to_flat_dict()
    assert d["_experiment_id"] == "exp_x"
