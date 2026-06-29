from __future__ import annotations

from itertools import islice
from typing import Any, Iterable

import requests


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, app_token: str) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._app_token = app_token
        self._token: str | None = None
        self._base_url = "https://open.feishu.cn/open-apis"

    def list_records(self, table_id: str) -> list[dict[str, Any]]:
        page_token: str | None = None
        records: list[dict[str, Any]] = []
        while True:
            params = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            response = self._request(
                "GET",
                f"/bitable/v1/apps/{self._app_token}/tables/{table_id}/records",
                params=params,
            )
            data = response.json()["data"]
            records.extend(data.get("items") or [])
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
        return records

    def batch_create_records(self, table_id: str, records: Iterable[dict[str, Any]]) -> None:
        iterator = iter(records)
        while True:
            chunk = list(islice(iterator, 200))
            if not chunk:
                return
            self._request(
                "POST",
                f"/bitable/v1/apps/{self._app_token}/tables/{table_id}/records/batch_create",
                json={"records": [{"fields": record} for record in chunk]},
            )

    def batch_update_records(self, table_id: str, records: Iterable[dict[str, Any]]) -> None:
        iterator = iter(records)
        while True:
            chunk = list(islice(iterator, 200))
            if not chunk:
                return
            self._request(
                "POST",
                f"/bitable/v1/apps/{self._app_token}/tables/{table_id}/records/batch_update",
                json={
                    "records": [
                        {"record_id": record["record_id"], "fields": record["fields"]}
                        for record in chunk
                    ]
                },
            )

    def create_record(self, table_id: str, fields: dict[str, Any]) -> None:
        self._request(
            "POST",
            f"/bitable/v1/apps/{self._app_token}/tables/{table_id}/records",
            json={"fields": fields},
        )

    def list_tables(self) -> list[dict[str, Any]]:
        page_token: str | None = None
        tables: list[dict[str, Any]] = []
        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            response = self._request(
                "GET",
                f"/bitable/v1/apps/{self._app_token}/tables",
                params=params,
            )
            data = response.json()["data"]
            tables.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
        return tables

    def list_fields(self, table_id: str) -> list[dict[str, Any]]:
        page_token: str | None = None
        fields: list[dict[str, Any]] = []
        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            response = self._request(
                "GET",
                f"/bitable/v1/apps/{self._app_token}/tables/{table_id}/fields",
                params=params,
            )
            data = response.json()["data"]
            fields.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
        return fields

    def batch_delete_records(self, table_id: str, record_ids: Iterable[str]) -> None:
        iterator = iter(record_ids)
        while True:
            chunk = list(islice(iterator, 500))
            if not chunk:
                return
            self._request(
                "POST",
                f"/bitable/v1/apps/{self._app_token}/tables/{table_id}/records/batch_delete",
                json={"records": chunk},
            )

    def create_table(self, name: str, fields: list[dict[str, Any]]) -> str:
        response = self._request(
            "POST",
            f"/bitable/v1/apps/{self._app_token}/tables",
            json={
                "table": {
                    "name": name,
                    "default_view_name": "默认视图",
                    "fields": fields,
                }
            },
        )
        data = response.json()["data"]
        return data["table_id"]

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if not self._token:
            self._token = self._fetch_tenant_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"
        headers["Content-Type"] = "application/json; charset=utf-8"
        response = requests.request(method, f"{self._base_url}{path}", headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (0, None):
            raise RuntimeError(f"Feishu API error: {payload}")
        return response

    def _fetch_tenant_token(self) -> str:
        response = requests.post(
            f"{self._base_url}/auth/v3/tenant_access_token/internal",
            json={"app_id": self._app_id, "app_secret": self._app_secret},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Failed to get Feishu token: {payload}")
        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError("Feishu token response did not include tenant_access_token.")
        return token
