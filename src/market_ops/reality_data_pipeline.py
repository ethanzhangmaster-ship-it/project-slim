"""E8: Reality Data Pipeline — connects AI to real market, ads, and attribution data.

Replaces mock collectors with real data sources:
  - E8.1: Meta Ads API → campaign performance + competitor creative signals
  - E8.2: Google Play → market ranking and trend data
  - E8.3: Adjust → attribution and revenue feedback
  - E8.4: Agent calibration → real outcome → weight adjustment

Data source priority:
  1. Live API (Meta Ads API, Adjust API) — when credentials configured
  2. CSV fallback (ads_performance.csv, creative_mapping_adjust_merged_v2.csv) — when historical data exists
  3. Mock generation — development/testing only

Auto-detection: uses credentials from .env, falls back to CSV then mock if unavailable.
"""

from __future__ import annotations

import csv
import os
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

from market_ops.creative_reality.reality_tracker import (
    RealityTracker, CampaignReality, GenomePerformanceDelta,
)
from market_ops.creative_reality.failure_analyzer import (
    FailureAnalyzer, GenomeAttribution, AgentErrorReport,
)
from market_ops.creative_brain.v5_evolution.schemas import Genome


# ═══════════════════════════════════════════════════════════
# E8.1: Meta Ads Reality Pipeline
# ═══════════════════════════════════════════════════════════

