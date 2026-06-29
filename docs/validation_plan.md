# FinalBandit 小流量真实验证方案

## 数据现状

- `creative_performance`: 984 行, 588 个 creative, 仅 1 天数据 (2026-05-27)
- `creative_features`: 424 个 creative 有视觉特征, 但 `hook_type` 全部为空
- 交叉: 0 个 creative 同时满足 "有 feature + 500+ impressions"

## 结论: 当前数据不足以按 hook_type/subject_type 做 Bandit 学习

FinalBandit 需要 `gene_type` (如 hook_type) + `gene_value` (如 mystery) 来建立 arm。
但 creative_features 表中这些字段全是空的。需要先补齐特征数据。

---

## Phase 1: 补齐特征数据 (前置条件)

### 1.1 从 creative_features 中提取可用的特征

当前 creative_features 中有值的字段:

| 字段 | 有值比例 (估算) | 可用作 gene_type |
|------|:---:|------|
| primary_color | 高 | color_tone |
| warm_cool | 高 | color_tone |
| subject_type | 中 | subject |
| has_ui / has_reward / has_text | 高 | game_element |
| left_right_layout / center_layout | 高 | layout |

### 1.2 动作

Step 1: 运行分析脚本, 确认哪些 feature 字段有足够的数据覆盖
Step 2: 将 feature 值映射到 FeatureSpace 枚举
Step 3: 补全 hook_type (可先用 has_ui/has_text/has_reward 等布尔字段推导)

---

## Phase 2: 小流量验证 (特征数据就绪后)

### 2.1 验证范围

| 参数 | 值 |
|------|-----|
| 维度 | 选 2-3 个 gene_type (如 color_tone, layout, game_element) |
| 每个 gene_type 的 arm 数 | 2-5 个 (选有 ≥500 impressions 的 creative) |
| 验证天数 | 7 天 |
| 每天 backfill 次数 | 1 次 (cron) |
| Budget 模拟 | 不需要真实 budget, 用 historical data replay |

### 2.2 验证指标

| 指标 | 判定标准 | 检查方法 |
|------|----------|----------|
| theta 排序稳定性 | flip_rate < 0.3 (7 天) | Monitor Dashboard |
| sigma 下降 | decline_ratio < 0.9 | Monitor Dashboard |
| 去重生效 | 重复 backfill 后 dup_rejects = 100% | Monitor health |
| entropy 不崩塌 | late_entropy > early_entropy × 0.3 | Monitor Dashboard |
| ranking 合理 | 高 ROAS creative 的 theta 排名靠前 | Arm State 表 |

### 2.3 判定标准

| 结果 | 条件 |
|------|------|
| ✅ GO | 5/5 指标通过 → 可以扩大维度 |
| ⚠️ HOLD | 3-4/5 通过 → 需要调参后重试 |
| ❌ NO-GO | <3/5 通过 → 需要排查数据质量 |

---

## Phase 3: 真实投放验证 (Phase 2 通过后)

### 3.1 最小投放单元

- 选 1 个 gene_type (如 layout), 3 个 arm (left_right, center, top_bottom)
- 每个 arm 生成 2-3 张图片
- 1 个 Facebook campaign, 1 个 adset
- Daily budget: $20-50
- 投放 7 天

### 3.2 数据回收

- 每天 cron 运行 `backfill_results()` 拉取 Facebook 数据
- Monitor Dashboard 实时观察 theta/sigma 变化
- 7 天后对比 FinalBandit ranking vs 真实 ROAS ranking

---

## 立即可以做的

**特征数据补全脚本** — 从 creative_features 提取可用的特征, 映射到 FeatureSpace, 写入 variant 表。
这是最紧急的前置工作，做完才能跑 Phase 2。
