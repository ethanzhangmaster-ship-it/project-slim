"""
E14.7.1 — Meta (Facebook/Instagram) Ads live client (Lean: urllib only, no deps).

P1.3 把真实 Meta Ads 买量数据接入 E17.1 Growth Reality Hub 的 acquisition 域。
这是 Meta 唯一真实传输层（对比 monetization/reality/production/meta_reader.py 的
sample-backed 假数据——那里只读 JSON 不接 API，本文件才是真打 Graph API）。

设计（与 operation/providers/live/adjust/kpi_client.py 一致）：
- 仅读（GET insights），绝不写；符合 P2 之前「只读拉真实状态」铁律。
- urllib 传输层 + 代理感知（本机带代理 127.0.0.1:7897 才能出 GFW）。
- 真实调用才能置 real_api_called=True（由 MetaRealitySource 负责）。
- 测试用 mock server 替换 GRAPH_BASE 指向 127.0.0.1，仍真实跑 urllib。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


GRAPH_BASE = "https://graph.facebook.com"


class MetaError(Exception):
    pass


class MetaAuthError(MetaError):
    pass


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
def _store_path() -> str:
    # operation/providers/live/meta/meta_client.py
    # -> workspace/credentials/live_accounts.json
    here = os.path.dirname(os.path.abspath(__file__))
    lf_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(here)))))
    return os.path.join(lf_root, "credentials", "live_accounts.json")


def load_meta_config() -> Dict[str, Any]:
    path = _store_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data.get("meta", {}) or {}


def _proxy_from_env() -> Optional[str]:
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(k)
        if v:
            return v
    return None


def _open(url: str, headers: Dict[str, str], timeout: int,
          proxy: Optional[str]) -> Any:
    req = urllib.request.Request(url, headers=headers)
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _request_json(token: str, url: str, params: Optional[Dict] = None,
                  timeout: int = 40, proxy: Optional[str] = None
                  ) -> Tuple[Any, str]:
    full = url if not params else f"{url}?{urllib.parse.urlencode(params)}"
    hdr = {"Authorization": f"Bearer {token}"}
    try:
        resp = _open(full, hdr, timeout, proxy)
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body), "Bearer"
    except urllib.error.HTTPError as e:
        err = e.read()[:400].decode("utf-8", errors="replace")
        if e.code in (401, 403):
            raise MetaAuthError(f"HTTP {e.code}: {err}") from e
        raise MetaError(f"HTTP {e.code}: {err}") from e
    except urllib.error.URLError as e:
        p = proxy or _proxy_from_env()
        if p:
            try:
                resp = _open(full, hdr, timeout, p)
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body), "Bearer"
            except Exception as ex:
                raise MetaError(f"network: {ex}") from ex
        raise MetaError(f"network: {e}") from e


# --------------------------------------------------------------------------- #
# 真实读取：per-campaign insights（含 install 动作）
# --------------------------------------------------------------------------- #
def fetch_campaign_insights(
    access_token: str,
    ad_account_id: str,
    start: str,
    end: str,
    timeout: int = 40,
    proxy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """真实拉取 Meta 广告系列级 insights（spend / impressions / installs）。

    Meta 的 install 在 ``actions`` 数组里（action_type 含 ``install``），
    这里解析成结构化每行：campaign_id / campaign_name / spend / impressions /
    installs / cpm / cpp / country（取 insights 的 ``country`` 维度若有）/ platform。

    Returns: 结构化 campaign 列表（空列表表示无数据/出错，不抛异常）。
    """
    if not access_token or not ad_account_id:
        raise MetaError("access_token 与 ad_account_id 均为必填")
    acct = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
    fields = (
        "name,"
        "insights.fields("
        "spend,impressions,actions,cpm,cpp,country"
        "){spend,impressions,actions,cpm,cpp,country}"
    )
    params = {
        "fields": fields,
        "time_range": json.dumps({"since": start, "until": end}),
        "limit": "200",
        "access_token": access_token,
    }
    url = f"{GRAPH_BASE}/v19.0/{acct}/campaigns"
    try:
        data, _ = _request_json(access_token, url, params=params,
                                timeout=timeout, proxy=proxy)
    except MetaError:
        return []
    return _parse_campaign_insights(data)


def _parse_campaign_insights(data: Any) -> List[Dict[str, Any]]:
    """把 Meta Graph API 的 campaigns+insights JSON 解析成结构化行。

    标准响应：{"data":[{"id","name","insights":{"data":[{"spend","impressions",
    "actions":[{"action_type","value"}],"cpm","cpp","country"}]}}]}
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(data, dict):
        return out
    for c in data.get("data", []) or []:
        if not isinstance(c, dict):
            continue
        ins = (c.get("insights") or {}).get("data") or []
        if not ins:
            continue
        row0 = ins[0]
        spend = _to_float(row0.get("spend"))
        impressions = int(_to_float(row0.get("impressions")))
        installs = _sum_installs(row0.get("actions"))
        # 多日 insights 会拆成多条，这里对 spend/installs 求和、impressions 取首条
        for extra in ins[1:]:
            spend += _to_float(extra.get("spend"))
            installs += _sum_installs(extra.get("actions"))
        out.append({
            "campaign_id": c.get("id", ""),
            "campaign_name": c.get("name", ""),
            "spend": round(spend, 2),
            "impressions": impressions,
            "installs": installs,
            "cpm": _to_float(row0.get("cpm")),
            "cpp": _to_float(row0.get("cpp")),
            "country": (row0.get("country") or ""),
            "platform": "meta",
        })
    return out