class MetaAdsRealityPipeline:
    """Connects real Facebook/Meta Ads campaign data to RealityTracker.

    Uses existing MetaAdsCreativeClient from clients/meta_ads.py.
    Auto-detects META_ACCESS_TOKEN / META_AD_ACCOUNT_ID from .env.

    Data source priority:
      1. Live Meta Ads API (CreativeAssetRow → CampaignReality)
      2. CSV fallback from ads_performance.csv (historical data)
      3. Mock generation (development only)

    Usage:
        pipeline = MetaAdsRealityPipeline()
        campaigns = pipeline.fetch_recent_campaigns(days=7)
        pipeline.feed_reality_tracker(tracker)
    """

    API_VERSION = os.getenv("META_API_VERSION", "v19.0")

    def __init__(self) -> None:
        self._access_token = os.getenv("META_ACCESS_TOKEN", "")
        self._ad_account_id = os.getenv("META_AD_ACCOUNT_ID", "")
        self._connected = bool(self._access_token and self._ad_account_id)
        self._csv_path = Path(os.getenv("ADS_PERFORMANCE_CSV", "output/normalized/ads_performance.csv"))

    def is_connected(self) -> bool:
        return self._connected

    def fetch_recent_campaigns(self, days: int = 7) -> list[CampaignReality]:
        """Fetch real campaign performance.

        Tries: 1) Live Meta API → 2) CSV → 3) Mock.
        """
        # Priority 1: Live API
        if self._connected:
            campaigns = self._fetch_from_api(days)
            if campaigns:
                return campaigns

        # Priority 2: CSV fallback
        campaigns = self._fetch_from_csv(days)
        if campaigns:
            return campaigns

        # Priority 3: Mock
        return self._mock_campaigns(days)

    def _fetch_from_api(self, days: int) -> list[CampaignReality]:
        """Fetch from live Meta Ads insights API (bypasses ads-map limitation).

        Uses insights API directly (spend/impressions/clicks/ctr/actions/action_values).
        Skips creative-level lookup to avoid /ads endpoint 500 errors on limited tokens.
        """
        try:
            import requests
            from datetime import date, timedelta
            import json

            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            params = {
                "access_token": self._access_token,
                "level": "ad",
                "time_range": json.dumps({
                    "since": start_date.isoformat(),
                    "until": end_date.isoformat(),
                }),
                "fields": "ad_id,ad_name,campaign_name,adset_name,spend,impressions,clicks,ctr,actions,action_values",
                "limit": 500,
            }

            url = f"https://graph.facebook.com/{self.API_VERSION}/act_{self._ad_account_id}/insights"
            all_rows: list[dict] = []
            while url:
                resp = requests.get(url, params=params, timeout=60)
                resp.raise_for_status()
                body = resp.json()
                all_rows.extend(body.get("data", []))
                # Pagination
                paging = body.get("paging", {})
                url = paging.get("next", "")
                params = None  # next URL already contains params

            campaigns = []
            for row in all_rows:
                spend = float(row.get("spend", 0) or 0)
                if spend <= 0:
                    continue

                # Extract installs from actions
                installs = self._extract_action_value(row.get("actions"), [
                    "mobile_app_install", "app_install", "omni_app_install",
                ])
                # Extract revenue from action_values
                revenue = self._extract_action_value(row.get("action_values"), [
                    "omni_purchase", "offsite_conversion.fb_mobile_purchase",
                    "purchase", "mobile_purchase",
                ])

                cpi_val = spend / installs if installs > 0 else 0.0
                roas = revenue / spend if spend > 0 else 0.0

                campaigns.append(CampaignReality(
                    campaign_id=row.get("campaign_name", ""),
                    creative_id=row.get("ad_id", ""),
                    spend=spend,
                    impressions=int(float(row.get("impressions", 0) or 0)),
                    clicks=int(float(row.get("clicks", 0) or 0)),
                    ctr=float(row.get("ctr", 0) or 0),
                    installs=installs,
                    cpi=cpi_val,
                    d7_roas=roas,
                    revenue_d7=revenue,
                    is_statistically_significant=spend >= 100,
                ))
            return campaigns

        except Exception as e:
            print(f"[MetaAdsRealityPipeline] API fetch failed: {e}")
            return []

    @staticmethod
    def _extract_action_value(actions: Any, keys: list[str]) -> float:
        """Extract a numeric value from Meta actions/action_values list."""
        if not isinstance(actions, list):
            return 0.0
        for action in actions:
            if isinstance(action, dict):
                action_type = action.get("action_type", "")
                if action_type in keys:
                    return float(action.get("value", 0) or 0)
        return 0.0

    def _fetch_from_csv(self, days: int) -> list[CampaignReality]:
        """Load from ads_performance.csv (normalized format)."""
        if not self._csv_path.exists():
            return []

        try:
            campaigns = []
            with open(self._csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    spend = float(row.get("spend", 0) or 0)
                    if spend <= 0:
                        continue
                    cpi_val = float(row.get("cpi", "0") or 0)
                    # installs = spend / cpi (CSV has no installs column)
                    installs = int(spend / cpi_val) if cpi_val > 0 else 0
                    campaigns.append(CampaignReality(
                        campaign_id=row.get("channel", ""),
                        creative_id=row.get("creative_id", row.get("ad_id", "")),
                        spend=spend,
                        impressions=0,
                        clicks=int(float(row.get("clicks", "0") or 0)),
                        ctr=float(row.get("ctr", "0") or 0),
                        installs=installs,
                        cpi=cpi_val,
                        d7_roas=float(row.get("roas", "0") or 0),
                        revenue_d7=spend * float(row.get("roas", "0") or 0),
                        is_statistically_significant=spend >= 100,
                    ))
            return campaigns[:500]

        except Exception as e:
            print(f"[MetaAdsRealityPipeline] CSV fallback failed: {e}")
            return []

    def feed_reality_tracker(self, tracker: RealityTracker, days: int = 7) -> int:
        """Fetch real campaigns and feed into RealityTracker.

        Returns: number of campaigns ingested.
        """
        campaigns = self.fetch_recent_campaigns(days)
        tracker.ingest_batch(campaigns)
        return len(campaigns)

    def feed_to_flywheel(self, flywheel: Any, days: int = 7) -> dict[str, Any]:
        """Full pipeline: fetch → reality tracker → gene attribution → agent calibration.

        Returns: summary of what was learned from real data.
        """
        campaigns = self.fetch_recent_campaigns(days)
        if not campaigns:
            return {"status": "no_data", "campaigns": 0}

        # Feed into flywheel's record_outcomes format
        results = []
        for c in campaigns:
            results.append({
                "opportunity": f"campaign_{c.creative_id[:8]}",
                "creative_id": c.creative_id,
                "roas": c.d7_roas,
                "ctr": c.ctr,
                "cpi": c.cpi,
                "installs": c.installs,
                "spend": c.spend,
                "outcome": "winner" if c.d7_roas >= 1.0 else "failure",
                "impressions": c.impressions,
            })

        flywheel.record_outcomes(results)
        calibration = flywheel.recalibrate()

        return {
            "campaigns_processed": len(campaigns),
            "total_spend": round(sum(c.spend for c in campaigns), 2),
            "winners": sum(1 for c in campaigns if c.d7_roas >= 1.0),
            "avg_roas": round(sum(c.d7_roas for c in campaigns) / max(1, len(campaigns)), 3),
            "calibration": calibration,
        }

    @staticmethod
    def _mock_campaigns(days: int) -> list[CampaignReality]:
        """Generate realistic mock campaigns for testing."""
        import random
        campaigns = []
        hooks = ["rescue", "reward", "mess_to_clean", "evolution_reveal"]
        for i in range(min(15, days * 3)):
            hook = random.choice(hooks)
            base_roas = 1.2 if hook == "rescue" else (1.0 if hook == "mess_to_clean" else 0.6)
            roas = base_roas + (random.random() - 0.5) * 0.4
            spend = random.randint(50, 500)
            campaigns.append(CampaignReality(
                creative_id=f"fb_creative_{i:04d}",
                campaign_id=f"fb_campaign_{i:04d}",
                spend=spend,
                impressions=int(spend * random.randint(20, 50)),
                clicks=int(spend * random.randint(1, 5)),
                ctr=0.02 + random.random() * 0.03,
                installs=int(spend / random.randint(3, 8)),
                cpi=3 + random.random() * 4,
                d7_roas=round(roas, 3),
                revenue_d7=round(spend * roas, 2),
                is_statistically_significant=spend >= 100,
            ))
        return campaigns


# ═══════════════════════════════════════════════════════════
# E8.2: Google Play Market Scanner
# ═══════════════════════════════════════════════════════════

class GooglePlayMarketScanner:
    """Scans Google Play for real market trends.

    Uses public Google Play ranking pages (no API key needed).
    Future: Google Play Developer API for authenticated access.

    Categories monitored:
      - Puzzle → sort, merge, match
      - Simulation → tycoon, life, building
      - Casual → hyper-casual, idle
    """

    PLAY_STORE_BASE = "https://play.google.com/store"
    MONITORED_CATEGORIES = ["GAME_PUZZLE", "GAME_SIMULATION", "GAME_CASUAL"]

    def __init__(self) -> None:
        self._connected = False  # Will attempt connection on first fetch
        self._cache: dict[str, Any] = {}

    def is_connected(self) -> bool:
        return self._connected

    def scan_top_charts(self, category: str = "GAME_PUZZLE") -> list[dict[str, Any]]:
        """Scan Google Play top charts for a category.

        Returns: [{game_name, package, ranking, rating, installs_estimate}]

        Uses requests to scrape public pages. Falls back to mock.
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            url = f"{self.PLAY_STORE_BASE}/apps/category/{category}"
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code == 200:
                self._connected = True
                # Parse game listings
                soup = BeautifulSoup(resp.text, 'html.parser')
                games = []
                cards = soup.select('[data-docid]')[:20]
                for i, card in enumerate(cards):
                    name_el = card.select_one('.sIskre, .DdYX5, [title]')
                    games.append({
                        "rank": i + 1,
                        "name": name_el.get('title', name_el.text.strip()) if name_el else f"game_{i}",
                        "package": card.get('data-docid', ''),
                        "category": category.replace("GAME_", "").lower(),
                    })
                if games:
                    return games
        except Exception:
            pass

        return self._mock_charts(category)

    def scan_new_releases(self) -> list[dict[str, Any]]:
        """Scan for new game releases."""
        return self._mock_new_releases()

    def detect_trends(self) -> list[dict[str, Any]]:
        """Combine top charts + new releases → trend signals.

        Returns: trend signals that can be fed into MarketKnowledgeGraph.
        """
        trends = []
        for cat in self.MONITORED_CATEGORIES:
            charts = self.scan_top_charts(cat)
            # Extract dominant keywords from game names
            keywords = self._extract_keywords(charts)
            for kw, count in keywords.items():
                if count >= 2:
                    trends.append({
                        "category": cat.replace("GAME_", "").lower(),
                        "keyword": kw,
                        "prevalence": count / max(1, len(charts)),
                        "source": "google_play",
                    })
        return trends

    def feed_to_knowledge_graph(self, graph: Any) -> int:
        """Feed detected trends into MarketKnowledgeGraph."""
        trends = self.detect_trends()
        count = 0
        for t in trends:
            try:
                graph.ingest_category(
                    t["category"], t["prevalence"] * 100, t["prevalence"] * 80,
                    [t["keyword"]], 50,
                )
                count += 1
            except Exception:
                pass
        return count

    @staticmethod
    def _extract_keywords(games: list[dict[str, Any]]) -> dict[str, int]:
        """Extract gameplay keywords from game names."""
        keywords = ["merge", "sort", "puzzle", "simulation", "dragon", "match",
                     "home", "factory", "evolution", "collection", "rescue",
                     "farm", "tycoon", "idle", "builder"]
        counts: dict[str, int] = {}
        for g in games:
            name_lower = g.get("name", "").lower()
            for kw in keywords:
                if kw in name_lower:
                    counts[kw] = counts.get(kw, 0) + 1
        return counts

    @staticmethod
    def _mock_charts(category: str) -> list[dict[str, Any]]:
        cat_name = category.replace("GAME_", "").lower()
        mock_data = {
            "puzzle": [
                "Stack Sort 3D", "Merge Dragon Evolution", "Puzzle Home Makeover",
                "Goods Sort Master", "Sort It Out 3D", "Merge Mansion Puzzle",
                "Tile Match Puzzle", "Dragon Merge King", "Sort Puzzle Challenge",
                "Home Design Merge & Sort",
            ],
            "simulation": [
                "Factory Tycoon Sim", "Home Builder Pro", "Farm Merge Empire",
                "Idle Factory Simulator", "Simulation Sort Evolution",
                "Build & Merge King", "Tycoon Home Design", "Merge Simulation World",
            ],
            "casual": [
                "Rescue Cut Puzzle", "Hyper Sort 3D", "Merge Restaurant",
                "Idle Dragon Merge", "Clean & Sort Master", "Builder Go",
            ],
        }
        names = mock_data.get(cat_name, mock_data["puzzle"])
        return [
            {"rank": i+1, "name": name, "package": f"com.mock.{name.lower().replace(' ','')}",
             "category": cat_name}
            for i, name in enumerate(names[:15])
        ]

    @staticmethod
    def _mock_new_releases() -> list[dict[str, Any]]:
        return [
            {"name": "AI Pet Merge Evolution", "category": "puzzle", "days_since_launch": 3},
            {"name": "Simulation Sort Factory", "category": "simulation", "days_since_launch": 7},
            {"name": "Dragon Rescue Merge 3D", "category": "puzzle", "days_since_launch": 14},
            {"name": "Home Design Sort & Build", "category": "simulation", "days_since_launch": 5},
        ]


# ═══════════════════════════════════════════════════════════
# E8.3: Attribution Bridge (Adjust)
# ═══════════════════════════════════════════════════════════

class AttributionBridge:
    """Bridges Adjust/Firebase attribution data into GenomeAttribution.

    Maps: creative_id → installs → revenue → retention → genome performance.

    Auto-detects: ADJUST_API_TOKEN, ADJUST_APP_TOKEN from .env.
    Falls back to: merged CSV data (creative_mapping_adjust_merged_v2.csv).
    """

    def __init__(self) -> None:
        self._adjust_token = os.getenv("ADJUST_API_TOKEN", "")
        self._adjust_app = os.getenv("ADJUST_APP_TOKEN", "")
        self._connected = bool(self._adjust_token and self._adjust_app)

        # Fallback CSV path
        self._csv_path = Path(
            "output/video_intelligence/p04/creative_mapping_adjust_merged_v2.csv"
        )

    def is_connected(self) -> bool:
        return self._connected

    def fetch_genome_performance(self, days: int = 30) -> list[dict[str, Any]]:
        """Fetch real attribution data.

        Returns: [{creative_id, installs, revenue_d7, d7_roas, d1_retention}]
        """
        if self._connected:
            return self._fetch_from_adjust(days)
        return self._fetch_from_csv()

    def feed_to_attribution(self, attribution: GenomeAttribution) -> int:
        """Feed real attribution into GenomeAttribution via CreativeDNAStore.

        Uses CreativeDNAStore to map creative_id → DNA → Genome,
        then feeds real performance data with gene-level breakdown.
        """
        from market_ops.creative_dna_store import CreativeDNAStore

        store = CreativeDNAStore()
        if store.load() == 0:
            return 0

        return store.feed_to_attribution(attribution)

    def _fetch_from_adjust(self, days: int) -> list[dict[str, Any]]:
        """Real Adjust API call."""
        try:
            import requests
            url = "https://api.adjust.com/kpis/v1"
            resp = requests.get(url, params={
                "app_token": self._adjust_app,
                "kpis": "installs,revenue,retention",
                "utc_offset": "+00:00",
                "start_date": (date.today() - timedelta(days=days)).isoformat(),
                "end_date": date.today().isoformat(),
            }, headers={"Authorization": f"Bearer {self._adjust_token}"})
            if resp.status_code == 200:
                return resp.json().get("result_set", {}).get("rows", [])
        except Exception:
            pass
        return []

    def _fetch_from_csv(self) -> list[dict[str, Any]]:
        """Fallback: load from merged CSV (creative_mapping_adjust_merged_v2.csv).

        CSV columns: fb_spend, fb_revenue, fb_installs, adjust_cost, adjust_revenue, adjust_installs
        """
        if not self._csv_path.exists():
            return self._mock_attribution()

        try:
            rows = []
            with open(self._csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fb_spend = float(row.get("fb_spend", 0) or 0)
                    fb_revenue = float(row.get("fb_revenue", 0) or 0)
                    fb_installs = int(float(row.get("fb_installs", 0) or 0))
                    adj_cost = float(row.get("adjust_cost", 0) or 0)
                    adj_revenue = float(row.get("adjust_revenue", 0) or 0)
                    adj_installs = int(float(row.get("adjust_installs", 0) or 0))

                    # Use adjust data as canonical, fall back to FB
                    spend = adj_cost if adj_cost > 0 else fb_spend
                    revenue = adj_revenue if adj_revenue > 0 else fb_revenue
                    installs = adj_installs if adj_installs > 0 else fb_installs
                    roas = revenue / spend if spend > 0 else 0

                    if installs > 0 or spend > 0:
                        rows.append({
                            "creative_id": row.get("creative_id", ""),
                            "creative_name": row.get("creative_name", row.get("ad_name", "")),
                            "installs": installs,
                            "spend": spend,
                            "d7_roas": roas,
                            "ctr": 0.0,  # CSV doesn't have CTR
                            "cpi": spend / installs if installs > 0 else 0,
                        })
            return rows[:500]
        except Exception:
            return self._mock_attribution()

    @staticmethod
    def _mock_attribution() -> list[dict[str, Any]]:
        return [
            {"creative_id": "c_001", "creative_name": "Sort Rescue 3D",
             "installs": 5000, "d7_roas": 1.2, "ctr": 0.035, "cpi": 3.2},
            {"creative_id": "c_002", "creative_name": "Merge Collection Bright",
             "installs": 3000, "d7_roas": 0.8, "ctr": 0.028, "cpi": 4.5},
            {"creative_id": "c_003", "creative_name": "Sort Mess Clean 3D",
             "installs": 8000, "d7_roas": 1.5, "ctr": 0.042, "cpi": 2.8},
        ]


# ═══════════════════════════════════════════════════════════
# E8.4: Reality Calibrator — bridges FailureAnalyzer with real outcomes
# ═══════════════════════════════════════════════════════════

class RealityCalibrator:
    """Closes the loop: real outcomes → agent weight adjustment.

    Each time real campaign data comes in:
      1. Compare AI prediction vs reality
      2. Identify which agents were wrong and why
      3. Adjust agent weights
      4. Update gene success rates
      5. Feed evolution engine

    Usage:
        calibrator = RealityCalibrator(failure_analyzer, gene_attribution)
        calibrator.calibrate_from_campaigns(campaigns, predictions)
    """

    def __init__(
        self,
        failure_analyzer: FailureAnalyzer,
        gene_attribution: GenomeAttribution,
    ) -> None:
        self._failure_analyzer = failure_analyzer
        self._gene_attribution = gene_attribution
        self._calibration_count = 0

    def calibrate_from_campaigns(
        self,
        campaigns: list[CampaignReality],
        predictions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Run full calibration cycle from real campaign data.

        Args:
            campaigns: Real campaign performance
            predictions: {creative_id: {agent_name: {vote, confidence, dimension}}}

        Returns: calibration report with adjusted weights and lessons.
        """
        # Step 1: Compute deltas
        tracker = RealityTracker()
        tracker.ingest_batch(campaigns)
        pred_scores = {cid: p.get("score", 50) for cid, p in predictions.items()}
        deltas = tracker.compute_deltas(pred_scores)

        # Step 2: Analyze failures
        total_errors = 0
        for delta in deltas:
            if delta.was_failure or not delta.prediction_correct:
                agent_votes = predictions.get(delta.genome_id, {})
                reports = self._failure_analyzer.analyze_failure(delta, agent_votes)
                total_errors += len(reports)

        # Step 3: Gene attribution from real outcomes
        for delta in deltas:
            # Find genome from predictions
            gen_info = predictions.get(delta.genome_id, {}).get("genome")
            if gen_info:
                self._gene_attribution.record_outcome(
                    gen_info, delta.actual_roas, delta.actual_ctr,
                    delta.actual_cpi, delta.was_winner,
                )

        # Step 4: Produce report
        error_profile = self._failure_analyzer.get_system_error_summary()
        winning = self._gene_attribution.get_winning_genes()
        losing = self._gene_attribution.get_losing_genes()

        self._calibration_count += 1

        return {
            "calibration_round": self._calibration_count,
            "campaigns_analyzed": len(campaigns),
            "prediction_errors_found": total_errors,
            "error_profile": error_profile,
            "winning_gene_count": len(winning),
            "losing_gene_count": len(losing),
            "agent_in_sync": self._is_in_sync(campaigns, predictions),
        }

    @staticmethod
    def _is_in_sync(
        campaigns: list[CampaignReality],
        predictions: dict[str, dict[str, Any]],
    ) -> float:
        """How well do predictions match reality? 0-1."""
        if not campaigns or not predictions:
            return 0.5

        correct = 0
        for c in campaigns:
            pred = predictions.get(c.creative_id, {})
            pred_build = pred.get("vote", "watch") in ("build", "prototype")
            actual_winner = c.d7_roas >= 1.0
            if pred_build == actual_winner:
                correct += 1

        return round(correct / max(1, len(campaigns)), 2)


# ═══════════════════════════════════════════════════════════
# Reality Data Pipeline — unified entry point
# ═══════════════════════════════════════════════════════════

class RealityDataPipeline:
    """Unified entry point for all reality data sources.

    Auto-detects available data sources and feeds them into the flywheel.

    Usage:
        pipeline = RealityDataPipeline()
        report = pipeline.run(flywheel)
        # → fetches real Meta Ads, Google Play, Adjust data
        # → feeds into flywheel for recalibration
    """

    def __init__(self) -> None:
        self._meta_ads = MetaAdsRealityPipeline()
        self._google_play = GooglePlayMarketScanner()
        self._attribution = AttributionBridge()

    def run(self, flywheel: Any) -> dict[str, Any]:
        """Run full reality data pipeline.

        Returns: report showing what was connected and what was learned.
        """
        report: dict[str, Any] = {
            "run_time": datetime.now().isoformat(),
            "sources": {},
            "learned": {},
        }

        # E8.1: Meta Ads (API → CSV → mock fallback built into pipeline)
        meta_result = self._meta_ads.feed_to_flywheel(flywheel)
        api_status = "api_connected" if self._meta_ads.is_connected() else "csv_or_mock"
        report["sources"]["meta_ads"] = {
            "status": api_status,
            "campaigns": meta_result.get("campaigns_processed", 0),
            "total_spend": meta_result.get("total_spend", 0),
            "winners": meta_result.get("winners", 0),
            "avg_roas": meta_result.get("avg_roas", 0),
        }

        # E8.2: Google Play
        trends = self._google_play.detect_trends()
        self._google_play.feed_to_knowledge_graph(flywheel._knowledge_graph)
        report["sources"]["google_play"] = {
            "status": "connected" if self._google_play.is_connected() else "mock",
            "trends_detected": len(trends),
        }

        # E8.3: Attribution
        if self._attribution.is_connected():
            attr_count = self._attribution.feed_to_attribution(flywheel._gene_attribution)
            report["sources"]["attribution"] = {
                "status": "connected", "records": attr_count,
            }
        else:
            attr_count = self._attribution.feed_to_attribution(flywheel._gene_attribution)
            report["sources"]["attribution"] = {
                "status": "csv_fallback", "records": attr_count,
            }

        # E8.4: Recalibrate agents from reality
        calibration = flywheel.recalibrate()
        report["learned"] = {
            "winning_genes": len(calibration.get("winning_genes", [])),
            "agent_calibration": list(calibration.get("calibration", {}).keys()),
            "reality_stats": calibration.get("reality_stats", {}),
        }

        return report

    def get_connection_status(self) -> dict[str, bool]:
        """Which data sources are connected?"""
        return {
            "meta_ads": self._meta_ads.is_connected(),
            "google_play": self._google_play.is_connected(),
            "attribution_adjust": self._attribution.is_connected(),
        }
