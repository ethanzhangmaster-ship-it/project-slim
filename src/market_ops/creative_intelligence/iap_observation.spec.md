# IAP Observation Layer Spec v1.0

> **FinalBandit 不变**。本层独立，只输出 `quality_score` 给 Bandit。
> 任何代码修改必须遵循此 Spec。

---

## §1 设计目标

让系统适配海外 IAP（内购）产品。FinalBandit 不再直接学习 CTR/ROAS，而是学习 **Creative Quality**。

### 核心约束（强约束）

- ❌ FinalBandit 算法（theta/sigma/trials/rank/sample）封版，禁止修改
- ❌ Bandit 不允许直接接收 CTR/ROAS/Purchase/Revenue
- ❌ 不允许绕过 Observation Builder 直接喂 reward
- ✔ Bandit 只接收 `quality_score`（0~1）
- ✔ 所有原始指标进入 `CreativeObservation`
- ✔ 支持 delayed reward 回流 + replay 幂等
- ✔ 支持最低样本过滤（anti-noise）
- ✔ 每个 quality_score 必须可解释来源

---

## §2 数据流

```
Facebook / Adjust → CreativeObservation → QualityScoreBuilder → quality_score → FinalBandit
```

FinalBandit 不允许知道：CTR / ROAS / Purchase / Facebook。
只接收：`quality_score`（float, 0~1）。

---

## §3 核心对象

### CreativeObservation（唯一观测对象）

| 字段组 | 字段 | 类型 |
|---|---|---|
| 标识 | creative_id / campaign_id / adset_id / date | str |
| Facebook 投放 | impression / click / ctr / install / cvr / cpi / ipm / spend | int/float |
| Adjust 内购（分天） | purchase_d0/d1/d3/d7 | int |
| Adjust 收入（分天） | revenue_d0/d1/d3/d7 | float |
| Adjust ROAS（分天） | roas_d0/d1/d3/d7 | float |
| 付费率 | pay_rate_d0/d1 | float |
| 元数据 | collected_at / data_source | str |

**所有指标进入 Observation，禁止直接进入 Bandit。**

### QualityScore

| 字段 | 类型 | 说明 |
|---|---|---|
| score | float (0~1) | 唯一传给 Bandit 的值 |
| stage | int (1~4) | 4 阶段评分所属阶段 |
| maturity | float (0~1) | 数据成熟度 |
| sufficient_data | bool | 是否过门槛 |
| components | dict | explainability 来源 |

---

## §4 4 阶段 IAP 评分

随时间推移，CTR 权重逐步让位给 ROAS/Revenue 权重。

| Stage | 时间窗 | 权重构成 |
|---|---|---|
| Stage 1 | < 24h | CTR 20% + CVR 30% + IPM 30% + Install 20%（**禁用 ROAS D7**） |
| Stage 2 | 24h~72h | CTR 10% + CVR 20% + PurchaseRate 30% + RevenueD0 20% + ROAS D1 20% |
| Stage 3 | 3~7 天 | CTR 5% + CVR 15% + PurchaseRate 25% + RevenueD3 25% + ROAS D3 30% |
| Stage 4 | 7 天+ | ROAS D7 40% + Revenue D7 30% + PayRate 20% + CVR 5% + CTR 5% |

归一化：稳定 sigmoid `x/(1+|x|)` 映射到 [0,1]。

---

## §5 Observation Maturity

`maturity = hours_since_install / 168`，clamp 到 [0,1]。

| 安装后时间 | maturity |
|---|---|
| 2 小时 | ≈ 0.01 |
| 24 小时 | ≈ 0.14 |
| 72 小时 | ≈ 0.43 |
| 7 天 | ≈ 1.0 |

---

## §6 Delayed Reward + Replay 幂等

### Delayed Reward

支持迟到收入回流：
- 今天：ROAS=0
- 三天后：ROAS 更新
- 系统必须重新计算 QualityScore 并重新生成 Observation

### Replay 幂等

`ObservationStore.ingest(obs)`：
- key = `f"{creative_id}:{date}"`
- 新数据 → 返回 True
- 已存在但有新 revenue → `max()` 合并字段，返回 True
- 完全相同 → 返回 False（幂等）

`FinalBandit.update()` 只针对新增 Observation，不得重复学习。靠 `has_learned_on_date(gene_type, gene_value, date_str)` 工程层去重保证。