def _sum_installs(actions: Any) -> int:
    if not isinstance(actions, list):
        return 0
    total = 0
    for a in actions:
        if not isinstance(a, dict):
            continue
        at = str(a.get("action_type", "")).lower()
        if "install" in at:
            total += int(_to_float(a.get("value")))
    return total


def _to_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------- #
# 真实写入：暂停 / 激活广告系列（campaign/update）
# --------------------------------------------------------------------------- #
def update_campaign_status(
    access_token: str,
    campaign_id: str,
    status: str,                 # "PAUSED" | "ACTIVE"
    proxy: Optional[str] = None,
    timeout: int = 40,
) -> Dict[str, Any]:
    """真实调用 Meta Graph API campaign/update 暂停或激活广告系列（写入动作）。

    这是 Meta 唯一真实「写」传输层，专供 P2.2 MetaExecutionProvider 落地
    PAUSE_CAMPAIGN 使用。与 fetch_campaign_insights（只读）共用代理感知与
    Bearer 鉴权；真实调用成功后由 Provider 负责置 real_api_called=True。

    Returns:
        {"success": bool, "data": {...}} 或 {"success": False, "error": str}
    """
    if not access_token or not campaign_id:
        raise MetaError("access_token 与 campaign_id 均为必填")
    if status not in ("PAUSED", "ACTIVE"):
        raise MetaError(f"非法 campaign status：{status!r}")
    url = f"{GRAPH_BASE}/v19.0/{campaign_id}"
    body = urllib.parse.urlencode({"status": status}).encode("utf-8")
    hdr = {"Authorization": f"Bearer {access_token}",
           "Content-Type": "application/x-www-form-urlencoded"}
    try:
        req = urllib.request.Request(url, data=body, method="POST", headers=hdr)
        p = proxy or _proxy_from_env()
        if p:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": p, "https": p}))
            opener.open(req, timeout=timeout)
        else:
            urllib.request.urlopen(req, timeout=timeout)
        return {"success": True, "data": {"campaign_id": campaign_id,
                                          "status": status}}
    except urllib.error.HTTPError as e:
        err = e.read()[:400].decode("utf-8", errors="replace")
        if e.code in (401, 403):
            raise MetaAuthError(f"HTTP {e.code}: {err}") from e
        return {"success": False, "error": f"HTTP {e.code}: {err}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"network: {e}"}


__all__ = ["MetaError", "MetaAuthError", "load_meta_config",
           "fetch_campaign_insights", "update_campaign_status"]
