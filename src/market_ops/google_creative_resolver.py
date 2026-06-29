from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from market_ops.models import CreativeAssetRow, RevenueBreakdownRow


GENERIC_GOOGLE_VALUES = {
    "",
    "-",
    "display",
    "search googlesearch",
    "youtube youtubevideos",
    "video",
    "image",
    "unknown",
    "(not set)",
    "nan",
    "none",
}


@dataclass(slots=True)
class ResolvedCreativeIdentity:
    identity_id: str
    identity_name: str
    identity_mode: str
    resolution_quality: str
    asset_id: str = ""
    creative_name: str = ""
    campaign_id: str = ""
    adgroup_id: str = ""
    source_id: str = ""


class GoogleCreativeResolver:
    def __init__(self, creative_rows: Iterable[CreativeAssetRow]) -> None:
        self._by_source: dict[tuple[str, str, str], list[CreativeAssetRow]] = {}
        self._by_adgroup: dict[tuple[str, str], list[CreativeAssetRow]] = {}
        self._by_campaign: dict[str, list[CreativeAssetRow]] = {}
        self._build_indexes(creative_rows)

    def resolve(self, row: RevenueBreakdownRow) -> ResolvedCreativeIdentity | None:
        if not self._is_google(row.partner):
            return None

        creative_id = str(row.creative_id or "").strip()
        creative_name = str(row.creative_name or "").strip()
        if self._is_real_creative(creative_id, creative_name):
            return ResolvedCreativeIdentity(
                identity_id=creative_id or creative_name,
                identity_name=creative_name or creative_id,
                identity_mode="creative_id",
                resolution_quality="resolved",
                asset_id=creative_id,
                creative_name=creative_name,
                campaign_id=str(row.campaign_id or "").strip(),
                adgroup_id=str(row.adgroup_id or "").strip(),
                source_id=str(row.source_id or "").strip(),
            )

        candidate = self._match_api_row(row)
        if candidate is not None:
            label = candidate.creative_name or candidate.asset_id
            candidate_type = str(getattr(candidate, "creative_type", "") or "").lower()
            if "source proxy" in candidate_type:
                return ResolvedCreativeIdentity(
                    identity_id=candidate.asset_id,
                    identity_name=label,
                    identity_mode="source_proxy",
                    resolution_quality="proxy_source",
                    asset_id=candidate.asset_id,
                    creative_name=candidate.creative_name,
                    campaign_id=candidate.campaign_id,
                    adgroup_id=candidate.adgroup_id,
                    source_id=candidate.source_id,
                )
            if "adgroup proxy" in candidate_type:
                return ResolvedCreativeIdentity(
                    identity_id=candidate.asset_id,
                    identity_name=label,
                    identity_mode="adgroup_proxy",
                    resolution_quality="proxy_adgroup",
                    asset_id=candidate.asset_id,
                    creative_name=candidate.creative_name,
                    campaign_id=candidate.campaign_id,
                    adgroup_id=candidate.adgroup_id,
                    source_id=candidate.source_id,
                )
            if "campaign proxy" in candidate_type:
                return ResolvedCreativeIdentity(
                    identity_id=candidate.asset_id,
                    identity_name=label,
                    identity_mode="campaign_proxy",
                    resolution_quality="proxy_campaign",
                    asset_id=candidate.asset_id,
                    creative_name=candidate.creative_name,
                    campaign_id=candidate.campaign_id,
                    adgroup_id=candidate.adgroup_id,
                    source_id=candidate.source_id,
                )
            return ResolvedCreativeIdentity(
                identity_id=candidate.asset_id,
                identity_name=label,
                identity_mode="creative_api",
                resolution_quality="resolved_api",
                asset_id=candidate.asset_id,
                creative_name=candidate.creative_name,
                campaign_id=candidate.campaign_id,
                adgroup_id=candidate.adgroup_id,
                source_id=candidate.source_id,
            )

        adgroup_id = str(row.adgroup_id or "").strip()
        adgroup_name = str(row.adgroup or "").strip()
        if self._is_usable_text(adgroup_id):
            return ResolvedCreativeIdentity(
                identity_id=adgroup_id,
                identity_name=adgroup_name or adgroup_id,
                identity_mode="adgroup_proxy",
                resolution_quality="proxy_adgroup",
                campaign_id=str(row.campaign_id or "").strip(),
                adgroup_id=adgroup_id,
            )

        source_id = str(row.source_id or "").strip()
        source_name = str(row.source_name or "").strip()
        if self._is_usable_text(source_id):
            return ResolvedCreativeIdentity(
                identity_id=source_id,
                identity_name=source_name or str(row.adgroup or "").strip() or source_id,
                identity_mode="source_proxy",
                resolution_quality="proxy_source",
                campaign_id=str(row.campaign_id or "").strip(),
                adgroup_id=str(row.adgroup_id or "").strip(),
                source_id=source_id,
            )

        campaign_id = str(row.campaign_id or "").strip()
        campaign_name = str(row.campaign or "").strip()
        if self._is_usable_text(campaign_id):
            return ResolvedCreativeIdentity(
                identity_id=campaign_id,
                identity_name=campaign_name or campaign_id,
                identity_mode="campaign_proxy",
                resolution_quality="proxy_campaign",
                campaign_id=campaign_id,
            )
        return None

    def _build_indexes(self, creative_rows: Iterable[CreativeAssetRow]) -> None:
        for row in creative_rows:
            if not self._is_google(row.channel):
                continue
            source_id = str(row.source_id or "").strip()
            adgroup_id = str(row.adgroup_id or "").strip()
            campaign_id = str(row.campaign_id or "").strip()
            if source_id and adgroup_id and campaign_id:
                self._by_source.setdefault((source_id, adgroup_id, campaign_id), []).append(row)
            if adgroup_id and campaign_id:
                self._by_adgroup.setdefault((adgroup_id, campaign_id), []).append(row)
            if campaign_id:
                self._by_campaign.setdefault(campaign_id, []).append(row)

    def _match_api_row(self, row: RevenueBreakdownRow) -> CreativeAssetRow | None:
        source_id = str(row.source_id or "").strip()
        adgroup_id = str(row.adgroup_id or "").strip()
        campaign_id = str(row.campaign_id or "").strip()

        if source_id and adgroup_id and campaign_id:
            matched = self._pick_best(self._by_source.get((source_id, adgroup_id, campaign_id), []))
            if matched is not None:
                return matched
        if adgroup_id and campaign_id:
            matched = self._pick_best(self._by_adgroup.get((adgroup_id, campaign_id), []))
            if matched is not None:
                return matched
        if campaign_id:
            return self._pick_best(self._by_campaign.get(campaign_id, []))
        return None

    @staticmethod
    def _pick_best(rows: list[CreativeAssetRow]) -> CreativeAssetRow | None:
        usable = [
            row
            for row in rows
            if str(row.asset_id or "").strip()
            and not GoogleCreativeResolver._is_generic_value(row.asset_id)
        ]
        if not usable:
            return None
        return max(
            usable,
            key=lambda row: (
                float(row.spend or 0.0),
                float(row.revenue_value or 0.0),
                float(row.conversions or 0.0),
            ),
        )

    @classmethod
    def _is_real_creative(cls, creative_id: str, creative_name: str) -> bool:
        return cls._is_usable_text(creative_id) and not cls._is_generic_value(creative_id) and not cls._is_generic_value(creative_name)

    @classmethod
    def _is_usable_text(cls, value: str) -> bool:
        return str(value or "").strip().lower() not in {"", "-", "unknown", "(not set)", "nan", "none"}

    @classmethod
    def _is_generic_value(cls, value: str) -> bool:
        return str(value or "").strip().lower() in GENERIC_GOOGLE_VALUES

    @staticmethod
    def _is_google(value: str) -> bool:
        return "google" in str(value or "").strip().lower()
