from __future__ import annotations

from time import sleep
from typing import Any

import requests


class ThinkingDataClient:
    def __init__(self, base_url: str, token: str) -> None:
        base_url = base_url.rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise ValueError("ThinkingData base_url must start with https:// or http://")
        self._base_url = base_url
        self._token = token.strip()

    # ------------------------------------------------------------------
    # Model Query API (模型查询 API)
    # ------------------------------------------------------------------

    def event_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/event-analyze", body=payload, extra_params={"projectId": project_id})

    def retention_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/retention-analyze", body=payload, extra_params={"projectId": project_id})

    def funnel_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/funnel-analyze", body=payload, extra_params={"projectId": project_id})

    def interval_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/interval-analyze", body=payload, extra_params={"projectId": project_id})

    def distribution_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/distribution-analyze", body=payload, extra_params={"projectId": project_id})

    def path_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/path-analyze", body=payload, extra_params={"projectId": project_id})

    def property_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/property-analyze", body=payload, extra_params={"projectId": project_id})

    def attribution_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/attribution-analyze", body=payload, extra_params={"projectId": project_id})

    def user_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/user-analyze", body=payload, extra_params={"projectId": project_id})

    def behavior_sequence_analyze(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/behavior-sequence-analyze", body=payload, extra_params={"projectId": project_id})

    def user_list(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/user-list", body=payload, extra_params={"projectId": project_id})

    # ------------------------------------------------------------------
    # Custom Query API (数据自定义查询 API)
    # ------------------------------------------------------------------

    def sql_query(self, project_id: int, sql: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/sql-query",
            body={"sql": sql},
            extra_params={"projectId": project_id},
        )

    # ------------------------------------------------------------------
    # User Cluster & Tag API (用户分群和标签 API)
    # ------------------------------------------------------------------

    def add_user_cluster(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/user-cluster-add", body=payload, extra_params={"projectId": project_id})

    def get_user_cluster_detail(self, project_id: int, cluster_name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/open/user-cluster-detail",
            params={"projectId": project_id, "clusterName": cluster_name},
        )

    def update_user_cluster_by_name(self, project_id: int, cluster_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/user-cluster-update-by-name",
            body=payload,
            extra_params={"projectId": project_id, "clusterName": cluster_name},
        )

    def delete_user_cluster_by_name(self, project_id: int, cluster_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/delete-user-cluster-by-name",
            extra_params={"projectId": project_id, "clusterName": cluster_name},
        )

    def list_user_clusters(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/user-cluster-list", body=payload)

    # ------------------------------------------------------------------
    # Generate SQL API (生成SQL语句 API)
    # ------------------------------------------------------------------

    def get_sql_for_user_search(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/get-sql-for-user-search",
            body=payload,
            extra_params={"projectId": project_id},
        )

    # ------------------------------------------------------------------
    # Metadata Management API (元数据管理 API)
    # ------------------------------------------------------------------

    def list_events(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", "/open/list-event", params={"projectId": project_id})

    def list_event_properties(self, project_id: int, event_name: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"projectId": project_id}
        if event_name:
            params["eventName"] = event_name
        return self._request("GET", "/open/list-event-property", params=params)

    def list_user_properties(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", "/open/list-user-property", params={"projectId": project_id})

    def get_event_property_detail(self, project_id: int, event_name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/open/list-event-property-detail",
            params={"projectId": project_id, "eventName": event_name},
        )

    def list_event_categories(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", "/open/list-event-category", params={"projectId": project_id})

    # ------------------------------------------------------------------
    # Dashboard Management API (看板报表管理 API)
    # ------------------------------------------------------------------

    def list_dashboards(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", "/open/dashboard-list", params={"projectId": project_id})

    def get_dashboard_detail(self, project_id: int, dashboard_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            "/open/dashboard-detail",
            params={"projectId": project_id, "dashboardId": dashboard_id},
        )

    def create_dashboard(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/dashboard-create",
            body=payload,
            extra_params={"projectId": project_id},
        )

    def update_dashboard(self, project_id: int, dashboard_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/dashboard-update",
            body=payload,
            extra_params={"projectId": project_id, "dashboardId": dashboard_id},
        )

    def delete_dashboard(self, project_id: int, dashboard_id: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/dashboard-delete",
            extra_params={"projectId": project_id, "dashboardId": dashboard_id},
        )

    # ------------------------------------------------------------------
    # Dimension Table API (维度表 API)
    # ------------------------------------------------------------------

    def list_dimension_tables(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", "/open/dimension-table-list", params={"projectId": project_id})

    def sync_dimension_table(self, project_id: int, table_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/dimension-table-sync",
            extra_params={"projectId": project_id, "tableName": table_name},
        )

    # ------------------------------------------------------------------
    # Data Table API (数据表 API)
    # ------------------------------------------------------------------

    def list_data_tables(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", "/open/list-data-table", params={"projectId": project_id})

    def get_data_table_detail(self, project_id: int, table_name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/open/data-table-detail",
            params={"projectId": project_id, "tableName": table_name},
        )

    def create_data_table(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/create-data-table",
            body=payload,
            extra_params={"projectId": project_id},
        )

    def delete_data_table(self, project_id: int, table_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/delete-data-table",
            extra_params={"projectId": project_id, "tableName": table_name},
        )

    def query_data_table(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/data-table-query",
            body=payload,
            extra_params={"projectId": project_id},
        )

    # ------------------------------------------------------------------
    # Metric Query API (指标查询 API)
    # ------------------------------------------------------------------

    def list_metrics(self, project_id: int) -> dict[str, Any]:
        return self._request("GET", "/open/metric-list", params={"projectId": project_id})

    def query_metric(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/open/metric-query", body=payload, extra_params={"projectId": project_id})

    # ------------------------------------------------------------------
    # User Management API (用户管理 API)
    # ------------------------------------------------------------------

    def list_auth_users_by_login_names(self, login_names: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/list-auth-users-by-login-names",
            body={"loginNames": login_names},
        )

    def get_auth_user_info(self, login_name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/open/get-auth-user-info-by-login-name",
            params={"loginName": login_name},
        )

    def get_auth_user_status(self, login_name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/open/get-auth-user-status",
            params={"loginName": login_name},
        )

    def freeze_user(self, login_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/member-lock",
            extra_params={"loginName": login_name},
        )

    def unfreeze_user(self, login_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/member-unlock",
            extra_params={"loginName": login_name},
        )

    def unbind_user_mfa(self, login_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/unbind-auth-user-mfa",
            extra_params={"loginName": login_name},
        )

    def batch_create_users_and_set_roles(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/batch-create-auth-user-and-set-roles",
            body=payload,
        )

    def create_sso_user(self, login_type: str, login_name: str, password: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"loginType": login_type, "loginName": login_name}
        if password:
            params["password"] = password
        try:
            return self._request("GET", "/open/create/ssoUser", params=params)
        finally:
            params.clear()

    def delete_user_from_project(self, project_id: int, login_name: str, handover_to: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/delete-auth-user-from-project",
            extra_params={
                "projectId": project_id,
                "loginName": login_name,
                "handoverToLoginName": handover_to,
            },
        )

    def delete_user_from_system(self, login_name: str, handover_to: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/delete-auth-user-from-system",
            extra_params={"loginName": login_name, "handoverToLoginName": handover_to},
        )

    def get_user_group_by_name(self, project_id: int, group_name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/open/get-user-group-by-name",
            params={"projectId": project_id, "userGroupName": group_name},
        )

    def create_user_group(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/create-user-group",
            body=payload,
            extra_params={"projectId": project_id},
        )

    def update_user_group(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/update-user-group",
            body=payload,
            extra_params={"projectId": project_id},
        )

    # ------------------------------------------------------------------
    # Project Management API (项目管理 API)
    # ------------------------------------------------------------------

    def list_user_projects(self, login_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/project-list",
            extra_params={"loginName": login_name},
        )

    def update_project_info(self, project_id: int, project_name: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/project/update-project-info",
            body={"projectName": project_name},
            extra_params={"projectId": project_id},
        )

    def create_project(self, project_name: str, load_history: int = 0) -> dict[str, Any]:
        return self._request(
            "POST",
            "/open/project/generate-project-app-id",
            extra_params={"projectName": project_name, "loadHistory": load_history},
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_params: dict[str, Any] = {"token": self._token}
        if params:
            merged_params.update(params)
        if extra_params:
            merged_params.update(extra_params)

        url = f"{self._base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                if method.upper() == "GET":
                    response = requests.get(url, params=merged_params, timeout=60)
                else:
                    response = requests.post(url, params=merged_params, json=body or {}, timeout=60)
                response.raise_for_status()
                data = response.json()
                return_code = data.get("return_code")
                if return_code not in (0, None):
                    raise RuntimeError(
                        f"ThinkingData API error (code={return_code}): {data.get('return_message', 'unknown')}"
                    )
                return data
            except requests.RequestException as exc:
                last_error = self._redact_token(exc)
                if attempt == 2:
                    break
                sleep(1.5 * (attempt + 1))

        if last_error:
            raise last_error
        raise RuntimeError("Unknown ThinkingData API request failure.")

    def _redact_token(self, exc: requests.RequestException) -> requests.RequestException:
        """Replace the token string in error messages to prevent credential leakage."""
        if not self._token:
            return exc

        redacted = "***REDACTED***"
        token = self._token

        if hasattr(exc, "request") and exc.request is not None and token in str(exc.request.url):
            exc.request.url = exc.request.url.replace(token, redacted)

        if hasattr(exc, "response") and exc.response is not None:
            if token in str(exc.response.url):
                exc.response.url = exc.response.url.replace(token, redacted)

        if token in str(exc):
            safe_msg = str(exc).replace(token, redacted)
            new_exc = exc.__class__(safe_msg)
            if hasattr(exc, "request"):
                new_exc.request = exc.request
            if hasattr(exc, "response"):
                new_exc.response = exc.response
            return new_exc

        return exc