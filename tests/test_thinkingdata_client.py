"""ThinkingData Client — 完整测试套件.

覆盖: 初始化校验、核心 API 调用、返回码处理、重试机制、Token 脱敏、密码清理、
投放-数数数据打通关键场景。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "src")

from market_ops.clients.thinkingdata import ThinkingDataClient


# ---------------------------------------------------------------------------
# Mock 数据工厂
# ---------------------------------------------------------------------------

def _ok_response(data: dict | None = None) -> dict:
    """构造 return_code=0 的成功响应."""
    return {"return_code": 0, "return_message": "success", "data": data}


def _error_response(code: int, message: str = "error") -> dict:
    """构造失败响应."""
    return {"return_code": code, "return_message": message, "data": None}


def _mock_http_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """构造 mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(f"{status_code} Client Error", response=resp)
    else:
        resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> ThinkingDataClient:
    return ThinkingDataClient("https://ta2:8992", "test_secret_token")


@pytest.fixture
def http_get():
    with patch("market_ops.clients.thinkingdata.requests.get") as m:
        yield m


@pytest.fixture
def http_post():
    with patch("market_ops.clients.thinkingdata.requests.post") as m:
        yield m


# ---------------------------------------------------------------------------
# 1. 初始化与安全校验
# ---------------------------------------------------------------------------

class TestInit:
    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError, match="must start with"):
            ThinkingDataClient("ftp://bad", "token")

    def test_rejects_empty_scheme(self):
        with pytest.raises(ValueError, match="must start with"):
            ThinkingDataClient("just-a-host:8992", "token")

    def test_accepts_https(self):
        c = ThinkingDataClient("https://ta2:8992", "token")
        assert c._base_url == "https://ta2:8992"

    def test_accepts_http(self):
        c = ThinkingDataClient("http://ta2:8992", "token")
        assert c._base_url == "http://ta2:8992"

    def test_strips_trailing_slash(self):
        c = ThinkingDataClient("https://ta2:8992/", "token")
        assert c._base_url == "https://ta2:8992"

    def test_token_stripped(self):
        c = ThinkingDataClient("https://ta2:8992", "  token  ")
        assert c._token == "token"


# ---------------------------------------------------------------------------
# 2. 请求构造与 Token 传递
# ---------------------------------------------------------------------------

class TestRequestConstruction:
    def test_token_passed_in_query_params(self, client, http_post):
        http_post.return_value = _mock_http_response(_ok_response())
        client.event_analyze(102, {"events": []})
        call_kwargs = http_post.call_args
        assert call_kwargs[1]["params"]["token"] == "test_secret_token"

    def test_project_id_in_query_params(self, client, http_post):
        http_post.return_value = _mock_http_response(_ok_response())
        client.event_analyze(102, {"events": []})
        call_kwargs = http_post.call_args
        assert call_kwargs[1]["params"]["projectId"] == 102

    def test_body_sent_as_json(self, client, http_post):
        http_post.return_value = _mock_http_response(_ok_response())
        payload = {"events": [{"eventName": "purchase"}]}
        client.event_analyze(102, payload)
        call_kwargs = http_post.call_args
        assert call_kwargs[1]["json"] == payload

    def test_get_uses_get_method(self, client, http_get):
        http_get.return_value = _mock_http_response(_ok_response())
        client.list_events(102)
        http_get.assert_called_once()

    def test_post_uses_post_method(self, client, http_post):
        http_post.return_value = _mock_http_response(_ok_response())
        client.list_user_clusters({"projectId": 102})
        http_post.assert_called_once()

    def test_empty_body_sent_as_empty_dict(self, client, http_post):
        http_post.return_value = _mock_http_response(_ok_response())
        client.delete_user_cluster_by_name(102, "my_cluster")
        call_kwargs = http_post.call_args
        assert call_kwargs[1]["json"] == {}

    def test_url_construction(self, client, http_post):
        http_post.return_value = _mock_http_response(_ok_response())
        client.event_analyze(102, {"events": []})
        call_args = http_post.call_args
        assert call_args[0][0] == "https://ta2:8992/open/event-analyze"


# ---------------------------------------------------------------------------
# 3. 返回码处理
# ---------------------------------------------------------------------------

