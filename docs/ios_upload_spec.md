# P0 — iOS App Store 上架能力规范 (upload_spec)

**版本**: v0.1
**日期**: 2026-08-06
**作者**: TRAE Agent
**关联**: [AI_Game_Studio_OS_审计报告](file:///d:/project_slim/project_slim/AI_Game_Studio_OS_审计报告.md) P0-2、[p0_approval_gate_v2_spec.md](file:///d:/project_slim/project_slim/docs/p0_approval_gate_v2_spec.md)

---

## 1. 背景

审计报告指出 P0-2 缺口：**Apple App Store 上传 build/submit review 未实现**，导致 50% 海外市场覆盖缺失。当前代码现状：

| 文件 | 现状 | 缺口 |
|------|------|------|
| [operation/publishing/app_store/client.py](file:///d:/project_slim/project_slim/operation/publishing/app_store/client.py) | `MockAppStoreClient` 完整 mock | 无缺口（mock 用） |
| [operation/publishing/providers/app_store/real_client.py](file:///d:/project_slim/project_slim/operation/publishing/providers/app_store/real_client.py) | `AppStoreRealClient` 框架已搭好 | `upload_build` 是 stub（POST /builds 非真实端点）；`submit_review` 端点近似但未验证；无 phased release；无 build 号查询；无 TestFlight |
| [operation/providers/live/auth.py](file:///d:/project_slim/project_slim/operation/providers/live/auth.py#L31-L56) | `make_appstore_jwt` ES256 JWT 签名已实现 | 无缺口 |
| [operation/publishing/providers/models.py](file:///d:/project_slim/project_slim/operation/publishing/providers/models.py) | `PublishingChange` + `OP_*` 操作常量 | 缺 `OP_UPLOAD_BUILD_CHUNKS` / `OP_COMMIT_BUILD` / `OP_PHASED_RELEASE` / `OP_CANCEL_PHASED_RELEASE` |

**核心问题**：`upload_build` 当前实现是 `POST /builds`，但 App Store Connect API **没有这个端点**。真实流程是：
1. **创建 build 保留**（`POST /appStoreVersions` + build 文件上传预留）
2. **分片上传 IPA**（通过 App Store Connect 的 upload assets 接口，或使用 `altool`/`Transporter` CLI）
3. **提交 build**（`PATCH /builds/{id}` 提交 processing）
4. **等待 Apple 处理**（异步，通常 5-15 分钟）
5. **提交审核**（`POST /appStoreVersionSubmissions`）

---

## 2. 目标

**30 天内实现 iOS 自动上架 3 大能力**：

1. **Build Upload** — 自动上传 IPA 到 App Store Connect
2. **Submit Review** — 自动提交审核 + 审核状态轮询
3. **Phased Release** — 7 天灰度发布（Apple 标准流程）

**非目标**（明确排除）：
- ❌ TestFlight beta 测试（P1，下个季度）
- ❌ In-App Purchase 配置（走 `monetization/iap/client.py`，本 spec 不涉及）
- ❌ App Store Connect 用户/角色管理
- ❌ 审核拒绝后的自动修复（人工介入）

---

## 3. App Store Connect API 真实流程

### 3.1 Build Upload 完整流程

App Store Connect 的 build 上传**不通过 REST API**，而是通过以下两种方式之一：

#### 方式 A：altool CLI（推荐，简单）

```bash
xcrun altool --upload-app \
  -f app.ipa \
  -t ios \
  -u "apple@email.com" \
  -p "app-specific-password" \
  --apiKey "DEVELOPER_API_KEY" \
  --apiIssuer "issuer_id"
```

**优点**：Apple 官方支持，处理分片/重试/校验。
**缺点**：依赖 macOS + Xcode 环境。

#### 方式 B：App Store Connect API + Transporter（生产级）

1. **创建 upload operation**：
   ```
   POST /v1/appStoreVersionBuilds
   ```
   返回 `uploadOperations` 数组，每个包含分片上传 URL。

2. **分片上传 IPA**：
   对每个 `uploadOperation`，用 `PUT` 上传 IPA 文件分片到 Apple 提供的 GCS URL。

3. **提交 build**：
   ```
   PATCH /v1/appStoreVersionBuilds/{id}
   { "data": { "type": "appStoreVersionBuilds", "id": "{id}",
               "attributes": { "uploaded": true } } }
   ```

4. **轮询 build 状态**：
   ```
   GET /v1/builds/{id}
   ```
   状态：`PROCESSING` → `VALID` / `FAILED`

**本 spec 选择**：方式 A（altool CLI）作为首期实现，理由：
- 服务端通常是 macOS（CI/CD 环境）
- 无需实现复杂的分片上传逻辑
- Apple 官方维护，稳定性高
- 方式 B 留作 P1 优化（跨平台支持）

### 3.2 Submit Review 流程

1. **确保 build 已 processing 完成**：
   ```
   GET /v1/apps/{app_id}/builds?filter[processingState]=VALID
   ```

2. **关联 build 到 version**：
   ```
   PATCH /v1/appStoreVersions/{version_id}/relationships/build
   { "data": { "type": "builds", "id": "{build_id}" } }
   ```

3. **提交审核**：
   ```
   POST /v1/appStoreVersionSubmissions
   { "data": { "type": "appStoreVersionSubmissions",
               "relationships": { "appStoreVersion": { "data": { "type": "appStoreVersions", "id": "{version_id}" } } } } }
   ```

4. **轮询审核状态**：
   ```
   GET /v1/appStoreVersions/{version_id}
   ```
   状态映射：
   - `PREPARE_FOR_SUBMISSION` → prepare_for_submission
   - `WAITING_FOR_REVIEW` → waiting_for_review
   - `IN_REVIEW` → in_review
   - `REJECTED` → rejected
   - `PENDING_DEVELOPER_RELEASE` → approved
   - `READY_FOR_SALE` → ready_for_sale

### 3.3 Phased Release 流程

仅当 `appStoreVersion.releaseType = PHASED` 时启用。

1. **启动 phased release**（审核通过后自动触发）：
   ```
   POST /v1/appStoreVersionPhasedReleases
   { "data": { "type": "appStoreVersionPhasedReleases",
               "relationships": { "appStoreVersion": { "data": { "type": "appStoreVersions", "id": "{version_id}" } } } } }
   ```

2. **查询 phased release 状态**：
   ```
   GET /v1/appStoreVersions/{version_id}/appStoreVersionPhasedRelease
   ```
   状态：`INACTIVE` → `ACTIVE` → `COMPLETE`
   每日释放比例：1% → 2% → 5% → 10% → 20% → 50% → 100%

3. **暂停/恢复/立即完成**：
   ```
   PATCH /v1/appStoreVersionPhasedReleases/{id}
   { "data": { "type": "appStoreVersionPhasedReleases", "id": "{id}",
               "attributes": { "state": "PAUSED" | "ACTIVE" | "COMPLETE" } } }
   ```

---

## 4. 数据模型扩展

### 4.1 新增操作常量

[operation/publishing/providers/models.py](file:///d:/project_slim/project_slim/operation/publishing/providers/models.py) 新增：

```python
# Build upload 三步操作
OP_UPLOAD_BUILD_ALTOOL = "upload_build_altool"      # altool CLI 上传 IPA
OP_POLL_BUILD_STATUS = "poll_build_status"          # 轮询 build processing 状态
OP_SELECT_BUILD = "select_build"                    # 关联 build 到 version

# Phased release
OP_START_PHASED_RELEASE = "start_phased_release"
OP_PAUSE_PHASED_RELEASE = "pause_phased_release"
OP_RESUME_PHASED_RELEASE = "resume_phased_release"
OP_COMPLETE_PHASED_RELEASE = "complete_phased_release"
OP_CHECK_PHASED_RELEASE = "check_phased_release"
```

### 4.2 PublishingChange 扩展

`PublishingChange.new` 字段承载操作特定参数：

```python
# upload_build_altool
change.new = {
    "ipa_path": "/path/to/app.ipa",
    "version": "1.2.0",
    "build_number": 42,
    "apple_id": "user@email.com",        # App Store Connect 账号
    "app_specific_password": "...",       # app-specific password
    # 或 API key 方式：
    "api_key_id": "DEVELOPER_API_KEY",
    "api_issuer_id": "issuer_id",
}

# poll_build_status
change.new = {
    "app_id": "as_app_xxx",
    "version": "1.2.0",
    "build_number": 42,
    "timeout_seconds": 1800,  # 30 分钟超时
}

# start_phased_release
change.new = {
    "version_id": "v1.2.0",
}
```

### 4.3 BuildStatus 新模型

```python
@dataclass
class BuildStatus:
    """App Store Connect build processing 状态。"""
    build_id: str               # App Store Connect build ID
    version: str                # e.g. "1.2.0"
    build_number: int           # e.g. 42
    processing_state: str       # PROCESSING | VALID | FAILED
    icon_url: str = ""
    uploaded_date: str = ""
    # FAILED 时填充
    error_code: str = ""
    error_message: str = ""

    @property
    def is_valid(self) -> bool:
        return self.processing_state == "VALID"

    @property
    def is_processing(self) -> bool:
        return self.processing_state == "PROCESSING"

    @property
    def is_failed(self) -> bool:
        return self.processing_state == "FAILED"
```

---

## 5. 改造方案

### 5.1 `AppStoreRealClient` 改造

[operation/publishing/providers/app_store/real_client.py](file:///d:/project_slim/project_slim/operation/publishing/providers/app_store/real_client.py) 改造点：

#### 5.1.1 `upload_build` 重写为 altool 调用

```python
def upload_build(self, game_id: str, build_path: str,
                 version: str, build_number: int) -> dict:
    """通过 altool CLI 上传 IPA 到 App Store Connect。

    真实流程（Spec §3.1 方式 A）：
      xcrun altool --upload-app -f {ipa} -t ios \
        --apiKey {key_id} --apiIssuer {issuer_id}

    返回：
        {"success": True, "build_id": "..."} 或 {"success": False, "error": "..."}
    """
    import subprocess
    import shutil

    if not shutil.which("xcrun"):
        return {"success": False, "error": "xcrun not found — requires macOS + Xcode"}

    cred = self._credential or {}
    api_key = cred.get("api_key_id")
    issuer_id = cred.get("api_issuer_id")
    if not (api_key and issuer_id):
        return {"success": False, "error": "missing api_key_id / api_issuer_id"}

    cmd = [
        "xcrun", "altool", "--upload-app",
        "-f", build_path,
        "-t", "ios",
        "--apiKey", api_key,
        "--apiIssuer", issuer_id,
        "--output-format", "json",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800  # 30 分钟超时
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "altool upload timed out (30min)"}
    except Exception as exc:
        return {"success": False, "error": f"altool raised: {exc}"}

    if result.returncode != 0:
        return {
            "success": False,
            "error": f"altool failed (rc={result.returncode}): {result.stderr}",
        }

    # altool 成功输出是 JSON（--output-format json）
    try:
        payload = json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError:
        payload = {}

    return {
        "success": True,
        "build_id": payload.get("buildId", ""),
        "version": version,
        "build_number": build_number,
    }
```

#### 5.1.2 新增 `poll_build_status`

```python
def poll_build_status(
    self, game_id: str, version: str, build_number: int,
    timeout_seconds: int = 1800,
    poll_interval_seconds: int = 30,
) -> dict:
    """轮询 build processing 状态直到 VALID/FAILED 或超时。

    App Store Connect 异步处理 IPA，通常 5-15 分钟。

    Returns:
        {"success": True, "build_status": BuildStatus} 或
        {"success": False, "error": "...", "build_status": None}
    """
    import time

    bundle = self._resolve_bundle(game_id)
    if not bundle:
        return {"success": False, "error": "bundle_id missing"}

    deadline = time.time() + timeout_seconds
    last_state = "PROCESSING"

    while time.time() < deadline:
        # GET /v1/builds?filter[app]={app_id}&filter[version]={version}
        # &filter[preReleaseVersion.versionString]={version}
        # &filter[preReleaseVersion.buildVersion]={build_number}
        r = self._call_api(
            "GET",
            f"/builds?filter[app]={self._apps.get(game_id, {}).get('app_id', '')}"
            f"&filter[version]={version}"
            f"&filter[preReleaseVersion.buildVersion]={build_number}"
        )
        if not r.get("success"):
            # API 失败 → 等待重试（不立即 fail-closed，给 Apple 时间）
            time.sleep(poll_interval_seconds)
            continue

        builds = (r.get("data") or {}).get("data") or []
        if not builds:
            time.sleep(poll_interval_seconds)
            continue

        attrs = builds[0].get("attributes", {})
        last_state = attrs.get("processingState", "PROCESSING")

        if last_state == "VALID":
            return {
                "success": True,
                "build_status": {
                    "build_id": builds[0].get("id", ""),
                    "version": version,
                    "build_number": build_number,
                    "processing_state": "VALID",
                    "icon_url": attrs.get("iconAssetToken", {}).get("templateUrl", ""),
                    "uploaded_date": attrs.get("uploadedDate", ""),
                },
            }
        if last_state == "FAILED":
            return {
                "success": False,
                "error": f"build processing failed",
                "build_status": {
                    "build_id": builds[0].get("id", ""),
                    "version": version,
                    "build_number": build_number,
                    "processing_state": "FAILED",
                    "error_message": attrs.get("processingError", "unknown"),
                },
            }

        time.sleep(poll_interval_seconds)

    return {
        "success": False,
        "error": f"poll timed out after {timeout_seconds}s (last_state={last_state})",
        "build_status": None,
    }
```

#### 5.1.3 新增 `select_build`

```python
def select_build(self, version_id: str, build_id: str) -> dict:
    """关联 build 到 appStoreVersion（提交审核前必需）。

    PATCH /v1/appStoreVersions/{version_id}/relationships/build
    """
    path = f"/appStoreVersions/{version_id}/relationships/build"
    body = {
        "data": {"type": "builds", "id": build_id}
    }
    result = self._call_api("PATCH", path, body)
    return result if result.get("success") else result
```

#### 5.1.4 `submit_review` 修正

当前实现已近似，但缺少 `version_id` 关联。修正为：

```python
def submit_review(self, game_id: str, version_id: str | None = None) -> dict:
    """提交审核。

    若 version_id 未提供，需先查询最新 version。
    """
    if version_id is None:
        version_id = self._get_latest_version_id(game_id)
        if not version_id:
            return {"success": False, "error": "no appStoreVersion found"}

    path = "/appStoreVersionSubmissions"
    body = {
        "data": {
            "type": "appStoreVersionSubmissions",
            "relationships": {
                "appStoreVersion": {
                    "data": {"type": "appStoreVersions", "id": version_id}
                }
            },
        }
    }
    result = self._call_api("POST", path, body)
    return result if result.get("success") else result
```

#### 5.1.5 新增 phased release 方法

```python
def start_phased_release(self, version_id: str) -> dict:
    """启动 7 天灰度发布。"""
    path = "/appStoreVersionPhasedReleases"
    body = {
        "data": {
            "type": "appStoreVersionPhasedReleases",
            "relationships": {
                "appStoreVersion": {
                    "data": {"type": "appStoreVersions", "id": version_id}
                }
            },
        }
    }
    return self._call_api("POST", path, body)

def pause_phased_release(self, phased_release_id: str) -> dict:
    """暂停灰度发布。"""
    path = f"/appStoreVersionPhasedReleases/{phased_release_id}"
    body = {
        "data": {
            "type": "appStoreVersionPhasedReleases",
            "id": phased_release_id,
            "attributes": {"state": "PAUSED"},
        }
    }
    return self._call_api("PATCH", path, body)

def resume_phased_release(self, phased_release_id: str) -> dict:
    """恢复灰度发布。"""
    path = f"/appStoreVersionPhasedReleases/{phased_release_id}"
    body = {
        "data": {
            "type": "appStoreVersionPhasedReleases",
            "id": phased_release_id,
            "attributes": {"state": "ACTIVE"},
        }
    }
    return self._call_api("PATCH", path, body)

def complete_phased_release(self, phased_release_id: str) -> dict:
    """立即完成灰度发布（100% 推送）。"""
    path = f"/appStoreVersionPhasedReleases/{phased_release_id}"
    body = {
        "data": {
            "type": "appStoreVersionPhasedReleases",
            "id": phased_release_id,
            "attributes": {"state": "COMPLETE"},
        }
    }
    return self._call_api("PATCH", path, body)

def check_phased_release(self, version_id: str) -> dict:
    """查询灰度发布状态。"""
    path = f"/appStoreVersions/{version_id}/appStoreVersionPhasedRelease"
    return self._call_api("GET", path)
```

### 5.2 `AppStoreProvider` 改造

[operation/publishing/app_store/provider.py](file:///d:/project_slim/project_slim/operation/publishing/app_store/provider.py) `apply_change` 新增分支：

```python
elif operation == OP_UPLOAD_BUILD_ALTOOL:
    return self.client.upload_build(
        game_id, payload.get("ipa_path", ""),
        payload.get("version", "1.0.0"),
        payload.get("build_number", 1))
elif operation == OP_POLL_BUILD_STATUS:
    return self.client.poll_build_status(
        game_id, payload.get("version", "1.0.0"),
        payload.get("build_number", 1),
        timeout_seconds=payload.get("timeout_seconds", 1800))
elif operation == OP_SELECT_BUILD:
    return self.client.select_build(
        payload.get("version_id", ""), payload.get("build_id", ""))
elif operation == OP_START_PHASED_RELEASE:
    return self.client.start_phased_release(payload.get("version_id", ""))
elif operation == OP_PAUSE_PHASED_RELEASE:
    return self.client.pause_phased_release(payload.get("phased_release_id", ""))
elif operation == OP_RESUME_PHASED_RELEASE:
    return self.client.resume_phased_release(payload.get("phased_release_id", ""))
elif operation == OP_COMPLETE_PHASED_RELEASE:
    return self.client.complete_phased_release(payload.get("phased_release_id", ""))
elif operation == OP_CHECK_PHASED_RELEASE:
    return self.client.check_phased_release(payload.get("version_id", ""))
```

---

## 6. 完整发布流程编排

### 6.1 端到端流程

```
[IPA 文件就绪]
    ↓
1. OP_UPLOAD_BUILD_ALTOOL — altool 上传 IPA
    ↓ (success)
2. OP_POLL_BUILD_STATUS — 轮询 build processing（5-15 分钟）
    ↓ (VALID)
3. OP_SELECT_BUILD — 关联 build 到 appStoreVersion
    ↓ (success)
4. OP_SUBMIT_REVIEW — 提交审核
    ↓ (waiting_for_review)
5. OP_CHECK_STATUS — 轮询审核状态（通常 24-48 小时）
    ↓ (approved / pending_developer_release)
6. OP_START_PHASED_RELEASE — 启动 7 天灰度
    ↓
7. OP_CHECK_PHASED_RELEASE — 每日查询灰度进度
    ↓ (complete)
[发布完成]
```

### 6.2 失败处理

| 步骤 | 失败原因 | 处理 |
|------|----------|------|
| 1. upload_build | altool 不存在 / 凭证错误 / IPA 无效 | 阻塞，人工介入 |
| 2. poll_build_status | processing 失败 / 超时 | 阻塞，检查 IPA 签名/Info.plist |
| 3. select_build | version 不存在 / build 已关联 | 阻塞，检查 version 状态 |
| 4. submit_review | metadata 缺失 / build 未选 | 阻塞，补全 metadata |
| 5. check_status | 审核拒绝 | 阻塞，人工阅读 rejection reason |
| 6. start_phased_release | version 未 approved | 阻塞，等待 check_status=approved |

**幂等性**：所有操作通过 `change_id` 去重，重复调用返回上次结果。

---

## 7. 凭证管理

### 7.1 必需凭证

```python
# App Store Connect API Key 方式（推荐）
credential = {
    "api_key_id": "DEVELOPER_API_KEY",      # App Store Connect → Users → Keys
    "api_issuer_id": "issuer_id",            # 同上页面顶部显示
    "private_key_p8": "-----BEGIN PRIVATE KEY-----\n...",  # .p8 文件内容
    "bundle_id": "com.company.game",         # App bundle identifier
    "app_id": "as_app_xxx",                  # App Store Connect app ID（可选，自动解析）
}
```

### 7.2 存储与加载

复用现有 [operation/providers/live/store_keys.py](file:///d:/project_slim/project_slim/operation/providers/live/store_keys.py)：

```python
# 环境变量
APPSTORE_API_KEY_ID=...
APPSTORE_API_ISSUER_ID=...
APPSTORE_PRIVATE_KEY_P8_PATH=/path/to/AuthKey_XXX.p8
APPSTORE_BUNDLE_ID=com.company.game

# 加载
from operation.providers.live import store_keys
cred = store_keys.get_appstore()
```

### 7.3 安全要求

- `.p8` 私钥文件权限 `600`，仅 owner 可读
- 私钥**不**写入版本控制（`.gitignore` 包含 `*.p8`）
- JWT 签名复用 `make_appstore_jwt`，缓存 10 分钟
- `app_specific_password`（如用 Apple ID 方式）走 keyring，不落盘明文

---

## 8. 测试策略

### 8.1 单元测试

新增 `tests/integration/test_appstore_upload.py`：

| # | 场景 | 期望 |
|---|------|------|
| 1 | upload_build altool 成功 | success=True, build_id 非空 |
| 2 | upload_build altool 不存在 | success=False, error 含 "xcrun not found" |
| 3 | upload_build 凭证缺失 | success=False, error 含 "missing api_key_id" |
| 4 | upload_build altool 超时 | success=False, error 含 "timed out" |
| 5 | poll_build_status VALID | success=True, processing_state="VALID" |
| 6 | poll_build_status FAILED | success=False, processing_state="FAILED" |
| 7 | poll_build_status 超时 | success=False, error 含 "poll timed out" |
| 8 | select_build 成功 | success=True |
| 9 | submit_review 成功 | success=True, status="waiting_for_review" |
| 10 | start_phased_release 成功 | success=True |
| 11 | pause/resume/complete phased release | success=True |
| 12 | check_phased_release 状态查询 | success=True, state 字段返回 |

### 8.2 Mock 策略

- `altool` CLI：mock `subprocess.run`，返回预设 JSON
- API 调用：复用 `arm_real_client` hook，注入 mock HTTP 响应
- 轮询：mock 时间，加速 polling 循环

### 8.3 回归门控

- 现有 `tests/test_publishing*.py` 全绿（不破坏 mock 行为）
- `MockAppStoreClient` 行为不变
- `AppStoreProvider` 在 SIMULATION 模式下走 mock，PRODUCTION 模式下走 real

---

## 9. 实施排期（Week 3）

| Day | 产出 | 验收 |
|-----|------|------|
| D15 | 本 Spec 文档（本文档） | 评审通过 |
| D16 | `models.py` 新增操作常量 + `BuildStatus` | 单元测试通过 |
| D17 | `real_client.py` 改造 `upload_build`（altool） | 单元测试场景 1-4 通过 |
| D18 | `real_client.py` 新增 `poll_build_status` + `select_build` | 单元测试场景 5-8 通过 |
| D19 | `real_client.py` 修正 `submit_review` + 新增 phased release | 单元测试场景 9-12 通过 |
| D20 | `provider.py` 改造 `apply_change` 新增分支 | 集成测试通过 |
| D21 | `test_appstore_upload.py` 完整 12 场景 + 回归 | 12/12 PASS + 现有 publishing 全绿 |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| altool 依赖 macOS，CI 在 Linux | P1 实现方式 B（API 分片上传），跨平台 |
| Apple 审核拒绝无法自动处理 | 阻塞 + 人工通知（复用 P0 ApprovalGate audit log 机制） |
| Build processing 时间不确定（最长 1 小时） | `poll_build_status` 可配置超时（默认 30 分钟），超时阻塞 |
| Phased release 中途暂停后忘记恢复 | 监控告警：phased release 状态 PAUSED 超过 24 小时触发通知 |
| 凭证泄露 | .p8 不入版本控制，权限 600，JWT 短时效（10 分钟） |
| API rate limit | 复用 `http_util` 的重试机制，429 指数退避 |

---

## 11. 不做的事（Out of Scope）

明确排除，避免范围蔓延：

- ❌ TestFlight beta 测试（P1，下季度）
- ❌ App Store Connect 用户/角色管理
- ❌ 审核拒绝自动修复
- ❌ IAP 配置（走 `monetization/iap/client.py`）
- ❌ App Store Connect API 方式 B 分片上传（P1）
- ❌ 桌面版 Transporter app 集成
- ❌ Android AAB 上传（Google Play 走另一条路径）

---

## 12. 验收标准（Week 3 出口）

1. ✅ 本 Spec 评审通过（本文档）
2. ✅ `models.py` 新增 9 个操作常量 + `BuildStatus` 数据类
3. ✅ `real_client.py` 改造 `upload_build`（altool CLI）+ 新增 `poll_build_status` / `select_build` / 5 个 phased release 方法
4. ✅ `provider.py` `apply_change` 支持 9 个新操作分支
5. ✅ `test_appstore_upload.py` 12/12 PASS
6. ✅ 现有 `tests/test_publishing*.py` 全绿（V1/mock 兼容）
7. ✅ 全量回归 ≥ 120+/120 PASS

---

## 变更记录

| 日期 | 版本 | 作者 | 变更 |
|------|------|------|------|
| 2026-08-06 | v0.1 | TRAE Agent | 初始草案，基于 [审计报告](file:///d:/project_slim/project_slim/AI_Game_Studio_OS_审计报告.md) P0-2 与现有 `AppStoreRealClient` 现状起草 |
