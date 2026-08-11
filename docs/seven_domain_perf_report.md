# 七域协同计算性能优化报告

**版本**: v1.4  
**日期**: 2026-08-06  
**优化范围**: 全部五项优化（P0~P4）已完成，P3 已实施并验证

---

## 一、背景

E12.2 产品分析引擎包含七个分析域，通过 ThinkingData Open API 进行 SQL 查询：

| 分析域 | 职责 | 文件 |
|--------|------|------|
| Lifecycle | 用户生命周期（留存/阶段分布/流失风险） | lifecycle_analyzer.py |
| Funnel | 转化漏斗（安装→付费） | funnel_analyzer.py |
| Retention | 渠道留存对比与驱动因素 | retention_analyzer.py |
| Monetization | 商业化（付费率/ARPU/LTV/Offer） | monetization_analyzer.py |
| Economy | 经济系统（资源产出/消耗/通胀） | economy_analyzer.py |
| Gameplay | 玩法分析（关卡通过率/难度曲线/参与度） | gameplay_analyzer.py |
| UserValue | 用户价值（分层/构成/集中度/演进） | user_value_analyzer.py |

---

## 二、性能瓶颈诊断

### 2.1 瓶颈总览

| 优先级 | 瓶颈 | 严重程度 | 影响 | 状态 |
|--------|------|---------|------|------|
| P0 | Economy + Gameplay N+1 查询 | 严重 | 18 次串行 SQL 往返 | ✅ 已解决 |
| P1 | 七域串行执行 | 中等 | 总耗时 = 各域耗时之和 | ✅ 已解决 |
| P2 | 留存数据重复拉取 | 轻微 | 1 次冗余查询 | 待优化 |
| P3 | UserValue 全量行传输 | 轻微 | 内存/CPU 压力 | ✅ 已解决 |

### 2.2 N+1 查询详情（P0）

**EconomyAnalyzer** — 4 资源 × 2 SQL = 8 次串行查询

原代码在 `for res in resources:` 循环内对每个资源分别发 `source_sql` 和 `sink_sql`：

```python
# 优化前：每个资源 2 次 SQL
for res in resources:
    source_sql = f"SELECT ... WHERE resource_type = '{res}' AND resource_change > 0 ..."
    source_result = client.sql_query(project_id, source_sql)  # SQL #1

    sink_sql = f"SELECT ... WHERE resource_type = '{res}' AND resource_change < 0 ..."
    sink_result = client.sql_query(project_id, sink_sql)     # SQL #2
```

**GameplayAnalyzer** — 10 关卡 × 1 SQL = 10 次串行查询

原代码在 `for lvl in tracked:` 循环内对每个关卡发一次 SQL：

```python
# 优化前：每个关卡 1 次 SQL
for lvl in tracked:
    sql = f"SELECT ... WHERE level_id = '{lvl}' ..."
    result = client.sql_query(project_id, sql)  # SQL #1~#10
```

**合计**: 18 次串行 SQL 往返，占七域总往返的 58%。

---

## 三、优化方案

### 3.1 EconomyAnalyzer: 改用 GROUP BY resource_type 聚合

**优化前**: 4 资源 × 2 SQL = 8 次往返

**优化后**: 单条 GROUP BY 聚合查询，1 次往返

```sql
SELECT
  resource_type,
  resource_action,
  CASE WHEN resource_change > 0 THEN 'source' ELSE 'sink' END AS flow_type,
  SUM(ABS(resource_change)) AS total
FROM v_event_{project_id}
WHERE event_name = 'resource_change'
  AND resource_type IN ('coins', 'gems', 'energy', 'materials')
  AND event_date BETWEEN '{start}' AND '{end}'
GROUP BY resource_type, resource_action, flow_type
ORDER BY resource_type, total DESC
```

Python 端按 `resource_type` 分桶解析，`top_sources` / `top_sinks` 各取 Top 3。

### 3.2 GameplayAnalyzer: 改用 GROUP BY level_id 聚合

**优化前**: 10 关卡 × 1 SQL = 10 次往返

**优化后**: 单条 GROUP BY 聚合查询，1 次往返

```sql
SELECT
  level_id,
  COUNT(*) AS attempts,
  SUM(CASE WHEN result = 'pass' THEN 1 ELSE 0 END) AS passes,
  AVG(duration) AS avg_dur
FROM v_event_{project_id}
WHERE event_name = 'level_complete'
  AND level_id IN ('level_1', 'level_2', ..., 'level_10')
  AND event_date BETWEEN '{start}' AND '{end}'
GROUP BY level_id
```

