"""ThinkingData 端到端集成测试脚本.

使用真实数数实例 (https://www.starmoondata.com:8996) 跑完整链路。
运行前需在 .env 中配置 THINKINGDATA_TOKEN。

执行: python scripts/e2e_thinkingdata.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "src")

from market_ops.clients.thinkingdata import ThinkingDataClient
from market_ops.config import load_settings


# ---------------------------------------------------------------------------
# 日志工具
# ---------------------------------------------------------------------------

def log(step: int, total: int, title: str, detail: str = "", ok: bool | None = None):
    icon = "✅" if ok is True else "❌" if ok is False else "⏳"
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{step}/{total}] {icon} {title}")
    if detail:
        print(f"       {detail}")


def pretty_json(data: dict | list, indent: int = 6, max_len: int = 120) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=indent)
    if len(raw) > max_len * 4:
        return raw[:max_len] + " ... (truncated)"
    return raw


# ---------------------------------------------------------------------------
# E2E 测试套件
# ---------------------------------------------------------------------------

def main() -> int:
    settings = load_settings()

    if not settings.thinkingdata_base_url:
        print("❌ 未配置 THINKINGDATA_BASE_URL，请在 .env 中设置")
        return 1
    if not settings.thinkingdata_token:
        print("❌ 未配置 THINKINGDATA_TOKEN，请在 .env 中设置 API 查询密钥")
        return 1

    client = ThinkingDataClient(settings.thinkingdata_base_url, settings.thinkingdata_token)

    # 从看板 URL 解析出的 projectIds
    # 2_117 → projectId=2, 4_132 → projectId=4, 6_162 → projectId=6
    test_project_ids = [6]  # 先用一个测试，成功后扩展
    test_dashboard_ids = [162, 132, 117]  # panel IDs

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
            f"base_url={settings.thinkingdata_base_url}", ok=True)
        print(f"       返回: {pretty_json(result)}")
    except Exception as e:
        log(current, total_steps, "连通性 + Token 验证", str(e), ok=False)
        failures += 1
        print("       💡 如果 Token 无效，请在数数后台重新生成 OpenAPI 查询密钥")
        return 1

    # ------------------------------------------------------------------
    # Step 2: 项目列表
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            result = client.list_events(pid)
            event_count = len(result.get("data", [])) if isinstance(result.get("data"), list) else "N/A"
            log(current, total_steps, f"项目 {pid} — 事件列表",
                f"事件数量: {event_count}", ok=True)
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
            prop_count = len(result.get("data", [])) if isinstance(result.get("data"), list) else "N/A"
            log(current, total_steps, f"项目 {pid} — 用户属性列表",
                f"属性数量: {prop_count}", ok=True)
            print(f"       示例: {pretty_json(result.get('data', [])[:2] if isinstance(result.get('data'), list) else result)}")
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
            dashboards = result.get("data", [])
            dash_count = len(dashboards) if isinstance(dashboards, list) else "N/A"
            log(current, total_steps, f"项目 {pid} — 看板列表",
                f"看板数量: {dash_count}", ok=True)
            if isinstance(dashboards, list):
                for d in dashboards[:3]:
                    print(f"       📊 {d.get('dashboardName', 'N/A')} (id={d.get('dashboardId', 'N/A')})")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 看板列表", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 5: 看板详情
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        for did in test_dashboard_ids[:1]:  # 只测第一个
            try:
                result = client.get_dashboard_detail(pid, did)
                log(current, total_steps, f"项目 {pid} — 看板详情 (id={did})",
                    f"返回数据: {pretty_json(result)[:100]}", ok=True)
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
            clusters = result.get("data", {}).get("list", []) if isinstance(result.get("data"), dict) else []
            log(current, total_steps, f"项目 {pid} — 用户分群列表",
                f"分群数量: {len(clusters)}", ok=True)
            for c in clusters[:3]:
                print(f"       👥 {c.get('clusterName', 'N/A')} (用户数: {c.get('userCount', 'N/A')})")
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
                ],
                "timeRange": {"start": "2026-08-01", "end": "2026-08-05"},
                "groupBy": ["#channel"],
            })
            rows = result.get("data", {}).get("rows", []) if isinstance(result.get("data"), dict) else []
            log(current, total_steps, f"项目 {pid} — 事件分析 (page_view by channel)",
                f"数据行数: {len(rows)}", ok=True)
            for row in rows[:3]:
                print(f"       📈 {pretty_json(row)}")
        except Exception as e:
            log(current, total_steps, f"项目 {pid} — 事件分析", str(e), ok=False)
            failures += 1

    # ------------------------------------------------------------------
    # Step 8: SQL 查询 (最灵活的数据打通方式)
    # ------------------------------------------------------------------
    current += 1
    for pid in test_project_ids:
        try:
            sql = f"SELECT * FROM v_event_{pid} LIMIT 5"
            result = client.sql_query(pid, sql)
            log(current, total_steps, f"项目 {pid} — SQL 查询",
                f"SQL: {sql}", ok=True)
            print(f"       返回: {pretty_json(result)}")
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
            metrics = result.get("data", [])
            metric_count = len(metrics) if isinstance(metrics, list) else "N/A"
            log(current, total_steps, f"项目 {pid} — 指标列表",
                f"指标数量: {metric_count}", ok=True)
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
    print(f"🏁 E2E 测试完成: {passed}/{total} 通过")
    if failures == 0:
        print("✅ 所有接口连通正常，数数数据接入就绪！")
    else:
        print(f"⚠️  有 {failures} 个接口失败，请检查上方日志")
    print("=" * 60)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())