# Experiment System v1.0（最终稳定版）

---

# ① Production Spec（唯一系统真相）

任何代码修改必须严格遵循此 Spec，不得引入额外层级或兼容逻辑。

---

## §1 系统目标

构建 A/B 实验生成 → 投放 → 归因 → Bandit 更新的闭环系统。

---

## §2 核心对象（字段级定义）

### FeatureSpace

```
feature_id: str
name: str
domain: str
values: list[str]
```

### ExperimentVariant

```
variant_id: str
experiment_id: str
features: dict[str, str]
weight: float
```

### Experiment

```
experiment_id: str
project: str
type: enum(CREATIVE, AUDIENCE, STRUCTURAL)
status: enum(RUNNING, STOPPED, WON, LOST)
variants: list[ExperimentVariant]
hypothesis: str
created_at: timestamp
```

---

## §3 唯一数据流

```
Generate → Log → Publish → Run → Backfill → Bandit Update
```

| 步骤 | 动作 | 数据库 |
|---|---|---|
| **Generate** | 创建 Experiment + Variants | 只读 Bandit |
| **Log** | 写入 DuckDB（唯一写入口） | **写** experiment + variant |
| **Publish** | 推送广告平台 | 写 experiment（更新 status/ad_id） |
| **Run** | 真实投放 | 无（外部） |
| **Backfill** | 回收 performance | **读** creative_performance → **写** metrics |
| **Bandit Update** | 更新权重与选择策略 | 只写 Bandit memory |

---

## §4 系统约束（强约束）

- ❌ 不允许绕过 Bandit 进行 variant 选择
- ❌ 不允许新增数据表（除 experiment / variant / metrics）
- ❌ 不允许在代码中加入 migration logic
- ❌ 所有写操作必须通过 `log_experiment()`
- ❌ performance 数据只能由 `backfill_results()` 写入
- ✔ FeatureSpace 必须固定枚举值
- ✔ 所有实验必须可回放（deterministic）

---

## §5 外部依赖接口

```
FinalBandit.sample(gene_type) → gene_value  (Spec §13 封版)
FacebookPublisher.publish(experiment)
DuckDB:
    INSERT experiment
    INSERT variant
    UPDATE metrics
```

---

## §6 唯一写路径

所有 experiment 写入必须通过：

```
log_experiment(experiment)
```

所有 performance 写入必须通过：

```
backfill_results(experiment_id)
```

---

## §7 扩展规则（极强约束）

任何新增能力必须：

1. 修改 Spec
2. 版本号 +1
3. 更新 FeatureSpace
4. 修改 Engine
5. 回归测试

❌ 不允许：

- 直接改代码加逻辑
- bypass Spec
- 临时 workaround

---

---

# ② Runtime Policy（投放运行层）

不进入代码，不影响系统结构，仅控制运行行为。

---

## 1. Budget 结构

| Pool | 占比 |
|---|---|
| Cold Start Pool | 70% |
| Exploit Pool | 25% |
| Safety Pool | 5% |

单 Adset：

- $5–$20 / day
- ≤10% total budget / experiment
- ❌ 不允许 scale before 24h
- ❌ 不允许跨 experiment 合并预算

---

## 2. Experiment Density

| 阶段 | 密度 |
|---|---|
| Day 1–3 | 3–5 / day |
| Day 4–7 | 5–10 / day |
| Stable | ≤15 / day |

约束：

- 每 feature slot ≤ 2 active variants
- 每变量 ≤ 3-way test

---

## 3. Bandit Gate（放量条件）

满足任一：

- CTR ≥ baseline +20%
- CPI ≤ baseline -15%
- ROAS ≥ 1.2×

门槛：

- impressions ≥ 1000 / variant
- clicks ≥ 50 / variant

---

## 4. Rollback Rules

### 单 Experiment

触发：

- CTR < 0.5× baseline（持续 6h）
- CPI > 2× baseline
- spend > $30 且 0 conversion

动作：

- stop adset
- mark FAILED
- apply bandit penalty

### 全局 Rollback

触发：

- 3 个连续失败 experiment
- ROAS < 0.8

动作：

- freeze generation
- only exploit pool
- reduce bandit temperature