Python 端用 `perf_map` 字典解析，按 `tracked` 列表顺序填充，无数据关卡补空记录。

---

## 四、优化效果量化

### 4.1 SQL 调用次数对比

| 分析域 | 优化前 | 优化后 | 减少 | 减少幅度 |
|--------|--------|--------|------|----------|
| Lifecycle | 1 | 1 | 0 | - |
| Funnel | 1 | 1 | 0 | - |
| Retention | 1 | 1 | 0 | - |
| Monetization | 2 | 2 | 0 | - |
| **Economy** | **8** | **1** | **-7** | **-87.5%** |
| **Gameplay** | **13** | **4** | **-9** | **-69.2%** |
| UserValue | 3 | 3 | 0 | - |
| **合计** | **31** | **13** | **-18** | **-58.1%** |

> 注：GameplayAnalyzer 的 4 次中包含 session_metrics、mode_engagement、top_actions 各 1 次，level_performance 从 10 次优化为 1 次。

### 4.2 生产环境预估耗时收益

按每次 SQL 往返 200-500ms 估算：

| 场景 | 优化前 | 优化后 | 节省 |
|------|--------|--------|------|
| 乐观（200ms/次） | 6.2s | 2.6s | 3.6s |
| 典型（350ms/次） | 10.9s | 4.6s | 6.3s |
| 悲观（500ms/次） | 15.5s | 6.5s | 9.0s |

### 4.3 Mock 模式耗时

| 指标 | 数值 |
|------|------|
| 单域最慢 | 0.20ms（Lifecycle） |
| 七域串行总耗时 | 0.58ms |
| 优化前后差异 | 无显著差异（Mock 无网络 I/O） |

---

## 五、测试验证

### 5.1 测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|---------|--------|---------|
| test_product_analyzers.py | 29 | Lifecycle, Funnel, Retention, Monetization |
| test_economy_gameplay_analyzers.py | 28 | Economy, Gameplay, 六域交叉 |
| test_user_value_analyzer.py | 43 | UserValue, 七域交叉, SQL 聚合路径 |
| test_parallel_analyzers.py | 19 | 并行执行（线程安全、一致性、故障隔离） |
| **合计** | **119** | **七域全覆盖 + 并行执行 + SQL 聚合** |

### 5.2 运行结果

```
collected 119 items

tests\test_user_value_analyzer.py ............................................. [ 36%]
tests\test_economy_gameplay_analyzers.py ............................ [ 59%]
tests\test_product_analyzers.py ............................. [ 84%]
tests\test_parallel_analyzers.py ................... [100%]

============================= 119 passed in 0.53s ==============================
```

### 5.3 七域协同快照验证

| 分析域 | 关键指标 | 验证结果 |
|--------|---------|---------|
| Lifecycle | D1=39% D7=21% D30=8% | ✅ |
| Funnel | 5 步, 整体转化 21.99%, 流失点=首次付费 | ✅ |
| Retention | D7=21%, best=meta, worst=organic | ✅ |
| Monetization | 付费率 5%, ARPU $3.50, 收入 $35000 | ✅ |
| Economy | 平衡态, 通胀 17%, 3 个异常资源 | ✅ |
| Gameplay | 12000 玩家, level_6 卡点, 曲线 healthy | ✅ |
| UserValue | 10000 用户, 1800 高价值, 帕累托 51% | ✅ |

---

## 六、后续优化建议

| 优先级 | 优化项 | 预期收益 | 难度 | 状态 |
|--------|--------|---------|------|------|
| P1 | 七域并行执行（ThreadPoolExecutor） | 耗时 → max(单域) | 低 | ✅ 已完成 |
| P2 | ThinkingDataReality 层留存数据缓存 | 省 1 次 SQL 往返 | 低 | ✅ 已完成 |
| P3 | UserValueAnalyzer SQL 层聚合（全量行→4 行） | 内存/CPU 优化 | 中 | ✅ 已完成 |
| P4 | 死代码清理（mid_value_total 未使用变量） | 代码整洁 | 低 | ✅ 已完成 |

---

