"""ThinkingData E2E 测试 — Mock 模式.

无需真实数数实例，本地验证客户端全部 9 个接口的调用逻辑。
运行: python scripts/e2e_thinkingdata_mock.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

sys.path.insert(0, "src")

from market_ops.clients.thinkingdata import ThinkingDataClient


# ---------------------------------------------------------------------------
# 日志工具
# ---------------------------------------------------------------------------

def log(step: int, total: int, title: str, detail: str = "", ok: bool | None = None):
    icon = "✅" if ok is True else "❌" if ok is False else "⏳"
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{step}/{total}] {icon} {title}")
    if detail:
        print(f"       {detail}")


def pretty_json(data: dict | list, indent: int = 6, max_len: int = 150) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=indent)
    if len(raw) > max_len * 4:
        return raw[:max_len] + " ... (truncated)"
    return raw


# ---------------------------------------------------------------------------
# Mock 响应数据工厂 — 模拟真实数数返回结构
# ---------------------------------------------------------------------------

def _ok(data: dict | list | None = None) -> dict:
    return {"return_code": 0, "return_message": "success", "data": data}


def _mock_list_user_projects(login_name: str) -> dict:
    return _ok({
        "total": 3,
        "list": [
            {"projectId": 2, "projectName": "P02 Mermaid", "appId": "app_p02", "status": "active"},
            {"projectId": 4, "projectName": "P07 Vampire", "appId": "app_p07", "status": "active"},
            {"projectId": 6, "projectName": "P04 Witch", "appId": "app_p04", "status": "active"},
        ],
    })


def _mock_list_events(project_id: int) -> dict:
    return _ok([
        {"eventName": "page_view", "displayName": "页面浏览", "isAutoTrack": True, "projectId": project_id},
        {"eventName": "add_to_cart", "displayName": "加购", "isAutoTrack": False, "projectId": project_id},
        {"eventName": "purchase", "displayName": "付费", "isAutoTrack": False, "projectId": project_id},
        {"eventName": "signup", "displayName": "注册", "isAutoTrack": False, "projectId": project_id},
        {"eventName": "login", "displayName": "登录", "isAutoTrack": False, "projectId": project_id},
        {"eventName": "share", "displayName": "分享", "isAutoTrack": False, "projectId": project_id},
        {"eventName": "level_up", "displayName": "升级", "isAutoTrack": False, "projectId": project_id},
        {"eventName": "watch_ad", "displayName": "观看广告", "isAutoTrack": False, "projectId": project_id},
    ])


def _mock_list_user_properties(project_id: int) -> dict:
    return _ok([
        {"propertyName": "#channel", "displayName": "渠道", "dataType": "string", "projectId": project_id},
        {"propertyName": "#platform", "displayName": "平台", "dataType": "string", "projectId": project_id},
        {"propertyName": "#country", "displayName": "国家", "dataType": "string", "projectId": project_id},
        {"propertyName": "#total_revenue", "displayName": "累计收入", "dataType": "number", "projectId": project_id},
        {"propertyName": "#first_pay_date", "displayName": "首次付费日期", "dataType": "date", "projectId": project_id},
        {"propertyName": "#login_times", "displayName": "登录次数", "dataType": "number", "projectId": project_id},
        {"propertyName": "#device_model", "displayName": "设备型号", "dataType": "string", "projectId": project_id},
    ])


def _mock_list_dashboards(project_id: int) -> dict:
    return _ok([
        {"dashboardId": 117, "dashboardName": "P04 核心指标看板", "projectId": project_id, "isDefault": True},
        {"dashboardId": 132, "dashboardName": "P04 渠道分析看板", "projectId": project_id, "isDefault": False},
        {"dashboardId": 162, "dashboardName": "P04 用户行为看板", "projectId": project_id, "isDefault": False},
        {"dashboardId": 201, "dashboardName": "P04 留存分析看板", "projectId": project_id, "isDefault": False},
    ])


def _mock_dashboard_detail(project_id: int, dashboard_id: int) -> dict:
    return _ok({
        "dashboardId": dashboard_id,
        "dashboardName": f"看板 {dashboard_id}",
        "projectId": project_id,
        "charts": [
            {"chartId": f"chart_{dashboard_id}_1", "chartName": "DAU 趋势", "chartType": "line"},
            {"chartId": f"chart_{dashboard_id}_2", "chartName": "渠道分布", "chartType": "pie"},
            {"chartId": f"chart_{dashboard_id}_3", "chartName": "转化漏斗", "chartType": "funnel"},
        ],
        "updateTime": "2026-08-05T10:30:00Z",
    })


def _mock_list_user_clusters(payload: dict) -> dict:
    project_id = payload.get("projectId", 0)
    return _ok({
        "total": 5,
        "list": [
            {"clusterName": f"project_{project_id}_paying_users", "clusterId": 501, "userCount": 12847, "clusterType": "cluster_by_static_condition"},
            {"clusterName": f"project_{project_id}_whale_users", "clusterId": 502, "userCount": 342, "clusterType": "cluster_by_static_condition"},
            {"clusterName": f"project_{project_id}_new_users_d7", "clusterId": 503, "userCount": 5621, "clusterType": "cluster_by_static_condition"},
            {"clusterName": f"project_{project_id}_churn_risk", "clusterId": 504, "userCount": 891, "clusterType": "cluster_by_static_condition"},
            {"clusterName": f"project_{project_id}_high_retention", "clusterId": 505, "userCount": 3421, "clusterType": "cluster_by_static_condition"},
        ],
    })


def _mock_event_analyze(project_id: int, payload: dict) -> dict:
    return _ok({
        "rows": [
            {"channel": "meta", "event_count": 45230, "revenue": 45230.50, "projectId": project_id},
            {"channel": "google", "event_count": 28450, "revenue": 28450.20, "projectId": project_id},
            {"channel": "organic", "event_count": 15230, "revenue": 8923.00, "projectId": project_id},
            {"channel": "tiktok", "event_count": 12847, "revenue": 15230.80, "projectId": project_id},
            {"channel": "ios", "event_count": 9823, "revenue": 12450.00, "projectId": project_id},
        ],
    })


def _mock_sql_query(project_id: int, sql: str) -> dict:
    return _ok({
        "columns": ["campaign_id", "ad_spend", "revenue", "roi"],
        "rows": [
            ["meta_001", 5000.00, 45230.50, 9.05],
            ["meta_002", 3200.00, 12847.20, 4.01],
            ["google_003", 1500.00, 8923.00, 5.95],
            ["tiktok_004", 2800.00, 22450.80, 8.02],
            ["organic_005", 0.00, 8923.00, float("inf")],
        ],
    })


def _mock_list_metrics(project_id: int) -> dict:
    return _ok([
        {"metricId": 1, "metricName": "DAU", "displayName": "日活跃用户", "projectId": project_id},
        {"metricId": 2, "metricName": "revenue", "displayName": "收入", "projectId": project_id},
        {"metricId": 3, "metricName": "roi", "displayName": "投资回报率", "projectId": project_id},
        {"metricId": 4, "metricName": "retention_d1", "displayName": "次日留存率", "projectId": project_id},
        {"metricId": 5, "metricName": "conversion_rate", "displayName": "转化率", "projectId": project_id},
    ])


# ---------------------------------------------------------------------------
# Mock Dispatcher — 根据 API path 分发到对应 mock 数据
# ---------------------------------------------------------------------------

def build_mock_request_handler(client: ThinkingDataClient):
    """返回一个函数，替换 client._request 的真实 HTTP 调用。"""

    original_request = client._request

    def mock_request(method: str, path: str, params=None, body=None, extra_params=None):
        # 构造统一参数
        merged = {"token": "mock_token"}
        if params:
            merged.update(params)
        if extra_params:
            merged.update(extra_params)

        pid = merged.get("projectId", 0)

        # 路由匹配
        if path == "/open/project-list":
            return _mock_list_user_projects(merged.get("loginName", "admin"))
        elif path == "/open/list-event":
            return _mock_list_events(pid)
        elif path == "/open/list-user-property":
            return _mock_list_user_properties(pid)
        elif path == "/open/dashboard-list":
            return _mock_list_dashboards(pid)
        elif path == "/open/dashboard-detail":
            return _mock_dashboard_detail(pid, merged.get("dashboardId", 0))
        elif path == "/open/user-cluster-list":
            return _mock_list_user_clusters(body or {})
        elif path == "/open/event-analyze":
            return _mock_event_analyze(pid, body or {})
        elif path == "/open/sql-query":
            return _mock_sql_query(pid, (body or {}).get("sql", ""))
        elif path == "/open/metric-list":
            return _mock_list_metrics(pid)
        else:
            # 未 mock 的接口返回通用成功响应
            print(f"       ⚠️  接口 {path} 未配置 mock，返回通用响应")
            return _ok({"note": f"mock not configured for {path}"})

    return mock_request


# ---------------------------------------------------------------------------
# E2E 测试套件
# ---------------------------------------------------------------------------

def main() -> int:
    # 使用测试用 base_url（不会真的发请求）
    client = ThinkingDataClient("https://mock.thinkingdata.local:8996", "mock_test_token")

    # 拦截 _request，用 mock 数据替代真实 HTTP 调用
    mock_handler = build_mock_request_handler(client)
    client._request = mock_handler  # type: ignore[assignment]

    test_project_ids = [6, 4, 2]
    test_dashboard_ids = [162, 132, 117]

    total_steps = 9
    current = 0
    failures = 0

    # ------------------------------------------------------------------
    # Step 1: 连通性 + Token 有效性
    # ------------------------------------------------------------------
    current += 1
    try:
        result = client.list_user_projects("admin")
        log(current, total_steps, "连通性 + Token 验证",
            f"base_url=https://mock.thinkingdata.local:8996", ok=True)
        projects = result["data"]["list"]
        print(f"       📋 项目列表 ({len(projects)} 个):")
        for p in projects:
            print(f"          - {p['projectName']} (id={p['projectId']}, appId={p['appId']})")
    except Exception as e:
        log(current, total_steps, "连通性 + Token 验证", str(e), ok=False)
        failures += 1

    # ------------------------------------------------------------------
    # Step 2: 事件列表
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            result = client.list_events(pid)
            events = result["data"]
            log(current, total_steps, f"项目 {pid} — 事件列表",
                f"事件数量: {len(events)}", ok=True)
            print(f"       📋 事件列表: {', '.join(e['eventName'] for e in events[:5])}...")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 事件列表", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 3: 用户属性列表
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            result = client.list_user_properties(pid)
            props = result["data"]
            log(current, total_steps, f"项目 {pid} — 用户属性列表",
                f"属性数量: {len(props)}", ok=True)
            print(f"       🏷️  用户属性: {', '.join(p['propertyName'] for p in props[:4])}...")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 用户属性列表", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 4: 看板列表
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            result = client.list_dashboards(pid)
            dashboards = result["data"]
            log(current, total_steps, f"项目 {pid} — 看板列表",
                f"看板数量: {len(dashboards)}", ok=True)
            for d in dashboards:
                print(f"       📊 {d['dashboardName']} (id={d['dashboardId']}, 默认={d['isDefault']})")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 看板列表", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 5: 看板详情
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        for did in test_dashboard_ids:
            try:
                result = client.get_dashboard_detail(pid, did)
                charts = result["data"]["charts"]
                log(current, total_steps, f"项目 {pid} — 看板详情 (id={did})",
                    f"图表数量: {len(charts)}", ok=True)
                for c in charts:
                    print(f"          📈 {c['chartName']} (type={c['chartType']})")
            except Exception as e:
                log(current, total_steps, f"项目 {pid} — 看板详情 (id={did})", str(e), ok=False)
                failures += 1

    # ------------------------------------------------------------------
    # Step 6: 用户分群列表
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            result = client.list_user_clusters({
                "projectId": pid,
                "clusterCatalog": "catalog_cluster",
                "clusterTypes": ["cluster_by_static_condition"],
                "pagerHeader": {"pageNum": 1, "pageSize": 10},
            })
            clusters = result["data"]["list"]
            log(current, total_steps, f"项目 {pid} — 用户分群列表",
                f"分群数量: {len(clusters)}", ok=True)
            for c in clusters:
                print(f"       👥 {c['clusterName']} (用户数: {c['userCount']})")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 用户分群列表", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 7: 事件分析 (核心 — 投放对账场景)
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            result = client.event_analyze(pid, {
                "events": [
                    {"eventName": "page_view", "analysis": "COUNT", "property": "#event_name"},
                    {"eventName": "purchase", "analysis": "SUM", "property": "#total_revenue"},
                ],
                "timeRange": {"start": "2026-08-01", "end": "2026-08-05"},
                "groupBy": ["#channel"],
            })
            rows = result["data"]["rows"]
            log(current, total_steps, f"项目 {pid} — 事件分析 (channel 维度)",
                f"数据行数: {len(rows)}", ok=True)
            total_revenue = sum(r.get("revenue", 0) for r in rows)
            total_events = sum(r.get("event_count", 0) for r in rows)
            print(f"       📈 总事件数: {total_events:,} | 总收入: ¥{total_revenue:,.2f}")
            for row in rows:
                print(f"          {row['channel']}: {row['event_count']:,} 次事件, ¥{row['revenue']:,.2f} 收入")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 事件分析", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 8: SQL 查询 (最灵活的数据打通方式)
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            sql = f"SELECT campaign_id, ad_spend, revenue, roi FROM v_event_{pid} WHERE event_name='purchase' AND roi > 3.0 ORDER BY roi DESC LIMIT 5"
            result = client.sql_query(pid, sql)
            data = result["data"]
            log(current, total_steps, f"项目 {pid} — SQL 查询",
                f"SQL: SELECT ... FROM v_event_{pid} ... LIMIT 5", ok=True)
            print(f"       🔍 查询结果 ({len(data['rows'])} 行):")
            header = " | ".join(data["columns"])
            print(f"          {header}")
            print(f"          {'-' * len(header)}")
            for row in data["rows"]:
                print(f"          {' | '.join(str(v) for v in row)}")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — SQL 查询", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 9: 指标列表
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            result = client.list_metrics(pid)
            metrics = result["data"]
            log(current, total_steps, f"项目 {pid} — 指标列表",
                f"指标数量: {len(metrics)}", ok=True)
            for m in metrics:
                print(f"       📏 {m['displayName']} ({m['metricName']})")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 指标列表", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # 总结
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    total = current
    passed = total - failures
    print(f"🏁 Mock E2E 测试完成: {passed}/{total} 通过")
    print(f"   测试项目: {', '.join(str(p) for p in test_project_ids)}")
    print(f"   测试看板: {', '.join(str(d) for d in test_dashboard_ids)}")
    if failures == 0:
        print("✅ 所有 9 个接口调用逻辑验证通过！")
        print()
        print("📋 已验证的接口:")
        print("   1. list_user_projects      — 项目列表")
        print("   2. list_events             — 事件元数据")
        print("   3. list_user_properties   — 用户属性元数据")
        print("   4. list_dashboards         — 看板列表")
        print("   5. get_dashboard_detail    — 看板详情")
        print("   6. list_user_clusters      — 用户分群")
        print("   7. event_analyze           — 事件分析 (投放对账)")
        print("   8. sql_query               — SQL 灵活取数")
        print("   9. list_metrics            — 指标列表")
        print()
        print("🔜 下一步: 在 .env 中配置 THINKINGDATA_TOKEN 后，")
        print("    运行 python scripts/e2e_thinkingdata.py 连接真实数数实例")
    else:
        print(f"⚠️  有 {failures} 个接口失败，请检查上方日志")
    print("=" * 60)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())