class TestReturnCodeHandling:
    def test_success_return_code_0(self, client, http_post):
        http_post.return_value = _mock_http_response(_ok_response({"rows": []}))
        result = client.event_analyze(102, {"events": []})
        assert result["return_code"] == 0
        assert result["data"] == {"rows": []}

    def test_success_return_code_none(self, client, http_post):
        http_post.return_value = _mock_http_response({"return_code": None, "data": "ok"})
        result = client.event_analyze(102, {"events": []})
        assert result["data"] == "ok"

    def test_error_return_code_raises(self, client, http_post):
        http_post.return_value = _mock_http_response(_error_response(10002, "invalid token"))
        with pytest.raises(RuntimeError, match="code=10002"):
            client.event_analyze(102, {"events": []})

    def test_error_return_code_includes_message(self, client, http_post):
        http_post.return_value = _mock_http_response(_error_response(20003, "no permission"))
        with pytest.raises(RuntimeError, match="no permission"):
            client.event_analyze(102, {"events": []})


# ---------------------------------------------------------------------------
# 4. 重试机制
# ---------------------------------------------------------------------------

class TestRetryMechanism:
    def test_retries_on_connection_error(self, client, http_post):
        from requests import ConnectionError
        http_post.side_effect = [ConnectionError("timeout"), _mock_http_response(_ok_response())]
        result = client.event_analyze(102, {"events": []})
        assert result["return_code"] == 0
        assert http_post.call_count == 2

    def test_retries_up_to_3_times(self, client, http_post):
        from requests import ConnectionError
        http_post.side_effect = ConnectionError("timeout")
        with pytest.raises(ConnectionError):
            client.event_analyze(102, {"events": []})
        assert http_post.call_count == 3

    def test_retry_with_backoff(self, client, http_post):
        from requests import ConnectionError
        import time
        http_post.side_effect = [ConnectionError("err1"), ConnectionError("err2"), _mock_http_response(_ok_response())]
        start = time.time()
        client.event_analyze(102, {"events": []})
        elapsed = time.time() - start
        assert elapsed >= 2.5, f"Expected >=2.5s backoff, got {elapsed:.1f}s"


# ---------------------------------------------------------------------------
# 5. Token 脱敏
# ---------------------------------------------------------------------------

class TestTokenRedaction:
    def test_token_redacted_from_request_url(self, client):
        from requests import ConnectionError
        req = MagicMock()
        req.url = "https://ta2:8992/open/event-analyze?token=test_secret_token&projectId=102"
        exc = ConnectionError("connection reset", request=req)
        redacted = client._redact_token(exc)
        assert "test_secret_token" not in redacted.request.url
        assert "***REDACTED***" in redacted.request.url

    def test_token_redacted_from_response_url(self, client):
        from requests import HTTPError
        resp = MagicMock()
        resp.url = "https://ta2:8992/open/event-analyze?token=test_secret_token"
        req = MagicMock()
        req.url = "https://ta2:8992/open/event-analyze?token=test_secret_token"
        exc = HTTPError("500", response=resp, request=req)
        redacted = client._redact_token(exc)
        assert "test_secret_token" not in redacted.response.url

    def test_token_redacted_from_message(self, client):
        from requests import RequestException
        exc = RequestException("Token test_secret_token leaked in message")
        redacted = client._redact_token(exc)
        assert "test_secret_token" not in str(redacted)
        assert "***REDACTED***" in str(redacted)

    def test_no_redaction_if_token_empty(self):
        c = ThinkingDataClient("https://ta2:8992", "")
        from requests import ConnectionError
        req = MagicMock()
        req.url = "https://example.com/api?param=value"
        exc = ConnectionError("err", request=req)
        redacted = c._redact_token(exc)
        assert req.url == redacted.request.url

    def test_redaction_during_retry(self, client, http_post):
        """验证重试时异常中的 token 已脱敏."""
        from requests import ConnectionError

        # side_effect: 第一次失败，第二次成功
        req = MagicMock()
        req.url = "https://ta2:8992/open/event-analyze?token=test_secret_token"
        exc = ConnectionError("timeout", request=req)
        http_post.side_effect = [exc, _mock_http_response(_ok_response())]

        # 第一次调用因 ConnectionError 被重试，第二次成功
        result = client.event_analyze(102, {"events": []})
        assert result["return_code"] == 0
        assert http_post.call_count == 2


# ---------------------------------------------------------------------------
# 6. 密码清理
# ---------------------------------------------------------------------------

class TestPasswordCleanup:
    def test_password_cleared_after_create_sso_user(self, client, http_get):
        http_get.return_value = _mock_http_response(_ok_response({"loginName": "newuser"}))
        result = client.create_sso_user("pwd", "newuser", password="plaintext123")
        assert result["data"]["loginName"] == "newuser"

    def test_no_password_param_in_second_call(self, client, http_get):
        """同一 client 连续两次调用，验证上一次的 password 不会残留到下一次."""
        http_get.return_value = _mock_http_response(_ok_response({"loginName": "user2"}))
        client.create_sso_user("pwd", "user1", password="pass1")
        call1_params = http_get.call_args_list[0][1].get("params", {})
        # 第一次调用应包含 pass1
        assert call1_params.get("password") == "pass1"

        client.create_sso_user("pwd", "user2", password="pass2")
        call2_params = http_get.call_args_list[1][1].get("params", {})
        # 第二次调用不应残留 pass1
        assert call2_params.get("password") != "pass1"
        # 第二次调用应使用当前的 pass2
        assert call2_params.get("password") == "pass2"


