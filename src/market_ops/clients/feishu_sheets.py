from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests


@dataclass(slots=True)
class FeishuSheetRef:
    source_type: str
    token: str
    sheet_id: str
    original_url: str


class FeishuSheetsClient:
    def __init__(self, app_id: str, app_secret: str) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._tenant_token: str | None = None
        self._base_url = "https://open.feishu.cn/open-apis"

    def parse_url(self, url: str) -> FeishuSheetRef:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2 or parts[0] not in {"sheets", "wiki"}:
            raise ValueError(f"Unsupported Feishu sheet URL: {url}")
        sheet_id = parse_qs(parsed.query).get("sheet", [None])[0]
        if not sheet_id:
            raise ValueError(f"Missing sheet id in Feishu URL: {url}")
        return FeishuSheetRef(
            source_type=parts[0],
            token=parts[1],
            sheet_id=sheet_id,
            original_url=url,
        )

    def resolve_spreadsheet_token(self, ref: FeishuSheetRef) -> tuple[str, str | None]:
        if ref.source_type == "sheets":
            return ref.token, None
        response = self._request(
            "GET",
            "/wiki/v2/spaces/get_node",
            params={"token": ref.token},
        )
        node = response.json()["data"]["node"]
        return node["obj_token"], node.get("title")

    def list_sheets(self, url: str) -> list[dict[str, Any]]:
        ref = self.parse_url(url)
        spreadsheet_token, _ = self.resolve_spreadsheet_token(ref)
        response = self._request(
            "GET",
            f"/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query",
        )
        return response.json()["data"]["sheets"]

    def find_sheet_id_by_title(self, url: str, title: str) -> str:
        for sheet in self.list_sheets(url):
            if sheet["title"] == title:
                return sheet["sheet_id"]
        raise ValueError(f"Sheet title not found: {title}")

    def ensure_sheet_id(self, url: str, title: str) -> str:
        try:
            return self.find_sheet_id_by_title(url, title)
        except ValueError:
            return self.create_sheet(url, title)

    def read_values(
        self,
        url: str,
        range_suffix: str,
        sheet_id: str | None = None,
    ) -> list[list[Any]]:
        ref = self.parse_url(url)
        spreadsheet_token, _ = self.resolve_spreadsheet_token(ref)
        target_sheet_id = sheet_id or ref.sheet_id
        response = self._request(
            "GET",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values/{target_sheet_id}!{range_suffix}",
        )
        return response.json()["data"]["valueRange"].get("values", [])

    def overwrite_rows(
        self,
        url: str,
        headers: list[str],
        rows: list[list[Any]],
        *,
        sheet_title: str | None = None,
        sheet_id: str | None = None,
        read_width: str = "AZ",
        max_scan_rows: int = 5000,
    ) -> None:
        ref = self.parse_url(url)
        spreadsheet_token, _ = self.resolve_spreadsheet_token(ref)
        target_sheet_id = sheet_id or (self.ensure_sheet_id(url, sheet_title) if sheet_title else ref.sheet_id)
        existing = self.read_values(url, f"A1:{read_width}{max_scan_rows}", sheet_id=target_sheet_id)
        payload_rows = [headers, *rows]
        existing_row_count = max(len(existing), 1)
        final_row_count = max(existing_row_count, len(payload_rows))
        width = max(len(headers), max((len(row) for row in rows), default=0))
        width = max(width, len(existing[0]) if existing else 0)

        normalized_rows: list[list[Any]] = []
        for row in payload_rows:
            normalized_rows.append([self._sheet_value(value) for value in row] + [""] * (width - len(row)))
        while len(normalized_rows) < final_row_count:
            normalized_rows.append([""] * width)

        range_suffix = f"A1:{self._column_label(width)}{final_row_count}"
        self._request(
            "PUT",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/values",
            json={
                "valueRange": {
                    "range": f"{target_sheet_id}!{range_suffix}",
                    "values": normalized_rows,
                }
            },
        )

    def create_sheet(self, url: str, title: str) -> str:
        ref = self.parse_url(url)
        spreadsheet_token, _ = self.resolve_spreadsheet_token(ref)
        existing_sheets = self.list_sheets(url)
        response = self._request(
            "POST",
            f"/sheets/v2/spreadsheets/{spreadsheet_token}/sheets_batch_update",
            json={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": title,
                                "index": len(existing_sheets),
                            }
                        }
                    }
                ]
            },
        )
        replies = response.json().get("data", {}).get("replies", [])
        if replies:
            sheet = replies[0].get("addSheet", {}).get("properties", {})
            if sheet.get("sheetId"):
                return str(sheet["sheetId"])
            if sheet.get("sheet_id"):
                return str(sheet["sheet_id"])
        return self.find_sheet_id_by_title(url, title)

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if not self._tenant_token:
            self._tenant_token = self._fetch_tenant_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._tenant_token}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    timeout=30,
                    **kwargs,
                )
                if response.status_code >= 400:
                    body = response.text[:1000]
                    raise RuntimeError(f"Feishu Sheets HTTP {response.status_code}: {body}")
                payload = response.json()
                if payload.get("code") not in (0, None):
                    raise RuntimeError(f"Feishu Sheets API error: {payload}")
                return response
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt == 2:
                    break
                sleep(1.5 * (attempt + 1))
        if last_error:
            raise last_error
        raise RuntimeError("Unknown Feishu Sheets request failure.")

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

    @staticmethod
    def _sheet_value(value: Any) -> Any:
        if value is None:
            return ""
        return value

    @staticmethod
    def _column_label(index: int) -> str:
        if index <= 0:
            return "A"
        result = []
        current = index
        while current > 0:
            current, remainder = divmod(current - 1, 26)
            result.append(chr(ord("A") + remainder))
        return "".join(reversed(result))
