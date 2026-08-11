# CEO Agent 统一调度 Spec（AI Game Studio OS Phase 1）

> 状态：定义中（实现前锁定）
> 优先级：P0（AI Game Studio OS Phase 1 核心任务）
> 目标：让 CEO Agent 真正能调度全公司各部门，workspace UI 可触达

---

## 1. 定位（不重新发明轮子）

CEO Agent 统一调度 **不是** 新建一个 CEO 引擎，也不是合并三套 CEO 实现。它是将**已存在但仅 CLI 可达的 CEO 每日经营闭环**暴露为 workspace HTTP 端点，让 CEO 真正能被调度。

```
当前割裂现状（必须解决）：

┌──────────────────────────────────────┐
│ 链路 A：UA Growth Loop               │
│ /api/loop/trigger → GrowthLoop       │
│ 仅 UA 域，creative 级自动化          │
│ ✅ HTTP 可达，workspace 可触发        │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ 链路 B：CEO Daily Operator           │
│ CLI → DailyOperatorPipeline (13阶段) │
│ 全公司多域（UA/Creative/Economy/...） │
│ ❌ 仅 CLI，workspace 不可达           │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ 链路 C：v9_company ceo_agent         │
│ 硬编码 mock，零外部引用              │
│ ❌ 死代码                             │
└──────────────────────────────────────┘
```

统一职责一句话：**将链路 B（DailyOperatorPipeline）暴露为 HTTP 端点 `/api/ceo/daily-run`，让 workspace UI 能触发 CEO 每日例会，CEO 产出的决策和动作回流 Dashboard。**

纪律红线（继承全库 + memory 约束）：
- **禁止**新增算法层或新版本，只做薄层 HTTP 包装
- **禁止**修改 DailyOperatorPipeline 内部逻辑，只调用 `build_growth_operator` + `run_daily_cycle`
- **禁止**物理删除 v9_company（本次仅标记 deprecated，后续清理）
- **必须**保留幂等门（当日已跑过则 SKIPPED）
- **必须**默认 DRY_RUN，`real_api_called=True` 时告警

---

## 2. 方案设计

### 2.1 新增 HTTP 端点

```
POST /api/ceo/daily-run
```

请求体：
```python
class CEODailyRunRequest(BaseModel):
    business_date: str = ""        # 默认今天
    force: bool = False            # 越过幂等门重跑
    use_real_data: bool = False    # 生产模式（四真实源），默认 demo
```

响应体：
```python
class CEODailyRunResponse(BaseModel):
    status: str           # completed / partial / skipped / failed
    run_id: str
    business_date: str
    stages: list[dict]    # 13 阶段结果
    decisions: dict       # 决策统计 {EXECUTE: N, APPROVE: N, BLOCK: N}
    executions: dict      # 执行统计 {success: N, failed: N, skipped: N}
    errors: list[str]
    report_id: str        # CEO 决策单 ID
    real_api_called: bool
    summary: dict         # 聚合摘要
    duration_seconds: float
```

### 2.2 前端 Dashboard 变更

新增"CEO 每日例会"触发区域：
- 按钮触发 `POST /api/ceo/daily-run`
- 展示 13 阶段执行进度（每阶段 ✅/⏭️/❌）
- 展示决策统计（EXECUTE/APPROVE/BLOCK 分布）
- 展示执行统计（成功/失败/跳过）
- 展示 CEO 决策单 report_id（可跳转查看）

### 2.3 与现有 /api/loop/trigger 的关系

| 维度 | /api/loop/trigger | /api/ceo/daily-run |
|------|-------------------|---------------------|
| 定位 | UA 域 creative 级自动化 | 全公司每日经营例会 |
| 链路 | 链路 A (GrowthLoop) | 链路 B (DailyOperatorPipeline) |
| 频率 | 高频（每数小时一次） | 低频（每日一次） |
| 域 | 仅 UA | 多域（UA/Creative/Economy/Product） |
| 数据目录 | data/growth_loop/ | data/ceo/ + reports/daily/ |

两者**并存不合并**：UA 自动化保持高频独立运行，CEO 例会每日一次统筹全局。

---

## 3. 实现范围

### 3.1 后端（src/market_ops/workspace/app.py）

新增端点 `POST /api/ceo/daily-run`：
1. 构造 `build_growth_operator`（复用 `scripts/run_daily_operator.py` 的 demo/prod 构造逻辑）
2. 调用 `scheduler.run_daily_cycle(business_date, force)`
3. 将 `OperatorRunResult.to_dict()` 包装为 HTTP 响应
4. 异常兜底：返回 500 + 错误详情

### 3.2 前端（workspace/src/）

- `lib/api.ts`：新增 `CEODailyRunResponse` 类型 + `api.triggerCEODailyRun()` 方法
- `app/page.tsx`：Dashboard 新增"CEO 每日例会"触发区 + 结果展示

### 3.3 不在本次范围

- ❌ 不修改 DailyOperatorPipeline 内部逻辑
- ❌ 不合并链路 A 和链路 B 的数据模型
- ❌ 不实现 CEO 主动派单语义（v9_company ExecutiveOrchestrator 重写）
- ❌ 不物理删除 v9_company
- ❌ 不统一 ExperienceStore 和 OperatorMemory

---

## 4. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| §4.1 | `POST /api/ceo/daily-run` 返回 200 + 完整 stages | HTTP 请求验证 |
| §4.2 | 默认 demo 模式可离线跑（不依赖真实 API） | 无 META_ACCESS_TOKEN 时跑通 |
| §4.3 | 幂等门生效：同日重复触发返回 SKIPPED | 连续两次调用验证 |
| §4.4 | force=true 可越过幂等门 | 验证 force 参数 |
| §4.5 | 响应包含 13 阶段结果 | 验证 stages 数组 |
| §4.6 | 响应包含 decisions/executions 统计 | 验证决策和执行统计 |
| §4.7 | 前端 Dashboard 可触发并展示结果 | UI 验证 |
| §4.8 | 现有 /api/loop/trigger 不受影响 | 回归测试 |
| §4.9 | 单元测试覆盖（≥10 个用例） | pytest 验证 |

---

## 5. 依赖扫描（已逐项核对）

- [src/operator/__init__.py](file:///d:/project_slim/project_slim/src/operator/__init__.py) `build_growth_operator(**kwargs) -> GrowthOperatorScheduler`
- [src/operator/scheduler.py](file:///d:/project_slim/project_slim/src/operator/scheduler.py) `run_daily_cycle(business_date, force) -> OperatorRunResult`
- [src/operator/models.py](file:///d:/project_slim/project_slim/src/operator/models.py) `OperatorRunResult.to_dict()`
- [scripts/run_daily_operator.py](file:///d:/project_slim/project_slim/scripts/run_daily_operator.py) `build_demo_scheduler` / `build_prod_scheduler`
- [src/market_ops/workspace/app.py](file:///d:/project_slim/project_slim/src/market_ops/workspace/app.py) 现有 `/api/loop/trigger` 端点（参考模式）