---

## §7 Anti-Noise 最低样本门槛

`QualityScoreBuilder`：

```python
MIN_IMPRESSIONS = 100
MIN_CLICKS = 5
MIN_INSTALLS = 1
```

三个条件**必须同时满足**。不满足时：
- `sufficient_data = False`
- `score = 0.0`
- **禁止进入 Bandit**（调用方需判断 sufficient_data，False 时跳过 `bandit.update`）

---

## §8 Explainability

`QualityScore.components` 字典结构：

```python
{
    "ctr": {"value": 0.02, "weight": 0.10, "score": 0.002},
    "cvr": {"value": 0.05, "weight": 0.20, "score": 0.01},
    ...
}
```

每个维度存原始值、权重、归一化后得分。

`QualityScore.explain()` 输出：
```
Stage 4 | Quality=0.82 | roas_d7: 0.85 (w=40%) | revenue_d7: 0.80 (w=30%) | ...
```

Dashboard 必须展示当前所有 Creative 的 maturity + QualityScore 来源。

---

## §9 接入生产链路（核心改造点）

### §9.1 `scripts/run_pipeline.py` step3_learn

**改造前**（旧 reward，禁止保留）：

```python
roas_score = sigmoid((roas - b_roas) / max(b_roas, 1e-6))
cpi_score = sigmoid((b_cpi - cpi) / max(b_cpi, 1e-6))
reward = 0.6 * roas_score + 0.4 * cpi_score
monitor.update(gt, gv, reward)
```

**改造后**：

```python
from market_ops.creative_intelligence.iap_observation import (
    CreativeObservation, QualityScoreBuilder,
)
obs = CreativeObservation(
    creative_id=..., date=date_str,
    impression=arm["imp"], click=int(ctr/100*arm["imp"]),
    ctr=arm["ctr"], install=arm["installs"], spend=arm["spend"],
    roas_d7=arm["roas"],
)
obs.cvr = obs.install / max(obs.click, 1)
obs.cpi = obs.spend / max(obs.install, 1)
obs.ipm = obs.install / max(obs.impression, 1) * 1000
qs = QualityScoreBuilder().build(obs)
if not qs.sufficient_data:
    continue  # anti-noise: 不过门槛不进 Bandit
monitor.update(gt, gv, qs.score)
```

### §9.2 `src/market_ops/creative_intelligence/experiment_engine.py` backfill_results

**改造前**（deprecated）：

```python
reward = self._compute_reward_v2(ctr, roas_d7, impressions, baseline_ctr, baseline_roas)
```

**改造后**：

```python
reward = self._compute_quality_score(
    creative_id=creative_id, ctr=ctr, roas_d7=roas_d7,
    impressions=impressions, clicks=clicks, installs=installs,
    spend=spend, date=today,
)
if reward < 0:  # insufficient_data 哨兵
    continue
```

### §9.3 不允许改动的文件

- `final_bandit.py`（Spec §13 封版）
- `iap_observation.py`（已完整实现，本次只接入不重写）

---

## §10 8 问验收

`scripts/verify_iap_observation.py` 必须真正验证生产路径：

| # | 问题 | 验收逻辑 |
|---|------|----------|
| ① | FinalBandit 是否完全保持不变？ | git diff final_bandit.py 为空 |
| ② | 所有数据先进入 Observation Builder？ | run_pipeline.py / experiment_engine.py 不再直接算 `0.6*roas+0.4*cpi` |
| ③ | Bandit 只接收 Quality Score？ | grep 生产路径调用 `bandit.update` 时 reward 来源是 `qs.score` |
| ④ | 支持 Delayed Revenue 回流？ | ObservationStore `_has_new_revenue` + max 合并 |
| ⑤ | 支持 Observation Maturity？ | maturity ∈ [0,1]，基于安装后时间 |
| ⑥ | 支持 Replay 幂等？ | 相同数据再 ingest 返回 False |
| ⑦ | 支持最低样本过滤？ | imp<100 / click<5 / install<1 → sufficient_data=False |
| ⑧ | 可以解释每个 Quality Score 来源？ | components dict 非空 + explain() 输出 |

全部 PASS 后，FinalBandit 不再修改，进入真实 Facebook 小流量验证。

---

## §11 版本

- v1.0 (2026-06-29): 首版，IAP Observation Layer 接入生产链路