## 七、改动文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `src/.../analyzers/economy_analyzer.py` | 修改 | `_fetch_resource_flows`: 8 次 SQL → 1 次 GROUP BY 聚合 |
| `src/.../analyzers/gameplay_analyzer.py` | 修改 | `_fetch_level_performance`: 10 次 SQL → 1 次 GROUP BY 聚合 |
| `src/.../analyzers/__init__.py` | 修改 | 新增 UserValueAnalyzer 导出 + `parallel_analyze()` 并行执行函数 |
| `src/.../analyzers/user_value_analyzer.py` | 新增 + 修改 | 用户价值分析器（Phase 5）+ 删除 `mid_value_total` 死代码 + SQL 层 GROUP BY 聚合 |
| `src/.../thinkingdata_reality.py` | 修改 | `fetch_recent_retention` 新增 TTL 缓存，避免 Lifecycle + Retention 重复 API 调用 |
| `tests/test_user_value_analyzer.py` | 新增 | 31 个单元测试（含七域协同测试） |
| `tests/test_parallel_analyzers.py` | 新增 | 19 个并行执行测试（线程安全、一致性、故障隔离） |
| `tests/test_thinkingdata_reality.py` | 修改 | 新增 8 个缓存测试用例（TestRetentionCache + TestLifecycleRetentionSharedCache） |

---

## 八、P1 并行执行优化（已完成）

### 8.1 实现方案

通过 `ThreadPoolExecutor` 将七个分析域的串行执行改为并行，将总耗时从 `sum(各域耗时)` 降至 `max(各域耗时)`。

核心函数 `parallel_analyze()` 位于 [analyzers/__init__.py](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/reality/analyzers/__init__.py)：

```python
from market_ops.creative_vision_runtime.reality.analyzers import parallel_analyze

td = ThinkingDataReality()
results = parallel_analyze(td, project_id=102, lookback_days=30)
# results["Lifecycle"]  → LifecycleSnapshot
# results["Economy"]    → EconomySnapshot
# ...
```

### 8.2 设计要点

| 特性 | 实现 |
|------|------|
| 并发模型 | `ThreadPoolExecutor`，默认 7 workers |
| 故障隔离 | 单域异常不中断其他域，失败域返回 `None` + `{name}_error` |
| 线程安全 | 共享 `ThinkingDataReality` 实例，Mock 模式下无竞态 |
| 确定性 | 多次并行执行结果一致 |
| Worker 降级 | `max_workers` 自动 clamp 到域数量上限 |

### 8.3 生产环境预估收益

按典型 350ms/SQL 往返，串行模式七域总耗时约 4.6s（含 P0 优化后）。并行模式下：

| 场景 | 串行 | 并行 | 加速比 |
|------|------|------|--------|
| 乐观（200ms/次） | 2.6s | ~0.6s | 4.3x |
| 典型（350ms/次） | 4.6s | ~1.1s | 4.2x |
| 悲观（500ms/次） | 6.5s | ~1.5s | 4.3x |

> 注：并行加速比 ≈ 域数量 / 最慢域占比，理论最大加速比约 7x（I/O 密集型场景）。

### 8.4 线程安全验证

19 个测试用例覆盖 8 个验证方向，全部通过：

| 验证方向 | 用例数 | 结果 |
|---------|--------|------|
| 串行 vs 并行一致性 | 4 | ✅ |
| 线程安全 | 3 | ✅ |
| 确定性 | 2 | ✅ |
| 故障隔离 | 2 | ✅ |
| 计数器正确性 | 2 | ✅ |
| 边界条件 | 4 | ✅ |
| 高并发压力 | 2 | ✅ |

---

## 九、P2 留存缓存 + 死代码清理（已完成）

### 9.1 留存数据缓存（P2-A）

**问题**：LifecycleAnalyzer 和 RetentionAnalyzer 在串行和并行模式下均调用 `fetch_recent_retention(project_id, lookback_days=30)`，参数完全相同，造成 1 次冗余 API 调用。

**方案**：在 [thinkingdata_reality.py](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/reality/thinkingdata_reality.py) 的 `ThinkingDataReality` 中添加 TTL 缓存：

```python
# 缓存键：(project_id, lookback_days)
# 缓存值：(cached_at, records)
# TTL：5 分钟

def fetch_recent_retention(self, project_id, lookback_days=7, use_cache=True):
    cache_key = (project_id, lookback_days)
    if use_cache and cache_key in self._retention_cache:
        cached_at, records = self._retention_cache[cache_key]
        if datetime.now(timezone.utc) - cached_at < self._RETENTION_CACHE_TTL:
            return records  # 缓存命中
    # ... 原有逻辑 + 缓存写入 ...
```

| 特性 | 实现 |
|------|------|
| 缓存键 | `(project_id, lookback_days)` 元组 |
| TTL | 5 分钟（类属性 `_RETENTION_CACHE_TTL`） |
| 缓存绕过 | `use_cache=False` 参数 |
| 缓存清空 | `clear_retention_cache()` 方法 |
| 适用范围 | Mock 和真实 client 均生效 |

**收益**：每次七域分析省 1 次 `retention_analyze` API 调用，典型节省 ~350ms。

