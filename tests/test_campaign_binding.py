import pytest

from market_ops.product.campaign_binding import CampaignBinding, CampaignBindingIndex


def test_binding_requires_exact_unique_active_mapping():
    index = CampaignBindingIndex([CampaignBinding("creative-1", "facebook", "campaign-1", 100.0)])
    assert index.resolve("creative-1").campaign_id == "campaign-1"
    with pytest.raises(KeyError, match="No verified"):
        index.resolve("missing")
    with pytest.raises(ValueError, match="Ambiguous"):
        CampaignBindingIndex([CampaignBinding("creative-1", "facebook", "a", 10), CampaignBinding("creative-1", "facebook", "b", 10)])


def test_inactive_binding_cannot_be_resolved():
    index = CampaignBindingIndex([CampaignBinding("creative-1", "facebook", "campaign-1", 100.0, active=False)])
    with pytest.raises(ValueError, match="inactive"):
        index.resolve("creative-1")
