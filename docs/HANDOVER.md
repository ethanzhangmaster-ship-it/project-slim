# 项目交接文档 — AI Game Studio OS

> **致接手 Agent**：本文档是项目的唯一权威交接文档。读完即可上手。根目录的 `AI_AGENT_HANDOFF.md` / `ZCODE_HANDOFF.md` 为早期阶段遗留，已废弃，请以本文档为准。

---

## 1. 项目定位

**AI Game Studio OS** — 模拟一家海外手游公司的完整组织架构，目标是"5 人真人团队 + 50 个 AI 员工，运营 10-50 款海外手游"。

核心思想：不是做一堆 Agent 工具箱，而是让每个 AI 部门对一个商业结果负责。用户打开 Workspace 工作台，就像进入一家 AI 游戏公司办公室。

**当前阶段**：已完成从决策（GrowthLoop）→ 执行（ApprovalGate）→ 监控（SystemMonitor）的完整闭环，并接入 LiveOps 回流活动、跨 Agent 协同、真实 Meta Ads 数据。

---

## 2. 技术栈

| 层 | 技术 | 位置 |
|---|---|---|
| 后端 | Python 3.10 + FastAPI | `src/market_ops/workspace/app.py` |
| 前端 | Next.js 16 + React 19 + TailwindCSS 4 | `workspace/` |
| 数据持久化 | JSONL 文件（append-only，无数据库） | `data/` |
| 测试 | pytest + TestClient | `tests/` |
| 外部 API | Meta Ads (Facebook Marketing)、Adjust | `src/market_ops/clients/` |

**注意**：运行环境是 Python 3.10，部分历史模块（如 `product/control_plane.py`）使用了 `from datetime import UTC`（3.11+ 语法），会导致 collection error，这是预先存在的兼容问题，非新引入。

---

## 3. 目录结构（核心）

```
project_slim/
├── src/market_ops/workspace/        # ★ Workspace 后端（主要工作区）
│   ├── app.py                       # FastAPI 入口，47 个端点
│   ├── system_monitor.py            # 统一监控模块
│   ├── liveops_agent.py             # LiveOps Agent（流失分析→回流活动）
│   ├── liveops_executor.py          # 活动执行层（ApprovalGate + Adapter）
│   ├── churn_alert_bridge.py        # LiveOps↔Growth 桥接层
│   ├── real_provider.py             # 真实数据 Provider（含组织架构）
│   ├── mock_provider.py             # Mock 数据 Provider（测试用）
│   ├── aggregator.py                # 组织架构聚合
│   └── agent_registry_store.py      # AgentRegistry 持久化
│
├── workspace/                       # ★ 前端（Next.js）
│   ├── src/app/page.tsx             # Dashboard 主页（白色主题）
│   ├── src/app/games/page.tsx       # 游戏管理页
│   ├── src/app/tasks/page.tsx       # 任务页
│   └── src/lib/api.ts               # API 类型定义 + 调用方法
│
├── src/market_ops/creative_vision_runtime/growth_runtime/agent/communication/
│   ├── agent_message.py             # Agent 角色与身份定义
│   ├── agent_registry.py            # 默认组织注册
│   └── message_bus.py               # 跨 Agent 消息总线
│
├── tests/                           # 测试
├── docs/                            # 规格/契约文档
└── data/                            # JSONL 运行时数据（gitignore）
```

---

## 4. 已完成能力清单

### 4.1 决策层
- **GrowthLoop**：信号采集 → 决策引擎 → 动作生成 → 执行 → 结果回流
- **真实 Meta Ads 数据接入**：`meta_ads_fetcher.py`，可生成真实 pause/suppress 动作
- **CEO 每日例会**：多阶段（Growth → LiveOps → 报告），结果写入 execution_memory

### 4.2 执行层
- **ApprovalGate V2**：Level 0/1/2 分级审批（<$50 自动 / dry_run / ≥$500 人工）
- **BudgetWindowTracker**：日累计窗口预算控制，防小额高频绕过
- **WinbackCampaignExecutor**：LiveOps 活动执行（奖励下发、推送、邮件、应用内消息）
- **WinbackCampaignAdapter**：execute/verify/rollback 接口

### 4.3 LiveOps 闭环
- **流失分析**：分群分布、生命周期阶段、高价值流失用户识别
- **回流活动设计**：login_bonus / special_offer / push_re-engagement
- **活动执行**：dry_run 模拟 + 三级审批 + 审计日志

### 4.4 跨 Agent 协同
- **CEO → LiveOps**：单向触发（STAGE_LIVEOPS 阶段）
- **LiveOps → All**：MessageBus 广播（churn_alert / campaign_executed）
- **LiveOps ↔ Growth**：ChurnAlertBridge 订阅 churn_alert 自动生成 Growth 响应动作（pause/reallocate/reduce/monitor），支持自动执行、审计、回滚