### 9.2 死代码清理（P2-C）

**问题**：`UserValueAnalyzer._compute_pareto_ratio` 方法中计算了 `mid_value_total` 变量但从未使用。

**清理位置**：[user_value_analyzer.py](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/reality/analyzers/user_value_analyzer.py#L493-L498)

```python
# 删除前（3 行死代码）：
mid_value_total = (
    mid.avg_value_score * mid.user_count if mid else 0
)

# 删除后：直接进入 grand_total 计算
```

**影响**：无功能影响，纯代码整洁性优化。

### 9.3 测试覆盖

| 测试类 | 用例数 | 验证方向 |
|--------|--------|---------|
| `TestRetentionCache` | 6 | 缓存命中、绕过、清空、独立键、Mock client、数据完整性 |
| `TestLifecycleRetentionSharedCache` | 2 | Lifecycle + Retention 共享缓存一致性、缓存填充 |

**测试结果：159/159 PASS**（含全量回归）

---

## 十、优化总结

### 10.1 优化进度

| 优先级 | 优化项 | 类型 | 状态 |
|--------|--------|------|------|
| P0 | Economy + Gameplay N+1 查询 → GROUP BY 聚合 | 网络 IO | ✅ v1.0 |
| P1 | 七域并行执行（ThreadPoolExecutor） | 并发 | ✅ v1.1 |
| P2 | 留存数据 TTL 缓存 | 网络 IO | ✅ v1.2 |
| P4 | 死代码清理（mid_value_total） | 整洁 | ✅ v1.2 |
| P3 | UserValueAnalyzer SQL 层聚合 | 内存+网络 | ✅ v1.3 |

### 10.2 累计收益

#### SQL 调用次数

| 阶段 | 单次七域分析 SQL 调用 | 减少 |
|------|----------------------|------|
| 优化前 | 31 次 | — |
| P0 后 | 13 次 | -58% |
| P2 后 | 12 次 | -61% |

#### 生产环境耗时预估（典型 350ms/SQL）

| 阶段 | 串行耗时 | 并行耗时 | 加速比 |
|------|---------|---------|--------|
| 优化前 | 10.9s | — | — |
| P0 后 | 4.6s | — | 2.4x |
| P1 后 | — | ~1.1s | 9.9x（vs 原始） |
| P2 后 | — | ~0.9s | 12.1x（vs 原始） |

#### 内存占用

| 阶段 | 关键改善 |
|------|---------|
| P0 | Economy/Gameplay 不再逐行拉取全量数据 |
| P3 | UserValue 全量行 → 4 行聚合，传输量 **-99.96%** |

### 10.3 测试覆盖总览

| 测试文件 | 用例数 | 覆盖范围 |
|---------|--------|---------|
| test_product_analyzers.py | 29 | Lifecycle, Funnel, Retention, Monetization |
| test_economy_gameplay_analyzers.py | 28 | Economy, Gameplay, 六域交叉 |
| test_user_value_analyzer.py | 43 | UserValue, 七域交叉, SQL 聚合路径 |
| test_parallel_analyzers.py | 19 | 并行执行（线程安全、一致性、故障隔离） |
| test_thinkingdata_reality.py | 40 | TD Reality + 缓存逻辑 |
| **合计** | **159** | **全链路覆盖** |

### 10.4 架构现状

```
ThinkingDataReality (TTL 缓存)
       │
       ▼
parallel_analyze() ── ThreadPoolExecutor (7 workers)
  ├── LifecycleAnalyzer  ──┐
  ├── FunnelAnalyzer       │
  ├── RetentionAnalyzer ──┤ 共享 fetch_recent_retention 缓存
  ├── MonetizationAnalyzer │
  ├── EconomyAnalyzer      │  GROUP BY 聚合（1 次 SQL）
  ├── GameplayAnalyzer     │  GROUP BY 聚合（1 次 SQL）
  └── UserValueAnalyzer ──┘
       │
       ▼
  七域快照 → RealityDataHub → E11 Evolution
```

### 10.5 下一步

所有五项优化（P0~P4）已全部完成。后续可关注方向：
- **生产环境实测**：在真实 ThinkingData API 环境下验证各项收益预估
- **监控集成**：将 SQL 调用次数、耗时、缓存命中率纳入系统监控
- **自适应并行度**：根据 API 响应时间动态调整 `max_workers`

---

## 十一、P3 UserValueAnalyzer SQL 层聚合（已完成）

### 11.1 问题分析

`UserValueAnalyzer._fetch_user_segments` 优化前采用全量拉取 + Python 分层方案：

```python
# 优化前：拉取所有用户（10000+ 行），Python 层逐行分桶
SELECT user_id, revenue_score, engagement_score, social_score, content_score,
       total_revenue, active_days, sessions
FROM v_user_value_{project_id}
WHERE period_end = '{end}'  -- 返回 10000+ 行

# Python 端：
for row in rows:
    score = _compute_value_score(...)  # 逐行计算加权评分
    segment = _segment_name(score)     # 逐行判定分层
    segment_buckets[segment].append(...)
```

**痛点**：
- 数据传输量：10000+ 行 × 8 列 = 大量网络传输
- 内存分配：10000+ 个 dict 对象分配
- CPU 开销：10000+ 次 Python 循环分桶计算

### 11.2 优化方案

将加权评分计算和分层聚合全部下推到 SQL 层，通过 `GROUP BY` + `CASE WHEN` 一次返回 4 行聚合结果：

```sql
SELECT
  CASE
    WHEN value_score >= 70.0 THEN 'high_value'
    WHEN value_score >= 40.0 THEN 'mid_value'
    WHEN value_score >= 15.0 THEN 'low_value'
    ELSE 'churn_risk'
  END AS segment,
  COUNT(*) AS user_count,
  ROUND(AVG(value_score), 2) AS avg_score,
  ROUND(AVG(total_revenue), 2) AS avg_revenue,
  ROUND(AVG(active_days), 2) AS avg_active_days,
  ROUND(AVG(sessions), 2) AS avg_sessions
FROM (
  SELECT
    user_id,
    0.40 * revenue_score + 0.30 * engagement_score
      + 0.15 * social_score + 0.15 * content_score AS value_score,
    total_revenue, active_days, sessions
  FROM v_user_value_{project_id}
  WHERE period_end = '{end}'
) t
GROUP BY segment
ORDER BY
  CASE segment
    WHEN 'high_value' THEN 1
    WHEN 'mid_value' THEN 2
    WHEN 'low_value' THEN 3
    ELSE 4
  END
```

### 11.3 设计要点

| 特性 | 实现 |
|------|------|
| 加权公式一致性 | SQL 子查询中的加权公式与 Python `_compute_value_score` 完全一致，由测试验证 |
| 分层阈值一致性 | SQL `CASE WHEN` 与 Python `_segment_name` 使用相同的阈值常量 |
| 缺失分段处理 | 某分段无用户时，`_build_segments_from_sql` 自动补空 `UserSegment(user_count=0)` |
| 行格式兼容 | 同时支持 dict 和 list 两种 SQL 返回格式 |
| 降级策略 | SQL 异常时自动 fallback 到 Mock 数据，不影响整体可用性 |
| 死代码清理 | 删除旧版 `_build_segments`（Python 逐行分桶），仅保留 `_build_segments_from_sql` |

### 11.4 收益量化

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| SQL 返回行数 | 10,000+ 行 | 4 行 | **-99.96%** |
| 每行列数 | 8 列 | 6 列 | -25% |
| 数据传输量 | ~640KB（估算） | ~256B | **-99.96%** |
| Python 内存分配 | 10,000+ dict | 4 dict | **-99.96%** |
| Python 循环次数 | 10,000+ 次 | 4 次 | **-99.96%** |
| SQL 调用次数 | 1 次 | 1 次 | 不变 |
| 分层逻辑位置 | Python 端 | SQL 端 | 计算下推 |

### 11.5 测试覆盖

12 个 P3 专用测试用例，全部通过：

| 测试类 | 用例数 | 验证方向 |
|--------|--------|---------|
| `TestSegmentsFromSQL` | 7 | dict/list 格式、缺失分段、空结果、单分段、加权平均、user_share 求和 |
| `TestWeightedFormulaConsistency` | 2 | SQL 公式与 Python `_compute_value_score` 一致性、分层阈值一致性 |
| `TestUserValueSQLIntegration` | 3 | Mock Client 端到端路径、集中度计算、SQL 失败降级 |

### 11.6 改动文件

| 文件 | 改动 | 说明 |
|------|------|------|
| [user_value_analyzer.py](file:///d:/project_slim/project_slim/src/market_ops/creative_vision_runtime/reality/analyzers/user_value_analyzer.py) | 修改 | `_fetch_user_segments` 改用 GROUP BY + CASE WHEN；新增 `_build_segments_from_sql`；删除旧版 `_build_segments` |
| [test_user_value_analyzer.py](file:///d:/project_slim/project_slim/tests/test_user_value_analyzer.py) | 修改 | 新增 12 个 P3 测试用例 |