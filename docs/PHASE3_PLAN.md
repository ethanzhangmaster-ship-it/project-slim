# Phase 3 整体规划 — 数据驱动闭环与协同深化

> **规划日期**: 2026-08-07
> **最后更新**: 2026-08-07 (进度回顾)
> **前置状态**: Phase 2 已交付 (470 测试通过, 10 Agent, ~106 API 端点)
> **规划原则**: 规范优先 (Spec → Code → Test → Version), 系统收敛, 不新增算法层

---

## 0. 进度回顾 (2026-08-07)

### 已完成任务

| 任务 | 状态 | 产出 |
|------|------|------|
| M4.1 Python 3.10 兼容性 | ✅ 已验证无问题 | 22334 tests collected, 0 errors (此前已修复) |
| M4.2 JSONL 数据轮转 | ✅ 已完成 | JsonlRotator (10MB/50000行触发, gzip 归档, 5 份保留) + 3 管理 API + 24 单元测试 |
| M4.4a SSE 实时事件流 | ✅ 已完成 | 多事件源聚合 + 心跳 + 事件 ID + 声音通知 |
| M4.4b 跨 Agent 拓扑可视化 | ✅ 已完成 | 10 节点 15 边交互式 SVG, 部门分组, 悬停高亮 |
| M4.4c 声音通知 | ✅ 已完成 | Web Audio API, 5 种事件类型音色, 未读计数 |
| M4.4d 桌面通知 | ✅ 已完成 | Notification API, 权限管理, 即使最小化也能弹出, 点击跳转 |
| M4.4e 事件详情面板 | ✅ 已完成 | EventDetailPanel + AgentDetailPanel, ESC 关闭, JSON 格式化, 嵌套面板 |
| Spec 文档 | ✅ 已完成 | AI_VIRTUAL_GAME_STUDIO_OS_SPEC.md (14 部门全景) |

### 当前测试基线
- 全量回归: 22358 tests, 0 failures, 0 errors, 0 skipped (165.6s)
- JSONL 轮转单元测试: 24/24 PASS
- 跨 Agent API 测试: 8/8 PASS
- 前端构建: 10 页面全部通过, TypeScript 零错误

---

## 1. Phase 3 定位

**核心目标**: 从"能力建设"转向"数据驱动闭环验证", 将模拟数据逐步替换为真实数据源, 验证 10 Agent 协同架构在真实业务场景下的有效性.

**与 Phase 1-2 的区别**:
- Phase 1-2: Agent 能力扩展 + 协同链路搭建 (模拟数据验证)
- Phase 3: 真实数据接入 + 闭环效果验证 + 协同深化

**红线约束** (继承自 project_memory):
- 不新增算法层、版本 (v7/v8/v9) 或数学定义
- 不修改已收敛的公共 API 签名和插件 ABI
- 工作范围限于: 数据接入、参数调优、工程实现、监控、运维

---

## 2. 里程碑规划

Phase 3 分为 4 个里程碑, 每个里程碑有明确的验收标准:

### M1: 真实数据源接入 (数据层)

**目标**: 打通 3 个真实数据源, 替代模拟数据

| 任务 | 数据源 | 替代对象 | 验收标准 |
|------|--------|----------|----------|
| M1.1 | Meta Ads API (live 模式) | dry_run 模拟执行 | 真实 campaign 创建/暂停/预算调整, dry_run=false |
| M1.2 | ThinkingData 玩家行为数据 | mock behavior_data | DataAnalyst 从真实 DAU/留存/付费数据生成分析报告 |
| M1.3 | 工单系统对接 | mock ticket data | PlayerSupport 从真实工单系统拉取并处理 |

**前置条件**:
- META_ACCESS_TOKEN 和 META_AD_ACCOUNT_ID 已配置
- ThinkingData SDK 已集成
- 工单系统 API 凭证已获取

**风险**:
- Meta Ads API 限流 → 需实现请求队列和指数退避
- ThinkingData 数据延迟 → 需设置合理的数据新鲜度阈值
- 工单系统 API 不稳定 → 需实现降级策略

