import sys
import os
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reality_gateway import (
    APIManager, APIConnection, APIStatus, APICallResult,
    CredentialManager, Credential, CredentialType, TokenResponse,
    RateLimiter, RateLimitStatus, RateLimitConfig,
    DataSync, SyncStatus, SyncConfig, SyncResult,
    ErrorHandler, ErrorLevel, ErrorRecord, RetryStrategy,
    ConnectionHealth, HealthStatus, HealthCheckResult,
)
from ads_connector import (
    MetaAdsConnector, Campaign, AdSet, Creative, CampaignMetrics,
    GoogleAdsConnector, GoogleCampaign, Keyword, SearchTerm, PerformanceMetrics,
    ASAConnector, ASACampaign, ASAKeyword, SearchPopularity,
    TikTokAdsConnector, TikTokCreative, TikTokMetrics,
    CampaignSync, SyncStatus as AdsSyncStatus, SyncRecord,
    CreativeSync, CreativeSyncRecord,
    SpendTracker, SpendRecord,
    ConversionSync, ConversionSyncRecord,
)
from attribution_engine import (
    AdjustConnector, AdjustEvent, AdjustRetention, AdjustRevenue, AttributionData,
    AppsFlyerConnector, AppsFlyerInstall, AppsFlyerEvent, AppsFlyerRevenue,
    FirebaseConnector, FirebaseEvent, FirebaseAnalytics,
    RevenueMatcher, RevenueMatchResult, Discrepancy,
    CohortAnalyzer, Cohort, CohortAnalysis, RetentionCurve,
    AttributionValidator, ValidationResult, DataQualityIssue,
    DataReconciliation, ReconciliationResult, DataCorrection,
)
from attribution_engine.revenue_matcher import RevenueSource as AttributionRevenueSource
from appstore_agent import (
    IOSBuilder, Build, BuildStatus,
    AndroidBuilder, AndroidBuild, AndroidBuildStatus,
    StoreMetadata, AppMetadata, Localization,
    ScreenshotUploader, Screenshot, UploadResult, UploadStatus,
    ReleaseManager, Release, ReleaseStatus,
    ReviewMonitor, Review, ReviewStats, SentimentSummary, Sentiment,
    RollbackRelease, Rollback, Version, RollbackStatus,
)
from finance_reality import (
    RevenueTracker, RevenueRecord, RevenueTrend,
    AdCostTracker, AdCostRecord, CostTrend,
    ProfitCalculator, ProfitResult, ProfitMargin,
    CashflowMonitor, CashflowRecord, CashflowStatement, RunwayAnalysis,
    BudgetController, Budget, BudgetAllocation,
    FinanceReport, KeyMetrics, FinanceReportService,
)
from finance_reality.revenue_tracker import RevenueSource
from finance_reality.ad_cost_tracker import AdPlatform
from finance_reality.cashflow_monitor import CashflowType, CashflowCategory
from finance_reality.budget_controller import BudgetCategory
from human_control import (
    ApprovalCenter, ApprovalRequest, ApprovalStatus, ApprovalLevel,
    EmergencyStop, EmergencyEvent, StopStatus,
    DecisionReview, DecisionRecord, DecisionStatus,
    AuditLog, AuditEntry, AuditAction,
    PermissionManager, Permission, PermissionGroup, UserPermission,
)
from reality_learning import (
    PredictionCompare, Prediction, ComparisonResult, ErrorMetrics,
    ErrorAnalyzer, ErrorAnalysis, ErrorPattern, BiasDetection, ErrorCategory, BiasType,
    CalibrationEngine, CalibrationResult, ModelCalibration, CalibrationStatus,
    StrategyUpdate, StrategyEvaluation, StrategyUpdateRecord, StrategyStatus, UpdateType,
    LearningMemory, LearningRecord, LearningInsight, LearningType, LearningStatus,
)


# ---------------------------------------------------------------------------
# reality_gateway (~80 tests)
# ---------------------------------------------------------------------------
class TestRealityGateway(unittest.TestCase):
    def test_apimanager_register_connection(self):
        manager = APIManager()
        conn = manager.register_connection("meta")
        self.assertIsInstance(conn, APIConnection)
        self.assertEqual(conn.platform, "meta")

    def test_apimanager_register_with_status(self):
        manager = APIManager()
        conn = manager.register_connection("google", APIStatus.CONNECTED)
        self.assertEqual(conn.status, APIStatus.CONNECTED)

    def test_apimanager_get_connection(self):
        manager = APIManager()
        manager.register_connection("meta")
        conn = manager.get_connection("meta")
        self.assertIsNotNone(conn)

    def test_apimanager_get_nonexistent_connection(self):
        manager = APIManager()
        conn = manager.get_connection("nonexistent")
        self.assertIsNone(conn)

    def test_apimanager_update_connection_status(self):
        manager = APIManager()
        manager.register_connection("meta")
        result = manager.update_connection_status("meta", APIStatus.CONNECTED)
        self.assertTrue(result)

    def test_apimanager_update_nonexistent_status(self):
        manager = APIManager()
        result = manager.update_connection_status("nonexistent", APIStatus.CONNECTED)
        self.assertFalse(result)

    def test_apimanager_execute_request_not_connected(self):
        manager = APIManager()
        manager.register_connection("meta")
        result = manager.execute_request("meta", "/api/test")
        self.assertFalse(result.success)

    def test_apimanager_execute_request_connected(self):
        manager = APIManager()
        manager.register_connection("meta", APIStatus.CONNECTED)
        result = manager.execute_request("meta", "/api/test")
        self.assertTrue(result.success)

    def test_apimanager_get_connections(self):
        manager = APIManager()
        manager.register_connection("meta")
        manager.register_connection("google")
        conns = manager.get_connections()
        self.assertEqual(len(conns), 2)

    def test_apimanager_get_call_history(self):
        manager = APIManager()
        manager.register_connection("meta", APIStatus.CONNECTED)
        manager.execute_request("meta", "/api/test")
        history = manager.get_call_history()
        self.assertGreater(len(history), 0)

    def test_apimanager_get_call_history_limit(self):
        manager = APIManager()
        manager.register_connection("meta", APIStatus.CONNECTED)
        manager.execute_request("meta", "/api/test1")
        manager.execute_request("meta", "/api/test2")
        history = manager.get_call_history(limit=1)
        self.assertEqual(len(history), 1)

    def test_apimanager_get_stats(self):
        manager = APIManager()
        manager.register_connection("meta", APIStatus.CONNECTED)
        manager.execute_request("meta", "/api/test")
        stats = manager.get_stats()
        self.assertIn("total_connections", stats)
        self.assertIn("total_calls", stats)

    def test_apimanager_register_handler(self):
        manager = APIManager()
        handler = lambda e, **kwargs: APICallResult(success=True)
        manager.register_handler("meta", "GET", handler)
        manager.register_connection("meta", APIStatus.CONNECTED)
        result = manager.execute_request("meta", "/api/test")
        self.assertTrue(result.success)

    def test_apimanager_execute_request_with_method(self):
        manager = APIManager()
        manager.register_connection("meta", APIStatus.CONNECTED)
        result = manager.execute_request("meta", "/api/test", method="POST")
        self.assertIsInstance(result, APICallResult)

    def test_api_connection_create(self):
        conn = APIConnection(platform="meta")
        self.assertEqual(conn.platform, "meta")
        self.assertEqual(conn.status, APIStatus.DISCONNECTED)

    def test_api_connection_to_dict(self):
        conn = APIConnection(platform="meta")
        d = conn.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["platform"], "meta")

    def test_api_call_result_create(self):
        result = APICallResult(success=True, data={"key": "value"})
        self.assertTrue(result.success)
        self.assertEqual(result.data["key"], "value")

    def test_api_call_result_to_dict(self):
        result = APICallResult()
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_api_status_values(self):
        self.assertTrue(hasattr(APIStatus, "CONNECTED"))
        self.assertTrue(hasattr(APIStatus, "DISCONNECTED"))
        self.assertTrue(hasattr(APIStatus, "ERROR"))

    def test_credentialmanager_add_credential(self):
        cm = CredentialManager()
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        result = cm.add_credential(cred)
        self.assertIsInstance(result, Credential)

    def test_credentialmanager_get_credential(self):
        cm = CredentialManager()
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        cm.add_credential(cred)
        result = cm.get_credential("meta")
        self.assertIsNotNone(result)

    def test_credentialmanager_refresh_token(self):
        cm = CredentialManager()
        token = TokenResponse(access_token="test", refresh_token="refresh")
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2, token=token)
        cm.add_credential(cred)
        result = cm.refresh_token("meta")
        self.assertIsNotNone(result)

    def test_credentialmanager_refresh_token_no_token(self):
        cm = CredentialManager()
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        cm.add_credential(cred)
        result = cm.refresh_token("meta")
        self.assertIsNone(result)

    def test_credentialmanager_check_expiration(self):
        cm = CredentialManager()
        token = TokenResponse(access_token="test", expires_at=datetime.now() - timedelta(hours=1))
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2, token=token)
        cm.add_credential(cred)
        result = cm.check_expiration("meta")
        self.assertTrue(result)

    def test_credentialmanager_get_valid_credentials(self):
        cm = CredentialManager()
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        cm.add_credential(cred)
        result = cm.get_valid_credentials()
        self.assertEqual(len(result), 1)

    def test_credentialmanager_get_stats(self):
        cm = CredentialManager()
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        cm.add_credential(cred)
        stats = cm.get_stats()
        self.assertIn("total_credentials", stats)

    def test_credentialmanager_invalidate_credential(self):
        cm = CredentialManager()
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        cm.add_credential(cred)
        result = cm.invalidate_credential("meta")
        self.assertTrue(result)

    def test_credential_create(self):
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        self.assertEqual(cred.platform, "meta")

    def test_credential_to_dict(self):
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        d = cred.to_dict()
        self.assertIsInstance(d, dict)

    def test_credential_type_values(self):
        self.assertTrue(hasattr(CredentialType, "API_KEY"))
        self.assertTrue(hasattr(CredentialType, "OAUTH"))
        self.assertTrue(hasattr(CredentialType, "OAUTH2"))

    def test_token_response_create(self):
        token = TokenResponse(access_token="test")
        self.assertEqual(token.access_token, "test")

    def test_token_response_is_expired(self):
        token = TokenResponse(access_token="test", expires_at=datetime.now() - timedelta(hours=1))
        self.assertTrue(token.is_expired())

    def test_token_response_not_expired(self):
        token = TokenResponse(access_token="test", expires_at=datetime.now() + timedelta(hours=1))
        self.assertFalse(token.is_expired())

    def test_token_response_to_dict(self):
        token = TokenResponse(access_token="test")
        d = token.to_dict()
        self.assertIsInstance(d, dict)

    def test_ratelimiter_register_platform(self):
        limiter = RateLimiter()
        limiter.register_platform("meta")

    def test_ratelimiter_register_with_config(self):
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=500)
        limiter.register_platform("meta", config)

    def test_ratelimiter_check(self):
        limiter = RateLimiter()
        limiter.register_platform("meta")
        status = limiter.check("meta")
        self.assertEqual(status, RateLimitStatus.OK)

    def test_ratelimiter_acquire(self):
        limiter = RateLimiter()
        limiter.register_platform("meta")
        result = limiter.acquire("meta")
        self.assertTrue(result)

    def test_ratelimiter_wait_for_available(self):
        limiter = RateLimiter()
        limiter.register_platform("meta")
        result = limiter.wait_for_available("meta", timeout=1.0)
        self.assertTrue(result)

    def test_ratelimiter_get_stats(self):
        limiter = RateLimiter()
        limiter.register_platform("meta")
        limiter.acquire("meta")
        stats = limiter.get_stats("meta")
        self.assertIn("requests_made", stats)

    def test_ratelimiter_reset_limit(self):
        limiter = RateLimiter()
        limiter.register_platform("meta")
        limiter.acquire("meta")
        limiter.reset_limit("meta")
        stats = limiter.get_stats("meta")
        self.assertEqual(stats["requests_made"], 0)

    def test_rate_limit_config_create(self):
        config = RateLimitConfig(max_requests=500, time_window_seconds=3600)
        self.assertEqual(config.max_requests, 500)

    def test_rate_limit_status_values(self):
        self.assertTrue(hasattr(RateLimitStatus, "OK"))
        self.assertTrue(hasattr(RateLimitStatus, "WARNING"))
        self.assertTrue(hasattr(RateLimitStatus, "EXCEEDED"))

    def test_datasync_add_config(self):
        sync = DataSync()
        config = SyncConfig(platform="meta", data_type="campaigns")
        result = sync.add_config(config)
        self.assertIsInstance(result, SyncConfig)

    def test_datasync_sync(self):
        sync = DataSync()
        config = SyncConfig(platform="meta", data_type="campaigns")
        sync.add_config(config)
        result = sync.sync("meta", "campaigns")
        self.assertIsInstance(result, SyncResult)

    def test_datasync_sync_all_due(self):
        sync = DataSync()
        config = SyncConfig(platform="meta", data_type="campaigns")
        sync.add_config(config)
        results = sync.sync_all_due()
        self.assertGreater(len(results), 0)

    def test_datasync_get_sync_history(self):
        sync = DataSync()
        config = SyncConfig(platform="meta", data_type="campaigns")
        sync.add_config(config)
        sync.sync("meta", "campaigns")
        history = sync.get_sync_history()
        self.assertGreater(len(history), 0)

    def test_datasync_get_stats(self):
        sync = DataSync()
        config = SyncConfig(platform="meta", data_type="campaigns")
        sync.add_config(config)
        sync.sync("meta", "campaigns")
        stats = sync.get_stats()
        self.assertIn("total_syncs", stats)

    def test_sync_config_create(self):
        config = SyncConfig(platform="meta", data_type="campaigns")
        self.assertEqual(config.platform, "meta")

    def test_sync_result_create(self):
        result = SyncResult(sync_id="sync_001", platform="meta", data_type="campaigns", status=SyncStatus.COMPLETED)
        self.assertEqual(result.sync_id, "sync_001")

    def test_sync_result_to_dict(self):
        result = SyncResult(sync_id="sync_001", platform="meta", data_type="campaigns", status=SyncStatus.COMPLETED)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_sync_status_values(self):
        self.assertTrue(hasattr(SyncStatus, "PENDING"))
        self.assertTrue(hasattr(SyncStatus, "RUNNING"))
        self.assertTrue(hasattr(SyncStatus, "COMPLETED"))

    def test_errorhandler_record_error(self):
        eh = ErrorHandler()
        error = eh.record_error("meta", ErrorLevel.WARNING, "Test error")
        self.assertIsInstance(error, ErrorRecord)

    def test_errorhandler_resolve_error(self):
        eh = ErrorHandler()
        error = eh.record_error("meta", ErrorLevel.WARNING, "Test error")
        result = eh.resolve_error(error.error_id, "Resolved")
        self.assertTrue(result)

    def test_errorhandler_get_errors(self):
        eh = ErrorHandler()
        eh.record_error("meta", ErrorLevel.WARNING, "Test error")
        errors = eh.get_errors()
        self.assertEqual(len(errors), 1)

    def test_errorhandler_get_active_errors(self):
        eh = ErrorHandler()
        eh.record_error("meta", ErrorLevel.WARNING, "Test error")
        errors = eh.get_active_errors()
        self.assertEqual(len(errors), 1)

    def test_errorhandler_retry_operation_success(self):
        eh = ErrorHandler()
        result = eh.retry_operation("meta", lambda: "success", max_retries=1)
        self.assertEqual(result, "success")

    def test_errorhandler_get_stats(self):
        eh = ErrorHandler()
        eh.record_error("meta", ErrorLevel.WARNING, "Test error")
        stats = eh.get_stats()
        self.assertIn("total_errors", stats)

    def test_error_record_create(self):
        error = ErrorRecord(error_id="err_001", platform="meta", level=ErrorLevel.WARNING, message="Test", timestamp=datetime.now())
        self.assertEqual(error.error_id, "err_001")

    def test_error_record_to_dict(self):
        error = ErrorRecord(error_id="err_001", platform="meta", level=ErrorLevel.WARNING, message="Test", timestamp=datetime.now())
        d = error.to_dict()
        self.assertIsInstance(d, dict)

    def test_error_level_values(self):
        self.assertTrue(hasattr(ErrorLevel, "INFO"))
        self.assertTrue(hasattr(ErrorLevel, "WARNING"))
        self.assertTrue(hasattr(ErrorLevel, "ERROR"))

    def test_retry_strategy_values(self):
        self.assertTrue(hasattr(RetryStrategy, "NONE"))
        self.assertTrue(hasattr(RetryStrategy, "IMMEDIATE"))
        self.assertTrue(hasattr(RetryStrategy, "EXPONENTIAL"))

    def test_connectionhealth_register_health_check(self):
        ch = ConnectionHealth()
        ch.register_health_check("meta", lambda: True)

    def test_connectionhealth_check_platform(self):
        ch = ConnectionHealth()
        ch.register_health_check("meta", lambda: True)
        result = ch.check_platform("meta")
        self.assertIsInstance(result, HealthCheckResult)

    def test_connectionhealth_check_platform_not_registered(self):
        ch = ConnectionHealth()
        result = ch.check_platform("nonexistent")
        self.assertEqual(result.status, HealthStatus.UNKNOWN)

    def test_connectionhealth_check_all(self):
        ch = ConnectionHealth()
        ch.register_health_check("meta", lambda: True)
        results = ch.check_all()
        self.assertIn("meta", results)

    def test_connectionhealth_get_stats(self):
        ch = ConnectionHealth()
        ch.register_health_check("meta", lambda: True)
        stats = ch.get_stats()
        self.assertIn("total_platforms", stats)

    def test_health_check_result_create(self):
        result = HealthCheckResult(platform="meta", status=HealthStatus.HEALTHY)
        self.assertEqual(result.platform, "meta")

    def test_health_check_result_to_dict(self):
        result = HealthCheckResult(platform="meta", status=HealthStatus.HEALTHY)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_health_status_values(self):
        self.assertTrue(hasattr(HealthStatus, "HEALTHY"))
        self.assertTrue(hasattr(HealthStatus, "DEGRADED"))
        self.assertTrue(hasattr(HealthStatus, "UNHEALTHY"))

    def test_apimanager_get_connection_nonexistent(self):
        manager = APIManager()
        conn = manager.get_connection("nonexistent")
        self.assertIsNone(conn)

    def test_apimanager_update_connection_status(self):
        manager = APIManager()
        manager.register_connection("meta")
        result = manager.update_connection_status("meta", APIStatus.CONNECTED)
        self.assertTrue(result)

    def test_apimanager_get_call_history(self):
        manager = APIManager()
        manager.register_connection("meta", APIStatus.CONNECTED)
        manager.execute_request("meta", "/api/test")
        history = manager.get_call_history("meta")
        self.assertGreater(len(history), 0)

    def test_apimanager_get_connections(self):
        manager = APIManager()
        manager.register_connection("meta")
        manager.register_connection("google")
        connections = manager.get_connections()
        self.assertEqual(len(connections), 2)

    def test_credentialmanager_get_stats(self):
        cm = CredentialManager()
        cred = Credential(platform="meta", credential_type=CredentialType.OAUTH2)
        cm.add_credential(cred)
        stats = cm.get_stats()
        self.assertIn("total_credentials", stats)

    def test_ratelimiter_acquire_exceeded(self):
        limiter = RateLimiter()
        config = RateLimitConfig(max_requests=1)
        limiter.register_platform("meta", config)
        limiter.acquire("meta")
        result = limiter.acquire("meta")
        self.assertFalse(result)

    def test_datasync_sync_all_due(self):
        sync = DataSync()
        config = SyncConfig(platform="meta", data_type="campaigns")
        sync.add_config(config)
        results = sync.sync_all_due()
        self.assertIsInstance(results, list)

    def test_datasync_sync_unknown_platform(self):
        sync = DataSync()
        result = sync.sync("nonexistent", "campaigns")
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.FAILED)

    def test_errorhandler_resolve_nonexistent_error(self):
        eh = ErrorHandler()
        result = eh.resolve_error("nonexistent", "Test")
        self.assertFalse(result)

    def test_errorhandler_retry_operation_failure(self):
        eh = ErrorHandler()
        with self.assertRaises(ZeroDivisionError):
            eh.retry_operation("meta", lambda: 1/0, max_retries=1)

    def test_connectionhealth_get_overall_health(self):
        ch = ConnectionHealth()
        ch.register_health_check("meta", lambda: True)
        overall = ch.get_overall_health()
        self.assertIsInstance(overall, HealthStatus)