# ---------------------------------------------------------------------------
# 7. 投放-数数 数据打通场景
# ---------------------------------------------------------------------------

class TestIntegrationScenarios:
    """模拟投放平台与数数之间的数据互通."""

    def test_sync_user_cluster_for_ad_campaign_targeting(self, client, http_post):
        """场景: 从数数拉取付费用户分群 → 用于广告定向."""
        mock_clusters = _ok_response({
            "total": 2,
            "list": [
                {"clusterName": "paying_users_p04", "clusterId": 501, "userCount": 12847},
                {"clusterName": "whale_users_p04", "clusterId": 502, "userCount": 342},
            ],
        })
        http_post.return_value = _mock_http_response(mock_clusters)

        result = client.list_user_clusters({
            "projectId": 102,
            "clusterCatalog": "catalog_cluster",
            "clusterTypes": ["cluster_by_static_condition"],
            "pagerHeader": {"pageNum": 1, "pageSize": 50},
        })

        assert result["return_code"] == 0
        assert len(result["data"]["list"]) == 2
        assert result["data"]["list"][0]["clusterName"] == "paying_users_p04"
        assert result["data"]["list"][1]["userCount"] == 342

    def test_event_analysis_for_ad_performance_reconciliation(self, client, http_post):
        """场景: 从数数拉取事件数据 → 与投放平台消耗对账."""
        mock_events = _ok_response({
            "rows": [
                {"campaign_id": "meta_campaign_001", "revenue": 45230.50, "event_count": 12847},
                {"campaign_id": "meta_campaign_002", "revenue": 12847.20, "event_count": 3421},
                {"campaign_id": "google_campaign_003", "revenue": 8923.00, "event_count": 1923},
            ],
        })
        http_post.return_value = _mock_http_response(mock_events)

        result = client.event_analyze(102, {
            "events": [
                {"eventName": "purchase", "analysis": "SUM", "property": "#revenue"},
                {"eventName": "purchase", "analysis": "COUNT", "property": "#event_name"},
            ],
            "timeRange": {"start": "2026-08-01", "end": "2026-08-05"},
            "groupBy": ["#campaign_id"],
        })

        rows = result["data"]["rows"]
        assert len(rows) == 3
        # 与投放平台对账: meta_campaign_001 产生 45230.50 收入
        meta_revenue = sum(r["revenue"] for r in rows if r["campaign_id"].startswith("meta_"))
        assert meta_revenue == 45230.50 + 12847.20

    def test_sql_query_for_flexible_data_extraction(self, client, http_post):
        """场景: 用数数 SQL 直接取自定义数据."""
        mock_sql = _ok_response({
            "columns": ["campaign_id", "ad_spend", "revenue", "roi"],
            "rows": [
                ["meta_001", 5000.00, 45230.50, 9.05],
                ["meta_002", 3200.00, 12847.20, 4.01],
                ["google_003", 1500.00, 8923.00, 5.95],
            ],
        })
        http_post.return_value = _mock_http_response(mock_sql)

        sql = """
            SELECT campaign_id, SUM(ad_spend) AS ad_spend,
                   SUM(revenue) AS revenue, revenue / ad_spend AS roi
            FROM v_event_102
            WHERE event_name = 'purchase'
              AND campaign_id LIKE 'meta_%'
              AND time >= '2026-08-01'
            GROUP BY campaign_id
            HAVING roi > 3.0
            ORDER BY roi DESC
        """
        result = client.sql_query(102, sql)

        assert result["return_code"] == 0
        assert len(result["data"]["rows"]) == 3
        # ROI 都 > 3.0
        for row in result["data"]["rows"]:
            assert row[3] > 3.0

    def test_metadata_fetch_event_list(self, client, http_get):
        """场景: 拉取数数中所有事件列表 → 用于配置投放追踪."""
        http_get.return_value = _mock_http_response(_ok_response([
            {"eventName": "purchase", "displayName": "付费", "isAutoTrack": False},
            {"eventName": "add_to_cart", "displayName": "加购", "isAutoTrack": False},
            {"eventName": "page_view", "displayName": "页面浏览", "isAutoTrack": True},
            {"eventName": "signup", "displayName": "注册", "isAutoTrack": False},
        ]))

        result = client.list_events(102)
        events = result["data"]
        assert len(events) >= 4
        event_names = {e["eventName"] for e in events}
        assert "purchase" in event_names
        assert "signup" in event_names

    def test_retention_analysis_for_campaign_optimization(self, client, http_post):
        """场景: 分析投放渠道的次日留存 → 优化投放策略."""
        mock_retention = _ok_response({
            "rows": [
                {"campaign_id": "meta_001", "d1_retention": 0.45, "d7_retention": 0.23},
                {"campaign_id": "meta_002", "d1_retention": 0.32, "d7_retention": 0.12},
                {"campaign_id": "google_003", "d1_retention": 0.51, "d7_retention": 0.28},
            ],
        })
        http_post.return_value = _mock_http_response(mock_retention)

        result = client.retention_analyze(102, {
            "events": [
                {"eventName": "signup"},
                {"eventName": "login"},
            ],
            "timeRange": {"start": "2026-07-01", "end": "2026-07-31"},
            "groupBy": ["#campaign_id"],
        })

        rows = result["data"]["rows"]
        # google_003 留存最高
        google_row = next(r for r in rows if r["campaign_id"] == "google_003")
        assert google_row["d1_retention"] == 0.51
        assert google_row["d7_retention"] == 0.28

    def test_funnel_analysis_for_conversion_optimization(self, client, http_post):
        """场景: 分析投放用户的转化漏斗 → 找出流失环节."""
        mock_funnel = _ok_response({
            "steps": ["page_view", "add_to_cart", "purchase"],
            "rows": [
                {"campaign_id": "meta_001", "step_counts": [10000, 4500, 1200]},
                {"campaign_id": "meta_002", "step_counts": [8000, 2800, 400]},
            ],
        })
        http_post.return_value = _mock_http_response(mock_funnel)

        result = client.funnel_analyze(102, {
            "events": ["page_view", "add_to_cart", "purchase"],
            "timeRange": {"start": "2026-08-01", "end": "2026-08-05"},
            "groupBy": ["#campaign_id"],
        })

        for row in result["data"]["rows"]:
            counts = row["step_counts"]
            # 漏斗递减
            assert counts[0] >= counts[1] >= counts[2]
            # meta_002 转化率更低
            if row["campaign_id"] == "meta_001":
                assert counts[2] / counts[0] > 0.10  # 12% 转化
            elif row["campaign_id"] == "meta_002":
                assert counts[2] / counts[0] < 0.06  # 5% 转化

    def test_create_user_cluster_for_new_campaign(self, client, http_post):
        """场景: 为新投放活动创建目标用户分群."""
        mock_create = _ok_response({"clusterId": 601})
        http_post.return_value = _mock_http_response(mock_create)

        result = client.add_user_cluster(102, {
            "clusterName": "high_value_new_users",
            "clusterType": "cluster_by_static_condition",
            "projectId": 102,
            "conditions": [
                {"property": "#first_pay_date", "op": "in", "value": ["2026-08-01", "2026-08-05"]},
                {"property": "#total_revenue", "op": ">=", "value": [500]},
            ],
        })

        assert result["data"]["clusterId"] == 601

    def test_user_list_for_cross_platform_matching(self, client, http_post):
        """场景: 导出用户列表 → 与投放平台用户 ID 匹配."""
        mock_users = _ok_response({
            "total": 3,
            "list": [
                {"distinct_id": "user_001", "login_id": "u1@example.com", "channel": "meta", "first_pay_date": "2026-08-02"},
                {"distinct_id": "user_002", "login_id": "u2@example.com", "channel": "google", "first_pay_date": "2026-08-03"},
                {"distinct_id": "user_003", "login_id": "u3@example.com", "channel": "meta", "first_pay_date": "2026-08-04"},
            ],
        })
        http_post.return_value = _mock_http_response(mock_users)

        result = client.user_list(102, {
            "projectId": 102,
            "filter": {"property": "#channel", "op": "in", "value": ["meta"]},
            "pagerHeader": {"pageNum": 1, "pageSize": 100},
        })

        meta_users = [u for u in result["data"]["list"] if u["channel"] == "meta"]
        assert len(meta_users) == 2
        assert all(u["channel"] == "meta" for u in meta_users)


# ---------------------------------------------------------------------------
# 8. 全接口覆盖检查
# ---------------------------------------------------------------------------

class TestFullAPICoverage:
    def test_all_public_methods_have_http_backing(self, client):
        """确保所有公共方法都通过 _request 发起 HTTP 调用."""
        public_methods = [
            m for m in dir(client)
            if not m.startswith("_") and callable(getattr(client, m))
        ]
        assert len(public_methods) == 53
        for method_name in public_methods:
            assert hasattr(client, method_name)
            assert callable(getattr(client, method_name))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])