---

## 5. Experiment 类型分配

| 类型 | 占比 |
|---|---|
| Creative | 60% |
| Audience | 25% |
| Structural | 15% |

---

## 6. Launch Phase

| Phase | 内容 |
|---|---|
| Phase 1 | Creative only |
| Phase 2 | Audience + Bandit selection |
| Phase 3 | Exploit scaling |

---

## 7. System Runtime Loop

```
Generate → Log → Run → Backfill → Bandit Update → Select → Repeat
```

硬约束：

- 没有 backfill → 不允许 generate 新 experiment（同维度）

---

---

## §8 Patches (v1.1 — 收敛修复)

基于 Stability Audit 发现的 Critical Failures，做 3 个最小补丁，不重构系统。

### 8.1 Patch-1: Backfill 去 snapshot 化（rolling 7 天）

**问题**：`ORDER BY date DESC LIMIT 1` 只取最新一天，学"最后一天噪声"，T+1~T+7 延迟转化未回流时数据不完整。

**修复**：改为 rolling 7 天 SUM 聚合，ctr/cpi 从 SUM 值重算，roas_d7 用 spend 加权平均。

```sql
SELECT
    COALESCE(SUM(impression), 0),
    COALESCE(SUM(click), 0),
    COALESCE(SUM(spend), 0),
    COALESCE(SUM(install), 0),
    COALESCE(SUM(roas_d7 * spend) / NULLIF(SUM(spend), 0), 0)
FROM creative_performance
WHERE creative_id = ?
  AND CAST(date AS DATE) >= CURRENT_DATE - 7
```

**目的**：去掉 day noise，引入稳定 reward surface。

### 8.2 Patch-2: Judge Win 加 sample gating

**问题**：10 impressions 1 click → CTR=10% → 判 win，early random spike 污染 bandit。

**修复**：`_judge_win` 最前面加 sample gating，不满足门槛返回 `None`（不参与 bandit）。

```
if impressions < 1000 or clicks < 50:
    return None  # 不参与 bandit 学习
```

**返回值变化**：`bool` → `bool | None`。`None` 表示样本不足，写 metrics 但不调 `_update_bandit`，不判胜负。

### 8.3 Patch-3: Bandit update 去重复学习

**问题**：backfill 每跑一次 = `update_arm` 一次，cron/replay 导致 trials 放大。

**修复**：in-process cache，同 `(experiment_id, variant_id, date)` 一天内只学习一次。

```
key = f"{experiment_id}:{variant_id}:{date}"
if key in seen_updates: return
seen_updates.add(key)
```

**约束**：纯 runtime protection，不动数据库结构。

---

## §9 Reward Shaping v2 (Continuous + Baseline Normalization)

把"绝对阈值判定 win/lose"改成"相对性能连续奖励信号"。
本质:把 Facebook noisy auction signal → 转换成 stationary reward process。

### 9.1 连续 reward function（替换 _judge_win）

**Step 1: baseline（project-level rolling 7 天）**
```
baseline_ctr  = median(ctr of all variants, last 7 days)
baseline_roas = median(roas_d7 of all variants, last 7 days)
```

**Step 2: 标准化**
```
ctr_norm  = (ctr  - baseline_ctr)  / (baseline_ctr + 1e-6)
roas_norm = (roas_d7 - baseline_roas) / (baseline_roas + 1e-6)
```

**Step 3: 连续 reward（固定 sigmoid）**
```
sigmoid(x) = x / (1 + abs(x))   # 比 exp 稳定,避免 saturation
reward = 0.6 * sigmoid(ctr_norm) + 0.4 * sigmoid(roas_norm)
```

**Step 4: sample gating（弱化）**
```
if impressions < 500:
    reward = 0.5  # neutral prior
```

返回值:`bool | None` → `float`（范围 -1 ~ 1）。

### 9.2 Bandit 配套（EMA reward）

`update_arm` 改为 EMA:
```
arm.value = 0.9 * arm.value + 0.1 * reward
```

删除: wins / losses / is_win 参与评分。

`select_gene` 改为 mean + uncertainty:
```
score = arm.value + 0.5 * sqrt(log(total_steps + 1) / (n + 1))
```