### M2: 闭环效果验证 (验证层)

**目标**: 基于 M1 真实数据, 验证 3 条核心闭环的实际效果

| 闭环 | 验证内容 | 验收标准 |
|------|----------|----------|
| M2.1 | GrowthLoop 闭环 | 真实 Meta Ads 数据 → 信号 → 决策 → 动作执行 → 效果回测 (ROAS 提升) |
| M2.2 | Data→Numerical 协同闭环 | 真实玩家行为 → LTV/CAC 建模 → 调优建议 → A/B 测试 → 效果验证 |
| M2.3 | LiveOps 回流闭环 | 真实流失数据 → 回流活动设计 → 奖励发放 → 召回率验证 |

**验收标准**:
- 每个闭环至少完成 1 次真实数据驱动的完整 cycle
- 闭环各步骤均有审计日志和效果指标
- CEO Memory 记录真实执行结果 (非模拟)

### M3: 协同深化 (协同层)

**目标**: 从单向协同升级为双向协同 + 冲突检测

| 任务 | 内容 | 验收标准 |
|------|------|----------|
| M3.1 | 双向协同 | Numerical Designer 反向通知 Data Analyst (调优后建议重新分析) |
| M3.2 | 冲突检测 | 多 Agent 同时修改同一游戏数值时检测冲突并告警 |
| M3.3 | 协同编排 | 支持自定义协同流程 (DAG 定义, 条件分支, 并行触发) |

**设计约束**:
- 双向协同不破坏现有单向链路 (向后兼容)
- 冲突检测基于 version 字段, 不引入分布式锁
- 协同编排放弃固定 4 步, 改为可配置 DAG

### M4: 运维与监控强化 (运维层)

**目标**: 解决已知技术债务, 强化生产运维能力

| 任务 | 内容 | 验收标准 | 状态 |
|------|------|----------|------|
| M4.1 | Python 3.10 兼容性 | 修复 14 个 collection error | ✅ 已验证无问题 |
| M4.2 | JSONL 数据轮转 | 实现 append-only 文件轮转机制 (按大小/时间) | ✅ 已完成 |
| M4.3 | 告警通知触达 | 接入邮件/企业微信/Slack 通知渠道 | ⏳ 待执行 |
| M4.4a | SSE 实时事件流 | 多事件源 + 心跳 + 事件 ID | ✅ 已完成 |
| M4.4b | 跨 Agent 拓扑可视化 | 交互式 SVG, 部门分组 | ✅ 已完成 |
| M4.4c | 声音通知 | Web Audio API, 5 种音色 | ✅ 已完成 |
| M4.4d | 桌面通知 | Notification API, 即使最小化也能弹出 | ✅ 已完成 |
| M4.4e | 事件详情面板 | 点击事件/节点弹出完整协同记录 | ✅ 已完成 |
| M4.5 | 文档更新 | 更新 architecture.md, 产出 Phase 3 交付报告 | ⏳ 待执行 |

---

## 3. 任务分解与优先级

### 优先级矩阵 (更新于 2026-08-07)

```
已完成 (✅):
  M4.1 Python 3.10 兼容性
  M4.2 JSONL 数据轮转
  M4.4a SSE 实时事件流
  M4.4b 跨 Agent 拓扑可视化
  M4.4c 声音通知
  M4.4d 桌面通知
  M4.4e 事件详情面板

高优先级 (P0) — 阻塞生产可用:
  M1.1 Meta Ads live 模式 (需凭证, 暂跳过)

中优先级 (P1) — 核心价值验证:
  M4.3 告警通知触达
  M1.2 ThinkingData 接入
  M2.1 GrowthLoop 闭环验证
  M2.2 Data→Numerical 闭环验证

低优先级 (P2) — 增强与优化:
  M1.3 工单系统对接
  M2.3 LiveOps 回流闭环验证
  M3.1 双向协同
  M3.2 冲突检测
  M4.5 文档更新

探索性 (P3) — 长期方向:
  M3.3 协同编排引擎
```

### 建议执行顺序 (更新于 2026-08-07)