### 4.5 监控与运维
- **SystemMonitor**：聚合 GrowthLoop / LiveOps / ChurnAlert / 审批队列统计
- **健康状态**：healthy / degraded / critical
- **告警检测**：成功率、审批积压、JSONL 文件大小、文件过期
- **API**：`/healthz`、`/readyz`、`/api/monitor/*` 系列
- **前端仪表盘**：健康总览、子系统统计、告警列表、JSONL 文件监控

### 4.6 Workspace 工作台
- 白色主题（`#fafafa` 页面 / `#ffffff` 卡片 / `text-gray-900` 主文字）
- Dashboard：KPI、游戏列表、GrowthLoop 触发、CEO 例会、LiveOps、跨 Agent 协同、系统监控
- SSE 实时事件流（`/api/events/stream`）

---

## 5. API 端点清单（47 个）

完整路由见 `app.py`。按功能分组：

| 分组 | 端点 |
|---|---|
| 健康检查 | `GET /healthz` `GET /readyz` |
| Dashboard | `GET /api/dashboard` `/api/kpi` `/api/briefing` `/api/organization` `/api/agents` `/api/agents/{id}` `/api/tasks` `/api/tasks/{id}` `/api/events` `/api/decisions` `/api/games` `/api/games/{id}` `/api/memory` |
| 执行审批 | `POST /api/decisions/{id}/approve` `/api/decisions/{id}/reject` |
| GrowthLoop | `GET /api/loop/history` `/api/loop/cycle/{n}` `POST /api/loop/trigger` |
| CEO | `POST /api/ceo/daily-run` |
| SSE | `GET /api/events/stream` |
| LiveOps | `GET /api/liveops/churn-analysis/{game_id}` `POST /api/liveops/winback-campaign` `GET /api/liveops/campaigns` `/{id}` `POST /{id}/evaluate` `POST /{id}/execute` `GET /api/liveops/executions` `/{id}` `/pending-approvals` `POST /{id}/approve` `POST /{id}/reject` `GET /api/liveops/stats` `/cross-agent` |
| Growth 响应 | `GET /api/growth/churn-responses` `/stats` `/{id}` `POST /{id}/rollback` `/audit/logs` |
| 监控 | `GET /api/monitor/overview` `/health` `/alerts` `/files` `/growth-loop` `/liveops` `/approval-queue` |

---

## 6. 运行与测试

### 启动后端
```powershell
cd d:\project_slim\project_slim
# 设置环境变量（见 .env.example）
python -m uvicorn src.market_ops.workspace.app:app --reload --port 8000
```

### 启动前端
```powershell
cd d:\project_slim\project_slim\workspace
npm run dev   # http://localhost:3000
```

### 运行测试
```powershell
cd d:\project_slim\project_slim

# Workspace 核心测试（全绿，292+ 用例）
python -m pytest tests/test_system_monitor.py tests/test_liveops_executor.py tests/test_liveops_agent.py tests/test_churn_alert_bridge.py tests/test_workspace_execution.py tests/test_e141_communication_layer.py -q

# 整体回归（注意 collection error，见下）
python -m pytest tests/ -q
```

### 测试基线（交接时，已验证）
- ✅ Workspace 相关 6 个测试文件：**280 用例全 PASS**（3.14s）
  - test_system_monitor.py: 29
  - test_liveops_executor.py: 64
  - test_liveops_agent.py: 27
  - test_churn_alert_bridge.py: 47
  - test_workspace_execution.py: 20
  - test_e141_communication_layer.py: 93
- ⚠️ 14 个测试文件 collection error（预先存在，非本次引入）：`control_plane.py` 用了 `from datetime import UTC`（Python 3.11+ 语法），与 3.10 环境不兼容。修复方式：改为 `from datetime import timezone; timezone.utc`。

---

## 7. 开发规范与红线（务必遵守）

以下规则来自项目负责人的硬性要求，违反会导致返工：

1. **Spec-first 流程**：修改 Spec → 更新代码 → 测试 → 版本递增。禁止先改代码后补 spec。
2. **禁止新增算法层**：系统已收敛，禁止添加 v7/v8/v9 新版本或修改已收敛的数学定义。
3. **工作范围**：仅限参数调优、工程实现（DB/Pipeline/Facebook API）、监控、运维。
4. **不硬编码 Prompt**：所有 Prompt 必须经过模板渲染、优化、验证。禁止字符串拼接 Blueprint 数据。
5. **Blueprint 唯一输入**：所有 Prompt 以 Blueprint 为唯一输入源，输出标准化（JSON/Markdown/TXT）+ 验证报告。
6. **接口稳定性**：冻结公共 API 签名和插件 ABI 契约。
7. **ApprovalGate 流程**：所有自动化动作必须经过分级审批，支持回滚。
8. **发布门禁**：版本发布前需全测试通过（如 120+/120 PASS）。
9. **优先级**：核心模块稳定性 > 新功能扩展。Action Engine / Media Buying Agent 优先。
10. **界面主题**：白色主题，不要改回暗色。