### 9.3 行为变化

- before (v1): winner flip / 0-1 spike / oscillation
- after (v2): reward 曲线连续平滑 / arm ranking 稳定收敛 / exploration 只在 uncertainty 驱动

### 9.4 判定标准

| 指标 | PASS 条件 |
|---|---|
| flip_rate | < 0.25 |
| signal_corr (真实质量 vs reward) | > 0.6 |
| variance ratio | 0.8 ~ 1.5 |
| convergence time | winner stabilizes before 40% of horizon |

---

## §10 Reward Entropy Injection v3 (Controlled Stochasticity)

v2 问题: 系统过早"确定化" → exploration collapse → 冻结在局部最优。
v3 目标: 不是提升 accuracy,而是控制 bandit 学习的信息熵流速(learning bandwidth)。
本质: 防止模型进入"过拟合自己历史"的状态 — 让 bandit 不会变笨。

### 10.1 三层结构

**Layer 1 — Base Reward (保持 v2)**
```
r_base = v2_reward(ctr, roas, baseline)
```

**Layer 2 — Entropy Gate (新增)**
```
entropy = std([arm.value for arm in arms])  # 系统当前确定度
```

**Layer 3 — Information Injection (核心)**
```
noise_scale = clamp(0.15 * (1 - entropy), 0.02, 0.15)
reward_v3 = r_base + Normal(0, noise_scale)
```

### 10.2 关键机制

- Case A (系统太确定): entropy ↓ → noise ↑ → 强制 exploration
- Case B (系统太混乱): entropy ↑ → noise ↓ → stabilize learning

### 10.3 Bandit 改动 (核心)

**新 state**: `arm.value`, `arm.uncertainty`, `arm.information_gain`

**update rule (替换 v2 EMA)**:
```
prediction_error = reward - arm.value
arm.value += 0.1 * prediction_error
arm.uncertainty = 0.9 * arm.uncertainty + 0.1 * abs(prediction_error)
```

**selection rule (核心变化)**:
```
score = arm.value + 0.5 * arm.uncertainty + entropy_bonus
```

### 10.4 新增关键指标

| 指标 | 定义 | 目标 |
|---|---|---|
| Learning Bandwidth | std(reward trajectory over time) | 0.08 ~ 0.18 |
| Entropy Stability | entropy 应振荡不崩塌 | 不单调趋近 0 |
| Exploration Persistence | % of non-greedy selections | > 5% |

### 10.5 判定标准

| 指标 | PASS 条件 |
|---|---|
| correctness (继承 v2) | corr > 0.9 |
| stability (继承 v2) | flip_rate < 0.1 |
| entropy health (新增核心) | 0.08 < reward_std < 0.18 |
| exploration alive | explore_rate > 5% |

### 10.6 系统行为对比

- v1: random oscillation
- v2: deterministic convergence
- v3: controlled stochasticity (黄金状态)

---

## §11 Policy-driven Entropy Bandit v4 (范式转换)

v1~v3 根因: reward 被 noise/EMA/threshold 扭曲, exploration 被附加项控制, bandit 在做"评分函数优化"而非"信息最大化"。
v4 范式: 彻底放弃 reward 作为决策中心, 让 bandit 变成"基于不确定性的策略生成器"。

### 11.1 范式对比

| 维度 | v1~v3 | v4 |
|---|---|---|
| decision | reward → value → argmax | observation → belief → policy → stochastic sample |
| reward role | central (truth) | observational (noisy signal) |
| exploration | 附加项 / ratio | 从 uncertainty 结构中自然涌现 |
| collapse risk | 高 | 低 |
| Facebook 适配 | ❌ | ✅ (reward is delayed/noisy/auction-coupled) |

### 11.2 核心结构

```
observation (CTR/ROAS)
    ↓
belief state updater (Bayesian: value + variance, n)
    ↓
policy scorer (value + c1*sqrt(var/n) + c2*info_gain + c3*entropy_pressure)
    ↓
action selection (softmax sampling, NOT argmax)
```

### 11.3 Arm 结构

```
class PolicyArm:
    value: float          # posterior mean
    variance: float       # uncertainty
    n: int                # sample count
    last_update: int
    success_rate: float   # smoothed win rate
```

