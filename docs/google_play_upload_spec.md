# P0 — Google Play 上架能力规范 (google_play_upload_spec)

**版本**: v0.1
**日期**: 2026-08-10
**作者**: TRAE Agent
**关联**: [ios_upload_spec.md](file:///d:/project_slim/project_slim/docs/ios_upload_spec.md)（对称参考）、
[production_roadmap.md](file:///d:/project_slim/project_slim/docs/production_roadmap.md) P0-3、
[p0_approval_gate_v2_spec.md](file:///d:/project_slim/project_slim/docs/p0_approval_gate_v2_spec.md)

---

## 1. 背景

iOS App Store 上架能力（P0-2）已完整实现 7 步编排器 + 5 API endpoints + 86 tests。
为达成海外市场对称覆盖，需实现 **Google Play 端到端发布能力（P0-3）**，
使 Android 应用上架流程与 iOS 对称：自动上传 AAB → 创建 release → 提交审核 →
轮询审核状态 → 启动 staged rollout → 监控 rollout 进度。

当前代码现状：

| 文件 | 现状 | 缺口 |
|------|------|------|
| [operation/publishing/google_play/client.py](file:///d:/project_slim/project_slim/operation/publishing/google_play/client.py) | `MockGooglePlayClient` 完整 mock | 无缺口（mock 用） |
| [operation/publishing/providers/google_play/real_client.py](file:///d:/project_slim/project_slim/operation/publishing/providers/google_play/real_client.py) | `GooglePlayRealClient` 完整实现，含 `set_rollout` / `halt_rollout` / `get_track_status` / Vitals / Reviews / Experiments | 无缺口（生产就绪，待凭证） |
| [operation/providers/live/store_keys.py](file:///d:/project_slim/project_slim/operation/providers/live/store_keys.py) | `get_googleplay()` 已实现 | 无缺口 |
| [operation/publishing/app_store/orchestrator.py](file:///d:/project_slim/project_slim/operation/publishing/app_store/orchestrator.py) | iOS 7 步编排器 | 无缺口（参考实现） |
| **orchestrator（Google Play）** | ❌ **缺失** | **本 spec 实现** |

**核心问题**：Google Play 缺少与 iOS 对称的端到端编排器，无法将现有
`GooglePlayRealClient` 串成可断点续跑、可重试、可监控的 7 步发布流程。

---

## 2. 目标

**实现 Google Play 自动上架 4 大能力（对称于 iOS）**：

1. **Bundle Upload** — 自动上传 AAB 到 Play Console Edits API
2. **Submit Review** — 创建 release + 提交审核 + 轮询审核状态
3. **Staged Rollout** — 审核通过后启动分阶段灰度发布
4. **Rollout Control** — 查询进度 / 暂停回滚 / 推进百分比

**非目标**（明确排除）：
- ❌ Internal testing / Closed testing 邀请（已有 `invite_testers_to_closed_track`，本 spec 不涉及）
- ❌ Store-listing experiments（已有 `create_listing_experiment`，本 spec 不涉及）
- ❌ Vitals 监控（已有 `get_vitals`，本 spec 不涉及；rollout 监控仅用 `get_track_status`）
- ❌ 审核拒绝后的自动修复（人工介入）
- ❌ In-App Purchase 配置（走 `monetization/iap/client.py`）

---

## 3. Google Play Developer API 真实流程

### 3.1 Bundle Upload 完整流程

Google Play 的 build 上传通过 **Edits API** 完成（非独立 upload 端点）：

1. **打开 edit**：
   ```
   POST /androidpublisher/v3/applications/{packageName}/edits
   ```
   返回 `editId`，后续所有操作都基于此 `editId`。

2. **上传 AAB**：
   ```
   POST /androidpublisher/v3/applications/{packageName}/edits/{editId}/bundles?ackBundleInstallationWarning=true
   Content-Type: application/octet-stream
   Body: <AAB binary>
   ```
   返回 `versionCode`。

3. **commit edit**（提交审核时执行，见 §3.3）。

**本 spec 选择**：使用 `GooglePlayRealClient.upload_bundle()` 封装上述流程，
内部走 Edits API。无需 CLI 工具（与 iOS 的 altool 不同），跨平台支持。

### 3.2 Create Release 流程

1. **（在已打开的 edit 内）配置 track release**：
   ```
   PUT /androidpublisher/v3/applications/{packageName}/edits/{editId}/tracks/{track}
   {
     "releases": [{
       "name": "Release {version}",
       "versionCodes": ["{version_code}"],
       "status": "completed"  // internal track 直接完成
     }]
   }
   ```
   `track` ∈ `internal` / `closed` / `production`。

2. **创建 release**（`create_release` 步骤）：
   `GooglePlayRealClient.create_release()` 封装上述操作。

### 3.3 Submit Review 流程

1. **commit edit**（提交审核）：
   ```
   POST /androidpublisher/v3/applications/{packageName}/edits/{editId}:commit
   { "changesNotSentForReview": false }
   ```
   `changesNotSentForReview=false` 表示立即送审。

2. **轮询审核状态**：
   ```
   POST /androidpublisher/v3/applications/{packageName}/edits  // 打开临时 edit
   GET  /androidpublisher/v3/applications/{packageName}/edits/{editId}/tracks/production
   DELETE /androidpublisher/v3/applications/{packageName}/edits/{editId}  // 清理临时 edit
   ```
   状态映射：
   - `completed` → `published`（已发布到 production）
   - `inProgress` → `in_review`（审核中或 rollout 中）
   - `draft` → `draft`
   - `halted` → `rejected`（被拒或暂停）

**注意**：Google Play 的审核状态不像 Apple 那样有明确的 `approved`/`rejected`
中间态，而是通过 track release 的 `status` 间接推断。本编排器在 `check_status`
步骤中轮询直到状态稳定在终态（approved/rejected），与 iOS 对称。

### 3.4 Staged Rollout 流程

1. **启动 staged rollout**（审核通过后）：
   ```
   PUT /androidpublisher/v3/applications/{packageName}/edits/{editId}/tracks/production
   {
     "releases": [{
       "versionCodes": ["{version_code}"],
       "status": "inProgress",
       "userFraction": 0.05
     }]
   }
   POST   /androidpublisher/v3/applications/{packageName}/edits/{editId}:commit
   ```
   `userFraction` 阶梯：`0.05` → `0.10` → `0.20` → `0.50` → `1.00`。

2. **查询 rollout 进度**：
   ```
   GET /androidpublisher/v3/applications/{packageName}/edits/{editId}/tracks/production
   ```
   返回当前 `status` + `userFraction`。

3. **暂停 rollout（halt）**：
   ```
   PUT .../tracks/production
   { "releases": [{"status": "halted"}] }
   ```

4. **推进到下一阶段（advance）**：
   ```
   PUT .../tracks/production
   { "releases": [{"status": "inProgress", "userFraction": 0.10}] }
   ```

**本 spec 选择**：使用 `GooglePlayRealClient` 的 `set_rollout` / `halt_rollout` /
`get_track_status` 方法封装上述操作，编排器调用这些方法而非直接发 HTTP。

---

## 4. 数据模型

### 4.1 操作常量（复用已有）

复用 [operation/publishing/providers/models.py](file:///d:/project_slim/project_slim/operation/publishing/providers/models.py)
的 `GP_DRAFT` / `GP_IN_REVIEW` / `GP_REJECTED` / `GP_APPROVED` / `GP_PUBLISHED`
和 `OP_UPLOAD_BUILD` / `OP_CREATE_RELEASE` / `OP_SUBMIT_REVIEW` /
`OP_CHECK_STATUS` / `OP_RELEASE` / `OP_ROLLBACK`。

### 4.2 ReleaseState（新增，对称于 iOS ReleaseState）

```python
@dataclass
class ReleaseState:
    release_id: str           # 内部 release ID (gprel_*)
    game_id: str
    package_name: str         # com.company.game
    version: str              # 1.2.0
    build_number: int         # version code
    aab_path: str
    track: str = "internal"
    rollout_fraction: float = 0.05
    current_step: str = "upload_bundle"
    completed_steps: list[str] = []
    step_results: dict[str, StepResult] = {}
    version_code: str = ""              # upload_bundle 后填充
    release_id_play: str = ""           # create_release 后填充 (Play 内部 id)
    review_status: str = ""             # approved/rejected
    rejection: dict | None = None
    rollout_status: str = ""            # completed/inProgress/halted
    status: str = "pending"             # 整体状态
```

### 4.3 StepResult（对称于 iOS）

```python
@dataclass
class StepResult:
    step: str
    success: bool
    started_at: str = ""
    finished_at: str = ""
    data: dict = {}
    error: str = ""
```

---

## 5. 编排器设计

### 5.1 7 步流程（对称于 iOS）

```
1. upload_bundle    — 上传 AAB (Edits API upload_bundle)
2. create_release   — 在 track 创建 release (create_release)
3. submit_review    — commit edit → 提交审核 (submit_review)
4. [审核等待 — 外部, 数小时到数天]
5. check_status     — 轮询审核状态直到 approved/rejected (check_status)
6. start_rollout    — 审核通过后启动 staged rollout (set_rollout 5%)
7. check_rollout    — 查询 rollout 进度 (get_track_status)
```

### 5.2 设计原则（对称于 iOS）

- **每步独立可重试**：失败后可从失败步重试，无需从头开始
- **幂等**：同一 `release_id` 重复调用返回上次结果
- **状态持久化**：`data/google_play_release/{release_id}.json` 记录执行进度
- **错误隔离**：单步失败不阻塞已成功步骤
- **SIMULATION 模式**：无凭证时自动用 `MockGooglePlayClient`
- **PRODUCTION 模式**：有凭证时用 `GooglePlayRealClient`，走真实 Play Developer API

### 5.3 默认流程

- `run()` 默认执行到 `submit_review`（等待人工审核）
- `run_full_release()` 执行完整流程到 `check_rollout`（审核通过后灰度发布）
- `run(start_step="start_rollout")` 从指定步骤恢复（审核通过后启动灰度）

### 5.4 Rollout 控制

- `halt_rollout()`：暂停 staged rollout（用户主动暂停/回滚）
- `advance_rollout(next_fraction)`：推进到下一百分比

---

## 6. API 端点（7 个，对称于 iOS 的 5 个 + 2 个 rollout 控制）

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/googleplay/credentials/status` | GET | 凭证配置状态（不暴露凭证值） |
| `/api/googleplay/release/start` | POST | 启动 7 步发布（params: game_id, package_name, aab_path, version, build_number, track?, rollout_fraction?, stop_step?） |
| `/api/googleplay/release/{release_id}/status` | GET | 查询发布进度 |
| `/api/googleplay/release/{release_id}/resume` | POST | 断点续跑（params: start_step?, stop_step?） |
| `/api/googleplay/releases` | GET | 列出所有发布流程 |
| `/api/googleplay/release/{release_id}/halt` | POST | 暂停/回滚 staged rollout |
| `/api/googleplay/release/{release_id}/advance` | POST | 推进 staged rollout 到下一百分比（params: next_fraction） |

---

## 7. 凭证要求

### 7.1 SIMULATION 模式（默认）

无需凭证，自动使用 `MockGooglePlayClient`。用于 CI / dry-run / 测试。

### 7.2 PRODUCTION 模式

需要在 `credentials/store_keys.json` 配置 Google Play 服务账号：

```json
{
  "google_play": {
    "service_account_json_path": "/path/to/service-account.json",
    "package_name": "com.company.game"
  }
}
```

或直接内嵌（不推荐，建议用 path）：

```json
{
  "google_play": {
    "service_account_json": { ... },
    "package_name": "com.company.game"
  }
}
```

服务账号需要的最小权限：
- `Android Publisher` 角色（Edits API 读写）
- `Play Developer Reporting API Viewer`（Vitals 读取，本 spec 不强依赖）

---

## 8. 测试覆盖

测试文件：[test_google_play_release_orchestrator.py](file:///d:/project_slim/project_slim/tests/test_google_play_release_orchestrator.py)

8 大测试类共 31 个测试：

1. **TestFullFlow**（5）：全链路 7 步、步骤顺序、字段传播
2. **TestResume**（2）：断点续跑、状态持久化
3. **TestFailureRetry**（3）：单步失败阻塞、重试成功、create_release 失败
4. **TestStateManagement**（5）：get_status、load 不存在、状态文件创建、未知步骤错误
5. **TestModeSwitch**（2）：SIMULATION/PRODUCTION 模式自动切换
6. **TestRejectionScenario**（2）：审核被拒终态、被拒后 rollout 阻塞
7. **TestRolloutControl**（4）：halt、advance（mock 不支持）、advance（RealClient）、完整 staged rollout
8. **TestGooglePlayReleaseAPI**（8）：7 个 API 端点 + 不存在 release 错误处理

---

## 9. 与 iOS 对称性对照

| 维度 | iOS (P0-2) | Google Play (P0-3) |
|------|-----------|-------------------|
| 编排器 | `IOSReleaseOrchestrator` | `GooglePlayReleaseOrchestrator` |
| 步骤数 | 7 步 | 7 步 |
| 状态持久化 | `data/ios_release/{release_id}.json` | `data/google_play_release/{release_id}.json` |
| Mock 客户端 | `MockAppStoreClient` | `MockGooglePlayClient` |
| Real 客户端 | `AppStoreRealClient` (altool + REST) | `GooglePlayRealClient` (Edits API) |
| 凭证 | App Store Connect API key (ES256 JWT) | Google Play 服务账号 (OAuth2) |
| 审核轮询 | `poll_build_status` (PROCESSING→VALID) | `check_status` (in_review→approved/rejected) |
| 灰度发布 | Phased Release (7 天固定阶梯) | Staged Rollout (5%→10%→20%→50%→100%) |
| Rollout 控制 | 无（Apple 固定阶梯） | `halt_rollout` / `advance_rollout`（可手动控制） |
| API 端点数 | 5 | 7（多 2 个 rollout 控制） |
| 测试数 | 20 | 31 |

---

## 10. 验收标准

- [x] `GooglePlayReleaseOrchestrator` 实现 7 步流程
- [x] 状态持久化到 JSON，支持断点续跑
- [x] SIMULATION/PRODUCTION 模式自动切换
- [x] 7 个 API 端点暴露到 workspace FastAPI app
- [x] 31 个单元测试全部 PASS
- [x] 审核被拒场景作为终态处理（非编排器失败）
- [x] Rollout 控制（halt/advance）实现
- [ ] **PRODUCTION 模式真实上传**（阻塞于 Google Play 服务账号凭证，属 P0 外部证据 E2）

---

## 11. 后续 P1 扩展（非本 spec 范围）

- **Vitals 集成**：rollout 期间自动监控 crash/ANR rate，超阈值自动 halt
- **Store-listing experiments**：ASO A/B 测试与发布流程联动
- **Closed testing 邀请**：发布前自动邀请测试人员
- **多 track 推送**：internal → closed → production 的多 track 编排
- **Release notes 自动生成**：从 commit log / changelog 生成多语言 release notes