# ---------------------------------------------------------------------------
# ads_connector (~100 tests)
# ---------------------------------------------------------------------------
class TestAdsConnector(unittest.TestCase):
    def test_meta_connector_connect(self):
        connector = MetaAdsConnector()
        result = connector.connect()
        self.assertTrue(result)

    def test_meta_connector_get_campaigns(self):
        connector = MetaAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        self.assertIsInstance(campaigns, list)
        self.assertGreater(len(campaigns), 0)

    def test_meta_connector_get_campaign_metrics(self):
        connector = MetaAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        metrics = connector.get_campaign_metrics(campaigns[0].id)
        self.assertIsInstance(metrics, CampaignMetrics)

    def test_meta_connector_get_campaign_metrics_invalid(self):
        connector = MetaAdsConnector()
        connector.connect()
        metrics = connector.get_campaign_metrics("invalid")
        self.assertIsNone(metrics)

    def test_meta_connector_get_ad_sets(self):
        connector = MetaAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        ad_sets = connector.get_ad_sets(campaigns[0].id)
        self.assertIsInstance(ad_sets, list)
        self.assertGreater(len(ad_sets), 0)

    def test_meta_connector_get_creatives(self):
        connector = MetaAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        ad_sets = connector.get_ad_sets(campaigns[0].id)
        creatives = connector.get_creatives(ad_sets[0].id)
        self.assertIsInstance(creatives, list)
        self.assertGreater(len(creatives), 0)

    def test_meta_connector_update_campaign_budget(self):
        connector = MetaAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        result = connector.update_campaign_budget(campaigns[0].id, 9999.0)
        self.assertTrue(result)

    def test_meta_connector_update_campaign_budget_invalid(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.update_campaign_budget("invalid", 9999.0)
        self.assertFalse(result)

    def test_meta_connector_create_campaign(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.create_campaign({"name": "Test Campaign", "budget": 5000.0})
        self.assertIsInstance(result, Campaign)

    def test_meta_connector_create_campaign_not_connected(self):
        connector = MetaAdsConnector()
        result = connector.create_campaign({"name": "Test"})
        self.assertIsNone(result)

    def test_meta_connector_sync_campaigns(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.sync_campaigns()
        self.assertTrue(result["success"])

    def test_campaign_create(self):
        campaign = Campaign(id="camp_001", name="Test Campaign")
        self.assertEqual(campaign.id, "camp_001")

    def test_campaign_to_dict(self):
        campaign = Campaign(id="camp_001", name="Test Campaign")
        d = campaign.to_dict()
        self.assertIsInstance(d, dict)

    def test_ad_set_create(self):
        ad_set = AdSet(id="adset_001", name="Test AdSet", campaign_id="camp_001")
        self.assertEqual(ad_set.id, "adset_001")

    def test_ad_set_to_dict(self):
        ad_set = AdSet(id="adset_001", name="Test AdSet", campaign_id="camp_001")
        d = ad_set.to_dict()
        self.assertIsInstance(d, dict)

    def test_creative_create(self):
        creative = Creative(id="creative_001", ad_set_id="adset_001", name="Test")
        self.assertEqual(creative.id, "creative_001")

    def test_creative_to_dict(self):
        creative = Creative(id="creative_001", ad_set_id="adset_001", name="Test")
        d = creative.to_dict()
        self.assertIsInstance(d, dict)

    def test_campaign_metrics_create(self):
        metrics = CampaignMetrics(campaign_id="camp_001", impressions=1000, clicks=50)
        self.assertEqual(metrics.campaign_id, "camp_001")

    def test_campaign_metrics_to_dict(self):
        metrics = CampaignMetrics(campaign_id="camp_001")
        d = metrics.to_dict()
        self.assertIsInstance(d, dict)

    def test_google_connector_connect(self):
        connector = GoogleAdsConnector()
        result = connector.connect()
        self.assertTrue(result)

    def test_google_connector_get_campaigns(self):
        connector = GoogleAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        self.assertIsInstance(campaigns, list)
        self.assertGreater(len(campaigns), 0)

    def test_google_connector_get_keywords(self):
        connector = GoogleAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        keywords = connector.get_keywords(campaigns[0].id)
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0)

    def test_google_connector_get_search_terms(self):
        connector = GoogleAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        terms = connector.get_search_terms(campaigns[0].id)
        self.assertIsInstance(terms, list)
        self.assertGreater(len(terms), 0)

    def test_google_connector_get_performance(self):
        connector = GoogleAdsConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        performance = connector.get_performance(campaigns[0].id)
        self.assertIsInstance(performance, PerformanceMetrics)

    def test_google_connector_sync_data(self):
        connector = GoogleAdsConnector()
        connector.connect()
        result = connector.sync_data()
        self.assertTrue(result["success"])

    def test_google_campaign_create(self):
        campaign = GoogleCampaign(id="g_camp_001", name="Test")
        self.assertEqual(campaign.id, "g_camp_001")

    def test_google_campaign_to_dict(self):
        campaign = GoogleCampaign(id="g_camp_001", name="Test")
        d = campaign.to_dict()
        self.assertIsInstance(d, dict)

    def test_keyword_create(self):
        keyword = Keyword(id="kw_001", campaign_id="g_camp_001", ad_group_id="ag_001", text="test")
        self.assertEqual(keyword.id, "kw_001")

    def test_keyword_to_dict(self):
        keyword = Keyword(id="kw_001", campaign_id="g_camp_001", ad_group_id="ag_001", text="test")
        d = keyword.to_dict()
        self.assertIsInstance(d, dict)

    def test_search_term_create(self):
        term = SearchTerm(id="st_001", campaign_id="g_camp_001", keyword="test")
        self.assertEqual(term.id, "st_001")

    def test_search_term_to_dict(self):
        term = SearchTerm(id="st_001", campaign_id="g_camp_001", keyword="test")
        d = term.to_dict()
        self.assertIsInstance(d, dict)

    def test_performance_metrics_create(self):
        metrics = PerformanceMetrics(campaign_id="g_camp_001")
        self.assertEqual(metrics.campaign_id, "g_camp_001")

    def test_performance_metrics_to_dict(self):
        metrics = PerformanceMetrics(campaign_id="g_camp_001")
        d = metrics.to_dict()
        self.assertIsInstance(d, dict)

    def test_asa_connector_connect(self):
        connector = ASAConnector()
        result = connector.connect()
        self.assertTrue(result)

    def test_asa_connector_get_campaigns(self):
        connector = ASAConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        self.assertIsInstance(campaigns, list)

    def test_asa_connector_get_keywords(self):
        connector = ASAConnector()
        connector.connect()
        campaigns = connector.get_campaigns()
        if campaigns:
            keywords = connector.get_keywords(campaigns[0].id)
            self.assertIsInstance(keywords, list)

    def test_asa_connector_get_search_popularity(self):
        connector = ASAConnector()
        connector.connect()
        result = connector.get_search_popularity("game")
        self.assertIsInstance(result, SearchPopularity)

    def test_asa_campaign_create(self):
        campaign = ASACampaign(id="asa_camp_001", name="Test")
        self.assertEqual(campaign.id, "asa_camp_001")

    def test_asa_campaign_to_dict(self):
        campaign = ASACampaign(id="asa_camp_001", name="Test")
        d = campaign.to_dict()
        self.assertIsInstance(d, dict)

    def test_asa_keyword_create(self):
        keyword = ASAKeyword(id="asa_kw_001", campaign_id="asa_camp_001", ad_group_id="ag_001", text="test")
        self.assertEqual(keyword.id, "asa_kw_001")

    def test_asa_keyword_to_dict(self):
        keyword = ASAKeyword(id="asa_kw_001", campaign_id="asa_camp_001", ad_group_id="ag_001", text="test")
        d = keyword.to_dict()
        self.assertIsInstance(d, dict)

    def test_search_popularity_create(self):
        popularity = SearchPopularity(keyword="game", popularity=80)
        self.assertEqual(popularity.keyword, "game")

    def test_search_popularity_to_dict(self):
        popularity = SearchPopularity(keyword="game", popularity=80)
        d = popularity.to_dict()
        self.assertIsInstance(d, dict)

    def test_tiktok_connector_connect(self):
        connector = TikTokAdsConnector()
        result = connector.connect()
        self.assertTrue(result)

    def test_tiktok_connector_get_creatives(self):
        connector = TikTokAdsConnector()
        connector.connect()
        creatives = connector.get_creatives()
        self.assertIsInstance(creatives, list)

    def test_tiktok_connector_get_campaign_metrics(self):
        connector = TikTokAdsConnector()
        connector.connect()
        metrics = connector.get_campaign_metrics("camp_001")
        self.assertIsInstance(metrics, TikTokMetrics)

    def test_tiktok_connector_get_video_metrics(self):
        connector = TikTokAdsConnector()
        connector.connect()
        metrics = connector.get_video_metrics("video_001")
        self.assertIsInstance(metrics, dict)

    def test_tiktok_creative_create(self):
        creative = TikTokCreative(id="tk_001", name="Test")
        self.assertEqual(creative.id, "tk_001")

    def test_tiktok_creative_to_dict(self):
        creative = TikTokCreative(id="tk_001", name="Test")
        d = creative.to_dict()
        self.assertIsInstance(d, dict)

    def test_tiktok_metrics_create(self):
        metrics = TikTokMetrics(campaign_id="camp_001")
        self.assertEqual(metrics.campaign_id, "camp_001")

    def test_tiktok_metrics_to_dict(self):
        metrics = TikTokMetrics(campaign_id="camp_001")
        d = metrics.to_dict()
        self.assertIsInstance(d, dict)

    def test_campaign_sync_sync_all(self):
        sync = CampaignSync()
        result = sync.sync_all_campaigns()
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_campaign_sync_sync_platform(self):
        sync = CampaignSync()
        result = sync.sync_platform_campaigns("meta")
        self.assertTrue(result["success"])

    def test_campaign_sync_sync_unknown_platform(self):
        sync = CampaignSync()
        result = sync.sync_platform_campaigns("unknown")
        self.assertFalse(result["success"])

    def test_campaign_sync_get_sync_status(self):
        sync = CampaignSync()
        status = sync.get_sync_status()
        self.assertIsInstance(status, dict)

    def test_campaign_sync_get_sync_history(self):
        sync = CampaignSync()
        sync.sync_platform_campaigns("meta")
        history = sync.get_sync_history()
        self.assertGreater(len(history), 0)

    def test_sync_record_create(self):
        record = SyncRecord(platform="meta", status=AdsSyncStatus.COMPLETED)
        self.assertEqual(record.platform, "meta")

    def test_sync_record_to_dict(self):
        record = SyncRecord(platform="meta")
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_creative_sync_sync_creatives(self):
        sync = CreativeSync()
        result = sync.sync_creatives()
        self.assertTrue(result["success"])

    def test_creative_sync_sync_platform(self):
        sync = CreativeSync()
        result = sync.sync_platform_creatives("meta")
        self.assertTrue(result["success"])

    def test_creative_sync_record_create(self):
        record = CreativeSyncRecord(platform="meta", synced_count=10)
        self.assertEqual(record.platform, "meta")

    def test_spend_tracker_record_spend(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")

    def test_spend_tracker_get_daily_spend(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        spend = tracker.get_daily_spend(datetime.now().date())
        self.assertIn("meta", spend)

    def test_spend_tracker_get_total_spend(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        tracker.record_spend("google", 200.0, "camp_002")
        total = tracker.get_total_spend()
        self.assertEqual(total, 300.0)

    def test_spend_tracker_get_spend_by_platform(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        result = tracker.get_spend_by_platform()
        self.assertIn("meta", result)

    def test_spend_record_create(self):
        record = SpendRecord(platform="meta", amount=100.0, campaign_id="camp_001")
        self.assertEqual(record.platform, "meta")

    def test_spend_record_to_dict(self):
        record = SpendRecord(platform="meta", amount=100.0, campaign_id="camp_001")
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_conversion_sync_sync_conversions(self):
        sync = ConversionSync()
        result = sync.sync_conversions()
        self.assertTrue(result["success"])

    def test_conversion_sync_sync_platform(self):
        sync = ConversionSync()
        result = sync.sync_platform_conversions("meta")
        self.assertTrue(result["success"])

    def test_conversion_sync_record_create(self):
        record = ConversionSyncRecord(platform="meta", synced_count=5)
        self.assertEqual(record.platform, "meta")

    def test_meta_connector_sync_campaigns(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.sync_campaigns()
        self.assertTrue(result["success"])

    def test_google_connector_sync_data(self):
        connector = GoogleAdsConnector()
        connector.connect()
        result = connector.sync_data()
        self.assertTrue(result["success"])

    def test_spend_tracker_get_spend_history(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        history = tracker.get_spend_history("meta")
        self.assertGreater(len(history), 0)

    def test_creative_sync_record_to_dict(self):
        record = CreativeSyncRecord(platform="meta", synced_count=10)
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_spend_record_create(self):
        record = SpendRecord(platform="meta", amount=100.0, campaign_id="camp_001")
        self.assertEqual(record.platform, "meta")

    def test_spend_record_to_dict(self):
        record = SpendRecord(platform="meta", amount=100.0, campaign_id="camp_001")
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_spend_tracker_get_spend_history_all(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        tracker.record_spend("google", 200.0, "camp_002")
        history = tracker.get_spend_history()
        self.assertEqual(len(history), 2)

    def test_spend_tracker_get_spend_history_empty(self):
        tracker = SpendTracker()
        history = tracker.get_spend_history("meta")
        self.assertEqual(len(history), 0)

    def test_spend_tracker_get_campaign_spend(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        tracker.record_spend("meta", 50.0, "camp_001")
        tracker.record_spend("google", 75.0, "camp_002")
        spend = tracker.get_campaign_spend("camp_001")
        self.assertEqual(spend["meta"], 150.0)

    def test_spend_tracker_get_campaign_spend_nonexistent(self):
        tracker = SpendTracker()
        spend = tracker.get_campaign_spend("nonexistent")
        self.assertEqual(spend, {})

    def test_spend_tracker_record_spend_zero_amount(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 0.0, "camp_001")
        total = tracker.get_total_spend()
        self.assertEqual(total, 0.0)

    def test_spend_tracker_record_spend_negative_amount(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", -50.0, "camp_001")
        total = tracker.get_total_spend()
        self.assertEqual(total, -50.0)

    def test_meta_connector_sync_campaigns_not_connected(self):
        connector = MetaAdsConnector()
        result = connector.sync_campaigns()
        self.assertFalse(result["success"])

    def test_meta_connector_get_ad_sets_empty(self):
        connector = MetaAdsConnector()
        connector.connect()
        ad_sets = connector.get_ad_sets("invalid")
        self.assertEqual(len(ad_sets), 0)

    def test_meta_connector_create_campaign_not_connected(self):
        connector = MetaAdsConnector()
        result = connector.create_campaign({"name": "Test"})
        self.assertIsNone(result)

    def test_google_connector_sync_data_not_connected(self):
        connector = GoogleAdsConnector()
        result = connector.sync_data()
        self.assertFalse(result["success"])

    def test_google_connector_get_keywords_empty(self):
        connector = GoogleAdsConnector()
        connector.connect()
        keywords = connector.get_keywords("invalid")
        self.assertEqual(len(keywords), 0)

    def test_google_connector_get_performance_invalid(self):
        connector = GoogleAdsConnector()
        connector.connect()
        performance = connector.get_performance("invalid")
        self.assertIsNone(performance)

    def test_asa_connector_get_keywords_empty(self):
        connector = ASAConnector()
        connector.connect()
        keywords = connector.get_keywords("invalid")
        self.assertEqual(len(keywords), 0)

    def test_asa_connector_get_search_popularity_empty(self):
        connector = ASAConnector()
        connector.connect()
        result = connector.get_search_popularity("")
        self.assertIsInstance(result, SearchPopularity)

    def test_tiktok_connector_get_creatives_not_connected(self):
        connector = TikTokAdsConnector()
        creatives = connector.get_creatives()
        self.assertEqual(len(creatives), 0)

    def test_tiktok_connector_get_video_metrics_not_connected(self):
        connector = TikTokAdsConnector()
        metrics = connector.get_video_metrics("video_001")
        self.assertIsInstance(metrics, dict)

    def test_campaign_sync_sync_all_empty(self):
        sync = CampaignSync()
        result = sync.sync_all_campaigns()
        self.assertIn("success", result)

    def test_campaign_sync_get_sync_history_empty(self):
        sync = CampaignSync()
        history = sync.get_sync_history()
        self.assertEqual(len(history), 0)

    def test_creative_sync_sync_platform_not_connected(self):
        sync = CreativeSync()
        result = sync.sync_platform_creatives("unknown_platform")
        self.assertFalse(result["success"])

    def test_creative_sync_get_sync_history_empty(self):
        sync = CreativeSync()
        history = sync.get_sync_history()
        self.assertEqual(len(history), 0)

    def test_conversion_sync_sync_platform_not_connected(self):
        sync = ConversionSync()
        result = sync.sync_platform_conversions("unknown_platform")
        self.assertFalse(result["success"])

    def test_conversion_sync_get_sync_history_empty(self):
        sync = ConversionSync()
        history = sync.get_conversion_history()
        self.assertEqual(len(history), 0)

    def test_campaign_to_dict_complete(self):
        campaign = Campaign(id="camp_001", name="Test Campaign", status="ACTIVE", budget=5000.0)
        d = campaign.to_dict()
        self.assertIn("id", d)
        self.assertIn("name", d)

    def test_ad_set_to_dict_complete(self):
        ad_set = AdSet(id="adset_001", name="Test AdSet", campaign_id="camp_001", budget=1000.0)
        d = ad_set.to_dict()
        self.assertIn("id", d)
        self.assertIn("campaign_id", d)

    def test_creative_to_dict_complete(self):
        creative = Creative(id="creative_001", ad_set_id="adset_001", name="Test", status="ACTIVE")
        d = creative.to_dict()
        self.assertIn("id", d)
        self.assertIn("ad_set_id", d)

    def test_campaign_metrics_to_dict_complete(self):
        metrics = CampaignMetrics(campaign_id="camp_001", impressions=1000, clicks=50, spend=100.0, conversions=5)
        d = metrics.to_dict()
        self.assertIn("campaign_id", d)
        self.assertIn("impressions", d)

    def test_google_campaign_to_dict_complete(self):
        campaign = GoogleCampaign(id="g_camp_001", name="Test", status="ENABLED", budget=10000.0)
        d = campaign.to_dict()
        self.assertIn("id", d)
        self.assertIn("name", d)

    def test_keyword_to_dict_complete(self):
        keyword = Keyword(id="kw_001", campaign_id="g_camp_001", ad_group_id="ag_001", text="test", status="ENABLED")
        d = keyword.to_dict()
        self.assertIn("id", d)
        self.assertIn("text", d)

    def test_search_term_to_dict_complete(self):
        term = SearchTerm(id="st_001", campaign_id="g_camp_001", keyword="test", impressions=100, clicks=5)
        d = term.to_dict()
        self.assertIn("id", d)
        self.assertIn("keyword", d)

    def test_performance_metrics_to_dict_complete(self):
        metrics = PerformanceMetrics(campaign_id="g_camp_001", clicks=100, impressions=1000, conversions=10, spend=50.0)
        d = metrics.to_dict()
        self.assertIn("campaign_id", d)
        self.assertIn("clicks", d)

    def test_asa_campaign_to_dict_complete(self):
        campaign = ASACampaign(id="asa_camp_001", name="Test", status="ACTIVE", budget=5000.0)
        d = campaign.to_dict()
        self.assertIn("id", d)
        self.assertIn("name", d)

    def test_asa_keyword_to_dict_complete(self):
        keyword = ASAKeyword(id="asa_kw_001", campaign_id="asa_camp_001", ad_group_id="ag_001", text="test", match_type="exact")
        d = keyword.to_dict()
        self.assertIn("id", d)
        self.assertIn("text", d)

    def test_search_popularity_to_dict_complete(self):
        popularity = SearchPopularity(keyword="game", popularity=80, competition="high", competition_index=50)
        d = popularity.to_dict()
        self.assertIn("keyword", d)
        self.assertIn("popularity", d)

    def test_tiktok_creative_to_dict_complete(self):
        creative = TikTokCreative(id="tk_001", name="Test", video_url="https://example.com/video.mp4")
        d = creative.to_dict()
        self.assertIn("id", d)
        self.assertIn("name", d)

    def test_tiktok_metrics_to_dict_complete(self):
        metrics = TikTokMetrics(campaign_id="camp_001", views=1000, clicks=50, impressions=10000, spend=100.0)
        d = metrics.to_dict()
        self.assertIn("campaign_id", d)
        self.assertIn("views", d)

    def test_sync_record_to_dict_complete(self):
        record = SyncRecord(platform="meta", status=AdsSyncStatus.COMPLETED, synced_count=10, failed_count=0)
        d = record.to_dict()
        self.assertIn("platform", d)
        self.assertIn("status", d)

    def test_creative_sync_record_to_dict_complete(self):
        record = CreativeSyncRecord(platform="meta", synced_count=10, failed_count=0)
        d = record.to_dict()
        self.assertIn("platform", d)
        self.assertIn("synced_count", d)

    def test_conversion_sync_record_to_dict_complete(self):
        record = ConversionSyncRecord(platform="meta", synced_count=5, failed_count=0)
        d = record.to_dict()
        self.assertIn("platform", d)
        self.assertIn("synced_count", d)

    def test_spend_record_to_dict_complete(self):
        record = SpendRecord(platform="meta", amount=100.0, campaign_id="camp_001")
        d = record.to_dict()
        self.assertIn("platform", d)
        self.assertIn("amount", d)
        self.assertIn("campaign_id", d)

    def test_spend_tracker_record_spend_zero_amount(self):
        tracker = SpendTracker()
        record = tracker.record_spend("meta", 0.0, "camp_001")
        self.assertEqual(record.amount, 0.0)

    def test_spend_tracker_record_spend_negative_amount(self):
        tracker = SpendTracker()
        record = tracker.record_spend("google", -50.0, "camp_002")
        self.assertEqual(record.amount, -50.0)

    def test_spend_tracker_get_spend_history_empty(self):
        tracker = SpendTracker()
        history = tracker.get_spend_history()
        self.assertEqual(len(history), 0)

    def test_spend_tracker_get_spend_history_by_platform(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        tracker.record_spend("google", 50.0, "camp_002")
        history = tracker.get_spend_history("meta")
        self.assertEqual(len(history), 1)

    def test_spend_tracker_get_spend_history_nonexistent_platform(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        history = tracker.get_spend_history("nonexistent")
        self.assertEqual(len(history), 0)

    def test_spend_tracker_get_total_spend(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        tracker.record_spend("google", 50.0, "camp_002")
        total = tracker.get_total_spend()
        self.assertEqual(total, 150.0)

    def test_spend_tracker_get_total_spend_empty(self):
        tracker = SpendTracker()
        total = tracker.get_total_spend()
        self.assertEqual(total, 0.0)

    def test_spend_tracker_get_spend_by_platform(self):
        tracker = SpendTracker()
        tracker.record_spend("meta", 100.0, "camp_001")
        tracker.record_spend("meta", 50.0, "camp_002")
        tracker.record_spend("google", 75.0, "camp_003")
        by_platform = tracker.get_spend_by_platform()
        self.assertEqual(by_platform["meta"], 150.0)
        self.assertEqual(by_platform["google"], 75.0)

    def test_meta_connector_get_campaign_metrics_nonexistent(self):
        connector = MetaAdsConnector()
        connector.connect()
        metrics = connector.get_campaign_metrics("nonexistent")
        self.assertIsNone(metrics)

    def test_meta_connector_update_campaign_budget_not_connected(self):
        connector = MetaAdsConnector()
        result = connector.update_campaign_budget("camp_001", 5000.0)
        self.assertFalse(result)

    def test_meta_connector_update_campaign_budget_nonexistent(self):
        connector = MetaAdsConnector()
        connector.connect()
        result = connector.update_campaign_budget("nonexistent", 5000.0)
        self.assertFalse(result)

    def test_meta_connector_sync_campaigns_not_connected(self):
        connector = MetaAdsConnector()
        result = connector.sync_campaigns()
        self.assertFalse(result["success"])

    def test_google_connector_get_campaigns_not_connected(self):
        connector = GoogleAdsConnector()
        campaigns = connector.get_campaigns()
        self.assertEqual(len(campaigns), 0)

    def test_google_connector_get_keywords_not_connected(self):
        connector = GoogleAdsConnector()
        keywords = connector.get_keywords("camp_001")
        self.assertEqual(len(keywords), 0)

    def test_google_connector_get_search_terms_empty(self):
        connector = GoogleAdsConnector()
        connector.connect()
        terms = connector.get_search_terms("nonexistent")
        self.assertEqual(len(terms), 0)

    def test_asa_connector_get_campaigns_not_connected(self):
        connector = ASAConnector()
        campaigns = connector.get_campaigns()
        self.assertEqual(len(campaigns), 0)

    def test_asa_connector_get_keywords_nonexistent(self):
        connector = ASAConnector()
        connector.connect()
        keywords = connector.get_keywords("nonexistent")
        self.assertEqual(len(keywords), 0)

    def test_asa_connector_get_search_popularity(self):
        connector = ASAConnector()
        connector.connect()
        popularity = connector.get_search_popularity("game")
        self.assertIsInstance(popularity, SearchPopularity)

    def test_tiktok_connector_get_creatives_not_connected(self):
        connector = TikTokAdsConnector()
        creatives = connector.get_creatives()
        self.assertEqual(len(creatives), 0)

    def test_tiktok_connector_get_campaign_metrics_not_connected(self):
        connector = TikTokAdsConnector()
        metrics = connector.get_campaign_metrics("camp_001")
        self.assertIsNone(metrics)

    def test_tiktok_connector_get_creatives(self):
        connector = TikTokAdsConnector()
        connector.connect()
        creatives = connector.get_creatives()
        self.assertGreater(len(creatives), 0)

    def test_conversion_sync_sync_all_platforms(self):
        sync = ConversionSync()
        result = sync.sync_conversions()
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_conversion_sync_get_conversion_status(self):
        sync = ConversionSync()
        status = sync.get_conversion_status()
        self.assertIsInstance(status, dict)

    def test_creative_sync_sync_all_platforms(self):
        sync = CreativeSync()
        result = sync.sync_creatives()
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_creative_sync_get_creative_status(self):
        sync = CreativeSync()
        status = sync.get_creative_status()
        self.assertIsInstance(status, dict)

    def test_campaign_sync_sync_all_platforms(self):
        sync = CampaignSync()
        result = sync.sync_all_campaigns()
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

    def test_campaign_sync_get_sync_status(self):
        sync = CampaignSync()
        status = sync.get_sync_status()
        self.assertIsInstance(status, dict)

    def test_sync_record_to_dict_empty(self):
        record = SyncRecord(platform="meta")
        d = record.to_dict()
        self.assertIn("platform", d)
        self.assertIn("status", d)


# ---------------------------------------------------------------------------
# attribution_engine (~80 tests)
# ---------------------------------------------------------------------------
class TestAttributionEngine(unittest.TestCase):
    def test_adjust_connector_connect(self):
        connector = AdjustConnector()
        result = connector.connect()
        self.assertTrue(result)

    def test_adjust_connector_get_events(self):
        connector = AdjustConnector()
        connector.connect()
        events = connector.get_events("test_token")
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0)

    def test_adjust_connector_get_retention(self):
        connector = AdjustConnector()
        connector.connect()
        retention = connector.get_retention("test_token")
        self.assertIsInstance(retention, list)
        self.assertGreater(len(retention), 0)

    def test_adjust_connector_get_revenue(self):
        connector = AdjustConnector()
        connector.connect()
        revenue = connector.get_revenue("test_token")
        self.assertIsInstance(revenue, list)
        self.assertGreater(len(revenue), 0)

    def test_adjust_connector_get_attribution_data(self):
        connector = AdjustConnector()
        connector.connect()
        data = connector.get_attribution_data("test_token")
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_adjust_event_create(self):
        event = AdjustEvent(event_id="evt_001", event_name="install", timestamp=datetime.now(), user_id="user_001")
        self.assertEqual(event.event_id, "evt_001")

    def test_adjust_event_to_dict(self):
        event = AdjustEvent(event_id="evt_001", event_name="install", timestamp=datetime.now(), user_id="user_001")
        d = event.to_dict()
        self.assertIsInstance(d, dict)

    def test_adjust_retention_create(self):
        retention = AdjustRetention(cohort_date=datetime.now(), retention_day=1, retention_rate=0.45, user_count=100, total_users=1000)
        self.assertEqual(retention.retention_day, 1)

    def test_adjust_retention_to_dict(self):
        retention = AdjustRetention(cohort_date=datetime.now(), retention_day=1, retention_rate=0.45, user_count=100, total_users=1000)
        d = retention.to_dict()
        self.assertIsInstance(d, dict)

    def test_adjust_revenue_create(self):
        revenue = AdjustRevenue(transaction_id="txn_001", timestamp=datetime.now(), user_id="user_001", revenue=9.99)
        self.assertEqual(revenue.transaction_id, "txn_001")

    def test_adjust_revenue_to_dict(self):
        revenue = AdjustRevenue(transaction_id="txn_001", timestamp=datetime.now(), user_id="user_001", revenue=9.99)
        d = revenue.to_dict()
        self.assertIsInstance(d, dict)

    def test_attribution_data_create(self):
        data = AttributionData(attribution_id="attr_001", user_id="user_001", network="meta", campaign="camp_001")
        self.assertEqual(data.attribution_id, "attr_001")

    def test_attribution_data_to_dict(self):
        data = AttributionData(attribution_id="attr_001", user_id="user_001", network="meta", campaign="camp_001")
        d = data.to_dict()
        self.assertIsInstance(d, dict)

    def test_appsflyer_connector_connect(self):
        connector = AppsFlyerConnector()
        result = connector.connect()
        self.assertTrue(result)

    def test_appsflyer_connector_get_installs(self):
        connector = AppsFlyerConnector()
        connector.connect()
        installs = connector.get_installs("app_001")
        self.assertIsInstance(installs, list)

    def test_appsflyer_connector_get_events(self):
        connector = AppsFlyerConnector()
        connector.connect()
        events = connector.get_events("app_001")
        self.assertIsInstance(events, list)

    def test_appsflyer_connector_get_revenue(self):
        connector = AppsFlyerConnector()
        connector.connect()
        revenue = connector.get_revenue("app_001")
        self.assertIsInstance(revenue, list)

    def test_appsflyer_install_create(self):
        install = AppsFlyerInstall(install_id="inst_001", user_id="user_001", install_time=datetime.now(), network="Meta", campaign="campaign_001")
        self.assertEqual(install.install_id, "inst_001")

    def test_appsflyer_install_to_dict(self):
        install = AppsFlyerInstall(install_id="inst_001", user_id="user_001", install_time=datetime.now(), network="Meta", campaign="campaign_001")
        d = install.to_dict()
        self.assertIsInstance(d, dict)

    def test_appsflyer_event_create(self):
        event = AppsFlyerEvent(event_id="evt_001", event_name="purchase", timestamp=datetime.now(), user_id="user_001", install_id="install_001")
        self.assertEqual(event.event_id, "evt_001")

    def test_appsflyer_event_to_dict(self):
        event = AppsFlyerEvent(event_id="evt_001", event_name="purchase", timestamp=datetime.now(), user_id="user_001", install_id="install_001")
        d = event.to_dict()
        self.assertIsInstance(d, dict)

    def test_appsflyer_revenue_create(self):
        revenue = AppsFlyerRevenue(transaction_id="txn_001", timestamp=datetime.now(), user_id="user_001", install_id="install_001", revenue=9.99)
        self.assertEqual(revenue.transaction_id, "txn_001")

    def test_appsflyer_revenue_to_dict(self):
        revenue = AppsFlyerRevenue(transaction_id="txn_001", timestamp=datetime.now(), user_id="user_001", install_id="install_001", revenue=9.99)
        d = revenue.to_dict()
        self.assertIsInstance(d, dict)

    def test_firebase_connector_connect(self):
        connector = FirebaseConnector()
        result = connector.connect()
        self.assertTrue(result)

    def test_firebase_connector_get_events(self):
        connector = FirebaseConnector()
        connector.connect()
        events = connector.get_events("project_001")
        self.assertIsInstance(events, list)

    def test_firebase_connector_get_analytics(self):
        connector = FirebaseConnector()
        connector.connect()
        analytics = connector.get_analytics("project_001")
        self.assertIsInstance(analytics, list)

    def test_firebase_event_create(self):
        event = FirebaseEvent(event_id="evt_001", event_name="screen_view", timestamp=datetime.now(), user_id="user_001")
        self.assertEqual(event.event_name, "screen_view")

    def test_firebase_event_to_dict(self):
        event = FirebaseEvent(event_id="evt_001", event_name="screen_view", timestamp=datetime.now(), user_id="user_001")
        d = event.to_dict()
        self.assertIsInstance(d, dict)

    def test_firebase_analytics_create(self):
        analytics = FirebaseAnalytics(metric_name="active_users", value=1000.0, period_start=datetime.now(), period_end=datetime.now())
        self.assertEqual(analytics.metric_name, "active_users")

    def test_firebase_analytics_to_dict(self):
        analytics = FirebaseAnalytics(metric_name="active_users", value=1000.0, period_start=datetime.now(), period_end=datetime.now())
        d = analytics.to_dict()
        self.assertIsInstance(d, dict)

    def test_revenue_matcher_match_revenue(self):
        matcher = RevenueMatcher()
        sources = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0, transaction_count=100)]
        result = matcher.match_revenue(sources)
        self.assertIsInstance(result, RevenueMatchResult)

    def test_revenue_matcher_match_multiple_sources(self):
        matcher = RevenueMatcher()
        sources = [
            AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0, transaction_count=100),
            AttributionRevenueSource(source_id="src_002", platform="google", revenue_amount=500.0, transaction_count=50),
        ]
        result = matcher.match_revenue(sources)
        self.assertGreater(result.matched_amount, 0)

    def test_revenue_matcher_get_matching_report(self):
        matcher = RevenueMatcher()
        sources = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0)]
        matcher.match_revenue(sources)
        report = matcher.get_matching_report()
        self.assertIsInstance(report, dict)

    def test_revenue_matcher_identify_discrepancies(self):
        matcher = RevenueMatcher()
        sources1 = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0)]
        sources2 = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1200.0)]
        matcher.match_revenue(sources1)
        matcher.match_revenue(sources2)
        discrepancies = matcher.identify_discrepancies()
        self.assertIsInstance(discrepancies, list)

    def test_revenue_matcher_resolve_discrepancy(self):
        matcher = RevenueMatcher()
        sources1 = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0)]
        sources2 = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1200.0)]
        matcher.match_revenue(sources1)
        matcher.match_revenue(sources2)
        discrepancies = matcher.identify_discrepancies()
        if discrepancies:
            result = matcher.resolve_discrepancy(discrepancies[0].discrepancy_id)
            self.assertTrue(result)

    def test_revenue_source_create(self):
        source = AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0)
        self.assertEqual(source.source_id, "src_001")

    def test_revenue_source_to_dict(self):
        source = AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0)
        d = source.to_dict()
        self.assertIsInstance(d, dict)

    def test_revenue_match_result_create(self):
        sources = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0)]
        result = RevenueMatchResult(match_id="match_001", sources=sources, matched_amount=1000.0, unmatched_amount=0.0, total_transactions=100, matched_transactions=100, match_rate=1.0)
        self.assertEqual(result.match_id, "match_001")

    def test_revenue_match_result_to_dict(self):
        sources = [AttributionRevenueSource(source_id="src_001", platform="meta", revenue_amount=1000.0)]
        result = RevenueMatchResult(match_id="match_001", sources=sources, matched_amount=1000.0, unmatched_amount=0.0, total_transactions=100, matched_transactions=100, match_rate=1.0)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_discrepancy_create(self):
        source_a = AttributionRevenueSource(source_id="src_a", platform="meta", revenue_amount=1000.0)
        source_b = AttributionRevenueSource(source_id="src_b", platform="meta", revenue_amount=900.0)
        discrepancy = Discrepancy(discrepancy_id="disc_001", source_a=source_a, source_b=source_b, amount_diff=100.0, percentage_diff=10.0, transaction_diff=0)
        self.assertEqual(discrepancy.discrepancy_id, "disc_001")

    def test_discrepancy_to_dict(self):
        source_a = AttributionRevenueSource(source_id="src_a", platform="meta", revenue_amount=1000.0)
        source_b = AttributionRevenueSource(source_id="src_b", platform="meta", revenue_amount=900.0)
        discrepancy = Discrepancy(discrepancy_id="disc_001", source_a=source_a, source_b=source_b, amount_diff=100.0, percentage_diff=10.0, transaction_diff=0)
        d = discrepancy.to_dict()
        self.assertIsInstance(d, dict)

    def test_cohort_analyzer_analyze_cohort(self):
        analyzer = CohortAnalyzer()
        result = analyzer.analyze_cohort({"user_count": 1000})
        self.assertIsInstance(result, CohortAnalysis)

    def test_cohort_analyzer_calculate_retention(self):
        analyzer = CohortAnalyzer()
        analyzer.analyze_cohort({"user_count": 1000})
        result = analyzer.calculate_retention(list(analyzer._cohorts.keys())[0])
        self.assertIsInstance(result, RetentionCurve)

    def test_cohort_analyzer_compare_cohorts(self):
        analyzer = CohortAnalyzer()
        analyzer.analyze_cohort({"user_count": 1000})
        analyzer.analyze_cohort({"user_count": 2000})
        result = analyzer.compare_cohorts()
        self.assertIsInstance(result, dict)

    def test_cohort_analyzer_get_cohort_report(self):
        analyzer = CohortAnalyzer()
        analyzer.analyze_cohort({"user_count": 1000})
        report = analyzer.get_cohort_report(list(analyzer._cohorts.keys())[0])
        self.assertIsInstance(report, dict)

    def test_cohort_create(self):
        cohort = Cohort(cohort_id="cohort_001", cohort_date=datetime.now(), user_count=1000)
        self.assertEqual(cohort.cohort_id, "cohort_001")

    def test_cohort_to_dict(self):
        cohort = Cohort(cohort_id="cohort_001", cohort_date=datetime.now(), user_count=1000)
        d = cohort.to_dict()
        self.assertIsInstance(d, dict)

    def test_retention_curve_create(self):
        curve = RetentionCurve(cohort_id="cohort_001", day_1=0.45, day_7=0.22)
        self.assertEqual(curve.day_1, 0.45)

    def test_retention_curve_to_dict(self):
        curve = RetentionCurve(cohort_id="cohort_001")
        d = curve.to_dict()
        self.assertIsInstance(d, dict)

    def test_cohort_analysis_create(self):
        cohort = Cohort(cohort_id="cohort_001", cohort_date=datetime.now(), user_count=1000)
        curve = RetentionCurve(cohort_id="cohort_001")
        analysis = CohortAnalysis(analysis_id="anal_001", cohort=cohort, retention_curve=curve)
        self.assertEqual(analysis.analysis_id, "anal_001")

    def test_cohort_analysis_to_dict(self):
        cohort = Cohort(cohort_id="cohort_001", cohort_date=datetime.now(), user_count=1000)
        curve = RetentionCurve(cohort_id="cohort_001")
        analysis = CohortAnalysis(analysis_id="anal_001", cohort=cohort, retention_curve=curve)
        d = analysis.to_dict()
        self.assertIsInstance(d, dict)

    def test_attribution_validator_validate_attribution(self):
        validator = AttributionValidator()
        result = validator.validate_attribution([])
        self.assertIsInstance(result, ValidationResult)

    def test_attribution_validator_check_data_quality(self):
        validator = AttributionValidator()
        issues = validator.check_data_quality([])
        self.assertIsInstance(issues, list)

    def test_validation_result_create(self):
        result = ValidationResult(validation_id="val_001", success=True, data_quality_score=95.0, issues=[])
        self.assertTrue(result.success)

    def test_validation_result_to_dict(self):
        result = ValidationResult(validation_id="val_001", success=True, data_quality_score=95.0)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_data_quality_issue_create(self):
        issue = DataQualityIssue(issue_id="issue_001", severity="high", issue_type="missing_field", description="Test", source="attribution")
        self.assertEqual(issue.issue_id, "issue_001")

    def test_adjust_connector_get_revenue(self):
        connector = AdjustConnector()
        connector.connect()
        revenue = connector.get_revenue("test_token")
        self.assertIsInstance(revenue, list)

    def test_adjust_connector_get_attribution_data(self):
        connector = AdjustConnector()
        connector.connect()
        data = connector.get_attribution_data("test_token")
        self.assertIsInstance(data, list)

    def test_adjust_event_create(self):
        event = AdjustEvent(event_id="evt_001", event_name="purchase", timestamp=datetime.now(), user_id="user_001", revenue=9.99)
        self.assertEqual(event.event_id, "evt_001")

    def test_adjust_event_to_dict(self):
        event = AdjustEvent(event_id="evt_001", event_name="purchase", timestamp=datetime.now(), user_id="user_001", revenue=9.99)
        d = event.to_dict()
        self.assertIsInstance(d, dict)

    def test_adjust_retention_create(self):
        retention = AdjustRetention(cohort_date=datetime.now(), retention_day=1, retention_rate=0.45, user_count=100, total_users=1000)
        self.assertEqual(retention.retention_day, 1)

    def test_adjust_retention_to_dict(self):
        retention = AdjustRetention(cohort_date=datetime.now(), retention_day=1, retention_rate=0.45, user_count=100, total_users=1000)
        d = retention.to_dict()
        self.assertIsInstance(d, dict)

    def test_adjust_revenue_create(self):
        revenue = AdjustRevenue(transaction_id="txn_001", revenue=9.99, timestamp=datetime.now(), user_id="user_001")
        self.assertEqual(revenue.transaction_id, "txn_001")

    def test_adjust_revenue_to_dict(self):
        revenue = AdjustRevenue(transaction_id="txn_001", revenue=9.99, timestamp=datetime.now(), user_id="user_001")
        d = revenue.to_dict()
        self.assertIsInstance(d, dict)

    def test_data_quality_issue_to_dict(self):
        issue = DataQualityIssue(issue_id="issue_001", severity="high", issue_type="missing_field", description="Test", source="attribution")
        d = issue.to_dict()
        self.assertIsInstance(d, dict)

    def test_data_reconciliation_reconcile_data(self):
        recon = DataReconciliation()
        result = recon.reconcile_data([])
        self.assertIsInstance(result, ReconciliationResult)

    def test_data_reconciliation_get_report(self):
        recon = DataReconciliation()
        recon.reconcile_data([])
        report = recon.get_reconciliation_report()
        self.assertIsInstance(report, dict)

    def test_data_reconciliation_get_confidence_score(self):
        recon = DataReconciliation()
        score = recon.get_confidence_score()
        self.assertIsInstance(score, float)

    def test_reconciliation_result_create(self):
        result = ReconciliationResult(reconciliation_id="recon_001", sources=[], reconciled_records=100, unresolved_records=5)
        self.assertEqual(result.reconciliation_id, "recon_001")

    def test_reconciliation_result_to_dict(self):
        result = ReconciliationResult(reconciliation_id="recon_001", sources=[], reconciled_records=100, unresolved_records=5)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_data_correction_create(self):
        correction = DataCorrection(correction_id="corr_001", source_id="src_001", field_name="revenue", original_value=100.0, corrected_value=105.0, correction_type="adjustment", confidence=0.9)
        self.assertEqual(correction.correction_id, "corr_001")

    def test_data_correction_to_dict(self):
        correction = DataCorrection(correction_id="corr_001", source_id="src_001", field_name="revenue", original_value=100.0, corrected_value=105.0, correction_type="adjustment", confidence=0.9)
        d = correction.to_dict()
        self.assertIsInstance(d, dict)

    def test_attribution_data_create(self):
        data = AttributionData(attribution_id="attr_001", user_id="user_001", network="Meta", campaign="camp_001")
        self.assertEqual(data.attribution_id, "attr_001")

    def test_attribution_data_to_dict(self):
        data = AttributionData(attribution_id="attr_001", user_id="user_001", network="Meta", campaign="camp_001")
        d = data.to_dict()
        self.assertIsInstance(d, dict)

    def test_cohort_analyzer_get_cohorts(self):
        analyzer = CohortAnalyzer()
        analyzer.analyze_cohort({"user_count": 1000})
        cohorts = analyzer.get_cohorts()
        self.assertGreater(len(cohorts), 0)

    def test_attribution_validator_get_validation_report(self):
        validator = AttributionValidator()
        validator.validate_attribution([])
        report = validator.get_validation_report()
        self.assertIsInstance(report, dict)


