"""
E15.1.2 — Market-opportunity source adapters (Growth intake connector).

Producers of ``data/market_opportunities.json`` consumed (with zero
coupling) by ``OpportunityIntake`` / ``FactoryBrain``.

  * AppleTopFreeSource — REAL, no-auth public-chart scraper (Apple
        top-free Games RSS). Live-first + cache fallback. Runs by default.
  * MockMarketSource  — deterministic stand-in for demos/offline; opt-in
        via ``--source mock``.
  * RealMarketSource  — inert skeleton; plug a provider adapter + config
                        to go live (never hits network until configured).
  * MarketOpportunityIngester — merge + dedupe + rank + persist.
"""
from .base import MarketSource
from .mock_source import MockMarketSource
from .real_source import RealMarketSource, register_provider
from .public_chart_source import AppleTopFreeSource
from .ingester import MarketOpportunityIngester, build_default_sources

__all__ = [
    "MarketSource", "MockMarketSource", "RealMarketSource",
    "AppleTopFreeSource", "register_provider",
    "MarketOpportunityIngester", "build_default_sources",
]
