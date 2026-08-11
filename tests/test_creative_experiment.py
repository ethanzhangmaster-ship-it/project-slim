import pytest
from market_ops.product.creative_experiment import CreativeExperimentLedger


def test_variant_requires_delivery_binding_before_revenue(tmp_path):
    ledger = CreativeExperimentLedger(tmp_path / "ledger.sqlite3")
    variant = ledger.create_variant(parent_creative_id="winner-1", changed_variable="hook", changed_from="calm opening", changed_to="boss attack opening", prompt="test")
    with pytest.raises(ValueError, match="delivery binding"):
        ledger.record_outcome(variant.variant_id, spend=10, revenue=20, impressions=100, clicks=10, installs=2)
    ledger.bind_delivery(variant.variant_id, platform="META", ad_id="ad-1", adset_id="set-1", campaign_id="campaign-1")
    assert ledger.record_outcome(variant.variant_id, spend=10, revenue=20, impressions=100, clicks=10, installs=2)["roas"] == 2.0


def test_variant_rejects_no_actual_change(tmp_path):
    with pytest.raises(ValueError, match="different"):
        CreativeExperimentLedger(tmp_path / "ledger.sqlite3").create_variant(parent_creative_id="winner", changed_variable="hook", changed_from="A", changed_to="A", prompt="test")


def test_variant_exports_materialized_asset_path(tmp_path):
    asset = tmp_path / "creative.png"
    asset.write_bytes(b"materialized-asset")
    ledger = CreativeExperimentLedger(tmp_path / "ledger.sqlite3")
    variant = ledger.create_variant(
        parent_creative_id="winner-1",
        changed_variable="merge_equation",
        changed_from="two eggs to dragon",
        changed_to="three eggs to witch",
        prompt="single variable mutation",
        asset_path=str(asset),
    )
    packet = ledger.outcome(variant.variant_id)
    assert packet["asset_path"] == str(asset)


def test_variant_rejects_missing_asset_path(tmp_path):
    ledger = CreativeExperimentLedger(tmp_path / "ledger.sqlite3")
    with pytest.raises(FileNotFoundError, match="does not exist"):
        ledger.create_variant(
            parent_creative_id="winner-1",
            changed_variable="hook",
            changed_from="A",
            changed_to="B",
            prompt="test",
            asset_path=str(tmp_path / "missing.png"),
        )


def test_delivery_bound_variant_asset_cannot_be_replaced(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    ledger = CreativeExperimentLedger(tmp_path / "ledger.sqlite3")
    variant = ledger.create_variant(
        parent_creative_id="winner-1",
        changed_variable="hook",
        changed_from="A",
        changed_to="B",
        prompt="test",
        asset_path=str(first),
    )
    ledger.attach_asset(variant.variant_id, str(second))
    assert ledger.outcome(variant.variant_id)["asset_path"] == str(second)
    ledger.bind_delivery(variant.variant_id, platform="META", ad_id="ad", adset_id="set", campaign_id="campaign")
    with pytest.raises(ValueError, match="cannot be replaced"):
        ledger.attach_asset(variant.variant_id, str(first))