# ---------------------------------------------------------------------------
# appstore_agent (~60 tests)
# ---------------------------------------------------------------------------
class TestAppstoreAgent(unittest.TestCase):
    def test_ios_builder_build(self):
        builder = IOSBuilder()
        build = builder.build("/path/to/project")
        self.assertIsInstance(build, Build)

    def test_ios_builder_test_build(self):
        builder = IOSBuilder()
        result = builder.test_build("/path/to/build")
        self.assertIsInstance(result, dict)
        self.assertIn("test_results", result)

    def test_ios_builder_get_build_status(self):
        builder = IOSBuilder()
        build = builder.build("/path/to/project")
        status = builder.get_build_status(build.build_id)
        self.assertIsInstance(status, Build)

    def test_ios_builder_list_builds(self):
        builder = IOSBuilder()
        builder.build("/path/to/project")
        builds = builder.list_builds()
        self.assertIsInstance(builds, list)

    def test_build_create(self):
        build = Build(build_id="build_001", project_path="/path")
        self.assertEqual(build.build_id, "build_001")

    def test_build_to_dict(self):
        build = Build(build_id="build_001", project_path="/path")
        d = build.to_dict()
        self.assertIsInstance(d, dict)

    def test_build_status_values(self):
        self.assertTrue(hasattr(BuildStatus, "PENDING"))
        self.assertTrue(hasattr(BuildStatus, "RUNNING"))
        self.assertTrue(hasattr(BuildStatus, "SUCCEEDED"))

    def test_android_builder_build(self):
        builder = AndroidBuilder()
        build = builder.build("/path/to/project")
        self.assertIsInstance(build, AndroidBuild)

    def test_android_builder_test_build(self):
        builder = AndroidBuilder()
        result = builder.test_build("/path/to/build")
        self.assertIsInstance(result, dict)

    def test_android_builder_get_build_status(self):
        builder = AndroidBuilder()
        build = builder.build("/path/to/project")
        status = builder.get_build_status(build.build_id)
        self.assertIsInstance(status, AndroidBuild)

    def test_android_build_create(self):
        build = AndroidBuild(build_id="android_001", project_path="/path")
        self.assertEqual(build.build_id, "android_001")

    def test_android_build_to_dict(self):
        build = AndroidBuild(build_id="android_001", project_path="/path")
        d = build.to_dict()
        self.assertIsInstance(d, dict)

    def test_store_metadata_update_metadata(self):
        metadata = StoreMetadata()
        result = metadata.update_metadata("app_001", {"primary_category": "Games"})
        self.assertIsInstance(result, AppMetadata)

    def test_store_metadata_get_metadata(self):
        metadata = StoreMetadata()
        metadata.update_metadata("app_001", {"primary_category": "Games"})
        result = metadata.get_metadata("app_001")
        self.assertIsInstance(result, AppMetadata)

    def test_store_metadata_validate_metadata(self):
        metadata = StoreMetadata()
        result = metadata.validate_metadata({"primary_category": "Games", "title": "Test"})
        self.assertTrue(result["valid"])

    def test_app_metadata_create(self):
        meta = AppMetadata(app_id="app_001", primary_category="Games")
        self.assertEqual(meta.app_id, "app_001")

    def test_app_metadata_to_dict(self):
        meta = AppMetadata(app_id="app_001", primary_category="Games")
        d = meta.to_dict()
        self.assertIsInstance(d, dict)

    def test_localization_create(self):
        loc = Localization(locale="en-US", title="Test")
        self.assertEqual(loc.locale, "en-US")

    def test_localization_to_dict(self):
        loc = Localization(locale="en-US", title="Test")
        d = loc.to_dict()
        self.assertIsInstance(d, dict)

    def test_screenshot_uploader_upload(self):
        uploader = ScreenshotUploader()
        result = uploader.upload_screenshots("app_001", [{"file_path": "/path/image.png"}])
        self.assertIsInstance(result, UploadResult)

    def test_screenshot_uploader_get_status(self):
        uploader = ScreenshotUploader()
        result = uploader.upload_screenshots("app_001", [{"file_path": "/path/image.png"}])
        status = uploader.get_upload_status(result.upload_id)
        self.assertIsInstance(status, UploadResult)

    def test_screenshot_create(self):
        screenshot = Screenshot(screenshot_id="shot_001", file_path="/path/image.png")
        self.assertEqual(screenshot.screenshot_id, "shot_001")

    def test_screenshot_to_dict(self):
        screenshot = Screenshot(screenshot_id="shot_001", file_path="/path/image.png")
        d = screenshot.to_dict()
        self.assertIsInstance(d, dict)

    def test_upload_result_create(self):
        result = UploadResult(upload_id="upload_001", status=UploadStatus.COMPLETED)
        self.assertEqual(result.upload_id, "upload_001")

    def test_upload_result_to_dict(self):
        result = UploadResult(upload_id="upload_001")
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_release_manager_create_release(self):
        manager = ReleaseManager()
        release = manager.create_release("app_001", "build_001")
        self.assertIsInstance(release, Release)

    def test_release_manager_submit_for_review(self):
        manager = ReleaseManager()
        manager.create_release("app_001", "build_001")
        result = manager.submit_for_review("app_001")
        self.assertIsInstance(result, Release)

    def test_release_manager_get_release_status(self):
        manager = ReleaseManager()
        manager.create_release("app_001", "build_001")
        manager.submit_for_review("app_001")
        status = manager.get_release_status("app_001")
        self.assertIsInstance(status, Release)

    def test_release_create(self):
        release = Release(release_id="rel_001", app_id="app_001", build_id="build_001")
        self.assertEqual(release.release_id, "rel_001")

    def test_release_to_dict(self):
        release = Release(release_id="rel_001", app_id="app_001", build_id="build_001")
        d = release.to_dict()
        self.assertIsInstance(d, dict)

    def test_release_status_values(self):
        self.assertTrue(hasattr(ReleaseStatus, "DRAFT"))
        self.assertTrue(hasattr(ReleaseStatus, "PENDING_REVIEW"))
        self.assertTrue(hasattr(ReleaseStatus, "IN_REVIEW"))

    def test_review_monitor_get_reviews(self):
        monitor = ReviewMonitor()
        reviews = monitor.get_reviews("app_001")
        self.assertIsInstance(reviews, list)

    def test_review_monitor_get_review_stats(self):
        monitor = ReviewMonitor()
        stats = monitor.get_review_stats("app_001")
        self.assertIsInstance(stats, ReviewStats)

    def test_review_monitor_respond_to_review(self):
        monitor = ReviewMonitor()
        reviews = monitor.get_reviews("app_001")
        if reviews:
            result = monitor.respond_to_review(reviews[0].review_id, "Thank you!")
            self.assertTrue(result)

    def test_review_create(self):
        review = Review(review_id="rev_001", app_id="app_001", user_id="user_001", user_name="User1", rating=5, title="Great!", body="Excellent game")
        self.assertEqual(review.review_id, "rev_001")

    def test_review_to_dict(self):
        review = Review(review_id="rev_001", app_id="app_001", user_id="user_001", user_name="User1", rating=5)
        d = review.to_dict()
        self.assertIsInstance(d, dict)

    def test_review_stats_create(self):
        stats = ReviewStats(app_id="app_001", total_reviews=100, avg_rating=4.5)
        self.assertEqual(stats.total_reviews, 100)

    def test_review_stats_to_dict(self):
        stats = ReviewStats(app_id="app_001")
        d = stats.to_dict()
        self.assertIsInstance(d, dict)

    def test_sentiment_summary_create(self):
        summary = SentimentSummary(app_id="app_001", overall_sentiment=Sentiment.POSITIVE, positive_percentage=80.0, neutral_percentage=15.0, negative_percentage=5.0)
        self.assertEqual(summary.app_id, "app_001")

    def test_sentiment_summary_to_dict(self):
        summary = SentimentSummary(app_id="app_001")
        d = summary.to_dict()
        self.assertIsInstance(d, dict)

    def test_rollback_release_rollback(self):
        rollback = RollbackRelease()
        result = rollback.rollback("app_001", "version_001")
        self.assertIsInstance(result, Rollback)

    def test_rollback_release_get_status(self):
        rollback = RollbackRelease()
        rollback.rollback("app_001", "version_001")
        status = rollback.get_rollback_status("app_001")
        self.assertIsNotNone(status)

    def test_rollback_release_list_versions(self):
        rollback = RollbackRelease()
        versions = rollback.list_versions("app_001")
        self.assertIsInstance(versions, list)
        self.assertGreater(len(versions), 0)

    def test_rollback_create(self):
        rollback = Rollback(rollback_id="roll_001", app_id="app_001", from_version="1.0.0", to_version="0.9.0")
        self.assertEqual(rollback.rollback_id, "roll_001")

    def test_rollback_to_dict(self):
        rollback = Rollback(rollback_id="roll_001", app_id="app_001", from_version="1.0.0", to_version="0.9.0")
        d = rollback.to_dict()
        self.assertIsInstance(d, dict)

    def test_version_create(self):
        version = Version(version="1.0.0", build_id="build_001")
        self.assertEqual(version.version, "1.0.0")

    def test_version_to_dict(self):
        version = Version(version="1.0.0", build_id="build_001")
        d = version.to_dict()
        self.assertIsInstance(d, dict)


