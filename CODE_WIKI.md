# Code Wiki — LaunchForge / AI Game Studio OS

> 本文档为 `d:\project_slim\project_slim` 项目的结构化代码百科。涵盖项目整体架构、主要模块职责、关键类与函数说明、依赖关系以及项目运行方式等关键信息。
>
> 生成日期：2026-08-10 · 适用版本：Growth Loop V2 + P4 Autonomous Growth

---

## 目录

1. [项目概述](#1-项目概述)
2. [项目架构总览](#2-项目架构总览)
3. [核心模块详解](#3-核心模块详解)
   - 3.1 [Growth Loop V2（增长闭环核心）](#31-growth-loop-v2增长闭环核心)
   - 3.2 [src/execution/（P2 执行契约层 + V2 审批栈）](#32-srcexecutionp2-执行契约层--v2-审批栈)
   - 3.3 [src/growth_reality/（现实数据大脑）](#33-srcgrowth_reality现实数据大脑)
   - 3.4 [src/operator/（P3 运营决策层）](#34-srcoperatorp3-运营决策层)
   - 3.5 [src/autonomous_growth/（P4 自治增长层）](#35-srcautonomous_growthp4-自治增长层)
   - 3.6 [src/market_ops/（市场运营全栈）](#36-srcmarket_ops市场运营全栈)
   - 3.7 [src/aso_intelligence/ 与 src/aso_os/（ASO 智能 + OS 内核）](#37-srcaso_intelligence-与-srcaso_osaso-智能--os-内核)
   - 3.8 [monetization/（自治变现 OS）](#38-monetization自治变现-os)
   - 3.9 [operation/（变现运营层）](#39-operation变现运营层)
   - 3.10 [基础设施层（audit/backup/health/observability/security/release_gate）](#310-基础设施层)
4. [数据流与集成](#4-数据流与集成)
5. [关键类与函数说明](#5-关键类与函数说明)
6. [依赖关系](#6-依赖关系)
7. [项目运行方式](#7-项目运行方式)
8. [测试体系](#8-测试体系)
9. [部署与运维](#9-部署与运维)

---

## 1. 项目概述

### 1.1 项目定位

LaunchForge / AI Game Studio OS 是面向海外休闲手游的 **AI Game Publishing Operating System**，目标是一人管理 10-50 款游戏。系统把绩效信号转化为安全可测量的创意增长动作，通过一个可观测循环：

```
collect → normalize → understand → decide → produce → approve → execute → measure → learn
```

### 1.2 核心能力

| 能力域 | 说明 |
|--------|------|
| **Growth Loop V2** | Meta Ads 信号 → 诊断 → 假设 → 策略 → 动作 → 执行 → 评估 → 经验回写的全自动增长闭环 |
| **P2 执行层** | V2 三级审批栈（Level 0 自动 / Level 1 dry_run 验证 / Level 2 人工） |
| **P3 运营层** | 15 阶段每日经营循环 + CEO 决策单 + 策略反馈 |
| **P4 自治层** | 舰队分片编排 + 11 阶段认知循环 + 多 Agent 治理 + 系统硬化 |
| **ASO OS** | 13 子模块的商店优化操作系统（事件总线 + 工作流 + 知识图谱） |
| **变现 OS** | 广告指标引擎 + 变现代理 + Provider 契约 + 决策记忆 |
| **创意进化** | Creative DNA → 变异 → 进化 → 市场反馈 → 收入归因校准 |

### 1.3 设计原则（不可协商边界）

来自 [ULTIMATE_PRODUCT_TARGET.md](file:///d:/project_slim/project_slim/ULTIMATE_PRODUCT_TARGET.md)：

1. 观察/推荐可自动；创意生成可在成本限额内自动
2. **平台写入必须显式批准 artifact**
3. 每次写入幂等/审计/限速/可逆
4. 失败依赖/陈旧源/质量门阻断下游
5. 实验引擎无稳定契约不得成生产依赖
6. **Lean 架构**：纯 Python + JSONL，无 FastAPI/Postgres/React 主框架
7. **Three-Gate Execution**：推荐 → 仿真 → 批准 → 执行
8. **Fail-Closed**：默认 dry_run / `MARKET_OPS_ALLOW_PLATFORM_WRITES=0` / `FACEBOOK_SANDBOX=true`

---

## 2. 项目架构总览

### 2.1 五层架构模型

来自 [docs/architecture.md](file:///d:/project_slim/project_slim/docs/architecture.md)：

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 5: Agent Decision（业务大脑）                          │
│  ASO Intelligence / Revenue / Economy / CFO / Monetization   │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: Growth OS（编排/组合）                              │
│  Growth Loop V2 Orchestrator / P3 Pipeline / P4 Fleet        │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: Execution（发布/变现运营/审批）                     │
│  src/execution (P2) / operation/ (E15) / monetization/ (E13) │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 2: Reality/Data（MAX/Google Play/App Store/Adjust/TD） │
│  src/growth_reality / market_ops/clients / RealityGate       │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: Memory/Learning（模式/实验/审计）                   │
│  ExperienceStore / PatternMemory / DecisionRecord / Audit    │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 版本路线图

来自 [specs/E9_ROADMAP.md](file:///d:/project_slim/project_slim/specs/E9_ROADMAP.md)：

| 版本 | 名称 | 状态 | 核心里程碑 |
|------|------|------|-----------|
| E9.4-E9.7 | Player Intelligence | DONE | Player Value / Archetype / Prediction / Feedback Learning |
| E10 | Game Company OS | VISION | 终极愿景 |
| E11 | Creative Growth Evolution | DONE | Genome → Mutation → Evolution → Market Feedback |
| E12 | Reality Integration | DONE | TD/Adjust/Meta Reality → RealityDataHub |
| E13 | Monetization OS | DONE | 变现代理 + Provider 契约 + 决策记忆 |
| E14 | Multi-Game Isolation | DONE | GameFactoryOS + HealthMonitor |
| E15 | Live Pipeline | DONE | MAX/Adjust 真实数据运营 |
| E16 | ASO Intelligence | DONE | 4 Analyzers + ASOAction + DecisionValidator |
| E17 | Growth Reality Hub | DONE | E17.1-E17.9 完整决策脑 |
| P2 | Execution Layer | DONE | V2 三级审批栈 |
| P3 | Operator Layer | DONE | 15 阶段日循环 + CEO 报告 |
| P4 | Autonomous Growth | COMPLETE | Fleet + Cycle + ProductFactory + MultiAgent + Hardening |
| **Growth Loop V2** | **Signal-Driven Loop** | **DONE** | **8 引擎闭环 + 三接线 + 跨重启续跑** |

### 2.3 顶层目录结构

```
project_slim/
├── src/                          # 主源码包（namespace packages）
│   ├── execution/                # P2 执行契约层 + V2 审批栈
│   ├── growth_reality/           # E17.1 现实数据大脑
│   ├── operator/                 # P3 运营决策层
│   ├── autonomous_growth/        # P4 自治增长层
│   ├── market_ops/               # 市场运营全栈（最大模块）
│   ├── aso_intelligence/         # ASO 智能 Agent
│   └── aso_os/                   # ASO Growth Operating System
├── scripts/                      # 可执行脚本（Growth Loop V2 核心链路）
├── monetization/                 # 自治变现 OS
├── operation/                    # 变现运营层（E15.2.x）
├── tests/                        # 测试套件（280+ 文件 / 1182+ 用例）
├── docs/                         # 架构文档
├── specs/                        # FROZEN 规范（E9 等）
├── deploy/                       # Lean Worker 容器部署
├── data/                         # JSONL 持久化数据
├── outputs/                      # 报告产物
├── credentials/                  # 凭证（不进 git）
└── requirements/                 # 依赖清单
```

---

## 3. 核心模块详解

### 3.1 Growth Loop V2（增长闭环核心）

**位置**：[scripts/](file:///d:/project_slim/project_slim/scripts/) 目录下的 8 个核心模块 + 入口脚本

Growth Loop V2 是项目的**核心增长闭环**，把 Meta Ads 信号转化为受控的预算调整动作，并回写经验形成长期学习。

#### 3.1.1 闭环数据流

来自 [scripts/run_growth_loop.py](file:///d:/project_slim/project_slim/scripts/run_growth_loop.py) L9-29：

```
Meta Ads API
  ↓ fetch_performance_rows (当前周期 + 上一周期)
aggregate_by_creative → {creative_id: metrics}
  ↓
接线 3: MetricsAdapter (七域快照 + PlayerProfile 富集)
  ↓
generate_predictions → RealityPrediction 列表
  ↓
FeedbackController.evaluate → triggered 信号
  ↓ (信号 + current_metrics + previous_metrics)
接线 1: RealityGate 审计 (可信分门控)
  ↓
GrowthLoopOrchestrator.run_cycle
  ├─ Phase A: 评估到期 PendingEvaluation
  ├─ Phase B: Diagnose → Hypothesize → Select → Plan → Execute
  └─ Phase C: 持久化全部状态
  ↓
CycleResult (含诊断/假设/策略/动作/执行结果)
```

#### 3.1.2 8 个核心引擎模块

| 模块 | 文件 | 行数 | 核心职责 |
|------|------|------|---------|
| **Orchestrator** | [growth_loop_orchestrator.py](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py) | 947 | 三阶段主循环编排（Phase A/B/C），V2 集成层支持 Level 0/1/2 分级执行 |
| **Diagnostic** | [diagnostic_engine.py](file:///d:/project_slim/project_slim/scripts/diagnostic_engine.py) | 638 | 从 FeedbackSignal + 指标推断 8 种根因（creative_fatigue / audience_saturation / hook_decay 等） |
| **Hypothesis** | [hypothesis_generator.py](file:///d:/project_slim/project_slim/scripts/hypothesis_generator.py) | 535 | 诊断结果 + 历史经验 → 可验证 GrowthHypothesis，三因子加权置信度（诊断0.5+模式0.3+全局0.2） |
| **Strategy** | [strategy_selector.py](file:///d:/project_slim/project_slim/scripts/strategy_selector.py) | 494 | 假设 → 策略类型 + 执行强度（SUPPRESS 降10-50% / SCALE 升10-30%） |
| **Planner** | [action_planner.py](file:///d:/project_slim/project_slim/scripts/action_planner.py) | 210 | 策略 → ExecutionAction（统一格式），预算安全边界（最低$20/单次升30%降50%） |
| **Executor** | [action_executor.py](file:///d:/project_slim/project_slim/scripts/action_executor.py) | 402 | 状态机 PENDING→SAFETY_CHECK→APPROVED→EXECUTING→COMPLETED/ROLLED_BACK，SafetyGate 门控 |
| **Outcome** | [outcome_evaluator.py](file:///d:/project_slim/project_slim/scripts/outcome_evaluator.py) | 220 | 评估执行效果（improvement>0.15=SUCCESS），写入 ExperienceStore 闭合循环 |
| **Persistence** | [loop_persistence.py](file:///d:/project_slim/project_slim/scripts/loop_persistence.py) | 285 | 管理 4 个文件：loop_state.json / pending_evaluations.jsonl / cycle_history.jsonl / experience_snapshot.json |

#### 3.1.3 关键类

**`GrowthLoopOrchestrator`**（[growth_loop_orchestrator.py:152](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py)）

```python
class GrowthLoopOrchestrator:
    def __init__(self, diagnostic_engine, hypothesis_generator, strategy_selector,
                 action_planner, action_executor, outcome_evaluator,
                 experience_store, pattern_memory=None,
                 loop_persistence=None, v2_executor=None,  # V2 集成
                 reality_scores=None, game_id_resolver=None):
        ...

    def run_cycle(self, signals, current_metrics, previous_metrics,
                  creative_to_adset_map, current_budgets) -> CycleResult:
        # Phase A: 评估到期 PendingEvaluation (L554-624)
        # Phase B: 对每个信号执行完整链路 (L712-859)
        # Phase C: 持久化全部状态 (L865-908)
```

**`CycleResult`**（[growth_loop_orchestrator.py:84](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py)）

含 V2 统计字段：`v2_level0_executed` / `v2_level0_shadow` / `v2_level1_promoted` / `v2_level1_blocked` / `v2_level2_blocked` / `v2_denied` / `v2_fallback_v1`

#### 3.1.4 三条接线

| 接线 | 入口 | 作用 |
|------|------|------|
| **Connection 1** | [run_growth_loop.py:705-737](file:///d:/project_slim/project_slim/scripts/run_growth_loop.py) | RealityGate 可信度门控注入 ActionExecutor（composite < 0.5 BLOCKED / 0.5-0.8 审批 / ≥0.8 自动） |
| **Connection 2** | [run_growth_loop.py:627-664](file:///d:/project_slim/project_slim/scripts/run_growth_loop.py) | Meta Ads 数据流 → 聚合 → 信号 → Orchestrator.run_cycle |
| **Connection 3** | [run_growth_loop.py:666-681](file:///d:/project_slim/project_slim/scripts/run_growth_loop.py) | MetricsAdapter 用产品侧真实收入（IAP+IAA）富集广告侧指标 |

#### 3.1.5 适配器层

- [meta_ads_adapter.py](file:///d:/project_slim/project_slim/scripts/meta_ads_adapter.py)：`MetaAdsPlatformAdapter` 封装 V1 FacebookClient，支持 update_campaign_budget / pause_campaign / resume_campaign
- [metrics_adapter.py](file:///d:/project_slim/project_slim/scripts/metrics_adapter.py)：`MetricsAdapter.adapt()` 以广告侧为主源，用产品侧真实收入替换反推值

#### 3.1.6 V2 三级审批执行路径

来自 [growth_loop_orchestrator.py:332-438](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py) `_execute_via_v2()`：

```
ApprovalPolicy.evaluate(intent)
  ├─ Level 0 (AUTO): 小额+低风险+高置信+allowlist + level0_enabled
  │   ├─ shadow_mode → 只记 audit 不执行
  │   └─ v2_executor._execute_level0 → BudgetWindowTracker.record + executor.execute
  ├─ Level 1 (MANUAL + dry_run_required): 中额或中风险
  │   └─ DryRunVerifier.verify_and_promote
  │       ├─ 通过 → BudgetWindowTracker.record + executor.execute
  │       └─ 失败 → 阻塞等人工
  └─ Level 2 (MANUAL/ADMIN): 大额/超日累计/ADMIN 动作
      └─ 阻塞等人工
```

---

### 3.2 src/execution/（P2 执行契约层 + V2 审批栈）

**位置**：[src/execution/](file:///d:/project_slim/project_slim/src/execution/)

P2 执行层是 AI CEO 的"手部接口"，把 E17.3 GrowthDecision 转化为受控的真实世界动作。

#### 3.2.1 模块结构

```
src/execution/
├── __init__.py            # 包入口，导出 6 组公共符号
├── contracts.py           # ExecutionContract 端到端打包 (156 行)
├── intent.py              # ExecutionIntent 构建 + 风险分级 (98 行)
├── mapper.py              # Decision→Intent 映射表 (146 行)
├── models.py              # 执行域模型 (207 行)
├── registry.py            # 能力注册表 (131 行)
├── validator.py           # 契约校验器（五级放行）(116 行)
├── approval/              # V2 审批栈子包
│   ├── policy.py          # ApprovalPolicy V2 三级分级 (481 行)
│   ├── v2_executor.py     # V2ActionExecutor 集成层 (370 行)
│   ├── budget_window.py   # BudgetWindowTracker 日累计追踪 (297 行)
│   ├── dry_run_verifier.py# DryRunVerifier Level 1 验证 (226 行)
│   ├── models.py          # ApprovalRequest + ExecutionAuthorization (222 行)
│   ├── config.py          # ApprovalConfig 环境加载 (267 行)
│   ├── roles.py           # 四级角色权限 (95 行)
│   ├── store.py           # JsonlApprovalStore append-only (185 行)
│   └── workflow.py        # ApprovalWorkflow
├── monitor/               # 执行可观测层
│   ├── models.py          # 10 类事件 + 9 态状态机 (401 行)
│   └── health.py          # SLA + 健康分公式 (228 行)
└── providers/
    └── base.py            # ExecutionProvider 协议 (189 行)
```

#### 3.2.2 关键数据流（V2 审批栈）

```
E17.3 GrowthDecision
  ↓
mapper.DecisionToIntentMapper.map (决策动作→执行动作映射)
  ↓ ExecutionIntent
contracts.build_contract
  ├─ validator.ExecutionContractValidator.validate (五级放行)
  └─ ExecutionContract
  ↓
approval.policy.ApprovalPolicy.evaluate (V2 三级分级)
  ↓ ApprovalDecision
approval.store (ApprovalRequest 持久化, append-only JSONL)
  ↓ ExecutionAuthorization (24h TTL)
providers.base.BaseExecutionProvider.execute
  ├─ DRY_RUN/SIMULATION → real_api_called=False
  └─ PRODUCTION → _do_real → real_api_called=True
  ↓ ExecutionResult
monitor.models (10 类事件 + 9 态状态机)
monitor.health.compute_health_score
  (Score=SuccessRate×0.4+ProviderHealth×0.3+LatencyScore×0.2+RollbackSafety×0.1)
```

#### 3.2.3 关键类

**`ExecutionContract`**（[contracts.py:37](file:///d:/project_slim/project_slim/src/execution/contracts.py)）：不可变执行合同，含 `blocked` / `needs_approval` / `approved_auto` 属性

**`ApprovalPolicy`**（[approval/policy.py:122](file:///d:/project_slim/project_slim/src/execution/approval/policy.py)）：V2 策略引擎，七级决策流程，支持 V1/V2 双构造模式

**`V2ActionExecutor`**（[approval/v2_executor.py:85](file:///d:/project_slim/project_slim/src/execution/approval/v2_executor.py)）：组合 ApprovalPolicy + DryRunVerifier + BudgetWindowTracker + ActionExecutor，实现 Level 0/1/2 三级执行

**`BudgetWindowTracker`**（[approval/budget_window.py:101](file:///d:/project_slim/project_slim/src/execution/approval/budget_window.py)）：按 (game_id, action_type, day) 追踪累计金额，防止小额高频绕过单次阈值

**`DryRunVerifier`**（[approval/dry_run_verifier.py:62](file:///d:/project_slim/project_slim/src/execution/approval/dry_run_verifier.py)）：Level 1 动作真实执行前先跑 dry_run，对比 expected_impact，差异 > 20% 拒绝升级

#### 3.2.4 角色权限系统

来自 [approval/roles.py](file:///d:/project_slim/project_slim/src/execution/approval/roles.py)：

| 角色 | 能力 | 典型动作 |
|------|------|---------|
| SYSTEM | 策略自动批准白名单低风险 | DISABLE_NETWORK, CREATE_INVESTIGATION |
| OPERATOR | 日常安全操作 | + PAUSE_CAMPAIGN |
| MANAGER | 资金调度 | + SCALE_BUDGET, UPDATE_WATERFALL, CREATE_ASO_UPDATE |
| ADMIN | 发布与超大额预算 | + CREATE_RELEASE |

低角色能力被高角色继承。

---

### 3.3 src/growth_reality/（现实数据大脑）

**位置**：[src/growth_reality/](file:///d:/project_slim/project_slim/src/growth_reality/)

E17.1 Growth Reality Hub，项目的"现实数据大脑"，从多源采集→归一化→持久化→聚合→审计→门控的完整现实数据链路。

#### 3.3.1 模块结构

```
src/growth_reality/
├── agent.py           # GrowthRealityHub 编排入口 (59 行)
├── collector.py       # RealityCollector 数据采集 (195 行)
├── models.py          # GrowthRealitySnapshot 五域 Fact (281 行)
├── normalizer.py      # RealityNormalizer 归一化 (80+ 行)
├── feature_store.py   # GrowthFeatureStore 逐游戏 JSONL (56 行)
├── registry.py        # GameRegistry 游戏映射 (229 行)
├── snapshot.py        # CompanySnapshot 公司级聚合 (97 行)
├── validation/        # P1.7 审计层
│   ├── auditor.py     # RealityAuditor 全链路审计 (107 行)
│   ├── gate.py        # RealityGate 决策门控 (101 行)
│   ├── confidence.py  # ConfidenceScorer 三维可信分 (59 行)
│   ├── reconciliation.py # RevenueReconciler 收入对账 (80+ 行)
│   ├── freshness.py   # DataFreshnessMonitor 新鲜度 (80+ 行)
│   └── models.py      # 审计数据模型 (216 行)
├── coverage/          # P1.6 真实数据覆盖层
└── production_sources/# 生产数据源（Adjust/MAX/Meta）
```

#### 3.3.2 RealityGate 决策门控

来自 [validation/gate.py](file:///d:/project_slim/project_slim/src/growth_reality/validation/gate.py)：

| 可信分 composite | 决策等级 | 行为 |
|-----------------|---------|------|
| < 0.5 | BLOCKED | 禁止 EXECUTE，降级为 OBSERVE |
| 0.5 - 0.8 | APPROVE | 需人工审批 |
| > 0.8 | EXECUTE | 允许自动执行 |

#### 3.3.3 关键数据流

```
RealitySource (Protocol) → RealityCollector.collect_fleet
  ↓ 原始 domain dict
RealityNormalizer.normalize_game
  ↓ GrowthRealitySnapshot (含派生指标 arpdau/roas)
GrowthFeatureStore.append
  ↓ 逐游戏 JSONL (data/growth_reality/<game_id>.jsonl)
build_company_snapshot
  ↓ CompanySnapshot (公司级总览)
RealityAuditor.audit
  ├─ RevenueReconciler (对账: Adjust IAP + MAX 广告收入)
  ├─ DataFreshnessMonitor (新鲜度: <6h GREEN / 6-24h YELLOW / >24h RED)
  └─ ConfidenceScorer (可信分: Coverage × Freshness × Consistency)
  ↓ AuditReport
RealityGate.apply (门控决策)
```

---

### 3.4 src/operator/（P3 运营决策层）

**位置**：[src/operator/](file:///d:/project_slim/project_slim/src/operator/)

P3 是"每日增长经营循环（Operating Loop）的薄编排层"，承担五条主线：依赖装配 / 15 阶段编排 / 幂等调度 / 策略反馈 / CEO 日报。

#### 3.4.1 15 阶段编排

来自 [pipeline.py](file:///d:/project_slim/project_slim/src/operator/pipeline.py)（900 行）`DailyOperatorPipeline`：

| # | 阶段 | 职责 |
|---|------|------|
| 1 | reality | E17.9 hub.refresh 或预置 company |
| 2 | audit | P1.7 RealityAuditor.audit |
| 3 | opportunities | 提取 E17.9 统计 |
| 4 | simulations | 模拟统计 |
| 5 | decisions | 决策统计 |
| 6 | approval | P2.1 合同 → P2.3 ApprovalService.submit |
| 7 | executions | P2.4 SafeExecutor 唯一执行出口 |
| 8 | monitor | P2.5 ExecutionMonitor.observe_batch |
| 9 | recovery | P2.6 RecoveryEngine.handle |
| 10 | memory | 校验 E17.9 跨日记忆落盘 |
| 10.5 | liveops | CEO → LiveOps 单向触发流失分析 |
| 11 | strategy_loop | P3.3 策略反馈控制器（只读 + 产建议） |
| 11.5 | portfolio | P3.4.5 跨游戏资源编排（只建议不执行） |
| 12 | ceo_report | P3.2 聚合产物 → 运营决策单 |
| 14 | report | 工程日志 |

#### 3.4.2 子包结构

```
src/operator/
├── __init__.py        # build_growth_operator 一键装配入口
├── context.py         # OperatorContext + build_operator_context (132 行)
├── pipeline.py        # DailyOperatorPipeline 15 阶段编排 (900 行)
├── scheduler.py       # GrowthOperatorScheduler 幂等调度 (88 行)
├── state.py           # OperatorRunStore JSONL 状态 (78 行)
├── feedback.py        # 决策学习反馈适配器 (100 行)
├── models.py          # StageResult / OperatorRunResult (181 行)
├── report/            # CEO 日报
│   ├── builder.py     # CEOReportBuilder (192 行)
│   ├── models.py      # CEODailyReport 三态行动队列 (311 行)
│   ├── renderer.py    # render_markdown 11 节决策单 (337 行)
│   └── sections.py    # 各 section 纯数据装配 (353 行)
└── strategy/          # 策略反馈控制
    ├── loop.py        # StrategyLoop Observe→Evaluate→Learn→Adjust→Emit (261 行)
    ├── guard.py       # StrategyGuard 闸门 (50 行)
    ├── memory.py      # StrategyMemoryAdapter 经验持久化 (194 行)
    └── models.py      # StrategyProposal / StrategyState (254 行)
```

#### 3.4.3 关键架构特征

1. **单向依赖**：`autonomous_growth` → `operator` → `ceo_intelligence` / `execution` / `growth_reality`，无循环
2. **单一执行出口**：所有真实 API 调用必经 `SafeExecutor.execute`
3. **单一审批真相源**：`ApprovalService` 共享同一 `InMemoryApprovalStore`
4. **fail-open / fail-closed 分级**：feedback / memory_controller / liveops 为 fail-open；approval / safe_executor 为 fail-closed
5. **幂等分层**：E17.9 管循环、P3.1 OperatorRunStore 管全 15 阶段、canary 管灰度单动作

---

### 3.5 src/autonomous_growth/（P4 自治增长层）

**位置**：[src/autonomous_growth/](file:///d:/project_slim/project_slim/src/autonomous_growth/)

P4 把 `operator` 的每日运营流程升级为可自治运行的多 Agent 公司 OS。

#### 3.5.1 模块结构

```
src/autonomous_growth/
├── __init__.py         # 包入口，导出全模块公共符号
├── __main__.py         # CLI: python -m src.autonomous_growth [dry_run|production]
├── agent.py            # AutonomousGrowthAgent 安全外壳 (72 行)
├── canary.py           # CanaryCoordinator 单动作灰度 (77 行)
├── company_os.py       # CompanyOS 日循环入口 (55 行)
├── cycle.py            # AutonomousCycle 11 阶段认知循环 (119 行)
├── fleet.py            # FleetOrchestrator 分片并行 (113 行)
├── hardening.py        # SLO + DurableQueue + RecoveryDrill (111 行)
├── models.py           # AgentConfig / ReadinessReport (75 行)
├── multi_agent.py      # MultiAgentGovernor 提案仲裁 (57 行)
├── product_factory.py  # ProductFactory 生命周期 (61 行)
├── readiness.py        # ProductionReadinessGate 启动门 (76 行)
└── runtime.py          # LaunchForgeRuntime 组合根 (67 行)
```

#### 3.5.2 11 阶段认知循环

来自 [cycle.py](file:///d:/project_slim/project_slim/src/autonomous_growth/cycle.py) `CycleStage`：

```
OBSERVE → UNDERSTAND → REMEMBER → DECIDE → SIMULATE
  → APPROVE → EXECUTE → MEASURE → LEARN → IMPROVE → COMPLETE
```

每阶段：handler(state, artifacts) → state.artifacts[stage]，每步落盘 CycleState（revision 单调递增），支持中断续跑。

#### 3.5.3 舰队编排

来自 [fleet.py](file:///d:/project_slim/project_slim/src/autonomous_growth/fleet.py)：

- `FleetConfig`：max_games=200 / shard_size=12 / max_workers=8
- `FleetOrchestrator.shard()`：确定性分片
- `FleetOrchestrator.run()`：ThreadPoolExecutor 并行跑每个分片，单分片异常不毁整轮
- 7 种 AgentRole：STRATEGY / GROWTH / PRODUCT / UA / ASO / MONETIZATION / CREATIVE

#### 3.5.4 P4 五大子模块（全部 COMPLETE）

| 子模块 | 职责 |
|--------|------|
| P4.1 Fleet Orchestrator | 50-200 游戏分片并行 |
| P4.2 Autonomous Cycle | 11 步可恢复幂等循环 |
| P4.3 Product Factory | 产品全生命周期（IDEA→PROTOTYPE→MARKET_TEST→LIVE→RETIRED） |
| P4.4 Multi-Agent Governance | 7 角色最小权限 + 提案仲裁 |
| P4.5 Production Hardening | SLO + 持久化队列 + 备份恢复 + 金丝雀 |

---

### 3.6 src/market_ops/（市场运营全栈）

**位置**：[src/market_ops/](file:///d:/project_slim/project_slim/src/market_ops/)

项目**最大的模块**，涵盖数据采集→分析→报告→执行→监控的完整闭环。

#### 3.6.1 模块结构

```
src/market_ops/
├── cli.py             # CLI 主入口 (2362 行)
├── config.py          # Settings 配置 (373 行)
├── models.py          # AdsPerformanceRow / CreativeAssetRow / RevenueRow (149 行)
├── pipeline.py        # WeeklyPipeline / DailySyncPipeline (1805 行)
├── analyzers.py       # AnalysisService AI 分析 (226 行)
├── action_layer.py    # ActionLayerBuilder 审计执行意图 (227 行)
├── creative_dna.py    # CreativeDnaBuilder 创意 DNA (501 行)
├── digest.py          # WeeklyDigestBuilder (1845 行)
├── reports.py         # Markdown 渲染 (118 行)
├── signal_score.py    # SignalScoreBuilder 信号评分 (320 行)
├── user_quality.py    # UserQualityBuilder 用户质量 (153 行)
├── prompts.py         # AI 提示词模板 (99 行)
├── clients/           # 外部数据源客户端
│   ├── thinkingdata.py  # ThinkingDataClient 数数 Open API
│   ├── adjust.py        # AdjustClient
│   ├── meta_ads.py      # MetaAdsCreativeClient
│   └── google_ads.py    # GoogleAdsClient
├── core/              # 创意生成核心管道（Phase 2.2A）
│   ├── generation_store.py      # SQLite 持久化 + 状态机
│   ├── lovart_queue.py          # LovartQueue 任务队列
│   ├── lovart_worker.py         # Worker + 事件发布
│   └── creative_generation_manager.py # 管道编排器
├── e11/               # 创意增长进化层（6 子层）
│   ├── genome/        # CreativeGenome / GenomeManager
│   ├── mutation/      # MutationOperator / StrategyLayer
│   ├── evolution/     # EvolutionOrchestrator / ConvergenceDetector
│   ├── market/        # FeedbackLoopController
│   ├── reality/       # GenomeAttributor / FitnessCalibrator
│   └── storage/       # 持久化
├── caf/               # Character-as-Feature 特征层
├── creative_vision_runtime/
│   └── reality/
│       ├── thinkingdata_reality.py  # ThinkingDataReality 门面层 (583 行)
│       ├── __init__.py              # E12 Reality Integration Layer
│       └── reality_data_hub.py      # RealityDataHub
└── workspace/         # FastAPI 工作台
    ├── app.py                  # 80+ API 端点 (2400+ 行)
    ├── growth_loop_scheduler.py # 后台线程调度器 (521 行)
    ├── alert_notifier.py       # 多渠道告警 (513 行)
    └── system_monitor.py       # 系统监控 (462 行)
```

#### 3.6.2 ThinkingData Reality 集成

来自 [creative_vision_runtime/reality/thinkingdata_reality.py](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/reality/thinkingdata_reality.py)（583 行）：

```
ThinkingData Open API
  ↓
ThinkingDataClient (clients/thinkingdata.py)
  ↓
ThinkingDataReality (本文件，薄门面层)
  ↓
ProductBehaviorRecord[]
  ↓
RealityDataHub → RealitySnapshot → E11 Evolution
```

`ThinkingDataReality` 类提供：
- `fetch_campaign_users(project_id, campaign_ids, date_range)` — 按 Campaign 拉取用户行为
- `fetch_recent_retention(project_id, lookback_days, use_cache)` — 留存数据（5 分钟 TTL 缓存）
- `fetch_user_cluster(project_id, cluster_name)` — 用户分群
- `fetch_multi_revenue(project_id, campaign_ids, date_range)` — 批量付费用户
- 默认 sandbox（mock），生产环境通过 config 切换

#### 3.6.3 workspace/ FastAPI 工作台

[app.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/app.py) 提供 80+ API 端点：

| 端点组 | 路径前缀 | 说明 |
|--------|---------|------|
| 基础 | `/healthz`, `/readyz`, `/api/dashboard` | 健康检查 + 仪表盘 |
| 组织 | `/api/organization`, `/api/agents`, `/api/tasks` | Agent 管理 |
| GrowthLoop | `/api/loop/history`, `/api/loop/scheduler/*` | 循环调度 |
| CEO | `/api/ceo/dashboard`, `/api/ceo/company-report` | CEO 决策中心 |
| 设计师 | `/api/designer/levels`, `/api/designer/economy` | 设计 Agent |
| 数值 | `/api/numerical/model`, `/api/numerical/ab-test` | 数值 Agent |
| 数据分析 | `/api/data-analyst/behavior`, `/api/data-analyst/funnel` | 数据分析 Agent |

---

### 3.7 src/aso_intelligence/ 与 src/aso_os/（ASO 智能 + OS 内核）

#### 3.7.1 src/aso_intelligence/（ASO 智能 Agent，E16.6.1）

**位置**：[src/aso_intelligence/](file:///d:/project_slim/project_slim/src/aso_intelligence/)

继 Revenue E16.1 和 Economy E16.2 之后的"第三个大脑"。

**关键文件**：
- [agent.py](file:///d:/project_slim/project_slim/src/aso_intelligence/agent.py)（377 行）：`ASOIntelligenceAgent` 编排器，4 大 Analyzer（Keyword/Conversion/Listing/Competitor）
- [memory.py](file:///d:/project_slim/project_slim/src/aso_intelligence/memory.py)（94 行）：`ASOMemory` 双写机制（experience + pattern）
- [models.py](file:///d:/project_slim/project_slim/src/aso_intelligence/models.py)（408 行）：8 类 ASOInsightType + 7 种 ASOAction

**核心数据流**：
```
ASORealityConnector.collect(game_id)
  → ASOSnapshot + Reviews + Competitors
  → 4 Analyzers → ASOInsight (去重 + 按 impact 排序)
  → ASOActionMapper → GrowthAction (携带 ASOAction enum)
  → DecisionValidator (3 置信度门: AUTO / HUMAN_QUEUE / RECORD_ONLY)
  → Growth Executor / 人工队列 / 仅记录
  → record_outcome → ASOMemory (双写 experience + pattern)
```

**关键原则**：ASO Agent **绝不直接执行 ASO 改动**，所有推荐都流经共享的 `DecisionValidator` 进行审计。

#### 3.7.2 src/aso_os/（ASO Growth OS，E16.6.14）

**位置**：[src/aso_os/](file:///d:/project_slim/project_slim/src/aso_os/)

包裹所有 13 个 ASO 子模块的"操作系统"层。

**关键文件**：
- [agent.py](file:///d:/project_slim/project_slim/src/aso_os/agent.py)（189 行）：`ASOOSAgent` 7 步每日循环
- [governance/policy.py](file:///d:/project_slim/project_slim/src/aso_os/governance/policy.py)（61 行）：3 级审批路由（auto / human_confirm / human_decide）
- [kernel/models.py](file:///d:/project_slim/project_slim/src/aso_os/kernel/models.py)（236 行）：13 种 ASOEventType + 8 阶段 WorkflowStage + 知识图谱
- [kernel/state.py](file:///d:/project_slim/project_slim/src/aso_os/kernel/state.py)（91 行）：`ASOOSKernel` 事件总线 + 状态管理

**7 步每日循环**（`ASOOSAgent.daily_run`）：
1. 更新 kernel 状态
2. Events → Opportunities
3. 优先级排序（含 portfolio 过滤）
4-5. Workflow + Execute（仅 auto 来源）
6. 从 revenue feedback 学习 pattern
7. 生成 Dashboard Report

**8 阶段工作流**：`DISCOVERED → ANALYZED → PLANNED → GENERATED → APPROVED → RUNNING → MEASURED → LEARNED`

---

### 3.8 monetization/（自治变现 OS）

**位置**：[monetization/](file:///d:/project_slim/project_slim/monetization/)

完整的自治变现操作系统，从现实观测到配置执行的全闭环控制。

#### 3.8.1 模块结构

```
monetization/
├── facts.py            # MonetizationFact + build_monetization_facts (132 行)
├── metrics.py          # 纯函数指标引擎 (144 行)
├── agent/              # 自治变现代理
│   ├── models.py       # 四动作词汇 + AgentState (204 行)
│   ├── planner.py      # Planner 融合 sim_conf 0.5 + prior_mean 0.5 (121 行)
│   ├── policy.py       # Policy 五级决策优先级 (92 行)
│   ├── registry.py     # GameFactoryOS 多游戏隔离 (172 行)
│   ├── scheduler.py    # Scheduler 调度 (50 行)
│   └── guardrails.py   # Guardrails 硬约束
├── executor/
│   └── models.py       # Change / ExecutionRequest / ExecutionResult (195 行)
├── learning/
│   └── models.py       # DecisionRecord 决策生命周期 (219 行)
├── providers/
│   └── base.py         # MonetizationProvider FROZEN 契约 (191 行)
├── runtime/
│   └── health.py       # HealthMonitor 三类检查 (112 行)
└── strategy/
    └── models.py       # StrategyCandidate / ScoredCandidate (139 行)
```

#### 3.8.2 核心数据流

```
EventAggregator → AggregatedData
  ↓
metrics.py (compute_ad/user/retention/ltv)
  ↓
facts.py (build_monetization_facts) → MonetizationFact[]
  ↓
Reality Engine → Opportunity
  ↓
strategy/models.py → Simulator → ScoredCandidate → RankedStrategy
  ↓
agent/planner.py (融合 sim_conf 0.5 + prior_mean 0.5)
  ↓ Policy.decide → Guardrails.enforce
Plan
  ↓
executor/models.py (ExecutionRequest → Approval Gate → ExecutionResult)
  ↓
providers/base.py (apply_change / rollback_change)
  ↓
learning/models.py (DecisionRecord) → OutcomeTracker 闭环
  ↓
runtime/health.py (HealthMonitor.check)
```

#### 3.8.3 四动作词汇

| 动作 | 含义 | 触发条件 |
|------|------|---------|
| OBSERVE | 仅观察 | 兜底 |
| EXPERIMENT | 实验 | 引入策略 + 新分段 |
| EXECUTE | 执行 | 成熟组合 + severe + known_good + confident |
| BLOCK | 阻断 | 高保留风险 |

---

### 3.9 operation/（变现运营层）

**位置**：[operation/](file:///d:/project_slim/project_slim/operation/)

E15.2.x 变现运营层，面向 MAX/AdMob 广告变现 waterfall 运营。

**与 src/execution/ 的关系**：
- `operation/`：**变现侧**的执行与记忆（waterfall 重排、bid-floor 调整、before/after 快照）
- `src/execution/`：**决策侧**的执行契约与审批分级（Level 0/1/2）

两者互补而非重叠。Growth Loop V2 通过 `src.execution` 的 ExecutionIntent 走 V2 审批路径，动作经审批后由 `MetaAdsPlatformAdapter`（广告侧）或 `operation/`（变现侧）落地。

**子目录**：
- `memory/`：MemoryAgent 快照 before/after + 记录 context/results + 查询相似历史操作
- `optimizer/`：RevenueAnalyzer 确定性规则检测变现问题
- `providers/`：真实 MAX/Adjust provider factory + secrets
- `safety/`：SafetyAgent 安全守护 + rules

---

### 3.10 基础设施层

| 目录 | 文件 | 用途 |
|------|------|------|
| **audit/** | `trail.py` | EP0.7 审计追踪：不可变记录每个 agent 决策与执行 |
| **backup/** | `manager.py` | EP0.8 备份与恢复：快照/恢复 Memory/Patterns/Decision history |
| **health/** | `agent_health.py` | EP0.11.7 AgentHealth：运行时健康门控（HEALTHY/DEGRADED/BLOCKED） |
| **observability/** | `logger.py`, `metrics.py` | EP0.6 可观测性：统一日志，禁止 print() |
| **release_gate/** | `checker.py` | EP0.4 回归门：merge/release 前 GREEN 检查 |
| **security/** | `permissions.py`, `secrets/` | EP0.1.4 权限审计 + 密钥扫描 |
| **analytics/** | (空) | 预留分析模块包 |
| **optimization/** | (空) | 预留优化模块包 |
| **simulation/** | (空) | 预留模拟模块包 |

---

## 4. 数据流与集成

### 4.1 系统级数据流（Growth Loop V2 完整闭环）

```
┌─────────────────────────────────────────────────────────────────────┐
│  外部数据源                                                          │
│  Meta Ads API · Adjust · ThinkingData · MAX · Google Play · App Store│
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: Reality/Data                                               │
│  src/growth_reality/ RealityCollector → Normalizer → FeatureStore   │
│  src/market_ops/clients/ (TD/Adjust/Meta/Google)                    │
│  → CompanySnapshot + RealityScore                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 4: Growth Loop V2 Orchestrator                                │
│  scripts/growth_loop_orchestrator.py run_cycle                       │
│  ├─ Phase A: 评估到期 PendingEvaluation                              │
│  ├─ Phase B: Diagnose → Hypothesize → Select → Plan → Execute       │
│  │   ├─ diagnostic_engine (8 种根因推断)                             │
│  │   ├─ hypothesis_generator (三因子加权置信度)                      │
│  │   ├─ strategy_selector (SUPPRESS/SCALE 强度)                     │
│  │   ├─ action_planner (ExecutionAction 统一格式)                    │
│  │   └─ action_executor (状态机 + SafetyGate)                        │
│  │       ├─ V1 路径: 直接执行                                        │
│  │       └─ V2 路径: v2_executor → ApprovalPolicy → Level 0/1/2     │
│  └─ Phase C: 持久化 (loop_persistence)                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: Execution                                                  │
│  src/execution/ V2 审批栈                                            │
│  ApprovalPolicy → BudgetWindowTracker → DryRunVerifier               │
│  → ExecutionAuthorization → Provider execute                         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Memory/Learning                                            │
│  outcome_evaluator → ExperienceStore (JSONL) → PatternMemory        │
│  → 反哺下一轮 HypothesisGenerator 置信度计算                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 P3 Operator 15 阶段数据流

```
GrowthOperatorScheduler.run_daily_cycle(business_date)
  │  幂等门: run_store.has_completed(date) → SKIPPED
  │  run_id = op-<date>-<序号>
  ↓
DailyOperatorPipeline.execute()
  ├─ _reality   → E17.9 agent.run_daily_for_company
  ├─ _audit     → RealityAuditor.audit(company)
  ├─ _approval  → build_contract → ApprovalService.submit
  ├─ _executions→ SafeExecutor.execute (唯一出口)
  ├─ _monitor   → ExecutionMonitor.observe_batch
  ├─ _recovery  → RecoveryEngine.handle (失败 outcome)
  ├─ _liveops   → LiveOpsAgent.analyze_churn + design_winback
  ├─ _strategy_loop → StrategyLoop.run → StrategyGuard
  ├─ _portfolio → PortfolioOptimizer.optimize (只建议)
  ├─ _ceo_report→ build_ceo_report + write_outputs
  └─ _report    → engineering_report.md
  ↓
run_store.record(result) → data/operator/runs.jsonl (append-only)
```

### 4.3 P4 Autonomous Growth 舰队编排

```
CompanyOS.run_daily(business_date, game_ids, roles, approval_present)
  ↓
AutonomousCycle.run(cycle_id)  [11 阶段认知循环]
  ↓ EXECUTE 阶段
LaunchForgeRuntime.run()
  ↓
FleetOrchestrator.run(business_date, games)
  │  shard → 切片 (shard_size=12)
  │  ThreadPoolExecutor 并行 (max_workers=8)
  ↓
_run_one → LaunchForgeRuntime._run_shard
  │  context_factory(game_ids, mode, shard_id)
  │  校验 memory_controller / approval_service / safe_executor
  ↓
DailyOperatorPipeline(context).execute()
  → 返回 {shard_id, stages, aggregates, real_api_called}
```

### 4.4 关键集成点

| 集成点 | 位置 | 说明 |
|--------|------|------|
| RealityGate → ActionExecutor | [run_growth_loop.py:705-737](file:///d:/project_slim/project_slim/scripts/run_growth_loop.py) | 可信度门控注入执行层 |
| Meta Ads → Orchestrator | [run_growth_loop.py:627-664](file:///d:/project_slim/project_slim/scripts/run_growth_loop.py) | 信号生成与喂入 |
| MetricsAdapter 富集 | [run_growth_loop.py:666-681](file:///d:/project_slim/project_slim/scripts/run_growth_loop.py) | 产品侧七域快照 + PlayerProfile |
| DecisionValidator 共享 | [aso_intelligence/agent.py](file:///d:/project_slim/project_slim/src/aso_intelligence/agent.py) | ASO/Revenue/Economy 共享审批管道 |
| GrowthRealityHub → Decision Engine | [growth_reality/agent.py](file:///d:/project_slim/project_slim/src/growth_reality/agent.py) | CompanySnapshot + RealityScore |
| ExperienceStore 反哺 | [outcome_evaluator.py](file:///d:/project_slim/project_slim/scripts/outcome_evaluator.py) | 经验回写 → HypothesisGenerator 置信度增强 |

---

## 5. 关键类与函数说明

### 5.1 Growth Loop V2 核心类

| 类名 | 文件:行 | 职责 |
|------|---------|------|
| `GrowthLoopOrchestrator` | [growth_loop_orchestrator.py:152](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py) | 三阶段主循环编排 |
| `CycleResult` | [growth_loop_orchestrator.py:84](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py) | 单轮结果（含 V2 统计） |
| `DiagnosticEngine` | [diagnostic_engine.py:172](file:///d:/project_slim/project_slim/scripts/diagnostic_engine.py) | 根因诊断决策树 |
| `HypothesisGenerator` | [hypothesis_generator.py:228](file:///d:/project_slim/project_slim/scripts/hypothesis_generator.py) | 可验证增长假设生成 |
| `GrowthHypothesis` | [hypothesis_generator.py:152](file:///d:/project_slim/project_slim/scripts/hypothesis_generator.py) | 假设数据模型（含 is_actionable） |
| `StrategySelector` | [strategy_selector.py:183](file:///d:/project_slim/project_slim/scripts/strategy_selector.py) | 策略类型 + 执行强度选择 |
| `GrowthStrategy` | [strategy_selector.py:92](file:///d:/project_slim/project_slim/scripts/strategy_selector.py) | 策略数据模型 |
| `ActionPlanner` | [action_planner.py:176](file:///d:/project_slim/project_slim/scripts/action_planner.py) | 策略 → ExecutionAction |
| `ExecutionAction` | [action_planner.py:82](file:///d:/project_slim/project_slim/scripts/action_planner.py) | 统一执行动作格式 |
| `ActionExecutor` | [action_executor.py:402](file:///d:/project_slim/project_slim/scripts/action_executor.py) | 状态机执行器 |
| `SafetyGate` | [action_executor.py:308](file:///d:/project_slim/project_slim/scripts/action_executor.py) | 安全门控 |
| `OutcomeEvaluator` | [outcome_evaluator.py:176](file:///d:/project_slim/project_slim/scripts/outcome_evaluator.py) | 结果评估 + 经验回写 |
| `LoopPersistence` | [loop_persistence.py:88](file:///d:/project_slim/project_slim/scripts/loop_persistence.py) | 4 文件持久化管理 |
| `PendingEvaluation` | [pending_evaluation.py:63](file:///d:/project_slim/project_slim/scripts/pending_evaluation.py) | 待评估队列项 |
| `MetaAdsPlatformAdapter` | [meta_ads_adapter.py:27](file:///d:/project_slim/project_slim/scripts/meta_ads_adapter.py) | Meta Ads 真实 API 适配器 |
| `MetricsAdapter` | [metrics_adapter.py:69](file:///d:/project_slim/project_slim/scripts/metrics_adapter.py) | 多源指标富集 |

### 5.2 P2 执行层关键类

| 类名 | 文件:行 | 职责 |
|------|---------|------|
| `ExecutionContract` | [contracts.py:37](file:///d:/project_slim/project_slim/src/execution/contracts.py) | 不可变执行合同 |
| `ExecutionIntent` | [models.py:86](file:///d:/project_slim/project_slim/src/execution/models.py) | 决策→执行意图 |
| `ApprovalPolicy` | [approval/policy.py:122](file:///d:/project_slim/project_slim/src/execution/approval/policy.py) | V2 三级分级策略 |
| `V2ActionExecutor` | [approval/v2_executor.py:85](file:///d:/project_slim/project_slim/src/execution/approval/v2_executor.py) | V2 集成执行器 |
| `BudgetWindowTracker` | [approval/budget_window.py:101](file:///d:/project_slim/project_slim/src/execution/approval/budget_window.py) | 日累计预算追踪 |
| `DryRunVerifier` | [approval/dry_run_verifier.py:62](file:///d:/project_slim/project_slim/src/execution/approval/dry_run_verifier.py) | Level 1 dry_run 验证 |
| `ApprovalRequest` | [approval/models.py:80](file:///d:/project_slim/project_slim/src/execution/approval/models.py) | 审批请求 |
| `ExecutionAuthorization` | [approval/models.py:171](file:///d:/project_slim/project_slim/src/execution/approval/models.py) | 授权令牌（24h TTL） |

### 5.3 现实层关键类

| 类名 | 文件:行 | 职责 |
|------|---------|------|
| `GrowthRealityHub` | [growth_reality/agent.py:23](file:///d:/project_slim/project_slim/src/growth_reality/agent.py) | 数据大脑编排入口 |
| `GrowthRealitySnapshot` | [growth_reality/models.py](file:///d:/project_slim/project_slim/src/growth_reality/models.py) | 单游戏五域 Fact 快照 |
| `CompanySnapshot` | [growth_reality/snapshot.py](file:///d:/project_slim/project_slim/src/growth_reality/snapshot.py) | 公司级聚合快照 |
| `RealityAuditor` | [validation/auditor.py:34](file:///d:/project_slim/project_slim/src/growth_reality/validation/auditor.py) | 全链路审计编排 |
| `RealityGate` | [validation/gate.py:36](file:///d:/project_slim/project_slim/src/growth_reality/validation/gate.py) | 决策门控（<0.5 BLOCKED） |
| `ConfidenceScorer` | [validation/confidence.py](file:///d:/project_slim/project_slim/src/growth_reality/validation/confidence.py) | 三维可信分计算 |
| `ThinkingDataReality` | [thinkingdata_reality.py:51](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/reality/thinkingdata_reality.py) | TD 玩家行为门面层 |

### 5.4 P3/P4 关键类

| 类名 | 文件:行 | 职责 |
|------|---------|------|
| `DailyOperatorPipeline` | [operator/pipeline.py:71](file:///d:/project_slim/project_slim/src/operator/pipeline.py) | 15 阶段编排器 |
| `OperatorContext` | [operator/context.py:39](file:///d:/project_slim/project_slim/src/operator/context.py) | 依赖装配 |
| `GrowthOperatorScheduler` | [operator/scheduler.py:26](file:///d:/project_slim/project_slim/src/operator/scheduler.py) | 幂等调度入口 |
| `CEODailyReport` | [operator/report/models.py:204](file:///d:/project_slim/project_slim/src/operator/report/models.py) | CEO 日报模型 |
| `StrategyLoop` | [operator/strategy/loop.py:51](file:///d:/project_slim/project_slim/src/operator/strategy/loop.py) | 策略反馈控制器 |
| `AutonomousCycle` | [autonomous_growth/cycle.py:80](file:///d:/project_slim/project_slim/src/autonomous_growth/cycle.py) | 11 阶段认知循环 |
| `FleetOrchestrator` | [autonomous_growth/fleet.py:62](file:///d:/project_slim/project_slim/src/autonomous_growth/fleet.py) | 分片并行编排 |
| `AutonomousGrowthAgent` | [autonomous_growth/agent.py:10](file:///d:/project_slim/project_slim/src/autonomous_growth/agent.py) | 安全外壳（熔断器+配额门） |
| `MultiAgentGovernor` | [autonomous_growth/multi_agent.py:30](file:///d:/project_slim/project_slim/src/autonomous_growth/multi_agent.py) | 多 Agent 提案仲裁 |
| `ProductionReadinessGate` | [autonomous_growth/readiness.py:10](file:///d:/project_slim/project_slim/src/autonomous_growth/readiness.py) | 启动就绪门 |

### 5.5 关键函数

| 函数 | 文件:行 | 职责 |
|------|---------|------|
| `build_contract()` | [contracts.py:102](file:///d:/project_slim/project_slim/src/execution/contracts.py) | 端到端打包执行合同 |
| `run_cycle()` | [growth_loop_orchestrator.py:485](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py) | Orchestrator 主循环入口 |
| `_execute_via_v2()` | [growth_loop_orchestrator.py:332](file:///d:/project_slim/project_slim/scripts/growth_loop_orchestrator.py) | V2 三级执行路径 |
| `build_company_snapshot()` | [growth_reality/snapshot.py](file:///d:/project_slim/project_slim/src/growth_reality/snapshot.py) | 公司级快照聚合 |
| `build_operator_context()` | [operator/context.py:58](file:///d:/project_slim/project_slim/src/operator/context.py) | P3 依赖装配工厂 |
| `build_growth_operator()` | [operator/__init__.py](file:///d:/project_slim/project_slim/src/operator/__init__.py) | 一键装配入口 |
| `compute_health_score()` | [execution/monitor/health.py:183](file:///d:/project_slim/project_slim/src/execution/monitor/health.py) | 执行健康分计算 |

---

## 6. 依赖关系

### 6.1 模块间依赖图

```
                    ┌─────────────────────┐
                    │ autonomous_growth   │ P4
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ operator            │ P3
                    └──────────┬──────────┘
                               ↓
        ┌──────────────────────┼──────────────────────┐
        ↓                      ↓                      ↓
┌───────────────┐    ┌──────────────────┐    ┌───────────────┐
│ execution     │    │ growth_reality   │    │ ceo_intel     │
│ (P2)          │    │ (E17.1)          │    │ (E17.x)       │
└───────┬───────┘    └────────┬─────────┘    └───────────────┘
        ↓                     ↓
┌───────────────┐    ┌──────────────────┐
│ monetization  │    │ market_ops       │
│ (E13)         │    │ (clients/e11/    │
└───────────────┘    │  workspace)      │
                     └──────────────────┘
```

### 6.2 外部依赖（pyproject.toml）

| 类别 | 依赖 | 版本 | 用途 |
|------|------|------|------|
| **AI/LLM** | openai | >=1.30.0 | OpenAI API（默认 gpt-4.1-mini，支持 `AI_PROVIDER=mock`） |
| **广告 SDK** | google-ads | >=25.1.0 | Google Ads API 接入 |
| **数据科学** | beautifulsoup4 | >=4.12.3 | HTML/XML 解析 |
| **计算机视觉** | opencv-python-headless | >=4.10.0 | Creative DNA 素材分析 |
| **数据库** | sqlalchemy | >=2.0 | SQL ORM |
| **缓存/队列** | redis | >=5.0 | 缓存/队列 |
| **JSON 校验** | jsonschema | >=4.18 | JSONL store 契约层 |
| **加密** | pycryptodome | >=3.20.0 | 加密 |
| **加密** | cryptography | >=42.0 | 加密原语 |
| **JWT** | pyjwt | >=2.8 | 飞书/Google Ads 鉴权 |
| **配置** | pyyaml | >=6.0 | YAML 配置 |
| **HTTP** | requests | >=2.32.3 | HTTP 客户端 |
| **环境** | python-dotenv | >=1.0.1 | 环境变量加载 |
| **测试** | pytest | >=8.0 | 测试框架（dev） |
| **测试覆盖** | pytest-cov | >=5.0 | 覆盖率（dev） |

**Lean 架构原则**：无 FastAPI/Flask 主框架、无 Postgres、无 React（如 [deploy/Dockerfile](file:///d:/project_slim/project_slim/deploy/Dockerfile) 所示）。

### 6.3 运行时集成

| 集成 | 模块 | 凭证 |
|------|------|------|
| Meta Ads | scripts/meta_ads_adapter.py | `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` / `META_API_VERSION` |
| Google Ads | market_ops/clients/google_ads.py | `DEVELOPER_TOKEN` / `CLIENT_ID` / `CLIENT_SECRET` / `REFRESH_TOKEN` |
| ThinkingData | market_ops/clients/thinkingdata.py | `THINKINGDATA_BASE_URL` / `THINKINGDATA_TOKEN` |
| Adjust | market_ops/clients/adjust.py | `ADJUST_API_TOKEN` |
| 飞书 | market_ops/workspace/ | `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / Webhooks |
| OpenAI | market_ops/clients/ai.py | `OPENAI_API_KEY` / `OPENAI_MODEL` |

---

## 7. 项目运行方式

### 7.1 环境准备

```powershell
cd d:\project_slim\project_slim
cp .env.example .env  # 编辑填入凭证
pip install -r requirements/dev.txt
$env:PYTHONIOENCODING='utf-8'  # Windows 必须设置
```

### 7.2 核心运行入口

#### 7.2.1 Growth Loop V2（主闭环）

```powershell
# Dry-run（默认，不调用真实 API，不执行真实动作）
python scripts/run_growth_loop.py --days 7

# 真实执行（调用 Meta Ads API + 执行平台动作）
python scripts/run_growth_loop.py --days 7 --live

# 启用接线 3 指标适配（七域快照富集）
python scripts/run_growth_loop.py --days 7 --enrich-metrics

# 启用接线 3 + IAA 收入归因
python scripts/run_growth_loop.py --days 7 --enrich-metrics --player-app-id com.game.x
```

#### 7.2.2 P3 日运营

```powershell
# 每日运营 13 阶段（恒 DRY_RUN）
python scripts/run_daily_operator.py
```

#### 7.2.3 P4 自治增长

```powershell
# 生产就绪门校验
python -m src.autonomous_growth dry_run
python -m src.autonomous_growth production
```

#### 7.2.4 Closed Loop Runner（Bandit 路线）

```powershell
# 在线策略执行引擎
python scripts/closed_loop_runner.py --dry-run
python scripts/closed_loop_runner.py --live
```

#### 7.2.5 现实审计

```powershell
# P1.7 每日真实审计报告
python scripts/run_reality_audit.py --demo    # 验收绿路
python scripts/run_reality_audit.py            # 生产模式
```

#### 7.2.6 LaunchForge CLI（新游戏脚手架）

```powershell
python cli.py init --name "Word Puzzle 01" --genre word --platform android,ios --ads MAX --analytics Firebase,Adjust
```

生成 `games/<slug>/` 下：product.yaml / monetization.yaml / release.yaml / gamefactory_config.json

### 7.3 E2E 验收

```powershell
# 系统自检（零网络/零凭证）
python system_check.py

# E2E 无人值守验收（9 步完整链路）
python run_e2e_acceptance.py
```

### 7.4 控制中心（FastAPI 工作台）

```powershell
# 启动 workspace API（默认 8000 端口）
python -m market_ops.workspace.app
```

主要端点：
- `/healthz` / `/readyz` — 健康检查
- `/api/dashboard` — 仪表盘
- `/api/loop/scheduler/start` — 启动 Growth Loop 调度器
- `/api/ceo/dashboard` — CEO 决策中心

---

## 8. 测试体系

### 8.1 测试规模

- **测试文件**：280+ 个 `test_*.py` 文件
- **测试用例**：1182+ 个 `def test_`（实际更多）
- **全量回归**：3771 tests passing（2026-08-06 基线）

### 8.2 测试金字塔标记

来自 [tests/conftest_lf.py](file:///d:/project_slim/project_slim/tests/conftest_lf.py)（67 行）：

每个 collected test 恰好获得一个金字塔 marker：
- `unit`（默认）— 单元测试
- `integration` — 集成测试
- `e2e` — 端到端测试
- `security`（可选 domain marker）

规则优先级：显式 marker 不被覆盖 → 目录路径推断 → 名称启发式 → 默认 unit

```powershell
# 度量金字塔
pytest tests/ --collect-only -q -m unit
pytest tests/ --collect-only -q -m integration
pytest tests/ --collect-only -q -m e2e
```

### 8.3 测试文件分类

| 类别 | 代表性测试文件 | 说明 |
|------|---------------|------|
| **growth_loop** | `test_growth_loop_orchestrator.py`（29）、`test_growth_loop_scheduler.py`（37）、`test_loop_persistence.py`（61）、`integration/test_growth_loop_unattended.py`（11） | Growth Loop V2 编排/调度/持久化/闭环 |
| **action_planner** | `test_action_planner.py`（36）、`test_action_executor.py`（38） | 动作规划与执行层 |
| **outcome** | `test_outcome_evaluator.py`（43）、`test_hypothesis_generator.py`（34）、`test_strategy_selector.py`（37）、`test_diagnostic_engine.py`（47） | 诊断/假设/策略/评估全链路 |
| **execution** | `p2_2/`、`p2_3/`、`p2_4/`、`p2_5/`、`p2_6/` | P2 执行层分级测试 |
| **operator** | `p3_1/`、`p3_2/`、`p3_3/`、`p3_3_3/`、`p3_4_*`、`p3_5_*` | P3 运营层全链路 |
| **autonomous_growth** | `test_p4_api.py`、`test_p4_fleet_orchestrator.py`、`test_p4_multi_agent.py`、`test_p4_hardening.py` | P4 自治层 |
| **aso** | `e15_1_1/test_aso_engine.py`、`e16_6_2/test_aso_reality.py` | ASO 引擎/现实 |
| **monetization** | `player_monetization/`、`revenue_optimizer/`、`test_e116*` | 玩家变现与收入优化 |
| **e1xx 系列** | `test_e101~e102_phase*`、`test_e111~e119_*`、`test_e121~e127*`、`test_e131~e137*`、`test_e141~e148*` | E1xx 系列模块单元测试 |

### 8.4 集成测试

[tests/integration/test_growth_loop_unattended.py](file:///d:/project_slim/project_slim/tests/integration/test_growth_loop_unattended.py)（11 个测试，5 个测试类）：

- `TestUnattended24hSimulation` — 24h 模拟 20 动作分级执行（5×L0 + 10×L1 + 5×L2）
- `TestUnattendedV1Compat` — V1 兼容（无 v2_executor 时 V2 统计恒 0）
- `TestUnattendedShadowMode` — Shadow 模式（Level 0 只记 audit 不执行）
- `TestUnattendedBudgetWindow` — 累计窗口溢出升级 Level 2
- `TestUnattendedEndToEnd` — run_cycle 端到端 + intent 映射 + RESUME_CAMPAIGN 回退 V1

### 8.5 运行测试

```powershell
# 全量测试
pytest tests/ -v

# 按标记运行
pytest tests/ -m unit
pytest tests/ -m integration

# 按模块运行
pytest tests/test_growth_loop_orchestrator.py -v
pytest tests/p2_4/ -v

# 带覆盖率
pytest tests/ --cov=src --cov=scripts --cov-report=term-missing
```

---

## 9. 部署与运维

### 9.1 部署形态

#### 9.1.1 根 Dockerfile（3 目标）

来自 [Dockerfile](file:///d:/project_slim/project_slim/Dockerfile)（26 行）：

```dockerfile
# 多阶段构建：base → api / worker / scheduler
# 基于 python:3.12-slim

# api: EXPOSE 8000, HEALTHCHECK /healthz, 启动 market_ops.product.server
# worker: 启动 market_ops.product.doctor --write
# scheduler: 启动 market_ops.cli daily-sync，间隔 60 分钟
```

#### 9.1.2 Lean Container Runtime（deploy/Dockerfile）

来自 [deploy/Dockerfile](file:///d:/project_slim/project_slim/deploy/Dockerfile)（34 行）：

```dockerfile
# Lean Container Runtime（E14.4.1）
# 基于 python:3.13-slim
# 独立 venv /opt/venv
# 三个挂载卷：/app/data/stores / /app/data/checkpoints / /app/credentials
# ENTRYPOINT: deploy/worker.py
# 纯 Python 编排器，无 FastAPI/Postgres/Redis/S3
```

#### 9.1.3 Lean Worker

来自 [deploy/worker.py](file:///d:/project_slim/project_slim/deploy/worker.py)（166 行）：

```powershell
# 裸机运行
python deploy/worker.py --max-concurrent 8 --daily-cycles --once

# 容器运行（支持分片横向扩展）
docker run -e GAMES=witch_merge,puzzle_island deploy/worker
```

装配链：`GameRegistry → GameFactoryOS → RuntimeSupervisor → GameScheduler`

支持分片（`GAMES=slug1,slug2`）横向扩展——50 个游戏可分散到 N 个 worker。

### 9.2 生产安全默认

来自 [PRODUCTION_RUNBOOK.md](file:///d:/project_slim/project_slim/PRODUCTION_RUNBOOK.md)：

```powershell
# 安全默认启动
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

override 强制：
- `FACEBOOK_SANDBOX=true`
- `MARKET_OPS_ALLOW_PLATFORM_WRITES=0`（允许报告/刷新/推荐/审计但禁止广告平台改动）

### 9.3 Release Gate 5 项

1. doctor 不 blocked
2. 数据新鲜度
3. CI 合约套件
4. `/readyz` 返回 200
5. 控制中心无待审批准

### 9.4 启用真实 Meta 写

需验证：
- `campaign_bindings.json` 配置正确
- 设置 3 项 secret：`META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` / `META_API_VERSION`
- `MARKET_OPS_ALLOW_PLATFORM_WRITES=1`
- `FACEBOOK_SANDBOX=false`

### 9.5 事故响应

来自 [PRODUCTION_RUNBOOK.md](file:///d:/project_slim/project_slim/PRODUCTION_RUNBOOK.md)：

1. 先置 `MARKET_OPS_ALLOW_PLATFORM_WRITES=0`
2. 保留 cycle ID 和 task ID
3. 执行回滚计划
4. 保留审计与 memory

### 9.6 SLO 监控

来自 [docs/production_runbook.md](file:///d:/project_slim/project_slim/docs/production_runbook.md)：

| SLO | 阈值 |
|-----|------|
| 成功率 | ≥ 99% |
| 失败分片 | = 0 |
| 平均循环延迟 | ≤ 300s |
| 队列深度 | ≤ 1000 |

### 9.7 受控发布流程

来自 [docs/production_runbook.md](file:///d:/project_slim/project_slim/docs/production_runbook.md)：

1. 1 游戏 dry-run 24h
2. 单动作批准
3. 验证审计/幂等/回滚快照
4. 监控间隔观察
5. 逐步放量

### 9.8 关键数据目录

| 路径 | 用途 |
|------|------|
| `data/growth_reality/<game_id>.jsonl` | 逐游戏现实快照时序 |
| `data/operator/runs.jsonl` | P3 运行状态 |
| `data/ceo/audit/` | 审批与决策审计 |
| `data/p4/cycle_state.jsonl` | P4 循环状态 |
| `data/p4/durable_queue.jsonl` | 持久化工作队列 |
| `data/liveops/campaigns.jsonl` | LiveOps 活动记录 |
| `outputs/growth/` | Growth Loop 报告 |
| `outputs/approval_audit/` | V2 审批审计日志 |
| `reports/daily/` | 每日报告 |

---

## 附录：关键文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 架构基线（FROZEN） | [specs/E9_ARCHITECTURE_V1.md](file:///d:/project_slim/project_slim/specs/E9_ARCHITECTURE_V1.md) | 4 层模型 + 5 大契约 |
| 版本路线图 | [specs/E9_ROADMAP.md](file:///d:/project_slim/project_slim/specs/E9_ROADMAP.md) | E9.4-E9.9 + E10 VISION |
| 架构总览 | [docs/architecture.md](file:///d:/project_slim/project_slim/docs/architecture.md) | 5 层架构 + 核心原则 |
| 生产路线图 | [docs/production_roadmap.md](file:///d:/project_slim/project_slim/docs/production_roadmap.md) | P4 COMPLETE |
| 生产 Runbook | [docs/production_runbook.md](file:///d:/project_slim/project_slim/docs/production_runbook.md) | LaunchForge runbook |
| Market Ops Runbook | [PRODUCTION_RUNBOOK.md](file:///d:/project_slim/project_slim/PRODUCTION_RUNBOOK.md) | Market Ops runbook |
| Agent 开发规范 | [docs/agent-guide.md](file:///d:/project_slim/project_slim/docs/agent-guide.md) | models→engine→agent 三文件模式 |
| P4 契约 | [docs/p4_contract.md](file:///d:/project_slim/project_slim/docs/p4_contract.md) | 10 条冻结规则 |
| 产品边界 | [ULTIMATE_PRODUCT_TARGET.md](file:///d:/project_slim/project_slim/ULTIMATE_PRODUCT_TARGET.md) | 6 条不可协商边界 + 8 项 DoD |
| 部署指南 | [docs/deployment.md](file:///d:/project_slim/project_slim/docs/deployment.md) | 本地/Docker/生产 Checklist |
| 测试指南 | [docs/testing.md](file:///d:/project_slim/project_slim/docs/testing.md) | 测试金字塔 |
| 安全规范 | [docs/security.md](file:///d:/project_slim/project_slim/docs/security.md) | 权限/密钥/审计 |

---

*本文档由代码库自动梳理生成，如有疑问请对照源码行号引用核实。*