```
已完成:
  ✅ M4.1 (兼容性验证)
  ✅ M4.2 (JSONL 轮转)
  ✅ M4.4a-c (SSE + 拓扑 + 声音)
  ✅ M4.4d (桌面通知)
  ✅ M4.4e (事件详情面板)

下一步 (按依赖关系排序):
  Step 4: M1.1 (Meta Ads live)        — [暂跳过, 需 META_ACCESS_TOKEN 凭证]
  Step 5: M4.3 (告警通知触达)         — 工程实现, 接入邮件/企微 ← 当前
  Step 6: M1.2 (ThinkingData 接入)    — 需 SDK 凭证
  Step 7: M2.1 (GrowthLoop 闭环验证)  — 依赖 M1.1
  Step 8: M2.2 (Data→Numerical 验证)  — 依赖 M1.2
  Step 9: M3.1 (双向协同)             — 协同深化
  Step 10: M3.2 (冲突检测)            — 协同深化
  Step 11: M1.3 (工单系统)            — 需工单系统 API 凭证
  Step 12: M2.3 (LiveOps 验证)        — 依赖 M1.2 + M1.3
  Step 13: M4.5 (文档更新)            — 收尾
```

---

## 4. 验收标准

### Phase 3 整体验收标准

1. **测试覆盖**: 全量测试 ≥ 500 项 (当前 470), 新增测试覆盖真实数据接入和闭环验证
2. **真实数据闭环**: 至少 2 条核心闭环 (GrowthLoop + Data→Numerical) 基于真实数据完成完整 cycle
3. **技术债务清零**: Python 3.10 兼容性、JSONL 轮转、告警通知 3 项技术债务全部解决
4. **文档更新**: architecture.md 更新, 产出 PHASE3_DELIVERY_REPORT.md
5. **回归无破坏**: 现有 470 项测试全部通过, 无回归

### 各里程碑验收门禁

| 里程碑 | 门禁条件 | 阻塞条件 |
|--------|----------|----------|
| M1 | 至少 1 个真实数据源接入并产出真实数据 | API 凭证未获取 |
| M2 | 至少 1 条闭环完成真实数据驱动的完整 cycle | M1 未完成 |
| M3 | 双向协同 + 冲突检测可用 | M2 未完成 |
| M4 | 3 项技术债务清零 + 前端增强完成 | 无 (可与 M1-M3 并行) |

---

## 5. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Meta Ads API 限流 | 中 | 高 | 实现请求队列 + 指数退避 + 缓存 |
| ThinkingData SDK 集成困难 | 中 | 中 | 预留 mock 降级, 不阻塞 M2.1 |
| 真实数据质量差 | 低 | 高 | 数据清洗 + 异常值过滤 + 人工抽检 |
| 闭环效果不达预期 | 中 | 中 | 设置效果阈值, 不达预期时分析根因 |
| 工时超预期 | 中 | 中 | 按 P0→P1→P2 优先级执行, 必要时裁剪 P2/P3 |

---

## 6. 不做事项 (Out of Scope)

以下内容**不属于 Phase 3 范围**, 明确排除:

1. **不新增 Agent**: 10 个 Agent 已覆盖核心业务, Phase 3 不新增
2. **不新增算法层**: 不引入新的 ML 模型或算法版本 (v7/v8/v9)
3. **不修改数学定义**: 已收敛的数值模型定义不变
4. **不重构核心架构**: FastAPI + Next.js + JSONL 架构不变
5. **不做分布式改造**: 单机部署, 不引入 Redis/Kafka 等中间件
6. **不做多租户**: 单租户模式, 不支持多公司隔离

---

## 7. 成功指标

Phase 3 完成后应达到以下指标:

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 测试用例数 | 470 | ≥ 500 |
| 真实数据源数 | 0 (全 mock) | ≥ 2 |
| 真实数据闭环数 | 0 | ≥ 2 |
| Python 3.10 兼容性 | 14 errors | 0 errors |
| JSONL 轮转 | 无 | 按大小/时间自动轮转 |
| 告警通知渠道 | 仅 Dashboard | + 邮件/企业微信 |
| API 端点数 | ~106 | ~110 (仅新增数据接入相关) |
| Agent 数 | 10 | 10 (不新增) |