### 11.4 Observation → belief update (Bayesian-style)

```
delta = score - arm.value
arm.value += alpha * delta
arm.variance = (1 - beta) * arm.variance + beta * (delta ** 2)
arm.n += 1
```

### 11.5 Policy Score (核心)

```
score = arm.value
      + c1 * sqrt(arm.variance / (arm.n + 1))   # UCB 项
      + c2 * information_gain(arm)                # 信息增益
      + c3 * global_entropy_pressure              # 全局熵压
```

**Information Gain**: `info_gain = arm.variance * (1 / (arm.n + 1))` (越不确定越值得探索)

**Entropy Pressure**: `clamp(0.3 * (1 - entropy/entropy_target), 0.0, 0.5)` (entropy 低 → 强制探索)

### 11.6 Selection (stochastic, NOT greedy)

```
scores = [policy_score(a) for a in arms]
return softmax_sample(scores, temperature=0.2)
```

### 11.7 关键约束

- ❌ reward 完全退出 decision loop (仅用于 update belief)
- ❌ selection 不再 deterministic argmax
- ❌ 删除 explore_ratio (exploration 从 uncertainty 涌现)
- ✅ softmax sampling + entropy floor

### 11.8 系统行为

| 阶段 | entropy | exploration | ranking |
|---|---|---|---|
| early | high | high | unstable |
| mid | collapses | winner emerges | stabilizing |
| late | soft convergence | occasional exploration persists | stable |

### 11.9 判定标准

| 指标 | PASS 条件 |
|---|---|
| correctness | corr > 0.85 |
| stability | flip_rate < 0.15 |
| exploration alive | explore_rate > 8% |
| soft convergence | late explore_rate > 3% (不 hard lock) |

---

## §12 Facebook Reality Layer + Allocation v5

v4 问题: 没建模 auction, 没建模 delay, 没建模 budget coupling。
v5 范式: 不再假设 "reward = signal", 显式建模 "signal = latent θ + auction distortion + delay noise"。
bandit 变成 latent state estimator + policy allocator。

### 12.1 系统架构

```
Facebook Auction (external noise generator)
    ↓
Observation Normalizer (auction distortion removal + budget normalization)
    ↓
Latent Performance Model (true creative quality θ)
    ↓
Belief Update (Bayesian + EMA hybrid)
    ↓
Policy Engine (θ + uncertainty + entropy - auction_pressure)
    ↓
Allocation Engine (soft budget routing)
```

### 12.2 Auction Pressure Model (核心新增)

Facebook 问题: performance ≠ creative quality (CPM 波动 / auction competition / budget pacing)

```
auction_pressure = 0.4 * CPM_ratio
                 + 0.3 * impression_share_drop
                 + 0.3 * budget_competition_index
```

简化版 (可用现有数据): `auction_pressure = CPM / baseline_CPM`

**修正 observation**: `true_signal = observed_ROAS / auction_pressure`

### 12.3 Latent Performance State

真实: hidden creative quality θ
观测: `reward = θ × auction_noise × delay_noise`

**更新**: `θ_hat = EMA(auction_corrected_reward)`

### 12.4 Delay-aware Correction

Facebook T+1/T+3/T+7 回流:

```
final_reward_t = r_t + λ1 * r_{t+1} + λ2 * r_{t+3}
```

或: `credit_assignment = time_decay_weight(installs)`

### 12.5 Policy Engine v2 (升级)

```
score = θ_hat
      + α * uncertainty
      + β * entropy_pressure
      - γ * auction_pressure
```

关键变化: 减去 auction_pressure (高 auction 压力 → score 降低 → 少分配 budget)。

### 12.6 Allocation Engine (Facebook 关键缺失)

bandit 选 arm, 但 Facebook 还需要 budget allocation:

```
budget_share_i = softmax(score_i) × stability_factor
stability = 1 / (1 + variance_i)
```

防止 unstable creative 吃预算。

### 12.7 系统行为变化

| 层 | v4 | v5 |
|---|---|---|
| auction | 未建模 | external noise generator (剥离) |
| model | observed reward | latent θ estimation |
| policy | entropy + uncertainty | + auction_pressure |
| allocation | 单 arm 选择 | soft budget routing |