---

## 8. 数据流（端到端闭环）

```
CEO 每日例会
    ↓ STAGE_GROWTH
GrowthLoop（Meta Ads 真实数据 → 信号 → 决策 → 动作）
    ↓ 动作执行（ApprovalGate 分级审批）
    ↓ 结果回流 execution_memory
    ↓ STAGE_LIVEOPS
LiveOps Agent（流失分析 → 回流活动设计）
    ↓ churn_alert 广播（MessageBus）
    ↓
ChurnAlertBridge（订阅 → Growth 响应动作：pause/reallocate/reduce/monitor）
    ↓ 自动执行 + 审计日志
    ↓
WinbackCampaignExecutor（ApprovalGate + Adapter → 奖励下发/推送）
    ↓
SystemMonitor（聚合所有子系统指标 → 告警 → Dashboard）
```

---

## 9. 已知问题与技术债

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | `control_plane.py` 等用 `from datetime import UTC`（3.11+） | 14 个测试 collection error | 改为 `timezone.utc` |
| 2 | `test_e1713_cli_contract.py` 模块名与 Python 标准 `operator` 冲突 | 该测试文件失败 | 重命名或调整 import |
| 3 | JSONL 文件 append-only 无轮转 | 文件无限膨胀（SystemMonitor 已告警） | 实现数据归档/轮转 |
| 4 | 告警仅返回列表，无通知触达 | 运维需手动查看 | 接入邮件/Slack 通知 |
| 5 | Meta Ads 执行默认 dry_run | 真实下发需手动切模式 | 配置 META_ACCESS_TOKEN 后切 live |

---

## 10. 下一步方向（建议优先级）

1. **端到端无人值守闭环验证**：用真实场景跑一遍完整链路，输出验收报告，验证全链路可用性。
2. **监控告警通知落地**：让 SystemMonitor 告警真正触达（邮件/Slack/企业微信），完成运维闭环。
3. **数据归档与轮转**：实现 JSONL 历史数据归档和文件轮转机制。
4. **iOS 上架问题**：原审计报告 P0 缺口之一（见 `docs/ios_upload_spec.md`）。
5. **真实 Meta Ads 执行切换**：从 dry_run 切换到真实预算调整和素材下发。

---

## 11. 关键文档索引

| 文档 | 说明 |
|---|---|
| `docs/p0_approval_gate_v2_spec.md` | ApprovalGate V2 规格 |
| `docs/liveops_agent_spec.md` | LiveOps Agent 规格 |
| `docs/ceo_unified_dispatch_spec.md` | CEO 统一调度规格 |
| `docs/ios_upload_spec.md` | iOS 上架规格 |
| `docs/production_roadmap.md` | 生产路线图 |
| `docs/production_runbook.md` | 生产运维手册 |
| `docs/architecture.md` | 架构说明 |
| `docs/testing.md` | 测试指南 |
| `AI_Game_Studio_OS_审计报告.md` | 项目审计报告（含 P0 缺口） |
| `project_slim/src/market_ops/workspace/app.py` | 后端入口（所有 API） |
| `project_slim/workspace/src/app/page.tsx` | 前端 Dashboard |

---

## 12. 交接清单

接手后请按此顺序确认：

- [ ] 运行 `pytest tests/test_system_monitor.py tests/test_liveops_executor.py tests/test_liveops_agent.py tests/test_churn_alert_bridge.py tests/test_workspace_execution.py tests/test_e141_communication_layer.py -q` 确认 280 用例全绿
- [ ] 启动后端 + 前端，访问 http://localhost:3000 确认 Dashboard 白色主题正常
- [ ] 访问 http://localhost:8000/healthz 确认返回 healthy
- [ ] 访问 http://localhost:8000/api/monitor/overview 确认监控指标正常
- [ ] 阅读本文档第 7 节"开发规范与红线"
- [ ] 阅读 `AI_Game_Studio_OS_审计报告.md` 了解 P0 缺口
- [ ] 确认 `project_memory.md` 中的项目规则已加载（接手 Agent 会自动继承）

---

*交接日期：2026-08-07*
*测试基线：280 PASS（Workspace 核心，3.14s）*