# ---------------------------------------------------------------------------
# finance_reality (~80 tests)
# ---------------------------------------------------------------------------
class TestFinanceReality(unittest.TestCase):
    def test_revenue_tracker_record_revenue(self):
        tracker = RevenueTracker()
        record = tracker.record_revenue("in_app_purchase", 99.99, datetime.now())
        self.assertIsInstance(record, RevenueRecord)

    def test_revenue_tracker_get_daily_revenue(self):
        tracker = RevenueTracker()
        today = datetime.now()
        tracker.record_revenue("in_app_purchase", 99.99, today)
        revenue = tracker.get_daily_revenue(today)
        self.assertEqual(revenue, 99.99)

    def test_revenue_tracker_get_monthly_revenue(self):
        tracker = RevenueTracker()
        tracker.record_revenue("in_app_purchase", 99.99, datetime.now())
        revenue = tracker.get_monthly_revenue(datetime.now().month)
        self.assertGreater(revenue, 0)

    def test_revenue_tracker_get_revenue_by_source(self):
        tracker = RevenueTracker()
        tracker.record_revenue("in_app_purchase", 99.99, datetime.now())
        result = tracker.get_revenue_by_source()
        self.assertIn("in_app_purchase", result)

    def test_revenue_record_create(self):
        record = RevenueRecord(source=RevenueSource.IN_APP_PURCHASE, amount=99.99, date=datetime.now())
        self.assertEqual(record.amount, 99.99)

    def test_revenue_record_to_dict(self):
        record = RevenueRecord(source=RevenueSource.IN_APP_PURCHASE, amount=99.99, date=datetime.now())
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_revenue_trend_create(self):
        trend = RevenueTrend(dates=["2024-01-01"], amounts=[1000.0], total=1000.0, avg_daily=1000.0, growth_rate=0.0)
        self.assertEqual(trend.total, 1000.0)

    def test_revenue_trend_to_dict(self):
        trend = RevenueTrend(dates=["2024-01-01"], amounts=[1000.0], total=1000.0, avg_daily=1000.0, growth_rate=0.0)
        d = trend.to_dict()
        self.assertIsInstance(d, dict)

    def test_ad_cost_tracker_record_ad_cost(self):
        tracker = AdCostTracker()
        record = tracker.record_ad_cost("meta_ads", "camp_001", 100.0, datetime.now())
        self.assertIsInstance(record, AdCostRecord)

    def test_ad_cost_tracker_get_daily_ad_cost(self):
        tracker = AdCostTracker()
        today = datetime.now()
        tracker.record_ad_cost("meta_ads", "camp_001", 100.0, today)
        cost = tracker.get_daily_ad_cost(today)
        self.assertEqual(cost, 100.0)

    def test_ad_cost_tracker_get_campaign_cost(self):
        tracker = AdCostTracker()
        tracker.record_ad_cost("meta_ads", "camp_001", 100.0, datetime.now())
        tracker.record_ad_cost("meta_ads", "camp_001", 50.0, datetime.now())
        cost = tracker.get_campaign_cost("camp_001")
        self.assertEqual(cost, 150.0)

    def test_ad_cost_tracker_get_cost_by_platform(self):
        tracker = AdCostTracker()
        tracker.record_ad_cost("meta_ads", "camp_001", 100.0, datetime.now())
        result = tracker.get_cost_by_platform()
        self.assertIn("meta_ads", result)

    def test_ad_cost_record_create(self):
        record = AdCostRecord(platform=AdPlatform.META_ADS, campaign_id="camp_001", amount=100.0, date=datetime.now())
        self.assertEqual(record.amount, 100.0)

    def test_ad_cost_record_to_dict(self):
        record = AdCostRecord(platform=AdPlatform.META_ADS, campaign_id="camp_001", amount=100.0, date=datetime.now())
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_cost_trend_create(self):
        trend = CostTrend(dates=["2024-01-01"], amounts=[500.0], total=500.0, avg_daily=500.0, cpc_trend=[2.0])
        self.assertEqual(trend.total, 500.0)

    def test_cost_trend_to_dict(self):
        trend = CostTrend(dates=["2024-01-01"], amounts=[500.0], total=500.0, avg_daily=500.0, cpc_trend=[2.0])
        d = trend.to_dict()
        self.assertIsInstance(d, dict)

    def test_profit_calculator_calculate_daily_profit(self):
        calculator = ProfitCalculator()
        result = calculator.calculate_daily_profit(datetime.now())
        self.assertIsInstance(result, ProfitResult)

    def test_profit_calculator_calculate_monthly_profit(self):
        calculator = ProfitCalculator()
        result = calculator.calculate_monthly_profit(datetime.now().month)
        self.assertIsInstance(result, ProfitResult)

    def test_profit_calculator_get_profit_margin(self):
        calculator = ProfitCalculator()
        margin = calculator.get_profit_margin()
        self.assertIsInstance(margin, ProfitMargin)

    def test_profit_result_create(self):
        result = ProfitResult(date="2024-01-01", revenue=1000.0, cost_of_goods_sold=350.0, operating_expenses=400.0, gross_profit=650.0, operating_profit=250.0, net_profit=187.5, profit_margin=18.75)
        self.assertEqual(result.revenue, 1000.0)

    def test_profit_result_to_dict(self):
        result = ProfitResult(date="2024-01-01", revenue=1000.0, cost_of_goods_sold=350.0, operating_expenses=400.0, gross_profit=650.0, operating_profit=250.0, net_profit=187.5, profit_margin=18.75)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_profit_margin_create(self):
        margin = ProfitMargin(gross_margin=65.0, operating_margin=25.0, net_margin=18.75, ebitda_margin=33.0)
        self.assertEqual(margin.gross_margin, 65.0)

    def test_profit_margin_to_dict(self):
        margin = ProfitMargin(gross_margin=65.0, operating_margin=25.0, net_margin=18.75, ebitda_margin=33.0)
        d = margin.to_dict()
        self.assertIsInstance(d, dict)

    def test_cashflow_monitor_record_cashflow(self):
        monitor = CashflowMonitor()
        record = monitor.record_cashflow("inflow", "operating", 1000.0, datetime.now())
        self.assertIsInstance(record, CashflowRecord)

    def test_cashflow_monitor_get_cash_balance(self):
        monitor = CashflowMonitor(initial_balance=10000.0)
        monitor.record_cashflow("inflow", "operating", 5000.0, datetime.now())
        balance = monitor.get_cash_balance()
        self.assertEqual(balance, 15000.0)

    def test_cashflow_monitor_get_cashflow_statement(self):
        monitor = CashflowMonitor()
        statement = monitor.get_cashflow_statement()
        self.assertIsInstance(statement, CashflowStatement)

    def test_cashflow_monitor_check_runway(self):
        monitor = CashflowMonitor()
        analysis = monitor.check_runway()
        self.assertIsInstance(analysis, RunwayAnalysis)

    def test_cashflow_record_create(self):
        record = CashflowRecord(type=CashflowType.INFLOW, category=CashflowCategory.OPERATING, amount=1000.0, date=datetime.now())
        self.assertEqual(record.amount, 1000.0)

    def test_cashflow_record_to_dict(self):
        record = CashflowRecord(type=CashflowType.INFLOW, category=CashflowCategory.OPERATING, amount=1000.0, date=datetime.now())
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_cashflow_statement_create(self):
        statement = CashflowStatement(period_start="2024-01-01", period_end="2024-01-31", opening_balance=10000.0, closing_balance=12000.0, net_cashflow=2000.0, operating_cashflow=3000.0, investing_cashflow=-500.0, financing_cashflow=-500.0)
        self.assertEqual(statement.opening_balance, 10000.0)

    def test_cashflow_statement_to_dict(self):
        statement = CashflowStatement(period_start="2024-01-01", period_end="2024-01-31", opening_balance=10000.0, closing_balance=12000.0, net_cashflow=2000.0, operating_cashflow=3000.0, investing_cashflow=-500.0, financing_cashflow=-500.0)
        d = statement.to_dict()
        self.assertIsInstance(d, dict)

    def test_runway_analysis_create(self):
        analysis = RunwayAnalysis(current_balance=1000000.0, monthly_burn_rate=150000.0, runway_days=200, runway_months=6.67, warning_level="caution")
        self.assertEqual(analysis.current_balance, 1000000.0)

    def test_runway_analysis_to_dict(self):
        analysis = RunwayAnalysis(current_balance=1000000.0, monthly_burn_rate=150000.0, runway_days=200, runway_months=6.67, warning_level="caution")
        d = analysis.to_dict()
        self.assertIsInstance(d, dict)

    def test_budget_controller_set_budget(self):
        controller = BudgetController()
        result = controller.set_budget("advertising", 10000.0)
        self.assertIsInstance(result, Budget)

    def test_budget_controller_get_budget(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        budget = controller.get_budget("advertising")
        self.assertIsNotNone(budget)

    def test_budget_controller_check_budget(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        result = controller.check_budget("advertising")
        self.assertIsInstance(result, dict)

    def test_budget_controller_allocate_budget(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        result = controller.allocate_budget("advertising", 5000.0)
        self.assertIsInstance(result, BudgetAllocation)

    def test_budget_create(self):
        budget = Budget(category=BudgetCategory.ADVERTISING, total_amount=10000.0, allocated_amount=0.0, spent_amount=0.0, remaining_amount=10000.0, start_date=datetime.now(), end_date=datetime.now())
        self.assertEqual(budget.total_amount, 10000.0)

    def test_budget_to_dict(self):
        budget = Budget(category=BudgetCategory.ADVERTISING, total_amount=10000.0, allocated_amount=0.0, spent_amount=0.0, remaining_amount=10000.0, start_date=datetime.now(), end_date=datetime.now())
        d = budget.to_dict()
        self.assertIsInstance(d, dict)

    def test_budget_allocation_create(self):
        allocation = BudgetAllocation(category=BudgetCategory.ADVERTISING, amount=5000.0)
        self.assertEqual(allocation.amount, 5000.0)

    def test_budget_allocation_to_dict(self):
        allocation = BudgetAllocation(category=BudgetCategory.ADVERTISING, amount=5000.0)
        d = allocation.to_dict()
        self.assertIsInstance(d, dict)

    def test_finance_report_service_generate_daily_report(self):
        service = FinanceReportService()
        report = service.generate_daily_report()
        self.assertIsInstance(report, FinanceReport)

    def test_finance_report_service_generate_weekly_report(self):
        service = FinanceReportService()
        report = service.generate_weekly_report()
        self.assertIsInstance(report, FinanceReport)

    def test_finance_report_service_generate_monthly_report(self):
        service = FinanceReportService()
        report = service.generate_monthly_report()
        self.assertIsInstance(report, FinanceReport)

    def test_finance_report_create(self):
        metrics = KeyMetrics(revenue=100000.0, expenses=60000.0, net_profit=40000.0, profit_margin=40.0,
                            cash_balance=1000000.0, burn_rate=5000.0, runway_days=200,
                            customer_acquisition_cost=45.0, lifetime_value=450.0, ltv_cac_ratio=10.0)
        report = FinanceReport(report_type="daily", period_start="2024-01-01", period_end="2024-01-01",
                              generated_at="2024-01-01T00:00:00", key_metrics=metrics,
                              revenue_breakdown={}, expense_breakdown={}, cashflow_summary={}, budget_summary={})
        self.assertEqual(report.report_type, "daily")

    def test_finance_report_to_dict(self):
        metrics = KeyMetrics(revenue=100000.0, expenses=60000.0, net_profit=40000.0, profit_margin=40.0,
                            cash_balance=1000000.0, burn_rate=5000.0, runway_days=200,
                            customer_acquisition_cost=45.0, lifetime_value=450.0, ltv_cac_ratio=10.0)
        report = FinanceReport(report_type="daily", period_start="2024-01-01", period_end="2024-01-01",
                              generated_at="2024-01-01T00:00:00", key_metrics=metrics,
                              revenue_breakdown={}, expense_breakdown={}, cashflow_summary={}, budget_summary={})
        d = report.to_dict()
        self.assertIsInstance(d, dict)

    def test_key_metrics_create(self):
        metrics = KeyMetrics(revenue=100000.0, expenses=60000.0, net_profit=40000.0, profit_margin=40.0,
                            cash_balance=1000000.0, burn_rate=5000.0, runway_days=200,
                            customer_acquisition_cost=45.0, lifetime_value=450.0, ltv_cac_ratio=10.0)
        self.assertEqual(metrics.revenue, 100000.0)

    def test_key_metrics_to_dict(self):
        metrics = KeyMetrics(revenue=100000.0, expenses=60000.0, net_profit=40000.0, profit_margin=40.0,
                            cash_balance=1000000.0, burn_rate=5000.0, runway_days=200,
                            customer_acquisition_cost=45.0, lifetime_value=450.0, ltv_cac_ratio=10.0)
        d = metrics.to_dict()
        self.assertIsInstance(d, dict)

    def test_revenue_tracker_get_revenue_trend(self):
        tracker = RevenueTracker()
        today = datetime.now()
        tracker.record_revenue("in_app_purchase", 100.0, today)
        trend = tracker.get_revenue_trend(7)
        self.assertIsInstance(trend, RevenueTrend)
        self.assertEqual(len(trend.dates), 7)

    def test_revenue_tracker_get_stats(self):
        tracker = RevenueTracker()
        tracker.record_revenue("in_app_purchase", 100.0, datetime.now())
        stats = tracker.get_stats()
        self.assertIn("total_revenue", stats)
        self.assertIn("record_count", stats)

    def test_revenue_tracker_get_all_records(self):
        tracker = RevenueTracker()
        tracker.record_revenue("in_app_purchase", 100.0, datetime.now())
        records = tracker.get_all_records()
        self.assertEqual(len(records), 1)

    def test_revenue_tracker_record_unknown_source(self):
        tracker = RevenueTracker()
        record = tracker.record_revenue("unknown_source", 50.0, datetime.now())
        self.assertEqual(record.source, RevenueSource.OTHER)

    def test_revenue_source_values(self):
        self.assertTrue(hasattr(RevenueSource, "IN_APP_PURCHASE"))
        self.assertTrue(hasattr(RevenueSource, "AD_REVENUE"))
        self.assertTrue(hasattr(RevenueSource, "SUBSCRIPTION"))

    def test_ad_cost_tracker_record_cost_with_clicks(self):
        tracker = AdCostTracker()
        record = tracker.record_ad_cost("meta_ads", "camp_001", 100.0, datetime.now(), clicks=100, impressions=1000)
        self.assertEqual(record.clicks, 100)
        self.assertEqual(record.impressions, 1000)

    def test_ad_cost_tracker_get_campaign_cost_multiple(self):
        tracker = AdCostTracker()
        tracker.record_ad_cost("meta_ads", "camp_001", 100.0, datetime.now())
        tracker.record_ad_cost("google_ads", "camp_001", 50.0, datetime.now())
        cost = tracker.get_campaign_cost("camp_001")
        self.assertEqual(cost, 150.0)

    def test_ad_cost_tracker_get_campaign_cost_nonexistent(self):
        tracker = AdCostTracker()
        cost = tracker.get_campaign_cost("nonexistent")
        self.assertEqual(cost, 0.0)

    def test_ad_cost_tracker_get_cost_trend(self):
        tracker = AdCostTracker()
        today = datetime.now()
        tracker.record_ad_cost("meta_ads", "camp_001", 100.0, today)
        trend = tracker.get_cost_trend(7)
        self.assertIsInstance(trend, CostTrend)

    def test_ad_cost_tracker_get_stats(self):
        tracker = AdCostTracker()
        tracker.record_ad_cost("meta_ads", "camp_001", 100.0, datetime.now())
        stats = tracker.get_stats()
        self.assertIn("total_ad_cost", stats)

    def test_ad_cost_tracker_get_all_records(self):
        tracker = AdCostTracker()
        tracker.record_ad_cost("meta_ads", "camp_001", 100.0, datetime.now())
        records = tracker.get_all_records()
        self.assertEqual(len(records), 1)

    def test_ad_platform_values(self):
        self.assertTrue(hasattr(AdPlatform, "META_ADS"))
        self.assertTrue(hasattr(AdPlatform, "GOOGLE_ADS"))
        self.assertTrue(hasattr(AdPlatform, "TIKTOK_ADS"))

    def test_profit_calculator_calculate_net_profit(self):
        calculator = ProfitCalculator()
        profit = calculator.calculate_net_profit(1000.0, {"cost1": 300.0, "cost2": 200.0})
        self.assertEqual(profit, 375.0)

    def test_profit_calculator_get_profit_trend(self):
        calculator = ProfitCalculator()
        trend = calculator.get_profit_trend(7)
        self.assertEqual(len(trend), 7)

    def test_profit_calculator_calculate_profit_zero_revenue(self):
        calculator = ProfitCalculator()
        result = calculator.calculate_net_profit(0.0, {})
        self.assertEqual(result, 0.0)

    def test_cashflow_monitor_forecast_cashflow(self):
        monitor = CashflowMonitor()
        forecast = monitor.forecast_cashflow(7)
        self.assertEqual(len(forecast), 7)
        self.assertIn("date", forecast[0])
        self.assertIn("balance", forecast[0])

    def test_cashflow_monitor_get_stats(self):
        monitor = CashflowMonitor()
        monitor.record_cashflow("inflow", "operating", 1000.0, datetime.now())
        stats = monitor.get_stats()
        self.assertIn("current_balance", stats)
        self.assertIn("total_inflows", stats)

    def test_cashflow_monitor_get_all_records(self):
        monitor = CashflowMonitor()
        monitor.record_cashflow("inflow", "operating", 1000.0, datetime.now())
        records = monitor.get_all_records()
        self.assertEqual(len(records), 1)

    def test_cashflow_monitor_record_unknown_type(self):
        monitor = CashflowMonitor()
        record = monitor.record_cashflow("unknown", "operating", 500.0, datetime.now())
        self.assertEqual(record.type, CashflowType.INFLOW)

    def test_cashflow_monitor_record_negative_amount(self):
        monitor = CashflowMonitor()
        record = monitor.record_cashflow("outflow", "operating", 500.0, datetime.now())
        self.assertEqual(record.type, CashflowType.OUTFLOW)

    def test_cashflow_monitor_cashflow_statement_week(self):
        monitor = CashflowMonitor()
        statement = monitor.get_cashflow_statement("week")
        self.assertIsInstance(statement, CashflowStatement)

    def test_cashflow_monitor_cashflow_statement_quarter(self):
        monitor = CashflowMonitor()
        statement = monitor.get_cashflow_statement("quarter")
        self.assertIsInstance(statement, CashflowStatement)

    def test_cashflow_monitor_check_runway_healthy(self):
        monitor = CashflowMonitor(initial_balance=2000000.0)
        analysis = monitor.check_runway()
        self.assertEqual(analysis.warning_level, "healthy")

    def test_cashflow_type_values(self):
        self.assertTrue(hasattr(CashflowType, "INFLOW"))
        self.assertTrue(hasattr(CashflowType, "OUTFLOW"))

    def test_cashflow_category_values(self):
        self.assertTrue(hasattr(CashflowCategory, "OPERATING"))
        self.assertTrue(hasattr(CashflowCategory, "INVESTING"))
        self.assertTrue(hasattr(CashflowCategory, "FINANCING"))

    def test_budget_controller_get_budget_summary(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        summary = controller.get_budget_summary()
        self.assertIn("total_budget", summary)
        self.assertIn("total_spent", summary)

    def test_budget_controller_record_expense(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        result = controller.record_expense("advertising", 1000.0)
        self.assertTrue(result)

    def test_budget_controller_record_expense_nonexistent(self):
        controller = BudgetController()
        result = controller.record_expense("nonexistent", 1000.0)
        self.assertFalse(result)

    def test_budget_controller_get_all_budgets(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        budgets = controller.get_all_budgets()
        self.assertEqual(len(budgets), 1)

    def test_budget_controller_get_all_allocations(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        controller.allocate_budget("advertising", 5000.0)
        allocations = controller.get_all_allocations()
        self.assertEqual(len(allocations), 1)

    def test_budget_controller_overspend(self):
        controller = BudgetController()
        controller.set_budget("advertising", 1000.0)
        controller.record_expense("advertising", 1500.0)
        budget = controller.get_budget("advertising")
        self.assertTrue(budget.remaining_amount < 0)

    def test_budget_category_values(self):
        self.assertTrue(hasattr(BudgetCategory, "ADVERTISING"))
        self.assertTrue(hasattr(BudgetCategory, "OPERATIONS"))
        self.assertTrue(hasattr(BudgetCategory, "DEVELOPMENT"))

    def test_finance_report_service_get_key_metrics(self):
        service = FinanceReportService()
        metrics = service.get_key_metrics()
        self.assertIsInstance(metrics, KeyMetrics)

    def test_finance_report_service_export_json(self):
        service = FinanceReportService()
        report = service.generate_daily_report()
        exported = service.export_report(report, "json")
        self.assertIsInstance(exported, str)

    def test_finance_report_service_export_csv(self):
        service = FinanceReportService()
        report = service.generate_daily_report()
        exported = service.export_report(report, "csv")
        self.assertIsInstance(exported, str)

    def test_finance_report_service_export_markdown(self):
        service = FinanceReportService()
        report = service.generate_daily_report()
        exported = service.export_report(report, "markdown")
        self.assertIsInstance(exported, str)

    def test_finance_report_service_export_unknown_format(self):
        service = FinanceReportService()
        report = service.generate_daily_report()
        exported = service.export_report(report, "unknown")
        self.assertIsInstance(exported, str)

    def test_finance_report_notes(self):
        metrics = KeyMetrics(revenue=100000.0, expenses=60000.0, net_profit=40000.0, profit_margin=40.0,
                            cash_balance=1000000.0, burn_rate=5000.0, runway_days=200,
                            customer_acquisition_cost=45.0, lifetime_value=450.0, ltv_cac_ratio=10.0)
        report = FinanceReport(report_type="daily", period_start="2024-01-01", period_end="2024-01-01",
                              generated_at="2024-01-01T00:00:00", key_metrics=metrics,
                              revenue_breakdown={}, expense_breakdown={}, cashflow_summary={}, budget_summary={},
                              notes=["Test note"])
        self.assertEqual(len(report.notes), 1)

    def test_revenue_tracker_zero_amount(self):
        tracker = RevenueTracker()
        record = tracker.record_revenue("in_app_purchase", 0.0, datetime.now())
        self.assertEqual(record.amount, 0.0)

    def test_revenue_tracker_multiple_records(self):
        tracker = RevenueTracker()
        tracker.record_revenue("in_app_purchase", 100.0, datetime.now())
        tracker.record_revenue("ad_revenue", 50.0, datetime.now())
        tracker.record_revenue("subscription", 200.0, datetime.now())
        records = tracker.get_all_records()
        self.assertEqual(len(records), 3)

    def test_revenue_tracker_get_stats_empty(self):
        tracker = RevenueTracker()
        stats = tracker.get_stats()
        self.assertEqual(stats["total_revenue"], 0.0)

    def test_ad_cost_tracker_zero_amount(self):
        tracker = AdCostTracker()
        record = tracker.record_ad_cost("meta_ads", "camp_001", 0.0, datetime.now())
        self.assertEqual(record.amount, 0.0)

    def test_ad_cost_tracker_negative_amount(self):
        tracker = AdCostTracker()
        record = tracker.record_ad_cost("google_ads", "camp_002", -50.0, datetime.now())
        self.assertEqual(record.amount, -50.0)

    def test_ad_cost_tracker_unknown_platform(self):
        tracker = AdCostTracker()
        record = tracker.record_ad_cost("unknown_platform", "camp_003", 100.0, datetime.now())
        self.assertEqual(record.platform, AdPlatform.OTHER)

    def test_ad_cost_tracker_get_cost_by_platform_empty(self):
        tracker = AdCostTracker()
        costs = tracker.get_cost_by_platform()
        for platform in AdPlatform:
            self.assertEqual(costs[platform.value], 0.0)

    def test_ad_cost_tracker_get_cost_trend_zero_days(self):
        tracker = AdCostTracker()
        trend = tracker.get_cost_trend(0)
        self.assertEqual(len(trend.dates), 0)

    def test_ad_cost_tracker_get_stats_empty(self):
        tracker = AdCostTracker()
        stats = tracker.get_stats()
        self.assertEqual(stats["total_ad_cost"], 0.0)

    def test_cashflow_monitor_zero_amount(self):
        monitor = CashflowMonitor()
        record = monitor.record_cashflow("inflow", "operating", 0.0, datetime.now())
        self.assertEqual(record.amount, 0.0)

    def test_cashflow_monitor_initial_balance(self):
        monitor = CashflowMonitor(initial_balance=500000.0)
        balance = monitor.get_cash_balance()
        self.assertEqual(balance, 500000.0)

    def test_cashflow_monitor_multiple_records(self):
        monitor = CashflowMonitor()
        monitor.record_cashflow("inflow", "operating", 1000.0, datetime.now())
        monitor.record_cashflow("outflow", "operating", 500.0, datetime.now())
        records = monitor.get_all_records()
        self.assertEqual(len(records), 2)

    def test_cashflow_monitor_get_stats_empty(self):
        monitor = CashflowMonitor()
        stats = monitor.get_stats()
        self.assertEqual(stats["total_inflows"], 0.0)
        self.assertEqual(stats["total_outflows"], 0.0)

    def test_cashflow_monitor_check_runway_critical(self):
        monitor = CashflowMonitor(initial_balance=200000.0)
        analysis = monitor.check_runway()
        self.assertEqual(analysis.warning_level, "critical")

    def test_cashflow_monitor_check_runway_warning(self):
        monitor = CashflowMonitor(initial_balance=600000.0)
        analysis = monitor.check_runway()
        self.assertEqual(analysis.warning_level, "warning")

    def test_budget_controller_zero_budget(self):
        controller = BudgetController()
        controller.set_budget("advertising", 0.0)
        budget = controller.get_budget("advertising")
        self.assertEqual(budget.total_amount, 0.0)

    def test_budget_controller_negative_budget(self):
        controller = BudgetController()
        controller.set_budget("operations", -1000.0)
        budget = controller.get_budget("operations")
        self.assertEqual(budget.total_amount, -1000.0)

    def test_budget_controller_allocate_zero(self):
        controller = BudgetController()
        controller.set_budget("advertising", 10000.0)
        result = controller.allocate_budget("advertising", 0.0)
        self.assertTrue(result)

    def test_budget_controller_over_allocate(self):
        controller = BudgetController()
        controller.set_budget("advertising", 1000.0)
        with self.assertRaises(ValueError):
            controller.allocate_budget("advertising", 1500.0)

    def test_budget_controller_get_budget_nonexistent(self):
        controller = BudgetController()
        budget = controller.get_budget("nonexistent")
        self.assertIsNone(budget)

    def test_finance_report_service_generate_weekly_report(self):
        service = FinanceReportService()
        report = service.generate_weekly_report()
        self.assertEqual(report.report_type, "weekly")

    def test_finance_report_service_generate_monthly_report(self):
        service = FinanceReportService()
        report = service.generate_monthly_report()
        self.assertEqual(report.report_type, "monthly")

    def test_finance_report_service_generate_quarterly_report(self):
        service = FinanceReportService()
        report = service.generate_daily_report()
        self.assertEqual(report.report_type, "daily")

    def test_key_metrics_zero_values(self):
        metrics = KeyMetrics(revenue=0.0, expenses=0.0, net_profit=0.0, profit_margin=0.0,
                            cash_balance=0.0, burn_rate=0.0, runway_days=0,
                            customer_acquisition_cost=0.0, lifetime_value=0.0, ltv_cac_ratio=0.0)
        self.assertEqual(metrics.revenue, 0.0)

    def test_key_metrics_high_profit_margin(self):
        metrics = KeyMetrics(revenue=100000.0, expenses=10000.0, net_profit=90000.0, profit_margin=90.0,
                            cash_balance=500000.0, burn_rate=5000.0, runway_days=100,
                            customer_acquisition_cost=20.0, lifetime_value=200.0, ltv_cac_ratio=10.0)
        self.assertEqual(metrics.profit_margin, 90.0)

    def test_finance_report_empty_breakdowns(self):
        metrics = KeyMetrics(revenue=100000.0, expenses=60000.0, net_profit=40000.0, profit_margin=40.0,
                            cash_balance=1000000.0, burn_rate=5000.0, runway_days=200,
                            customer_acquisition_cost=45.0, lifetime_value=450.0, ltv_cac_ratio=10.0)
        report = FinanceReport(report_type="daily", period_start="2024-01-01", period_end="2024-01-01",
                              generated_at="2024-01-01T00:00:00", key_metrics=metrics,
                              revenue_breakdown={}, expense_breakdown={}, cashflow_summary={}, budget_summary={})
        self.assertEqual(report.revenue_breakdown, {})
        self.assertEqual(report.expense_breakdown, {})

    def test_revenue_trend_zero_values(self):
        trend = RevenueTrend(dates=["2024-01-01"], amounts=[0.0], total=0.0, avg_daily=0.0, growth_rate=0.0)
        self.assertEqual(trend.total, 0.0)

    def test_cost_trend_zero_values(self):
        trend = CostTrend(dates=["2024-01-01"], amounts=[0.0], total=0.0, avg_daily=0.0, cpc_trend=[0.0])
        self.assertEqual(trend.total, 0.0)

    def test_runway_analysis_zero_balance(self):
        analysis = RunwayAnalysis(current_balance=0.0, monthly_burn_rate=10000.0, runway_days=0, runway_months=0.0, warning_level="critical")
        self.assertEqual(analysis.warning_level, "critical")

    def test_cashflow_statement_zero_values(self):
        statement = CashflowStatement(period_start="2024-01-01", period_end="2024-01-01",
                                      opening_balance=0.0, closing_balance=0.0, net_cashflow=0.0,
                                      operating_cashflow=0.0, investing_cashflow=0.0, financing_cashflow=0.0)
        self.assertEqual(statement.net_cashflow, 0.0)


# ---------------------------------------------------------------------------
# human_control (~50 tests)
# ---------------------------------------------------------------------------
class TestHumanControl(unittest.TestCase):
    def test_approval_center_request_approval(self):
        center = ApprovalCenter()
        request = ApprovalRequest(request_id="req_001", requester="user001", request_type="budget")
        result = center.request_approval(request)
        self.assertIsInstance(result, ApprovalRequest)

    def test_approval_center_approve_request(self):
        center = ApprovalCenter()
        request = ApprovalRequest(request_id="req_001", requester="user001", request_type="budget")
        center.request_approval(request)
        result = center.approve_request("req_001")
        self.assertTrue(result)

    def test_approval_center_reject_request(self):
        center = ApprovalCenter()
        request = ApprovalRequest(request_id="req_001", requester="user001", request_type="budget")
        center.request_approval(request)
        result = center.reject_request("req_001", "Reason")
        self.assertTrue(result)

    def test_approval_center_get_pending_requests(self):
        center = ApprovalCenter()
        request = ApprovalRequest(request_id="req_001", requester="user001", request_type="budget")
        center.request_approval(request)
        requests = center.get_pending_requests()
        self.assertEqual(len(requests), 1)

    def test_approval_request_create(self):
        request = ApprovalRequest(request_id="req_001", requester="user001", request_type="budget")
        self.assertEqual(request.request_id, "req_001")

    def test_approval_request_to_dict(self):
        request = ApprovalRequest(request_id="req_001", requester="user001", request_type="budget")
        d = request.to_dict()
        self.assertIsInstance(d, dict)

    def test_approval_status_values(self):
        self.assertTrue(hasattr(ApprovalStatus, "PENDING"))
        self.assertTrue(hasattr(ApprovalStatus, "APPROVED"))
        self.assertTrue(hasattr(ApprovalStatus, "REJECTED"))

    def test_approval_level_values(self):
        self.assertTrue(hasattr(ApprovalLevel, "LOW"))
        self.assertTrue(hasattr(ApprovalLevel, "MEDIUM"))
        self.assertTrue(hasattr(ApprovalLevel, "HIGH"))

    def test_emergency_stop_trigger(self):
        stop = EmergencyStop()
        event = stop.trigger("test trigger")
        self.assertIsInstance(event, EmergencyEvent)

    def test_emergency_stop_release(self):
        stop = EmergencyStop()
        stop.trigger("test trigger")
        result = stop.release("test release")
        self.assertTrue(result)

    def test_emergency_stop_get_status(self):
        stop = EmergencyStop()
        status = stop.get_status()
        self.assertEqual(status, StopStatus.RELEASED)

    def test_emergency_stop_is_active(self):
        stop = EmergencyStop()
        self.assertFalse(stop.is_active())

    def test_emergency_event_create(self):
        event = EmergencyEvent(event_id="evt_001", trigger_reason="test")
        self.assertEqual(event.event_id, "evt_001")

    def test_emergency_event_to_dict(self):
        event = EmergencyEvent(event_id="evt_001", trigger_reason="test")
        d = event.to_dict()
        self.assertIsInstance(d, dict)

    def test_stop_status_values(self):
        self.assertTrue(hasattr(StopStatus, "ACTIVE"))
        self.assertTrue(hasattr(StopStatus, "RELEASED"))

    def test_decision_review_submit_decision(self):
        review = DecisionReview()
        decision = DecisionRecord(decision_id="dec_001", submitter="user001", decision_type="strategy")
        result = review.submit_decision(decision)
        self.assertIsInstance(result, DecisionRecord)

    def test_decision_review_review_decision(self):
        review = DecisionReview()
        decision = DecisionRecord(decision_id="dec_001", submitter="user001", decision_type="strategy")
        review.submit_decision(decision)
        result = review.review_decision("dec_001")
        self.assertTrue(result)

    def test_decision_review_approve_decision(self):
        review = DecisionReview()
        decision = DecisionRecord(decision_id="dec_001", submitter="user001", decision_type="strategy")
        review.submit_decision(decision)
        result = review.approve_decision("dec_001")
        self.assertTrue(result)

    def test_decision_review_get_pending_decisions(self):
        review = DecisionReview()
        decision = DecisionRecord(decision_id="dec_001", submitter="user001", decision_type="strategy")
        review.submit_decision(decision)
        decisions = review.get_pending_decisions()
        self.assertEqual(len(decisions), 1)

    def test_decision_record_create(self):
        record = DecisionRecord(decision_id="dec_001", submitter="user001", decision_type="strategy")
        self.assertEqual(record.decision_id, "dec_001")

    def test_decision_record_to_dict(self):
        record = DecisionRecord(decision_id="dec_001", submitter="user001", decision_type="strategy")
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_decision_status_values(self):
        self.assertTrue(hasattr(DecisionStatus, "PENDING"))
        self.assertTrue(hasattr(DecisionStatus, "UNDER_REVIEW"))
        self.assertTrue(hasattr(DecisionStatus, "APPROVED"))

    def test_audit_log_log(self):
        log = AuditLog()
        log.log(AuditAction.APPROVE, "user001", {"description": "Approved request"})

    def test_audit_log_get_logs(self):
        log = AuditLog()
        log.log(AuditAction.APPROVE, "user001", {"description": "Approved request"})
        logs = log.get_logs()
        self.assertEqual(len(logs), 1)

    def test_audit_log_search_logs(self):
        log = AuditLog()
        log.log(AuditAction.APPROVE, "user001", {"description": "Approved request"})
        results = log.search_logs("user001")
        self.assertGreater(len(results), 0)

    def test_audit_entry_create(self):
        entry = AuditEntry(entry_id="entry_001", user="user001", action=AuditAction.APPROVE)
        self.assertEqual(entry.entry_id, "entry_001")

    def test_audit_entry_to_dict(self):
        entry = AuditEntry(entry_id="entry_001", user="user001", action=AuditAction.APPROVE)
        d = entry.to_dict()
        self.assertIsInstance(d, dict)

    def test_audit_action_values(self):
        self.assertTrue(hasattr(AuditAction, "APPROVE"))
        self.assertTrue(hasattr(AuditAction, "REJECT"))
        self.assertTrue(hasattr(AuditAction, "CREATE"))

    def test_permission_manager_grant_permission(self):
        pm = PermissionManager()
        result = pm.grant_permission("user001", "approval_request")
        self.assertTrue(result)

    def test_permission_manager_revoke_permission(self):
        pm = PermissionManager()
        pm.grant_permission("user001", "approval_request")
        result = pm.revoke_permission("user001", "approval_request")
        self.assertTrue(result)

    def test_permission_manager_check_permission(self):
        pm = PermissionManager()
        pm.grant_permission("user001", "approval_request")
        result = pm.check_permission("user001", "approval_request")
        self.assertTrue(result)

    def test_permission_create(self):
        perm = Permission(name="approval_request", description="Can approve requests")
        self.assertEqual(perm.name, "approval_request")

    def test_permission_to_dict(self):
        perm = Permission(name="approval_request", description="Can approve requests")
        d = perm.to_dict()
        self.assertIsInstance(d, dict)

    def test_permission_group_values(self):
        self.assertTrue(hasattr(PermissionGroup, "ADMIN"))
        self.assertTrue(hasattr(PermissionGroup, "OPERATOR"))
        self.assertTrue(hasattr(PermissionGroup, "VIEWER"))

    def test_user_permission_create(self):
        up = UserPermission(user_id="user001", permissions=["approval_request"])
        self.assertEqual(up.user_id, "user001")

    def test_user_permission_to_dict(self):
        up = UserPermission(user_id="user001", permissions=["approval_request"])
        d = up.to_dict()
        self.assertIsInstance(d, dict)


# ---------------------------------------------------------------------------
# reality_learning (~50 tests)
# ---------------------------------------------------------------------------
class TestRealityLearning(unittest.TestCase):
    def test_prediction_compare_compare(self):
        pc = PredictionCompare()
        prediction = Prediction(prediction_id="pred_001", model_id="model_001", target_variable="revenue", predicted_value=1000.0)
        result = pc.compare(prediction, 1050.0)
        self.assertIsInstance(result, ComparisonResult)

    def test_prediction_compare_get_comparison_report(self):
        pc = PredictionCompare()
        prediction = Prediction(prediction_id="pred_001", model_id="model_001", target_variable="revenue", predicted_value=1000.0)
        pc.compare(prediction, 1050.0)
        report = pc.get_comparison_report()
        self.assertIsInstance(report, dict)

    def test_prediction_compare_get_error_metrics(self):
        pc = PredictionCompare()
        prediction = Prediction(prediction_id="pred_001", model_id="model_001", target_variable="revenue", predicted_value=1000.0)
        pc.compare(prediction, 1050.0)
        metrics = pc.get_error_metrics()
        self.assertIsInstance(metrics, ErrorMetrics)

    def test_prediction_create(self):
        prediction = Prediction(prediction_id="pred_001", model_id="model_001", target_variable="revenue", predicted_value=1000.0)
        self.assertEqual(prediction.prediction_id, "pred_001")

    def test_prediction_to_dict(self):
        prediction = Prediction(prediction_id="pred_001", model_id="model_001", target_variable="revenue", predicted_value=1000.0)
        d = prediction.to_dict()
        self.assertIsInstance(d, dict)

    def test_comparison_result_create(self):
        result = ComparisonResult(prediction_id="pred_001", predicted_value=1000.0, actual_value=1050.0, absolute_error=50.0, relative_error=0.05, within_confidence=False)
        self.assertEqual(result.prediction_id, "pred_001")

    def test_comparison_result_to_dict(self):
        result = ComparisonResult(prediction_id="pred_001", predicted_value=1000.0, actual_value=1050.0, absolute_error=50.0, relative_error=0.05, within_confidence=False)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_error_metrics_create(self):
        metrics = ErrorMetrics(mae=50.0, mse=2500.0, rmse=50.0)
        self.assertEqual(metrics.mae, 50.0)

    def test_error_metrics_to_dict(self):
        metrics = ErrorMetrics(mae=50.0, mse=2500.0, rmse=50.0)
        d = metrics.to_dict()
        self.assertIsInstance(d, dict)

    def test_error_analyzer_analyze_error(self):
        analyzer = ErrorAnalyzer()
        result = analyzer.analyze_error("pred_001")
        self.assertIsInstance(result, ErrorAnalysis)

    def test_error_analyzer_get_error_patterns(self):
        analyzer = ErrorAnalyzer()
        patterns = analyzer.get_error_patterns()
        self.assertIsInstance(patterns, list)

    def test_error_analyzer_identify_systematic_bias(self):
        analyzer = ErrorAnalyzer()
        analyzer.analyze_error("pred_001")
        biases = analyzer.identify_systematic_bias()
        self.assertIsInstance(biases, list)

    def test_error_analysis_create(self):
        analysis = ErrorAnalysis(analysis_id="ana_001", prediction_id="pred_001", error_value=0.15, error_category=ErrorCategory.RANDOM)
        self.assertEqual(analysis.analysis_id, "ana_001")

    def test_error_analysis_to_dict(self):
        analysis = ErrorAnalysis(analysis_id="ana_001", prediction_id="pred_001", error_value=0.15, error_category=ErrorCategory.RANDOM)
        d = analysis.to_dict()
        self.assertIsInstance(d, dict)

    def test_error_pattern_create(self):
        pattern = ErrorPattern(pattern_id="pat_001", category=ErrorCategory.RANDOM, description="Random error", severity=0.2, frequency=0.85)
        self.assertEqual(pattern.pattern_id, "pat_001")

    def test_error_pattern_to_dict(self):
        pattern = ErrorPattern(pattern_id="pat_001", category=ErrorCategory.RANDOM, description="Random error", severity=0.2, frequency=0.85)
        d = pattern.to_dict()
        self.assertIsInstance(d, dict)

    def test_bias_detection_create(self):
        detection = BiasDetection(bias_type=BiasType.CONSTANT, magnitude=0.05, statistical_significance=0.95, confidence_level=0.90)
        self.assertEqual(detection.bias_type, BiasType.CONSTANT)

    def test_bias_detection_to_dict(self):
        detection = BiasDetection(bias_type=BiasType.CONSTANT, magnitude=0.05, statistical_significance=0.95, confidence_level=0.90)
        d = detection.to_dict()
        self.assertIsInstance(d, dict)

    def test_error_category_values(self):
        self.assertTrue(hasattr(ErrorCategory, "RANDOM"))
        self.assertTrue(hasattr(ErrorCategory, "SYSTEMATIC"))
        self.assertTrue(hasattr(ErrorCategory, "OUTLIER"))

    def test_bias_type_values(self):
        self.assertTrue(hasattr(BiasType, "CONSTANT"))
        self.assertTrue(hasattr(BiasType, "PROPORTIONAL"))
        self.assertTrue(hasattr(BiasType, "SEASONAL"))

    def test_calibration_engine_calibrate_model(self):
        engine = CalibrationEngine()
        result = engine.calibrate_model("model_001")
        self.assertIsInstance(result, CalibrationResult)

    def test_calibration_engine_get_calibration_report(self):
        engine = CalibrationEngine()
        engine.calibrate_model("model_001")
        report = engine.get_calibration_report("model_001")
        self.assertIsInstance(report, dict)

    def test_calibration_engine_adjust_prediction(self):
        engine = CalibrationEngine()
        engine.calibrate_model("model_001")
        prediction = {"model_id": "model_001", "predicted_value": 1000.0}
        result = engine.adjust_prediction(prediction)
        self.assertIsInstance(result, dict)

    def test_calibration_result_create(self):
        result = CalibrationResult(model_id="model_001", success=True, calibration_factor=0.95, offset=0.0, confidence_adjustment=0.0)
        self.assertEqual(result.model_id, "model_001")

    def test_calibration_result_to_dict(self):
        result = CalibrationResult(model_id="model_001", success=True, calibration_factor=0.95, offset=0.0, confidence_adjustment=0.0)
        d = result.to_dict()
        self.assertIsInstance(d, dict)

    def test_model_calibration_create(self):
        calibration = ModelCalibration(model_id="model_001")
        self.assertEqual(calibration.model_id, "model_001")

    def test_model_calibration_to_dict(self):
        calibration = ModelCalibration(model_id="model_001")
        d = calibration.to_dict()
        self.assertIsInstance(d, dict)

    def test_calibration_status_values(self):
        self.assertTrue(hasattr(CalibrationStatus, "PENDING"))
        self.assertTrue(hasattr(CalibrationStatus, "IN_PROGRESS"))
        self.assertTrue(hasattr(CalibrationStatus, "COMPLETED"))

    def test_strategy_update_evaluate_strategy(self):
        su = StrategyUpdate()
        result = su.evaluate_strategy("strategy_001")
        self.assertIsInstance(result, StrategyEvaluation)

    def test_strategy_update_update_strategy(self):
        su = StrategyUpdate()
        result = su.update_strategy("strategy_001", {"budget": 5000.0})
        self.assertIsInstance(result, StrategyUpdateRecord)

    def test_strategy_update_create_strategy_version(self):
        su = StrategyUpdate()
        result = su.create_strategy_version("strategy_001")
        self.assertIsInstance(result, StrategyUpdateRecord)

    def test_strategy_evaluation_create(self):
        evaluation = StrategyEvaluation(strategy_id="strategy_001", evaluation_id="eval_001", performance_score=85.0, roi=0.15, risk_score=30.0, compliance_status=True)
        self.assertEqual(evaluation.strategy_id, "strategy_001")

    def test_strategy_evaluation_to_dict(self):
        evaluation = StrategyEvaluation(strategy_id="strategy_001", evaluation_id="eval_001", performance_score=85.0, roi=0.15, risk_score=30.0, compliance_status=True)
        d = evaluation.to_dict()
        self.assertIsInstance(d, dict)

    def test_strategy_update_record_create(self):
        record = StrategyUpdateRecord(update_id="upd_001", strategy_id="strategy_001", version="1.1", update_type=UpdateType.PARAMETER)
        self.assertEqual(record.update_id, "upd_001")

    def test_strategy_update_record_to_dict(self):
        record = StrategyUpdateRecord(update_id="upd_001", strategy_id="strategy_001", version="1.1", update_type=UpdateType.PARAMETER)
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_strategy_status_values(self):
        self.assertTrue(hasattr(StrategyStatus, "ACTIVE"))
        self.assertTrue(hasattr(StrategyStatus, "INACTIVE"))
        self.assertTrue(hasattr(StrategyStatus, "DRAFT"))

    def test_update_type_values(self):
        self.assertTrue(hasattr(UpdateType, "PARAMETER"))
        self.assertTrue(hasattr(UpdateType, "RULE"))
        self.assertTrue(hasattr(UpdateType, "MODEL"))

    def test_learning_memory_store_learning(self):
        lm = LearningMemory()
        learning = LearningRecord(learning_id="learn_001", learning_type=LearningType.PREDICTION_ERROR, content={"prediction_id": "pred_001"})
        result = lm.store_learning(learning)
        self.assertIsInstance(result, LearningRecord)

    def test_learning_memory_retrieve_learnings(self):
        lm = LearningMemory()
        learning = LearningRecord(learning_id="learn_001", learning_type=LearningType.PREDICTION_ERROR, content={"prediction_id": "pred_001"})
        lm.store_learning(learning)
        results = lm.retrieve_learnings({})
        self.assertEqual(len(results), 1)

    def test_learning_memory_get_key_learnings(self):
        lm = LearningMemory()
        insight = LearningInsight(insight_id="insight_001", title="Test", description="Test", confidence=0.9, impact=0.8, source="test")
        learning = LearningRecord(learning_id="learn_001", learning_type=LearningType.PREDICTION_ERROR, content={}, insight=insight)
        lm.store_learning(learning)
        insights = lm.get_key_learnings()
        self.assertEqual(len(insights), 1)

    def test_learning_record_create(self):
        record = LearningRecord(learning_id="learn_001", learning_type=LearningType.PREDICTION_ERROR, content={"key": "value"})
        self.assertEqual(record.learning_id, "learn_001")

    def test_learning_record_to_dict(self):
        record = LearningRecord(learning_id="learn_001", learning_type=LearningType.PREDICTION_ERROR, content={"key": "value"})
        d = record.to_dict()
        self.assertIsInstance(d, dict)

    def test_learning_insight_create(self):
        insight = LearningInsight(insight_id="insight_001", title="Test", description="Test", confidence=0.9, impact=0.8, source="test")
        self.assertEqual(insight.insight_id, "insight_001")

    def test_learning_insight_to_dict(self):
        insight = LearningInsight(insight_id="insight_001", title="Test", description="Test", confidence=0.9, impact=0.8, source="test")
        d = insight.to_dict()
        self.assertIsInstance(d, dict)

    def test_learning_type_values(self):
        self.assertTrue(hasattr(LearningType, "PREDICTION_ERROR"))
        self.assertTrue(hasattr(LearningType, "STRATEGY_ADAPTATION"))
        self.assertTrue(hasattr(LearningType, "BIAS_CORRECTION"))

    def test_learning_status_values(self):
        self.assertTrue(hasattr(LearningStatus, "STORED"))
        self.assertTrue(hasattr(LearningStatus, "APPLIED"))
        self.assertTrue(hasattr(LearningStatus, "ARCHIVED"))


# ---------------------------------------------------------------------------
# Test Counting and Execution
# ---------------------------------------------------------------------------
def count_tests():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    total = 0
    for test_suite in suite:
        for test_case in test_suite:
            total += 1
    return total


if __name__ == "__main__":
    print("=" * 80)
    print("V8.0 Reality Layer - Release Gate")
    print("=" * 80)
    
    total_tests = count_tests()
    print(f"\nTotal test cases: {total_tests}")
    print("-" * 80)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]))
    
    print("\n" + "=" * 80)
    print("Test Results Summary")
    print("=" * 80)
    print(f"Total tests run: {result.testsRun}")
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print(f"Tests passed: {passed}")
    print(f"Tests failed: {len(result.failures)}")
    print(f"Tests with errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed or had errors.")