### 12.8 解决的 3 个核心失败

| 问题 | v5 解决方式 |
|---|---|
| auction 污染 | auction_pressure 修正 |
| delayed attribution | temporal credit assignment |
| budget 干扰 | allocation engine |

### 12.9 判定标准

| 指标 | PASS 条件 |
|---|---|
| correctness | corr(true_θ, θ_hat) > 0.85 |
| auction robustness | 高 auction noise 下 corr 下降 < 10% |
| allocation stability | budget_share variance < 0.15 |
| delay robustness | T+3 延迟下归因误差 < 15% |

---

## §13 Final Architecture (封版)

**本节为唯一算法真相。§9-§12 全部 deprecated,仅保留为历史记录。**

完成后不允许 v7/v8/v9 或任何新算法层。后续仅允许:参数调优、工程实现(DB/Pipeline/Facebook API)、监控运维。

### 13.1 唯一 State (每个 Arm 只允许 3 个字段)

```
theta    // quality estimate
sigma    // uncertainty
trials   // sample count
```

禁止: value / weight / score / reward_avg / ucb_score / confidence_score / policy_score_cache / uncertainty / information_gain / success_rate / n_updates

### 13.2 唯一 Update

```
delta = reward - theta
theta += alpha * delta
sigma = (1 - beta) * sigma + beta * abs(delta)
trials += 1
```

禁止: reward shaping / winner-loser / threshold / EMA reward / 多层 smoothing

### 13.3 Reward 定位

Reward = Observation。不得参与 Decision、不得排序、不得进入 Policy Score、不得保存为状态。

### 13.4 唯一 Decision

```
Ranking = theta DESC
```

禁止: reward / UCB / auction / entropy / baseline score 参与最终 Ranking。

### 13.5 Exploration (只影响 Sampling,不影响 Ranking)

```
Sampling = Softmax(theta/tau + gamma*sigma)
```

禁止: score += entropy / score += auction / score += reward / score += bonus

### 13.6 Entropy (系统状态,不是 Arm 状态)

```
entropy = std([arm.theta for arm in arms])
tau = auto_adjust(entropy)   // 只调温度,不进 ranking
```

禁止: entropy 进入 ranking / theta / reward / observation

### 13.7 Auction (仅 Diagnostic)

Auction 信息只能用于: Diagnostic / Logging / Dashboard / Analysis。
禁止: 进入 Decision / Policy / Ranking / Sampling Score

### 13.8 Facebook 数据 (只产生 Observation)

CTR/CPI/ROAS/Spend/Conversion → reward → 结束。不得继续影响其它模块。

### 13.9 唯一数据流

```
Facebook API → Observation → Reward → Update(theta,sigma) → Policy(theta DESC) → Sampling → Facebook
```

### 13.10 封版约束

- ❌ 不允许新增 reward 层
- ❌ 不允许新增 entropy 层
- ❌ 不允许新增 score
- ❌ 不允许新增 policy
- ❌ 不允许新增 optimizer
- ❌ 不允许新增 correction
- ❌ 不允许新增版本
- ✔ 仅允许: 参数调优 (alpha/beta/tau/gamma)
- ✔ 仅允许: 工程优化 (DB/Pipeline/Facebook API)
- ✔ 仅允许: 监控运维

---

## 版本历史

| 版本 | 日期 | 状态 | 变更 |
|---|---|---|---|
| v1.0 | 2026-06-26 | deprecated | Production Spec + Runtime Policy |
| v1.1 | 2026-06-26 | deprecated | rolling backfill + sample gating |
| v2.0 | 2026-06-26 | deprecated | Reward Shaping |
| v3.0 | 2026-06-26 | deprecated | Entropy Injection |
| v4.0 | 2026-06-26 | deprecated | Policy-driven Bandit |
| v5.0 | 2026-06-26 | deprecated | Facebook Reality Layer |
| **Final** | **2026-06-26** | **ACTIVE** | **Final Architecture: theta/sigma/trials + theta DESC + Softmax sampling. 封版,不再新增算法层** |
