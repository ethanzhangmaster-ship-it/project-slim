"""L15 - 7-Day Meta AEO Campaign — 7天真实投放优化系统

Real-world Paid AEO Optimization Loop System
"""
from __future__ import annotations

import importlib

_PKG = "market_ops.creative_growth_loop.15_7day_aeo"

_mod = importlib.import_module(f"{_PKG}.seven_day_aeo_campaign")
SevenDayAEOCampaign = _mod.SevenDayAEOCampaign
SevenDayReport = _mod.SevenDayReport
DailyMetrics = _mod.DailyMetrics
AdSetInfo = _mod.AdSetInfo
AdCreative = _mod.AdCreative
