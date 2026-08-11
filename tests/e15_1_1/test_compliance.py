"""E15.1.1 — Compliance tests (15)."""
from tests.e15_1_1.e15_1_1_helpers import game, fleet
from operation.publishing_factory.catalog.game_registry import GameRegistry
from operation.publishing_factory.compliance.policy_scanner import (
    PolicyScanner, PolicyReport,
)
from operation.publishing_factory.compliance.privacy_checker import (
    PrivacyChecker, PrivacyReport,
)
from operation.publishing_factory.compliance.store_risk_predictor import (
    StoreRiskPredictor, RiskPrediction,
)


def _fleet():
    r = GameRegistry(path="data/_t_comp.json")
    for g in fleet(5):
        r.add(g)
    return r


def test_policy_clean_for_unique_game():
    g = game(genre="merge", keywords=["merge", "magic"],
             selling_points=["Combine", "Discover"])
    rep = PolicyScanner().scan(g, [game(genre="puzzle", keywords=["x"])])
    assert rep.clean is True


def test_policy_flags_similar_metadata():
    a = game(game_id="a", genre="merge", keywords=["merge", "magic", "dragon"],
             display_name="Merge Witch", selling_points=["Combine", "Discover"])
    b = game(game_id="b", genre="merge", keywords=["merge", "magic", "dragon"],
             display_name="Merge Witch", selling_points=["Combine", "Discover"])
    rep = PolicyScanner().scan(a, [b])
    assert not rep.clean and rep.flags


def test_policy_similarity_score_high():
    a = game(game_id="a", genre="merge", keywords=["merge", "magic"],
             display_name="Merge Witch")
    b = game(game_id="b", genre="merge", keywords=["merge", "magic"],
             display_name="Merge Witch")
    rep = PolicyScanner().scan(a, [b])
    assert rep.max_similarity >= 0.6


def test_policy_skips_self():
    g = game(genre="merge", keywords=["merge"])
    rep = PolicyScanner().scan(g, [g])
    assert rep.clean is True


def test_policy_report_to_dict():
    g = game(genre="merge", keywords=["merge"])
    rep = PolicyScanner().scan(g, [game(genre="puzzle")])
    assert "flags" in rep.to_dict()


def test_privacy_pass_with_url():
    g = game(monetization="iaa")
    rep = PrivacyChecker().check(g, {"privacy_policy_url": "https://x", "has_consent": True,
                                     "data_collection_disclosed": True})
    assert rep.passed is True


def test_privacy_fail_missing_url():
    g = game()
    rep = PrivacyChecker().check(g, {})
    assert rep.passed is False
    assert any("privacy_policy_url" in i for i in rep.issues)


def test_privacy_child_needs_age_gate():
    g = game()
    rep = PrivacyChecker().check(g, {"child_directed": True, "age_gate": False,
                                     "coppa_compliant": False,
                                     "privacy_policy_url": "x",
                                     "data_collection_disclosed": True})
    assert rep.passed is False
    assert any("age gate" in i for i in rep.issues)


def test_privacy_monetized_needs_consent():
    g = game(monetization="iaa")
    rep = PrivacyChecker().check(g, {"privacy_policy_url": "x",
                                     "data_collection_disclosed": True})
    assert rep.passed is False


def test_privacy_report_to_dict():
    g = game()
    rep = PrivacyChecker().check(g, {"privacy_policy_url": "x",
                                     "data_collection_disclosed": True,
                                     "has_consent": True})
    assert rep.to_dict()["passed"] is True


def test_privacy_child_pass_with_gate():
    g = game()
    rep = PrivacyChecker().check(g, {"child_directed": True, "age_gate": True,
                                     "coppa_compliant": True,
                                     "privacy_policy_url": "x",
                                     "data_collection_disclosed": True,
                                     "has_consent": True})
    assert rep.passed is True


def test_risk_low_when_clean():
    g = game(genre="merge", keywords=["merge", "magic", "dragon"])
    policy = PolicyScanner().scan(g, [game(genre="puzzle")])
    privacy = PrivacyChecker().check(g, {"privacy_policy_url": "x",
                                         "data_collection_disclosed": True,
                                         "has_consent": True})
    risk = StoreRiskPredictor().predict(g, policy, privacy)
    assert risk.level == "low"
    assert risk.apple_prob < 0.25


def test_risk_high_with_policy_and_privacy():
    g = game(game_id="a", genre="merge", keywords=["merge", "magic"],
             display_name="Merge Witch", monetization="iaa")
    b = game(game_id="b", genre="merge", keywords=["merge", "magic"],
             display_name="Merge Witch")
    policy = PolicyScanner().scan(g, [b])
    privacy = PrivacyChecker().check(g, {})  # missing everything
    risk = StoreRiskPredictor().predict(g, policy, privacy)
    assert risk.level == "high"


def test_risk_apple_stricter_than_google_on_43():
    g = game(game_id="a", genre="merge", keywords=["merge"],
             display_name="Merge Witch")
    b = game(game_id="b", genre="merge", keywords=["merge"],
             display_name="Merge Witch")
    policy = PolicyScanner().scan(g, [b])
    privacy = PrivacyChecker().check(g, {"privacy_policy_url": "x",
                                         "data_collection_disclosed": True,
                                         "has_consent": True})
    risk = StoreRiskPredictor().predict(g, policy, privacy)
    assert risk.apple_prob >= risk.google_prob


def test_risk_to_dict():
    g = game()
    policy = PolicyScanner().scan(g, [game(genre="puzzle")])
    privacy = PrivacyChecker().check(g, {"privacy_policy_url": "x",
                                         "data_collection_disclosed": True,
                                         "has_consent": True})
    risk = StoreRiskPredictor().predict(g, policy, privacy)
    d = risk.to_dict()
    assert "apple_prob" in d and "google_prob" in d
