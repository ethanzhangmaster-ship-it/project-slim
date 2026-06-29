from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from market_ops.clients.feishu_bot import FeishuBotClient
from market_ops.config import Settings, load_settings
from market_ops.final_digest import FinalWeeklyDigestBuilder
from market_ops.final_executive import FinalExecutiveReportBuilder
from market_ops.pipeline import DataRepository, WeeklyPipeline
from market_ops.pre_send_summary import PreSendSummaryBuilder

DEFAULT_BOSS_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/1dc70405-022d-48e2-b1ba-4fa4b4998c25"
DEFAULT_MARKET_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/bee81e5c-c527-4ac4-bc82-5b54c726c18f"


@dataclass(slots=True)
class BroadcastTargets:
    boss_webhook: str
    market_webhook: str


@dataclass(slots=True)
class BroadcastArtifacts:
    digest: Any
    executive: Any
    boss_card: dict
    market_simple_card: dict
    market_detailed_card: dict
    recovery_card: dict
    summary_card: dict


def _section(title: str, lines: list[str]) -> dict:
    return {
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**{title}**\n" + "\n".join(lines),
        },
    }


def _resolve_market_webhook(settings: Settings, override: str | None = None) -> str:
    webhook = (override or settings.feishu_market_webhook or settings.feishu_bot_webhook or DEFAULT_MARKET_WEBHOOK).strip()
    if not webhook:
        raise ValueError("Market webhook is missing. Set FEISHU_MARKET_WEBHOOK or pass --market-webhook.")
    return webhook


def _resolve_boss_webhook(settings: Settings, override: str | None = None) -> str:
    if not settings.allow_boss_send and not override:
        raise ValueError("Boss send is locked. Set ALLOW_BOSS_SEND=true or pass --boss-webhook explicitly.")
    webhook = (override or settings.feishu_boss_webhook or DEFAULT_BOSS_WEBHOOK).strip()
    if not webhook:
        raise ValueError("Boss webhook is missing. Set FEISHU_BOSS_WEBHOOK or pass --boss-webhook.")
    return webhook


def build_artifacts(report_date: date, meeting_name: str, *, writeback: bool = False) -> BroadcastArtifacts:
    settings = load_settings()
    repo = DataRepository(settings)
    weekly_pipeline = WeeklyPipeline(settings)
    report, _ = weekly_pipeline.run(report_date=report_date, meeting_name=meeting_name, writeback=writeback)

    ads_rows = repo.load_ads_performance()
    creative_rows = repo.load_creative_library()
    revenue_rows = repo.load_adjust_revenue()
    revenue_breakdown_rows = repo.load_adjust_revenue_breakdown(report_date - timedelta(days=13), report_date)

    digest_builder = FinalWeeklyDigestBuilder(settings)
    executive_builder = FinalExecutiveReportBuilder(settings)

    digest = digest_builder.build(
        report,
        ads_rows,
        creative_rows,
        revenue_rows,
        revenue_breakdown_rows,
    )
    executive = executive_builder.build(
        period="weekly",
        report_date=report_date,
        ads_rows=ads_rows,
        creative_rows=creative_rows,
        revenue_rows=revenue_rows,
        revenue_breakdown_rows=revenue_breakdown_rows,
        market_digest=digest,
    )

    boss_card = executive_builder.build_card(executive)
    market_simple_card = digest_builder.build_simple_card(digest)
    market_detailed_card = digest_builder.build_card(digest)
    recovery_card = digest_builder.build_recovery_card(digest)
    summary_builder = PreSendSummaryBuilder(settings)
    summary_result = summary_builder.build(report_date=report_date)
    summary_payload = json.loads(summary_result.json_path.read_text(encoding="utf-8"))
    summary_card = summary_builder.build_card(summary_payload)
    return BroadcastArtifacts(
        digest=digest,
        executive=executive,
        boss_card=boss_card,
        market_simple_card=market_simple_card,
        market_detailed_card=market_detailed_card,
        recovery_card=recovery_card,
        summary_card=summary_card,
    )


def build_cards(report_date: date, meeting_name: str) -> tuple[dict, dict, dict]:
    artifacts = build_artifacts(report_date, meeting_name)
    return artifacts.boss_card, artifacts.market_simple_card, artifacts.recovery_card


def send_cards(report_date: date, meeting_name: str, targets: BroadcastTargets) -> dict[str, dict]:
    boss_card, market_card, recovery_card = build_cards(report_date, meeting_name)
    boss_bot = FeishuBotClient(targets.boss_webhook)
    market_bot = FeishuBotClient(targets.market_webhook)
    return {
        "boss_executive": boss_bot.send_card(boss_card),
        "boss_recovery": boss_bot.send_card(recovery_card),
        "market_digest": market_bot.send_card(market_card),
        "market_recovery": market_bot.send_card(recovery_card),
    }


def send_selected_cards(
    report_date: date,
    meeting_name: str,
    *,
    send_boss: bool,
    send_market: bool,
    include_recovery: bool = True,
    market_detailed: bool = False,
    boss_webhook: str | None = None,
    market_webhook: str | None = None,
) -> dict[str, dict]:
    if not send_boss and not send_market:
        raise ValueError("At least one target must be selected: boss or market.")

    settings = load_settings()
    artifacts = build_artifacts(report_date, meeting_name)
    results: dict[str, dict] = {}

    if send_boss:
        webhook = _resolve_boss_webhook(settings, boss_webhook)
        boss_bot = FeishuBotClient(webhook)
        results["boss_executive"] = boss_bot.send_card(artifacts.boss_card)
        if include_recovery:
            results["boss_recovery"] = boss_bot.send_card(artifacts.recovery_card)

    if send_market:
        webhook = _resolve_market_webhook(settings, market_webhook)
        market_bot = FeishuBotClient(webhook)
        market_card = artifacts.market_detailed_card if market_detailed else artifacts.market_simple_card
        results["market_digest"] = market_bot.send_card(market_card)
        if include_recovery and market_detailed:
            results["market_recovery"] = market_bot.send_card(artifacts.recovery_card)

    return results


def send_market_all_cards(
    report_date: date,
    meeting_name: str,
    *,
    include_recovery: bool = True,
    market_webhook: str | None = None,
) -> dict[str, dict]:
    settings = load_settings()
    artifacts = build_artifacts(report_date, meeting_name)
    webhook = _resolve_market_webhook(settings, market_webhook)
    market_bot = FeishuBotClient(webhook)

    results: dict[str, dict] = {
        "market_summary": market_bot.send_card(artifacts.summary_card),
        "market_simple": market_bot.send_card(artifacts.market_simple_card),
        "market_detail": market_bot.send_card(artifacts.market_detailed_card),
    }
    if include_recovery:
        results["market_recovery"] = market_bot.send_card(artifacts.recovery_card)
    return results


if __name__ == "__main__":
    result = send_cards(
        report_date=date(2026, 6, 3),
        meeting_name="Weekly Market Ops Review",
        targets=BroadcastTargets(
            boss_webhook=DEFAULT_BOSS_WEBHOOK,
            market_webhook=DEFAULT_MARKET_WEBHOOK,
        ),
    )
    print(result)