---

## 8. 交付物清单

Phase 3 完成后应交付:

1. `docs/PHASE3_DELIVERY_REPORT.md` — Phase 3 最终交付报告
2. 更新 `docs/HANDOVER.md` — 反映 Phase 3 最新状态
3. 更新 `docs/architecture.md` — 修正过时内容
4. 真实数据接入模块代码 (Meta Ads live / ThinkingData / 工单系统)
5. 双向协同 + 冲突检测模块代码
6. JSONL 轮转 + 告警通知模块代码
7. 前端增强组件代码
8. 全量测试通过证明 (≥ 500 项)

---

## 附录 A: Phase 1-2 成果摘要

### Phase 1 — Product Manager Agent + CEO 决策中心
- Product Agent 注册 (10 项能力: 5 立项 + 5 增长)
- CEO 决策中心空数据 Bug 修复
- 59/59 测试通过

### Phase 2 — Game Designer + Numerical Designer + 跨 Agent 协同
- Game Designer Agent (5 模型, 3 品类, 5 方法, 8 API, 45 测试)
- Numerical Designer Agent (LTV/CAC/留存/付费/调优/A-B/通胀)
- DataNumericalBridge (~620 行, 4 步协同闭环)
- 2 个集成缺口修复 (MessageBus 注入 + EconomyBalance 消费)
- 55 项测试 (36 单元 + 19 集成)
- 470/470 全量回归通过

### Phase 2 后延伸
- 10 Agent 完整架构 (Data Analyst + Player Support 补齐)
- SSE 实时事件流 (多事件源 + 心跳 + 声音通知)
- 跨 Agent 拓扑可视化 (10 节点 15 边, 交互式 SVG)
- GrowthLoop 定时调度 (7×24 无人值守)

---

## 附录 B: 当前 10 Agent 清单

| # | Agent | 部门 | 角色 |
|---|-------|------|------|
| 1 | Growth Supervisor | 增长 | 目标分解/任务编排 |
| 2 | UA Agent | 增长 | Meta Ads/预算分配 |
| 3 | Creative Agent | 增长 | 创意 DNA/疲劳检测 |
| 4 | Monetization Agent | 增长 | LTV/付费转化 |
| 5 | LiveOps Agent | 运营 | 流失分析/回流活动 |
| 6 | Product Manager Agent | 研发 | PRD/GDD/Roadmap |
| 7 | Game Designer Agent | 研发 | 关卡/数值/系统 |
| 8 | Numerical Designer Agent | 研发 | LTV/CAC/调优/A-B |
| 9 | Data Analyst Agent | 运营 | 行为分析/BI/异常 |
| 10 | Player Support Agent | 运营 | 工单/FAQ/VIP |

---

## 附录 C: 当前协同链路清单

| 链路 | 方向 | 类型 | 状态 |
|------|------|------|------|
| CEO → LiveOps | 决策触发 | trigger | ✅ 已实现 |
| CEO → Growth | GrowthLoop 触发 | trigger | ✅ 已实现 |
| CEO → Product | 立项指令 | trigger | ✅ 已实现 |
| Product → Designer | GDD 传递 | data_flow | ✅ 已实现 |
| Designer → Numerical | EconomyBalance | data_flow | ✅ 已实现 |
| Data Analyst → Numerical | behavior_analyzed | collaboration | ✅ 已实现 |
| LiveOps → Growth | churn_alert | alert | ✅ 已实现 |
| LiveOps → Creative | 素材需求 | collaboration | ✅ 已实现 |
| Player Support → LiveOps | VIP 反馈 | collaboration | ✅ 已实现 |
| 各 Agent → CEO Memory | 执行结果回流 | feedback | ✅ 已实现 |
| Numerical → Data Analyst | 调优后重分析 | collaboration | ⏳ Phase 3 M3.1 |
| 冲突检测 | 多 Agent 数值修改 | guard | ⏳ Phase 3 M3.2 |
